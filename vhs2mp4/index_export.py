"""Export helpers for the future master index.

This module provides placeholders for JSON/CSV exports. Real export logic will be
added once pipeline outputs exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def export_master_index_json(destination: Path, rows: Iterable[dict]) -> None:
    """Export the master index to JSON.

    Args:
        destination: Output file path.
        rows: Iterable of row dictionaries.
    """

    raise NotImplementedError("Master index JSON export is not implemented yet.")


def export_master_index_csv(destination: Path, rows: Iterable[dict]) -> None:
    """Export the master index to CSV.

    Args:
        destination: Output file path.
        rows: Iterable of row dictionaries.
    """

    raise NotImplementedError("Master index CSV export is not implemented yet.")
