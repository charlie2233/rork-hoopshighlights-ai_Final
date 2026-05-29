from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .backend_imports import ensure_ios_backend_on_path

ensure_ios_backend_on_path()

from app.editing import (  # noqa: E402
    CreateEditJobRequest,
    EditCandidateClip,
    EditPlan,
    EditPlanValidationIssue,
    EditRevisionResponse,
    GPT_CANDIDATE_REVIEW_LIMIT,
    GPTHighlightRerankSummary,
    MIN_PLAN_CLIP_SECONDS,
    PlanTier,
    get_plan_tier_policy,
    get_template_pack,
    is_shot_like_clip,
    native_shot_signals_for_clip,
    policy_summary_for_client,
)


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


RenderStatus = Literal["render_requested", "created", "queued", "rendering", "rendered", "failed", "failed_timeout", "cancelled"]
AIWorkStepStatus = Literal["pending", "running", "complete", "failed"]
MIN_RECEIPT_DEFENSIVE_LEAD_IN_SECONDS = 0.6
MIN_RECEIPT_DEFENSIVE_FOLLOW_THROUGH_SECONDS = 0.5


class CreateRenderJobRequest(APIModel):
    editJobId: str = Field(min_length=1, max_length=128)
    revisionId: Optional[str] = Field(default=None, min_length=1, max_length=128)
    installId: str = Field(min_length=8, max_length=128)
    sourceObjectKey: str = Field(min_length=1, max_length=512)
    planTier: PlanTier = "free"
    revenueCatAppUserID: Optional[str] = Field(default=None, min_length=1, max_length=160)
    editPlan: EditPlan
    sourceClips: List[EditCandidateClip] = Field(default_factory=list, max_length=GPT_CANDIDATE_REVIEW_LIMIT)
    gptRerankSummary: Optional[GPTHighlightRerankSummary] = None
    idempotencyKey: Optional[str] = Field(default=None, min_length=8, max_length=160)


class StartEditJobRenderRequest(APIModel):
    installId: str = Field(min_length=8, max_length=128)
    sourceObjectKey: Optional[str] = Field(default=None, min_length=1, max_length=512)
    planTier: Optional[PlanTier] = None
    revenueCatAppUserID: Optional[str] = Field(default=None, min_length=1, max_length=160)
    editPlan: Optional[EditPlan] = None
    sourceClips: List[EditCandidateClip] = Field(default_factory=list, max_length=GPT_CANDIDATE_REVIEW_LIMIT)
    idempotencyKey: Optional[str] = Field(default=None, min_length=8, max_length=160)
    forceNew: bool = False


class StartEditRevisionRenderRequest(APIModel):
    installId: str = Field(min_length=8, max_length=128)
    idempotencyKey: Optional[str] = Field(default=None, min_length=8, max_length=160)


class AIWorkStep(APIModel):
    stepId: str
    title: str
    detail: Optional[str] = None
    status: AIWorkStepStatus
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None


class AIWorkTimeline(APIModel):
    editJobId: str
    revisionId: Optional[str] = None
    renderJobId: Optional[str] = None
    status: RenderStatus
    generatedAt: datetime
    steps: List[AIWorkStep]


class AIWorkReceipt(APIModel):
    editJobId: str
    revisionId: Optional[str] = None
    renderJobId: Optional[str] = None
    selectedClipCount: Optional[int] = None
    candidateClipCount: Optional[int] = None
    templateId: Optional[str] = None
    templateName: Optional[str] = None
    slowMotionMomentCount: int = 0
    outputDurationSeconds: Optional[float] = None
    outputResolution: Optional[str] = None
    aspectRatio: Optional[str] = None
    watermarkIncluded: Optional[bool] = None
    outroIncluded: Optional[bool] = None
    storageExpiresAt: Optional[datetime] = None
    planTier: PlanTier = "free"
    priorityQueue: bool = False
    gptRerankApplied: bool = False
    gptRerankModel: Optional[str] = None
    gptRerankSampledClipCount: Optional[int] = None
    gptRerankSampledFrameCount: Optional[int] = None
    gptRerankKeptClipCount: Optional[int] = None
    gptRerankRejectedClipCount: Optional[int] = None
    gptUncertainReviewClipCount: Optional[int] = None
    gptUncertainReviewClipIds: List[str] = Field(default_factory=list)
    gptRerankRejectedReasonCounts: Dict[str, int] = Field(default_factory=dict)
    gptRerankStoryOrderClipIds: List[str] = Field(default_factory=list)
    gptPlanEditApplied: bool = False
    gptRerankFallbackReason: Optional[str] = None
    teamUncertainCandidateCount: Optional[int] = None
    teamUncertainSelectedClipCount: Optional[int] = None
    defensiveSelectedClipCount: Optional[int] = None
    timingQualitySelectedClipCount: Optional[int] = None
    timingIssueCandidateCount: Optional[int] = None
    timingIssueSelectedClipCount: Optional[int] = None
    shotOutcomeEvidenceSelectedClipCount: Optional[int] = None
    shotOutcomeIssueSelectedClipCount: Optional[int] = None
    labelOnlyOutcomeSelectedClipCount: Optional[int] = None
    summaryRows: List[str] = Field(default_factory=list)


class RenderJobResponse(APIModel):
    editJobId: str
    revisionId: Optional[str] = None
    renderJobId: str
    renderer: str
    rendererVersion: str
    planVersion: Optional[str] = None
    templateId: Optional[str] = None
    status: RenderStatus
    outputObjectKey: Optional[str] = None
    renderLogObjectKey: Optional[str] = None
    durationSeconds: Optional[float] = None
    aspectRatio: str
    traceId: str
    failureReason: Optional[str] = None
    validationErrors: List[EditPlanValidationIssue] = Field(default_factory=list)
    planTier: PlanTier = "free"
    policy: Dict[str, Any] = Field(default_factory=dict)
    retryCount: int = 0
    outputBytes: Optional[int] = None
    retentionMetadata: Optional[Dict[str, Any]] = None
    workTimeline: Optional[AIWorkTimeline] = None
    workReceipt: Optional[AIWorkReceipt] = None


class DownloadUrlResponse(APIModel):
    editJobId: str
    renderJobId: str
    downloadUrl: str
    outputObjectKey: str
    contentType: str = "video/mp4"
    expiresAt: datetime


class RenderJobListResponse(APIModel):
    installId: str
    generatedAt: datetime
    renders: List[RenderJobResponse] = Field(default_factory=list)


class ErrorResponse(APIModel):
    errorCode: str
    errorMessage: str
    failureReason: Optional[str] = None


class EditRevisionListResponse(APIModel):
    editJobId: str
    revisions: List[EditRevisionResponse] = Field(default_factory=list)


@dataclass
class StoredRenderJob:
    edit_job_id: str
    render_job_id: str
    install_id: str
    trace_id: str
    status: RenderStatus
    aspect_ratio: str
    created_at: datetime
    updated_at: datetime
    output_object_key: Optional[str] = None
    render_log_object_key: Optional[str] = None
    source_object_key: Optional[str] = None
    plan_version: Optional[str] = None
    template_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    failure_reason: Optional[str] = None
    validation_errors: List[EditPlanValidationIssue] = field(default_factory=list)
    plan_tier: PlanTier = "free"
    retry_count: int = 0
    idempotency_key: Optional[str] = None
    output_bytes: Optional[int] = None
    retention_metadata: Optional[Dict[str, Any]] = None
    revision_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    renderer_version: str = "ffmpeg-renderer-v1"
    lease_owner: Optional[str] = None
    lease_token: Optional[str] = None
    lease_acquired_at: Optional[datetime] = None
    lease_expires_at: Optional[datetime] = None
    heartbeat_at: Optional[datetime] = None

    def to_response(
        self,
        work_timeline: Optional[AIWorkTimeline] = None,
        work_receipt: Optional[AIWorkReceipt] = None,
    ) -> RenderJobResponse:
        return RenderJobResponse(
            editJobId=self.edit_job_id,
            revisionId=self.revision_id,
            renderJobId=self.render_job_id,
            renderer="cloud_ffmpeg",
            rendererVersion=self.renderer_version,
            planVersion=self.plan_version,
            templateId=self.template_id,
            status=self.status,
            outputObjectKey=self.output_object_key,
            renderLogObjectKey=self.render_log_object_key,
            durationSeconds=self.duration_seconds,
            aspectRatio=self.aspect_ratio,
            traceId=self.trace_id,
            failureReason=self.failure_reason,
            validationErrors=self.validation_errors,
            planTier=self.plan_tier,
            policy=policy_summary_for_client(self.plan_tier),
            retryCount=self.retry_count,
            outputBytes=self.output_bytes,
            retentionMetadata=self.retention_metadata,
            workTimeline=work_timeline,
            workReceipt=work_receipt,
        )

    def to_durable_dict(self) -> Dict[str, Any]:
        return {
            "version": "render-state-v1",
            "editJobId": self.edit_job_id,
            "revisionId": self.revision_id,
            "renderJobId": self.render_job_id,
            "installId": self.install_id,
            "traceId": self.trace_id,
            "status": self.status,
            "planVersion": self.plan_version,
            "templateId": self.template_id,
            "planTier": self.plan_tier,
            "sourceObjectKey": self.source_object_key,
            "outputObjectKey": self.output_object_key,
            "renderLogObjectKey": self.render_log_object_key,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "expiresAt": self.expires_at.isoformat() if self.expires_at else None,
            "failureReason": self.failure_reason,
            "retryCount": self.retry_count,
            "idempotencyKey": self.idempotency_key,
            "rendererVersion": self.renderer_version,
            "outputBytes": self.output_bytes,
            "durationSeconds": self.duration_seconds,
            "aspectRatio": self.aspect_ratio,
            "retentionMetadata": self.retention_metadata,
            "validationErrors": [error.model_dump() for error in self.validation_errors],
            "leaseOwner": self.lease_owner,
            "leaseToken": self.lease_token,
            "leaseAcquiredAt": self.lease_acquired_at.isoformat() if self.lease_acquired_at else None,
            "leaseExpiresAt": self.lease_expires_at.isoformat() if self.lease_expires_at else None,
            "heartbeatAt": self.heartbeat_at.isoformat() if self.heartbeat_at else None,
        }

    @classmethod
    def from_durable_dict(cls, payload: Dict[str, Any]) -> "StoredRenderJob":
        return cls(
            edit_job_id=str(payload["editJobId"]),
            render_job_id=str(payload["renderJobId"]),
            install_id=str(payload["installId"]),
            trace_id=str(payload["traceId"]),
            status=payload.get("status", "failed"),
            aspect_ratio=str(payload.get("aspectRatio") or "9:16"),
            created_at=parse_datetime(payload.get("createdAt")) or now_utc(),
            updated_at=parse_datetime(payload.get("updatedAt")) or now_utc(),
            output_object_key=payload.get("outputObjectKey"),
            render_log_object_key=payload.get("renderLogObjectKey"),
            source_object_key=payload.get("sourceObjectKey"),
            plan_version=payload.get("planVersion"),
            template_id=payload.get("templateId"),
            duration_seconds=payload.get("durationSeconds"),
            failure_reason=payload.get("failureReason"),
            validation_errors=[EditPlanValidationIssue(**error) for error in payload.get("validationErrors", [])],
            plan_tier=payload.get("planTier", "free"),
            retry_count=int(payload.get("retryCount") or 0),
            idempotency_key=payload.get("idempotencyKey"),
            output_bytes=payload.get("outputBytes"),
            retention_metadata=payload.get("retentionMetadata"),
            revision_id=payload.get("revisionId"),
            started_at=parse_datetime(payload.get("startedAt")),
            completed_at=parse_datetime(payload.get("completedAt")),
            expires_at=parse_datetime(payload.get("expiresAt")),
            renderer_version=str(payload.get("rendererVersion") or "ffmpeg-renderer-v1"),
            lease_owner=payload.get("leaseOwner"),
            lease_token=payload.get("leaseToken"),
            lease_acquired_at=parse_datetime(payload.get("leaseAcquiredAt")),
            lease_expires_at=parse_datetime(payload.get("leaseExpiresAt")),
            heartbeat_at=parse_datetime(payload.get("heartbeatAt")),
        )


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def parse_datetime(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _clip_count_label(count: Optional[int], singular: str, plural: str) -> Optional[str]:
    if count is None:
        return None
    return f"{count} {singular if count == 1 else plural}"


def _slow_motion_moment_count(edit_plan: Optional[EditPlan]) -> int:
    if edit_plan is None:
        return 0
    return sum(1 for clip in edit_plan.clips for effect in clip.effects if effect.type == "slow_motion")


def _duplicate_group_count(source_clips: Optional[List[EditCandidateClip]]) -> Optional[int]:
    if source_clips is None:
        return None
    return len({clip.duplicateGroup for clip in source_clips if clip.duplicateGroup})


def _team_uncertain_clip_ids(source_clips: Optional[List[EditCandidateClip]]) -> set[str]:
    if source_clips is None:
        return set()
    return {
        clip.id
        for clip in source_clips
        if clip.teamAttributionStatus == "uncertain"
        or (clip.teamAttribution is not None and clip.teamAttribution.confidence < 0.85)
    }


def _defensive_clip_ids(source_clips: Optional[List[EditCandidateClip]]) -> set[str]:
    if source_clips is None:
        return set()
    defensive_tokens = {
        "block",
        "blocked",
        "steal",
        "strip",
        "turnover",
        "forced",
        "defense",
        "defensive",
        "stop",
        "pressure",
        "lockdown",
    }
    return {
        clip.id
        for clip in source_clips
        if any(token in clip.label.strip().lower() for token in defensive_tokens)
    }


def _timing_issue_clip_ids(source_clips: Optional[List[EditCandidateClip]]) -> set[str]:
    if source_clips is None:
        return set()
    defensive_ids = _defensive_clip_ids(source_clips)
    issue_ids: set[str] = set()
    for clip in source_clips:
        if clip.duration < MIN_PLAN_CLIP_SECONDS:
            issue_ids.add(clip.id)
            continue
        if clip.id in defensive_ids:
            lead_in = max(0.0, clip.eventCenter - clip.start)
            follow_through = max(0.0, clip.end - clip.eventCenter)
            if lead_in < MIN_RECEIPT_DEFENSIVE_LEAD_IN_SECONDS or follow_through < MIN_RECEIPT_DEFENSIVE_FOLLOW_THROUGH_SECONDS:
                issue_ids.add(clip.id)
            continue
        if is_shot_like_clip(clip) and not native_shot_signals_for_clip(clip).timingWindowOk:
            issue_ids.add(clip.id)
    return issue_ids


def _shot_outcome_evidence_clip_ids(source_clips: Optional[List[EditCandidateClip]]) -> set[str]:
    if source_clips is None:
        return set()
    evidence_sources = {"gpt_shot_tracking", "gpt_defensive_tracking", "native_shot_signals", "defensive_event"}
    evidence_ids: set[str] = set()
    for clip in source_clips:
        signals = native_shot_signals_for_clip(clip)
        if signals.outcome not in {"made", "missed", "blocked"}:
            continue
        if signals.outcomeEvidenceSource in evidence_sources and signals.outcomeReliabilityScore >= 0.72:
            evidence_ids.add(clip.id)
    return evidence_ids


def _shot_outcome_issue_clip_ids(source_clips: Optional[List[EditCandidateClip]]) -> set[str]:
    if source_clips is None:
        return set()
    issue_ids: set[str] = set()
    for clip in source_clips:
        signals = native_shot_signals_for_clip(clip)
        if signals.outcome not in {"made", "missed", "blocked"}:
            continue
        if signals.outcomeEvidenceSource == "label_only" or signals.outcomeReliabilityScore < 0.72:
            issue_ids.add(clip.id)
    return issue_ids


def _label_only_outcome_clip_ids(source_clips: Optional[List[EditCandidateClip]]) -> set[str]:
    if source_clips is None:
        return set()
    return {
        clip.id
        for clip in source_clips
        if native_shot_signals_for_clip(clip).outcomeEvidenceSource == "label_only"
        and native_shot_signals_for_clip(clip).outcome in {"made", "missed", "blocked"}
    }


def _step_status_for_render(render_status: RenderStatus) -> AIWorkStepStatus:
    if render_status == "rendered":
        return "complete"
    if render_status in {"failed", "failed_timeout", "cancelled"}:
        return "failed"
    return "running"


def _finalize_status_for_render(render_job: StoredRenderJob) -> AIWorkStepStatus:
    if render_job.status == "rendered" and render_job.output_object_key:
        return "complete"
    if render_job.status in {"failed", "failed_timeout", "cancelled"}:
        return "failed"
    return "pending"


def build_ai_work_timeline(
    render_job: StoredRenderJob,
    edit_plan: Optional[EditPlan] = None,
    source_clips: Optional[List[EditCandidateClip]] = None,
    gpt_rerank_summary: Optional[GPTHighlightRerankSummary] = None,
) -> AIWorkTimeline:
    candidate_count = len(source_clips) if source_clips is not None else None
    selected_count = len(edit_plan.clips) if edit_plan is not None else None
    duplicate_groups = _duplicate_group_count(source_clips)
    slow_motion_count = _slow_motion_moment_count(edit_plan)
    template = get_template_pack(edit_plan.templateId if edit_plan is not None else render_job.template_id)
    plan_ready_status: AIWorkStepStatus = "complete" if edit_plan is not None else ("failed" if render_job.status in {"failed", "failed_timeout", "cancelled"} else "pending")
    branding_detail = None
    if edit_plan is not None:
        branding_parts = []
        branding_parts.append("watermark included" if edit_plan.watermark.enabled else "watermark not included")
        branding_parts.append("outro included" if edit_plan.outro.enabled else "outro not included")
        branding_detail = ", ".join(branding_parts).capitalize() + "."

    finding_detail = f"Reviewed {_clip_count_label(candidate_count, 'candidate clip', 'candidate clips')}." if candidate_count is not None else None
    if gpt_rerank_summary is not None and gpt_rerank_summary.status == "applied":
        finding_detail = f"GPT reranked {gpt_rerank_summary.sampledClipCount} candidate clips from {gpt_rerank_summary.sampledFrameCount} sampled keyframes."

    steps = [
        AIWorkStep(
            stepId="video_uploaded",
            title="Uploaded game video",
            detail="Cloud source is ready for editing." if render_job.source_object_key else None,
            status="complete" if render_job.source_object_key else plan_ready_status,
            startedAt=render_job.created_at,
            completedAt=render_job.created_at if render_job.source_object_key else None,
        ),
        AIWorkStep(
            stepId="finding_highlights",
            title="Finding your best plays",
            detail=finding_detail,
            status=plan_ready_status,
            startedAt=render_job.created_at if edit_plan is not None else None,
            completedAt=render_job.created_at if edit_plan is not None else None,
        ),
        AIWorkStep(
            stepId="selecting_best_clips",
            title="Selecting strongest clips",
            detail=f"Selected {selected_count} clips from {candidate_count} candidates." if selected_count is not None and candidate_count is not None else (_clip_count_label(selected_count, "selected clip", "selected clips") if selected_count is not None else None),
            status=plan_ready_status,
            startedAt=render_job.created_at if edit_plan is not None else None,
            completedAt=render_job.created_at if edit_plan is not None else None,
        ),
        AIWorkStep(
            stepId="removing_duplicates",
            title="Checking duplicate plays",
            detail=f"Checked {duplicate_groups} duplicate groups." if duplicate_groups is not None else None,
            status=plan_ready_status,
            startedAt=render_job.created_at if edit_plan is not None else None,
            completedAt=render_job.created_at if edit_plan is not None else None,
        ),
        AIWorkStep(
            stepId="applying_template",
            title=f"Applying {template.displayName} style",
            detail=f"Template: {template.displayName}.",
            status=plan_ready_status,
            startedAt=render_job.created_at if edit_plan is not None else None,
            completedAt=render_job.created_at if edit_plan is not None else None,
        ),
        AIWorkStep(
            stepId="adding_slow_motion",
            title="Adding slow motion",
            detail=f"Slow-motion moments: {slow_motion_count}.",
            status=plan_ready_status,
            startedAt=render_job.created_at if edit_plan is not None else None,
            completedAt=render_job.created_at if edit_plan is not None else None,
        ),
        AIWorkStep(
            stepId="adding_watermark_outro",
            title="Adding HoopClips branding",
            detail=branding_detail,
            status=plan_ready_status,
            startedAt=render_job.created_at if edit_plan is not None else None,
            completedAt=render_job.created_at if edit_plan is not None else None,
        ),
        AIWorkStep(
            stepId="rendering_mp4",
            title="Rendering final MP4",
            detail="Cloud renderer is creating the MP4.",
            status=_step_status_for_render(render_job.status),
            startedAt=render_job.started_at or render_job.created_at,
            completedAt=render_job.completed_at if render_job.status == "rendered" else None,
        ),
        AIWorkStep(
            stepId="finalizing_download",
            title="Finalizing your MP4",
            detail="Final MP4 is stored for preview and sharing." if render_job.output_object_key else None,
            status=_finalize_status_for_render(render_job),
            startedAt=render_job.completed_at if render_job.output_object_key else None,
            completedAt=render_job.completed_at if render_job.output_object_key else None,
        ),
    ]
    return AIWorkTimeline(
        editJobId=render_job.edit_job_id,
        revisionId=render_job.revision_id,
        renderJobId=render_job.render_job_id,
        status=render_job.status,
        generatedAt=now_utc(),
        steps=steps,
    )


def build_ai_work_receipt(
    render_job: StoredRenderJob,
    edit_plan: Optional[EditPlan] = None,
    source_clips: Optional[List[EditCandidateClip]] = None,
    gpt_rerank_summary: Optional[GPTHighlightRerankSummary] = None,
) -> AIWorkReceipt:
    candidate_count = len(source_clips) if source_clips is not None else None
    selected_count = len(edit_plan.clips) if edit_plan is not None else None
    slow_motion_count = _slow_motion_moment_count(edit_plan)
    template = get_template_pack(edit_plan.templateId if edit_plan is not None else render_job.template_id)
    policy = get_plan_tier_policy(render_job.plan_tier)
    storage_expires_at = parse_datetime(render_job.retention_metadata.get("expiresAt") if render_job.retention_metadata else None) or render_job.expires_at
    watermark_included = edit_plan.watermark.enabled if edit_plan is not None else None
    outro_included = edit_plan.outro.enabled if edit_plan is not None else None
    selected_clip_ids = {clip.clipId for clip in edit_plan.clips} if edit_plan is not None else set()
    uncertain_clip_ids = _team_uncertain_clip_ids(source_clips)
    defensive_clip_ids = _defensive_clip_ids(source_clips)
    timing_issue_clip_ids = _timing_issue_clip_ids(source_clips)
    shot_outcome_evidence_clip_ids = _shot_outcome_evidence_clip_ids(source_clips)
    shot_outcome_issue_clip_ids = _shot_outcome_issue_clip_ids(source_clips)
    label_only_outcome_clip_ids = _label_only_outcome_clip_ids(source_clips)
    team_uncertain_candidate_count = len(uncertain_clip_ids) if source_clips is not None else None
    team_uncertain_selected_count = len(selected_clip_ids & uncertain_clip_ids) if edit_plan is not None and source_clips is not None else None
    defensive_selected_count = len(selected_clip_ids & defensive_clip_ids) if edit_plan is not None and source_clips is not None else None
    timing_issue_candidate_count = len(timing_issue_clip_ids) if source_clips is not None else None
    timing_issue_selected_count = len(selected_clip_ids & timing_issue_clip_ids) if edit_plan is not None and source_clips is not None else None
    timing_quality_selected_count = (selected_count - timing_issue_selected_count) if selected_count is not None and timing_issue_selected_count is not None else None
    shot_outcome_evidence_selected_count = (
        len(selected_clip_ids & shot_outcome_evidence_clip_ids) if edit_plan is not None and source_clips is not None else None
    )
    shot_outcome_issue_selected_count = (
        len(selected_clip_ids & shot_outcome_issue_clip_ids) if edit_plan is not None and source_clips is not None else None
    )
    label_only_outcome_selected_count = (
        len(selected_clip_ids & label_only_outcome_clip_ids) if edit_plan is not None and source_clips is not None else None
    )
    summary_rows: List[str] = []
    if selected_count is not None and candidate_count is not None:
        summary_rows.append(f"Selected {selected_count} clips from {candidate_count} candidates.")
    elif selected_count is not None:
        summary_rows.append(f"Selected {selected_count} clips.")
    if gpt_rerank_summary is not None:
        if gpt_rerank_summary.status == "applied":
            summary_rows.append(
                f"GPT reranked {gpt_rerank_summary.sampledClipCount} clips from {gpt_rerank_summary.sampledFrameCount} keyframes."
            )
            if gpt_rerank_summary.rejectedReasonCounts:
                summary_rows.append(
                    "GPT rejected clips: "
                    + ", ".join(
                        f"{reason} x{count}"
                        for reason, count in sorted(gpt_rerank_summary.rejectedReasonCounts.items())
                        if count > 0
                    )
                    + "."
                )
            if gpt_rerank_summary.storyOrderClipIds:
                story_count = len(gpt_rerank_summary.storyOrderClipIds)
                summary_rows.append(f"GPT story order applied to {story_count} candidate clip{'s' if story_count != 1 else ''}.")
            if gpt_rerank_summary.uncertainReviewClipIds:
                review_count = len(gpt_rerank_summary.uncertainReviewClipIds)
                summary_rows.append(
                    f"Kept {review_count} uncertain team candidate{'s' if review_count != 1 else ''} available for Review."
                )
            if gpt_rerank_summary.planEditApplied:
                summary_rows.append("GPT plan edit applied after deterministic validation.")
        elif gpt_rerank_summary.status == "fallback" and gpt_rerank_summary.fallbackReason:
            summary_rows.append(f"GPT rerank fallback: {gpt_rerank_summary.fallbackReason}.")
    if team_uncertain_selected_count:
        summary_rows.append(
            f"Kept {team_uncertain_selected_count} uncertain team clip{'s' if team_uncertain_selected_count != 1 else ''} for review."
        )
    if defensive_selected_count:
        summary_rows.append(
            f"Included {defensive_selected_count} defensive highlight{'s' if defensive_selected_count != 1 else ''}."
        )
    if timing_issue_selected_count:
        summary_rows.append(
            f"Flagged {timing_issue_selected_count} selected clip{'s' if timing_issue_selected_count != 1 else ''} with weak timing/context."
        )
    elif timing_quality_selected_count:
        summary_rows.append(
            f"Timing quality: {timing_quality_selected_count} selected clip{'s' if timing_quality_selected_count != 1 else ''} passed context checks."
        )
    if shot_outcome_evidence_selected_count:
        summary_rows.append(
            f"Shot outcome evidence: {shot_outcome_evidence_selected_count} selected clip{'s' if shot_outcome_evidence_selected_count != 1 else ''} passed rim/result tracking checks."
        )
    if label_only_outcome_selected_count:
        summary_rows.append(
            f"Needs review: {label_only_outcome_selected_count} selected shot outcome{'s' if label_only_outcome_selected_count != 1 else ''} came from label-only evidence."
        )
    elif shot_outcome_issue_selected_count:
        summary_rows.append(
            f"Needs review: {shot_outcome_issue_selected_count} selected shot outcome{'s' if shot_outcome_issue_selected_count != 1 else ''} had weak result evidence."
        )
    summary_rows.append(f"Applied {template.displayName} template.")
    summary_rows.append(f"Added {slow_motion_count} slow-motion moments.")
    if render_job.duration_seconds is not None:
        summary_rows.append(f"Rendered {round(render_job.duration_seconds, 1)}s MP4.")
    summary_rows.append(f"Export limit: {policy.maxOutputResolution}.")
    if watermark_included is not None or outro_included is not None:
        summary_rows.append(
            "Branding: "
            + ", ".join(
                part
                for part in [
                    "watermark included" if watermark_included else ("watermark removed" if watermark_included is not None else None),
                    "outro included" if outro_included else ("outro removed" if outro_included is not None else None),
                ]
                if part
            )
            + "."
        )
    if storage_expires_at is not None:
        summary_rows.append(f"Stored until {storage_expires_at.isoformat()}.")

    return AIWorkReceipt(
        editJobId=render_job.edit_job_id,
        revisionId=render_job.revision_id,
        renderJobId=render_job.render_job_id,
        selectedClipCount=selected_count,
        candidateClipCount=candidate_count,
        templateId=template.templateId,
        templateName=template.displayName,
        slowMotionMomentCount=slow_motion_count,
        outputDurationSeconds=render_job.duration_seconds,
        outputResolution=policy.maxOutputResolution,
        aspectRatio=render_job.aspect_ratio,
        watermarkIncluded=watermark_included,
        outroIncluded=outro_included,
        storageExpiresAt=storage_expires_at,
        planTier=render_job.plan_tier,
        priorityQueue=render_job.plan_tier in {"pro", "internal", "dev"},
        gptRerankApplied=gpt_rerank_summary.status == "applied" if gpt_rerank_summary is not None else False,
        gptRerankModel=gpt_rerank_summary.model if gpt_rerank_summary is not None else None,
        gptRerankSampledClipCount=gpt_rerank_summary.sampledClipCount if gpt_rerank_summary is not None else None,
        gptRerankSampledFrameCount=gpt_rerank_summary.sampledFrameCount if gpt_rerank_summary is not None else None,
        gptRerankKeptClipCount=len(gpt_rerank_summary.keptClipIds) if gpt_rerank_summary is not None else None,
        gptRerankRejectedClipCount=len(gpt_rerank_summary.rejectedClipIds) if gpt_rerank_summary is not None else None,
        gptUncertainReviewClipCount=len(gpt_rerank_summary.uncertainReviewClipIds) if gpt_rerank_summary is not None else None,
        gptUncertainReviewClipIds=gpt_rerank_summary.uncertainReviewClipIds if gpt_rerank_summary is not None else [],
        gptRerankRejectedReasonCounts=gpt_rerank_summary.rejectedReasonCounts if gpt_rerank_summary is not None else {},
        gptRerankStoryOrderClipIds=gpt_rerank_summary.storyOrderClipIds if gpt_rerank_summary is not None else [],
        gptPlanEditApplied=gpt_rerank_summary.planEditApplied if gpt_rerank_summary is not None else False,
        gptRerankFallbackReason=gpt_rerank_summary.fallbackReason if gpt_rerank_summary is not None else None,
        teamUncertainCandidateCount=team_uncertain_candidate_count,
        teamUncertainSelectedClipCount=team_uncertain_selected_count,
        defensiveSelectedClipCount=defensive_selected_count,
        timingQualitySelectedClipCount=timing_quality_selected_count,
        timingIssueCandidateCount=timing_issue_candidate_count,
        timingIssueSelectedClipCount=timing_issue_selected_count,
        shotOutcomeEvidenceSelectedClipCount=shot_outcome_evidence_selected_count,
        shotOutcomeIssueSelectedClipCount=shot_outcome_issue_selected_count,
        labelOnlyOutcomeSelectedClipCount=label_only_outcome_selected_count,
        summaryRows=summary_rows,
    )


def render_log_payload(render_job: StoredRenderJob, status: str, extra: Dict[str, Any]) -> str:
    import json

    payload: Dict[str, Any] = {
        "editJobId": render_job.edit_job_id,
        "revisionId": render_job.revision_id,
        "renderJobId": render_job.render_job_id,
        "traceId": render_job.trace_id,
        "status": status,
        "renderer": "cloud_ffmpeg",
        "rendererVersion": "ffmpeg-renderer-v1",
        "updatedAt": now_utc().isoformat(),
    }
    payload.update(extra)
    return json.dumps(payload, indent=2, sort_keys=True)
