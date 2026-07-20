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
from .detection_pipeline import (
    annotate_external_clips,
    pipeline_summary_for_clips,
    run_staged_detection_pipeline,
    with_merge_provenance,
)
from .external_providers import detect_with_optional_external_provider, rerank_with_optional_external_provider
from .models import CandidateWindow, CloudAnalysisResult, CloudClip, CloudDiagnostics, CloudNativeShotSignals, DetectionPipelineSummary, PipelineError, StoredJob, TeamOption, TeamSelection, clamp
from .team_identity import team_identity_matches, team_key
from .team_quick_scan import TeamQuickScanReport, apply_team_quick_scan_with_report


NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS = 2.0
NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS = 1.25
NATIVE_SHOT_SIGNAL_MIN_DURATION_SECONDS = 3.0
NATIVE_DEFENSIVE_CONTEXT_TARGET_LEAD_SECONDS = 1.5
NATIVE_DEFENSIVE_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS = 1.2
NATIVE_DEFENSIVE_CONTEXT_TARGET_SECONDS = 4.0
NATIVE_DEFENSIVE_CONTEXT_MIN_LEAD_SECONDS = 0.6
NATIVE_DEFENSIVE_CONTEXT_MIN_FOLLOW_THROUGH_SECONDS = 0.5
HYBRID_OVERLAP_DEDUPE_RATIO = 0.55
TEMPORAL_DEDUPE_MIN_OVERLAP_RATIO = 0.25
TEMPORAL_DEDUPE_CENTER_GAP_SECONDS = 1.25
TEMPORAL_DEDUPE_SCORE_BOOST_WEIGHT = 0.22
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
AUDIO_PROFILE_BUCKET_SECONDS = 0.5
AUDIO_POP_EVENT_CENTER_THRESHOLD = 0.45
AUDIO_REACTION_BOUNDARY_MIN_SCORE = 0.32
AUDIO_REACTION_BOUNDARY_MIN_GAP_SECONDS = 2.25
AUDIO_REACTION_BOUNDARY_MAX_COUNT = 96
AUDIO_REACTION_BOUNDARY_CONTEXT_BUCKETS = 4
AUDIO_REACTION_ONSET_CONTEXT_BUCKETS = 5
AUDIO_REACTION_SUSTAIN_CONTEXT_BUCKETS = 5
AUDIO_REACTION_CLUSTER_CONTEXT_BUCKETS = 4
AUDIO_REACTION_CLUSTER_MIN_PEAK = 0.56
AUDIO_REACTION_CLUSTER_SPIKE_MARGIN = 0.16
AUDIO_REACTION_WINDOW_LEAD_SECONDS = 3.4
AUDIO_REACTION_WINDOW_FOLLOW_SECONDS = 1.7
AUDIO_REACTION_HIGH_SALIENCE_WINDOW_LEAD_SECONDS = 5.2
AUDIO_REACTION_HIGH_SALIENCE_WINDOW_FOLLOW_SECONDS = 2.4
AUDIO_REACTION_VISUAL_EVENT_LOOKBACK_SECONDS = 4.25
AUDIO_REACTION_HIGH_SALIENCE_VISUAL_EVENT_LOOKBACK_SECONDS = 6.75
AUDIO_REACTION_VISUAL_EVENT_POST_POP_SECONDS = 0.9
HIGH_SALIENCE_AUDIO_REACTION_MIN_SCORE = 0.62
HIGH_SALIENCE_AUDIO_REACTION_MIN_CONFIDENCE = 0.74
UNLABELED_AUDIO_REACTION_MIN_AUDIO_SCORE = 0.92
UNLABELED_AUDIO_REACTION_MIN_ACTIVITY_SCORE = 0.58
UNLABELED_AUDIO_REACTION_MIN_COMBINED_SCORE = 0.50
SUPER_LOUD_AUDIO_REACTION_MIN_AUDIO_SCORE = 0.97
SUPER_LOUD_AUDIO_REACTION_MIN_ACTIVITY_SCORE = 0.46
SUPER_LOUD_AUDIO_REACTION_MIN_COMBINED_SCORE = 0.48
RECOGNIZED_AUDIO_REACTION_MIN_AUDIO_SCORE = 0.72
RECOGNIZED_AUDIO_REACTION_MIN_CUE_CONFIDENCE = 0.55
ANALYSIS_REVIEW_SECONDS_PER_CLIP = 30.0
ANALYSIS_REVIEW_MIN_CLIPS = 8
ANALYSIS_REVIEW_MAX_CLIPS = 96
ANALYSIS_REVIEW_SOURCE_CAP_TRIGGER = 320
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


@dataclass(frozen=True)
class AudioPopSignal:
    score: float
    time_seconds: Optional[float]
    baseline: float
    cue_type: str = "none"
    confidence: float = 0.0


def run_analysis(job: StoredJob, settings: Settings, source_path: Path) -> CloudAnalysisResult:
    started_at = perf_counter()
    if not source_path.exists():
        raise PipelineError("upload_missing", "The uploaded video could not be found.")

    if job.file_size_bytes > settings.max_file_size_bytes:
        raise PipelineError("file_too_large", "Videos larger than 2 GB are not supported in cloud analysis v1.")

    duration_seconds = _probe_duration(source_path, fallback=job.duration_seconds)
    if duration_seconds > settings.max_duration_seconds:
        raise PipelineError("unsupported_duration", "Videos longer than 75 minutes are not supported in cloud analysis right now.")

    provider_tags: list[str] = []
    pipeline_summary: DetectionPipelineSummary | None = None
    candidate_pool_limit = _analysis_candidate_pool_limit(settings, job.team_selection)
    expanded_settings = _settings_with_candidate_limit(settings, candidate_pool_limit)

    external_clips, detection_provider = detect_with_optional_external_provider(
        source_path=source_path,
        duration_seconds=duration_seconds,
        settings=expanded_settings,
    )

    if detection_provider and settings.detection_provider == "hoopcut":
        provider_tags.append(detection_provider)
        external_pipeline = annotate_external_clips(
            external_clips[:candidate_pool_limit],
            source=detection_provider,
            model_version=f"{settings.backend_model_version}+{detection_provider}",
        )
        clips = external_pipeline.clips
        pipeline_summary = external_pipeline.summary
        candidate_segments = len(external_clips)
    else:
        native_clips, native_candidate_segments, native_pipeline_summary = _normalize_native_detection_result(
            _run_native_candidate_detection(
                source_path,
                duration_seconds,
                settings,
                clip_limit=candidate_pool_limit,
            ),
            settings=expanded_settings,
        )
        if detection_provider:
            provider_tags.append(detection_provider)
            external_pipeline = annotate_external_clips(
                external_clips,
                source=detection_provider,
                model_version=f"{settings.backend_model_version}+{detection_provider}",
            )
            clips = _merge_hybrid_detection_clips(
                external_clips=external_pipeline.clips,
                native_clips=native_clips,
                clip_limit=candidate_pool_limit,
                duration_seconds=duration_seconds,
                settings=settings,
            )
            candidate_segments = len(external_clips) + native_candidate_segments
            pipeline_summary = pipeline_summary_for_clips(
                clips,
                taxonomy_version=native_pipeline_summary.taxonomyVersion,
                model_version=f"{settings.backend_model_version}+hybrid",
            )
        else:
            clips = native_clips
            candidate_segments = native_candidate_segments
            pipeline_summary = native_pipeline_summary

    clips = _normalize_analysis_clips(clips, duration_seconds, settings, clip_limit=candidate_pool_limit)
    clips = [with_merge_provenance(clip, rank=index + 1) for index, clip in enumerate(clips)]

    clips, ranking_provider = rerank_with_optional_external_provider(
        clips=clips,
        source_path=source_path,
        settings=settings,
    )
    if ranking_provider:
        provider_tags.append(ranking_provider)

    clips, used_gemini = maybe_relabel_with_gemini(clips, settings.use_gemini_relabeling)
    clips, detected_teams, team_quick_scan_report = apply_team_quick_scan_with_report(
        source_path,
        duration_seconds,
        clips,
        settings,
    )
    used_team_quick_scan = team_quick_scan_report.used
    if used_team_quick_scan:
        provider_tags.append("team-scan")
    if not detected_teams:
        detected_teams = _detected_teams_from_clips(clips)
    pre_team_filter_clips = list(clips)
    clips = _filter_analysis_clips_for_team_selection(clips, job.team_selection)
    clips = _trim_analysis_clips_for_review(clips, job.team_selection, settings.max_returned_clips)
    clips = [with_merge_provenance(clip, rank=index + 1) for index, clip in enumerate(clips)]
    clips = _annotate_analysis_team_status(clips, job.team_selection)
    team_diagnostics = _analysis_team_diagnostic_counts(
        candidate_clips=pre_team_filter_clips,
        review_clips=clips,
        team_selection=job.team_selection,
        used_team_quick_scan=used_team_quick_scan,
        team_quick_scan_report=team_quick_scan_report,
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
        proposalSegments=pipeline_summary.proposalCount if pipeline_summary is not None else candidate_segments,
        embeddedSegments=pipeline_summary.rerankedCount if pipeline_summary is not None else 0,
        classifiedSegments=pipeline_summary.classifiedCount if pipeline_summary is not None else len(clips),
        mergedCandidateSegments=len(clips),
        usedSemanticRerank=bool(pipeline_summary and pipeline_summary.rerankedCount > 0),
        taxonomyVersion=pipeline_summary.taxonomyVersion if pipeline_summary is not None else None,
        **team_diagnostics,
    )

    if pipeline_summary is not None:
        pipeline_summary = pipeline_summary.model_copy(
            update={
                "mergedCandidateCount": len(clips),
                "classifiedCount": max(pipeline_summary.classifiedCount, len(clips)),
            }
        )

    return CloudAnalysisResult(
        clipCount=len(clips),
        clips=clips,
        diagnostics=diagnostics,
        resultConfidence=_analysis_result_confidence(clips),
        candidateClips=clips,
        pipeline=pipeline_summary,
        detectedTeams=detected_teams,
        teamSelection=job.team_selection,
    )


def _analysis_team_diagnostic_counts(
    *,
    candidate_clips: Sequence[CloudClip],
    review_clips: Sequence[CloudClip],
    team_selection: Optional[TeamSelection],
    used_team_quick_scan: bool,
    team_quick_scan_report: Optional[TeamQuickScanReport] = None,
) -> dict[str, int | bool]:
    candidate_statuses = [_analysis_team_status(clip, team_selection) for clip in candidate_clips]
    review_statuses = [_analysis_team_status(clip, team_selection) for clip in review_clips]
    scan_report = team_quick_scan_report or TeamQuickScanReport(used=used_team_quick_scan)
    return {
        "usedTeamQuickScan": bool(used_team_quick_scan),
        "preTeamFilterSegments": len(candidate_clips),
        "teamMatchedCandidateSegments": sum(1 for status in candidate_statuses if status == "matched"),
        "teamUncertainCandidateSegments": sum(1 for status in candidate_statuses if status == "uncertain"),
        "teamOpponentFilteredSegments": sum(1 for status in candidate_statuses if status == "opponent"),
        "teamMatchedReviewSegments": sum(1 for status in review_statuses if status == "matched"),
        "teamUncertainReviewSegments": sum(1 for status in review_statuses if status == "uncertain"),
        "teamScanRequestedCandidates": scan_report.requested_candidates,
        "teamScanReturnedAttributions": scan_report.returned_attributions,
        "teamScanExplicitUnknownAttributions": scan_report.explicit_unknown_attributions,
        "teamScanMissingAttributions": scan_report.missing_attributions,
        "teamScanCompletedBatches": scan_report.completed_batches,
        "teamScanFailedBatches": scan_report.failed_batches,
        "teamScanBudgetExhausted": scan_report.budget_exhausted,
        "defensiveReviewSegments": sum(1 for clip in review_clips if _is_defensive_label(clip.label)),
        "blockReviewSegments": sum(1 for clip in review_clips if _defensive_label_family(clip.label) == "block"),
        "stealReviewSegments": sum(1 for clip in review_clips if _defensive_label_family(clip.label) == "steal"),
        "forcedTurnoverReviewSegments": sum(1 for clip in review_clips if _defensive_label_family(clip.label) == "forced_turnover"),
        "defensiveStopReviewSegments": sum(1 for clip in review_clips if _defensive_label_family(clip.label) == "defensive_stop"),
        "audioReactionReviewSegments": sum(1 for clip in review_clips if _is_audio_reaction_candidate(clip)),
    }


def _analysis_result_confidence(clips: Sequence[CloudClip]) -> float:
    if not clips:
        return 0.0
    return round(sum(clamp(clip.confidence, 0.0, 1.0) for clip in clips) / len(clips), 4)


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
        clips, _, _ = _normalize_native_detection_result(
            _run_native_candidate_detection(
                source_path,
                probed_duration,
                settings,
                clip_limit=candidate_limit,
            ),
            settings=settings,
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


def _normalize_native_detection_result(result, *, settings: Settings) -> tuple[list[CloudClip], int, DetectionPipelineSummary]:
    if isinstance(result, tuple) and len(result) == 3:
        clips, candidate_segments, summary = result
        return list(clips), int(candidate_segments), summary
    if isinstance(result, tuple) and len(result) == 2:
        clips, candidate_segments = result
        clip_list = list(clips)
        summary = pipeline_summary_for_clips(
            clip_list,
            taxonomy_version="legacy-native",
            model_version=getattr(settings, "backend_model_version", "native"),
            fallback_reason="legacy_native_detection_result",
        )
        return clip_list, int(candidate_segments), summary
    raise ValueError("native detection must return clips/candidate count with optional pipeline summary")


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


def _audio_reaction_review_reserve_limit(max_clips: int, audio_reaction_count: int) -> int:
    max_clips = max(0, int(max_clips))
    audio_reaction_count = max(0, int(audio_reaction_count))
    if max_clips < 4 or audio_reaction_count == 0:
        return 0
    if max_clips < 8:
        return min(audio_reaction_count, 1)
    if max_clips >= 160:
        return min(audio_reaction_count, 16)
    if max_clips >= 80:
        return min(audio_reaction_count, 10)
    if max_clips >= 40:
        return min(audio_reaction_count, 6)
    if max_clips >= 20:
        return min(audio_reaction_count, 4)
    return min(audio_reaction_count, 2)


def _trim_analysis_clips_for_review(
    clips: Sequence[CloudClip],
    team_selection: Optional[TeamSelection],
    max_clips: int,
) -> list[CloudClip]:
    max_clips = _review_clip_limit_for_source(clips, max_clips)
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

    audio_reactions = [
        (index, clip)
        for index, clip in indexed_clips
        if _is_audio_reaction_candidate(clip)
    ]
    audio_reaction_reserve = _audio_reaction_review_reserve_limit(max_clips, len(audio_reactions))
    for index, clip in sorted(audio_reactions, key=_audio_reaction_reserved_clip_quality_key, reverse=True)[
        :audio_reaction_reserve
    ]:
        add_clip(index, clip)

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

    for index, clip in sorted(indexed_clips, key=_review_fill_clip_quality_key, reverse=True):
        add_clip(index, clip)
        if len(selected) >= max_clips:
            break

    return [clip for _, clip in sorted(selected, key=lambda item: item[0])]


def _review_clip_limit_for_source(clips: Sequence[CloudClip], max_clips: int) -> int:
    requested_limit = max(0, int(max_clips))
    if requested_limit == 0 or not clips:
        return 0
    if requested_limit < ANALYSIS_REVIEW_SOURCE_CAP_TRIGGER:
        return min(requested_limit, len(clips))

    source_span_seconds = max((max(clip.endTime, clip.startTime) for clip in clips), default=0.0)
    duration_scaled_limit = int(math.ceil(source_span_seconds / ANALYSIS_REVIEW_SECONDS_PER_CLIP))
    effective_limit = max(ANALYSIS_REVIEW_MIN_CLIPS, duration_scaled_limit)
    effective_limit = min(effective_limit, ANALYSIS_REVIEW_MAX_CLIPS)
    return min(requested_limit, effective_limit, len(clips))


def _review_reserved_clip_quality_key(
    item: tuple[int, CloudClip],
) -> tuple[float, float, float, float, float, float, float, int]:
    index, clip = item
    return (*_hybrid_clip_quality_key(clip), -index)


def _review_fill_clip_quality_key(
    item: tuple[int, CloudClip],
) -> tuple[float, float, float, float, float, float, float, float, int]:
    index, clip = item
    auto_keep_allowed = _analysis_clip_auto_keep_allowed(clip)
    defensive_label = _is_defensive_label(clip.label)
    return (
        1.0 if auto_keep_allowed else 0.0,
        1.0 if _is_shot_like_label(clip.label) and not defensive_label else 0.0,
        1.0 if defensive_label else 0.0,
        _analysis_clip_context_score(clip),
        0.0 if _is_audio_reaction_candidate(clip) else 1.0,
        clip.combinedScore,
        clip.confidence,
        clip.motionScore,
        -index,
    )


def _audio_reaction_reserved_clip_quality_key(
    item: tuple[int, CloudClip],
) -> tuple[float, float, float, float, float, float, int]:
    index, clip = item
    cue_confidence = clip.audioCueConfidence or 0.0
    return (
        _audio_reaction_review_salience_score(clip),
        clip.audioScore,
        cue_confidence,
        clip.combinedScore,
        clip.motionScore,
        clip.confidence,
        -index,
    )


def _audio_reaction_review_salience_score(clip: CloudClip) -> float:
    cue_confidence = clip.audioCueConfidence or 0.0
    cue_bonus = {
        "super_loud_cluster": 0.12,
        "cluster": 0.08,
        "swell": 0.06,
        "spike": 0.04,
    }.get(clip.audioCueType or "none", 0.0)
    activity_score = max(clip.motionScore, clip.visualScore, clip.confidence)
    score = (
        (clip.audioScore * 0.64)
        + (clip.combinedScore * 0.12)
        + (activity_score * 0.12)
        + (cue_confidence * 0.08)
        + cue_bonus
    )
    return round(clamp(score, 0.0, 1.0), 4)


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
) -> tuple[list[CloudClip], int, DetectionPipelineSummary]:
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

    windows = [replace(window, source_path=source_path) for window in windows]
    resolved_limit = clip_limit or settings.max_returned_clips
    result = run_staged_detection_pipeline(windows, clip_limit=resolved_limit)
    return result.clips, len(windows), result.summary


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
    merged = _merge_near_duplicate_analysis_clips(normalized, duration_seconds=duration_seconds, settings=settings)
    return merged[: (clip_limit or settings.max_returned_clips)]


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
    duration_seconds: float,
    settings: Settings,
) -> list[CloudClip]:
    ranked = sorted([*external_clips, *native_clips], key=_hybrid_clip_quality_key, reverse=True)
    kept: list[CloudClip] = []
    for clip in ranked:
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(kept)
                if _clips_describe_same_highlight_timeframe(clip, existing)
            ),
            None,
        )
        if duplicate_index is None:
            kept.append(clip)
            continue
        kept[duplicate_index] = _merge_duplicate_cloud_clips(
            kept[duplicate_index],
            clip,
            duration_seconds=duration_seconds,
            settings=settings,
        )

    kept.sort(key=_hybrid_clip_quality_key, reverse=True)
    return kept[:clip_limit]


def _merge_near_duplicate_analysis_clips(
    clips: Sequence[CloudClip],
    *,
    duration_seconds: float,
    settings: Settings,
) -> list[CloudClip]:
    kept: list[CloudClip] = []
    for clip in clips:
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(kept)
                if _clips_describe_same_highlight_timeframe(clip, existing)
            ),
            None,
        )
        if duplicate_index is None:
            kept.append(clip)
            continue
        kept[duplicate_index] = _merge_duplicate_cloud_clips(
            kept[duplicate_index],
            clip,
            duration_seconds=duration_seconds,
            settings=settings,
        )
    return kept


def _clips_describe_same_highlight_timeframe(left: CloudClip, right: CloudClip) -> bool:
    overlap_ratio = _clip_overlap_ratio(left, right)
    if overlap_ratio > HYBRID_OVERLAP_DEDUPE_RATIO:
        return True
    left_center = _clip_merge_center(left)
    right_center = _clip_merge_center(right)
    center_gap = abs(left_center - right_center)
    return center_gap <= TEMPORAL_DEDUPE_CENTER_GAP_SECONDS and overlap_ratio >= TEMPORAL_DEDUPE_MIN_OVERLAP_RATIO


def _merge_duplicate_cloud_clips(
    left: CloudClip,
    right: CloudClip,
    *,
    duration_seconds: float,
    settings: Settings,
) -> CloudClip:
    best = max((left, right), key=_hybrid_clip_quality_key)
    audio_clip = max((left, right), key=lambda clip: ((clip.audioCueConfidence or 0.0), clip.audioScore, clip.combinedScore))
    team_clip = max((left, right), key=_clip_team_attribution_quality)
    start_time, end_time, event_center = _merged_duplicate_clip_window(left, right, duration_seconds=duration_seconds, settings=settings)
    merged = best.model_copy(
        update={
            "startTime": start_time,
            "endTime": end_time,
            "eventCenter": event_center,
            "confidence": _merged_duplicate_score(left.confidence, right.confidence),
            "audioScore": _merged_duplicate_score(left.audioScore, right.audioScore),
            "visualScore": _merged_duplicate_score(left.visualScore, right.visualScore),
            "motionScore": _merged_duplicate_score(left.motionScore, right.motionScore),
            "combinedScore": _merged_duplicate_score(left.combinedScore, right.combinedScore),
            "audioCueType": audio_clip.audioCueType,
            "audioCueConfidence": audio_clip.audioCueConfidence,
            "audioCueTime": audio_clip.audioCueTime,
            "teamAttribution": team_clip.teamAttribution,
            "teamAttributionStatus": team_clip.teamAttributionStatus,
            "shouldAutoKeep": left.shouldAutoKeep or right.shouldAutoKeep,
            "shouldEnableSlowMotion": left.shouldEnableSlowMotion or right.shouldEnableSlowMotion,
        }
    )
    auto_keep_allowed = _analysis_clip_auto_keep_allowed(merged)
    return merged.model_copy(
        update={
            "shouldAutoKeep": merged.shouldAutoKeep and auto_keep_allowed,
            "shouldEnableSlowMotion": merged.shouldEnableSlowMotion and auto_keep_allowed,
            "nativeShotSignals": _native_shot_signals_for_analysis_clip(merged),
        }
    )


def _merged_duplicate_clip_window(
    left: CloudClip,
    right: CloudClip,
    *,
    duration_seconds: float,
    settings: Settings,
) -> tuple[float, float, float]:
    duration_seconds = max(0.0, duration_seconds)
    start_time = clamp(min(left.startTime, right.startTime), 0.0, duration_seconds)
    end_time = clamp(max(left.endTime, right.endTime), 0.0, duration_seconds)
    event_center = clamp(_weighted_clip_merge_center(left, right), 0.0, duration_seconds)
    max_duration = min(settings.max_clip_duration_seconds, duration_seconds) if duration_seconds > 0 else settings.max_clip_duration_seconds
    min_duration = min(settings.min_clip_duration_seconds, duration_seconds) if duration_seconds > 0 else settings.min_clip_duration_seconds

    if max_duration > 0 and end_time - start_time > max_duration:
        start_time = max(0.0, event_center - (max_duration / 2.0))
        end_time = min(duration_seconds, start_time + max_duration)
        if end_time - start_time < max_duration:
            start_time = max(0.0, end_time - max_duration)

    if min_duration > 0 and end_time - start_time < min_duration:
        missing = min_duration - (end_time - start_time)
        start_time = max(0.0, start_time - (missing / 2.0))
        end_time = min(duration_seconds, end_time + (missing / 2.0))
        if end_time - start_time < min_duration:
            start_time = max(0.0, min(start_time, duration_seconds - min_duration))
            end_time = min(duration_seconds, start_time + min_duration)

    event_center = clamp(event_center, start_time, end_time)
    return round(start_time, 3), round(end_time, 3), round(event_center, 3)


def _merged_duplicate_score(left_score: float, right_score: float) -> float:
    stronger = max(left_score, right_score)
    weaker = min(left_score, right_score)
    return round(clamp(stronger + (weaker * TEMPORAL_DEDUPE_SCORE_BOOST_WEIGHT), 0.0, 1.0), 4)


def _weighted_clip_merge_center(left: CloudClip, right: CloudClip) -> float:
    if left.eventCenter is not None and right.eventCenter is None:
        return left.eventCenter
    if right.eventCenter is not None and left.eventCenter is None:
        return right.eventCenter
    left_weight = max(left.combinedScore, 0.001)
    right_weight = max(right.combinedScore, 0.001)
    return ((left_weight * _clip_merge_center(left)) + (right_weight * _clip_merge_center(right))) / (left_weight + right_weight)


def _clip_merge_center(clip: CloudClip) -> float:
    if clip.eventCenter is not None:
        return clip.eventCenter
    return (clip.startTime + clip.endTime) / 2.0


def _clip_team_attribution_quality(clip: CloudClip) -> float:
    status_score = {
        "matched": 0.35,
        "all": 0.2,
        "uncertain": 0.05,
        "opponent": -0.4,
        None: 0.0,
    }.get(clip.teamAttributionStatus, 0.0)
    attribution_confidence = clip.teamAttribution.confidence if clip.teamAttribution is not None else 0.0
    return status_score + attribution_confidence


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
        "contested",
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
    if tokens & {"block", "blocked", "swat", "swatted", "rejection", "rejected"}:
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
    if (
        "stop" in tokens
        and ("defensive stop" in normalized or "defense stop" in normalized or normalized == "stop")
    ) or tokens & {"contest", "contested"}:
        return "defensive_stop"
    if tokens & {
        "defense",
        "defensive",
        "pressure",
        "lockdown",
    }:
        return "defensive"
    return None


def _is_audio_reaction_label(label: str) -> bool:
    normalized = label.strip().lower()
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    return normalized in {
        "audio pop",
        "audio reaction",
        "bench reaction",
        "crowd pop",
        "crowd roar",
        "crowd reaction",
        "loud cheer",
    } or (
        "crowd" in tokens and tokens & {"reaction", "pop", "roar", "cheer"}
    ) or (
        "bench" in tokens and "reaction" in tokens
    )


def _is_audio_reaction_context_label(label: str) -> bool:
    normalized = label.strip().lower()
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    if not normalized:
        return False
    if normalized in {"highlight", "clip", "play", "moment"} or normalized.endswith(" highlight"):
        return True
    if "shot attempt" in normalized or "scoring chance" in normalized or "basketball action" in normalized:
        return True
    return bool(
        tokens
        & {
            "basket",
            "bucket",
            "drive",
            "dunk",
            "finish",
            "jumper",
            "layup",
            "make",
            "made",
            "score",
            "scoring",
            "shot",
            "three",
            "transition",
        }
    )


def _is_audio_reaction_candidate(clip: CloudClip) -> bool:
    if _is_audio_reaction_label(clip.label):
        return True
    if not _is_audio_reaction_context_label(clip.label):
        return False
    activity_score = max(clip.motionScore, clip.visualScore, clip.confidence)
    recognized_cue = (
        clip.audioCueType in {"spike", "cluster", "super_loud_cluster", "swell"}
        and (clip.audioCueConfidence or 0.0) >= RECOGNIZED_AUDIO_REACTION_MIN_CUE_CONFIDENCE
        and clip.audioScore >= RECOGNIZED_AUDIO_REACTION_MIN_AUDIO_SCORE
    )
    if recognized_cue:
        return (
            activity_score >= UNLABELED_AUDIO_REACTION_MIN_ACTIVITY_SCORE
            and clip.combinedScore >= UNLABELED_AUDIO_REACTION_MIN_COMBINED_SCORE
        )
    if clip.audioScore >= SUPER_LOUD_AUDIO_REACTION_MIN_AUDIO_SCORE:
        return (
            activity_score >= SUPER_LOUD_AUDIO_REACTION_MIN_ACTIVITY_SCORE
            and clip.combinedScore >= SUPER_LOUD_AUDIO_REACTION_MIN_COMBINED_SCORE
        )
    return (
        clip.audioScore >= UNLABELED_AUDIO_REACTION_MIN_AUDIO_SCORE
        and activity_score >= UNLABELED_AUDIO_REACTION_MIN_ACTIVITY_SCORE
        and clip.combinedScore >= UNLABELED_AUDIO_REACTION_MIN_COMBINED_SCORE
    )


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
    center = max(int(time_seconds / AUDIO_PROFILE_BUCKET_SECONDS), 0)
    start = max(center - 1, 0)
    end = min(center + 2, len(audio_profile))
    return clamp(max(audio_profile[start:end] or [0.0]), 0.0, 1.0)


def _audio_pop_signal_for_window(
    audio_profile: Sequence[float],
    bucket_start: int,
    bucket_end: int,
) -> AudioPopSignal:
    if not audio_profile or bucket_start >= len(audio_profile):
        return AudioPopSignal(score=0.0, time_seconds=None, baseline=0.0)

    bounded_start = max(bucket_start, 0)
    bounded_end = min(max(bucket_end, bounded_start + 1), len(audio_profile))
    window_values = list(audio_profile[bounded_start:bounded_end])
    if not window_values:
        return AudioPopSignal(score=0.0, time_seconds=None, baseline=0.0)

    peak_offset, peak_value = max(enumerate(window_values), key=lambda item: item[1])
    peak_index = bounded_start + peak_offset
    local_start = max(0, peak_index - 6)
    local_end = min(len(audio_profile), peak_index + 7)
    surrounding_values = [
        value
        for index, value in enumerate(audio_profile[local_start:local_end], start=local_start)
        if abs(index - peak_index) > 1
    ]
    baseline = mean(surrounding_values or window_values)
    window_mean = mean(window_values)
    onset_values = audio_profile[
        max(0, peak_index - AUDIO_REACTION_ONSET_CONTEXT_BUCKETS - 1) : max(0, peak_index - 1)
    ]
    onset_baseline = mean(onset_values or surrounding_values or window_values)
    sustain_values = audio_profile[
        peak_index + 1 : min(len(audio_profile), peak_index + AUDIO_REACTION_SUSTAIN_CONTEXT_BUCKETS + 1)
    ]
    sustain_mean = mean(sustain_values or [0.0])
    sustain_above_baseline = max(sustain_mean - baseline, 0.0)
    cluster_boost, cluster_count, cluster_mean = _audio_reaction_cluster_boost(audio_profile, peak_index, peak_value, baseline)
    loudness_gate = clamp((peak_value - 0.48) / 0.28, 0.0, 1.0)
    rise_above_window = max(peak_value - window_mean, 0.0)
    rise_above_baseline = max(peak_value - baseline, 0.0)
    rise_from_onset = max(peak_value - onset_baseline, 0.0)
    score = clamp(
        (
            (rise_above_window * 0.72)
            + (rise_above_baseline * 0.48)
            + (rise_from_onset * 0.58)
            + (sustain_above_baseline * 0.22)
            + (max(peak_value - 0.70, 0.0) * 0.2)
            + cluster_boost
        )
        * loudness_gate,
        0.0,
        1.0,
    )
    cue_type = _classify_audio_reaction_cue(
        peak_value=peak_value,
        baseline=baseline,
        rise_above_baseline=rise_above_baseline,
        rise_from_onset=rise_from_onset,
        sustain_above_baseline=sustain_above_baseline,
        cluster_count=cluster_count,
        cluster_mean=cluster_mean,
    )
    cue_confidence = _audio_reaction_cue_confidence(
        cue_type=cue_type,
        score=score,
        peak_value=peak_value,
        rise_above_baseline=rise_above_baseline,
        sustain_above_baseline=sustain_above_baseline,
        cluster_boost=cluster_boost,
    )
    time_seconds = (peak_index + 0.5) * AUDIO_PROFILE_BUCKET_SECONDS
    return AudioPopSignal(
        score=round(score, 4),
        time_seconds=round(time_seconds, 3),
        baseline=round(baseline, 4),
        cue_type=cue_type,
        confidence=round(cue_confidence, 4),
    )


def _audio_reaction_cluster_boost(
    audio_profile: Sequence[float],
    peak_index: int,
    peak_value: float,
    baseline: float,
) -> tuple[float, int, float]:
    if peak_value < AUDIO_REACTION_CLUSTER_MIN_PEAK:
        return 0.0, 0, 0.0

    cluster_start = max(0, peak_index - AUDIO_REACTION_CLUSTER_CONTEXT_BUCKETS)
    cluster_end = min(len(audio_profile), peak_index + AUDIO_REACTION_CLUSTER_CONTEXT_BUCKETS + 1)
    elevated_floor = max(0.50, baseline + AUDIO_REACTION_CLUSTER_SPIKE_MARGIN)
    elevated_values = [value for value in audio_profile[cluster_start:cluster_end] if value >= elevated_floor]
    if len(elevated_values) < 2:
        return 0.0, len(elevated_values), mean(elevated_values or [0.0])

    density_score = min((len(elevated_values) - 1) / 3.0, 1.0)
    elevation_score = clamp((mean(elevated_values) - baseline) / 0.42, 0.0, 1.0)
    return clamp((density_score * 0.20) + (elevation_score * 0.16), 0.0, 0.36), len(elevated_values), mean(elevated_values)


def _classify_audio_reaction_cue(
    *,
    peak_value: float,
    baseline: float,
    rise_above_baseline: float,
    rise_from_onset: float,
    sustain_above_baseline: float,
    cluster_count: int,
    cluster_mean: float,
) -> str:
    if peak_value < 0.50:
        return "none"
    if rise_above_baseline < 0.10 and rise_from_onset < 0.10:
        return "steady_noise"
    if (
        peak_value >= 0.94
        and cluster_count >= 3
        and cluster_mean >= max(0.62, baseline + 0.24)
    ):
        return "super_loud_cluster"
    if cluster_count >= 3 and cluster_mean >= max(0.54, baseline + 0.18):
        return "cluster"
    if sustain_above_baseline >= 0.12 and peak_value >= max(0.62, baseline + 0.20):
        return "swell"
    return "spike"


def _audio_reaction_cue_confidence(
    *,
    cue_type: str,
    score: float,
    peak_value: float,
    rise_above_baseline: float,
    sustain_above_baseline: float,
    cluster_boost: float,
) -> float:
    if cue_type in {"none", "steady_noise"}:
        return 0.0
    pattern_bonus = {
        "spike": 0.04,
        "swell": 0.08,
        "cluster": 0.12,
        "super_loud_cluster": 0.18,
    }.get(cue_type, 0.0)
    return clamp(
        (score * 0.58)
        + (peak_value * 0.18)
        + (rise_above_baseline * 0.12)
        + (sustain_above_baseline * 0.08)
        + (cluster_boost * 0.12)
        + pattern_bonus,
        0.0,
        1.0,
    )


def _audio_pop_context_score(pop_time_seconds: Optional[float], start_time: float, end_time: float) -> float:
    if pop_time_seconds is None:
        return 0.0
    lead_in = max(pop_time_seconds - start_time, 0.0)
    follow = max(end_time - pop_time_seconds, 0.0)
    lead_score = min(lead_in / 1.6, 1.0)
    follow_score = min(follow / 1.3, 1.0)
    return clamp((lead_score * 0.75) + (follow_score * 0.25), 0.0, 1.0)


def _detect_audio_reaction_boundaries(audio_profile: Sequence[float]) -> List[AudioPopSignal]:
    if not audio_profile:
        return []

    candidates: List[AudioPopSignal] = []
    for index, value in enumerate(audio_profile):
        before = audio_profile[max(0, index - AUDIO_REACTION_BOUNDARY_CONTEXT_BUCKETS) : index]
        after = audio_profile[index + 1 : min(len(audio_profile), index + AUDIO_REACTION_BOUNDARY_CONTEXT_BUCKETS + 1)]
        if before and value < max(before):
            continue
        if after and value < max(after):
            continue

        signal = _audio_pop_signal_for_window(
            audio_profile,
            max(0, index - AUDIO_REACTION_BOUNDARY_CONTEXT_BUCKETS),
            min(len(audio_profile), index + AUDIO_REACTION_BOUNDARY_CONTEXT_BUCKETS + 1),
        )
        if signal.time_seconds is None or signal.score < AUDIO_REACTION_BOUNDARY_MIN_SCORE:
            continue
        candidates.append(signal)

    candidates.sort(key=lambda item: item.score, reverse=True)
    selected: List[AudioPopSignal] = []
    min_gap = AUDIO_REACTION_BOUNDARY_MIN_GAP_SECONDS
    for signal in candidates:
        if signal.time_seconds is None:
            continue
        if any(existing.time_seconds is not None and abs(signal.time_seconds - existing.time_seconds) < min_gap for existing in selected):
            continue
        selected.append(signal)
        if len(selected) >= AUDIO_REACTION_BOUNDARY_MAX_COUNT:
            break

    return sorted(selected, key=lambda item: item.time_seconds or 0.0)


def _visual_event_anchor_before_audio_reaction(
    pop_time_seconds: float,
    shot_boundaries: Sequence[float],
    lookback_seconds: float = AUDIO_REACTION_VISUAL_EVENT_LOOKBACK_SECONDS,
) -> Optional[float]:
    candidates = [
        boundary
        for boundary in shot_boundaries
        if 0.0 <= pop_time_seconds - boundary <= lookback_seconds
    ]
    if not candidates:
        return None
    return max(candidates)


def _is_high_salience_audio_reaction_signal(signal: AudioPopSignal) -> bool:
    if signal.score >= HIGH_SALIENCE_AUDIO_REACTION_MIN_SCORE:
        return True
    if signal.confidence >= HIGH_SALIENCE_AUDIO_REACTION_MIN_CONFIDENCE:
        return True
    if signal.cue_type == "super_loud_cluster":
        return signal.confidence >= 0.62
    if signal.cue_type == "spike" and signal.score >= 0.56 and signal.confidence >= 0.68:
        return True
    return signal.cue_type in {"cluster", "swell"} and signal.confidence >= 0.68


def _extract_audio_profile(path: Path, duration_seconds: float) -> List[float]:
    bucket_count = max(int(math.ceil(duration_seconds / AUDIO_PROFILE_BUCKET_SECONDS)), 1)
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

    samples_per_bucket = max(int(sample_rate * AUDIO_PROFILE_BUCKET_SECONDS), 1)
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

        bucket_start = max(int(time_cursor / AUDIO_PROFILE_BUCKET_SECONDS), 0)
        bucket_end = max(int(math.ceil(end_time / AUDIO_PROFILE_BUCKET_SECONDS)), bucket_start + 1)
        slice_values = audio_profile[bucket_start:bucket_end] or [0.0]

        audio_score = max(slice_values)
        audio_mean = mean(slice_values)
        volatility = max(audio_score - audio_mean, 0.0)
        audio_pop_signal = _audio_pop_signal_for_window(audio_profile, bucket_start, bucket_end)
        audio_context_score = _audio_pop_context_score(audio_pop_signal.time_seconds, time_cursor, end_time)
        audio_pop_score = round(audio_pop_signal.score * audio_context_score, 4)
        audio_cue_confidence = round(audio_pop_signal.confidence * audio_context_score, 4)
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
            (audio_score * 0.58)
            + (volatility * 0.92)
            + (audio_pop_score * 0.18)
            + (center_transition_boost * 0.75)
            + (context_boost * 0.55),
            0.0,
            1.0,
        )
        visual_score = clamp(
            (audio_mean * 0.45) + (max(center_bias, 0.0) * 0.25) + center_transition_boost + context_boost,
            0.0,
            1.0,
        )
        baseline_score = clamp(
            (audio_score * 0.36) + (motion_score * 0.32) + (visual_score * 0.22) + (audio_pop_score * 0.1),
            0.0,
            1.0,
        )
        combined_score = clamp(
            baseline_score + (shot_context_score * 0.16) + (audio_pop_score * 0.04),
            0.0,
            1.0,
        )
        if shot_event_time is not None and shot_context_score >= 0.45:
            peak_time = shot_event_time
        elif audio_pop_signal.time_seconds is not None and audio_pop_score >= AUDIO_POP_EVENT_CENTER_THRESHOLD:
            peak_time = min(max(audio_pop_signal.time_seconds, time_cursor), end_time)
        else:
            peak_time = center

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
                audio_pop_score=audio_pop_score,
                audio_pop_time=audio_pop_signal.time_seconds,
                audio_cue_type=audio_pop_signal.cue_type if audio_cue_confidence > 0.0 else None,
                audio_cue_confidence=audio_cue_confidence,
            )
        )

        time_cursor += stride

    windows.extend(
        _build_audio_reaction_candidate_windows(
            duration_seconds=duration_seconds,
            audio_profile=audio_profile,
            shot_boundaries=shot_boundaries,
            settings=settings,
        )
    )
    windows.sort(key=lambda item: item.start_time)

    segmented = _segment_with_hysteresis(windows, settings, clip_limit=resolved_limit)
    if segmented:
        return _backfill_segmented_candidate_windows(segmented, windows, resolved_limit)

    ranked = sorted(windows, key=lambda item: item.combined_score, reverse=True)[:resolved_limit]
    return _reserve_audio_reaction_candidate_windows(ranked, windows, resolved_limit)


def _build_audio_reaction_candidate_windows(
    *,
    duration_seconds: float,
    audio_profile: Sequence[float],
    shot_boundaries: List[float],
    settings: Settings,
) -> List[CandidateWindow]:
    reaction_windows: List[CandidateWindow] = []
    for signal in _detect_audio_reaction_boundaries(audio_profile):
        if signal.time_seconds is None:
            continue

        event_time = clamp(signal.time_seconds, 0.0, duration_seconds)
        high_salience_signal = _is_high_salience_audio_reaction_signal(signal)
        lookback_seconds = (
            AUDIO_REACTION_HIGH_SALIENCE_VISUAL_EVENT_LOOKBACK_SECONDS
            if high_salience_signal
            else AUDIO_REACTION_VISUAL_EVENT_LOOKBACK_SECONDS
        )
        lead_seconds = (
            AUDIO_REACTION_HIGH_SALIENCE_WINDOW_LEAD_SECONDS
            if high_salience_signal
            else AUDIO_REACTION_WINDOW_LEAD_SECONDS
        )
        follow_seconds = (
            AUDIO_REACTION_HIGH_SALIENCE_WINDOW_FOLLOW_SECONDS
            if high_salience_signal
            else AUDIO_REACTION_WINDOW_FOLLOW_SECONDS
        )
        visual_event_anchor = _visual_event_anchor_before_audio_reaction(
            event_time,
            shot_boundaries,
            lookback_seconds=lookback_seconds,
        )
        if visual_event_anchor is not None:
            visual_event_anchor = clamp(visual_event_anchor, 0.0, duration_seconds)
            start_time = max(0.0, visual_event_anchor - NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS)
            end_time = min(
                duration_seconds,
                max(
                    visual_event_anchor + NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS,
                    event_time + AUDIO_REACTION_VISUAL_EVENT_POST_POP_SECONDS,
                ),
            )
        else:
            start_time = max(0.0, event_time - lead_seconds)
            end_time = min(duration_seconds, event_time + follow_seconds)
        target_duration = min(
            settings.max_clip_duration_seconds,
            max(settings.min_clip_duration_seconds, lead_seconds + follow_seconds),
        )
        if end_time - start_time < target_duration:
            missing = target_duration - (end_time - start_time)
            start_time = max(0.0, start_time - (missing * 0.58))
            end_time = min(duration_seconds, end_time + (missing * 0.42))
            if end_time - start_time < target_duration:
                start_time = max(0.0, min(start_time, duration_seconds - target_duration))
                end_time = min(duration_seconds, start_time + target_duration)

        if end_time - start_time < settings.min_clip_duration_seconds:
            continue
        if end_time - start_time > settings.max_clip_duration_seconds:
            start_time = max(0.0, event_time - min(lead_seconds, settings.max_clip_duration_seconds * 0.68))
            end_time = min(duration_seconds, start_time + settings.max_clip_duration_seconds)
            if event_time > end_time:
                end_time = min(duration_seconds, event_time + follow_seconds)
                start_time = max(0.0, end_time - settings.max_clip_duration_seconds)

        bucket_start = max(int(start_time / AUDIO_PROFILE_BUCKET_SECONDS), 0)
        bucket_end = max(int(math.ceil(end_time / AUDIO_PROFILE_BUCKET_SECONDS)), bucket_start + 1)
        slice_values = list(audio_profile[bucket_start:bucket_end]) or [0.0]
        audio_score = clamp(max(slice_values), 0.0, 1.0)
        audio_mean = mean(slice_values)
        center = (start_time + end_time) / 2.0
        shot_context_score, shot_event_time = _shot_context_score_for_window(
            start_time=start_time,
            end_time=end_time,
            center_time=center,
            shot_boundaries=shot_boundaries,
        )
        event_anchor = shot_event_time if shot_event_time is not None and shot_context_score >= 0.45 else event_time
        visual_score = clamp((shot_context_score * 0.52) + (audio_mean * 0.16) + (signal.score * 0.10) + 0.12, 0.0, 0.62)
        motion_score = clamp((signal.score * 0.62) + (audio_score * 0.22) + (shot_context_score * 0.16), 0.0, 1.0)
        combined_score = clamp(0.48 + (signal.score * 0.25) + (audio_score * 0.08) + (shot_context_score * 0.17), 0.0, 0.92)

        reaction_windows.append(
            CandidateWindow(
                start_time=round(start_time, 3),
                end_time=round(end_time, 3),
                peak_time=round(clamp(event_anchor, start_time, end_time), 3),
                audio_score=round(audio_score, 4),
                visual_score=round(visual_score, 4),
                motion_score=round(motion_score, 4),
                combined_score=round(combined_score, 4),
                event_context_score=round(shot_context_score, 4),
                audio_pop_score=round(signal.score, 4),
                audio_pop_time=signal.time_seconds,
                audio_cue_type=signal.cue_type if signal.confidence > 0.0 else None,
                audio_cue_confidence=round(signal.confidence, 4),
            )
        )

    return reaction_windows


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
        return _reserve_audio_reaction_candidate_windows(kept, windows, resolved_limit)

    for window in sorted(windows, key=_candidate_window_recall_key, reverse=True):
        if len(kept) >= resolved_limit:
            break
        if any(_candidate_window_overlap_ratio(window, existing) > NATIVE_RECALL_BACKFILL_OVERLAP_RATIO for existing in kept):
            continue
        kept.append(window)

    return _reserve_audio_reaction_candidate_windows(kept, windows, resolved_limit)


def _audio_reaction_window_reserve_limit(max_windows: int, audio_reaction_count: int) -> int:
    max_windows = max(0, int(max_windows))
    audio_reaction_count = max(0, int(audio_reaction_count))
    if max_windows < 4 or audio_reaction_count == 0:
        return 0
    if max_windows >= 320:
        return min(audio_reaction_count, 32)
    if max_windows >= 160:
        return min(audio_reaction_count, 24)
    if max_windows >= 80:
        return min(audio_reaction_count, 16)
    if max_windows >= 40:
        return min(audio_reaction_count, 10)
    if max_windows >= 20:
        return min(audio_reaction_count, 6)
    if max_windows >= 8:
        return min(audio_reaction_count, 3)
    return min(audio_reaction_count, 1)


def _reserve_audio_reaction_candidate_windows(
    kept: Sequence[CandidateWindow],
    windows: Sequence[CandidateWindow],
    resolved_limit: int,
) -> List[CandidateWindow]:
    resolved_limit = max(0, int(resolved_limit))
    if resolved_limit == 0:
        return []

    selected = list(kept[:resolved_limit])
    audio_candidates = [window for window in windows if _is_audio_reaction_candidate_window(window)]
    reserve_limit = _audio_reaction_window_reserve_limit(resolved_limit, len(audio_candidates))
    if reserve_limit == 0:
        return sorted(selected, key=_candidate_window_recall_key, reverse=True)[:resolved_limit]

    selected_audio_count = sum(1 for window in selected if _is_audio_reaction_candidate_window(window))
    if selected_audio_count >= reserve_limit:
        return sorted(selected, key=_candidate_window_recall_key, reverse=True)[:resolved_limit]

    for candidate in sorted(audio_candidates, key=_audio_reaction_window_quality_key, reverse=True):
        if selected_audio_count >= reserve_limit:
            break

        duplicate_index = next(
            (
                index
                for index, existing in enumerate(selected)
                if _candidate_window_overlap_ratio(candidate, existing) > NATIVE_RECALL_BACKFILL_OVERLAP_RATIO
            ),
            None,
        )
        if duplicate_index is not None:
            existing = selected[duplicate_index]
            if _is_audio_reaction_candidate_window(existing):
                continue
            if _audio_reaction_window_quality_key(candidate) > _audio_reaction_window_quality_key(existing):
                selected[duplicate_index] = candidate
                selected_audio_count += 1
            continue

        if len(selected) < resolved_limit:
            selected.append(candidate)
            selected_audio_count += 1
            continue

        replacement_index = _audio_reaction_replacement_index(selected)
        if replacement_index is None:
            break
        selected[replacement_index] = candidate
        selected_audio_count += 1

    return sorted(selected, key=_candidate_window_recall_key, reverse=True)[:resolved_limit]


def _audio_reaction_replacement_index(windows: Sequence[CandidateWindow]) -> Optional[int]:
    replacement_candidates = [
        (index, window)
        for index, window in enumerate(windows)
        if not _is_audio_reaction_candidate_window(window)
    ]
    if not replacement_candidates:
        return None
    return min(replacement_candidates, key=lambda item: _candidate_window_recall_key(item[1]))[0]


def _is_audio_reaction_candidate_window(window: CandidateWindow) -> bool:
    if window.audio_pop_time is None:
        return False
    if window.audio_pop_score < AUDIO_REACTION_BOUNDARY_MIN_SCORE:
        return False
    recognized_cue = window.audio_cue_type in {"spike", "cluster", "super_loud_cluster", "swell"}
    super_loud = window.audio_score >= SUPER_LOUD_AUDIO_REACTION_MIN_AUDIO_SCORE
    return recognized_cue or super_loud


def _audio_reaction_window_quality_key(window: CandidateWindow) -> tuple[float, float, float, float, float, float, float, float]:
    cue_confidence = window.audio_cue_confidence or 0.0
    high_salience = 1.0 if _is_high_salience_audio_reaction_signal(
        AudioPopSignal(
            score=window.audio_pop_score,
            time_seconds=window.audio_pop_time,
            baseline=0.0,
            cue_type=window.audio_cue_type or "none",
            confidence=cue_confidence,
        )
    ) else 0.0
    cue_bonus = {
        "super_loud_cluster": 0.12,
        "cluster": 0.08,
        "swell": 0.06,
        "spike": 0.04,
    }.get(window.audio_cue_type or "none", 0.0)
    return (
        high_salience,
        window.audio_pop_score + cue_bonus,
        cue_confidence,
        window.audio_score,
        window.event_context_score,
        window.combined_score,
        window.motion_score,
        window.visual_score,
    )


def _candidate_window_recall_key(window: CandidateWindow) -> tuple[float, float, float, float, float]:
    return (
        window.event_context_score,
        window.audio_pop_score,
        window.combined_score,
        window.motion_score,
        window.visual_score,
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
    peak_window = max(group, key=lambda item: (item.event_context_score, item.audio_pop_score, item.combined_score))
    has_event_anchor = peak_window.event_context_score >= 0.45 or peak_window.audio_pop_score >= AUDIO_POP_EVENT_CENTER_THRESHOLD
    anchor_window = peak_window if has_event_anchor else group[0]

    start_time = max(anchor_window.start_time - settings.clip_padding_seconds, 0.0)
    group_end = peak_window.end_time if has_event_anchor else group[-1].end_time
    if (
        peak_window.audio_pop_score >= AUDIO_POP_EVENT_CENTER_THRESHOLD
        and peak_window.audio_pop_time is not None
        and peak_window.event_context_score < 0.45
    ):
        start_time = max(0.0, min(start_time, peak_window.audio_pop_time - AUDIO_REACTION_WINDOW_LEAD_SECONDS))
        group_end = max(group_end, peak_window.audio_pop_time + AUDIO_REACTION_WINDOW_FOLLOW_SECONDS)
    padded_end = group_end + settings.clip_padding_seconds
    max_end = max(group_end, start_time + settings.max_clip_duration_seconds)
    end_time = min(padded_end, max_end)
    duration = end_time - start_time

    if duration < settings.min_clip_duration_seconds:
        end_time = start_time + settings.min_clip_duration_seconds
    if end_time - start_time > settings.max_clip_duration_seconds:
        if (
            peak_window.audio_pop_score >= AUDIO_POP_EVENT_CENTER_THRESHOLD
            and peak_window.audio_pop_time is not None
            and peak_window.event_context_score < 0.45
        ):
            preferred_lead = min(
                AUDIO_REACTION_WINDOW_LEAD_SECONDS,
                settings.max_clip_duration_seconds * 0.62,
            )
            start_time = max(0.0, peak_window.audio_pop_time - preferred_lead)
            end_time = min(
                max(group_end, peak_window.audio_pop_time + AUDIO_REACTION_WINDOW_FOLLOW_SECONDS),
                start_time + settings.max_clip_duration_seconds,
            )
        else:
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
        audio_pop_score=max(item.audio_pop_score for item in group),
        audio_pop_time=max(group, key=lambda item: item.audio_pop_score).audio_pop_time,
        audio_cue_type=max(group, key=lambda item: item.audio_cue_confidence).audio_cue_type,
        audio_cue_confidence=max(item.audio_cue_confidence for item in group),
    )


def _fallback_window(duration_seconds: float, audio_profile: List[float], settings: Settings) -> CandidateWindow:
    peak_index = max(range(len(audio_profile)), key=lambda index: audio_profile[index], default=0)
    audio_pop_time = min((peak_index + 0.5) * AUDIO_PROFILE_BUCKET_SECONDS, duration_seconds)
    center = min(audio_pop_time, max(duration_seconds - (settings.min_clip_duration_seconds / 2.0), 0.0))
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
        peak_time=min(max(audio_pop_time, start_time), end_time),
        audio_score=audio_score,
        visual_score=visual_score,
        motion_score=motion_score,
        combined_score=combined_score,
        audio_pop_score=0.0,
        audio_pop_time=audio_pop_time,
    )
