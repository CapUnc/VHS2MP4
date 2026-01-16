"""Background job runner for VHS2MP4."""

from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from vhs2mp4.db import get_project_connection, update_job

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)


def enqueue_job(project_slug: str, job_id: int, job_callable: Callable) -> None:
    """Enqueue a job to run in the background."""

    def _run_job() -> None:
        conn = get_project_connection(project_slug)
        try:
            update_job(job_id, status="running", project_slug=project_slug)
            result = job_callable(conn)
            conn.commit()
            update_job(
                job_id,
                status="success",
                percent=100,
                result=result if isinstance(result, dict) else {},
                project_slug=project_slug,
            )
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            error_text = f"{exc}\n{traceback.format_exc(limit=5)}"
            logger.exception(
                "Job failed",
                extra={
                    "event": "job_failed",
                    "context": {"job_id": job_id, "project_slug": project_slug},
                },
            )
            update_job(
                job_id,
                status="failed",
                error=error_text,
                project_slug=project_slug,
            )
        finally:
            conn.close()

    _executor.submit(_run_job)


def job_progress(
    job_id: int,
    percent: int,
    step: str,
    detail: str = "",
    project_slug: str | None = None,
) -> None:
    """Update progress for a running job."""

    update_job(
        job_id,
        percent=percent,
        step=step,
        detail=detail,
        project_slug=project_slug,
    )
