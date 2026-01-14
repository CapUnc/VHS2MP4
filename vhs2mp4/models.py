"""Lightweight data structures for VHS2MP4."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Tape:
    """Represents a VHS tape entry in the library."""

    id: int | None
    title: str
    source_label: str | None
    date_type: str
    date_exact: str | None
    date_start: str | None
    date_end: str | None
    date_locked: bool
    notes: str | None
    created_at: datetime


@dataclass
class ReviewItem:
    """Represents a queued review item for operator attention."""

    id: int | None
    tape_id: int
    item_type: str
    description: str
    status: str
    created_at: datetime
