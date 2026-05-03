from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
import tempfile
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, Header, Query, Response
from fastapi.responses import FileResponse, JSONResponse

from .backend_imports import ensure_ios_backend_on_path
from .config import EditingSettings, get_settings
from .models import (
    CreateEditJobRequest,
    CreateRenderJobRequest,
    DownloadUrlResponse,
    EditRevisionListResponse,
    ErrorResponse,
    RenderJobResponse,
    StartEditJobRenderRequest,
    StartEditRevisionRenderRequest,
    StoredRenderJob,
    now_utc,
    render_log_payload,
)
from .render_storage import EditingServiceError, RenderStorage

ensure_ios_backend_on_path()

from app.editing import (  # noqa: E402
    AIEditFeatureFlags,
    EditPlanValidationIssue,
    EditRevisionResponse,
    ReviseEditJobRequest,
    StoredEditJob,
    build_edit_job,
    build_revision_response,
    default_ai_edit_feature_flags,
    estimate_render_cost,
    get_plan_tier_policy,
    policy_summary_for_client,
    validate_edit_plan,
)
from app.models import APIError  # noqa: E402
from app.renderers.ffmpeg_renderer import FfmpegRenderer, ffmpeg_diagnostics  # noqa: E402


def resolve_feature_flags() -> AIEditFeatureFlags:
    import os

    def flag(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    max_daily = os.getenv("HOOPS_AI_EDIT_MAX_DAILY_RENDERS")
    parsed_max_daily = int(max_daily) if max_daily and max_daily.isdigit() else None
    defaults = default_ai_edit_feature_flags()
    return AIEditFeatureFlags(
        aiEditEnabled=flag("HOOPS_AI_EDIT_ENABLED", defaults.aiEditEnabled),
        aiEditRevisionEnabled=flag("HOOPS_AI_EDIT_REVISION_ENABLED", defaults.aiEditRevisionEnabled),
        aiEditTemplatePackEnabled=flag("HOOPS_AI_EDIT_TEMPLATE_PACK_ENABLED", defaults.aiEditTemplatePackEnabled),
        aiEditMaxDailyRenders=parsed_max_daily,
        aiEditFreeWatermarkRequired=flag("HOOPS_AI_EDIT_FREE_WATERMARK_REQUIRED", defaults.aiEditFreeWatermarkRequired),
        aiEditProExportsEnabled=flag("HOOPS_AI_EDIT_PRO_EXPORTS_ENABLED", defaults.aiEditProExportsEnabled),
    )


def create_app(settings: Optional[EditingSettings] = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    storage = RenderStorage(resolved_settings)
    app = FastAPI(title=resolved_settings.service_name, version=resolved_settings.backend_model_version)
    render_jobs: Dict[str, StoredRenderJob] = {}
    render_jobs_by_edit_id: Dict[str, str] = {}
    render_jobs_by_idempotency_key: Dict[str, str] = {}
    render_requests: Dict[str, CreateRenderJobRequest] = {}
    render_created_by_install: Dict[str, list] = {}
    edit_jobs: Dict[str, StoredEditJob] = {}
    edit_revisions: Dict[str, list[EditRevisionResponse]] = {}
    edit_revisions_by_id: Dict[str, EditRevisionResponse] = {}
    feature_flags = resolve_feature_flags()

    def error_response(error: EditingServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=ErrorResponse(errorCode=error.error_code, errorMessage=error.error_message, failureReason=error.error_message).model_dump(exclude_none=True),
        )

    def require_secret(value: Optional[str]) -> None:
        expected = resolved_settings.shared_secret
        if expected and value != expected:
            raise EditingServiceError(401, "invalid_editing_secret", "Invalid editing service secret.")

    def require_job(render_job_id: str) -> StoredRenderJob:
        job = render_jobs.get(render_job_id)
        if job is None:
            raise EditingServiceError(404, "render_job_not_found", "Render job was not found.")
        return job

    def require_edit_job(edit_job_id: str) -> StoredEditJob:
        job = edit_jobs.get(edit_job_id)
        if job is None:
            raise EditingServiceError(404, "edit_job_not_found", "Edit job was not found.")
        return job

    def require_edit_owner(job: StoredEditJob, install_id: Optional[str]) -> None:
        if not install_id or install_id != job.install_id:
            raise EditingServiceError(403, "install_mismatch", "Install ID does not own this edit job.")

    def require_owner(job: StoredRenderJob, install_id: Optional[str]) -> None:
        if not install_id or install_id != job.install_id:
            raise EditingServiceError(403, "install_mismatch", "Install ID does not own this render job.")

    def emit_event(event_name: str, **fields: object) -> None:
        payload = {"event": event_name, "service": resolved_settings.service_name, "environment": resolved_settings.environment, **fields}
        sanitized = {key: value for key, value in payload.items() if value is not None and "url" not in key.lower() and "secret" not in key.lower()}
        print(json.dumps(sanitized, sort_keys=True), flush=True)
        try:
            import sentry_sdk  # type: ignore

            sentry_sdk.add_breadcrumb(category="ai_edit", message=event_name, data=sanitized, level="info")
            if event_name.endswith(".failed"):
                sentry_sdk.capture_message(event_name, level="error")
        except Exception:
            pass

    def emit_policy_failed(error: EditingServiceError, **fields: object) -> None:
        if error.error_code in {
            "active_render_limit",
            "ai_edit_disabled",
            "ai_edit_revision_disabled",
            "ai_edit_template_pack_disabled",
            "daily_render_limit",
            "pro_exports_unavailable",
            "render_duration_limit",
            "render_retry_limit",
            "revision_limit",
            "source_video_too_long",
        }:
            emit_event("policy.failed", failureReason=error.error_code, **fields)

    def active_render_statuses() -> set[str]:
        return {"render_requested", "created", "queued", "rendering"}

    def mark_stale_renders() -> None:
        now = now_utc()
        for job in list(render_jobs.values()):
            if job.status not in active_render_statuses():
                continue
            timeout_seconds = get_plan_tier_policy(job.plan_tier).staleRenderTimeoutSeconds
            if (now - job.updated_at).total_seconds() > timeout_seconds:
                mark_failed(job, "failed_timeout")

    def prune_daily_render_counts(install_id: str) -> None:
        cutoff = now_utc() - timedelta(days=1)
        render_created_by_install[install_id] = [
            created_at for created_at in render_created_by_install.get(install_id, []) if created_at >= cutoff
        ]

    def effective_policy(plan_tier: str):
        policy = get_plan_tier_policy(plan_tier)
        if feature_flags.aiEditMaxDailyRenders is not None:
            policy = policy.model_copy(update={"maxDailyRenders": feature_flags.aiEditMaxDailyRenders})
        if plan_tier == "free" and not feature_flags.aiEditFreeWatermarkRequired:
            policy = policy.model_copy(update={"watermarkRequired": False})
        return policy

    def enforce_render_quota(request: CreateRenderJobRequest) -> None:
        policy = effective_policy(request.planTier)
        prune_daily_render_counts(request.installId)
        if len(render_created_by_install.get(request.installId, [])) >= policy.maxDailyRenders:
            raise EditingServiceError(429, "daily_render_limit", "Daily AI edit render limit reached for this plan.")
        active_count = sum(1 for job in render_jobs.values() if job.install_id == request.installId and job.status in active_render_statuses())
        if active_count >= policy.maxActiveRenders:
            raise EditingServiceError(429, "active_render_limit", "Too many AI edit renders are active for this plan.")

    def record_render_quota_usage(job: StoredRenderJob) -> None:
        render_created_by_install.setdefault(job.install_id, []).append(job.created_at)

    def validate_create_request_policy(request: CreateEditJobRequest) -> None:
        if not feature_flags.aiEditEnabled:
            raise EditingServiceError(403, "ai_edit_disabled", "AI Edit is temporarily unavailable.")
        if request.templateId and not feature_flags.aiEditTemplatePackEnabled:
            raise EditingServiceError(403, "ai_edit_template_pack_disabled", "AI Edit templates are temporarily unavailable.")
        if request.planTier == "pro" and not feature_flags.aiEditProExportsEnabled:
            raise EditingServiceError(403, "pro_exports_unavailable", "Pro AI exports are not enabled yet.")
        policy = effective_policy(request.planTier)
        estimated_source_seconds = max((clip.end for clip in request.clips), default=0.0)
        if estimated_source_seconds > policy.maxSourceVideoSeconds:
            raise EditingServiceError(400, "source_video_too_long", "Source video exceeds the plan tier source duration limit.")
        if request.targetDurationSeconds > policy.maxRenderSeconds:
            raise EditingServiceError(400, "render_duration_limit", "Requested AI edit length exceeds this plan's render limit.")

    def validate_revision_policy(edit_job_id: str, request: ReviseEditJobRequest) -> None:
        if not feature_flags.aiEditRevisionEnabled:
            raise EditingServiceError(403, "ai_edit_revision_disabled", "AI Edit revisions are temporarily unavailable.")
        job = require_edit_job(edit_job_id)
        policy = effective_policy(job.request.planTier)
        if len(edit_revisions.get(edit_job_id, [])) >= policy.maxRevisionsPerEdit:
            raise EditingServiceError(429, "revision_limit", "Revision limit reached for this edit.")
        if request.targetDurationSeconds is not None and request.targetDurationSeconds > policy.maxRenderSeconds:
            raise EditingServiceError(400, "render_duration_limit", "Requested revision length exceeds this plan's render limit.")

    def build_retention_metadata(job: StoredRenderJob, request: CreateRenderJobRequest, output_bytes: int, duration_seconds: float, status: str) -> Dict[str, Any]:
        policy = get_plan_tier_policy(request.planTier)
        retention_days = policy.renderRetentionDays if status == "rendered" else policy.failedRenderRetentionDays
        expires_at = now_utc() + timedelta(days=retention_days)
        return {
            "expiresAt": expires_at.isoformat(),
            "retentionClass": f"{request.planTier}_{'final_render' if status == 'rendered' else 'failed_render'}",
            "deleteEligible": True,
            "planTier": request.planTier,
            "editJobId": job.edit_job_id,
            "revisionId": request.revisionId,
            "renderJobId": job.render_job_id,
            "templateId": request.editPlan.templateId,
            "outputBytes": output_bytes,
            "durationSeconds": duration_seconds,
        }

    def mark_failed(job: StoredRenderJob, reason: str, validation_errors: Optional[list] = None) -> None:
        job.status = "failed"
        job.failure_reason = reason
        job.validation_errors = validation_errors or []
        job.render_log_object_key = f"edits/{job.edit_job_id}/render_jobs/{job.render_job_id}/render_log.json"
        request = render_requests.get(job.render_job_id)
        if request is not None:
            job.retention_metadata = build_retention_metadata(job, request, 0, 0.0, "failed")
        job.updated_at = now_utc()
        emit_event("render.failed", editJobId=job.edit_job_id, renderJobId=job.render_job_id, planTier=job.plan_tier, failureReason=reason)
        try:
            storage.put_json(
                job.render_log_object_key,
                render_log_payload(
                    job,
                    "failed",
                    {
                        "failureReason": reason,
                        "planTier": job.plan_tier,
                        "policy": policy_summary_for_client(job.plan_tier),
                        "retentionMetadata": job.retention_metadata,
                        "validationErrors": [error.model_dump() for error in job.validation_errors],
                    },
                ),
            )
        except Exception:
            pass

    def run_render_job(render_job_id: str) -> None:
        job = require_job(render_job_id)
        request = render_requests[render_job_id]
        source = None
        try:
            job.status = "rendering"
            job.updated_at = now_utc()
            emit_event("render.started", editJobId=job.edit_job_id, renderJobId=job.render_job_id, templateId=request.editPlan.templateId, planTier=request.planTier)
            source = storage.materialize_source(request.sourceObjectKey)
            with tempfile.TemporaryDirectory(prefix="hoopclips-edit-render-", dir=str(resolved_settings.upload_root)) as temp_dir:
                result = FfmpegRenderer().render(request.editPlan, source.local_path, Path(temp_dir))
                plan_key = f"edits/{request.editJobId}/plan.json"
                output_key = f"edits/{request.editJobId}/render_jobs/{render_job_id}/final.mp4"
                log_key = f"edits/{request.editJobId}/render_jobs/{render_job_id}/render_log.json"
                output_bytes = result.output_path.stat().st_size
                retention_metadata = build_retention_metadata(job, request, output_bytes, result.duration_seconds, "rendered")
                storage.put_json(plan_key, request.editPlan.model_dump_json(indent=2))
                storage.put_file(
                    output_key,
                    result.output_path,
                    "video/mp4",
                    metadata={key: value for key, value in retention_metadata.items() if key not in {"deleteEligible"}},
                )
                job.status = "rendered"
                job.output_object_key = output_key
                job.render_log_object_key = log_key
                job.duration_seconds = result.duration_seconds
                job.output_bytes = output_bytes
                job.retention_metadata = retention_metadata
                job.updated_at = now_utc()
                storage.put_json(
                    log_key,
                    render_log_payload(
                        job,
                        "rendered",
                        {
                            "outputObjectKey": output_key,
                            "durationSeconds": result.duration_seconds,
                            "outputBytes": output_bytes,
                            "aspectRatio": request.editPlan.aspectRatio,
                            "clipCount": len(request.editPlan.clips),
                            "planTier": request.planTier,
                            "policy": policy_summary_for_client(request.planTier),
                            "renderCost": estimate_render_cost(request.editPlan),
                            "retentionMetadata": retention_metadata,
                            "ffmpeg": result.render_log,
                        },
                    ),
                )
                emit_event(
                    "render.completed",
                    editJobId=job.edit_job_id,
                    renderJobId=job.render_job_id,
                    templateId=request.editPlan.templateId,
                    planTier=request.planTier,
                    rendererVersion="ffmpeg-renderer-v1",
                    durationSeconds=result.duration_seconds,
                    outputBytes=output_bytes,
                )
        except APIError as error:
            mark_failed(job, error.error_code)
        except EditingServiceError as error:
            mark_failed(job, error.error_code)
        except Exception:
            mark_failed(job, "render_failed")
        finally:
            if source is not None:
                source.cleanup()

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": resolved_settings.service_name}

    @app.get("/readyz")
    async def readyz() -> dict[str, object]:
        ffmpeg = ffmpeg_diagnostics()
        storage_diag = storage.diagnostics()
        auth_ready = bool(resolved_settings.shared_secret) or resolved_settings.is_local
        ready = (
            bool(ffmpeg["ffmpegAvailable"])
            and bool(ffmpeg["ffprobeAvailable"])
            and bool(storage_diag["providerReady"])
            and bool(storage_diag["uploadRootWritable"])
            and auth_ready
        )
        return {
            "status": "ok" if ready else "degraded",
            "service": resolved_settings.service_name,
            "environment": resolved_settings.environment,
            "auth": "configured" if auth_ready else "missing",
            "ffmpeg": ffmpeg,
            "renderStorage": storage_diag,
        }

    @app.get("/version")
    async def version() -> dict[str, object]:
        return {
            "service": resolved_settings.service_name,
            "backendModelVersion": resolved_settings.backend_model_version,
            "gitSha": resolved_settings.git_sha,
            "ffmpeg": ffmpeg_diagnostics(),
            "featureFlags": feature_flags.model_dump(),
        }

    def enqueue_render_job(request: CreateRenderJobRequest, background_tasks: BackgroundTasks, force_new: bool = False) -> RenderJobResponse:
        mark_stale_renders()
        idempotency_key = request.idempotencyKey or f"{request.installId}:{request.editJobId}:{request.editPlan.editJobId}:{request.editPlan.templateId}:{len(request.editPlan.clips)}"
        existing_by_key = render_jobs_by_idempotency_key.get(idempotency_key)
        if existing_by_key and existing_by_key in render_jobs:
            existing = render_jobs[existing_by_key]
            if existing.status in active_render_statuses() or existing.status == "rendered":
                return existing.to_response()
        existing_render_id = render_jobs_by_edit_id.get(request.editJobId)
        if existing_render_id and not force_new:
            existing = render_jobs[existing_render_id]
            if existing.status in active_render_statuses() or existing.status == "rendered":
                return existing.to_response()
            if existing.status == "failed" and existing.retry_count >= get_plan_tier_policy(request.planTier).maxRenderRetries:
                raise EditingServiceError(429, "render_retry_limit", "Render retry limit reached for this edit.")

        enforce_render_quota(request)

        render_job_id = "render_" + uuid4().hex
        job = StoredRenderJob(
            edit_job_id=request.editJobId,
            render_job_id=render_job_id,
            install_id=request.installId,
            trace_id="trace_" + uuid4().hex,
            status="queued",
            aspect_ratio=request.editPlan.aspectRatio,
            created_at=now_utc(),
            updated_at=now_utc(),
            plan_tier=request.planTier,
            retry_count=(render_jobs[existing_render_id].retry_count + 1) if existing_render_id and existing_render_id in render_jobs else 0,
            idempotency_key=idempotency_key,
            revision_id=request.revisionId,
        )
        render_jobs[render_job_id] = job
        render_jobs_by_edit_id[request.editJobId] = render_job_id
        render_jobs_by_idempotency_key[idempotency_key] = render_job_id
        render_requests[render_job_id] = request

        validation_errors = []
        if request.sourceClips:
            validation_errors.extend(validate_edit_plan(request.editPlan, request.sourceClips, request.planTier))
        if not storage.source_exists(request.sourceObjectKey):
            validation_errors.append(
                EditPlanValidationIssue(field="sourceObjectKey", code="source_missing", message="Source video object was not found.")
            )
        policy = effective_policy(request.planTier)
        if policy.watermarkRequired and not request.editPlan.watermark.enabled:
            validation_errors.append(
                EditPlanValidationIssue(field="watermark.enabled", code="missing_free_watermark", message="Free plans must include the Hoopclips watermark.")
            )
        if policy.outroRequired and (not request.editPlan.outro.enabled or request.editPlan.outro.durationSeconds <= 0):
            validation_errors.append(
                EditPlanValidationIssue(field="outro.enabled", code="missing_free_outro", message="Free plans must include a Hoopclips outro.")
            )
        if validation_errors:
            mark_failed(job, "invalid_edit_plan", validation_errors)
            return job.to_response()

        record_render_quota_usage(job)
        emit_event("render.requested", editJobId=job.edit_job_id, renderJobId=job.render_job_id, templateId=request.editPlan.templateId, planTier=request.planTier)
        background_tasks.add_task(run_render_job, render_job_id)
        return job.to_response()

    @app.post("/v1/edit-jobs", responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}})
    async def create_edit_job(
        request: CreateEditJobRequest,
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            validate_create_request_policy(request)
            edit_job_id = "edit_" + uuid4().hex
            job = build_edit_job(request, edit_job_id)
            if job.validation_errors:
                first_error = job.validation_errors[0]
                raise EditingServiceError(400, first_error.code, first_error.message)
            edit_jobs[edit_job_id] = job
            emit_event("edit_plan.created", editJobId=edit_job_id, templateId=job.plan.templateId, planTier=request.planTier)
            return job.to_response()
        except EditingServiceError as error:
            emit_policy_failed(error, templateId=request.templateId, planTier=request.planTier)
            return error_response(error)

    @app.get("/v1/edit-jobs/{edit_job_id}", responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
    async def get_edit_job(
        edit_job_id: str,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            job = require_edit_job(edit_job_id)
            require_edit_owner(job, installId or x_hoops_install_id)
            return job.to_response()
        except EditingServiceError as error:
            job = edit_jobs.get(edit_job_id)
            emit_policy_failed(
                error,
                editJobId=edit_job_id,
                command=request.command,
                planTier=job.request.planTier if job else None,
                templateId=job.plan.templateId if job else None,
            )
            return error_response(error)

    @app.get("/v1/edit-jobs/{edit_job_id}/plan", responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
    async def get_edit_job_plan(
        edit_job_id: str,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            job = require_edit_job(edit_job_id)
            require_edit_owner(job, installId or x_hoops_install_id)
            return job.to_plan_response()
        except EditingServiceError as error:
            stored_edit_job = edit_jobs.get(edit_job_id)
            emit_policy_failed(
                error,
                editJobId=edit_job_id,
                revisionId=revision_id,
                planTier=stored_edit_job.request.planTier if stored_edit_job else None,
                templateId=stored_edit_job.plan.templateId if stored_edit_job else None,
            )
            return error_response(error)

    @app.post("/v1/edit-jobs/{edit_job_id}/revise", response_model=EditRevisionResponse, responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
    async def revise_edit_job_plan(
        edit_job_id: str,
        request: ReviseEditJobRequest,
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            job = require_edit_job(edit_job_id)
            require_edit_owner(job, request.installId or x_hoops_install_id)
            validate_revision_policy(edit_job_id, request)
            revision_id = "rev_" + uuid4().hex
            revised_job, revision_response = build_revision_response(job, request, revision_id)
            if not revision_response.validationResult.valid:
                first_error = revision_response.validationResult.errors[0]
                raise EditingServiceError(400, first_error.code, first_error.message)
            edit_jobs[edit_job_id] = revised_job
            edit_revisions.setdefault(edit_job_id, []).append(revision_response)
            edit_revisions_by_id[revision_id] = revision_response
            emit_event("edit_revision.created", editJobId=edit_job_id, revisionId=revision_id, templateId=revision_response.revisedPlan.templateId, planTier=revised_job.request.planTier)
            return revision_response
        except EditingServiceError as error:
            emit_policy_failed(error, editJobId=request.editJobId, templateId=request.editPlan.templateId, planTier=request.planTier)
            return error_response(error)

    @app.get("/v1/edit-jobs/{edit_job_id}/revisions", response_model=EditRevisionListResponse, responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
    async def list_edit_revisions(
        edit_job_id: str,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            job = require_edit_job(edit_job_id)
            require_edit_owner(job, installId or x_hoops_install_id)
            return EditRevisionListResponse(editJobId=edit_job_id, revisions=edit_revisions.get(edit_job_id, []))
        except EditingServiceError as error:
            emit_policy_failed(
                error,
                editJobId=edit_job_id,
                templateId=request.editPlan.templateId if request.editPlan else None,
                planTier=request.planTier,
            )
            return error_response(error)

    @app.get("/v1/edit-jobs/{edit_job_id}/revisions/{revision_id}", response_model=EditRevisionResponse, responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
    async def get_edit_revision(
        edit_job_id: str,
        revision_id: str,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            job = require_edit_job(edit_job_id)
            require_edit_owner(job, installId or x_hoops_install_id)
            revision = edit_revisions_by_id.get(revision_id)
            if revision is None or revision.editJobId != edit_job_id:
                raise EditingServiceError(404, "revision_not_found", "Edit revision was not found.")
            return revision
        except EditingServiceError as error:
            return error_response(error)

    @app.post("/v1/edit-jobs/{edit_job_id}/revisions/{revision_id}/render", response_model=RenderJobResponse, responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
    async def render_edit_revision(
        edit_job_id: str,
        revision_id: str,
        request: StartEditRevisionRenderRequest,
        background_tasks: BackgroundTasks,
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            stored_edit_job = require_edit_job(edit_job_id)
            require_edit_owner(stored_edit_job, request.installId)
            revision = edit_revisions_by_id.get(revision_id)
            if revision is None or revision.editJobId != edit_job_id:
                raise EditingServiceError(404, "revision_not_found", "Edit revision was not found.")
            if not stored_edit_job.request.sourceObjectKey:
                raise EditingServiceError(400, "missing_source_object_key", "Revision render requires a source video object key.")
            return enqueue_render_job(
                CreateRenderJobRequest(
                    editJobId=edit_job_id,
                    installId=request.installId,
                    sourceObjectKey=stored_edit_job.request.sourceObjectKey,
                    planTier=stored_edit_job.request.planTier,
                    editPlan=revision.revisedPlan,
                    sourceClips=stored_edit_job.request.clips,
                    revisionId=revision_id,
                    idempotencyKey=request.idempotencyKey or f"{edit_job_id}:{revision_id}:render",
                ),
                background_tasks,
                force_new=True,
            )
        except EditingServiceError as error:
            return error_response(error)

    @app.post("/v1/render-jobs", response_model=RenderJobResponse, responses={401: {"model": ErrorResponse}})
    async def create_render_job(
        request: CreateRenderJobRequest,
        background_tasks: BackgroundTasks,
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            return enqueue_render_job(request, background_tasks)
        except EditingServiceError as error:
            return error_response(error)

    @app.post("/v1/edit-jobs/{edit_job_id}/render", response_model=RenderJobResponse, responses={401: {"model": ErrorResponse}})
    async def render_edit_job(
        edit_job_id: str,
        request: StartEditJobRenderRequest,
        background_tasks: BackgroundTasks,
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            stored_edit_job = edit_jobs.get(edit_job_id)
            if stored_edit_job is not None:
                require_edit_owner(stored_edit_job, request.installId)

            edit_plan = request.editPlan or (stored_edit_job.plan if stored_edit_job is not None else None)
            source_clips = request.sourceClips or (stored_edit_job.request.clips if stored_edit_job is not None else [])
            source_object_key = request.sourceObjectKey or (stored_edit_job.request.sourceObjectKey if stored_edit_job is not None else None)
            plan_tier = request.planTier or (stored_edit_job.request.planTier if stored_edit_job is not None else "free")
            if edit_plan is None:
                raise EditingServiceError(400, "missing_edit_plan", "Render request must include an EditPlan or reference a stored edit job.")
            if not source_object_key:
                raise EditingServiceError(400, "missing_source_object_key", "Render request must include a source video object key.")

            return enqueue_render_job(
                CreateRenderJobRequest(
                    editJobId=edit_job_id,
                    installId=request.installId,
                    sourceObjectKey=source_object_key,
                    planTier=plan_tier,
                    editPlan=edit_plan,
                    sourceClips=source_clips,
                    idempotencyKey=request.idempotencyKey,
                ),
                background_tasks,
            )
        except EditingServiceError as error:
            return error_response(error)

    @app.get("/v1/render-jobs/{render_job_id}", response_model=RenderJobResponse, responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
    async def get_render_job(
        render_job_id: str,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            mark_stale_renders()
            job = require_job(render_job_id)
            require_owner(job, installId or x_hoops_install_id)
            return job.to_response()
        except EditingServiceError as error:
            return error_response(error)

    @app.get("/v1/edit-jobs/{edit_job_id}/render-status", response_model=RenderJobResponse, responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
    async def get_edit_render_status(
        edit_job_id: str,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            mark_stale_renders()
            render_job_id = render_jobs_by_edit_id.get(edit_job_id)
            if not render_job_id:
                raise EditingServiceError(404, "render_job_not_found", "Render job was not found.")
            job = require_job(render_job_id)
            require_owner(job, installId or x_hoops_install_id)
            return job.to_response()
        except EditingServiceError as error:
            return error_response(error)

    @app.get("/v1/render-jobs/{render_job_id}/download-url", response_model=DownloadUrlResponse, responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
    async def get_download_url(
        render_job_id: str,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            mark_stale_renders()
            job = require_job(render_job_id)
            require_owner(job, installId or x_hoops_install_id)
            if job.status != "rendered" or not job.output_object_key:
                raise EditingServiceError(409, "render_not_ready", "Render output is not ready for download yet.")
            download_url, expires_at = storage.presigned_get_url(job.output_object_key, job.render_job_id)
            emit_event("download_url.created", editJobId=job.edit_job_id, renderJobId=job.render_job_id, planTier=job.plan_tier)
            return DownloadUrlResponse(
                editJobId=job.edit_job_id,
                renderJobId=job.render_job_id,
                downloadUrl=download_url,
                outputObjectKey=job.output_object_key,
                expiresAt=expires_at,
            )
        except EditingServiceError as error:
            return error_response(error)

    @app.get("/v1/edit-jobs/{edit_job_id}/download-url", response_model=DownloadUrlResponse, responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
    async def get_edit_download_url(
        edit_job_id: str,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            mark_stale_renders()
            render_job_id = render_jobs_by_edit_id.get(edit_job_id)
            if not render_job_id:
                raise EditingServiceError(404, "render_job_not_found", "Render job was not found.")
            job = require_job(render_job_id)
            require_owner(job, installId or x_hoops_install_id)
            if job.status != "rendered" or not job.output_object_key:
                raise EditingServiceError(409, "render_not_ready", "Render output is not ready for download yet.")
            download_url, expires_at = storage.presigned_get_url(job.output_object_key, job.render_job_id)
            emit_event("download_url.created", editJobId=job.edit_job_id, renderJobId=job.render_job_id, planTier=job.plan_tier)
            return DownloadUrlResponse(
                editJobId=job.edit_job_id,
                renderJobId=job.render_job_id,
                downloadUrl=download_url,
                outputObjectKey=job.output_object_key,
                expiresAt=expires_at,
            )
        except EditingServiceError as error:
            return error_response(error)

    @app.get("/v1/internal/render-downloads/{render_job_id}/final.mp4")
    async def download_local_render(render_job_id: str):
        try:
            job = require_job(render_job_id)
            if job.status != "rendered" or not job.output_object_key:
                raise EditingServiceError(404, "render_output_not_found", "Render output was not found.")
            output_path = storage.local_path_for_object(job.output_object_key)
            if not output_path.exists():
                raise EditingServiceError(404, "render_output_not_found", "Render output was not found.")
            return FileResponse(output_path, media_type="video/mp4", filename="Hoopclips.mp4")
        except EditingServiceError as error:
            return error_response(error)

    return app


app = create_app()
