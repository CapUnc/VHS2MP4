"""Flask entrypoint for VHS2MP4."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
import json
import logging
import os
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from vhs2mp4.config import (
    ensure_local_project_dirs,
    get_global_paths,
    get_project_paths,
    is_nas_available,
    slugify_project_name,
)
from vhs2mp4.db import (
    get_active_project,
    get_global_connection,
    get_project_connection,
    init_global_db,
    init_project_db,
    set_active_project,
    get_next_tape_code,
)
from vhs2mp4.logging_setup import setup_logging
from vhs2mp4.services.ingest import (
    format_bytes,
    ingest_inbox_file,
    list_inbox_files,
    list_unassigned_tapes,
    retry_backup,
)

STATUS_OPTIONS = ("New", "Ingested", "Mastered", "Reviewed", "Final")
DATE_TYPE_OPTIONS = ("exact", "range", "unknown")

EXPORT_COLUMNS = (
    "tape_code",
    "tape_id",
    "title",
    "tape_label_text",
    "label_is_guess",
    "source_label",
    "date_type",
    "year_exact",
    "year_from",
    "year_to",
    "lock_date",
    "tags",
    "notes",
    "status",
    "created_at",
    "ingested_at",
    "raw_filename",
    "raw_path",
    "sha256",
    "backup_status",
    "review_open_count",
    "last_review_type",
)


def normalize_tags(raw_tags: list[str]) -> list[str]:
    """Normalize tags by trimming, de-duplicating (case-insensitive), and dropping empties."""

    normalized: list[str] = []
    seen = set()
    for raw_tag in raw_tags:
        cleaned = raw_tag.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def get_tag_suggestions(
    conn, limit: int = 30, fallback_tags: list[str] | None = None
) -> list[str]:
    """Return tag suggestions sorted by frequency, then alphabetically."""

    counter: Counter[str] = Counter()
    rows = conn.execute(
        "SELECT tags_json FROM tapes WHERE tags_json IS NOT NULL"
    ).fetchall()
    for row in rows:
        try:
            tags = json.loads(row["tags_json"]) or []
        except json.JSONDecodeError:
            continue
        for tag in tags:
            if isinstance(tag, str) and tag.strip():
                counter[tag.strip()] += 1

    if fallback_tags:
        for tag in fallback_tags:
            if tag:
                counter[tag] += 0

    suggestions = sorted(
        counter.items(), key=lambda item: (-item[1], item[0].lower())
    )
    return [tag for tag, _ in suggestions[:limit]]


def serialize_tags(tags_json: str | None) -> str:
    """Convert a tags JSON string into a comma-separated list."""

    if not tags_json:
        return ""
    try:
        tags = json.loads(tags_json)
    except json.JSONDecodeError:
        return ""
    if not isinstance(tags, list):
        return ""
    cleaned = [tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()]
    return ", ".join(cleaned)


def determine_backup_status(tape_row, needs_backup_open: int) -> str:
    """Return the export-friendly backup status for a tape."""

    # We rely on review items to represent queued backup work because the
    # database doesn't store a NAS destination path yet.
    if needs_backup_open:
        return "queued"
    if tape_row["backup_status"] == "backed_up":
        return "backed_up"
    return "unknown"


def build_master_export_rows(conn) -> list[dict[str, str | int | None]]:
    """Collect tape rows for the master CSV export."""

    rows = conn.execute(
        """
        SELECT
            tapes.id,
            tapes.tape_code,
            tapes.title,
            tapes.tape_label_text,
            tapes.label_is_guess,
            tapes.source_label,
            tapes.date_type,
            tapes.date_exact,
            tapes.date_start,
            tapes.date_end,
            tapes.date_locked,
            tapes.notes,
            tapes.status,
            tapes.created_at,
            tapes.ingested_at,
            tapes.raw_filename,
            tapes.raw_path,
            tapes.sha256,
            tapes.backup_status,
            tapes.tags_json,
            (
                SELECT COUNT(*)
                FROM review_items
                WHERE review_items.tape_id = tapes.id
                  AND review_items.status = 'open'
            ) AS review_open_count,
            (
                SELECT type
                FROM review_items
                WHERE review_items.tape_id = tapes.id
                  AND review_items.status = 'open'
                ORDER BY review_items.created_at DESC
                LIMIT 1
            ) AS last_review_type,
            (
                SELECT COUNT(*)
                FROM review_items
                WHERE review_items.tape_id = tapes.id
                  AND review_items.status = 'open'
                  AND review_items.type = 'needs_backup'
            ) AS needs_backup_open
        FROM tapes
        ORDER BY tapes.created_at DESC
        """
    ).fetchall()

    export_rows: list[dict[str, str | int | None]] = []
    for row in rows:
        export_rows.append(
            {
                "tape_code": row["tape_code"] or "",
                "tape_id": row["id"],
                "title": row["title"] or "",
                "tape_label_text": row["tape_label_text"] or "",
                "label_is_guess": int(row["label_is_guess"] or 0),
                "source_label": row["source_label"] or "",
                "date_type": row["date_type"] or "",
                "year_exact": row["date_exact"] or "",
                "year_from": row["date_start"] or "",
                "year_to": row["date_end"] or "",
                "lock_date": int(row["date_locked"] or 0),
                "tags": serialize_tags(row["tags_json"]),
                "notes": row["notes"] or "",
                "status": row["status"] or "",
                "created_at": row["created_at"] or "",
                "ingested_at": row["ingested_at"] or "",
                "raw_filename": row["raw_filename"] or "",
                "raw_path": row["raw_path"] or "",
                "sha256": row["sha256"] or "",
                "backup_status": determine_backup_status(
                    row, row["needs_backup_open"]
                ),
                "review_open_count": row["review_open_count"] or 0,
                "last_review_type": row["last_review_type"] or "",
            }
        )
    return export_rows


def create_app() -> Flask:
    """Application factory for VHS2MP4."""

    global_paths = get_global_paths()
    setup_logging(global_paths.logs_dir)
    init_global_db()

    active_project = get_active_project()
    if active_project:
        project_paths = ensure_local_project_dirs(active_project)
        setup_logging(project_paths["logs_dir"])
        init_project_db(active_project)

    base_dir = Path(__file__).resolve().parent

    app = Flask(
        __name__,
        template_folder=str(base_dir / "web" / "templates"),
        static_folder=str(base_dir / "web" / "static"),
        static_url_path="/static",
    )
    # Flash messages help confirm actions without adding extra UI complexity.
    app.secret_key = os.environ.get("VHS2MP4_SECRET_KEY", "vhs2mp4-dev-secret")

    @app.before_request
    def ensure_active_project_loaded() -> None | str:
        """Load active project and redirect if needed."""

        g.active_project = get_active_project()
        g.active_project_name = None
        if g.active_project:
            g.project_paths = get_project_paths(g.active_project)
            conn = get_global_connection()
            try:
                row = conn.execute(
                    "SELECT name FROM projects WHERE slug = ?", (g.active_project,)
                ).fetchone()
                g.active_project_name = row["name"] if row else g.active_project
            finally:
                conn.close()
        else:
            g.project_paths = None
        allowed_endpoints = {"projects", "create_project", "activate_project", "static"}
        if request.endpoint in allowed_endpoints or request.endpoint is None:
            return None
        if g.active_project is None:
            return redirect(url_for("projects"))
        return None

    @app.route("/projects")
    def projects() -> str:
        """List available projects and show the active project."""

        conn = get_global_connection()
        projects = conn.execute(
            "SELECT id, name, slug, created_at FROM projects ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return render_template(
            "projects.html",
            projects=projects,
            active_project=g.active_project,
        )

    @app.route("/projects", methods=["POST"])
    def create_project() -> str:
        """Create a new project and activate it."""

        name = request.form.get("name", "").strip()
        slug = slugify_project_name(name)
        conn = get_global_connection()
        projects = conn.execute(
            "SELECT id, name, slug, created_at FROM projects ORDER BY created_at DESC"
        ).fetchall()
        if not name:
            conn.close()
            return render_template(
                "projects.html",
                projects=projects,
                active_project=g.active_project,
                error="Project name is required.",
            )
        if not slug:
            conn.close()
            return render_template(
                "projects.html",
                projects=projects,
                active_project=g.active_project,
                error="Project name must include alphanumeric characters.",
            )
        existing = conn.execute(
            "SELECT 1 FROM projects WHERE slug = ?", (slug,)
        ).fetchone()
        if existing:
            conn.close()
            return render_template(
                "projects.html",
                projects=projects,
                active_project=g.active_project,
                error=f"Project slug '{slug}' already exists.",
            )
        conn.execute(
            "INSERT INTO projects (name, slug, created_at) VALUES (?, ?, ?)",
            (
                name,
                slug,
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
            ),
        )
        conn.commit()
        conn.close()

        project_paths = ensure_local_project_dirs(slug)
        init_project_db(slug)
        set_active_project(slug)
        setup_logging(project_paths["logs_dir"])
        return redirect(url_for("library"))

    @app.route("/projects/<slug>/activate", methods=["POST"])
    def activate_project(slug: str) -> str:
        """Activate an existing project."""

        conn = get_global_connection()
        project = conn.execute(
            "SELECT slug FROM projects WHERE slug = ?", (slug,)
        ).fetchone()
        conn.close()
        if project is None:
            return redirect(url_for("projects"))
        project_paths = ensure_local_project_dirs(slug)
        init_project_db(slug)
        set_active_project(slug)
        setup_logging(project_paths["logs_dir"])
        return redirect(url_for("library"))

    @app.route("/")
    def library() -> str:
        """Render the library list."""

        query = request.args.get("q", "").strip()
        status = request.args.get("status", "All")
        date_type = request.args.get("date_type", "All")
        issues_only = request.args.get("issues") == "1"

        filters = []
        params: list[str] = []

        if query:
            # Use a single LIKE query for broad matching that is easy to debug.
            like_query = f"%{query.lower()}%"
            filters.append(
                "("
                "LOWER(tapes.title) LIKE ? OR "
                "LOWER(tapes.tape_label_text) LIKE ? OR "
                "LOWER(tapes.source_label) LIKE ? OR "
                "LOWER(tapes.notes) LIKE ? OR "
                "LOWER(tapes.tags_json) LIKE ?"
                ")"
            )
            params.extend(
                [like_query, like_query, like_query, like_query, like_query]
            )

        if status in STATUS_OPTIONS:
            filters.append("tapes.status = ?")
            params.append(status)

        if date_type in DATE_TYPE_OPTIONS:
            filters.append("tapes.date_type = ?")
            params.append(date_type)

        if issues_only:
            # Use EXISTS to avoid joining review items unless needed.
            filters.append(
                "EXISTS (SELECT 1 FROM review_items "
                "WHERE review_items.tape_id = tapes.id "
                "AND review_items.status = 'open')"
            )

        where_clause = "WHERE " + " AND ".join(filters) if filters else ""
        conn = get_project_connection(g.active_project)
        tapes = conn.execute(
            "SELECT id, title, source_label, date_type, date_exact, date_start, date_end, "
            "date_locked, created_at, status FROM tapes "
            f"{where_clause} ORDER BY created_at DESC",
            params,
        ).fetchall()
        conn.close()
        return render_template(
            "library.html",
            tapes=tapes,
            query=query,
            status=status,
            date_type=date_type,
            issues_only=issues_only,
        )

    @app.route("/export")
    def export_master() -> str:
        """Render the export page."""

        export_path = (
            get_project_paths(g.active_project)["exports_dir"]
            / f"vhs2mp4_master_{g.active_project}.csv"
        )
        export_exists = export_path.exists()
        last_generated = None
        if export_exists:
            last_generated = datetime.fromtimestamp(
                export_path.stat().st_mtime
            ).isoformat(timespec="seconds")
        return render_template(
            "export.html",
            export_exists=export_exists,
            last_generated=last_generated,
        )

    @app.route("/export/generate", methods=["POST"])
    def export_generate() -> str:
        """Generate the master CSV export for the active project."""

        project_slug = g.active_project
        export_dir = get_project_paths(project_slug)["exports_dir"]
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"vhs2mp4_master_{project_slug}.csv"

        logging.info(
            "Master export started",
            extra={
                "event": "export_started",
                "context": {"project_slug": project_slug},
            },
        )
        conn = get_project_connection(project_slug)
        try:
            rows = build_master_export_rows(conn)
        finally:
            conn.close()

        with export_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=EXPORT_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        logging.info(
            "Master export completed",
            extra={
                "event": "export_completed",
                "context": {
                    "project_slug": project_slug,
                    "rows": len(rows),
                    "output_path": str(export_path),
                },
            },
        )
        flash("Master CSV generated.", "success")
        return redirect(url_for("export_master"))

    @app.route("/export/download")
    def export_download() -> str:
        """Download the latest master CSV export."""

        export_path = (
            get_project_paths(g.active_project)["exports_dir"]
            / f"vhs2mp4_master_{g.active_project}.csv"
        )
        if not export_path.exists():
            flash("No export file found yet. Generate one first.", "warning")
            return redirect(url_for("export_master"))
        return send_file(export_path, as_attachment=True, download_name=export_path.name)

    @app.route("/tapes/new", methods=["GET", "POST"])
    def new_tape() -> str:
        """Add a new tape to the library."""

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            # Tape label text is stored separately because titles evolve over time.
            tape_label_text = request.form.get("tape_label_text", "").strip()
            label_is_guess = 1 if request.form.get("label_is_guess") == "1" else 0
            source_label = request.form.get("source_label", "").strip() or None
            date_type = request.form.get("date_type", "unknown")
            date_exact = request.form.get("date_exact") or None
            date_start = request.form.get("date_start") or None
            date_end = request.form.get("date_end") or None
            date_locked = 1 if request.form.get("date_locked") == "on" else 0
            notes = request.form.get("notes") or None
            tags_payload = request.form.get("tags_json", "[]")
            try:
                submitted_tags = json.loads(tags_payload)
            except json.JSONDecodeError:
                submitted_tags = []
            tags = normalize_tags(
                [tag for tag in submitted_tags if isinstance(tag, str)]
            )

            if not title:
                conn = get_project_connection(g.active_project)
                suggestions = get_tag_suggestions(conn)
                conn.close()
                return render_template(
                    "new_tape.html",
                    error="Title is required.",
                    form=request.form,
                    tag_suggestions=suggestions,
                )

            conn = get_project_connection(g.active_project)
            tape_code = get_next_tape_code(conn)
            conn.execute(
                """
                INSERT INTO tapes
                    (tape_code, tape_label_text, label_is_guess, title, source_label,
                     date_type, date_exact, date_start, date_end, date_locked, notes,
                     created_at, status, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tape_code,
                    tape_label_text,
                    label_is_guess,
                    title,
                    source_label,
                    date_type,
                    date_exact,
                    date_start,
                    date_end,
                    date_locked,
                    notes,
                    datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    STATUS_OPTIONS[0],
                    json.dumps(tags),
                ),
            )
            conn.commit()
            tape_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
            logging.info(
                "Tape created",
                extra={"event": "tape_created", "context": {"tape_id": tape_id}},
            )
            return redirect(url_for("tape_detail", tape_id=tape_id))

        conn = get_project_connection(g.active_project)
        tag_suggestions = get_tag_suggestions(conn)
        conn.close()
        return render_template(
            "new_tape.html", form={}, tag_suggestions=tag_suggestions
        )

    @app.route("/tapes/<int:tape_id>")
    def tape_detail(tape_id: int) -> str:
        """Render the tape detail page."""

        conn = get_project_connection(g.active_project)
        tape = conn.execute("SELECT * FROM tapes WHERE id = ?", (tape_id,)).fetchone()
        review_items = conn.execute(
            "SELECT * FROM review_items WHERE tape_id = ? ORDER BY created_at DESC",
            (tape_id,),
        ).fetchall()
        conn.close()
        if tape is None:
            return render_template("tape_detail.html", tape=None, review_items=[])
        tags = []
        if tape["tags_json"]:
            try:
                tags = json.loads(tape["tags_json"])
            except json.JSONDecodeError:
                tags = []
        return render_template(
            "tape_detail.html",
            tape=tape,
            review_items=review_items,
            tags=tags,
        )

    @app.route("/ingest")
    def ingest() -> str:
        """Render the ingest queue from the project inbox."""

        conn = get_project_connection(g.active_project)
        inbox_files = list_inbox_files(conn, g.active_project)
        unassigned_tapes = list_unassigned_tapes(conn)
        conn.close()
        return render_template(
            "ingest.html",
            inbox_files=inbox_files,
            unassigned_tapes=unassigned_tapes,
            format_bytes=format_bytes,
            nas_available=is_nas_available(),
            message=request.args.get("message"),
            status=request.args.get("status"),
        )

    @app.route("/ingest/file", methods=["POST"])
    def ingest_file() -> str:
        """Ingest a single inbox file."""

        filename = request.form.get("filename", "").strip()
        tape_id_raw = request.form.get("tape_id", "").strip()
        tape_id = int(tape_id_raw) if tape_id_raw else None
        conn = get_project_connection(g.active_project)
        try:
            result = ingest_inbox_file(conn, g.active_project, filename, tape_id)
            conn.commit()
        finally:
            conn.close()
        return redirect(
            url_for("ingest", message=result.get("message"), status=result.get("status"))
        )

    @app.route("/ingest/all", methods=["POST"])
    def ingest_all() -> str:
        """Ingest all new inbox files."""

        conn = get_project_connection(g.active_project)
        try:
            inbox_files = list_inbox_files(conn, g.active_project)
            ingested = 0
            skipped = 0
            for inbox_file in inbox_files:
                if inbox_file.status != "new":
                    skipped += 1
                    continue
                result = ingest_inbox_file(conn, g.active_project, inbox_file.name)
                if result.get("status") == "ingested":
                    ingested += 1
            conn.commit()
        finally:
            conn.close()
        message = f"Ingested {ingested} file(s). Skipped {skipped}."
        return redirect(url_for("ingest", message=message, status="ingested"))

    @app.route("/review")
    def review_queue() -> str:
        """Render the review queue list."""

        conn = get_project_connection(g.active_project)
        items = conn.execute(
            """
            SELECT review_items.*, tapes.title, tapes.tape_code
            FROM review_items
            LEFT JOIN tapes ON review_items.tape_id = tapes.id
            WHERE review_items.status = 'open'
            ORDER BY review_items.created_at DESC
            """
        ).fetchall()
        conn.close()
        needs_backup_items = [item for item in items if item["type"] == "needs_backup"]
        needs_metadata_items = [
            item for item in items if item["type"] == "needs_metadata"
        ]
        other_items = [
            item
            for item in items
            if item["type"] not in {"needs_backup", "needs_metadata"}
        ]
        return render_template(
            "review.html",
            needs_backup_items=needs_backup_items,
            needs_metadata_items=needs_metadata_items,
            other_items=other_items,
            message=request.args.get("message"),
            status=request.args.get("status"),
        )

    @app.route("/review/<int:item_id>/resolve", methods=["POST"])
    def resolve_review_item(item_id: int) -> str:
        """Mark a review item as resolved."""

        conn = get_project_connection(g.active_project)
        try:
            conn.execute(
                "UPDATE review_items SET status = 'resolved' WHERE id = ?", (item_id,)
            )
            conn.commit()
        finally:
            conn.close()
        return redirect(
            url_for("review_queue", message="Review item resolved.", status="resolved")
        )

    @app.route("/review/<int:item_id>/retry-backup", methods=["POST"])
    def retry_backup_item(item_id: int) -> str:
        """Retry NAS backup for a review item."""

        conn = get_project_connection(g.active_project)
        try:
            item = conn.execute(
                "SELECT * FROM review_items WHERE id = ?", (item_id,)
            ).fetchone()
            if not item:
                return redirect(
                    url_for(
                        "review_queue",
                        message="Review item not found.",
                        status="error",
                    )
                )
            if item["type"] != "needs_backup" or not item["tape_id"]:
                return redirect(
                    url_for(
                        "review_queue",
                        message="Review item cannot be retried.",
                        status="error",
                    )
                )
            tape = conn.execute(
                "SELECT id, raw_path FROM tapes WHERE id = ?", (item["tape_id"],)
            ).fetchone()
            if not tape or not tape["raw_path"]:
                return redirect(
                    url_for(
                        "review_queue",
                        message="Raw path missing for backup retry.",
                        status="error",
                    )
                )
            result = retry_backup(conn, g.active_project, tape["id"], tape["raw_path"])
            if result["status"] == "backed_up":
                conn.execute(
                    "UPDATE review_items SET status = 'resolved' WHERE id = ?",
                    (item_id,),
                )
            conn.commit()
        finally:
            conn.close()
        return redirect(
            url_for("review_queue", message=result["message"], status=result["status"])
        )

    @app.route("/settings")
    def settings() -> str:
        """Render the settings placeholder page."""

        return render_template(
            "settings.html",
            active_project=g.active_project,
            project_paths=g.project_paths,
        )

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(debug=True)
