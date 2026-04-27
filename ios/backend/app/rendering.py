from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from typing import List, Literal, Optional

from .editing import EditPlanValidationIssue, StoredEditJob, estimate_render_cost, validate_edit_plan
from .models import APIModel, now_utc
from .renderers.ffmpeg_renderer import resolve_music_track_path


RenderStatus = Literal["render_requested", "rendering", "rendered", "failed", "cancelled"]
RENDERER_VERSION = "ffmpeg-renderer-v1"


class StartRenderRequest(APIModel):
    installId: str


class RenderJobResponse(APIModel):
    editJobId: str
    renderJobId: str
    planVersion: str
    renderer: str
    rendererVersion: str
    status: RenderStatus
    outputObjectKey: Optional[str] = None
    renderLogObjectKey: Optional[str] = None
    durationSeconds: Optional[float] = None
    aspectRatio: str
    traceId: str
    failureReason: Optional[str] = None
    validationErrors: List[EditPlanValidationIssue] = []


class DownloadUrlResponse(APIModel):
    editJobId: str
    renderJobId: str
    downloadUrl: str
    outputObjectKey: str
    contentType: str = "video/mp4"
    expiresAt: datetime


@dataclass
class StoredRenderJob:
    edit_job_id: str
    render_job_id: str
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

    def to_response(self, plan_version: str) -> RenderJobResponse:
        return RenderJobResponse(
            editJobId=self.edit_job_id,
            renderJobId=self.render_job_id,
            planVersion=plan_version,
            renderer="cloud_ffmpeg",
            rendererVersion=RENDERER_VERSION,
            status=self.status,
            outputObjectKey=self.output_object_key,
            renderLogObjectKey=self.render_log_object_key,
            durationSeconds=self.duration_seconds,
            aspectRatio=self.aspect_ratio,
            traceId=self.trace_id,
            failureReason=self.failure_reason,
            validationErrors=self.validation_errors,
        )


def new_render_job(edit_job: StoredEditJob, render_job_id: str, trace_id: str) -> StoredRenderJob:
    return StoredRenderJob(
        edit_job_id=edit_job.edit_job_id,
        render_job_id=render_job_id,
        trace_id=trace_id,
        status="render_requested",
        aspect_ratio=edit_job.plan.aspectRatio,
        created_at=now_utc(),
        updated_at=now_utc(),
    )


def validate_render_request(edit_job: StoredEditJob, source_exists: bool) -> List[EditPlanValidationIssue]:
    errors = list(validate_edit_plan(edit_job.plan, edit_job.request.clips, edit_job.request.planTier))

    def add(field: str, code: str, message: str) -> None:
        errors.append(EditPlanValidationIssue(field=field, code=code, message=message))

    if not edit_job.request.sourceObjectKey:
        add("sourceObjectKey", "source_missing", "Edit job does not include a sourceObjectKey.")
    elif not source_exists:
        add("sourceObjectKey", "source_missing", "Source video object was not found.")

    max_complexity = float(os.getenv("HOOPS_MAX_RENDER_COMPLEXITY_UNITS", "600"))
    render_cost = estimate_render_cost(edit_job.plan)
    if render_cost["complexityUnits"] > max_complexity:
        add("renderCost", "render_cost_too_high", "Estimated render cost is above the configured limit.")

    if edit_job.request.planTier == "free":
        if edit_job.plan.watermark.position not in {"bottom_right", "bottom_left", "top_right", "top_left"}:
            add("watermark.position", "invalid_watermark_position", "Watermark position is not supported.")
        if edit_job.plan.outro.durationSeconds <= 0:
            add("outro.durationSeconds", "missing_free_outro", "Free plans must include a non-empty Hoopclips outro.")

    for index, clip in enumerate(edit_job.plan.clips):
        for effect_index, effect in enumerate(clip.effects):
            if effect.type == "slow_motion" and effect.speed is not None and not 0.5 <= effect.speed <= 1.0:
                add(
                    f"clips[{index}].effects[{effect_index}].speed",
                    "invalid_slow_motion_speed",
                    "Slow motion speed must be between 0.5x and 1.0x.",
                )

    if edit_job.plan.audio.musicTrackId == "none" and edit_job.plan.audio.musicVolume > 0:
        add("audio.musicVolume", "invalid_music_volume", "musicVolume must be zero when musicTrackId is none.")
    if edit_job.plan.audio.musicTrackId != "none" and resolve_music_track_path(edit_job.plan.audio.musicTrackId) is None:
        add("audio.musicTrackId", "music_track_missing", "Music track is allowed but no render asset was found.")

    return errors


def render_log_payload(render_job: StoredRenderJob, status: str, extra: dict) -> str:
    payload = {
        "editJobId": render_job.edit_job_id,
        "renderJobId": render_job.render_job_id,
        "traceId": render_job.trace_id,
        "status": status,
        "renderer": "cloud_ffmpeg",
        "rendererVersion": RENDERER_VERSION,
        "updatedAt": now_utc().isoformat(),
    }
    payload.update(extra)
    return json.dumps(payload, indent=2, sort_keys=True)
