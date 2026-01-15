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
