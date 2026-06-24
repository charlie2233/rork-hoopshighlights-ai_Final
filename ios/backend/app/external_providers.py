from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .config import Settings
from .models import CloudClip, clamp


MIN_EXTERNAL_SHOT_LEAD_IN_SECONDS = 2.0
MIN_EXTERNAL_SHOT_FOLLOW_THROUGH_SECONDS = 1.25
MIN_EXTERNAL_CLIP_DURATION_SECONDS = 2.0


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
        min_clip_duration=settings.min_clip_duration_seconds,
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
    min_clip_duration: float = MIN_EXTERNAL_CLIP_DURATION_SECONDS,
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

        event_center = _coerce_optional_event_center(item, duration_seconds)
        label = str(item.get("label") or "Highlight")
        action = str(item.get("action") or item.get("label") or "Highlight")
        start, end = _expand_shot_window_for_event_context(
            start,
            end,
            event_center,
            label,
            duration_seconds=duration_seconds,
            max_clip_duration=max_clip_duration,
        )

        if end - start > max_clip_duration:
            end = min(duration_seconds, start + max_clip_duration)
        if end - start < min_clip_duration:
            continue
        if end <= start:
            continue

        clip_payload = {
            "startTime": round(start, 3),
            "endTime": round(end, 3),
            "eventCenter": round(event_center, 3) if event_center is not None else None,
            "confidence": round(clamp(_coerce_float(item.get("confidence"), 0.52), 0.35, 0.99), 4),
            "label": label,
            "action": action,
            "audioScore": round(clamp(_coerce_float(item.get("audioScore"), 0.35), 0.0, 1.0), 4),
            "visualScore": round(clamp(_coerce_float(item.get("visualScore"), 0.45), 0.0, 1.0), 4),
            "motionScore": round(clamp(_coerce_float(item.get("motionScore"), 0.45), 0.0, 1.0), 4),
            "combinedScore": round(clamp(_coerce_float(item.get("combinedScore"), 0.5), 0.0, 1.0), 4),
            "detectionMethod": "cloud",
            "shouldAutoKeep": bool(item.get("shouldAutoKeep", False)),
            "shouldEnableSlowMotion": bool(item.get("shouldEnableSlowMotion", False)),
        }
        clip = CloudClip(**clip_payload)
        if _is_shot_like_label(clip.label) and _external_clip_context_score(clip) < 0.45:
            continue
        parsed.append(
            clip.model_copy(
                update={
                    "shouldAutoKeep": clip.shouldAutoKeep and _external_clip_auto_keep_allowed(clip),
                    "shouldEnableSlowMotion": clip.shouldEnableSlowMotion and _external_clip_auto_keep_allowed(clip),
                }
            )
        )

    parsed = _dedupe_external_clips(parsed)
    parsed.sort(key=_external_clip_quality_key, reverse=True)
    return parsed[:clip_limit]


def apply_autohighlight_boosts(clips: Sequence[CloudClip], boosts: Sequence[float]) -> list[CloudClip]:
    boosted: list[CloudClip] = []
    for index, clip in enumerate(clips):
        boost = clamp(_coerce_float(boosts[index], 0.0) if index < len(boosts) else 0.0, 0.0, 1.0)
        combined = round(clamp((clip.combinedScore * 0.78) + (boost * 0.22), 0.0, 1.0), 4)
        confidence = round(clamp(clip.confidence + (boost * 0.08), 0.35, 0.99), 4)
        should_auto_keep = clip.shouldAutoKeep or confidence >= 0.62 or boost >= 0.52
        scores = clip.scores.model_copy(update={"mergeScore": combined, "finalScore": combined}) if clip.scores else None
        updated = clip.model_copy(
            update={
                "confidence": confidence,
                "combinedScore": combined,
                "rankScore": combined,
                "scores": scores,
                "shouldAutoKeep": should_auto_keep,
            }
        )
        boosted.append(
            updated.model_copy(
                update={
                    "shouldAutoKeep": should_auto_keep and _external_clip_auto_keep_allowed(updated),
                    "shouldEnableSlowMotion": updated.shouldEnableSlowMotion and _external_clip_auto_keep_allowed(updated),
                }
            )
        )

    boosted.sort(key=_external_clip_quality_key, reverse=True)
    return boosted


def _coerce_optional_event_center(item: dict, duration_seconds: float) -> float | None:
    for key in ("eventCenter", "eventTime", "peakTime", "shotTime"):
        value = item.get(key)
        try:
            event_center = float(value)
        except (TypeError, ValueError):
            continue
        return clamp(event_center, 0.0, duration_seconds)
    return None


def _expand_shot_window_for_event_context(
    start: float,
    end: float,
    event_center: float | None,
    label: str,
    *,
    duration_seconds: float,
    max_clip_duration: float,
) -> tuple[float, float]:
    if event_center is None or not _is_shot_like_label(label):
        return start, end

    expanded_start = max(0.0, min(start, event_center - MIN_EXTERNAL_SHOT_LEAD_IN_SECONDS))
    expanded_end = min(duration_seconds, max(end, event_center + MIN_EXTERNAL_SHOT_FOLLOW_THROUGH_SECONDS))
    if expanded_end - expanded_start <= max_clip_duration:
        return expanded_start, expanded_end

    preferred_lead = min(max_clip_duration * 0.68, max_clip_duration - MIN_EXTERNAL_SHOT_FOLLOW_THROUGH_SECONDS)
    expanded_start = max(0.0, event_center - preferred_lead)
    expanded_end = min(duration_seconds, expanded_start + max_clip_duration)
    if expanded_end < event_center + MIN_EXTERNAL_SHOT_FOLLOW_THROUGH_SECONDS:
        expanded_end = min(duration_seconds, event_center + MIN_EXTERNAL_SHOT_FOLLOW_THROUGH_SECONDS)
        expanded_start = max(0.0, expanded_end - max_clip_duration)
    return expanded_start, expanded_end


def _is_shot_like_label(label: str) -> bool:
    normalized = label.strip().lower()
    return any(token in normalized for token in ("shot", "bucket", "basket", "layup", "dunk", "finish", "jumper", "three", "3pt"))


def _dedupe_external_clips(clips: Sequence[CloudClip]) -> list[CloudClip]:
    kept: list[CloudClip] = []
    for clip in clips:
        duplicate_index = next((index for index, existing in enumerate(kept) if _overlap_ratio(clip, existing) > 0.55), None)
        if duplicate_index is None:
            kept.append(clip)
            continue
        if _external_clip_quality_key(clip) > _external_clip_quality_key(kept[duplicate_index]):
            kept[duplicate_index] = clip
    return kept


def _external_clip_quality_key(clip: CloudClip) -> tuple[float, float, float, float, float, float]:
    duration = max(0.0, clip.endTime - clip.startTime)
    return (
        1.0 if duration >= MIN_EXTERNAL_CLIP_DURATION_SECONDS else 0.0,
        _external_clip_context_score(clip),
        clip.combinedScore,
        clip.confidence,
        clip.visualScore,
        clip.motionScore,
    )


def _external_clip_auto_keep_allowed(clip: CloudClip) -> bool:
    if clip.combinedScore < 0.58 or clip.confidence < 0.55:
        return False
    if _external_clip_context_score(clip) < 0.45:
        return False
    return True


def _external_clip_context_score(clip: CloudClip) -> float:
    duration = max(0.0, clip.endTime - clip.startTime)
    if duration < MIN_EXTERNAL_CLIP_DURATION_SECONDS:
        return 0.0
    if not _is_shot_like_label(clip.label):
        return min(1.0, duration / 4.5)
    if clip.eventCenter is None:
        return 0.2

    event_center = min(max(clip.eventCenter, clip.startTime), clip.endTime)
    lead_in = max(0.0, event_center - clip.startTime)
    follow_through = max(0.0, clip.endTime - event_center)
    if lead_in <= 0.0 or follow_through <= 0.0:
        return 0.0

    lead_score = min(1.0, lead_in / MIN_EXTERNAL_SHOT_LEAD_IN_SECONDS)
    follow_score = min(1.0, follow_through / MIN_EXTERNAL_SHOT_FOLLOW_THROUGH_SECONDS)
    duration_score = min(1.0, duration / 4.5)
    balance_score = min(lead_in, follow_through) / max(lead_in, follow_through)
    return round((lead_score * 0.36) + (follow_score * 0.28) + (duration_score * 0.22) + (balance_score * 0.14), 4)


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
