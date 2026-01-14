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

## UI looks stale

- Refresh the page.
- Confirm no aggressive browser caching.

## Permission issues

- Run the app from a directory you own.
- Ensure `scripts/run_local.sh` is executable if used.
