from __future__ import annotations

from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .config import get_settings
from .job_store import InMemoryJobStore
from .models import (
    APIError,
    CreateCloudAnalysisJobRequest,
    CreateCloudAnalysisJobResponse,
    ErrorResponse,
    JobStatus,
    StartCloudAnalysisJobRequest,
    StartCloudAnalysisJobResponse,
)
from .pipeline import run_analysis
from .storage import StorageManager


settings = get_settings()
job_store = InMemoryJobStore(settings)
storage = StorageManager(settings)
router = APIRouter()


def _error_response(error: APIError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content=error.to_response().model_dump(exclude_none=True))


async def _require_job(job_id: str):
    job = await job_store.get_job(job_id)
    if job is None:
        raise APIError(status_code=404, error_code="job_not_found", error_message="Cloud analysis job was not found.")
    return job


async def _process_job(job_id: str) -> None:
    try:
        job = await _require_job(job_id)
        await job_store.mark_processing(job_id, stage="Analyzing in cloud", progress=0.62)
        result = await run_in_threadpool(run_analysis, job, settings)
        await job_store.mark_succeeded(job_id, result)
    except APIError:
        return
    except Exception as error:
        if hasattr(error, "error_code") and hasattr(error, "error_message"):
            await job_store.mark_failed(job_id, error.error_code, error.error_message)
        else:
            await job_store.mark_failed(job_id, "processing_error", "Cloud analysis failed unexpectedly.")
    finally:
        job = await job_store.get_job(job_id)
        if job is not None and job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.EXPIRED}:
            storage.cleanup(job)


@router.post(
    "/v1/analysis/jobs",
    response_model=CreateCloudAnalysisJobResponse,
    responses={429: {"model": ErrorResponse}},
)
async def create_job(request: CreateCloudAnalysisJobRequest):
    try:
        if request.durationSeconds > settings.max_duration_seconds:
            raise APIError(400, "unsupported_duration", "Videos longer than 10 minutes are not supported in cloud analysis v1.")
        if request.fileSizeBytes > settings.max_file_size_bytes:
            raise APIError(400, "file_too_large", "Videos larger than 500 MB are not supported in cloud analysis v1.")

        quota_remaining = await job_store.reserve_quota(request.installId)
        job_id = uuid4().hex
        upload = storage.prepare_upload(job_id, request.filename, request.contentType)
        job = await job_store.create_job(job_id, request, upload)
        job.quota_remaining_today = quota_remaining

        return CreateCloudAnalysisJobResponse(
            jobId=job.job_id,
            uploadUrl=upload.upload_url,
            uploadHeaders=upload.upload_headers,
            expiresAt=job.expires_at,
            pollAfterSeconds=settings.default_poll_after_seconds,
            quotaRemainingToday=quota_remaining,
        )
    except APIError as error:
        return _error_response(error)


@router.put(
    "/v1/internal/uploads/{job_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
async def upload_video(job_id: str, request: Request):
    try:
        job = await _require_job(job_id)
        payload = await request.body()
        if not payload:
            raise APIError(400, "empty_upload", "The uploaded file body was empty.")
        if len(payload) > settings.max_file_size_bytes:
            raise APIError(413, "file_too_large", "Videos larger than 500 MB are not supported in cloud analysis v1.")

        storage_path = storage.write_upload(job, payload)
        await job_store.mark_uploaded(job_id, storage_path)
        return Response(status_code=204)
    except APIError as error:
        return _error_response(error)


@router.post(
    "/v1/analysis/jobs/{job_id}/start",
    response_model=StartCloudAnalysisJobResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def start_job(job_id: str, request: StartCloudAnalysisJobRequest, background_tasks: BackgroundTasks):
    try:
        job = await _require_job(job_id)
        if job.install_id != request.installId:
            raise APIError(403, "install_mismatch", "Install ID does not own this analysis job.")
        if not storage.object_exists(job):
            raise APIError(400, "upload_missing", "Upload is missing. Complete the signed upload before starting analysis.")

        if job.status in {JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.SUCCEEDED}:
            return StartCloudAnalysisJobResponse(jobId=job.job_id, status=job.status.value)

        await job_store.mark_queued(job_id)
        background_tasks.add_task(_process_job, job_id)
        return StartCloudAnalysisJobResponse(jobId=job.job_id, status=JobStatus.QUEUED.value)
    except APIError as error:
        return _error_response(error)


@router.get(
    "/v1/analysis/jobs/{job_id}",
    responses={404: {"model": ErrorResponse}},
)
async def get_job(job_id: str):
    try:
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
    try:
        job = await _require_job(job_id)
        storage.cleanup(job)
        await job_store.mark_expired(job_id)
        return Response(status_code=204)
    except APIError as error:
        return _error_response(error)


@router.post(
    "/v1/internal/process/{job_id}",
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def process_job(job_id: str, x_hoops_internal_secret: Optional[str] = Header(default=None)):
    try:
        if settings.internal_process_secret and x_hoops_internal_secret != settings.internal_process_secret:
            raise APIError(403, "forbidden", "Invalid internal processing secret.")
        await _require_job(job_id)
        await _process_job(job_id)
        job = await _require_job(job_id)
        return {"jobId": job.job_id, "status": job.status.value}
    except APIError as error:
        return _error_response(error)
