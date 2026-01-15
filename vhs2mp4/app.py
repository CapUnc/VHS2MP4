"""Flask entrypoint for VHS2MP4."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime
from collections import Counter

from flask import Flask, g, redirect, render_template, request, url_for

from vhs2mp4.config import (
    ensure_project_dirs,
    get_global_paths,
    get_project_paths,
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

STATUS_OPTIONS = ("New", "Ingested", "Mastered", "Reviewed", "Final")


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


def create_app() -> Flask:
    """Application factory for VHS2MP4."""

    global_paths = get_global_paths()
    setup_logging(global_paths.logs_dir)
    init_global_db()

    active_project = get_active_project()
    if active_project:
        project_paths = ensure_project_dirs(active_project)
        setup_logging(project_paths["logs_dir"])
        init_project_db(active_project)

    base_dir = Path(__file__).resolve().parent

    app = Flask(
        __name__,
        template_folder=str(base_dir / "web" / "templates"),
        static_folder=str(base_dir / "web" / "static"),
        static_url_path="/static",
    )

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

        project_paths = ensure_project_dirs(slug)
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
        project_paths = ensure_project_dirs(slug)
        init_project_db(slug)
        set_active_project(slug)
        setup_logging(project_paths["logs_dir"])
        return redirect(url_for("library"))

    @app.route("/")
    def library() -> str:
        """Render the library list."""

        conn = get_project_connection(g.active_project)
        tapes = conn.execute(
            "SELECT id, title, source_label, date_type, date_exact, date_start, date_end, "
            "date_locked, created_at FROM tapes ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return render_template("library.html", tapes=tapes)

    @app.route("/tapes/new", methods=["GET", "POST"])
    def new_tape() -> str:
        """Add a new tape to the library."""

        if request.method == "POST":
            title = request.form.get("title", "").strip()
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
                    (tape_code, title, source_label, date_type, date_exact, date_start, date_end,
                     date_locked, notes, created_at, status, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tape_code,
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
            "SELECT * FROM review_queue WHERE tape_id = ? ORDER BY created_at DESC",
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

    @app.route("/review")
    def review_queue() -> str:
        """Render the review queue placeholder list."""

        conn = get_project_connection(g.active_project)
        items = conn.execute(
            """
            SELECT review_queue.*, tapes.title
            FROM review_queue
            JOIN tapes ON review_queue.tape_id = tapes.id
            ORDER BY review_queue.created_at DESC
            """
        ).fetchall()
        conn.close()
        return render_template("review.html", items=items)

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
