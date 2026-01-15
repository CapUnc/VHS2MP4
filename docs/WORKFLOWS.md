# Workflows

## 1. Capture and ingest

1. Capture tapes using the ClearClick device; output is MP4 files.
2. Copy MP4s locally onto the Mac working directory.
3. Use the **Ingest** page to copy MP4s from the project inbox into `01_raw`.
4. Confirm NAS mirroring succeeds (review queue will flag missing backups).
5. Create or attach Tape entries in the web UI and add metadata.
   - Add short, consistent tags (birthday, cabin, soccer) to help grouping later.
   - Tape Label Text is the source-of-truth for what is physically written on the tape.
   - Title is the friendly display name you want people to browse.

## Tape label vs. title (best practice)

- Tape Label Text = keep it raw and literal (what is written on the cassette).
- Title = the friendly, browseable name you want family to see later.
- Use **label is a guess** when you are not confident in the label wording.

## 2. Ingest workflow

1. Drop ClearClick MP4 files into the active project `inbox` directory.
2. Navigate to **Ingest** and review file metadata + ingest status.
3. Attach files to existing tapes (optional) or let ingest auto-create tapes.
4. Click **Ingest** for a single file or **Ingest All** for the inbox.
5. Verify NAS backup status via the review queue if a backup is needed.

## 3. Review queue workflow

- Pipeline steps will enqueue review items rather than interrupting the operator.
- The review queue is the single place where prompts are resolved.
- Review items should be associated with a Tape ID and include a type + summary.

## 4. Face clustering workflow (future)

1. Run local clustering.
2. Present clusters in the review queue.
3. Operator can name clusters or skip.
4. Skipped clusters receive stable placeholder IDs like `Person_0007`.

## 5. Transcript workflow (future)

- Speech-to-text is only for context clues.
- No speaker attribution is performed.

## 6. Index export workflow

- Generate the master CSV export from the **Export** page.
- Keep exports idempotent so the latest file replaces the previous one.
- JSON exports will be added later once pipeline outputs exist.

## 7. Export workflow

1. Open **Export** from the top navigation.
2. Review the active project name before generating.
3. Click **Generate CSV** to create the latest master export.
4. Use **Download latest** to open the CSV in Excel.

## 8. Library search guidance

- Use short, everyday words that feel natural (birthday, cabin, soccer).
- Combine search + filters if results are too broad.
- If no results appear, clear filters and try a simpler search term.
