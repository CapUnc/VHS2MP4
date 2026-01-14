# VHS2MP4 Specification (Scaffold)

## Goals

1. Provide a **local-first** VHS processing interface for MP4 files captured via a
   ClearClick device.
2. Offer a **human-friendly review queue** that consolidates prompts instead of
   interrupting the operator.
3. Maintain **SQLite persistence** and a future-ready schema for idempotent processing.
4. Generate and maintain **master index exports** (CSV and JSON) later.
5. Use **boring, well-supported technologies** (Python 3.11+, Flask, SQLite).

## Non-goals (for this scaffold)

- No video processing yet.
- No face clustering or speech-to-text output yet.
- No background workers or job queue.
- No cloud dependencies.

## Operational constraints

- Capture input files locally on a Mac for speed.
- Backup RAW MP4 files to a NAS.
- Face clustering will be local and optionally unnamed; unnamed clusters must get
  stable placeholder names like `Person_0007`.
- Speech-to-text is **only** for context clues, not speaker attribution.
- Future pipeline must be idempotent and safe to re-run.

## UX requirements

- Library list: overview of tapes and their metadata.
- Add Tape form:
  - date modes: `Exact`, `Range`, or `Unknown`
  - “Lock Date” flag indicates the operator is confident in the date.
- Review screen: aggregated prompts list.
- Settings screen: placeholder for environment locations and behavior toggles.

## Persistence requirements

- SQLite database created automatically at first run.
- Global settings database stores:
  - `projects`
  - `settings` (active project)
- Per-project database stores:
  - `tapes`
  - `review_queue`
- Base schema must be documented and easy to extend.

## Future pipeline (stub interfaces only)

- Segmentation
- Face clustering
- Location inference
- Transcript (context-only)
- Metadata extraction
- Embedding generation
- Orchestration for idempotent steps

## Export requirements (future)

- Master index exported to JSON and CSV.
- Export should include tape metadata, derived entities, and review outcomes.

## Logging

- Structured JSON logging to `data/logs/` per project.
- Log entries must include event name, timestamp, and relevant IDs.

## Security/privacy

- Operate offline by default.
- Avoid any default cloud calls.

## Compatibility

- Python 3.11+.
- Mac primary development environment.

## Multi-project layout

All projects are scoped under the base roots:

- Local root: `/Users/Sather/Documents/VHS2MP4`
- NAS root: `/Volumes/home/VHS2MP4`

Each project creates local directories:

- `inbox/`, `data/`, `01_raw/`, `02_master/`, `03_work/`, `04_final/`, `exports/`

Each project creates NAS backup directories:

- `01_raw_backup/` (and later `04_final_backup/`)
