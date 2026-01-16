# Troubleshooting

## App won't start

- Ensure Python 3.11+ is installed.
- Confirm the virtual environment is activated.
- Check `requirements.txt` is installed.

## Database errors

- The app creates `data/vhs2mp4.db` automatically.
- If corruption occurs, back up the file and recreate it.

## Logs not appearing

- Logs are written to `data/logs/app.log` by default.
- Confirm the `data/logs/` directory is writable.

## ffmpeg not installed

- Thumbnails and scene suggestions require ffmpeg.
- Install on macOS with: `brew install ffmpeg`.
- The app remains usable without ffmpeg; media processing buttons will show a reminder.

## ffmpeg errors during media processing

- Check the project log file: `/Users/Sather/Documents/VHS2MP4/<project>/data/logs/app.log`.
- Look for events like `thumbnail_failed` or `scene_detection_failed` for details.
- Ensure the raw MP4 exists at the stored path and is readable.

## Why files are not auto-split yet

- Suggested splits are only stored as boundaries for review.
- Actual file splitting will be added in a later phase once workflows are vetted.

## NAS not mounted

- Ingest will still complete, but a review item of type `needs_backup` appears.
- Mount `/Volumes/home` and ensure the NAS path is reachable.
- Use **Review → Retry Backup** after the NAS is mounted.

## UI looks stale

- Refresh the page.
- Confirm no aggressive browser caching.

## Permission issues

- Run the app from a directory you own.
- Ensure `scripts/run_local.sh` is executable if used.

## Export issues

- CSV not generating: confirm the active project is set and try again.
- Permissions: ensure `/Users/Sather/Documents/VHS2MP4/<project>/exports` is writable.
- Folder missing: the app recreates local folders, but you can manually create `exports` if needed.
