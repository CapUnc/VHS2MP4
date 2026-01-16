"""Ingest ClearClick MP4 files into a project."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from vhs2mp4.config import (
    ensure_nas_project_dirs,
    get_project_paths,
    is_nas_available,
)
from vhs2mp4.db import get_next_tape_code

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InboxFile:
    """Metadata about an inbox file."""

    name: str
    path: Path
    size_bytes: int
    modified_time: str
    status: str
    sha256: str | None
    error: str | None


def is_mp4(path: Path) -> bool:
    """Return True if the path is an MP4 file (case-insensitive)."""

    return path.suffix.lower() == ".mp4"


def format_bytes(size_bytes: int) -> str:
    """Format bytes into a friendly string."""

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.0f} PB"


def compute_sha256(path: Path) -> str:
    """Compute SHA256 for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_conflict_path(directory: Path, filename: str) -> Path:
    """Return a non-conflicting destination path."""

    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        next_name = f"{stem}_{counter}{suffix}"
        candidate = directory / next_name
        if not candidate.exists():
            return candidate
        counter += 1


def list_unassigned_tapes(conn) -> list[dict[str, Any]]:
    """Return tapes that do not yet have raw media assigned."""

    rows = conn.execute(
        """
        SELECT id, title, tape_code, source_label
        FROM tapes
        WHERE status = 'New' AND (raw_path IS NULL OR raw_path = '')
        ORDER BY created_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def list_inbox_files(conn, project_slug: str) -> list[InboxFile]:
    """List MP4 files in the project inbox with ingest status."""

    paths = get_project_paths(project_slug)
    inbox_dir = paths["inbox_dir"]
    existing_hashes = {
        row["sha256"]
        for row in conn.execute(
            "SELECT sha256 FROM tapes WHERE sha256 IS NOT NULL"
        ).fetchall()
    }
    files: list[InboxFile] = []
    for path in sorted(inbox_dir.iterdir()):
        if not path.is_file() or not is_mp4(path):
            continue
        stat = path.stat()
        modified_time = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        status = "new"
        sha256 = None
        error = None
        try:
            sha256 = compute_sha256(path)
            if sha256 in existing_hashes:
                status = "ingested"
        except OSError as exc:
            status = "error"
            error = str(exc)
        files.append(
            InboxFile(
                name=path.name,
                path=path,
                size_bytes=stat.st_size,
                modified_time=modified_time,
                status=status,
                sha256=sha256,
                error=error,
            )
        )
    return files


def _create_review_item(
    conn,
    item_type: str,
    message: str,
    tape_id: int | None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Insert a new review item."""

    conn.execute(
        """
        INSERT INTO review_items (created_at, status, type, tape_id, message, payload_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "open",
            item_type,
            tape_id,
            message,
            json.dumps(payload) if payload else None,
        ),
    )


def _attempt_nas_backup(
    project_slug: str, raw_path: Path
) -> tuple[bool, Path | None, str | None]:
    """Copy a raw file to the NAS backup folder."""

    paths = get_project_paths(project_slug)
    nas_dir = paths["nas_raw_backup_dir"]
    try:
        if not is_nas_available():
            return False, None, "NAS not available"
        if not ensure_nas_project_dirs(project_slug):
            return False, None, "NAS directories could not be created"
        destination = resolve_conflict_path(nas_dir, raw_path.name)
        shutil.copy2(raw_path, destination)
        logger.info(
            "NAS backup completed",
            extra={
                "event": "nas_backup_complete",
                "context": {"source": str(raw_path), "destination": str(destination)},
            },
        )
        return True, destination, None
    except (OSError, TimeoutError) as exc:
        logger.warning(
            "NAS backup failed",
            extra={
                "event": "nas_backup_failed",
                "context": {"source": str(raw_path), "error": str(exc)},
            },
        )
        return False, None, str(exc)


def _report_progress(
    progress: Callable | None, percent: int, step: str, detail: str
) -> None:
    if progress:
        progress(percent, step, detail)


def ingest_inbox_file(
    conn,
    project_slug: str,
    filename: str,
    tape_id: int | None = None,
    progress: Callable | None = None,
) -> dict[str, Any]:
    """Ingest a single inbox file into raw storage and the database."""

    paths = get_project_paths(project_slug)
    inbox_path = paths["inbox_dir"] / filename
    _report_progress(progress, 5, "Validate inputs", f"Checking {filename}")
    if not inbox_path.exists():
        return {"status": "error", "message": f"File not found: {filename}"}
    if not is_mp4(inbox_path):
        return {"status": "error", "message": f"Unsupported file type: {filename}"}

    logger.info(
        "Ingest started",
        extra={"event": "ingest_started", "context": {"file": filename}},
    )

    source_hash = compute_sha256(inbox_path)
    existing = conn.execute(
        "SELECT id FROM tapes WHERE sha256 = ?", (source_hash,)
    ).fetchone()
    if existing:
        logger.info(
            "Ingest skipped (already ingested)",
            extra={
                "event": "ingest_skipped",
                "context": {"file": filename, "tape_id": existing["id"]},
            },
        )
        return {
            "status": "already_ingested",
            "message": f"Already ingested (Tape {existing['id']}).",
            "tape_id": existing["id"],
        }

    if tape_id:
        tape_row = conn.execute(
            "SELECT id FROM tapes WHERE id = ?", (tape_id,)
        ).fetchone()
        if not tape_row:
            return {"status": "error", "message": f"Tape {tape_id} not found."}

    raw_destination = resolve_conflict_path(paths["raw_dir"], inbox_path.name)
    try:
        _report_progress(progress, 15, "Copy files", f"Copying {filename}")
        shutil.copy2(inbox_path, raw_destination)
    except OSError as exc:
        logger.error(
            "Failed to copy to raw storage",
            extra={
                "event": "ingest_copy_failed",
                "context": {"file": filename, "error": str(exc)},
            },
        )
        return {"status": "error", "message": f"Copy failed: {exc}"}
    _report_progress(progress, 40, "Compute checksums", f"Hashing {filename}")
    raw_hash = compute_sha256(raw_destination)
    if raw_hash != source_hash:
        logger.warning(
            "SHA256 mismatch after copy",
            extra={
                "event": "ingest_hash_mismatch",
                "context": {
                    "file": filename,
                    "source_hash": source_hash,
                    "raw_hash": raw_hash,
                },
            },
        )

    _report_progress(progress, 70, "Write DB rows", "Saving ingest metadata")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    if tape_id:
        conn.execute(
            """
            UPDATE tapes
            SET raw_filename = ?, raw_path = ?, sha256 = ?, status = ?, ingested_at = ?,
                backup_status = ?
            WHERE id = ?
            """,
            (
                raw_destination.name,
                str(raw_destination),
                raw_hash,
                "Ingested",
                now,
                None,
                tape_id,
            ),
        )
        logger.info(
            "Tape updated with raw media",
            extra={
                "event": "tape_updated_raw",
                "context": {"tape_id": tape_id, "raw_path": str(raw_destination)},
            },
        )
        created_tape_id = tape_id
    else:
        tape_code = get_next_tape_code(conn)
        title = raw_destination.stem
        conn.execute(
            """
            INSERT INTO tapes
                (tape_code, title, source_label, date_type, date_exact, date_start,
                 date_end, date_locked, notes, created_at, status, tags_json,
                 raw_filename, raw_path, sha256, ingested_at, backup_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tape_code,
                title,
                inbox_path.name,
                "unknown",
                None,
                None,
                None,
                0,
                None,
                now,
                "Ingested",
                None,
                raw_destination.name,
                str(raw_destination),
                raw_hash,
                now,
                None,
            ),
        )
        created_tape_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        _create_review_item(
            conn,
            "needs_metadata",
            "Tape was auto-created from filename. Add label/year/tags when you can.",
            created_tape_id,
            {"priority": "low", "skippable": True},
        )
        logger.info(
            "Tape created from ingest",
            extra={
                "event": "tape_created_from_ingest",
                "context": {"tape_id": created_tape_id, "raw_path": str(raw_destination)},
            },
        )

    # Commit metadata writes promptly so we do not hold a long write transaction
    # while file operations and progress updates are running.
    conn.commit()

    _report_progress(progress, 85, "NAS backup attempt", "Copying to NAS")
    backup_status = "backed_up"
    success, nas_path, error = _attempt_nas_backup(project_slug, raw_destination)
    if not success:
        backup_status = "needs_backup"
        message = (
            f"NAS backup failed for {raw_destination.name} "
            f"to {paths['nas_raw_backup_dir']}"
        )
        _create_review_item(
            conn,
            "needs_backup",
            message,
            created_tape_id,
            {
                "attempted_path": str(paths["nas_raw_backup_dir"]),
                "error": error,
                "raw_path": str(raw_destination),
            },
        )

    conn.execute(
        "UPDATE tapes SET backup_status = ? WHERE id = ?",
        (backup_status, created_tape_id),
    )
    conn.commit()

    logger.info(
        "Ingest completed",
        extra={
            "event": "ingest_completed",
            "context": {
                "file": filename,
                "tape_id": created_tape_id,
                "backup_status": backup_status,
                "nas_path": str(nas_path) if nas_path else None,
            },
        },
    )
    _report_progress(progress, 100, "Done", "Ingest completed")
    return {
        "status": "ingested",
        "message": f"Ingested {filename}.",
        "tape_id": created_tape_id,
        "backup_status": backup_status,
    }


def retry_backup(
    conn, project_slug: str, tape_id: int, raw_path: str
) -> dict[str, Any]:
    """Retry NAS backup for a tape."""

    raw_file = Path(raw_path)
    if not raw_file.exists():
        return {"status": "error", "message": "Raw file not found for retry."}
    if not is_nas_available():
        logger.info(
            "NAS unavailable during backup retry",
            extra={"event": "nas_retry_unavailable", "context": {"tape_id": tape_id}},
        )
        return {
            "status": "error",
            "message": "NAS not available. Backup will remain queued.",
        }

    success, nas_path, error = _attempt_nas_backup(project_slug, raw_file)
    if success:
        conn.execute(
            "UPDATE tapes SET backup_status = ? WHERE id = ?",
            ("backed_up", tape_id),
        )
        return {
            "status": "backed_up",
            "message": f"Backup completed to {nas_path}",
        }

    return {
        "status": "error",
        "message": f"Backup retry failed: {error}",
    }
