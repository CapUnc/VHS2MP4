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

## Jobs show "stale"

- A stale job means the server restarted while the job was running.
- Re-run the action to start a fresh job.
- Check the job progress page for the `error_text` message to see what happened before the restart.

## Job failures

- Open the job progress page and review the error block for the `error_text` detail.
- Cross-reference the project log file for stack traces and context.

## ffmpeg not installed

- Thumbnails, scene suggestions, and segment exports require ffmpeg.
- Install on macOS with: `brew install ffmpeg`.
- The app remains usable without ffmpeg; media processing buttons will show a reminder.

## ffmpeg errors during media processing

- Check the project log file: `/Users/Sather/Documents/VHS2MP4/<project>/data/logs/app.log`.
- Look for events like `thumbnail_failed` or `scene_detection_failed` for details.
- Ensure the raw MP4 exists at the stored path and is readable.

## Segment export uses stream copy then fallback

- Segment export first uses stream copy (`-c copy`) for speed.
- If copy fails, the app falls back to a re-encode (libx264 + aac, medium preset).
- Check logs for `segment_export_copy_failed` or `segment_export_failed` events if clips are missing.

## Segment exports are missing

- Exported clips live in `/Users/Sather/Documents/VHS2MP4/<project>/02_segments/<tape_code>/`.
- Re-running export skips existing files unless you force a re-export later.
- If exports fail, a `needs_export_review` item appears in the review queue.

## Why files are not auto-split automatically

- Suggested splits are only stored as boundaries for review.
- Clips are only created after you accept suggestions (or create segments manually) and click **Export Segment Clips**.

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
