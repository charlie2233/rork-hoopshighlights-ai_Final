from __future__ import annotations

from .models import CandidateWindow, CloudClip, clamp


def classify_window(window: CandidateWindow) -> CloudClip:
    combined = clamp(window.combined_score, 0.0, 1.0)
    confidence = clamp(0.46 + (combined * 0.52), 0.55, 0.98)
    has_shot_context = window.event_context_score >= 0.45

    if has_shot_context and combined >= 0.82 and window.motion_score >= 0.70 and window.visual_score >= 0.52:
        label = "Dunk"
    elif has_shot_context and window.audio_score >= 0.70 and window.motion_score >= 0.56:
        label = "Three Pointer"
    elif has_shot_context and window.visual_score >= 0.60 and window.motion_score >= 0.48:
        label = "Shot Attempt"
    elif window.audio_pop_score >= 0.45 and window.visual_score < 0.50 and not has_shot_context:
        label = "Crowd Reaction"
    elif window.motion_score >= 0.64:
        label = "Fast Break"
    elif has_shot_context and combined >= 0.55:
        label = "Layup Attempt"
    else:
        label = "Highlight"

    return CloudClip(
        startTime=round(window.start_time, 3),
        endTime=round(window.end_time, 3),
        eventCenter=round(window.peak_time, 3),
        confidence=round(confidence, 4),
        label=label,
        action=label,
        audioScore=round(clamp(window.audio_score, 0.0, 1.0), 4),
        visualScore=round(clamp(window.visual_score, 0.0, 1.0), 4),
        motionScore=round(clamp(window.motion_score, 0.0, 1.0), 4),
        combinedScore=round(combined, 4),
        audioCueType=window.audio_cue_type,
        audioCueConfidence=round(clamp(window.audio_cue_confidence, 0.0, 1.0), 4) if window.audio_cue_type else None,
        audioCueTime=round(window.audio_pop_time, 3) if window.audio_pop_time is not None and window.audio_cue_type else None,
        shouldAutoKeep=confidence >= 0.62 and label not in {"Highlight", "Crowd Reaction"},
        shouldEnableSlowMotion=label in {"Dunk", "Posterize"},
    )


def maybe_relabel_with_gemini(clips: list[CloudClip], enabled: bool) -> tuple[list[CloudClip], bool]:
    # Stubbed for now. The backend keeps deterministic labels unless a dedicated
    # Gemini relabeling pass is wired in with Vertex AI credentials.
    return clips, False if enabled else False
