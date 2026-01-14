# AI Rules for VHS2MP4

These rules guide automated agents working in this repository. The purpose is to
preserve intent, avoid overreach, and keep the project maintainable by humans.

## Core principles

1. **Local-first**: assume no cloud services unless explicitly added.
2. **Boring tech**: prefer proven libraries and simple patterns.
3. **Idempotency**: future pipeline steps must be safe to re-run.
4. **Explainability**: code and docs should be clear to a new maintainer or AI.
5. **Non-interrupting UI**: prompts should be queued for later review.

## What not to do

- Do not implement real video processing without explicit approval.
- Do not add background queues or async workers unless asked.
- Do not remove structured logging or the `data/` directory conventions.

## Documentation expectations

- Every new module should include a top-level docstring.
- New workflows must be documented in `docs/WORKFLOWS.md`.
- Major changes should include an ADR.

## Consistency requirements

- Face clusters can be unnamed; use stable placeholder IDs like `Person_0001`.
- Speech-to-text output is for **context only**, not speaker attribution.
- Always keep the master index export in scope for future steps.

## Style

- Keep the code readable for non-experts.
- Prefer explicit types and clear variable names.
- Leave stubs with TODOs instead of speculative implementations.
