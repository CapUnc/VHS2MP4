"""SQLite database helpers and schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from vhs2mp4.config import get_paths


SCHEMA = """
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

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def ensure_data_dirs() -> Path:
    """Ensure data directories exist and return the database path."""

    paths = get_paths()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    return paths.db_path


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection with row factory set to dict-like access."""

    db_path = ensure_data_dirs()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database schema if it doesn't exist."""

    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
