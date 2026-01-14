# ADR 0001: Initial Architecture

## Status

Accepted — 2024-01-01 (placeholder date)

## Context

We need a local-first VHS processing tool with a simple UI. The system must be
reliable on a Mac, avoid external dependencies, and be easy to troubleshoot.

## Decision

- Use **Python 3.11+** for the application runtime.
- Use **Flask** for the web UI and routing.
- Use **SQLite** for persistence.
- Use **Jinja templates** and minimal JavaScript for UI behaviors.
- Implement **structured logging** to local disk.
- Provide **stub service modules** for future pipeline steps.

## Consequences

- The system remains lightweight and debuggable.
- We can evolve toward idempotent processing without refactoring the runtime.
- The UI can grow with minimal front-end complexity.

## Alternatives considered

- FastAPI: more modern but adds complexity for server-side rendering.
- Electron: heavier footprint and more complex packaging.
- PostgreSQL: unnecessary overhead for a local-first tool.
