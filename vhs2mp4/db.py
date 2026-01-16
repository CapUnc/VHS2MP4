"""SQLite database helpers and schema initialization.

Global settings (projects + active project) live in a dedicated database,
while each project stores tapes and review queue items in its own database.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from vhs2mp4.config import (
    ensure_local_project_dirs,
    get_global_paths,
    get_project_paths,
)


GLOBAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

PROJECT_SCHEMA = """
CREATE TABLE IF NOT EXISTS tapes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tape_code TEXT UNIQUE,
    -- Tape label text stays immutable as the source of truth; title can evolve.
    tape_label_text TEXT DEFAULT '',
    label_is_guess INTEGER DEFAULT 0,
    title TEXT NOT NULL,
    source_label TEXT,
    date_type TEXT NOT NULL,
    date_exact TEXT,
    date_start TEXT,
    date_end TEXT,
    date_locked INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'New',
    raw_filename TEXT,
    raw_path TEXT,
    sha256 TEXT,
    ingested_at TEXT,
    backup_status TEXT,
    duration_seconds REAL,
    file_size_bytes INTEGER,
    thumb_path TEXT DEFAULT '',
    thumb_generated_at TEXT,
    scene_suggested INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL,
    tags_json TEXT
);

CREATE TABLE IF NOT EXISTS review_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    type TEXT NOT NULL,
    tape_id INTEGER,
    message TEXT NOT NULL,
    payload_json TEXT,
    FOREIGN KEY (tape_id) REFERENCES tapes(id)
);

CREATE TABLE IF NOT EXISTS segment_suggestions (
    id INTEGER PRIMARY KEY,
    tape_id INTEGER NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    confidence REAL DEFAULT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    notes TEXT DEFAULT '',
    FOREIGN KEY (tape_id) REFERENCES tapes(id)
);

CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY,
    tape_id INTEGER NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    title TEXT DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tape_id) REFERENCES tapes(id)
);
"""


def ensure_global_dirs() -> Path:
    """Ensure global directories exist and return the global database path."""

    paths = get_global_paths()
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    return paths.db_path


def get_global_connection() -> sqlite3.Connection:
    """Create a SQLite connection to the global settings database."""

    db_path = ensure_global_dirs()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_global_db() -> None:
    """Initialize the global database schema if it doesn't exist."""

    conn = get_global_connection()
    try:
        conn.executescript(GLOBAL_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_project_db_path(project_slug: str) -> Path:
    """Return the database path for a project."""

    return get_project_paths(project_slug)["db_path"]


def get_project_connection(project_slug: str) -> sqlite3.Connection:
    """Create a SQLite connection for a project database."""

    ensure_local_project_dirs(project_slug)
    db_path = get_project_db_path(project_slug)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_project_db(project_slug: str) -> None:
    """Initialize the project database schema if it doesn't exist."""

    conn = get_project_connection(project_slug)
    try:
        conn.executescript(PROJECT_SCHEMA)
        ensure_project_schema(conn, project_slug)
        conn.commit()
    finally:
        conn.close()


def ensure_project_schema(conn: sqlite3.Connection, project_slug: str) -> None:
    """Ensure required columns exist for the per-project schema."""

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(tapes)")}
    applied_migrations: list[str] = []

    if "tape_code" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN tape_code TEXT")
        applied_migrations.append("tape_code")
    if "status" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN status TEXT NOT NULL DEFAULT 'New'")
        applied_migrations.append("status")
    if "tags_json" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN tags_json TEXT")
        applied_migrations.append("tags_json")
    if "created_at" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN created_at TEXT NOT NULL")
        applied_migrations.append("created_at")
    if "raw_filename" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN raw_filename TEXT")
        applied_migrations.append("raw_filename")
    if "raw_path" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN raw_path TEXT")
        applied_migrations.append("raw_path")
    if "sha256" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN sha256 TEXT")
        applied_migrations.append("sha256")
    if "ingested_at" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN ingested_at TEXT")
        applied_migrations.append("ingested_at")
    if "backup_status" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN backup_status TEXT")
        applied_migrations.append("backup_status")
    if "tape_label_text" not in columns:
        # Tape label text is immutable source-of-truth separate from display titles.
        conn.execute("ALTER TABLE tapes ADD COLUMN tape_label_text TEXT DEFAULT ''")
        applied_migrations.append("tape_label_text")
    if "label_is_guess" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN label_is_guess INTEGER DEFAULT 0")
        applied_migrations.append("label_is_guess")
    if "duration_seconds" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN duration_seconds REAL")
        applied_migrations.append("duration_seconds")
    if "file_size_bytes" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN file_size_bytes INTEGER")
        applied_migrations.append("file_size_bytes")
    if "thumb_path" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN thumb_path TEXT DEFAULT ''")
        applied_migrations.append("thumb_path")
    if "thumb_generated_at" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN thumb_generated_at TEXT")
        applied_migrations.append("thumb_generated_at")
    if "scene_suggested" not in columns:
        conn.execute("ALTER TABLE tapes ADD COLUMN scene_suggested INTEGER DEFAULT 0")
        applied_migrations.append("scene_suggested")

    if applied_migrations:
        _clear_project_logs(project_slug)
        for migration in applied_migrations:
            logging.info(
                "Applied project tape schema migration",
                extra={
                    "event": "project_schema_migrated",
                    "context": {
                        "project_slug": project_slug,
                        "migration": migration,
                    },
                },
            )

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tapes_tape_code ON tapes(tape_code)"
    )
    conn.execute("UPDATE tapes SET status = 'New' WHERE status IS NULL")
    backfill_tape_codes(conn)
    _create_table_if_missing(
        conn,
        project_slug,
        "review_items",
        """
        CREATE TABLE IF NOT EXISTS review_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            type TEXT NOT NULL,
            tape_id INTEGER,
            message TEXT NOT NULL,
            payload_json TEXT,
            FOREIGN KEY (tape_id) REFERENCES tapes(id)
        )
        """,
    )
    _create_table_if_missing(
        conn,
        project_slug,
        "segment_suggestions",
        """
        CREATE TABLE IF NOT EXISTS segment_suggestions (
            id INTEGER PRIMARY KEY,
            tape_id INTEGER NOT NULL,
            start_seconds REAL NOT NULL,
            end_seconds REAL NOT NULL,
            confidence REAL DEFAULT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            notes TEXT DEFAULT '',
            FOREIGN KEY (tape_id) REFERENCES tapes(id)
        )
        """,
    )
    _create_table_if_missing(
        conn,
        project_slug,
        "segments",
        """
        CREATE TABLE IF NOT EXISTS segments (
            id INTEGER PRIMARY KEY,
            tape_id INTEGER NOT NULL,
            start_seconds REAL NOT NULL,
            end_seconds REAL NOT NULL,
            title TEXT DEFAULT '',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (tape_id) REFERENCES tapes(id)
        )
        """,
    )


def _create_table_if_missing(
    conn: sqlite3.Connection, project_slug: str, table_name: str, ddl: str
) -> None:
    """Create a table if missing, logging when the table is created."""

    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    if row:
        return
    _clear_project_logs(project_slug)
    conn.execute(ddl)
    logging.info(
        "Applied project schema migration",
        extra={
            "event": "project_schema_migrated",
            "context": {"project_slug": project_slug, "migration": table_name},
        },
    )


def _clear_project_logs(project_slug: str) -> None:
    """Clear log file when a migration runs to keep log output focused."""

    logs_dir = get_project_paths(project_slug)["logs_dir"]
    logfile = logs_dir / "app.log"
    logger = logging.getLogger()
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            try:
                if Path(handler.baseFilename) == logfile:
                    handler.acquire()
                    try:
                        if handler.stream:
                            handler.stream.seek(0)
                            handler.stream.truncate()
                    finally:
                        handler.release()
            except OSError:
                continue


def _parse_tape_code(tape_code: str) -> int | None:
    """Parse a tape code like TAPE_0007 into an integer."""

    if not tape_code:
        return None
    if not tape_code.startswith("TAPE_"):
        return None
    suffix = tape_code.split("_", 1)[1]
    if not suffix.isdigit():
        return None
    return int(suffix)


def get_next_tape_code(conn: sqlite3.Connection) -> str:
    """Generate the next sequential tape code using existing entries."""

    rows = conn.execute(
        "SELECT tape_code FROM tapes WHERE tape_code IS NOT NULL"
    ).fetchall()
    max_number = 0
    for row in rows:
        parsed = _parse_tape_code(row["tape_code"])
        if parsed and parsed > max_number:
            max_number = parsed
    return f"TAPE_{max_number + 1:04d}"


def backfill_tape_codes(conn: sqlite3.Connection) -> None:
    """Assign tape codes to any existing rows missing them."""

    rows = conn.execute(
        "SELECT id FROM tapes WHERE tape_code IS NULL OR tape_code = '' ORDER BY id"
    ).fetchall()
    if not rows:
        return
    next_number = _parse_tape_code(get_next_tape_code(conn)) or 1
    for row in rows:
        tape_code = f"TAPE_{next_number:04d}"
        conn.execute(
            "UPDATE tapes SET tape_code = ? WHERE id = ?",
            (tape_code, row["id"]),
        )
        next_number += 1


def get_active_project() -> str | None:
    """Return the active project slug from global settings."""

    conn = get_global_connection()
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'active_project'"
        ).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def set_active_project(project_slug: str) -> None:
    """Set the active project in global settings."""

    conn = get_global_connection()
    try:
        conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES ('active_project', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (project_slug,),
        )
        conn.commit()
    finally:
        conn.close()
    logging.info(
        "Activated project",
        extra={"event": "project_activated", "context": {"project_slug": project_slug}},
    )
