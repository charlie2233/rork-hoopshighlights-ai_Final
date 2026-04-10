from __future__ import annotations

from .models import CandidateWindow, CloudClip, clamp


def classify_window(window: CandidateWindow) -> CloudClip:
    combined = clamp(window.combined_score, 0.0, 1.0)
    confidence = clamp(0.46 + (combined * 0.52), 0.55, 0.98)

    if combined >= 0.82 and window.motion_score >= 0.70 and window.visual_score >= 0.52:
        label = "Dunk"
    elif window.audio_score >= 0.70 and window.motion_score >= 0.56:
        label = "Three Pointer"
    elif window.visual_score >= 0.60 and window.motion_score >= 0.48:
        label = "Made Shot"
    elif window.motion_score >= 0.64:
        label = "Fast Break"
    elif combined >= 0.55:
        label = "Layup"
    else:
        label = "Highlight"

    shot_type = None
    if label == "Three Pointer":
        shot_type = "three_pointer"
    elif label in {"Made Shot", "Layup", "Dunk"}:
        shot_type = "field_goal"

    return CloudClip(
        startTime=round(window.start_time, 3),
        endTime=round(window.end_time, 3),
        confidence=round(confidence, 4),
        label=label,
        action=label,
        audioScore=round(clamp(window.audio_score, 0.0, 1.0), 4),
        visualScore=round(clamp(window.visual_score, 0.0, 1.0), 4),
        motionScore=round(clamp(window.motion_score, 0.0, 1.0), 4),
        combinedScore=round(combined, 4),
        shouldAutoKeep=confidence >= 0.62,
        shouldEnableSlowMotion=label in {"Dunk", "Posterize"},
        eventType="basketball_highlight",
        shotType=shot_type,
        rankScore=round(combined, 4),
    )


def maybe_relabel_with_gemini(clips: list[CloudClip], enabled: bool) -> tuple[list[CloudClip], bool]:
    # Stubbed for now. The backend keeps deterministic labels unless a dedicated
    # Gemini relabeling pass is wired in with Vertex AI credentials.
    return clips, False if enabled else False
