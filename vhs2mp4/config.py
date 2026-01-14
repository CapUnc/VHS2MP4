"""Configuration helpers for VHS2MP4."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


BASE_LOCAL_ROOT = Path("/Users/Sather/Documents/VHS2MP4")
BASE_NAS_ROOT = Path("/Volumes/home/VHS2MP4")
GLOBAL_DIR_NAME = "_global"


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

    This helper remains for backwards compatibility with the initial scaffold.
    New project-aware paths should come from get_project_paths().

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


def get_global_paths() -> AppPaths:
    """Resolve paths for the global settings database and logs."""

    global_root = BASE_LOCAL_ROOT / GLOBAL_DIR_NAME
    data_dir = global_root
    db_path = global_root / "vhs2mp4_global.db"
    logs_dir = global_root / "logs"
    return AppPaths(root=global_root, data_dir=data_dir, db_path=db_path, logs_dir=logs_dir)


def get_project_paths(project_slug: str) -> Dict[str, Path]:
    """Return all local and NAS paths for a given project."""

    project_root = BASE_LOCAL_ROOT / project_slug
    data_dir = project_root / "data"
    db_path = data_dir / "vhs2mp4.db"
    logs_dir = data_dir / "logs"
    nas_root = BASE_NAS_ROOT / project_slug
    return {
        "project_root": project_root,
        "inbox_dir": project_root / "inbox",
        "data_dir": data_dir,
        "raw_dir": project_root / "01_raw",
        "master_dir": project_root / "02_master",
        "work_dir": project_root / "03_work",
        "final_dir": project_root / "04_final",
        "exports_dir": project_root / "exports",
        "db_path": db_path,
        "logs_dir": logs_dir,
        "nas_root": nas_root,
        "nas_raw_backup_dir": nas_root / "01_raw_backup",
        "nas_final_backup_dir": nas_root / "04_final_backup",
    }


def ensure_project_dirs(project_slug: str) -> Dict[str, Path]:
    """Ensure project directories exist locally and on the NAS."""

    logger = logging.getLogger(__name__)
    paths = get_project_paths(project_slug)
    local_dirs = [
        paths["project_root"],
        paths["inbox_dir"],
        paths["data_dir"],
        paths["raw_dir"],
        paths["master_dir"],
        paths["work_dir"],
        paths["final_dir"],
        paths["exports_dir"],
        paths["logs_dir"],
    ]
    for directory in local_dirs:
        directory.mkdir(parents=True, exist_ok=True)
    nas_dirs = [paths["nas_root"], paths["nas_raw_backup_dir"]]
    for directory in nas_dirs:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Ensured project directories",
        extra={"event": "project_dirs_ensured", "context": {"project_slug": project_slug}},
    )
    return paths


def slugify_project_name(name: str) -> str:
    """Slugify a project name using safe, lowercase characters."""

    slug = name.strip().lower()
    slug = re.sub(r"\s+", "_", slug)
    slug = re.sub(r"[^a-z0-9_]+", "", slug)
    slug = re.sub(r"_+", "_", slug)
    return slug.strip("_")
