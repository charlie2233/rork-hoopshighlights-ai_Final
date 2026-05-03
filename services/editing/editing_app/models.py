from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .backend_imports import ensure_ios_backend_on_path

ensure_ios_backend_on_path()

from app.editing import CreateEditJobRequest, EditCandidateClip, EditPlan, EditPlanValidationIssue, EditRevisionResponse, PlanTier, policy_summary_for_client  # noqa: E402


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


RenderStatus = Literal["render_requested", "created", "queued", "rendering", "rendered", "failed", "failed_timeout", "cancelled"]


class CreateRenderJobRequest(APIModel):
    editJobId: str = Field(min_length=1, max_length=128)
    revisionId: Optional[str] = Field(default=None, min_length=1, max_length=128)
    installId: str = Field(min_length=8, max_length=128)
    sourceObjectKey: str = Field(min_length=1, max_length=512)
    planTier: PlanTier = "free"
    editPlan: EditPlan
    sourceClips: List[EditCandidateClip] = Field(default_factory=list, max_length=30)
    idempotencyKey: Optional[str] = Field(default=None, min_length=8, max_length=160)


class StartEditJobRenderRequest(APIModel):
    installId: str = Field(min_length=8, max_length=128)
    sourceObjectKey: Optional[str] = Field(default=None, min_length=1, max_length=512)
    planTier: Optional[PlanTier] = None
    editPlan: Optional[EditPlan] = None
    sourceClips: List[EditCandidateClip] = Field(default_factory=list, max_length=30)
    idempotencyKey: Optional[str] = Field(default=None, min_length=8, max_length=160)


class StartEditRevisionRenderRequest(APIModel):
    installId: str = Field(min_length=8, max_length=128)
    idempotencyKey: Optional[str] = Field(default=None, min_length=8, max_length=160)


class RenderJobResponse(APIModel):
    editJobId: str
    revisionId: Optional[str] = None
    renderJobId: str
    renderer: str
    rendererVersion: str
    planVersion: Optional[str] = None
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


class DownloadUrlResponse(APIModel):
    editJobId: str
    renderJobId: str
    downloadUrl: str
    outputObjectKey: str
    contentType: str = "video/mp4"
    expiresAt: datetime


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

    def to_response(self) -> RenderJobResponse:
        return RenderJobResponse(
            editJobId=self.edit_job_id,
            revisionId=self.revision_id,
            renderJobId=self.render_job_id,
            renderer="cloud_ffmpeg",
            rendererVersion=self.renderer_version,
            planVersion=self.plan_version,
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
