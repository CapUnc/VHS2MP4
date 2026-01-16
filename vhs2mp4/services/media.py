"""Media processing helpers for thumbnails and scene suggestions."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

_SCENE_THRESHOLD = 0.35
_MIN_SEGMENT_SECONDS = 90.0


@dataclass(frozen=True)
class MediaMetadata:
    """Metadata for a video file."""

    duration_seconds: float | None
    file_size_bytes: int | None


@dataclass(frozen=True)
class ThumbnailResult:
    """Result of a thumbnail generation attempt."""

    status: str
    message: str
    output_path: Path | None


@dataclass(frozen=True)
class SceneSuggestion:
    """Suggested segment boundaries from scene detection."""

    start_seconds: float
    end_seconds: float
    confidence: float | None


def is_ffmpeg_available() -> bool:
    """Return True if ffmpeg is available on the PATH."""

    return shutil.which("ffmpeg") is not None


def _ffprobe_path() -> str | None:
    """Return the ffprobe executable path if available."""

    return shutil.which("ffprobe")


def _ffmpeg_path() -> str | None:
    """Return the ffmpeg executable path if available."""

    return shutil.which("ffmpeg")


def _run_subprocess(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a subprocess command with logging and a timeout."""

    logger.info(
        "Running subprocess",
        extra={
            "event": "subprocess_start",
            "context": {"command": args, "timeout_seconds": timeout},
        },
    )
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _parse_duration_from_ffmpeg(stderr: str) -> float | None:
    """Parse a duration value from ffmpeg stderr output."""

    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", stderr)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    try:
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError:
        return None


def _parse_pts_times(stderr: str) -> list[float]:
    """Extract pts_time values from ffmpeg showinfo output."""

    points: list[float] = []
    for line in stderr.splitlines():
        if "showinfo" not in line:
            continue
        match = re.search(r"pts_time:(\d+\.?\d*)", line)
        if not match:
            continue
        try:
            points.append(float(match.group(1)))
        except ValueError:
            continue
    return sorted(set(points))


def _merge_short_segments(segments: Iterable[SceneSuggestion]) -> list[SceneSuggestion]:
    """Merge segments shorter than the minimum threshold."""

    merged: list[SceneSuggestion] = []
    for segment in segments:
        if not merged:
            merged.append(segment)
            continue
        current = merged[-1]
        if (segment.end_seconds - segment.start_seconds) < _MIN_SEGMENT_SECONDS:
            merged[-1] = SceneSuggestion(
                start_seconds=current.start_seconds,
                end_seconds=segment.end_seconds,
                confidence=current.confidence,
            )
            continue
        if (current.end_seconds - current.start_seconds) < _MIN_SEGMENT_SECONDS:
            merged[-1] = SceneSuggestion(
                start_seconds=current.start_seconds,
                end_seconds=segment.end_seconds,
                confidence=current.confidence,
            )
            continue
        merged.append(segment)
    return merged


def get_video_metadata(path: str | Path) -> MediaMetadata:
    """Return duration and file size for a video path.

    Duration uses ffprobe if available, with ffmpeg output parsing as a fallback.
    File size uses os.path.getsize regardless of ffmpeg availability.
    """

    video_path = Path(path)
    try:
        file_size = os.path.getsize(video_path)
    except OSError as exc:
        logger.warning(
            "File size lookup failed",
            extra={
                "event": "media_metadata_failed",
                "context": {"path": str(video_path), "error": str(exc)},
            },
        )
        file_size = None

    duration = _get_duration_seconds(video_path)
    return MediaMetadata(duration_seconds=duration, file_size_bytes=file_size)


def _get_duration_seconds(path: Path) -> float | None:
    """Return duration seconds using ffprobe or ffmpeg if available."""

    ffprobe = _ffprobe_path()
    if ffprobe:
        try:
            result = _run_subprocess(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                timeout=20,
            )
        except subprocess.TimeoutExpired as exc:
            logger.warning(
                "ffprobe timed out",
                extra={
                    "event": "ffprobe_timeout",
                    "context": {"path": str(path), "error": str(exc)},
                },
            )
        else:
            if result.returncode == 0:
                try:
                    return float(result.stdout.strip())
                except ValueError:
                    pass
            logger.warning(
                "ffprobe failed",
                extra={
                    "event": "ffprobe_failed",
                    "context": {
                        "path": str(path),
                        "returncode": result.returncode,
                        "stderr": result.stderr.strip(),
                    },
                },
            )

    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        logger.info(
            "ffmpeg not available for duration",
            extra={"event": "ffmpeg_missing", "context": {"path": str(path)}},
        )
        return None
    try:
        result = _run_subprocess([ffmpeg, "-i", str(path), "-f", "null", "-"], timeout=20)
    except subprocess.TimeoutExpired as exc:
        logger.warning(
            "ffmpeg duration probe timed out",
            extra={
                "event": "ffmpeg_duration_timeout",
                "context": {"path": str(path), "error": str(exc)},
            },
        )
        return None
    if result.returncode != 0:
        logger.warning(
            "ffmpeg duration probe failed",
            extra={
                "event": "ffmpeg_duration_failed",
                "context": {
                    "path": str(path),
                    "returncode": result.returncode,
                    "stderr": result.stderr.strip(),
                },
            },
        )
    return _parse_duration_from_ffmpeg(result.stderr)


def generate_thumbnail(
    video_path: str | Path, output_jpg_path: str | Path, force: bool = False
) -> ThumbnailResult:
    """Generate a JPEG thumbnail from a video using ffmpeg."""

    output_path = Path(output_jpg_path)
    if output_path.exists() and not force:
        return ThumbnailResult(
            status="skipped",
            message="Thumbnail already exists.",
            output_path=output_path,
        )

    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        return ThumbnailResult(
            status="unavailable",
            message="ffmpeg is not installed. Install with: brew install ffmpeg",
            output_path=None,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = _get_duration_seconds(Path(video_path))
    if duration:
        seek_seconds = max(1.0, min(duration * 0.1, 30.0))
    else:
        seek_seconds = 1.0
    args = [
        ffmpeg,
        "-y" if force else "-n",
        "-ss",
        f"{seek_seconds:.2f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        "scale=640:-2",
        str(output_path),
    ]
    try:
        result = _run_subprocess(args, timeout=60)
    except subprocess.TimeoutExpired as exc:
        logger.warning(
            "Thumbnail generation timed out",
            extra={
                "event": "thumbnail_timeout",
                "context": {"path": str(video_path), "error": str(exc)},
            },
        )
        return ThumbnailResult(
            status="timeout",
            message="Thumbnail generation timed out.",
            output_path=None,
        )

    if result.returncode != 0:
        logger.warning(
            "Thumbnail generation failed",
            extra={
                "event": "thumbnail_failed",
                "context": {
                    "path": str(video_path),
                    "returncode": result.returncode,
                    "stderr": result.stderr.strip(),
                },
            },
        )
        return ThumbnailResult(
            status="error",
            message="Thumbnail generation failed. Check logs for details.",
            output_path=None,
        )

    return ThumbnailResult(
        status="created",
        message="Thumbnail created.",
        output_path=output_path,
    )


def suggest_scene_segments(video_path: str | Path) -> list[SceneSuggestion]:
    """Suggest scene segments based on ffmpeg scene detection."""

    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        logger.info(
            "ffmpeg missing; scene detection skipped",
            extra={"event": "scene_detection_skipped", "context": {}},
        )
        return []

    duration = _get_duration_seconds(Path(video_path))
    if not duration:
        logger.warning(
            "Scene detection skipped due to missing duration",
            extra={
                "event": "scene_detection_no_duration",
                "context": {"path": str(video_path)},
            },
        )
        return []

    args = [
        ffmpeg,
        "-i",
        str(video_path),
        "-filter_complex",
        f"select='gt(scene,{_SCENE_THRESHOLD})',showinfo",
        "-f",
        "null",
        "-",
    ]
    try:
        result = _run_subprocess(args, timeout=90)
    except subprocess.TimeoutExpired as exc:
        logger.warning(
            "Scene detection timed out",
            extra={
                "event": "scene_detection_timeout",
                "context": {"path": str(video_path), "error": str(exc)},
            },
        )
        return []

    if result.returncode != 0:
        logger.warning(
            "Scene detection failed",
            extra={
                "event": "scene_detection_failed",
                "context": {
                    "path": str(video_path),
                    "returncode": result.returncode,
                    "stderr": result.stderr.strip(),
                },
            },
        )
        return []

    cut_points = _parse_pts_times(result.stderr)
    if len(cut_points) <= 1:
        logger.info(
            "Scene detection produced insufficient cut points",
            extra={
                "event": "scene_detection_empty",
                "context": {"path": str(video_path), "cuts": len(cut_points)},
            },
        )
        return []

    segments: list[SceneSuggestion] = []
    start = 0.0
    for cut in cut_points:
        if cut <= start:
            continue
        segments.append(
            SceneSuggestion(
                start_seconds=start,
                end_seconds=cut,
                confidence=None,
            )
        )
        start = cut
    if duration > start:
        segments.append(
            SceneSuggestion(
                start_seconds=start,
                end_seconds=duration,
                confidence=None,
            )
        )

    merged = _merge_short_segments(segments)
    if len(merged) <= 1:
        return []
    return merged
