from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .backend_imports import ensure_ios_backend_on_path

ensure_ios_backend_on_path()

from app.editing import CreateEditJobRequest, EditCandidateClip, EditPlan, EditPlanValidationIssue  # noqa: E402


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


RenderStatus = Literal["render_requested", "created", "queued", "rendering", "rendered", "failed", "cancelled"]


class CreateRenderJobRequest(APIModel):
    editJobId: str = Field(min_length=1, max_length=128)
    installId: str = Field(min_length=8, max_length=128)
    sourceObjectKey: str = Field(min_length=1, max_length=512)
    planTier: Literal["free", "pro"] = "free"
    editPlan: EditPlan
    sourceClips: List[EditCandidateClip] = Field(default_factory=list, max_length=30)


class StartEditJobRenderRequest(APIModel):
    installId: str = Field(min_length=8, max_length=128)
    sourceObjectKey: Optional[str] = Field(default=None, min_length=1, max_length=512)
    planTier: Optional[Literal["free", "pro"]] = None
    editPlan: Optional[EditPlan] = None
    sourceClips: List[EditCandidateClip] = Field(default_factory=list, max_length=30)


class RenderJobResponse(APIModel):
    editJobId: str
    renderJobId: str
    renderer: str
    rendererVersion: str
    status: RenderStatus
    outputObjectKey: Optional[str] = None
    renderLogObjectKey: Optional[str] = None
    durationSeconds: Optional[float] = None
    aspectRatio: str
    traceId: str
    failureReason: Optional[str] = None
    validationErrors: List[EditPlanValidationIssue] = Field(default_factory=list)


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
    duration_seconds: Optional[float] = None
    failure_reason: Optional[str] = None
    validation_errors: List[EditPlanValidationIssue] = field(default_factory=list)

    def to_response(self) -> RenderJobResponse:
        return RenderJobResponse(
            editJobId=self.edit_job_id,
            renderJobId=self.render_job_id,
            renderer="cloud_ffmpeg",
            rendererVersion="ffmpeg-renderer-v1",
            status=self.status,
            outputObjectKey=self.output_object_key,
            renderLogObjectKey=self.render_log_object_key,
            durationSeconds=self.duration_seconds,
            aspectRatio=self.aspect_ratio,
            traceId=self.trace_id,
            failureReason=self.failure_reason,
            validationErrors=self.validation_errors,
        )


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def render_log_payload(render_job: StoredRenderJob, status: str, extra: Dict[str, Any]) -> str:
    import json

    payload: Dict[str, Any] = {
        "editJobId": render_job.edit_job_id,
        "renderJobId": render_job.render_job_id,
        "traceId": render_job.trace_id,
        "status": status,
        "renderer": "cloud_ffmpeg",
        "rendererVersion": "ffmpeg-renderer-v1",
        "updatedAt": now_utc().isoformat(),
    }
    payload.update(extra)
    return json.dumps(payload, indent=2, sort_keys=True)
