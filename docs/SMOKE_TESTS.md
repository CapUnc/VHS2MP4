# Smoke Tests

## Library search + export

1. Create two tapes in the Library.
   - Add tags and notes to both.
   - Add tape label text on both; mark one label as a guess.
   - Leave one title blank and confirm it auto-fills from the label text.
   - Manually edit the other title, then change the label text and confirm it does not overwrite.
   - Ingest one tape so it becomes **Ingested**.
   - Leave the other as **New**.
2. Disconnect the NAS and ingest a tape to create a **needs_backup** review item.
3. Verify:
   - Library filters work (status, date type, and issues).
   - Search finds tapes by a word only in tape label text.
   - **Has Issues** only shows the tape with an open review item.
   - Export CSV generates with both tapes and includes tape_label_text + label_is_guess.

## Media processing

1. Ingest a short MP4 so the tape is **Ingested** with a raw path.
2. Open the Tape Details page and click **Generate Thumbnail + Suggest Scene Splits**.
3. Verify a thumbnail file appears in `/Users/Sather/Documents/VHS2MP4/<project>/thumbnails/`.
4. Confirm the Tape Detail view shows the thumbnail image.
5. Confirm suggested splits appear (or the empty-state message if none detected).
6. Click **Accept Suggestions** and verify segments rows exist in the database.
7. Click **Export Segment Clips** and confirm files appear in `/Users/Sather/Documents/VHS2MP4/<project>/02_segments/<tape_code>/`.
8. Confirm each segment row shows exported status in the Tape Details view.
9. Click **Ignore Suggestions** on another tape and confirm suggestions are marked ignored and the review item is resolved.

## Background job progress

1. From **Ingest**, click **Ingest All** and confirm you are redirected to a progress page.
2. Wait for the job to reach **Success** and confirm it redirects back to **Ingest**.
3. From a Tape Details page, click **Generate Thumbnail + Suggest Scene Splits** and confirm the progress page updates step text and percent.
4. After success, confirm you are redirected back to the tape detail page.
5. Click **Export Segment Clips** and confirm progress updates while segments export.
6. Simulate a failure (disconnect NAS or remove ffmpeg) and confirm the job status shows **Failed** with an error block.

## Pending tests when real VHS videos are available

- Scene split quality on home video content.
- Export segments accuracy on long tapes.
- Verify threshold/merge rules produce reasonable splits.
