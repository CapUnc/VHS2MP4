"""Flask entrypoint for VHS2MP4."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Flask, redirect, render_template, request, url_for

from vhs2mp4.config import get_paths
from vhs2mp4.db import get_connection, init_db
from vhs2mp4.logging_setup import setup_logging


def create_app() -> Flask:
    """Application factory for VHS2MP4."""

    paths = get_paths()
    setup_logging(paths.logs_dir)
    init_db()

    app = Flask(__name__)

    @app.route("/")
    def library() -> str:
        """Render the library list."""

        conn = get_connection()
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

            if not title:
                return render_template(
                    "new_tape.html",
                    error="Title is required.",
                    form=request.form,
                )

            conn = get_connection()
            conn.execute(
                """
                INSERT INTO tapes
                    (title, source_label, date_type, date_exact, date_start, date_end,
                     date_locked, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    source_label,
                    date_type,
                    date_exact,
                    date_start,
                    date_end,
                    date_locked,
                    notes,
                    datetime.utcnow().isoformat(timespec="seconds") + "Z",
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

        return render_template("new_tape.html", form={})

    @app.route("/tapes/<int:tape_id>")
    def tape_detail(tape_id: int) -> str:
        """Render the tape detail page."""

        conn = get_connection()
        tape = conn.execute("SELECT * FROM tapes WHERE id = ?", (tape_id,)).fetchone()
        review_items = conn.execute(
            "SELECT * FROM review_queue WHERE tape_id = ? ORDER BY created_at DESC",
            (tape_id,),
        ).fetchall()
        conn.close()
        if tape is None:
            return render_template("tape_detail.html", tape=None, review_items=[])
        return render_template("tape_detail.html", tape=tape, review_items=review_items)

    @app.route("/review")
    def review_queue() -> str:
        """Render the review queue placeholder list."""

        conn = get_connection()
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

        return render_template("settings.html")

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(debug=True)
