"""Configuration helpers for VHS2MP4."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Container for application paths.

    The data directory is created on startup.
    """

    root: Path
    data_dir: Path
    db_path: Path
    logs_dir: Path


def get_paths(root: Path | None = None) -> AppPaths:
    """Resolve application paths relative to the project root.

    Args:
        root: Optional project root override.

    Returns:
        AppPaths with data directory and database paths.
    """

    base = root or Path.cwd()
    data_dir = base / "data"
    db_path = data_dir / "vhs2mp4.db"
    logs_dir = data_dir / "logs"
    return AppPaths(root=base, data_dir=data_dir, db_path=db_path, logs_dir=logs_dir)
