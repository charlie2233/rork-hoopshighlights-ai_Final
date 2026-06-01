from __future__ import annotations

from array import array
from copy import copy
from dataclasses import dataclass, is_dataclass, replace
from pathlib import Path
from statistics import mean
from time import perf_counter
import json
import math
import re
import shutil
import subprocess
import tempfile
import wave
from typing import List, Optional, Sequence, Tuple

from .classifier import classify_window, maybe_relabel_with_gemini
from .config import Settings
from .external_providers import detect_with_optional_external_provider, rerank_with_optional_external_provider
from .models import CandidateWindow, CloudAnalysisResult, CloudClip, CloudDiagnostics, CloudNativeShotSignals, PipelineError, StoredJob, TeamOption, TeamSelection, clamp
from .team_identity import team_identity_matches, team_key
from .team_quick_scan import apply_team_quick_scan


NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS = 2.0
NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS = 1.25
NATIVE_SHOT_SIGNAL_MIN_DURATION_SECONDS = 3.0
NATIVE_DEFENSIVE_CONTEXT_TARGET_LEAD_SECONDS = 1.5
NATIVE_DEFENSIVE_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS = 1.2
NATIVE_DEFENSIVE_CONTEXT_TARGET_SECONDS = 4.0
NATIVE_DEFENSIVE_CONTEXT_MIN_LEAD_SECONDS = 0.6
NATIVE_DEFENSIVE_CONTEXT_MIN_FOLLOW_THROUGH_SECONDS = 0.5
HYBRID_OVERLAP_DEDUPE_RATIO = 0.55
VISUAL_EVENT_SAMPLE_FPS = 2.0
VISUAL_EVENT_FRAME_WIDTH = 64
VISUAL_EVENT_FRAME_HEIGHT = 36
VISUAL_EVENT_MIN_SCORE = 0.46
VISUAL_EVENT_MIN_VISUAL_SCORE = 0.28
VISUAL_EVENT_MIN_SETUP_CONTEXT_SCORE = 0.18
VISUAL_EVENT_MIN_OUTCOME_CONTEXT_SCORE = 0.12
VISUAL_EVENT_MIN_GAP_SECONDS = 1.4
VISUAL_EVENT_MAX_BOUNDARIES = 24
VISUAL_EVENT_SEQUENCE_GAP_SECONDS = 1.1
VISUAL_EVENT_CONTEXT_SECONDS = 1.25
NATIVE_RECALL_BACKFILL_OVERLAP_RATIO = 0.55
TEAM_SELECTION_PREFILTER_MULTIPLIER = 4
TEAM_SELECTION_PREFILTER_MAX_CLIPS = 1280
TEAM_EVIDENCE_REQUIRED_SOURCES = {"quick_scan", "gpt_frame_review", "provider", "unknown"}
MIN_CONFIDENT_TEAM_EVIDENCE_FRAME_REFS = 2
MIN_CONFIDENT_TEAM_EVIDENCE_ROLE_GROUPS = 2
MIN_DETECTED_TEAM_OPTION_CONFIDENCE = 0.85
VisualFrameSignal = Tuple[float, ...]


@dataclass(frozen=True)
class VisualEventFrame:
    time_seconds: float
    score: float
    visual_score: float
    full_motion: float
    upper_motion: float
    center_motion: float
    lower_motion: float
    audio_score: float


def run_analysis(job: StoredJob, settings: Settings, source_path: Path) -> CloudAnalysisResult:
    started_at = perf_counter()
    if not source_path.exists():
        raise PipelineError("upload_missing", "The uploaded video could not be found.")

    if job.file_size_bytes > settings.max_file_size_bytes:
        raise PipelineError("file_too_large", "Videos larger than 500 MB are not supported in cloud analysis v1.")

    duration_seconds = _probe_duration(source_path, fallback=job.duration_seconds)
    if duration_seconds > settings.max_duration_seconds:
        raise PipelineError("unsupported_duration", "Videos longer than 30 minutes are not supported in cloud analysis right now.")

    provider_tags: list[str] = []
    candidate_pool_limit = _analysis_candidate_pool_limit(settings, job.team_selection)
    expanded_settings = _settings_with_candidate_limit(settings, candidate_pool_limit)

    external_clips, detection_provider = detect_with_optional_external_provider(
        source_path=source_path,
        duration_seconds=duration_seconds,
        settings=expanded_settings,
    )

    if detection_provider and settings.detection_provider == "hoopcut":
        provider_tags.append(detection_provider)
        clips = external_clips[:candidate_pool_limit]
        candidate_segments = len(external_clips)
    else:
        native_clips, native_candidate_segments = _run_native_candidate_detection(
            source_path,
            duration_seconds,
            settings,
            clip_limit=candidate_pool_limit,
        )
        if detection_provider:
            provider_tags.append(detection_provider)
            clips = _merge_hybrid_detection_clips(
                external_clips=external_clips,
                native_clips=native_clips,
                clip_limit=candidate_pool_limit,
            )
            candidate_segments = len(external_clips) + native_candidate_segments
        else:
            clips = native_clips
            candidate_segments = native_candidate_segments

    clips = _normalize_analysis_clips(clips, duration_seconds, settings, clip_limit=candidate_pool_limit)

    clips, ranking_provider = rerank_with_optional_external_provider(
        clips=clips,
        source_path=source_path,
        settings=settings,
    )
    if ranking_provider:
        provider_tags.append(ranking_provider)

    clips, used_gemini = maybe_relabel_with_gemini(clips, settings.use_gemini_relabeling)
    clips, detected_teams, used_team_quick_scan = apply_team_quick_scan(source_path, duration_seconds, clips, settings)
    if used_team_quick_scan:
        provider_tags.append("team-scan")
    if not detected_teams:
        detected_teams = _detected_teams_from_clips(clips)
    pre_team_filter_clips = list(clips)
    clips = _filter_analysis_clips_for_team_selection(clips, job.team_selection)
    clips = _trim_analysis_clips_for_review(clips, job.team_selection, settings.max_returned_clips)
    clips = _annotate_analysis_team_status(clips, job.team_selection)
    team_diagnostics = _analysis_team_diagnostic_counts(
        candidate_clips=pre_team_filter_clips,
        review_clips=clips,
        team_selection=job.team_selection,
        used_team_quick_scan=used_team_quick_scan,
    )

    elapsed_ms = int((perf_counter() - started_at) * 1000)
    model_version = settings.backend_model_version
    if provider_tags:
        model_version = "{base}+{providers}".format(
            base=model_version,
            providers="+".join(provider_tags),
        )
    diagnostics = CloudDiagnostics(
        processingMs=max(elapsed_ms, 1),
        backendModelVersion=model_version,
        usedVideoIntelligence=False,
        usedGeminiRelabeling=used_gemini,
        candidateSegments=candidate_segments,
        finalSegments=len(clips),
        **team_diagnostics,
    )

    return CloudAnalysisResult(
        clipCount=len(clips),
        clips=clips,
        diagnostics=diagnostics,
        detectedTeams=detected_teams,
        teamSelection=job.team_selection,
    )


def _analysis_team_diagnostic_counts(
    *,
    candidate_clips: Sequence[CloudClip],
    review_clips: Sequence[CloudClip],
    team_selection: Optional[TeamSelection],
    used_team_quick_scan: bool,
) -> dict[str, int | bool]:
    candidate_statuses = [_analysis_team_status(clip, team_selection) for clip in candidate_clips]
    review_statuses = [_analysis_team_status(clip, team_selection) for clip in review_clips]
    return {
        "usedTeamQuickScan": bool(used_team_quick_scan),
        "preTeamFilterSegments": len(candidate_clips),
        "teamMatchedCandidateSegments": sum(1 for status in candidate_statuses if status == "matched"),
        "teamUncertainCandidateSegments": sum(1 for status in candidate_statuses if status == "uncertain"),
        "teamOpponentFilteredSegments": sum(1 for status in candidate_statuses if status == "opponent"),
        "teamMatchedReviewSegments": sum(1 for status in review_statuses if status == "matched"),
        "teamUncertainReviewSegments": sum(1 for status in review_statuses if status == "uncertain"),
        "defensiveReviewSegments": sum(1 for clip in review_clips if _is_defensive_label(clip.label)),
        "blockReviewSegments": sum(1 for clip in review_clips if _defensive_label_family(clip.label) == "block"),
        "stealReviewSegments": sum(1 for clip in review_clips if _defensive_label_family(clip.label) == "steal"),
        "forcedTurnoverReviewSegments": sum(1 for clip in review_clips if _defensive_label_family(clip.label) == "forced_turnover"),
        "defensiveStopReviewSegments": sum(1 for clip in review_clips if _defensive_label_family(clip.label) == "defensive_stop"),
    }


def build_team_quick_scan_candidate_clips(
    source_path: Path,
    duration_seconds: float,
    settings: Settings,
) -> list[CloudClip]:
    if not source_path.exists():
        return []
    candidate_limit = _team_quick_scan_candidate_pool_limit(settings)
    try:
        probed_duration = _probe_duration(source_path, fallback=duration_seconds)
        clips, _ = _run_native_candidate_detection(
            source_path,
            probed_duration,
            settings,
            clip_limit=candidate_limit,
        )
        return _normalize_analysis_clips(
            clips,
            probed_duration,
            settings,
            clip_limit=candidate_limit,
        )
    except Exception:
        return []


def _team_quick_scan_candidate_pool_limit(settings: Settings) -> int:
    configured = int(getattr(settings, "team_quick_scan_max_candidate_clips", TEAM_SELECTION_PREFILTER_MAX_CLIPS))
    base_limit = max(1, int(getattr(settings, "max_returned_clips", 1)))
    return min(TEAM_SELECTION_PREFILTER_MAX_CLIPS, max(base_limit, configured))


def _analysis_candidate_pool_limit(settings: Settings, team_selection: Optional[TeamSelection]) -> int:
    base_limit = max(1, int(settings.max_returned_clips))
    return min(TEAM_SELECTION_PREFILTER_MAX_CLIPS, max(base_limit, base_limit * TEAM_SELECTION_PREFILTER_MULTIPLIER))


def _settings_with_candidate_limit(settings: Settings, clip_limit: int) -> Settings:
    if int(settings.max_returned_clips) == clip_limit:
        return settings
    if is_dataclass(settings):
        return replace(settings, max_returned_clips=clip_limit)
    copied = copy(settings)
    copied.max_returned_clips = clip_limit
    return copied


def _team_key(value: Optional[str]) -> Optional[str]:
    return team_key(value)


def _analysis_team_status(
    clip: CloudClip,
    team_selection: Optional[TeamSelection],
) -> str:
    if team_selection is None or team_selection.mode == "all":
        return "all"
    if clip.teamAttributionStatus == "uncertain":
        return "uncertain"
    attribution = clip.teamAttribution
    if attribution is None or attribution.confidence < team_selection.confidenceThreshold:
        return "uncertain"
    if _analysis_team_evidence_required(attribution) and not _analysis_has_confident_team_evidence(attribution):
        return "uncertain"

    selected_team_id = _team_key(team_selection.teamId)
    clip_team_id = _team_key(attribution.teamId)
    if team_identity_matches(
        selected_team_id=team_selection.teamId,
        selected_color_label=team_selection.colorLabel,
        selected_label=team_selection.label,
        candidate_team_id=attribution.teamId,
        candidate_color_label=attribution.colorLabel,
        candidate_label=attribution.label,
    ):
        return "matched"
    if selected_team_id and clip_team_id and selected_team_id != clip_team_id:
        return "opponent"
    return "opponent"


def _analysis_team_evidence_required(attribution: ClipTeamAttribution) -> bool:
    source = (attribution.source or "unknown").strip().lower() or "unknown"
    return source in TEAM_EVIDENCE_REQUIRED_SOURCES


def _analysis_has_confident_team_evidence(attribution: ClipTeamAttribution) -> bool:
    frame_refs = {ref for ref in attribution.evidenceFrameRefs if ref}
    role_groups = {group for group in attribution.evidenceRoleGroups if group}
    return (
        len(frame_refs) >= MIN_CONFIDENT_TEAM_EVIDENCE_FRAME_REFS
        and len(role_groups) >= MIN_CONFIDENT_TEAM_EVIDENCE_ROLE_GROUPS
    )


def _filter_analysis_clips_for_team_selection(
    clips: Sequence[CloudClip],
    team_selection: Optional[TeamSelection],
) -> list[CloudClip]:
    if team_selection is None or team_selection.mode == "all":
        return list(clips)
    filtered: list[CloudClip] = []
    for clip in clips:
        status = _analysis_team_status(clip, team_selection)
        if status == "matched" or (status == "uncertain" and team_selection.includeUncertain):
            filtered.append(clip)
    return filtered


def _uncertain_review_reserve_limit(max_clips: int, uncertain_count: int) -> int:
    max_clips = max(0, int(max_clips))
    uncertain_count = max(0, int(uncertain_count))
    if max_clips == 0 or uncertain_count == 0:
        return 0
    if max_clips < 6:
        return 1
    return min(uncertain_count, max(3, max_clips // 2))


def _defensive_review_reserve_limit(max_clips: int, defensive_count: int) -> int:
    max_clips = max(0, int(max_clips))
    defensive_count = max(0, int(defensive_count))
    if max_clips < 3 or defensive_count == 0:
        return 0
    if max_clips < 4:
        return 1
    if max_clips < 8:
        return min(defensive_count, 2)
    return min(defensive_count, max(2, max_clips // 3))


def _trim_analysis_clips_for_review(
    clips: Sequence[CloudClip],
    team_selection: Optional[TeamSelection],
    max_clips: int,
) -> list[CloudClip]:
    max_clips = max(0, int(max_clips))
    if max_clips == 0:
        return []

    indexed_clips = list(enumerate(clips))
    selected: list[tuple[int, CloudClip]] = []
    selected_indexes: set[int] = set()

    def add_clip(index: int, clip: CloudClip) -> None:
        if index in selected_indexes or len(selected) >= max_clips:
            return
        selected.append((index, clip))
        selected_indexes.add(index)

    defensive = [
        (index, clip)
        for index, clip in indexed_clips
        if _is_defensive_label(clip.label) and _analysis_clip_auto_keep_allowed(clip)
    ]
    defensive_reserve = _defensive_review_reserve_limit(max_clips, len(defensive))
    if defensive_reserve == 1:
        for index, clip in sorted(defensive, key=_review_reserved_clip_quality_key, reverse=True)[:1]:
            add_clip(index, clip)
    elif defensive_reserve > 1:
        reserved_defensive_count = 0
        for family in ("block", "steal", "forced_turnover", "defensive_stop", "defensive"):
            family_candidates = [
                (index, clip)
                for index, clip in defensive
                if index not in selected_indexes and _defensive_label_family(clip.label) == family
            ]
            if not family_candidates:
                continue
            index, clip = max(family_candidates, key=_review_reserved_clip_quality_key)
            add_clip(index, clip)
            reserved_defensive_count += 1
            if reserved_defensive_count >= defensive_reserve:
                break

        for index, clip in sorted(defensive, key=_review_reserved_clip_quality_key, reverse=True):
            if reserved_defensive_count >= defensive_reserve:
                break
            if index in selected_indexes:
                continue
            add_clip(index, clip)
            reserved_defensive_count += 1

    uncertain: list[tuple[int, CloudClip]] = []
    uncertain_reserve = 0
    if team_selection is not None and team_selection.mode == "team" and team_selection.includeUncertain:
        uncertain = [
            (index, clip)
            for index, clip in indexed_clips
            if _analysis_team_status(clip, team_selection) == "uncertain"
        ]
        uncertain_reserve = _uncertain_review_reserve_limit(max_clips, len(uncertain))

    for index, clip in sorted(
        uncertain,
        key=_review_reserved_clip_quality_key,
        reverse=True,
    )[:uncertain_reserve]:
        add_clip(index, clip)

    for index, clip in indexed_clips:
        add_clip(index, clip)
        if len(selected) >= max_clips:
            break

    return [clip for _, clip in sorted(selected, key=lambda item: item[0])]


def _review_reserved_clip_quality_key(
    item: tuple[int, CloudClip],
) -> tuple[float, float, float, float, float, float, float, int]:
    index, clip = item
    return (*_hybrid_clip_quality_key(clip), -index)


def _annotate_analysis_team_status(
    clips: Sequence[CloudClip],
    team_selection: Optional[TeamSelection],
) -> list[CloudClip]:
    annotated: list[CloudClip] = []
    for clip in clips:
        status = _analysis_team_status(clip, team_selection)
        updates: dict[str, object] = {"teamAttributionStatus": status}
        if team_selection is not None and team_selection.mode == "team" and status == "uncertain":
            updates["shouldAutoKeep"] = False
            updates["shouldEnableSlowMotion"] = False
        annotated.append(clip.model_copy(update=updates))
    return annotated


def _detected_teams_from_clips(clips: Sequence[CloudClip]) -> list[TeamOption]:
    best_by_key: dict[str, TeamOption] = {}
    for clip in clips:
        if clip.teamAttributionStatus == "uncertain":
            continue
        attribution = clip.teamAttribution
        if attribution is None:
            continue
        if attribution.confidence < MIN_DETECTED_TEAM_OPTION_CONFIDENCE:
            continue
        if _analysis_team_evidence_required(attribution) and not _analysis_has_confident_team_evidence(attribution):
            continue
        team_id = attribution.teamId or attribution.colorLabel
        label = attribution.label or attribution.colorLabel or attribution.teamId
        if not team_id or not label:
            continue
        key = _team_key(team_id) or team_id
        option_source = attribution.source if attribution.source in {"quick_scan", "provider", "manual", "unknown"} else "unknown"
        option = TeamOption(
            teamId=team_id,
            label=label,
            colorLabel=attribution.colorLabel,
            confidence=attribution.confidence,
            source=option_source,
        )
        current = best_by_key.get(key)
        if current is None or option.confidence > current.confidence:
            best_by_key[key] = option
    return sorted(best_by_key.values(), key=lambda option: (-option.confidence, option.label))[:4]


def _run_native_candidate_detection(
    source_path: Path,
    duration_seconds: float,
    settings: Settings,
    clip_limit: Optional[int] = None,
) -> tuple[list[CloudClip], int]:
    audio_profile = _extract_audio_profile(source_path, duration_seconds)
    shot_boundaries = _detect_shot_boundaries(source_path, duration_seconds, audio_profile)
    windows = _build_candidate_windows(
        duration_seconds=duration_seconds,
        audio_profile=audio_profile,
        shot_boundaries=shot_boundaries,
        settings=settings,
        clip_limit=clip_limit,
    )

    if not windows:
        windows = [_fallback_window(duration_seconds, audio_profile, settings)]

    resolved_limit = clip_limit or settings.max_returned_clips
    clips = [classify_window(window) for window in windows[:resolved_limit]]
    return clips, len(windows)


def _normalize_analysis_clips(
    clips: Sequence[CloudClip],
    duration_seconds: float,
    settings: Settings,
    clip_limit: Optional[int] = None,
) -> list[CloudClip]:
    normalized: list[CloudClip] = []
    for clip in clips:
        normalized_clip = _normalize_clip_for_analysis_context(clip, duration_seconds, settings)
        if normalized_clip is not None:
            normalized.append(normalized_clip)
    return normalized[: (clip_limit or settings.max_returned_clips)]


def _normalize_clip_for_analysis_context(
    clip: CloudClip,
    duration_seconds: float,
    settings: Settings,
) -> CloudClip | None:
    start = clamp(clip.startTime, 0.0, duration_seconds)
    end = clamp(clip.endTime, 0.0, duration_seconds)
    if end <= start:
        return None

    event_center = clip.eventCenter
    if event_center is not None:
        event_center = clamp(event_center, 0.0, duration_seconds)

    normalized = clip.model_copy(
        update={
            "startTime": round(start, 3),
            "endTime": round(end, 3),
            "eventCenter": round(event_center, 3) if event_center is not None else None,
        }
    )
    defensive_event_like = _is_defensive_label(normalized.label)
    shot_like = _is_shot_like_label(normalized.label)
    if defensive_event_like:
        normalized = _expand_defensive_clip_for_analysis_context(normalized, duration_seconds, settings)
        if normalized is None:
            return None
    elif shot_like:
        normalized = _expand_shot_clip_for_analysis_context(normalized, duration_seconds, settings)
        if normalized is None:
            return None
        if _analysis_clip_context_score(normalized) < 0.45:
            return None
        auto_keep_allowed = _analysis_clip_auto_keep_allowed(normalized)
        return normalized.model_copy(
            update={
                "shouldAutoKeep": normalized.shouldAutoKeep and auto_keep_allowed,
                "shouldEnableSlowMotion": normalized.shouldEnableSlowMotion and auto_keep_allowed,
                "nativeShotSignals": _native_shot_signals_for_analysis_clip(normalized),
            }
        )

    if normalized.endTime - normalized.startTime < settings.min_clip_duration_seconds:
        return None
    if normalized.endTime - normalized.startTime > settings.max_clip_duration_seconds:
        normalized = normalized.model_copy(
            update={"endTime": round(min(duration_seconds, normalized.startTime + settings.max_clip_duration_seconds), 3)}
        )
    auto_keep_allowed = _analysis_clip_auto_keep_allowed(normalized)
    return normalized.model_copy(
        update={
            "shouldAutoKeep": normalized.shouldAutoKeep and auto_keep_allowed,
            "shouldEnableSlowMotion": normalized.shouldEnableSlowMotion and auto_keep_allowed,
            "nativeShotSignals": _native_shot_signals_for_analysis_clip(normalized),
        }
    )


def _expand_shot_clip_for_analysis_context(
    clip: CloudClip,
    duration_seconds: float,
    settings: Settings,
) -> CloudClip | None:
    if clip.eventCenter is None:
        return None

    event_center = clamp(clip.eventCenter, 0.0, duration_seconds)
    desired_start = min(clip.startTime, event_center - NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS)
    desired_end = max(clip.endTime, event_center + NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
    start = max(0.0, desired_start)
    end = min(duration_seconds, desired_end)

    min_duration = settings.min_clip_duration_seconds
    if end - start < min_duration:
        missing = min_duration - (end - start)
        start = max(0.0, start - (missing / 2.0))
        end = min(duration_seconds, end + (missing / 2.0))
        if end - start < min_duration:
            start = max(0.0, min(start, duration_seconds - min_duration))
            end = min(duration_seconds, start + min_duration)

    if end - start > settings.max_clip_duration_seconds:
        preferred_lead = min(
            settings.max_clip_duration_seconds - NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS,
            max(NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS, settings.max_clip_duration_seconds * 0.66),
        )
        start = max(0.0, event_center - preferred_lead)
        end = min(duration_seconds, start + settings.max_clip_duration_seconds)
        if end < event_center + NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS:
            end = min(duration_seconds, event_center + NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
            start = max(0.0, end - settings.max_clip_duration_seconds)

    if end <= start:
        return None

    lead_in = event_center - start
    follow_through = end - event_center
    if lead_in < NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS:
        return None
    if follow_through < NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS:
        return None
    if end - start < settings.min_clip_duration_seconds:
        return None

    return clip.model_copy(
        update={
            "startTime": round(start, 3),
            "endTime": round(end, 3),
            "eventCenter": round(event_center, 3),
        }
    )


def _expand_defensive_clip_for_analysis_context(
    clip: CloudClip,
    duration_seconds: float,
    settings: Settings,
) -> CloudClip | None:
    event_center = clip.eventCenter
    if event_center is None:
        event_center = (clip.startTime + clip.endTime) / 2.0
    event_center = clamp(event_center, 0.0, duration_seconds)
    desired_start = min(clip.startTime, event_center - NATIVE_DEFENSIVE_CONTEXT_TARGET_LEAD_SECONDS)
    desired_end = max(clip.endTime, event_center + NATIVE_DEFENSIVE_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
    start = max(0.0, desired_start)
    end = min(duration_seconds, desired_end)

    target_duration = min(settings.max_clip_duration_seconds, max(settings.min_clip_duration_seconds, NATIVE_DEFENSIVE_CONTEXT_TARGET_SECONDS))
    if end - start < target_duration:
        missing = target_duration - (end - start)
        start = max(0.0, start - (missing * 0.55))
        end = min(duration_seconds, end + (missing * 0.45))
        if end - start < target_duration:
            start = max(0.0, min(start, duration_seconds - target_duration))
            end = min(duration_seconds, start + target_duration)

    if end - start > settings.max_clip_duration_seconds:
        preferred_lead = min(
            settings.max_clip_duration_seconds - NATIVE_DEFENSIVE_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS,
            max(NATIVE_DEFENSIVE_CONTEXT_TARGET_LEAD_SECONDS, settings.max_clip_duration_seconds * 0.55),
        )
        start = max(0.0, event_center - preferred_lead)
        end = min(duration_seconds, start + settings.max_clip_duration_seconds)
        if end < event_center + NATIVE_DEFENSIVE_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS:
            end = min(duration_seconds, event_center + NATIVE_DEFENSIVE_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
            start = max(0.0, end - settings.max_clip_duration_seconds)

    if end <= start:
        return None
    if end - start < settings.min_clip_duration_seconds:
        return None

    return clip.model_copy(
        update={
            "startTime": round(start, 3),
            "endTime": round(end, 3),
            "eventCenter": round(event_center, 3),
        }
    )


def _analysis_clip_auto_keep_allowed(clip: CloudClip) -> bool:
    if clip.endTime - clip.startTime < 2.0:
        return False
    if clip.combinedScore < 0.55 or clip.confidence < 0.52:
        return False
    if _analysis_clip_context_score(clip) < 0.45:
        return False
    return True


def _analysis_clip_context_score(clip: CloudClip) -> float:
    return _hybrid_clip_context_score(clip)


def _native_shot_signals_for_analysis_clip(clip: CloudClip) -> CloudNativeShotSignals:
    is_shot_like = _is_shot_like_label(clip.label)
    defensive_event_like = _is_defensive_label(clip.label)
    duration = max(0.0, clip.endTime - clip.startTime)
    event_center = clip.eventCenter
    if event_center is None:
        lead_in = 0.0
        follow_through = 0.0
    else:
        bounded_center = min(max(event_center, clip.startTime), clip.endTime)
        lead_in = max(0.0, bounded_center - clip.startTime)
        follow_through = max(0.0, clip.endTime - bounded_center)

    if defensive_event_like:
        setup_context_score = min(1.0, lead_in / NATIVE_DEFENSIVE_CONTEXT_TARGET_LEAD_SECONDS)
        outcome_context_score = min(1.0, follow_through / NATIVE_DEFENSIVE_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
        duration_score = min(1.0, duration / max(4.0, NATIVE_DEFENSIVE_CONTEXT_TARGET_SECONDS))
        if lead_in <= 0.0 or follow_through <= 0.0:
            balance_score = 0.0
        else:
            balance_score = min(lead_in, follow_through) / max(lead_in, follow_through)
        event_center_quality = (
            (setup_context_score * 0.3)
            + (outcome_context_score * 0.3)
            + (duration_score * 0.25)
            + (balance_score * 0.15)
        )
        timing_window_ok = (
            duration >= NATIVE_SHOT_SIGNAL_MIN_DURATION_SECONDS
            and lead_in >= NATIVE_DEFENSIVE_CONTEXT_MIN_LEAD_SECONDS
            and follow_through >= NATIVE_DEFENSIVE_CONTEXT_MIN_FOLLOW_THROUGH_SECONDS
        )
    elif not is_shot_like:
        setup_context_score = 0.0
        outcome_context_score = 0.0
        event_center_quality = 0.0
        timing_window_ok = duration >= 2.0
    else:
        setup_context_score = min(1.0, lead_in / NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS)
        outcome_context_score = min(1.0, follow_through / NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
        duration_score = min(1.0, duration / max(4.5, NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS + NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS))
        if lead_in <= 0.0 or follow_through <= 0.0:
            balance_score = 0.0
        else:
            balance_score = min(lead_in, follow_through) / max(lead_in, follow_through)
        event_center_quality = (setup_context_score * 0.34) + (outcome_context_score * 0.28) + (duration_score * 0.2) + (balance_score * 0.18)
        timing_window_ok = (
            duration >= NATIVE_SHOT_SIGNAL_MIN_DURATION_SECONDS
            and lead_in >= NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS
            and follow_through >= NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS
        )

    outcome, outcome_confidence, evidence_source, reliability_score = _native_outcome_hint_for_label(
        clip.label,
        clip.confidence,
        is_shot_like,
        defensive_event_like,
    )
    return CloudNativeShotSignals(
        isShotLike=is_shot_like,
        leadInSeconds=round(lead_in, 3),
        followThroughSeconds=round(follow_through, 3),
        setupContextScore=round(setup_context_score, 4),
        outcomeContextScore=round(outcome_context_score, 4),
        eventCenterQuality=round(max(0.0, min(1.0, event_center_quality)), 4),
        contextQualityScore=_analysis_clip_context_score(clip),
        timingWindowOk=timing_window_ok,
        outcome=outcome,
        outcomeConfidence=round(outcome_confidence, 4),
        outcomeEvidenceSource=evidence_source,
        outcomeReliabilityScore=round(reliability_score, 4),
    )


def _native_outcome_hint_for_label(
    label: str,
    confidence: float,
    is_shot_like: bool,
    defensive_event_like: bool = False,
) -> tuple[str, float, str, float]:
    confidence = min(max(confidence, 0.0), 1.0)
    if defensive_event_like and any(token in label.strip().lower() for token in ("block", "blocked")):
        return "blocked", confidence, "defensive_event", min(0.78, 0.52 + (confidence * 0.26))
    if defensive_event_like and not is_shot_like:
        return "not_shot", 1.0, "defensive_event", 0.9
    if not is_shot_like:
        return "not_shot", 1.0, "non_shot", 0.82

    normalized = label.strip().lower()
    if any(token in normalized for token in ("block", "blocked")):
        return "blocked", confidence, "label_only", min(0.68, 0.42 + (confidence * 0.18))
    if any(token in normalized for token in ("miss", "missed")):
        return "missed", min(1.0, confidence * 0.85), "label_only", min(0.68, 0.42 + (confidence * 0.18))
    if any(token in normalized for token in ("made", "bucket", "basket", "dunk")):
        return "made", min(1.0, confidence * 0.9), "label_only", min(0.68, 0.42 + (confidence * 0.18))
    if any(token in normalized for token in ("attempt", "layup", "finish")):
        return "uncertain", 0.0, "uncertain", 0.35
    return "uncertain", 0.0, "uncertain", 0.35


def _merge_hybrid_detection_clips(
    *,
    external_clips: Sequence[CloudClip],
    native_clips: Sequence[CloudClip],
    clip_limit: int,
) -> list[CloudClip]:
    ranked = sorted([*external_clips, *native_clips], key=_hybrid_clip_quality_key, reverse=True)
    kept: list[CloudClip] = []
    for clip in ranked:
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(kept)
                if _clip_overlap_ratio(clip, existing) > HYBRID_OVERLAP_DEDUPE_RATIO
            ),
            None,
        )
        if duplicate_index is None:
            kept.append(clip)
            continue
        if _hybrid_clip_quality_key(clip) > _hybrid_clip_quality_key(kept[duplicate_index]):
            kept[duplicate_index] = clip

    kept.sort(key=_hybrid_clip_quality_key, reverse=True)
    return kept[:clip_limit]


def _hybrid_clip_quality_key(clip: CloudClip) -> tuple[float, float, float, float, float, float, float]:
    duration = max(0.0, clip.endTime - clip.startTime)
    return (
        1.0 if duration >= 2.0 else 0.0,
        _hybrid_clip_context_score(clip),
        1.0 if clip.shouldAutoKeep else 0.0,
        clip.combinedScore,
        clip.confidence,
        clip.visualScore,
        clip.motionScore,
    )


def _hybrid_clip_context_score(clip: CloudClip) -> float:
    duration = max(0.0, clip.endTime - clip.startTime)
    if duration < 2.0:
        return 0.0
    if _is_defensive_label(clip.label):
        return min(1.0, duration / 4.5)
    if not _is_shot_like_label(clip.label):
        return min(1.0, duration / 4.5)
    if clip.eventCenter is None:
        return 0.2

    event_center = min(max(clip.eventCenter, clip.startTime), clip.endTime)
    lead_in = max(0.0, event_center - clip.startTime)
    follow_through = max(0.0, clip.endTime - event_center)
    if lead_in <= 0.0 or follow_through <= 0.0:
        return 0.0

    lead_score = min(1.0, lead_in / NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS)
    follow_score = min(1.0, follow_through / NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
    duration_score = min(1.0, duration / 4.5)
    balance_score = min(lead_in, follow_through) / max(lead_in, follow_through)
    return round((lead_score * 0.36) + (follow_score * 0.28) + (duration_score * 0.22) + (balance_score * 0.14), 4)


def _clip_overlap_ratio(left: CloudClip, right: CloudClip) -> float:
    overlap = max(0.0, min(left.endTime, right.endTime) - max(left.startTime, right.startTime))
    if overlap <= 0.0:
        return 0.0
    shortest = min(max(left.endTime - left.startTime, 0.001), max(right.endTime - right.startTime, 0.001))
    return overlap / shortest


def _is_shot_like_label(label: str) -> bool:
    normalized = label.strip().lower()
    return any(
        token in normalized
        for token in ("shot", "bucket", "basket", "layup", "dunk", "finish", "jumper", "three", "3pt")
    )


def _is_defensive_label(label: str) -> bool:
    normalized = label.strip().lower()
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    if tokens & {
        "defense",
        "defensive",
        "block",
        "blocked",
        "steal",
        "strip",
        "contest",
        "pressure",
        "lockdown",
        "deflection",
        "deflected",
        "charge",
        "takeaway",
        "takeaways",
        "intercept",
        "intercepted",
        "interception",
        "poke",
        "poked",
        "rip",
        "ripped",
    }:
        return True
    if "loose ball" in normalized:
        return True
    if "turnover" in tokens and "unforced" not in tokens and tokens & {
        "forced",
        "force",
        "defensive",
        "defense",
        "steal",
        "strip",
        "takeaway",
    }:
        return True
    return "stop" in tokens and (normalized == "stop" or "defensive stop" in normalized or "defense stop" in normalized)


def _defensive_label_family(label: str) -> Optional[str]:
    normalized = label.strip().lower()
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    if tokens & {"block", "blocked", "contest", "swat", "swatted", "rejection", "rejected"}:
        return "block"
    if tokens & {
        "steal",
        "stolen",
        "strip",
        "stripped",
        "takeaway",
        "takeaways",
        "intercept",
        "intercepted",
        "interception",
        "pickpocket",
        "poke",
        "poked",
        "rip",
        "ripped",
    }:
        return "steal"
    if tokens & {"deflection", "deflected", "charge"} or "loose ball" in normalized:
        return "forced_turnover"
    if "turnover" in tokens and (tokens & {"forced", "force", "defensive", "defense", "steal", "strip", "takeaway"}):
        return "forced_turnover"
    if "stop" in tokens and ("defensive stop" in normalized or "defense stop" in normalized or normalized == "stop"):
        return "defensive_stop"
    if tokens & {
        "defense",
        "defensive",
        "pressure",
        "lockdown",
    }:
        return "defensive"
    return None


def _probe_duration(path: Path, fallback: float) -> float:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return max(fallback, 1.0)

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
        payload = json.loads(completed.stdout or "{}")
        duration = float(payload.get("format", {}).get("duration", fallback))
        return max(duration, 1.0)
    except (OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError):
        return max(fallback, 1.0)


def _detect_shot_boundaries(
    path: Path,
    duration_seconds: Optional[float] = None,
    audio_profile: Optional[List[float]] = None,
) -> List[float]:
    duration = duration_seconds if duration_seconds is not None else _probe_duration(path, fallback=1.0)
    frame_signals = _extract_visual_frame_signals(path, duration)
    if not frame_signals:
        return []
    return _visual_event_boundaries_from_signals(
        frame_signals,
        audio_profile or [],
        duration_seconds=duration,
    )


def _extract_visual_frame_signals(path: Path, duration_seconds: float) -> List[VisualFrameSignal]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return []

    frame_size = VISUAL_EVENT_FRAME_WIDTH * VISUAL_EVENT_FRAME_HEIGHT * 3
    command = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(path),
        "-vf",
        "fps={fps},scale={width}:{height}:flags=fast_bilinear".format(
            fps=VISUAL_EVENT_SAMPLE_FPS,
            width=VISUAL_EVENT_FRAME_WIDTH,
            height=VISUAL_EVENT_FRAME_HEIGHT,
        ),
        "-an",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=True,
            timeout=max(15.0, min(120.0, duration_seconds * 0.12)),
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []

    raw = completed.stdout or b""
    frame_count = len(raw) // frame_size
    if frame_count < 2:
        return []

    signals: List[VisualFrameSignal] = []
    previous = raw[:frame_size]
    for index in range(1, frame_count):
        start = index * frame_size
        current = raw[start : start + frame_size]
        if len(current) < frame_size:
            break
        time_seconds = index / VISUAL_EVENT_SAMPLE_FPS
        full_motion = _region_motion_score(
            current,
            previous,
            VISUAL_EVENT_FRAME_WIDTH,
            VISUAL_EVENT_FRAME_HEIGHT,
            0,
            VISUAL_EVENT_FRAME_WIDTH,
            0,
            VISUAL_EVENT_FRAME_HEIGHT,
        )
        upper_motion = _region_motion_score(
            current,
            previous,
            VISUAL_EVENT_FRAME_WIDTH,
            VISUAL_EVENT_FRAME_HEIGHT,
            0,
            VISUAL_EVENT_FRAME_WIDTH,
            0,
            VISUAL_EVENT_FRAME_HEIGHT // 2,
        )
        center_motion = _region_motion_score(
            current,
            previous,
            VISUAL_EVENT_FRAME_WIDTH,
            VISUAL_EVENT_FRAME_HEIGHT,
            VISUAL_EVENT_FRAME_WIDTH // 4,
            (VISUAL_EVENT_FRAME_WIDTH * 3) // 4,
            0,
            VISUAL_EVENT_FRAME_HEIGHT,
        )
        lower_motion = _region_motion_score(
            current,
            previous,
            VISUAL_EVENT_FRAME_WIDTH,
            VISUAL_EVENT_FRAME_HEIGHT,
            0,
            VISUAL_EVENT_FRAME_WIDTH,
            VISUAL_EVENT_FRAME_HEIGHT // 2,
            VISUAL_EVENT_FRAME_HEIGHT,
        )
        signals.append((round(time_seconds, 3), full_motion, upper_motion, center_motion, lower_motion))
        previous = current

    return signals


def _region_motion_score(
    current: bytes,
    previous: bytes,
    width: int,
    height: int,
    x_start: int,
    x_end: int,
    y_start: int,
    y_end: int,
) -> float:
    x_start = max(0, min(x_start, width))
    x_end = max(x_start, min(x_end, width))
    y_start = max(0, min(y_start, height))
    y_end = max(y_start, min(y_end, height))
    total = 0
    count = 0
    for y in range(y_start, y_end):
        row_offset = y * width * 3
        for x in range(x_start, x_end):
            offset = row_offset + (x * 3)
            total += abs(current[offset] - previous[offset])
            total += abs(current[offset + 1] - previous[offset + 1])
            total += abs(current[offset + 2] - previous[offset + 2])
            count += 3
    if count == 0:
        return 0.0
    # Small scaled-frame deltas are meaningful for basketball action, so normalize
    # around a 16/255 mean channel difference instead of requiring scene-cut motion.
    return round(clamp((total / count) / 16.0, 0.0, 1.0), 4)


def _visual_event_boundaries_from_signals(
    frame_signals: Sequence[VisualFrameSignal],
    audio_profile: Sequence[float],
    *,
    duration_seconds: float,
) -> List[float]:
    if not frame_signals:
        return []

    scored_frames: List[VisualEventFrame] = []
    for signal in frame_signals:
        time_seconds, full_motion, upper_motion, center_motion, lower_motion = _unpack_visual_frame_signal(signal)
        visual_score = clamp(
            (upper_motion * 0.44) + (center_motion * 0.32) + (lower_motion * 0.12) + (full_motion * 0.12),
            0.0,
            1.0,
        )
        audio_score = _audio_peak_near_time(audio_profile, time_seconds)
        edge_penalty = 1.0
        if time_seconds < 1.0 or time_seconds > max(duration_seconds - 0.75, 0.0):
            edge_penalty = 0.62
        score = clamp(((visual_score * 0.78) + (audio_score * 0.22)) * edge_penalty, 0.0, 1.0)
        scored_frames.append(
            VisualEventFrame(
                time_seconds=time_seconds,
                score=round(score, 4),
                visual_score=round(visual_score, 4),
                full_motion=full_motion,
                upper_motion=upper_motion,
                center_motion=center_motion,
                lower_motion=lower_motion,
                audio_score=audio_score,
            )
        )

    candidates: List[VisualEventFrame] = []
    for frame in scored_frames:
        setup_score, outcome_score = _visual_event_context_scores(frame, scored_frames)
        if frame.visual_score < VISUAL_EVENT_MIN_VISUAL_SCORE:
            continue
        if setup_score < VISUAL_EVENT_MIN_SETUP_CONTEXT_SCORE:
            continue
        if outcome_score < VISUAL_EVENT_MIN_OUTCOME_CONTEXT_SCORE:
            continue
        if _visual_event_is_setup_before_stronger_result(frame, scored_frames, setup_score, outcome_score):
            continue
        if _outcome_aware_visual_event_score(frame, scored_frames) < VISUAL_EVENT_MIN_SCORE:
            continue
        candidates.append(frame)
    clusters = _cluster_visual_event_frames(candidates)

    selected: List[tuple[float, float]] = []
    for cluster in clusters:
        best_frame = max(
            cluster,
            key=lambda frame: (
                _outcome_aware_visual_event_score(frame, scored_frames)
                + min(max(frame.time_seconds - cluster[0].time_seconds, 0.0) * 0.035, 0.055),
                frame.score,
                frame.time_seconds,
            ),
        )
        selected.append((best_frame.time_seconds, _outcome_aware_visual_event_score(best_frame, scored_frames)))

    selected.sort(key=lambda item: item[1], reverse=True)
    chosen: List[float] = []
    for time_seconds, _ in selected:
        if all(abs(time_seconds - existing) >= VISUAL_EVENT_MIN_GAP_SECONDS for existing in chosen):
            chosen.append(round(time_seconds, 3))
        if len(chosen) >= VISUAL_EVENT_MAX_BOUNDARIES:
            break

    return sorted(chosen)


def _unpack_visual_frame_signal(signal: VisualFrameSignal) -> tuple[float, float, float, float, float]:
    time_seconds, full_motion, upper_motion, center_motion = signal[:4]
    lower_motion = signal[4] if len(signal) >= 5 else center_motion
    return time_seconds, full_motion, upper_motion, center_motion, lower_motion


def _cluster_visual_event_frames(frames: Sequence[VisualEventFrame]) -> List[List[VisualEventFrame]]:
    clusters: List[List[VisualEventFrame]] = []
    for frame in sorted(frames, key=lambda item: item.time_seconds):
        if not clusters or frame.time_seconds - clusters[-1][-1].time_seconds > VISUAL_EVENT_SEQUENCE_GAP_SECONDS:
            clusters.append([frame])
        else:
            clusters[-1].append(frame)
    return clusters


def _outcome_aware_visual_event_score(frame: VisualEventFrame, frames: Sequence[VisualEventFrame]) -> float:
    setup_score, outcome_score = _visual_event_context_scores(frame, frames)
    # A release-only spike should not beat the rim/result frame when the
    # surrounding frames show setup and follow-through. Setup distinguishes a
    # real shot sequence from random camera motion; outcome context keeps the
    # anchor close to the basket/result instead of the release.
    context_bonus = min(
        (setup_score * 0.28) + (outcome_score * 0.12) + (min(setup_score, outcome_score) * 0.08),
        0.36,
    )
    return round(clamp(frame.score + context_bonus, 0.0, 1.0), 4)


def _visual_event_context_scores(frame: VisualEventFrame, frames: Sequence[VisualEventFrame]) -> tuple[float, float]:
    setup_score = max(
        (
            _shot_context_visual_score(candidate)
            for candidate in frames
            if frame.time_seconds - VISUAL_EVENT_CONTEXT_SECONDS <= candidate.time_seconds <= frame.time_seconds - 0.25
        ),
        default=0.0,
    )
    outcome_score = max(
        (
            _shot_result_visual_score(candidate)
            for candidate in frames
            if frame.time_seconds + 0.25 <= candidate.time_seconds <= frame.time_seconds + VISUAL_EVENT_CONTEXT_SECONDS
        ),
        default=0.0,
    )
    return setup_score, outcome_score


def _visual_event_is_setup_before_stronger_result(
    frame: VisualEventFrame,
    frames: Sequence[VisualEventFrame],
    setup_score: float,
    outcome_score: float,
) -> bool:
    if outcome_score < max(VISUAL_EVENT_MIN_OUTCOME_CONTEXT_SCORE, setup_score * 1.45):
        return False
    later_peak = max(
        (
            _shot_result_visual_score(candidate)
            for candidate in frames
            if frame.time_seconds + 0.25 <= candidate.time_seconds <= frame.time_seconds + 0.75
        ),
        default=0.0,
    )
    current_context_score = _shot_context_visual_score(frame)
    return later_peak > current_context_score * 0.6


def _shot_context_visual_score(frame: VisualEventFrame) -> float:
    return clamp((frame.upper_motion * 0.52) + (frame.center_motion * 0.34) + (frame.full_motion * 0.14), 0.0, 1.0)


def _shot_result_visual_score(frame: VisualEventFrame) -> float:
    return clamp(
        (frame.center_motion * 0.42) + (frame.lower_motion * 0.38) + (frame.upper_motion * 0.14) + (frame.full_motion * 0.06),
        0.0,
        1.0,
    )


def _audio_peak_near_time(audio_profile: Sequence[float], time_seconds: float) -> float:
    if not audio_profile:
        return 0.0
    center = max(int(time_seconds / 0.5), 0)
    start = max(center - 1, 0)
    end = min(center + 2, len(audio_profile))
    return clamp(max(audio_profile[start:end] or [0.0]), 0.0, 1.0)


def _extract_audio_profile(path: Path, duration_seconds: float) -> List[float]:
    bucket_count = max(int(math.ceil(duration_seconds / 0.5)), 1)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return [0.0] * bucket_count

    with tempfile.TemporaryDirectory(prefix="hoops-audio-") as temp_dir:
        wav_path = Path(temp_dir) / "audio.wav"
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(wav_path),
        ]
        try:
            subprocess.run(command, capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            return [0.0] * bucket_count

        try:
            with wave.open(str(wav_path), "rb") as wav_file:
                sample_rate = wav_file.getframerate() or 16000
                frames = wav_file.readframes(wav_file.getnframes())
        except (wave.Error, FileNotFoundError):
            return [0.0] * bucket_count

    samples = array("h")
    samples.frombytes(frames)
    if not samples:
        return [0.0] * bucket_count

    samples_per_bucket = max(int(sample_rate * 0.5), 1)
    peaks: List[float] = []
    for index in range(bucket_count):
        start = index * samples_per_bucket
        end = min(start + samples_per_bucket, len(samples))
        if start >= len(samples):
            peaks.append(0.0)
            continue
        bucket = samples[start:end]
        rms = math.sqrt(sum(sample * sample for sample in bucket) / max(len(bucket), 1))
        peaks.append(rms / 32768.0)

    maximum = max(peaks) or 1.0
    return [clamp(value / maximum, 0.0, 1.0) for value in peaks]


def _build_candidate_windows(
    duration_seconds: float,
    audio_profile: List[float],
    shot_boundaries: List[float],
    settings: Settings,
    clip_limit: Optional[int] = None,
) -> List[CandidateWindow]:
    resolved_limit = clip_limit or settings.max_returned_clips
    window_span = min(max(4.5, settings.min_clip_duration_seconds + 1.5), settings.max_clip_duration_seconds)
    stride = 1.5
    windows: List[CandidateWindow] = []

    time_cursor = 0.0
    while time_cursor < duration_seconds:
        end_time = min(duration_seconds, time_cursor + window_span)
        if end_time - time_cursor < settings.min_clip_duration_seconds:
            break

        bucket_start = max(int(time_cursor / 0.5), 0)
        bucket_end = max(int(math.ceil(end_time / 0.5)), bucket_start + 1)
        slice_values = audio_profile[bucket_start:bucket_end] or [0.0]

        audio_score = max(slice_values)
        audio_mean = mean(slice_values)
        volatility = max(audio_score - audio_mean, 0.0)
        center = (time_cursor + end_time) / 2.0
        center_bias = 1.0 - abs((center / max(duration_seconds, 1.0)) - 0.5) * 1.35
        shot_context_score, shot_event_time = _shot_context_score_for_window(
            start_time=time_cursor,
            end_time=end_time,
            center_time=center,
            shot_boundaries=shot_boundaries,
        )
        center_transition_boost = 0.14 if any(abs(boundary - center) <= 1.2 for boundary in shot_boundaries) else 0.0
        context_boost = 0.16 * shot_context_score

        motion_score = clamp(
            (audio_score * 0.65) + (volatility * 1.1) + (center_transition_boost * 0.75) + (context_boost * 0.55),
            0.0,
            1.0,
        )
        visual_score = clamp(
            (audio_mean * 0.45) + (max(center_bias, 0.0) * 0.25) + center_transition_boost + context_boost,
            0.0,
            1.0,
        )
        baseline_score = clamp((audio_score * 0.42) + (motion_score * 0.34) + (visual_score * 0.24), 0.0, 1.0)
        combined_score = clamp(baseline_score + (shot_context_score * 0.12), 0.0, 1.0)
        peak_time = shot_event_time if shot_event_time is not None and shot_context_score >= 0.45 else center

        windows.append(
            CandidateWindow(
                start_time=time_cursor,
                end_time=end_time,
                peak_time=peak_time,
                audio_score=audio_score,
                visual_score=visual_score,
                motion_score=motion_score,
                combined_score=combined_score,
                event_context_score=shot_context_score,
            )
        )

        time_cursor += stride

    segmented = _segment_with_hysteresis(windows, settings, clip_limit=resolved_limit)
    if segmented:
        return _backfill_segmented_candidate_windows(segmented, windows, resolved_limit)

    return sorted(windows, key=lambda item: item.combined_score, reverse=True)[:resolved_limit]


def _backfill_segmented_candidate_windows(
    segmented: Sequence[CandidateWindow],
    windows: Sequence[CandidateWindow],
    resolved_limit: int,
) -> List[CandidateWindow]:
    resolved_limit = max(0, int(resolved_limit))
    if resolved_limit == 0:
        return []

    kept = list(segmented[:resolved_limit])
    if len(kept) >= resolved_limit:
        return sorted(kept, key=_candidate_window_recall_key, reverse=True)[:resolved_limit]

    for window in sorted(windows, key=_candidate_window_recall_key, reverse=True):
        if len(kept) >= resolved_limit:
            break
        if any(_candidate_window_overlap_ratio(window, existing) > NATIVE_RECALL_BACKFILL_OVERLAP_RATIO for existing in kept):
            continue
        kept.append(window)

    return sorted(kept, key=_candidate_window_recall_key, reverse=True)[:resolved_limit]


def _candidate_window_recall_key(window: CandidateWindow) -> tuple[float, float, float, float, float]:
    return (
        window.event_context_score,
        window.combined_score,
        window.motion_score,
        window.visual_score,
        window.audio_score,
    )


def _candidate_window_overlap_ratio(left: CandidateWindow, right: CandidateWindow) -> float:
    overlap = max(0.0, min(left.end_time, right.end_time) - max(left.start_time, right.start_time))
    if overlap <= 0.0:
        return 0.0
    shortest = min(max(left.end_time - left.start_time, 0.001), max(right.end_time - right.start_time, 0.001))
    return overlap / shortest


def _shot_context_score_for_window(
    *,
    start_time: float,
    end_time: float,
    center_time: float,
    shot_boundaries: List[float],
) -> tuple[float, float | None]:
    best_score = 0.0
    best_boundary: float | None = None
    duration = max(end_time - start_time, 0.001)
    half_duration = max(duration / 2.0, 0.001)

    for boundary in shot_boundaries:
        if boundary < start_time or boundary > end_time:
            continue

        lead_in = max(0.0, boundary - start_time)
        follow_through = max(0.0, end_time - boundary)
        if lead_in <= 0.0 or follow_through <= 0.0:
            continue
        if lead_in < NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS:
            continue
        if follow_through < NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS:
            continue

        lead_score = min(1.0, lead_in / NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS)
        follow_score = min(1.0, follow_through / NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
        balance_score = min(lead_in, follow_through) / max(lead_in, follow_through)
        center_score = 1.0 - min(abs(boundary - center_time) / half_duration, 1.0)
        score = (
            (lead_score * 0.34)
            + (follow_score * 0.3)
            + (balance_score * 0.18)
            + (center_score * 0.18)
        )
        if score > best_score:
            best_score = score
            best_boundary = boundary

    return round(clamp(best_score, 0.0, 1.0), 4), best_boundary


def _segment_with_hysteresis(windows: List[CandidateWindow], settings: Settings, clip_limit: Optional[int] = None) -> List[CandidateWindow]:
    resolved_limit = clip_limit or settings.max_returned_clips
    high_threshold = 0.66
    low_threshold = 0.48
    active: List[CandidateWindow] = []
    merged: List[CandidateWindow] = []

    for window in windows:
        if not active:
            if window.combined_score >= high_threshold:
                active = [window]
            continue

        if window.combined_score >= low_threshold:
            active.append(window)
            continue

        merged.append(_collapse_windows(active, settings))
        active = [window] if window.combined_score >= high_threshold else []

    if active:
        merged.append(_collapse_windows(active, settings))

    merged.sort(key=lambda item: item.combined_score, reverse=True)
    return merged[:resolved_limit]


def _collapse_windows(group: List[CandidateWindow], settings: Settings) -> CandidateWindow:
    peak_window = max(group, key=lambda item: (item.event_context_score, item.combined_score))
    anchor_window = peak_window if peak_window.event_context_score >= 0.45 else group[0]

    start_time = max(anchor_window.start_time - settings.clip_padding_seconds, 0.0)
    group_end = peak_window.end_time if peak_window.event_context_score >= 0.45 else group[-1].end_time
    padded_end = group_end + settings.clip_padding_seconds
    max_end = max(group_end, start_time + settings.max_clip_duration_seconds)
    end_time = min(padded_end, max_end)
    duration = end_time - start_time

    if duration < settings.min_clip_duration_seconds:
        end_time = start_time + settings.min_clip_duration_seconds
    if end_time - start_time > settings.max_clip_duration_seconds:
        end_time = start_time + settings.max_clip_duration_seconds

    return CandidateWindow(
        start_time=start_time,
        end_time=end_time,
        peak_time=peak_window.peak_time,
        audio_score=max(item.audio_score for item in group),
        visual_score=mean(item.visual_score for item in group),
        motion_score=max(item.motion_score for item in group),
        combined_score=max(item.combined_score for item in group),
        event_context_score=max(item.event_context_score for item in group),
    )


def _fallback_window(duration_seconds: float, audio_profile: List[float], settings: Settings) -> CandidateWindow:
    peak_index = max(range(len(audio_profile)), key=lambda index: audio_profile[index], default=0)
    center = min((peak_index * 0.5) + 1.0, max(duration_seconds - (settings.min_clip_duration_seconds / 2.0), 0.0))
    start_time = max(center - 1.6, 0.0)
    end_time = min(duration_seconds, start_time + 4.0)
    if end_time - start_time < settings.min_clip_duration_seconds:
        end_time = min(duration_seconds, start_time + settings.min_clip_duration_seconds)

    audio_score = audio_profile[peak_index] if audio_profile else 0.0
    visual_score = clamp(0.35 + (audio_score * 0.2), 0.0, 0.7)
    motion_score = clamp(0.38 + (audio_score * 0.25), 0.0, 0.75)
    combined_score = clamp(0.48 + (audio_score * 0.3), 0.0, 0.82)

    return CandidateWindow(
        start_time=start_time,
        end_time=end_time,
        peak_time=(start_time + end_time) / 2.0,
        audio_score=audio_score,
        visual_score=visual_score,
        motion_score=motion_score,
        combined_score=combined_score,
    )
