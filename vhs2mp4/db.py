"""SQLite database helpers and schema initialization.

Global settings (projects + active project) live in a dedicated database,
while each project stores tapes and review queue items in its own database.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from vhs2mp4.config import ensure_project_dirs, get_global_paths, get_project_paths


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
    title TEXT NOT NULL,
    source_label TEXT,
    date_type TEXT NOT NULL,
    date_exact TEXT,
    date_start TEXT,
    date_end TEXT,
    date_locked INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tape_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
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

    ensure_project_dirs(project_slug)
    db_path = get_project_db_path(project_slug)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_project_db(project_slug: str) -> None:
    """Initialize the project database schema if it doesn't exist."""

    conn = get_project_connection(project_slug)
    try:
        conn.executescript(PROJECT_SCHEMA)
        conn.commit()
    finally:
        conn.close()


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
