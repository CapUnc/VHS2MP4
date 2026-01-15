# Smoke Tests

## Library search + export

1. Create two tapes in the Library.
   - Add tags and notes to both.
   - Ingest one tape so it becomes **Ingested**.
   - Leave the other as **New**.
2. Disconnect the NAS and ingest a tape to create a **needs_backup** review item.
3. Verify:
   - Library filters work (status, date type, and issues).
   - **Has Issues** only shows the tape with an open review item.
   - Export CSV generates with both tapes and all expected columns.
