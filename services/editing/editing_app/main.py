from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Dict, Optional
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, Header, Query, Response
from fastapi.responses import FileResponse, JSONResponse

from .backend_imports import ensure_ios_backend_on_path
from .config import EditingSettings, get_settings
from .models import (
    CreateEditJobRequest,
    CreateRenderJobRequest,
    DownloadUrlResponse,
    ErrorResponse,
    RenderJobResponse,
    StartEditJobRenderRequest,
    StoredRenderJob,
    now_utc,
    render_log_payload,
)
from .render_storage import EditingServiceError, RenderStorage

ensure_ios_backend_on_path()

from app.editing import EditPlanValidationIssue, StoredEditJob, build_edit_job, validate_edit_plan  # noqa: E402
from app.models import APIError  # noqa: E402
from app.renderers.ffmpeg_renderer import FfmpegRenderer, ffmpeg_diagnostics  # noqa: E402


def create_app(settings: Optional[EditingSettings] = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    storage = RenderStorage(resolved_settings)
    app = FastAPI(title=resolved_settings.service_name, version=resolved_settings.backend_model_version)
    render_jobs: Dict[str, StoredRenderJob] = {}
    render_jobs_by_edit_id: Dict[str, str] = {}
    render_requests: Dict[str, CreateRenderJobRequest] = {}
    edit_jobs: Dict[str, StoredEditJob] = {}

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

    def mark_failed(job: StoredRenderJob, reason: str, validation_errors: Optional[list] = None) -> None:
        job.status = "failed"
        job.failure_reason = reason
        job.validation_errors = validation_errors or []
        job.render_log_object_key = f"edits/{job.edit_job_id}/render_jobs/{job.render_job_id}/render_log.json"
        job.updated_at = now_utc()
        try:
            storage.put_json(
                job.render_log_object_key,
                render_log_payload(
                    job,
                    "failed",
                    {
                        "failureReason": reason,
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
            source = storage.materialize_source(request.sourceObjectKey)
            with tempfile.TemporaryDirectory(prefix="hoopclips-edit-render-", dir=str(resolved_settings.upload_root)) as temp_dir:
                result = FfmpegRenderer().render(request.editPlan, source.local_path, Path(temp_dir))
                plan_key = f"edits/{request.editJobId}/plan.json"
                output_key = f"edits/{request.editJobId}/render_jobs/{render_job_id}/final.mp4"
                log_key = f"edits/{request.editJobId}/render_jobs/{render_job_id}/render_log.json"
                storage.put_json(plan_key, request.editPlan.model_dump_json(indent=2))
                storage.put_file(output_key, result.output_path, "video/mp4")
                job.status = "rendered"
                job.output_object_key = output_key
                job.render_log_object_key = log_key
                job.duration_seconds = result.duration_seconds
                job.updated_at = now_utc()
                storage.put_json(
                    log_key,
                    render_log_payload(
                        job,
                        "rendered",
                        {
                            "outputObjectKey": output_key,
                            "durationSeconds": result.duration_seconds,
                            "aspectRatio": request.editPlan.aspectRatio,
                            "clipCount": len(request.editPlan.clips),
                            "ffmpeg": result.render_log,
                        },
                    ),
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
        }

    def enqueue_render_job(request: CreateRenderJobRequest, background_tasks: BackgroundTasks) -> RenderJobResponse:
        existing_render_id = render_jobs_by_edit_id.get(request.editJobId)
        if existing_render_id:
            existing = render_jobs[existing_render_id]
            if existing.status in {"queued", "rendering", "rendered"}:
                return existing.to_response()

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
        )
        render_jobs[render_job_id] = job
        render_jobs_by_edit_id[request.editJobId] = render_job_id
        render_requests[render_job_id] = request

        validation_errors = []
        if request.sourceClips:
            validation_errors.extend(validate_edit_plan(request.editPlan, request.sourceClips, request.planTier))
        if not storage.source_exists(request.sourceObjectKey):
            validation_errors.append(
                EditPlanValidationIssue(field="sourceObjectKey", code="source_missing", message="Source video object was not found.")
            )
        if request.planTier == "free" and not request.editPlan.watermark.enabled:
            validation_errors.append(
                EditPlanValidationIssue(field="watermark.enabled", code="missing_free_watermark", message="Free plans must include the Hoopclips watermark.")
            )
        if request.planTier == "free" and (not request.editPlan.outro.enabled or request.editPlan.outro.durationSeconds <= 0):
            validation_errors.append(
                EditPlanValidationIssue(field="outro.enabled", code="missing_free_outro", message="Free plans must include a Hoopclips outro.")
            )
        if validation_errors:
            mark_failed(job, "invalid_edit_plan", validation_errors)
            return job.to_response()

        background_tasks.add_task(run_render_job, render_job_id)
        return job.to_response()

    @app.post("/v1/edit-jobs", responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}})
    async def create_edit_job(
        request: CreateEditJobRequest,
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            edit_job_id = "edit_" + uuid4().hex
            job = build_edit_job(request, edit_job_id)
            if job.validation_errors:
                first_error = job.validation_errors[0]
                raise EditingServiceError(400, first_error.code, first_error.message)
            edit_jobs[edit_job_id] = job
            return job.to_response()
        except EditingServiceError as error:
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
            job = require_job(render_job_id)
            require_owner(job, installId or x_hoops_install_id)
            if job.status != "rendered" or not job.output_object_key:
                raise EditingServiceError(409, "render_not_ready", "Render output is not ready for download yet.")
            download_url, expires_at = storage.presigned_get_url(job.output_object_key, job.render_job_id)
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
            render_job_id = render_jobs_by_edit_id.get(edit_job_id)
            if not render_job_id:
                raise EditingServiceError(404, "render_job_not_found", "Render job was not found.")
            job = require_job(render_job_id)
            require_owner(job, installId or x_hoops_install_id)
            if job.status != "rendered" or not job.output_object_key:
                raise EditingServiceError(409, "render_not_ready", "Render output is not ready for download yet.")
            download_url, expires_at = storage.presigned_get_url(job.output_object_key, job.render_job_id)
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
