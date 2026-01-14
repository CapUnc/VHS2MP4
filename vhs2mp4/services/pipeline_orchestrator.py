"""Pipeline orchestration placeholder.

Future: coordinate idempotent pipeline steps and enqueue review tasks.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PipelineContext:
    """Context for running pipeline steps.

    TODO: include tape ID, file paths, and configuration in the future.
    """

    tape_id: int


def run_pipeline(context: PipelineContext) -> None:
    """Run the pipeline (stub).

    Args:
        context: PipelineContext for the tape.
    """

    raise NotImplementedError("Pipeline orchestration is not implemented yet.")
