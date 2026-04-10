from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FFmpegPreparationResult:
    source_path: Path
    prepared_path: Path
    used_transcode: bool
    ffmpeg_available: bool
    message: str | None = None


def prepare_media_source(
    source_path: Path,
    destination_dir: Path,
    *,
    enable_transcode: bool = True,
    max_width: int = 1280,
    video_preset: str = "veryfast",
    video_crf: int = 28,
) -> FFmpegPreparationResult:
    destination_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return FFmpegPreparationResult(
            source_path=source_path,
            prepared_path=source_path,
            used_transcode=False,
            ffmpeg_available=False,
            message="ffmpeg unavailable; using source file directly",
        )

    if not enable_transcode:
        return FFmpegPreparationResult(
            source_path=source_path,
            prepared_path=source_path,
            used_transcode=False,
            ffmpeg_available=True,
            message="ffmpeg transcode disabled; using source file directly",
        )

    prepared_path = destination_dir / f"{source_path.stem}.prepared.mp4"
    scale_filter = f"scale='min({max_width},iw)':-2"
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(source_path),
        "-an",
        "-vf",
        scale_filter,
        "-c:v",
        "libx264",
        "-preset",
        video_preset,
        "-crf",
        str(video_crf),
        str(prepared_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        return FFmpegPreparationResult(
            source_path=source_path,
            prepared_path=prepared_path,
            used_transcode=True,
            ffmpeg_available=True,
        )
    except Exception as exc:
        return FFmpegPreparationResult(
            source_path=source_path,
            prepared_path=source_path,
            used_transcode=False,
            ffmpeg_available=True,
            message=f"ffmpeg transcode failed; using source file directly ({exc.__class__.__name__})",
        )
