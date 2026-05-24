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
    EditPlanPatch,
    EditCandidateClip,
    GPTHighlightClipDecision,
    GPTPlanEdit,
    GPTHighlightRerankSummary,
    ReviseEditJobRequest,
    StoredEditJob,
    apply_gpt_highlight_rerank,
    build_agent_editing_context,
    derive_user_prompt_intent,
    get_template_pack_for_plan,
    rank_clips,
    summarize_clip_pool,
    validate_edit_plan_patch,
)


ResponseClient = Callable[[Dict[str, Any], str, str, float], Dict[str, Any]]
ALLOWED_IMAGE_DETAIL_LEVELS = {"low", "high", "original", "auto"}
REQUIRED_KEYFRAME_ROLES = {"start", "eventCenter", "finish"}


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
            model=os.getenv("HOOPS_AI_CLIP_GPT_MODEL", os.getenv("HOOPS_GPT_HIGHLIGHT_RERANK_MODEL", "gpt-4.1-mini")),
            endpoint=os.getenv("HOOPS_AI_CLIP_GPT_ENDPOINT", os.getenv("HOOPS_GPT_HIGHLIGHT_RERANK_ENDPOINT", "https://api.openai.com/v1/responses")),
            timeout_seconds=_env_float("HOOPS_AI_CLIP_GPT_TIMEOUT_SECONDS", _env_float("HOOPS_GPT_HIGHLIGHT_RERANK_TIMEOUT_SECONDS", 18.0, 1.0, 60.0), 1.0, 60.0),
            max_output_tokens=_env_int("HOOPS_AI_CLIP_GPT_MAX_OUTPUT_TOKENS", _env_int("HOOPS_GPT_HIGHLIGHT_RERANK_MAX_OUTPUT_TOKENS", 2200, 256, 6000), 256, 6000),
            free_max_clips=_env_int("HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE", _env_int("HOOPS_GPT_HIGHLIGHT_RERANK_FREE_MAX_CLIPS", 8, 1, 8), 1, 8),
            paid_max_clips=_env_int("HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO", _env_int("HOOPS_GPT_HIGHLIGHT_RERANK_PAID_MAX_CLIPS", 24, 20, 30), 20, 30),
            free_frames_per_clip=_env_int("HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP", _env_int("HOOPS_GPT_HIGHLIGHT_RERANK_FREE_FRAMES_PER_CLIP", 3, 3, 3), 3, 8),
            paid_frames_per_clip=_env_int("HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP", _env_int("HOOPS_GPT_HIGHLIGHT_RERANK_PAID_FRAMES_PER_CLIP", 5, 5, 8), 3, 8),
            frame_width=_env_int("HOOPS_GPT_HIGHLIGHT_RERANK_FRAME_WIDTH", 512, 256, 768),
            jpeg_quality=_env_int("HOOPS_GPT_HIGHLIGHT_RERANK_JPEG_QUALITY", 5, 2, 12),
            max_image_bytes=_env_int("HOOPS_GPT_HIGHLIGHT_RERANK_MAX_IMAGE_BYTES", 180_000, 40_000, 500_000),
            image_detail=_env_image_detail("HOOPS_AI_CLIP_GPT_IMAGE_DETAIL", _env_image_detail("HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL", "low")),
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

    max_clips, frames_per_clip = settings.limits_for(request.planTier)
    sampled_clips = rank_clips(request.clips)[:max_clips]
    sampled_frames = _extract_candidate_keyframes(source_path, sampled_clips, frames_per_clip, settings)
    if not sampled_frames:
        return _with_fallback(request, "fallback", settings.model, "keyframe_extraction_failed", len(sampled_clips), 0)
    if _missing_required_keyframes(sampled_clips, sampled_frames):
        return _with_fallback(request, "fallback", settings.model, "keyframe_extraction_incomplete", len(sampled_clips), len(sampled_frames))

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

    return apply_gpt_highlight_rerank(
        request,
        decisions,
        model=settings.model,
        sampled_clip_count=len(sampled_clips),
        sampled_frame_count=len(sampled_frames),
        story_order=story_order,
        plan_edit=plan_edit,
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
        patched_plan, errors = validate_edit_plan_patch(job.plan, patch, job.request.clips, job.request.planTier)
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
    summary = GPTHighlightRerankSummary(
        status=status if status in {"disabled", "fallback"} else "fallback",
        model=model,
        sampledClipCount=sampled_clip_count,
        sampledFrameCount=sampled_frame_count,
        fallbackReason=reason,
    )
    return request.model_copy(update={"gptRerankSummary": summary})


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


def _sample_times_for_clip(clip: EditCandidateClip, frames_per_clip: int) -> List[tuple[str, float]]:
    finish = max(clip.start, clip.end - 0.05)
    base = [("start", clip.start), ("eventCenter", clip.eventCenter), ("finish", finish)]
    base_samples = _clamp_sample_times(base, clip)
    if frames_per_clip <= 3:
        return base_samples

    duration = max(0.001, finish - clip.start)
    extra_count = max(0, frames_per_clip - 3)
    extras = []
    for index in range(extra_count):
        fraction = (index + 1) / (extra_count + 1)
        second = clip.start + (duration * fraction)
        if abs(second - clip.eventCenter) < 0.2:
            continue
        role = "action" if index == 0 else "rim" if index == 1 else f"context_{index + 1}"
        extras.append((role, second))
    reserved_buckets = {round(second, 1) for _, second in base_samples}
    context_samples = _dedupe_sample_times(extras, clip, reserved_buckets)
    return [base_samples[0], *context_samples, base_samples[1], base_samples[2]][:frames_per_clip]


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
            "templateId": template.templateId,
            "planTier": request.planTier,
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
            "Honor userEditIntent only when it is compatible with the supplied template, plan tier, candidate clips, and safety constraints. "
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
    agent_template_context = build_agent_editing_context(
        template.templateId,
        summarize_clip_pool(job.request.clips),
        job.request.clips,
    )
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
            }
            for clip in job.request.clips
        ],
    }
    return {
        "model": settings.model,
        "store": False,
        "instructions": (
            "You are HoopClips GPT Edit Cool. Return an EditPlanPatch JSON only. "
            "Do not output free-form prose. Do not generate FFmpeg commands, shell commands, render instructions, file paths, URLs, or storage keys. "
            "Use only provided clip IDs and safe patch paths; the backend will validate and repair before rendering."
        ),
        "input": [{"role": "user", "content": [{"type": "input_text", "text": json.dumps(compact_context, separators=(",", ":"))}]}],
        "text": {"format": {"type": "json_schema", "name": "hoopclips_gpt_edit_plan_patch", "strict": True, "schema": _edit_plan_patch_schema()}},
        "max_output_tokens": min(settings.max_output_tokens, 3000),
    }


def _response_schema() -> Dict[str, Any]:
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
            "outcome": {"type": "string", "enum": ["made", "missed", "blocked", "unclear", "not_basketball"]},
            "caption": {"type": "string", "maxLength": 24},
            "reason": {"type": "string"},
            "storyRole": {"type": "string", "enum": ["opener", "peak", "filler", "closer"]},
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
            "suggestedEdit",
        ],
    }
    plan_edit = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "orderedClipIds": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
            "pacing": {"type": "string", "enum": ["fast", "balanced", "cinematic", "chronological", "coach_review"]},
            "captions": {
                "type": "array",
                "maxItems": 30,
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
                "maxItems": 30,
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
