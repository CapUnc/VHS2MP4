# Workflows

## 1. Capture and ingest

1. Capture tapes using the ClearClick device; output is MP4 files.
2. Copy MP4s locally onto the Mac working directory.
3. Backup RAW MP4s to the NAS before any processing begins.
4. Create a Tape entry in the web UI and attach metadata.

## 2. Review queue workflow

- Pipeline steps will enqueue review items rather than interrupting the operator.
- The review queue is the single place where prompts are resolved.
- Review items should be associated with a Tape ID and include a type + summary.

## 3. Face clustering workflow (future)

1. Run local clustering.
2. Present clusters in the review queue.
3. Operator can name clusters or skip.
4. Skipped clusters receive stable placeholder IDs like `Person_0007`.

## 4. Transcript workflow (future)

- Speech-to-text is only for context clues.
- No speaker attribution is performed.

## 5. Index export workflow (future)

- Generate JSON + CSV master index.
- Export should be idempotent and include processing metadata.
