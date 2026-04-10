from __future__ import annotations

from typing import Any, Mapping


EVENT_LOCALIZATION_FIELDS = (
    "eventStart",
    "eventCenter",
    "eventEnd",
    "shotReleaseTime",
    "ballNearRimTime",
    "ballThroughHoopTime",
    "possessionChangeTime",
    "transitionStartTime",
)


def event_localization_template() -> dict[str, float | None]:
    return {field: None for field in EVENT_LOCALIZATION_FIELDS}


def derive_coarse_event_window(
    event_center_seconds: float | None,
    *,
    clip_duration_seconds: float | None = None,
    half_window_seconds: float = 1.5,
) -> dict[str, float | None]:
    if event_center_seconds is None:
        return event_localization_template()
    event_center = _coerce_optional_time(event_center_seconds, "eventCenter")
    if event_center is None:
        return event_localization_template()
    if half_window_seconds < 0:
        raise ValueError("half_window_seconds must be non-negative.")
    event_start = max(0.0, event_center - half_window_seconds)
    event_end = event_center + half_window_seconds
    if clip_duration_seconds is not None:
        clip_duration = _coerce_optional_time(clip_duration_seconds, "clipDurationSeconds")
        if clip_duration is not None:
            event_end = min(event_end, clip_duration)
            if event_start > event_end:
                event_start = max(0.0, event_end - half_window_seconds)
    return {
        "eventStart": event_start,
        "eventCenter": event_center,
        "eventEnd": event_end,
        "shotReleaseTime": None,
        "ballNearRimTime": None,
        "ballThroughHoopTime": None,
        "possessionChangeTime": None,
        "transitionStartTime": None,
    }


def normalize_event_localization_fields(row: Mapping[str, Any]) -> dict[str, float | None]:
    return {field: _coerce_optional_time(row.get(field), field) for field in EVENT_LOCALIZATION_FIELDS}


def _coerce_optional_time(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric.") from exc
    if parsed < 0.0:
        raise ValueError(f"{field_name} must be greater than or equal to 0.0.")
    return parsed
