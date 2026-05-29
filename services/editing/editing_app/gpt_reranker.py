from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Callable, Dict, List, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .backend_imports import ensure_ios_backend_on_path

ensure_ios_backend_on_path()

from app.editing import (  # noqa: E402
    CreateEditJobRequest,
    DEFENSIVE_TRACKING_EVENT_ROLES,
    DEFENSIVE_TRACKING_RESULT_ROLES,
    EditPlanPatch,
    EditCandidateClip,
    GPT_CANDIDATE_REVIEW_LIMIT,
    GPTHighlightClipDecision,
    GPTPlanEdit,
    GPTHighlightRerankSummary,
    MIN_PLAN_CLIP_SECONDS,
    MIN_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS,
    MIN_SHOT_CONTEXT_LEAD_IN_SECONDS,
    ReviseEditJobRequest,
    StoredEditJob,
    apply_gpt_highlight_rerank,
    build_agent_editing_context,
    clip_outcome_evidence_source,
    clip_outcome_reliability_score,
    derive_user_prompt_intent,
    filter_clips_for_team_selection,
    get_template_pack_for_plan,
    is_defensive_event_like_clip,
    is_plan_quality_eligible_clip,
    is_shot_like_clip,
    native_shot_signals_for_clip,
    rank_clips,
    summarize_clip_pool,
    team_attribution_status,
    team_evidence_summary,
    uncertain_review_clip_ids_for_team_selection,
    validate_edit_plan_patch,
)


ResponseClient = Callable[[Dict[str, Any], str, str, float], Dict[str, Any]]
ALLOWED_IMAGE_DETAIL_LEVELS = {"low", "high", "original", "auto"}
REQUIRED_KEYFRAME_ROLES = {"start", "eventCenter", "finish"}
SHOT_CONTEXT_KEYFRAME_ROLES = ("preEvent", "release", "shotArcEarly", "shotArcLate", "rimApproach", "rimEntry", "belowRim")
MIN_GPT_CANDIDATE_LEAD_IN_SECONDS = MIN_SHOT_CONTEXT_LEAD_IN_SECONDS
MIN_GPT_CANDIDATE_FOLLOW_THROUGH_SECONDS = MIN_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS
MIN_GPT_SHOT_LIKE_CANDIDATE_SECONDS = 3.0
MIN_GPT_DEFENSIVE_CANDIDATE_SECONDS = 2.0
MIN_GPT_DEFENSIVE_LEAD_IN_SECONDS = 0.6
MIN_GPT_DEFENSIVE_FOLLOW_THROUGH_SECONDS = 0.5
MIN_GPT_NON_SHOT_CANDIDATE_SECONDS = 2.5
SHOT_CONTEXT_EXPANSION_LEAD_SECONDS = 2.0
SHOT_CONTEXT_EXPANSION_FOLLOW_THROUGH_SECONDS = 1.25
SHOT_CONTEXT_EXPANSION_TARGET_SECONDS = 5.5
SHOT_CONTEXT_EXPANSION_MAX_SECONDS = 8.0
DEFENSIVE_CONTEXT_EXPANSION_LEAD_SECONDS = 1.6
DEFENSIVE_CONTEXT_EXPANSION_FOLLOW_THROUGH_SECONDS = 1.2
DEFENSIVE_CONTEXT_EXPANSION_TARGET_SECONDS = 4.5
DEFENSIVE_CONTEXT_EXPANSION_MAX_SECONDS = 7.0
TEAM_EVIDENCE_GPT_GUIDANCE = (
    "Treat teamEvidence as authoritative for selected-team confidence: teamEvidence.status=evidence_backed means the "
    "jersey-color attribution has enough cited frame and role evidence; teamEvidence.status=weak_evidence, "
    "teamEvidence.status=missing_attribution, or teamAttributionStatus=uncertain must never be promoted to a confident "
    "selected-team match from raw teamAttribution.confidence alone. For selected-team edits, exclude evidence-backed "
    "confident opponent clips; keep weak or uncertain team-attribution clips only as review-worthy candidates when the "
    "play is otherwise strong and not confidently the opponent. "
)


@dataclass(frozen=True)
class GPTHighlightRerankerSettings:
    enabled: bool
    api_key: Optional[str]
    model: str
    endpoint: str
    timeout_seconds: float
    max_output_tokens: int
    free_max_clips: int
    paid_max_clips: int
    free_frames_per_clip: int
    paid_frames_per_clip: int
    frame_width: int
    jpeg_quality: int
    max_image_bytes: int
    image_detail: str
    plan_edit_enabled: bool = False
    revision_enabled: bool = False

    @classmethod
    def from_env(cls) -> "GPTHighlightRerankerSettings":
        return cls(
            enabled=(
                _env_flag("HOOPS_AI_CLIP_GPT_EDITOR_ENABLED")
                or _env_flag("HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED")
                or _env_flag("HOOPS_GPT_HIGHLIGHT_RERANK_ENABLED")
            ),
            api_key=os.getenv("HOOPS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or None,
            model=os.getenv("HOOPS_AI_CLIP_GPT_MODEL", os.getenv("HOOPS_GPT_HIGHLIGHT_RERANK_MODEL", "gpt-4.1")),
            endpoint=os.getenv("HOOPS_AI_CLIP_GPT_ENDPOINT", os.getenv("HOOPS_GPT_HIGHLIGHT_RERANK_ENDPOINT", "https://api.openai.com/v1/responses")),
            timeout_seconds=_env_float("HOOPS_AI_CLIP_GPT_TIMEOUT_SECONDS", _env_float("HOOPS_GPT_HIGHLIGHT_RERANK_TIMEOUT_SECONDS", 60.0, 1.0, 60.0), 1.0, 60.0),
            max_output_tokens=_env_int("HOOPS_AI_CLIP_GPT_MAX_OUTPUT_TOKENS", _env_int("HOOPS_GPT_HIGHLIGHT_RERANK_MAX_OUTPUT_TOKENS", 12000, 256, 12000), 256, 12000),
            free_max_clips=_env_int(
                "HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE",
                _env_int("HOOPS_GPT_HIGHLIGHT_RERANK_FREE_MAX_CLIPS", GPT_CANDIDATE_REVIEW_LIMIT, 1, GPT_CANDIDATE_REVIEW_LIMIT),
                1,
                GPT_CANDIDATE_REVIEW_LIMIT,
            ),
            paid_max_clips=_env_int(
                "HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO",
                _env_int("HOOPS_GPT_HIGHLIGHT_RERANK_PAID_MAX_CLIPS", GPT_CANDIDATE_REVIEW_LIMIT, 20, GPT_CANDIDATE_REVIEW_LIMIT),
                20,
                GPT_CANDIDATE_REVIEW_LIMIT,
            ),
            free_frames_per_clip=_env_int("HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP", _env_int("HOOPS_GPT_HIGHLIGHT_RERANK_FREE_FRAMES_PER_CLIP", 10, 3, 10), 3, 10),
            paid_frames_per_clip=_env_int("HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP", _env_int("HOOPS_GPT_HIGHLIGHT_RERANK_PAID_FRAMES_PER_CLIP", 10, 5, 10), 3, 10),
            frame_width=_env_int("HOOPS_GPT_HIGHLIGHT_RERANK_FRAME_WIDTH", 1024, 256, 1280),
            jpeg_quality=_env_int("HOOPS_GPT_HIGHLIGHT_RERANK_JPEG_QUALITY", 4, 2, 12),
            max_image_bytes=_env_int("HOOPS_GPT_HIGHLIGHT_RERANK_MAX_IMAGE_BYTES", 750_000, 40_000, 1_000_000),
            image_detail=_env_image_detail("HOOPS_AI_CLIP_GPT_IMAGE_DETAIL", _env_image_detail("HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL", "high")),
            plan_edit_enabled=_env_flag("HOOPS_AI_CLIP_GPT_PLAN_EDIT_ENABLED"),
            revision_enabled=_env_flag("HOOPS_AI_CLIP_GPT_REVISION_ENABLED"),
        )

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.api_key)

    def limits_for(self, plan_tier: str) -> tuple[int, int]:
        if plan_tier == "free":
            return self.free_max_clips, self.free_frames_per_clip
        return self.paid_max_clips, self.paid_frames_per_clip

    def public_status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "model": self.model if self.enabled else None,
            "freeMaxClips": self.free_max_clips,
            "paidMaxClips": self.paid_max_clips,
            "freeFramesPerClip": self.free_frames_per_clip,
            "paidFramesPerClip": self.paid_frames_per_clip,
            "aiClipGptMaxCandidatesFree": self.free_max_clips,
            "aiClipGptMaxCandidatesPro": self.paid_max_clips,
            "aiClipGptKeyframesPerClip": {
                "free": self.free_frames_per_clip,
                "pro": self.paid_frames_per_clip,
            },
            "aiClipGptPlanEditEnabled": self.plan_edit_enabled,
            "aiClipGptRevisionEnabled": self.revision_enabled,
        }


@dataclass(frozen=True)
class SampledFrame:
    clip_id: str
    role: str
    time_seconds: float
    data_url: str


def rerank_edit_request_with_gpt(
    request: CreateEditJobRequest,
    source_path: Path,
    settings: GPTHighlightRerankerSettings,
    response_client: ResponseClient = None,
) -> CreateEditJobRequest:
    if not settings.enabled:
        return _with_fallback(request, "disabled", settings.model, "disabled")
    if not settings.api_key:
        return _with_fallback(request, "fallback", settings.model, "missing_api_key")
    if not source_path.is_file():
        return _with_fallback(request, "fallback", settings.model, "source_missing")

    request = expand_shot_candidate_windows_from_source_path(request, source_path)
    team_filtered_clips = filter_clips_for_team_selection(request.clips, request.teamSelection)
    request = request.model_copy(update={"clips": team_filtered_clips})
    max_clips, frames_per_clip = settings.limits_for(request.planTier)
    sampled_clips = _quality_filtered_sampled_clips(rank_clips(request.clips), max_clips, request=request)
    if not sampled_clips:
        return _with_fallback(request, "fallback", settings.model, "no_quality_candidates", 0, 0)
    sampled_frames = _extract_candidate_keyframes(source_path, sampled_clips, frames_per_clip, settings)
    if not sampled_frames:
        return _with_fallback(request, "fallback", settings.model, "keyframe_extraction_failed", len(sampled_clips), 0)
    missing_required = _missing_required_keyframes(sampled_clips, sampled_frames)
    if missing_required:
        incomplete_clip_ids = set(missing_required)
        sampled_clips = [clip for clip in sampled_clips if clip.id not in incomplete_clip_ids]
        sampled_frames = [frame for frame in sampled_frames if frame.clip_id not in incomplete_clip_ids]
        if not sampled_clips:
            return _with_fallback(request, "fallback", settings.model, "keyframe_extraction_incomplete", 0, len(sampled_frames))
    missing_shot_context = _missing_shot_context_keyframes(sampled_clips, sampled_frames, frames_per_clip)
    if missing_shot_context:
        incomplete_clip_ids = set(missing_shot_context)
        sampled_clips = [clip for clip in sampled_clips if clip.id not in incomplete_clip_ids]
        sampled_frames = [frame for frame in sampled_frames if frame.clip_id not in incomplete_clip_ids]
        if not sampled_clips:
            return _with_fallback(request, "fallback", settings.model, "shot_keyframe_extraction_incomplete", 0, len(sampled_frames))

    payload = _build_openai_payload(request, sampled_clips, sampled_frames, settings)
    try:
        client = response_client or _default_responses_client
        response_payload = client(payload, settings.api_key, settings.endpoint, settings.timeout_seconds)
        output_text = _extract_output_text(response_payload)
        output = json.loads(output_text)
        decisions = [GPTHighlightClipDecision(**item) for item in output.get("decisions", [])]
        raw_story_order = output.get("storyOrder", [])
        story_order = [str(item) for item in raw_story_order if isinstance(item, str)] if isinstance(raw_story_order, list) else []
        plan_edit = GPTPlanEdit(**output["planEdit"]) if settings.plan_edit_enabled and isinstance(output.get("planEdit"), dict) else None
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
        reason = "openai_unavailable"
        if isinstance(error, HTTPError):
            reason = f"openai_http_{error.code}"
        return _with_fallback(request, "fallback", settings.model, reason, len(sampled_clips), len(sampled_frames))

    sampled_clip_ids = {clip.id for clip in sampled_clips}
    valid_decision_ids = [decision.clipId for decision in decisions if decision.clipId in sampled_clip_ids]
    duplicate_decision_ids = {clip_id for clip_id in valid_decision_ids if valid_decision_ids.count(clip_id) > 1}
    if duplicate_decision_ids:
        return _with_fallback(request, "fallback", settings.model, "duplicate_gpt_decisions", len(sampled_clips), len(sampled_frames))
    valid_decision_id_set = set(valid_decision_ids)
    if valid_decision_id_set != sampled_clip_ids:
        return _with_fallback(request, "fallback", settings.model, "incomplete_gpt_decisions", len(sampled_clips), len(sampled_frames))
    sampled_decisions = [decision for decision in decisions if decision.clipId in sampled_clip_ids]

    return apply_gpt_highlight_rerank(
        request,
        sampled_decisions,
        model=settings.model,
        sampled_clip_count=len(sampled_clips),
        sampled_frame_count=len(sampled_frames),
        story_order=story_order,
        plan_edit=plan_edit,
        sampled_frame_roles_by_clip=_sampled_frame_roles_by_clip(sampled_frames),
    )


def request_gpt_edit_plan_patch(
    job: StoredEditJob,
    revision: ReviseEditJobRequest,
    settings: GPTHighlightRerankerSettings,
    response_client: ResponseClient = None,
) -> Optional[EditPlanPatch]:
    if not settings.revision_enabled or not settings.configured:
        return None
    payload = _build_revision_patch_payload(job, revision, settings)
    try:
        client = response_client or _default_responses_client
        response_payload = client(payload, settings.api_key or "", settings.endpoint, settings.timeout_seconds)
        output_text = _extract_output_text(response_payload)
        patch = EditPlanPatch(**json.loads(output_text))
        if patch.revisionIntent != revision.command or patch.baseEditPlanId != job.edit_job_id:
            return None
        source_clips = filter_clips_for_team_selection(
            job.request.clips,
            job.request.teamSelection,
            include_review_only_uncertain=False,
        )
        patched_plan, errors = validate_edit_plan_patch(job.plan, patch, source_clips, job.request.planTier)
        if patched_plan is None or errors:
            return None
        return patch
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError, TypeError):
        return None


def _with_fallback(
    request: CreateEditJobRequest,
    status: str,
    model: Optional[str],
    reason: str,
    sampled_clip_count: int = 0,
    sampled_frame_count: int = 0,
) -> CreateEditJobRequest:
    kept_clip_ids, rejected_clip_ids, rejected_reason_counts = _fallback_quality_receipt(request)
    summary = GPTHighlightRerankSummary(
        status=status if status in {"disabled", "fallback"} else "fallback",
        model=model,
        sampledClipCount=sampled_clip_count,
        sampledFrameCount=sampled_frame_count,
        keptClipIds=kept_clip_ids,
        rejectedClipIds=rejected_clip_ids,
        uncertainReviewClipIds=uncertain_review_clip_ids_for_team_selection(request.clips, request.teamSelection),
        rejectedReasonCounts=rejected_reason_counts,
        fallbackReason=reason,
    )
    return request.model_copy(update={"gptRerankSummary": summary})


def _fallback_quality_receipt(request: CreateEditJobRequest) -> tuple[List[str], List[str], Dict[str, int]]:
    render_clips = filter_clips_for_team_selection(
        request.clips,
        request.teamSelection,
        include_review_only_uncertain=False,
    )
    render_clip_ids = {clip.id for clip in render_clips}
    eligible_clips = rank_clips([clip for clip in render_clips if is_plan_quality_eligible_clip(clip)])
    eligible_clip_ids = {clip.id for clip in eligible_clips}
    rejected_clip_ids: List[str] = []
    rejected_reason_counts: Dict[str, int] = {}

    for clip in request.clips:
        if clip.id in eligible_clip_ids:
            continue
        reason = _fallback_rejection_reason(clip, request, render_clip_ids)
        rejected_clip_ids.append(clip.id)
        rejected_reason_counts[reason] = rejected_reason_counts.get(reason, 0) + 1

    return (
        [clip.id for clip in eligible_clips[:GPT_CANDIDATE_REVIEW_LIMIT]],
        rejected_clip_ids[:GPT_CANDIDATE_REVIEW_LIMIT],
        rejected_reason_counts,
    )


def _fallback_rejection_reason(
    clip: EditCandidateClip,
    request: CreateEditJobRequest,
    render_clip_ids: set[str],
) -> str:
    if request.teamSelection is not None and request.teamSelection.mode == "team":
        status = team_attribution_status(clip, request.teamSelection)
        if status == "opponent":
            return "opponent_team_candidate"
        if status == "uncertain" and clip.id not in render_clip_ids:
            return "needs_manual_team_review"
    return "candidate_missing_minimum_quality_context"


def expand_shot_candidate_windows_from_source_path(
    request: CreateEditJobRequest,
    source_path: Path,
) -> CreateEditJobRequest:
    if not source_path.is_file():
        return request
    return expand_shot_candidate_windows_for_source_context(
        request,
        _probe_source_duration_seconds(source_path),
    )


def expand_shot_candidate_windows_for_source_context(
    request: CreateEditJobRequest,
    source_duration_seconds: Optional[float],
) -> CreateEditJobRequest:
    if not source_duration_seconds or source_duration_seconds <= 0:
        return request

    expanded_clips: List[EditCandidateClip] = []
    changed = False
    for clip in request.clips:
        expanded = _expand_candidate_clip_for_source_context(clip, source_duration_seconds)
        expanded_clips.append(expanded)
        changed = changed or expanded.start != clip.start or expanded.end != clip.end

    if not changed:
        return request
    return request.model_copy(update={"clips": expanded_clips})


def _expand_candidate_clip_for_source_context(clip: EditCandidateClip, source_duration_seconds: float) -> EditCandidateClip:
    if _is_defensive_candidate_clip(clip):
        return _expand_defensive_candidate_clip(clip, source_duration_seconds)
    if is_shot_like_clip(clip):
        return _expand_shot_candidate_clip(clip, source_duration_seconds)
    return clip


def _expand_shot_candidate_clip(clip: EditCandidateClip, source_duration_seconds: float) -> EditCandidateClip:
    if not is_shot_like_clip(clip):
        return clip

    source_duration = max(source_duration_seconds, clip.end)
    event_center = min(max(clip.eventCenter, 0.0), source_duration)
    start = min(clip.start, event_center - SHOT_CONTEXT_EXPANSION_LEAD_SECONDS)
    end = max(clip.end, event_center + SHOT_CONTEXT_EXPANSION_FOLLOW_THROUGH_SECONDS)

    if end - start < SHOT_CONTEXT_EXPANSION_TARGET_SECONDS:
        missing = SHOT_CONTEXT_EXPANSION_TARGET_SECONDS - (end - start)
        start -= missing * 0.65
        end += missing * 0.35

    start, end = _clamp_expanded_window(start, end, source_duration)
    if end - start > SHOT_CONTEXT_EXPANSION_MAX_SECONDS:
        preferred_lead = min(
            SHOT_CONTEXT_EXPANSION_MAX_SECONDS - SHOT_CONTEXT_EXPANSION_FOLLOW_THROUGH_SECONDS,
            max(SHOT_CONTEXT_EXPANSION_LEAD_SECONDS, SHOT_CONTEXT_EXPANSION_MAX_SECONDS * 0.65),
        )
        start = event_center - preferred_lead
        end = start + SHOT_CONTEXT_EXPANSION_MAX_SECONDS
        start, end = _clamp_expanded_window(start, end, source_duration)

    if end - start <= clip.duration:
        return clip
    return clip.model_copy(
        update={
            "start": round(start, 3),
            "end": round(end, 3),
            "eventCenter": round(event_center, 3),
        }
    )


def _expand_defensive_candidate_clip(clip: EditCandidateClip, source_duration_seconds: float) -> EditCandidateClip:
    source_duration = max(source_duration_seconds, clip.end)
    event_center = min(max(clip.eventCenter, 0.0), source_duration)
    start = min(clip.start, event_center - DEFENSIVE_CONTEXT_EXPANSION_LEAD_SECONDS)
    end = max(clip.end, event_center + DEFENSIVE_CONTEXT_EXPANSION_FOLLOW_THROUGH_SECONDS)

    if end - start < DEFENSIVE_CONTEXT_EXPANSION_TARGET_SECONDS:
        missing = DEFENSIVE_CONTEXT_EXPANSION_TARGET_SECONDS - (end - start)
        start -= missing * 0.55
        end += missing * 0.45

    start, end = _clamp_expanded_window(start, end, source_duration)
    if end - start > DEFENSIVE_CONTEXT_EXPANSION_MAX_SECONDS:
        preferred_lead = min(
            DEFENSIVE_CONTEXT_EXPANSION_MAX_SECONDS - DEFENSIVE_CONTEXT_EXPANSION_FOLLOW_THROUGH_SECONDS,
            max(DEFENSIVE_CONTEXT_EXPANSION_LEAD_SECONDS, DEFENSIVE_CONTEXT_EXPANSION_MAX_SECONDS * 0.55),
        )
        start = event_center - preferred_lead
        end = start + DEFENSIVE_CONTEXT_EXPANSION_MAX_SECONDS
        start, end = _clamp_expanded_window(start, end, source_duration)

    if end - start <= clip.duration:
        return clip
    return clip.model_copy(
        update={
            "start": round(start, 3),
            "end": round(end, 3),
            "eventCenter": round(event_center, 3),
        }
    )


def _clamp_expanded_window(start: float, end: float, source_duration_seconds: float) -> tuple[float, float]:
    source_duration = max(source_duration_seconds, 0.001)
    if start < 0.0:
        end = min(source_duration, end - start)
        start = 0.0
    if end > source_duration:
        overflow = end - source_duration
        start = max(0.0, start - overflow)
        end = source_duration
    return max(0.0, start), min(source_duration, end)


def _probe_source_duration_seconds(source_path: Path) -> Optional[float]:
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(source_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=8,
        )
        payload = json.loads(completed.stdout)
        duration = float(payload.get("format", {}).get("duration", 0.0))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return duration if duration > 0.0 else None


def _candidate_quality_hints(clip: EditCandidateClip) -> Dict[str, Any]:
    lead_in = round(max(0.0, clip.eventCenter - clip.start), 3)
    follow_through = round(max(0.0, clip.end - clip.eventCenter), 3)
    duration = round(clip.duration, 3)
    is_shot_like = is_shot_like_clip(clip)
    is_defensive = _is_defensive_candidate_clip(clip)
    requires_shot_timing = is_shot_like and not is_defensive
    if requires_shot_timing:
        min_duration = max(MIN_PLAN_CLIP_SECONDS, MIN_GPT_SHOT_LIKE_CANDIDATE_SECONDS)
        min_lead_in = MIN_GPT_CANDIDATE_LEAD_IN_SECONDS
        min_follow_through = MIN_GPT_CANDIDATE_FOLLOW_THROUGH_SECONDS
    elif is_defensive:
        min_duration = max(MIN_PLAN_CLIP_SECONDS, MIN_GPT_DEFENSIVE_CANDIDATE_SECONDS)
        min_lead_in = MIN_GPT_DEFENSIVE_LEAD_IN_SECONDS
        min_follow_through = MIN_GPT_DEFENSIVE_FOLLOW_THROUGH_SECONDS
    else:
        min_duration = max(MIN_PLAN_CLIP_SECONDS, MIN_GPT_NON_SHOT_CANDIDATE_SECONDS)
        min_lead_in = MIN_GPT_CANDIDATE_LEAD_IN_SECONDS
        min_follow_through = MIN_GPT_CANDIDATE_FOLLOW_THROUGH_SECONDS
    return {
        "durationSeconds": duration,
        "defensiveEventLike": is_defensive,
        "leadInSeconds": lead_in,
        "followThroughSeconds": follow_through,
        "minRecommendedDurationSeconds": min_duration,
        "minLeadInSeconds": min_lead_in,
        "minFollowThroughSeconds": min_follow_through,
        "shotLike": is_shot_like,
        "nativeShotSignals": native_shot_signals_for_clip(clip).model_dump(mode="json"),
        "outcomeEvidenceSource": clip_outcome_evidence_source(clip),
        "outcomeReliabilityScore": clip_outcome_reliability_score(clip),
        "timingWindowOk": (
            duration >= min_duration
            and lead_in >= min_lead_in
            and follow_through >= min_follow_through
        ),
        "requiresVisibleOutcome": True,
        "rejectIfOnlyBasketOrAftermath": True,
    }


def _quality_filtered_sampled_clips(
    clips: Sequence[EditCandidateClip],
    max_clips: int,
    request: Optional[CreateEditJobRequest] = None,
) -> List[EditCandidateClip]:
    eligible: List[EditCandidateClip] = []
    for clip in clips:
        if not is_plan_quality_eligible_clip(clip):
            continue
        hints = _candidate_quality_hints(clip)
        if not hints["timingWindowOk"]:
            continue
        eligible.append(clip)

    if len(eligible) <= max_clips:
        return eligible

    selected: List[EditCandidateClip] = []
    selected_ids: set[str] = set()

    def add_clip(clip: EditCandidateClip) -> None:
        if len(selected) >= max_clips or clip.id in selected_ids:
            return
        selected.append(clip)
        selected_ids.add(clip.id)

    defense_reserve = _defensive_sampling_reserve_limit(request, max_clips)
    if defense_reserve == 1:
        for clip in eligible:
            if _is_defensive_candidate_clip(clip):
                add_clip(clip)
                break
    elif defense_reserve > 1:
        reserved_defensive_count = 0
        for family in ("block", "steal", "forced_turnover", "defensive_stop", "defensive"):
            for clip in eligible:
                if clip.id in selected_ids:
                    continue
                if _defensive_candidate_family(clip) != family:
                    continue
                add_clip(clip)
                reserved_defensive_count += 1
                break
            if reserved_defensive_count >= defense_reserve:
                break

        for clip in eligible:
            if reserved_defensive_count >= defense_reserve:
                break
            if clip.id in selected_ids or not _is_defensive_candidate_clip(clip):
                continue
            add_clip(clip)
            reserved_defensive_count += 1

    if request and request.teamSelection is not None and request.teamSelection.mode == "team":
        team_reserve = min(max(2, max_clips // 6), max_clips)
        for clip in eligible:
            if team_attribution_status(clip, request.teamSelection) == "uncertain":
                add_clip(clip)
                if sum(1 for item in selected if team_attribution_status(item, request.teamSelection) == "uncertain") >= team_reserve:
                    break

    for clip in eligible:
        add_clip(clip)
        if len(selected) >= max_clips:
            break

    return rank_clips(selected)


def _defensive_sampling_reserve_limit(request: Optional[CreateEditJobRequest], max_clips: int) -> int:
    if max_clips < 8:
        return 0
    reserve = max(3, max_clips // 6)
    if request is not None:
        user_intent = derive_user_prompt_intent(request.userPrompt, request.planTier)
        template = get_template_pack_for_plan(request.preset, request.templateId)
        defense_focused = bool(
            user_intent
            and (
                "defense" in user_intent.focusAreas
                or "defense_focus" in user_intent.styleIntents
            )
        )
        team_story_template = template.templateId in {"team_highlight_pro_v1", "coach_review_v1"}
        if defense_focused or team_story_template:
            reserve = max(reserve, max_clips // 4)
    return min(reserve, max_clips)


def _is_defensive_candidate_clip(clip: EditCandidateClip) -> bool:
    return is_defensive_event_like_clip(clip)


def _defensive_candidate_family(clip: EditCandidateClip) -> Optional[str]:
    label = clip.label.strip().lower()
    tokens = set(label.replace("-", " ").replace("_", " ").split())
    if tokens & {"block", "blocked", "contest"} or "blocked shot" in label:
        return "block"
    if tokens & {"steal", "strip"}:
        return "steal"
    if "turnover" in tokens and (tokens & {"forced", "force", "defensive", "defense"}):
        return "forced_turnover"
    if "stop" in tokens and ("defensive stop" in label or "defense stop" in label or label == "stop"):
        return "defensive_stop"
    if tokens & {"defense", "defensive", "pressure", "lockdown"}:
        return "defensive"
    return None


def _extract_candidate_keyframes(
    source_path: Path,
    clips: Sequence[EditCandidateClip],
    frames_per_clip: int,
    settings: GPTHighlightRerankerSettings,
) -> List[SampledFrame]:
    frames: List[SampledFrame] = []
    with tempfile.TemporaryDirectory(prefix="hoopclips-gpt-rerank-") as temp_dir:
        temp_root = Path(temp_dir)
        for clip in clips:
            for role, second in _sample_times_for_clip(clip, frames_per_clip):
                frame_path = temp_root / f"{_safe_id(clip.id)}-{role}.jpg"
                if not _extract_jpeg_frame(source_path, frame_path, second, settings):
                    continue
                if frame_path.stat().st_size > settings.max_image_bytes:
                    continue
                encoded = base64.b64encode(frame_path.read_bytes()).decode("ascii")
                frames.append(
                    SampledFrame(
                        clip_id=clip.id,
                        role=role,
                        time_seconds=round(second, 3),
                        data_url=f"data:image/jpeg;base64,{encoded}",
                    )
                )
    return frames


def _missing_required_keyframes(
    clips: Sequence[EditCandidateClip],
    frames: Sequence[SampledFrame],
) -> Dict[str, List[str]]:
    roles_by_clip_id: Dict[str, set[str]] = {clip.id: set() for clip in clips}
    for frame in frames:
        if frame.clip_id in roles_by_clip_id:
            roles_by_clip_id[frame.clip_id].add(frame.role)
    return {
        clip_id: sorted(REQUIRED_KEYFRAME_ROLES - roles)
        for clip_id, roles in roles_by_clip_id.items()
        if not REQUIRED_KEYFRAME_ROLES.issubset(roles)
    }


def _required_shot_context_roles(frames_per_clip: int) -> set[str]:
    if frames_per_clip >= 10:
        return set(SHOT_CONTEXT_KEYFRAME_ROLES)
    if frames_per_clip >= 9:
        return {"preEvent", "release", "shotArcEarly", "outcome", "rim", "postOutcome"}
    if frames_per_clip >= 8:
        return {"preEvent", "release", "outcome", "rim", "postOutcome"}
    if frames_per_clip >= 7:
        return {"preEvent", "release", "outcome", "rim"}
    if frames_per_clip >= 6:
        return {"preEvent", "release", "outcome"}
    if frames_per_clip >= 5:
        return {"preEvent", "outcome"}
    if frames_per_clip >= 4:
        return {"preEvent"}
    return set()


def _missing_shot_context_keyframes(
    clips: Sequence[EditCandidateClip],
    frames: Sequence[SampledFrame],
    frames_per_clip: int,
) -> Dict[str, List[str]]:
    required_roles = _required_shot_context_roles(frames_per_clip)
    if not required_roles:
        return {}
    roles_by_clip_id: Dict[str, set[str]] = {
        clip.id: set()
        for clip in clips
        if is_shot_like_clip(clip) and not _is_defensive_candidate_clip(clip)
    }
    for frame in frames:
        if frame.clip_id in roles_by_clip_id:
            roles_by_clip_id[frame.clip_id].add(frame.role)
    return {
        clip_id: sorted(required_roles - roles)
        for clip_id, roles in roles_by_clip_id.items()
        if not required_roles.issubset(roles)
    }


def _sampled_frame_roles_by_clip(frames: Sequence[SampledFrame]) -> Dict[str, List[str]]:
    roles_by_clip_id: Dict[str, List[str]] = {}
    for frame in frames:
        roles = roles_by_clip_id.setdefault(frame.clip_id, [])
        if frame.role not in roles:
            roles.append(frame.role)
    return roles_by_clip_id


def _sample_times_for_clip(clip: EditCandidateClip, frames_per_clip: int) -> List[tuple[str, float]]:
    if _is_defensive_candidate_clip(clip):
        return _defensive_sample_times_for_clip(clip, frames_per_clip)

    finish = max(clip.start, clip.end - 0.05)
    base = [("start", clip.start), ("eventCenter", clip.eventCenter), ("finish", finish)]
    base_samples = _clamp_sample_times(base, clip)
    if frames_per_clip <= 3:
        return base_samples

    # Native analysis anchors shot eventCenter on the rim/result moment, not release.
    setup_second = max(clip.start, clip.eventCenter - 1.8)
    release_second = max(clip.start, clip.eventCenter - 1.1)
    shot_arc_early_second = max(clip.start, clip.eventCenter - 0.65)
    shot_arc_late_second = max(clip.start, clip.eventCenter - 0.35)
    rim_approach_second = max(clip.start, clip.eventCenter - 0.15)
    rim_second = max(clip.start, clip.eventCenter - 0.08)
    outcome_second = min(finish, clip.eventCenter + 0.12)
    rim_entry_second = min(finish, clip.eventCenter + 0.12)
    below_rim_second = min(finish, clip.eventCenter + 0.35)
    post_outcome_second = min(finish, clip.eventCenter + 0.5)
    mid_action_second = clip.start + ((finish - clip.start) * 0.45)
    if frames_per_clip >= 10:
        candidates = [
            ("preEvent", setup_second),
            ("release", release_second),
            ("shotArcEarly", shot_arc_early_second),
            ("shotArcLate", shot_arc_late_second),
            ("rimApproach", rim_approach_second),
            ("rimEntry", rim_entry_second),
            ("belowRim", below_rim_second),
        ]
    elif frames_per_clip >= 9:
        candidates = [
            ("preEvent", setup_second),
            ("release", release_second),
            ("shotArcEarly", shot_arc_early_second),
            ("outcome", outcome_second),
            ("rim", rim_second),
            ("postOutcome", post_outcome_second),
        ]
    elif frames_per_clip >= 8:
        candidates = [
            ("preEvent", setup_second),
            ("release", release_second),
            ("outcome", outcome_second),
            ("rim", rim_second),
            ("postOutcome", post_outcome_second),
        ]
    elif frames_per_clip >= 7:
        candidates = [
            ("preEvent", setup_second),
            ("release", release_second),
            ("outcome", outcome_second),
            ("rim", rim_second),
        ]
    elif frames_per_clip >= 6:
        candidates = [
            ("preEvent", setup_second),
            ("release", release_second),
            ("outcome", outcome_second),
        ]
    elif frames_per_clip >= 5:
        candidates = [("preEvent", setup_second), ("outcome", outcome_second)]
    else:
        candidates = [("preEvent", setup_second), ("midAction", mid_action_second)]
    reserved_buckets = {round(second, 1) for _, second in base_samples}
    context_samples = _dedupe_sample_times(candidates, clip, reserved_buckets)[: max(0, frames_per_clip - 3)]
    return sorted([*base_samples, *context_samples], key=lambda item: item[1])


def _defensive_sample_times_for_clip(clip: EditCandidateClip, frames_per_clip: int) -> List[tuple[str, float]]:
    finish = max(clip.start, clip.end - 0.05)
    duration = max(finish - clip.start, 0.001)
    base = [("start", clip.start), ("eventCenter", clip.eventCenter), ("finish", finish)]
    base_samples = _clamp_sample_times(base, clip)
    if frames_per_clip <= 3:
        return base_samples

    defense_setup_second = clip.start + (duration * 0.18)
    challenge_second = max(clip.start, clip.eventCenter - 0.55)
    possession_change_second = min(finish, clip.eventCenter + 0.18)
    recovery_second = min(finish, clip.eventCenter + 0.55)
    defense_outcome_second = min(finish, clip.eventCenter + 0.9)
    mid_action_second = clip.start + (duration * 0.45)
    if frames_per_clip >= 8:
        candidates = [
            ("defenseSetup", defense_setup_second),
            ("challenge", challenge_second),
            ("possessionChange", possession_change_second),
            ("recovery", recovery_second),
            ("defenseOutcome", defense_outcome_second),
            ("midAction", mid_action_second),
        ]
    elif frames_per_clip >= 6:
        candidates = [
            ("defenseSetup", defense_setup_second),
            ("challenge", challenge_second),
            ("possessionChange", possession_change_second),
        ]
    elif frames_per_clip >= 5:
        candidates = [("challenge", challenge_second), ("possessionChange", possession_change_second)]
    else:
        candidates = [("challenge", challenge_second)]

    reserved_buckets = {round(second, 1) for _, second in base_samples}
    context_samples = _dedupe_sample_times(candidates, clip, reserved_buckets)[: max(0, frames_per_clip - 3)]
    return sorted([*base_samples, *context_samples], key=lambda item: item[1])


def _clamp_sample_times(samples: Sequence[tuple[str, float]], clip: EditCandidateClip) -> List[tuple[str, float]]:
    return [
        (role, round(min(max(second, clip.start), max(clip.start, clip.end - 0.05)), 3))
        for role, second in samples
    ]


def _dedupe_sample_times(
    samples: Sequence[tuple[str, float]],
    clip: EditCandidateClip,
    reserved_buckets: Optional[set[float]] = None,
) -> List[tuple[str, float]]:
    deduped: List[tuple[str, float]] = []
    seen: set[float] = set(reserved_buckets or set())
    for role, second in samples:
        clamped = round(min(max(second, clip.start), max(clip.start, clip.end - 0.05)), 3)
        bucket = round(clamped, 1)
        if bucket in seen:
            continue
        seen.add(bucket)
        deduped.append((role, clamped))
    return deduped


def _extract_jpeg_frame(source_path: Path, frame_path: Path, second: float, settings: GPTHighlightRerankerSettings) -> bool:
    scale = f"scale='min({settings.frame_width},iw)':-2"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{max(0.0, second):.3f}",
        "-i",
        str(source_path),
        "-frames:v",
        "1",
        "-vf",
        scale,
        "-q:v",
        str(settings.jpeg_quality),
        str(frame_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=8)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return frame_path.is_file() and frame_path.stat().st_size > 0


def _build_openai_payload(
    request: CreateEditJobRequest,
    sampled_clips: Sequence[EditCandidateClip],
    sampled_frames: Sequence[SampledFrame],
    settings: GPTHighlightRerankerSettings,
) -> Dict[str, Any]:
    sampled_clips = filter_clips_for_team_selection(sampled_clips, request.teamSelection)
    sampled_clip_ids = {clip.id for clip in sampled_clips}
    candidate_frames = [frame for frame in sampled_frames if frame.clip_id in sampled_clip_ids]
    template = get_template_pack_for_plan(request.preset, request.templateId)
    template_context = {
        "preset": request.preset,
        "templateId": template.templateId,
        "targetDurationSeconds": request.targetDurationSeconds,
        "aspectRatio": request.aspectRatio,
        "planTier": request.planTier,
    }
    user_edit_intent = derive_user_prompt_intent(request.userPrompt, request.planTier)
    if user_edit_intent is not None:
        template_context["userEditIntent"] = user_edit_intent.model_dump(mode="json")
    agent_template_context = build_agent_editing_context(
        template.templateId,
        summarize_clip_pool(sampled_clips),
        sampled_clips,
        teamSelection=request.teamSelection,
    )
    compact_clips = [
        {
            "clipId": clip.id,
            "start": round(clip.start, 3),
            "end": round(clip.end, 3),
            "duration": round(clip.duration, 3),
            "eventCenter": round(clip.eventCenter, 3),
            "existingLabel": clip.label,
            "motionScore": clip.motionScore,
            "audioPeak": clip.audioPeak,
            "confidence": clip.confidence,
            "watchabilityScore": clip.watchability,
            "duplicateGroup": clip.duplicateGroup,
            "userReviewDecision": clip.userReviewDecision,
            "teamAttribution": clip.teamAttribution.model_dump(mode="json") if clip.teamAttribution is not None else None,
            "teamAttributionStatus": team_attribution_status(clip, request.teamSelection),
            "teamEvidence": team_evidence_summary(clip),
            "templateId": template.templateId,
            "planTier": request.planTier,
            "qualityHints": _candidate_quality_hints(clip),
            "nativeShotSignals": native_shot_signals_for_clip(clip).model_dump(mode="json"),
            "outcomeEvidenceSource": clip_outcome_evidence_source(clip),
            "outcomeReliabilityScore": clip_outcome_reliability_score(clip),
            "sampledKeyframes": [
                {"role": frame.role, "time": frame.time_seconds}
                for frame in candidate_frames
                if frame.clip_id == clip.id
            ],
        }
        for clip in sampled_clips
    ]
    content: List[Dict[str, Any]] = [
        {
            "type": "input_text",
            "text": json.dumps(
                {
                    "task": "Rerank existing HoopClips basketball highlight candidates. Use only these clip IDs. Do not invent clips or exact timestamps.",
                    "templateContext": template_context,
                    "agentTemplateCookbook": agent_template_context,
                    "userEditIntent": user_edit_intent.model_dump(mode="json") if user_edit_intent is not None else None,
                    "teamTargeting": request.teamSelection.model_dump(mode="json") if request.teamSelection is not None else {
                        "mode": "all",
                        "teamId": None,
                        "label": None,
                        "colorLabel": None,
                        "confidenceThreshold": 0.85,
                        "includeUncertain": True,
                    },
                    "shotTrackerRules": {
                        "preferCompletePlayContext": True,
                        "rejectTinyClips": True,
                        "rejectPreBasketOnlyClips": True,
                        "treatLabelOnlyOutcomeEvidenceAsUnverified": True,
                        "nonScoringDefensiveOutcomes": ["steal", "forced_turnover", "defensive_stop"],
                        "madeShotRequiresSetupReleaseBallPathRimAndOutcome": True,
                        "madeOrMissedShotRequiresVisibleReleaseAndRimResult": True,
                        "madeOrMissedShotRequiresVisibleShotArc": True,
                        "madeOrMissedShotRequiresVisibleBallPath": True,
                        "defensiveOutcomeRequiresEventOutcomePlayerControlBallAndCleanCamera": True,
                        "defensiveOutcomeUsesPossessionChangeRolesWhenSampled": True,
                        "blockedShotRequiresVisibleChallengeBallPathPlayerControlAndOutcome": True,
                        "madeShotRequiresExplicitMadeResultEvidence": True,
                        "madeShotRequiresFrameRoleTrackingEvidence": True,
                        "madeShotRequiresRimEntrySequenceEvidence": True,
                        "mustUseRichSampledShotRolesWhenPresent": True,
                        "doNotKeepIfOutcomeIsOnlyImplied": True,
                        "netOrRimReactionDoesNotReplaceEntryFrameRoles": True,
                        "requiredMadeShotTracking": {
                            "releaseFrameRole": ["preEvent", "release", "eventCenter"],
                            "resultFrameRole": ["outcome", "shotArcLate", "rimApproach", "rim", "rimEntry", "belowRim", "postOutcome", "finish"],
                            "ballEntersRimFrameRole": ["outcome", "shotArcLate", "rim", "rimEntry", "finish"],
                            "minimumBallVisibleFrameRoles": 2,
                            "trajectoryContinuity": "continuous",
                            "rimEntrySequence": "visible_entry",
                            "ballApproachFrameRole": ["release", "shotArcEarly", "eventCenter", "shotArcLate", "rimApproach"],
                            "rimEntryFrameRole": ["outcome", "shotArcLate", "rim", "rimEntry", "finish"],
                            "ballBelowRimOrNetFrameRole": ["belowRim", "postOutcome", "finish"],
                            "minimumRimEntrySequenceConfidence": 0.72,
                            "dedicatedRimEntryPathRoles": ["rimApproach", "rimEntry", "belowRim"],
                        },
                        "requiredDefensiveTracking": {
                            "eventFrameRoles": ["challenge", "possessionChange", "recovery", "defenseOutcome"],
                            "resultFrameRoles": ["possessionChange", "recovery", "defenseOutcome", "finish"],
                            "mustCitePossessionChangeWhenSampled": True,
                            "mustCiteRecoveryOrOutcomeWhenSampled": True,
                        },
                        "requiredBlockedShotTracking": {
                            "eventFrameRoles": ["challenge", "defenseOutcome"],
                            "resultFrameRoles": ["defenseOutcome", "recovery", "finish"],
                            "mustCiteChallengeWhenSampled": True,
                            "doesNotRequirePossessionChange": True,
                        },
                        "richSampledShotRoleRules": {
                            "ifReleaseRoleIsSampledUseReleaseAsReleaseFrameRole": True,
                            "ifArcRolesAreSampledIncludeAtLeastOneArcRoleInBallVisibleFrameRoles": True,
                            "ifRimOrPostOutcomeIsSampledIncludeOneInRimVisibleFrameRoles": True,
                            "ifOutcomeRimOrPostOutcomeIsSampledUseOneAsResultFrameRole": True,
                            "ifRimApproachIsSampledUseItAsBallApproachFrameRole": True,
                            "ifRimEntryIsSampledUseItAsRimEntryFrameRole": True,
                            "ifRimEntryIsSampledUseItAsBallEntersRimFrameRole": True,
                            "ifBelowRimIsSampledUseItAsBallBelowRimOrNetFrameRole": True,
                        },
                        "requiredShotContextKeyframes": sorted(_required_shot_context_roles(settings.limits_for(request.planTier)[1])),
                    },
                    "clips": compact_clips,
                    "planEdit": "After selecting clips, propose final ordering, pacing, captions, and slow-motion moments as planEdit JSON.",
                },
                separators=(",", ":"),
            ),
        }
    ]
    for frame in candidate_frames:
        content.append({"type": "input_text", "text": f"clipId={frame.clip_id}; frameRole={frame.role}; time={frame.time_seconds}"})
        content.append({"type": "input_image", "image_url": frame.data_url, "detail": settings.image_detail})

    return {
        "model": settings.model,
        "store": False,
        "instructions": (
            "You are HoopClips GPT Highlight Reranker. Judge basketball highlight worthiness, watchability, event clarity, "
            "outcome sanity, boring/duplicate rejection, concise captions, story order, and safe edit suggestions. "
            "Act like a basketball shot-tracker: for made shots, verify visible setup, release, ball path, rim/result, and aftermath. "
            "Treat outcomeEvidenceSource=label_only as unverified until the sampled frames visibly prove the result. "
            "For made or missed shots, releaseVisible, shotArcVisible, and rimResultVisible must all be true; do not infer a make from a label or late rim-only aftermath. "
            "A made outcome requires shotResultEvidence.rimResultEvidence=made_visible with confident visible rim/net proof; use unclear if the result is guessed. "
            "A made outcome also requires shotResultEvidence.rimEntrySequence=visible_entry with approach, rim-entry, and below-rim/net frame roles. "
            "When rimApproach, rimEntry, and belowRim frames are sampled, use those dedicated roles for the made-basket entry path, and cite rimEntry as shotTrackingEvidence.ballEntersRimFrameRole. "
            "A made outcome also requires shotTrackingEvidence with release/result frame roles, ball-visible frame roles, continuous trajectory, and cited entry/follow-through frame roles; net/rim reaction can support evidence but must not replace those frame-role citations. "
            "When sampled roles include release, shot-arc, rim, or post-outcome frames, cite those specific rich roles instead of generic eventCenter/finish proof. "
            "reject clips that start right before the basket, clips shorter than the supplied quality minimum, or clips where the outcome is only implied. "
            "For steals, forced turnovers, or defensive stops, use outcome=steal, outcome=forced_turnover, or outcome=defensive_stop; do not force those plays into unclear or blocked. "
            "For blocks or blocked shots, use outcome=blocked only when the challenge, ball path/control, defender/player control, and blocked-shot outcome are visible; cite sampled challenge/defenseOutcome roles when present. "
            "Non-scoring defensive outcomes must show the defensive event, possession/control change or stop, visible ball/player control, clean camera, and full play context. "
            "When defensive roles like challenge, possessionChange, recovery, or defenseOutcome are sampled, cite those roles in shotTrackingEvidence instead of shot-arc or rim roles. "
            "Honor userEditIntent only when it is compatible with the supplied template, plan tier, candidate clips, and safety constraints. "
            "When a selected team is supplied, keep highlights for that team only; exclude confident opponent clips. Keep uncertain team-attribution clips for user review. "
            "For teamAttributionStatus=uncertain, userReviewDecision=kept is the only signal that the user explicitly promoted the clip for final editing; otherwise treat it as review-only. "
            + TEAM_EVIDENCE_GPT_GUIDANCE
            + "Selected-team blocks, steals, defensive stops, and forced turnovers can be highlights even when they are not scoring plays. "
            "Use only supplied candidate clip IDs and sampled keyframes. Do not replace FFmpeg extraction, CV tracking, rendering, or exact timestamps. "
            "Do not output FFmpeg commands, shell commands, file paths, source video URLs, or storage keys. "
            "Return strict JSON only."
        ),
        "input": [{"role": "user", "content": content}],
        "text": {"format": {"type": "json_schema", "name": "hoopclips_gpt_highlight_rerank", "strict": True, "schema": _response_schema()}},
        "max_output_tokens": settings.max_output_tokens,
    }


def _build_revision_patch_payload(
    job: StoredEditJob,
    revision: ReviseEditJobRequest,
    settings: GPTHighlightRerankerSettings,
) -> Dict[str, Any]:
    template = get_template_pack_for_plan(job.request.preset, job.plan.templateId or job.request.templateId)
    source_clips = filter_clips_for_team_selection(
        job.request.clips,
        job.request.teamSelection,
        include_review_only_uncertain=False,
    )
    agent_template_context = build_agent_editing_context(
        template.templateId,
        summarize_clip_pool(source_clips),
        source_clips,
        teamSelection=job.request.teamSelection,
    )
    team_targeting = job.request.teamSelection.model_dump(mode="json") if job.request.teamSelection is not None else {
        "mode": "all",
        "teamId": None,
        "label": None,
        "colorLabel": None,
        "confidenceThreshold": 0.85,
        "includeUncertain": True,
    }
    compact_context = {
        "task": "Create an EditPlanPatch JSON for this HoopClips revision command. Use only existing clip IDs and safe patch paths.",
        "revision": {
            "command": revision.command,
            "freeText": revision.freeText,
            "targetDurationSeconds": revision.targetDurationSeconds,
            "aspectRatio": revision.aspectRatio,
        },
        "planTier": job.request.planTier,
        "templateId": template.templateId,
        "teamTargeting": team_targeting,
        "agentTemplateCookbook": agent_template_context,
        "currentPlan": job.plan.model_dump(mode="json"),
        "candidateClips": [
            {
                "clipId": clip.id,
                "start": round(clip.start, 3),
                "end": round(clip.end, 3),
                "eventCenter": round(clip.eventCenter, 3),
                "label": clip.label,
                "confidence": clip.confidence,
                "motionScore": clip.motionScore,
                "watchabilityScore": clip.watchability,
                "duplicateGroup": clip.duplicateGroup,
                "teamAttribution": clip.teamAttribution.model_dump(mode="json") if clip.teamAttribution is not None else None,
                "teamAttributionStatus": team_attribution_status(clip, job.request.teamSelection),
                "teamEvidence": team_evidence_summary(clip),
                "nativeShotSignals": native_shot_signals_for_clip(clip).model_dump(mode="json"),
            }
            for clip in source_clips
        ],
    }
    return {
        "model": settings.model,
        "store": False,
        "instructions": (
            "You are HoopClips GPT Edit Cool. Return an EditPlanPatch JSON only. "
            "Do not output free-form prose. Do not generate FFmpeg commands, shell commands, render instructions, file paths, URLs, or storage keys. "
            + TEAM_EVIDENCE_GPT_GUIDANCE
            + "Use only provided render-eligible clip IDs and safe patch paths; the backend will validate and repair before rendering."
        ),
        "input": [{"role": "user", "content": [{"type": "input_text", "text": json.dumps(compact_context, separators=(",", ":"))}]}],
        "text": {"format": {"type": "json_schema", "name": "hoopclips_gpt_edit_plan_patch", "strict": True, "schema": _edit_plan_patch_schema()}},
        "max_output_tokens": min(settings.max_output_tokens, 3000),
    }


def _response_schema() -> Dict[str, Any]:
    frame_role_enum = [
        "start",
        "preEvent",
        "release",
        "shotArcEarly",
        "eventCenter",
        "outcome",
        "shotArcLate",
        "rimApproach",
        "rim",
        "rimEntry",
        "belowRim",
        "postOutcome",
        "finish",
        "midAction",
        "defenseSetup",
        "challenge",
        "possessionChange",
        "recovery",
        "defenseOutcome",
    ]
    frame_role_or_null = {"anyOf": [{"type": "string", "enum": frame_role_enum}, {"type": "null"}]}
    quality_signals = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "setupVisible": {"type": "boolean"},
            "releaseVisible": {"type": "boolean"},
            "shotArcVisible": {"type": "boolean"},
            "eventVisible": {"type": "boolean"},
            "outcomeVisible": {"type": "boolean"},
            "rimResultVisible": {"type": "boolean"},
            "ballPathVisible": {"type": "boolean"},
            "playerControlVisible": {"type": "boolean"},
            "cleanCamera": {"type": "boolean"},
            "fullPlayContext": {"type": "boolean"},
            "reason": {"type": "string", "maxLength": 160},
        },
        "required": [
            "setupVisible",
            "releaseVisible",
            "shotArcVisible",
            "eventVisible",
            "outcomeVisible",
            "rimResultVisible",
            "ballPathVisible",
            "playerControlVisible",
            "cleanCamera",
            "fullPlayContext",
            "reason",
        ],
    }
    shot_result_evidence = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "releaseToRimContinuity": {"type": "string", "enum": ["continuous", "partial", "missing"]},
            "rimResultEvidence": {"type": "string", "enum": ["made_visible", "clear_miss", "blocked", "unclear"]},
            "outcomeConfidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rimEntrySequence": {"type": "string", "enum": ["visible_entry", "visible_miss", "blocked", "unclear"]},
            "ballApproachFrameRole": frame_role_or_null,
            "rimEntryFrameRole": frame_role_or_null,
            "ballBelowRimOrNetFrameRole": frame_role_or_null,
            "rimEntrySequenceConfidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string", "maxLength": 160},
        },
        "required": [
            "releaseToRimContinuity",
            "rimResultEvidence",
            "outcomeConfidence",
            "rimEntrySequence",
            "ballApproachFrameRole",
            "rimEntryFrameRole",
            "ballBelowRimOrNetFrameRole",
            "rimEntrySequenceConfidence",
            "reason",
        ],
    }
    shot_tracking_evidence = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ballVisibleFrameRoles": {"type": "array", "items": {"type": "string", "enum": frame_role_enum}, "maxItems": 10},
            "rimVisibleFrameRoles": {"type": "array", "items": {"type": "string", "enum": frame_role_enum}, "maxItems": 10},
            "releaseFrameRole": frame_role_or_null,
            "resultFrameRole": frame_role_or_null,
            "ballEntersRimFrameRole": frame_role_or_null,
            "netOrRimReactionVisible": {"type": "boolean"},
            "trajectoryContinuity": {"type": "string", "enum": ["continuous", "partial", "missing"]},
            "reason": {"type": "string", "maxLength": 180},
        },
        "required": [
            "ballVisibleFrameRoles",
            "rimVisibleFrameRoles",
            "releaseFrameRole",
            "resultFrameRole",
            "ballEntersRimFrameRole",
            "netOrRimReactionVisible",
            "trajectoryContinuity",
            "reason",
        ],
    }
    suggested_edit = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "slowMotion": {"type": "boolean"},
            "slowMotionCenter": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "captionMoment": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "cropFocus": {"type": "string", "enum": ["center_action", "ball", "rim", "shooter", "team", "source"]},
            "extendBeforeSeconds": {"type": "number", "minimum": 0, "maximum": 3},
            "extendAfterSeconds": {"type": "number", "minimum": 0, "maximum": 3},
        },
        "required": ["slowMotion", "slowMotionCenter", "captionMoment", "cropFocus", "extendBeforeSeconds", "extendAfterSeconds"],
    }
    decision = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "clipId": {"type": "string"},
            "keep": {"type": "boolean"},
            "rejectReason": {"anyOf": [{"type": "string", "maxLength": 160}, {"type": "null"}]},
            "highlightScore": {"type": "number", "minimum": 0, "maximum": 1},
            "watchabilityScore": {"type": "number", "minimum": 0, "maximum": 1},
            "basketballEvent": {"type": "string"},
            "outcome": {"type": "string", "enum": ["made", "missed", "blocked", "steal", "forced_turnover", "defensive_stop", "unclear", "not_basketball"]},
            "caption": {"type": "string", "maxLength": 24},
            "reason": {"type": "string"},
            "storyRole": {"type": "string", "enum": ["opener", "peak", "filler", "closer"]},
            "qualitySignals": quality_signals,
            "shotResultEvidence": shot_result_evidence,
            "shotTrackingEvidence": shot_tracking_evidence,
            "suggestedEdit": suggested_edit,
        },
        "required": [
            "clipId",
            "keep",
            "rejectReason",
            "highlightScore",
            "watchabilityScore",
            "basketballEvent",
            "outcome",
            "caption",
            "reason",
            "storyRole",
            "qualitySignals",
            "shotResultEvidence",
            "shotTrackingEvidence",
            "suggestedEdit",
        ],
    }
    plan_edit = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "orderedClipIds": {"type": "array", "items": {"type": "string"}, "maxItems": GPT_CANDIDATE_REVIEW_LIMIT},
            "pacing": {"type": "string", "enum": ["fast", "balanced", "cinematic", "chronological", "coach_review"]},
            "captions": {
                "type": "array",
                "maxItems": GPT_CANDIDATE_REVIEW_LIMIT,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "clipId": {"type": "string"},
                        "caption": {"type": "string", "maxLength": 24},
                        "captionMoment": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                    },
                    "required": ["clipId", "caption", "captionMoment"],
                },
            },
            "slowMotionMoments": {
                "type": "array",
                "maxItems": GPT_CANDIDATE_REVIEW_LIMIT,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "clipId": {"type": "string"},
                        "center": {"type": "number"},
                        "speed": {"type": "number", "minimum": 0.5, "maximum": 1},
                    },
                    "required": ["clipId", "center", "speed"],
                },
            },
            "summary": {"anyOf": [{"type": "string", "maxLength": 240}, {"type": "null"}]},
        },
        "required": ["orderedClipIds", "pacing", "captions", "slowMotionMoments", "summary"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "decisions": {"type": "array", "items": decision},
            "storyOrder": {"type": "array", "items": {"type": "string"}},
            "planEdit": plan_edit,
            "summary": {"type": "string"},
        },
        "required": ["decisions", "storyOrder", "planEdit", "summary"],
    }


def _json_value_schema() -> Dict[str, Any]:
    nullable_number = {"anyOf": [{"type": "number"}, {"type": "null"}]}
    nullable_string = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    edit_plan_effect = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "type": {"type": "string"},
            "at": nullable_number,
            "sourceStart": nullable_number,
            "sourceEnd": nullable_number,
            "speed": nullable_number,
            "strength": nullable_number,
        },
        "required": ["type", "at", "sourceStart", "sourceEnd", "speed", "strength"],
    }
    edit_plan_clip = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "clipId": {"type": "string"},
            "sourceStart": {"type": "number"},
            "sourceEnd": {"type": "number"},
            "eventCenter": {"type": "number"},
            "timelineStart": {"type": "number"},
            "timelineEnd": {"type": "number"},
            "label": {"type": "string"},
            "caption": {"type": "string", "maxLength": 24},
            "captionMoment": nullable_number,
            "cropMode": {"type": "string"},
            "effects": {"type": "array", "items": edit_plan_effect},
        },
        "required": [
            "clipId",
            "sourceStart",
            "sourceEnd",
            "eventCenter",
            "timelineStart",
            "timelineEnd",
            "label",
            "caption",
            "captionMoment",
            "cropMode",
            "effects",
        ],
    }
    edit_plan_audio = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "mode": {"type": "string"},
            "musicTrackId": {"type": "string"},
            "musicVolume": {"type": "number"},
            "gameAudioVolume": {"type": "number"},
        },
        "required": ["mode", "musicTrackId", "musicVolume", "gameAudioVolume"],
    }
    timed_template = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "enabled": {"type": "boolean"},
            "durationSeconds": {"type": "number"},
            "templateId": {"type": "string"},
            "assetId": nullable_string,
        },
        "required": ["enabled", "durationSeconds", "templateId", "assetId"],
    }
    edit_plan_watermark = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "enabled": {"type": "boolean"},
            "position": {"type": "string"},
            "assetId": nullable_string,
        },
        "required": ["enabled", "position", "assetId"],
    }
    return {
        "anyOf": [
            {"type": "string"},
            {"type": "number"},
            {"type": "integer"},
            {"type": "boolean"},
            {"type": "null"},
            edit_plan_audio,
            {"type": "array", "items": edit_plan_clip, "maxItems": 80},
            timed_template,
            edit_plan_watermark,
        ]
    }


def _edit_plan_patch_schema() -> Dict[str, Any]:
    operation = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "op": {"type": "string", "enum": ["add", "remove", "replace"]},
            "path": {
                "type": "string",
                "enum": [
                    "/targetDurationSeconds",
                    "/aspectRatio",
                    "/preset",
                    "/templateId",
                    "/theme",
                    "/captionStyle",
                    "/audio",
                    "/clips",
                    "/intro",
                    "/outro",
                    "/watermark",
                ],
            },
            "value": _json_value_schema(),
            "reason": {"anyOf": [{"type": "string", "maxLength": 160}, {"type": "null"}]},
        },
        "required": ["op", "path", "value", "reason"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "version": {"type": "string", "enum": ["edit-plan-patch-v1"]},
            "baseEditPlanId": {"type": "string"},
            "revisionIntent": {
                "type": "string",
                "enum": [
                    "make_shorter",
                    "make_longer",
                    "make_more_hype",
                    "make_nba_style",
                    "make_personal",
                    "remove_weak_clips",
                    "add_more_slow_motion",
                    "use_original_audio",
                    "switch_format_vertical",
                    "switch_format_widescreen",
                    "export_vertical",
                    "export_widescreen",
                    "reduce_captions",
                    "show_more_full_play_context",
                ],
            },
            "summary": {"type": "string", "maxLength": 320},
            "operations": {"type": "array", "items": operation, "maxItems": 80},
            "requiresRerender": {"type": "boolean"},
        },
        "required": ["version", "baseEditPlanId", "revisionIntent", "summary", "operations", "requiresRerender"],
    }


def _default_responses_client(payload: Dict[str, Any], api_key: str, endpoint: str, timeout_seconds: float) -> Dict[str, Any]:
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "HoopClipsGPTVideoReranker/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_output_text(response_payload: Dict[str, Any]) -> str:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    for item in response_payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            refusal = content.get("refusal")
            if isinstance(refusal, str) and refusal:
                raise ValueError("model_refusal")
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text
    raise ValueError("missing_output_text")


def _env_flag(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


def _env_image_detail(name: str, default: str) -> str:
    value = os.getenv(name, default).strip().lower() or default
    return value if value in ALLOWED_IMAGE_DETAIL_LEVELS else default


def _safe_id(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)[:80]
