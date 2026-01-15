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
