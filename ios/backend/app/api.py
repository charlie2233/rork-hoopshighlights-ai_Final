from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4
from typing import Dict, Optional

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .editing import (
    CreateEditJobRequest,
    EditJobResponse,
    EditPlanResponse,
    ReviseEditJobRequest,
    StoredEditJob,
    build_edit_job,
    revise_edit_job,
)
from .job_store import FirestoreJobStore, InMemoryJobStore, JobStore
from .models import (
    APIError,
    CreateCloudAnalysisJobRequest,
    CreateCloudAnalysisJobResponse,
    ErrorResponse,
    JobStatus,
    PipelineError,
    StartCloudAnalysisJobRequest,
    StartCloudAnalysisJobResponse,
)
from .pipeline import run_analysis
from .storage import GCSStorageProvider, LocalStorageProvider, StorageProvider
from .task_dispatcher import CloudTasksDispatcher, InlineTaskDispatcher, TaskDispatcher


@dataclass(frozen=True)
class BackendRuntime:
    settings: Settings
    job_store: JobStore
    storage: StorageProvider
    dispatcher: TaskDispatcher


def create_router(settings: Optional[Settings] = None) -> APIRouter:
    resolved_settings = settings or get_settings()
    router = APIRouter()
    runtime: Optional[BackendRuntime] = None
    edit_jobs: Dict[str, StoredEditJob] = {}

    def _error_response(error: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=error.to_response().model_dump(exclude_none=True),
        )

    def _require_public_api_enabled() -> None:
        if not resolved_settings.public_api_enabled:
            raise APIError(status_code=404, error_code="not_found", error_message="Not found.")

    async def _require_job(job_id: str):
        assert runtime is not None
        job = await runtime.job_store.get_job(job_id)
        if job is None:
            raise APIError(status_code=404, error_code="job_not_found", error_message="Cloud analysis job was not found.")
        return job

    def _require_edit_job(edit_job_id: str) -> StoredEditJob:
        job = edit_jobs.get(edit_job_id)
        if job is None:
            raise APIError(status_code=404, error_code="edit_job_not_found", error_message="Cloud edit job was not found.")
        return job

    async def _process_job(job_id: str) -> None:
        assert runtime is not None
        source = None
        try:
            job = await _require_job(job_id)
            if job.status.is_terminal:
                return

            await runtime.job_store.mark_processing(job_id, stage="Analyzing in cloud", progress=0.62)
            job = await _require_job(job_id)
            source = await runtime.storage.materialize_source(job)
            result = await run_in_threadpool(run_analysis, job, resolved_settings, source.local_path)
            await runtime.job_store.mark_succeeded(job_id, result)
        except APIError as error:
            if error.error_code != "job_not_found":
                try:
                    await runtime.job_store.mark_failed(job_id, error.error_code, error.error_message)
                except Exception:
                    pass
        except PipelineError as error:
            try:
                await runtime.job_store.mark_failed(job_id, error.error_code, error.error_message)
            except Exception:
                pass
        except Exception:
            try:
                await runtime.job_store.mark_failed(job_id, "processing_error", "Cloud analysis failed unexpectedly.")
            except Exception:
                pass
        finally:
            if source is not None:
                source.cleanup()
            try:
                job = await runtime.job_store.get_job(job_id)
                if job is not None and job.status.is_terminal:
                    runtime.storage.cleanup(job)
            except Exception:
                pass

    def _create_runtime() -> BackendRuntime:
        if resolved_settings.is_local:
            job_store = InMemoryJobStore(resolved_settings)
            storage = LocalStorageProvider(resolved_settings)
            dispatcher = InlineTaskDispatcher(_process_job)
        else:
            job_store = FirestoreJobStore(resolved_settings)
            storage = GCSStorageProvider(resolved_settings)
            dispatcher = CloudTasksDispatcher(resolved_settings)
        return BackendRuntime(
            settings=resolved_settings,
            job_store=job_store,
            storage=storage,
            dispatcher=dispatcher,
        )

    runtime = _create_runtime()

    @router.post(
        "/v1/analysis/jobs",
        response_model=CreateCloudAnalysisJobResponse,
        responses={429: {"model": ErrorResponse}},
    )
    async def create_job(request: CreateCloudAnalysisJobRequest):
        assert runtime is not None
        try:
            _require_public_api_enabled()
            if request.durationSeconds > resolved_settings.max_duration_seconds:
                raise APIError(400, "unsupported_duration", "Videos longer than 30 minutes are not supported in cloud analysis right now.")
            if request.fileSizeBytes > resolved_settings.max_file_size_bytes:
                raise APIError(400, "file_too_large", "Videos larger than 500 MB are not supported in cloud analysis v1.")

            quota_remaining = await runtime.job_store.reserve_quota(request.installId)
            job_id = uuid4().hex
            upload = runtime.storage.prepare_upload(job_id, request.filename, request.contentType)
            job = await runtime.job_store.create_job(job_id, request, upload, quota_remaining)

            return CreateCloudAnalysisJobResponse(
                jobId=job.job_id,
                uploadUrl=upload.upload_url,
                uploadHeaders=upload.upload_headers,
                expiresAt=upload.expires_at,
                pollAfterSeconds=resolved_settings.default_poll_after_seconds,
                quotaRemainingToday=quota_remaining,
            )
        except APIError as error:
            return _error_response(error)

    if resolved_settings.enable_local_upload_emulation:

        @router.put(
            "/v1/internal/uploads/{job_id}",
            status_code=204,
            responses={404: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
        )
        async def upload_video(job_id: str, request: Request):
            assert runtime is not None
            try:
                job = await _require_job(job_id)
                payload = await request.body()
                if not payload:
                    raise APIError(400, "empty_upload", "The uploaded file body was empty.")
                if len(payload) > resolved_settings.max_file_size_bytes:
                    raise APIError(413, "file_too_large", "Videos larger than 500 MB are not supported in cloud analysis v1.")

                storage_path = runtime.storage.accept_local_upload(job, payload)
                await runtime.job_store.mark_uploaded(job_id, storage_path)
                return Response(status_code=204)
            except APIError as error:
                return _error_response(error)

    @router.post(
        "/v1/analysis/jobs/{job_id}/start",
        response_model=StartCloudAnalysisJobResponse,
        responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def start_job(job_id: str, request: StartCloudAnalysisJobRequest):
        assert runtime is not None
        try:
            _require_public_api_enabled()
            job = await _require_job(job_id)
            if job.install_id != request.installId:
                raise APIError(403, "install_mismatch", "Install ID does not own this analysis job.")
            if job.status != JobStatus.CREATED:
                return StartCloudAnalysisJobResponse(jobId=job.job_id, status=job.status.value)
            if not await runtime.storage.object_exists(job):
                raise APIError(400, "upload_missing", "Upload is missing. Complete the signed upload before starting analysis.")

            job = await runtime.job_store.mark_queued(job_id)
            await runtime.dispatcher.enqueue_process(job)
            return StartCloudAnalysisJobResponse(jobId=job.job_id, status=job.status.value)
        except APIError as error:
            return _error_response(error)

    @router.get(
        "/v1/analysis/jobs/{job_id}",
        responses={404: {"model": ErrorResponse}},
    )
    async def get_job(job_id: str):
        try:
            _require_public_api_enabled()
            job = await _require_job(job_id)
            return job.to_job_response()
        except APIError as error:
            return _error_response(error)

    @router.delete(
        "/v1/analysis/jobs/{job_id}",
        status_code=204,
        responses={404: {"model": ErrorResponse}},
    )
    async def delete_job(job_id: str):
        assert runtime is not None
        try:
            _require_public_api_enabled()
            job = await _require_job(job_id)
            await runtime.job_store.mark_expired(job_id)
            runtime.storage.cleanup(job)
            return Response(status_code=204)
        except APIError as error:
            return _error_response(error)

    @router.post(
        "/v1/edit-jobs",
        response_model=EditJobResponse,
        responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def create_edit_job(request: CreateEditJobRequest):
        try:
            _require_public_api_enabled()
            edit_job_id = "edit_" + uuid4().hex
            job = build_edit_job(request, edit_job_id)
            if job.validation_errors:
                first_error = job.validation_errors[0]
                raise APIError(400, first_error.code, first_error.message)
            edit_jobs[edit_job_id] = job
            return job.to_response()
        except APIError as error:
            return _error_response(error)

    @router.get(
        "/v1/edit-jobs/{edit_job_id}",
        response_model=EditJobResponse,
        responses={404: {"model": ErrorResponse}},
    )
    async def get_edit_job(edit_job_id: str):
        try:
            _require_public_api_enabled()
            return _require_edit_job(edit_job_id).to_response()
        except APIError as error:
            return _error_response(error)

    @router.get(
        "/v1/edit-jobs/{edit_job_id}/plan",
        response_model=EditPlanResponse,
        responses={404: {"model": ErrorResponse}},
    )
    async def get_edit_job_plan(edit_job_id: str):
        try:
            _require_public_api_enabled()
            return _require_edit_job(edit_job_id).to_plan_response()
        except APIError as error:
            return _error_response(error)

    @router.post(
        "/v1/edit-jobs/{edit_job_id}/revise",
        response_model=EditPlanResponse,
        responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def revise_edit_job_plan(edit_job_id: str, request: ReviseEditJobRequest):
        try:
            _require_public_api_enabled()
            job = _require_edit_job(edit_job_id)
            revised = revise_edit_job(job, request)
            if revised.validation_errors:
                first_error = revised.validation_errors[0]
                raise APIError(400, first_error.code, first_error.message)
            edit_jobs[edit_job_id] = revised
            return revised.to_plan_response()
        except APIError as error:
            return _error_response(error)

    @router.post(
        "/v1/internal/process/{job_id}",
        responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def process_job(job_id: str, x_hoops_internal_secret: Optional[str] = Header(default=None)):
        try:
            if resolved_settings.internal_process_secret and x_hoops_internal_secret != resolved_settings.internal_process_secret:
                raise APIError(403, "forbidden", "Invalid internal processing secret.")
            await _require_job(job_id)
            await _process_job(job_id)
            job = await _require_job(job_id)
            return {"jobId": job.job_id, "status": job.status.value}
        except APIError as error:
            return _error_response(error)

    return router
