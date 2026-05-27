from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import httpx
import os
from pathlib import Path
import re
import tempfile
from uuid import uuid4
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Header, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
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
    MaterializedSource,
    ScanCloudAnalysisSourceRequest,
    ScanCloudAnalysisTeamsRequest,
    ScanCloudAnalysisTeamsResponse,
    StartCloudAnalysisJobRequest,
    StartCloudAnalysisJobResponse,
    StoredJob,
    TeamSelection,
    now_utc,
)
from .pipeline import build_team_quick_scan_candidate_clips, run_analysis
from .render_storage import RenderStorage
from .renderers.ffmpeg_renderer import FfmpegRenderer
from .rendering import (
    DownloadUrlResponse,
    RenderJobResponse,
    StartRenderRequest,
    StoredRenderJob,
    new_render_job,
    render_log_payload,
    validate_render_request,
)
from .storage import GCSStorageProvider, LocalStorageProvider, StorageProvider
from .task_dispatcher import CloudTasksDispatcher, InlineTaskDispatcher, TaskDispatcher
from .team_quick_scan import apply_team_quick_scan


async def materialize_remote_source(
    source_url: str,
    filename: str,
    max_file_size_bytes: int,
    upload_root: Path,
) -> MaterializedSource:
    if not source_url.startswith(("https://", "http://")):
        raise APIError(400, "invalid_source_url", "Source video URL is invalid.")

    temp_dir = Path(tempfile.mkdtemp(prefix="hoops-source-url-", dir=str(upload_root)))
    local_path = temp_dir / _sanitize_remote_filename(filename)
    materialized = MaterializedSource(local_path=local_path, cleanup_after_use=True)
    written = 0

    try:
        timeout = httpx.Timeout(90.0, connect=15.0)
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            async with client.stream("GET", source_url) as response:
                if response.status_code >= 400:
                    raise APIError(400, "source_unavailable", "Source video could not be fetched for team scan.")
                with local_path.open("wb") as output:
                    async for chunk in response.aiter_bytes():
                        if not chunk:
                            continue
                        written += len(chunk)
                        if written > max_file_size_bytes:
                            raise APIError(413, "file_too_large", "Videos larger than 500 MB are not supported in cloud analysis v1.")
                        output.write(chunk)

        if written <= 0:
            raise APIError(400, "empty_source", "Source video was empty.")
        return materialized
    except APIError:
        materialized.cleanup()
        raise
    except httpx.TimeoutException as error:
        materialized.cleanup()
        raise APIError(504, "source_fetch_timeout", "Source video fetch timed out before team scan.") from error
    except httpx.HTTPError as error:
        materialized.cleanup()
        raise APIError(400, "source_unavailable", "Source video could not be fetched for team scan.") from error


def _sanitize_remote_filename(filename: str) -> str:
    name = Path(filename).name or "source.mp4"
    normalized = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return normalized[:120] or "source.mp4"


@dataclass(frozen=True)
class BackendRuntime:
    settings: Settings
    job_store: JobStore
    storage: StorageProvider
    dispatcher: TaskDispatcher
    render_storage: RenderStorage


def create_router(settings: Optional[Settings] = None) -> APIRouter:
    resolved_settings = settings or get_settings()
    router = APIRouter()
    runtime: Optional[BackendRuntime] = None
    edit_jobs: Dict[str, StoredEditJob] = {}
    render_jobs: Dict[str, StoredRenderJob] = {}
    render_jobs_by_edit_id: Dict[str, str] = {}

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

    def _require_render_job(render_job_id: str) -> StoredRenderJob:
        job = render_jobs.get(render_job_id)
        if job is None:
            raise APIError(status_code=404, error_code="render_job_not_found", error_message="Cloud render job was not found.")
        return job

    def _require_edit_owner(job: StoredEditJob, install_id: Optional[str]) -> None:
        if not install_id or job.install_id != install_id:
            raise APIError(403, "install_mismatch", "Install ID does not own this edit job.")

    def _request_install_id(query_install_id: Optional[str], header_install_id: Optional[str]) -> Optional[str]:
        return query_install_id or header_install_id

    def _require_internal_process_secret(secret: Optional[str]) -> None:
        if resolved_settings.internal_process_secret and secret != resolved_settings.internal_process_secret:
            raise APIError(403, "forbidden", "Invalid internal processing secret.")

    def _validate_scan_backed_team_selection(job: StoredJob, selection: Optional[TeamSelection]) -> None:
        if selection is None or selection.mode != "team":
            return
        if not job.detected_teams:
            raise APIError(
                400,
                "team_scan_required",
                "Run the cloud team scan and choose one of the detected jersey-color teams before selected-team analysis.",
            )

        selected_team_id = selection.teamId.strip() if selection.teamId else None
        selected_color = selection.colorLabel.strip().lower() if selection.colorLabel else None
        for team in job.detected_teams:
            team_id_matches = bool(selected_team_id and team.teamId == selected_team_id)
            color_matches = bool(selected_color and team.colorLabel and team.colorLabel.strip().lower() == selected_color)
            if team_id_matches or color_matches:
                return

        raise APIError(
            400,
            "team_selection_unavailable",
            "Selected team must match a jersey-color team from the cloud scan.",
        )

    def _now():
        return now_utc()

    def _download_url_expires_at():
        ttl_seconds = int(os.getenv("HOOPS_RENDER_DOWNLOAD_TTL_SECONDS", "900"))
        return now_utc() + timedelta(seconds=ttl_seconds)

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

    def _mark_render_failed(
        render_job: StoredRenderJob,
        reason: str,
        validation_errors: Optional[list] = None,
    ) -> None:
        assert runtime is not None
        render_job.status = "failed"
        render_job.failure_reason = reason
        render_job.validation_errors = validation_errors or []
        render_job.updated_at = _now()
        render_job.render_log_object_key = "edits/{edit_job_id}/render_jobs/{render_job_id}/render_log.json".format(
            edit_job_id=render_job.edit_job_id,
            render_job_id=render_job.render_job_id,
        )
        try:
            runtime.render_storage.put_json(
                render_job.render_log_object_key,
                render_log_payload(
                    render_job,
                    "failed",
                    {
                        "failureReason": reason,
                        "validationErrors": [error.model_dump() for error in render_job.validation_errors],
                    },
                ),
            )
        except Exception:
            pass

    def _run_render_job(edit_job_id: str, render_job_id: str) -> None:
        assert runtime is not None
        edit_job = _require_edit_job(edit_job_id)
        render_job = _require_render_job(render_job_id)
        source = None
        try:
            render_job.status = "rendering"
            render_job.updated_at = _now()
            source = runtime.render_storage.materialize_source(edit_job.request.sourceObjectKey)
            with tempfile.TemporaryDirectory(prefix="hoops-render-", dir=str(resolved_settings.upload_root)) as temp_dir:
                result = FfmpegRenderer().render(edit_job.plan, source.local_path, Path(temp_dir))
                plan_key = f"edits/{edit_job_id}/plan.json"
                output_key = f"edits/{edit_job_id}/render_jobs/{render_job_id}/final.mp4"
                log_key = f"edits/{edit_job_id}/render_jobs/{render_job_id}/render_log.json"
                runtime.render_storage.put_json(plan_key, edit_job.plan.model_dump_json(indent=2))
                runtime.render_storage.put_file(output_key, result.output_path, "video/mp4")
                render_job.status = "rendered"
                render_job.output_object_key = output_key
                render_job.render_log_object_key = log_key
                render_job.duration_seconds = result.duration_seconds
                render_job.updated_at = _now()
                runtime.render_storage.put_json(
                    log_key,
                    render_log_payload(
                        render_job,
                        "rendered",
                        {
                            "outputObjectKey": output_key,
                            "durationSeconds": result.duration_seconds,
                            "aspectRatio": edit_job.plan.aspectRatio,
                            "clipCount": len(edit_job.plan.clips),
                            "ffmpeg": result.render_log,
                        },
                    ),
                )
        except APIError as error:
            _mark_render_failed(render_job, error.error_code)
        except Exception:
            _mark_render_failed(render_job, "render_failed")
        finally:
            if source is not None:
                source.cleanup()

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
            render_storage=RenderStorage(resolved_settings),
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
        "/v1/analysis/jobs/{job_id}/team-scan",
        response_model=ScanCloudAnalysisTeamsResponse,
        responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def scan_job_teams(job_id: str, request: ScanCloudAnalysisTeamsRequest):
        assert runtime is not None
        source = None
        try:
            _require_public_api_enabled()
            job = await _require_job(job_id)
            if job.install_id != request.installId:
                raise APIError(403, "install_mismatch", "Install ID does not own this analysis job.")
            if job.status != JobStatus.CREATED:
                raise APIError(400, "job_already_started", "Team scan is only available before analysis starts.")
            if not await runtime.storage.object_exists(job):
                raise APIError(400, "upload_missing", "Upload is missing. Complete the signed upload before scanning teams.")

            await runtime.job_store.update_job(job_id, stage="Scanning teams", progress=max(job.progress, 0.18))
            job = await _require_job(job_id)
            source = await runtime.storage.materialize_source(job)
            candidate_clips = await run_in_threadpool(
                build_team_quick_scan_candidate_clips,
                source.local_path,
                job.duration_seconds,
                resolved_settings,
            )
            _, detected_teams, applied = await run_in_threadpool(
                apply_team_quick_scan,
                source.local_path,
                job.duration_seconds,
                candidate_clips,
                resolved_settings,
            )
            status = "scanned" if applied and detected_teams else "unavailable"
            await runtime.job_store.update_job(
                job_id,
                stage="Team scan complete",
                progress=max(job.progress, 0.22),
                detected_teams=detected_teams,
                team_scan_status=status,
            )
            return ScanCloudAnalysisTeamsResponse(jobId=job.job_id, status=status, detectedTeams=detected_teams)
        except APIError as error:
            return _error_response(error)
        finally:
            if source is not None:
                source.cleanup()

    @router.post(
        "/v1/team-scan",
        response_model=ScanCloudAnalysisTeamsResponse,
        responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    )
    async def scan_source_teams(
        request: ScanCloudAnalysisSourceRequest,
        x_hoops_inference_secret: Optional[str] = Header(default=None),
        x_hoops_internal_secret: Optional[str] = Header(default=None),
    ):
        source = None
        try:
            _require_internal_process_secret(x_hoops_inference_secret or x_hoops_internal_secret)
            source = await materialize_remote_source(
                request.sourceUrl,
                request.filename,
                resolved_settings.max_file_size_bytes,
                resolved_settings.upload_root,
            )
            candidate_clips = await run_in_threadpool(
                build_team_quick_scan_candidate_clips,
                source.local_path,
                request.durationSeconds,
                resolved_settings,
            )
            _, detected_teams, applied = await run_in_threadpool(
                apply_team_quick_scan,
                source.local_path,
                request.durationSeconds,
                candidate_clips,
                resolved_settings,
            )
            status = "scanned" if applied and detected_teams else "unavailable"
            return ScanCloudAnalysisTeamsResponse(jobId=request.jobId, status=status, detectedTeams=detected_teams)
        except APIError as error:
            return _error_response(error)
        finally:
            if source is not None:
                source.cleanup()

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

            effective_selection = request.teamSelection if request.teamSelection is not None else job.team_selection
            _validate_scan_backed_team_selection(job, effective_selection)
            if request.teamSelection is not None:
                job = await runtime.job_store.update_job(job_id, team_selection=request.teamSelection)
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
            render_jobs_by_edit_id.pop(edit_job_id, None)
            return revised.to_plan_response()
        except APIError as error:
            return _error_response(error)

    @router.post(
        "/v1/edit-jobs/{edit_job_id}/render",
        response_model=RenderJobResponse,
        responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def render_edit_job(edit_job_id: str, request: StartRenderRequest, background_tasks: BackgroundTasks):
        assert runtime is not None
        try:
            _require_public_api_enabled()
            edit_job = _require_edit_job(edit_job_id)
            _require_edit_owner(edit_job, request.installId)

            existing_render_id = render_jobs_by_edit_id.get(edit_job_id)
            if existing_render_id:
                existing = _require_render_job(existing_render_id)
                if existing.status in {"render_requested", "rendering", "rendered"}:
                    return existing.to_response(edit_job.plan.version)

            render_job_id = "render_" + uuid4().hex
            trace_id = "trace_" + uuid4().hex
            render_job = new_render_job(edit_job, render_job_id, trace_id)
            render_jobs[render_job_id] = render_job
            render_jobs_by_edit_id[edit_job_id] = render_job_id

            source_exists = runtime.render_storage.source_exists(edit_job.request.sourceObjectKey)
            validation_errors = validate_render_request(edit_job, source_exists)
            if validation_errors:
                _mark_render_failed(render_job, "invalid_edit_plan", validation_errors)
                return render_job.to_response(edit_job.plan.version)

            background_tasks.add_task(_run_render_job, edit_job_id, render_job_id)
            return render_job.to_response(edit_job.plan.version)
        except APIError as error:
            return _error_response(error)

    @router.get(
        "/v1/edit-jobs/{edit_job_id}/render-status",
        response_model=RenderJobResponse,
        responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def get_render_status(
        edit_job_id: str,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
    ):
        try:
            _require_public_api_enabled()
            edit_job = _require_edit_job(edit_job_id)
            _require_edit_owner(edit_job, _request_install_id(installId, x_hoops_install_id))
            render_job_id = render_jobs_by_edit_id.get(edit_job_id)
            if not render_job_id:
                raise APIError(404, "render_job_not_found", "Cloud render job was not found.")
            return _require_render_job(render_job_id).to_response(edit_job.plan.version)
        except APIError as error:
            return _error_response(error)

    @router.get(
        "/v1/edit-jobs/{edit_job_id}/download-url",
        response_model=DownloadUrlResponse,
        responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    )
    async def get_render_download_url(
        edit_job_id: str,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
    ):
        assert runtime is not None
        try:
            _require_public_api_enabled()
            edit_job = _require_edit_job(edit_job_id)
            _require_edit_owner(edit_job, _request_install_id(installId, x_hoops_install_id))
            render_job_id = render_jobs_by_edit_id.get(edit_job_id)
            if not render_job_id:
                raise APIError(404, "render_job_not_found", "Cloud render job was not found.")
            render_job = _require_render_job(render_job_id)
            if render_job.status != "rendered" or not render_job.output_object_key:
                raise APIError(409, "render_not_ready", "Render output is not ready for download yet.")
            return DownloadUrlResponse(
                editJobId=edit_job_id,
                renderJobId=render_job_id,
                downloadUrl=runtime.render_storage.presigned_get_url(render_job.output_object_key, token=render_job_id),
                outputObjectKey=render_job.output_object_key,
                expiresAt=_download_url_expires_at(),
            )
        except APIError as error:
            return _error_response(error)

    @router.get(
        "/v1/internal/render-downloads/{render_job_id}/final.mp4",
        responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def download_local_render(render_job_id: str):
        assert runtime is not None
        try:
            render_job = _require_render_job(render_job_id)
            if render_job.status != "rendered" or not render_job.output_object_key:
                raise APIError(404, "render_output_not_found", "Render output was not found.")
            output_path = runtime.render_storage.local_path_for_object(render_job.output_object_key)
            if not output_path.exists():
                raise APIError(404, "render_output_not_found", "Render output was not found.")
            return FileResponse(output_path, media_type="video/mp4", filename="Hoopclips.mp4")
        except APIError as error:
            return _error_response(error)

    @router.post(
        "/v1/internal/process/{job_id}",
        responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def process_job(job_id: str, x_hoops_internal_secret: Optional[str] = Header(default=None)):
        try:
            _require_internal_process_secret(x_hoops_internal_secret)
            await _require_job(job_id)
            await _process_job(job_id)
            job = await _require_job(job_id)
            return {"jobId": job.job_id, "status": job.status.value}
        except APIError as error:
            return _error_response(error)

    return router
