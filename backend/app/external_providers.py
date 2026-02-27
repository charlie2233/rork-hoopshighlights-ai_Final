from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .config import Settings
from .models import CloudClip, clamp


def detect_with_optional_external_provider(
    source_path: Path,
    duration_seconds: float,
    settings: Settings,
) -> tuple[list[CloudClip], Optional[str]]:
    provider = settings.detection_provider
    if provider not in {"hybrid", "hoopcut"}:
        return [], None
    if not settings.hoopcut_is_configured:
        return [], None

    payload = _run_json_command(
        [
            settings.hoopcut_python_bin or "python3",
            str(_scripts_root() / "run_hoopcut_adapter.py"),
            "--repo",
            str(settings.hoopcut_repo_path),
            "--video",
            str(source_path),
            "--min-clip",
            str(settings.min_clip_duration_seconds),
            "--max-clip",
            str(settings.max_clip_duration_seconds),
            "--max-clips",
            str(settings.max_returned_clips),
        ],
        timeout_seconds=180,
    )
    if payload is None:
        return [], None

    clips = parse_external_clips_from_payload(
        payload,
        duration_seconds=duration_seconds,
        max_clip_duration=settings.max_clip_duration_seconds,
        clip_limit=settings.max_returned_clips,
    )
    if not clips:
        return [], None

    return clips, "hoopcut"


def rerank_with_optional_external_provider(
    clips: Sequence[CloudClip],
    source_path: Path,
    settings: Settings,
) -> tuple[list[CloudClip], Optional[str]]:
    if settings.post_ranking_provider != "autohighlight":
        return list(clips), None
    if not settings.autohighlight_is_configured:
        return list(clips), None
    if not clips:
        return [], None

    payload = _run_json_command(
        [
            settings.autohighlight_python_bin or "python3",
            str(_scripts_root() / "run_autohighlight_ranker.py"),
            "--repo",
            str(settings.autohighlight_repo_path),
            "--video",
            str(source_path),
            "--model",
            str(Path(settings.autohighlight_repo_path) / "models" / "default.hdf5"),
        ],
        stdin_payload={"clips": [clip.model_dump() for clip in clips]},
        timeout_seconds=240,
    )
    if payload is None:
        return list(clips), None

    raw_boosts = payload.get("boosts") if isinstance(payload, dict) else None
    if not isinstance(raw_boosts, list):
        return list(clips), None

    boosts: list[float] = []
    for item in raw_boosts:
        try:
            boosts.append(float(item))
        except (TypeError, ValueError):
            boosts.append(0.0)

    return apply_autohighlight_boosts(clips, boosts), "autohighlight"


def parse_external_clips_from_payload(
    payload: object,
    *,
    duration_seconds: float,
    max_clip_duration: float,
    clip_limit: int,
) -> list[CloudClip]:
    if not isinstance(payload, dict):
        return []

    raw_clips = payload.get("clips")
    if not isinstance(raw_clips, list):
        return []

    parsed: List[CloudClip] = []
    for item in raw_clips:
        if not isinstance(item, dict):
            continue

        try:
            start = clamp(float(item.get("startTime", 0.0)), 0.0, duration_seconds)
            end = clamp(float(item.get("endTime", 0.0)), 0.0, duration_seconds)
        except (TypeError, ValueError):
            continue

        if end <= start:
            continue

        if end - start > max_clip_duration:
            end = min(duration_seconds, start + max_clip_duration)
        if end <= start:
            continue

        clip_payload = {
            "startTime": round(start, 3),
            "endTime": round(end, 3),
            "confidence": round(clamp(_coerce_float(item.get("confidence"), 0.68), 0.35, 0.99), 4),
            "label": str(item.get("label") or "Highlight"),
            "action": str(item.get("action") or item.get("label") or "Highlight"),
            "audioScore": round(clamp(_coerce_float(item.get("audioScore"), 0.45), 0.0, 1.0), 4),
            "visualScore": round(clamp(_coerce_float(item.get("visualScore"), 0.7), 0.0, 1.0), 4),
            "motionScore": round(clamp(_coerce_float(item.get("motionScore"), 0.72), 0.0, 1.0), 4),
            "combinedScore": round(clamp(_coerce_float(item.get("combinedScore"), 0.76), 0.0, 1.0), 4),
            "detectionMethod": "cloud",
            "shouldAutoKeep": bool(item.get("shouldAutoKeep", True)),
            "shouldEnableSlowMotion": bool(item.get("shouldEnableSlowMotion", False)),
        }
        parsed.append(CloudClip(**clip_payload))

    parsed = _dedupe_external_clips(parsed)
    parsed.sort(key=lambda clip: clip.combinedScore, reverse=True)
    return parsed[:clip_limit]


def apply_autohighlight_boosts(clips: Sequence[CloudClip], boosts: Sequence[float]) -> list[CloudClip]:
    boosted: list[CloudClip] = []
    for index, clip in enumerate(clips):
        boost = clamp(_coerce_float(boosts[index], 0.0) if index < len(boosts) else 0.0, 0.0, 1.0)
        combined = round(clamp((clip.combinedScore * 0.78) + (boost * 0.22), 0.0, 1.0), 4)
        confidence = round(clamp(clip.confidence + (boost * 0.08), 0.35, 0.99), 4)
        should_auto_keep = clip.shouldAutoKeep or confidence >= 0.62 or boost >= 0.52
        boosted.append(
            CloudClip(
                startTime=clip.startTime,
                endTime=clip.endTime,
                confidence=confidence,
                label=clip.label,
                action=clip.action,
                audioScore=clip.audioScore,
                visualScore=clip.visualScore,
                motionScore=clip.motionScore,
                combinedScore=combined,
                detectionMethod=clip.detectionMethod,
                shouldAutoKeep=should_auto_keep,
                shouldEnableSlowMotion=clip.shouldEnableSlowMotion,
            )
        )

    boosted.sort(key=lambda clip: clip.combinedScore, reverse=True)
    return boosted


def _dedupe_external_clips(clips: Sequence[CloudClip]) -> list[CloudClip]:
    kept: list[CloudClip] = []
    for clip in sorted(clips, key=lambda item: (item.startTime, -item.combinedScore)):
        if any(_overlap_ratio(clip, existing) > 0.55 for existing in kept):
            continue
        kept.append(clip)
    return kept


def _overlap_ratio(left: CloudClip, right: CloudClip) -> float:
    overlap = max(0.0, min(left.endTime, right.endTime) - max(left.startTime, right.startTime))
    if overlap <= 0.0:
        return 0.0
    shortest = min(max(left.endTime - left.startTime, 0.001), max(right.endTime - right.startTime, 0.001))
    return overlap / shortest


def _coerce_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _run_json_command(
    command: Sequence[str],
    *,
    stdin_payload: Optional[object] = None,
    timeout_seconds: int,
) -> Optional[object]:
    try:
        completed = subprocess.run(
            list(command),
            input=json.dumps(stdin_payload) if stdin_payload is not None else None,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return None

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def _scripts_root() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts"
