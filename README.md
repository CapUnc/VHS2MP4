# VHS2MP4

Local-first VHS processing and review tool scaffold. This repository focuses on the
foundation: a small Flask web UI, SQLite persistence, structured logging, and clear
documentation to guide future automation and pipeline work. **No video processing is
implemented yet.**

## Why this exists

VHS archives are slow and sensitive to manage. This tool is designed to be:

- **Local-first**: all processing runs on a Mac for speed and privacy.
- **Backup-aware**: RAW MP4 captures are backed up to a NAS.
- **Review-friendly**: UI queues review prompts rather than interrupting the operator.
- **AI-ready**: documentation is explicit so future agents can continue safely.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m vhs2mp4.app
```

Then open: `http://localhost:5000`.

The app automatically creates a local `./data` directory with:

- `data/vhs2mp4.db` (SQLite)
- `data/logs/` (structured log output)

## Project layout

```
VHS2MP4/
├── ADR/
├── docs/
├── scripts/
├── vhs2mp4/
│   ├── services/
│   └── web/
└── README.md
```

## Documentation index

- [SPEC.md](SPEC.md): full system spec and functional scope.
- [AI_RULES.md](AI_RULES.md): rules for automation and future agents.
- [docs/WORKFLOWS.md](docs/WORKFLOWS.md): operator workflows and data flow.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md): common issues.
- [ADR/0001-initial-architecture.md](ADR/0001-initial-architecture.md): architecture decision record.

## What exists today

- Flask app with pages:
  - `/` library list
  - `/tapes/new` add tape form
  - `/tapes/<id>` tape details
  - `/review` review queue placeholder
  - `/settings` settings placeholder
- SQLite initialization on first launch.
- Stubbed service modules for future pipeline stages.

## What is intentionally missing

- Any real video segmentation, face clustering, or transcription.
- Network/cloud dependencies.
- Advanced queue processing or background jobs.

## Development notes

- Python 3.11+
- Flask + Jinja templates
- SQLite (no external DB)
- Structured logging is configured in `vhs2mp4/logging_setup.py`.

## Projects and storage layout

VHS2MP4 is **multi-project** and uses a global settings database plus a per-project
database for tapes and review items. The base roots are:

- Local root: `/Users/Sather/Documents/VHS2MP4`
- NAS root: `/Volumes/home/VHS2MP4`

Each project lives at `/Users/Sather/Documents/VHS2MP4/<project_slug>/` with:

- `inbox/`, `data/`, `01_raw/`, `02_master/`, `03_work/`, `04_final/`, `exports/`
- `data/vhs2mp4.db` for project data
- `data/logs/` for logs

Each project is backed up to `/Volumes/home/VHS2MP4/<project_slug>/` with:

- `01_raw_backup/` (and later `04_final_backup/`)

The global settings database lives at:

- `/Users/Sather/Documents/VHS2MP4/_global/vhs2mp4_global.db`

## License

MIT (placeholder). Replace if needed.
