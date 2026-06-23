from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, Header, Query, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse

from .backend_imports import ensure_ios_backend_on_path
from .config import EditingSettings, get_settings
from .gpt_reranker import (
    GPTHighlightRerankerSettings,
    expand_shot_candidate_windows_from_source_path,
    request_gpt_edit_plan_patch_attempt,
    rerank_edit_request_with_gpt,
    with_gpt_fallback_summary,
)
from .models import (
    AIWorkReceipt,
    AIWorkTimeline,
    CreateEditJobRequest,
    CreateRenderJobRequest,
    DownloadUrlResponse,
    EditRevisionListResponse,
    ErrorResponse,
    RenderJobListResponse,
    RenderJobResponse,
    StartEditJobRenderRequest,
    StartEditRevisionRenderRequest,
    StoredRenderJob,
    build_ai_work_receipt,
    build_ai_work_timeline,
    now_utc,
    parse_datetime,
    render_log_payload,
)
from .render_state import DurableRenderStateStore
from .render_storage import EditingServiceError, RenderStorage

ensure_ios_backend_on_path()

from app.editing import (  # noqa: E402
    AIEditFeatureFlags,
    EditPlan,
    EditPlanValidationIssue,
    EditRevisionResponse,
    ReviseEditJobRequest,
    StoredEditJob,
    build_edit_job,
    build_revision_response,
    default_ai_edit_feature_flags,
    estimate_render_cost,
    get_plan_tier_policy,
    get_template_pack,
    policy_summary_for_client,
    source_clips_for_edit_request,
    validate_edit_plan,
)
from app.config import get_settings as get_analysis_settings  # noqa: E402
from app.models import (  # noqa: E402
    APIError,
    CloudAnalysisResult,
    InferenceDispatchRequest,
    JobStatus,
    MaterializedSource,
    PipelineError,
    ScanCloudAnalysisSourceRequest,
    ScanCloudAnalysisTeamsResponse,
    StoredJob,
)
from app.pipeline import run_analysis  # noqa: E402
from app.renderers.ffmpeg_renderer import FfmpegRenderer, ffmpeg_diagnostics  # noqa: E402
from app.team_quick_scan import apply_team_quick_scan, team_quick_prescan_settings  # noqa: E402


def materialize_team_scan_source(
    source_url: str,
    filename: str,
    max_file_size_bytes: int,
    upload_root: Path,
) -> MaterializedSource:
    if not source_url.startswith(("https://", "http://")):
        raise EditingServiceError(400, "invalid_source_url", "Source video URL is invalid.")

    temp_dir = Path(tempfile.mkdtemp(prefix="hoops-team-scan-", dir=str(upload_root)))
    local_path = temp_dir / sanitize_team_scan_filename(filename)
    materialized = MaterializedSource(local_path=local_path, cleanup_after_use=True)
    written = 0
    try:
        request = Request(source_url, headers={"User-Agent": "HoopClipsEditingService/1.0"})
        with urlopen(request, timeout=90) as response:
            with local_path.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_file_size_bytes:
                        raise EditingServiceError(
                            413,
                            "file_too_large",
                            "Videos larger than 500 MB are not supported for team scan.",
                        )
                    output.write(chunk)
        if written <= 0:
            raise EditingServiceError(400, "empty_source", "Source video was empty.")
        return materialized
    except EditingServiceError:
        materialized.cleanup()
        raise
    except HTTPError as error:
        materialized.cleanup()
        raise EditingServiceError(400, "source_unavailable", "Source video could not be fetched for team scan.") from error
    except (URLError, TimeoutError, OSError) as error:
        materialized.cleanup()
        raise EditingServiceError(400, "source_unavailable", "Source video could not be fetched for team scan.") from error


def sanitize_team_scan_filename(filename: str) -> str:
    name = Path(filename).name or "source.mp4"
    normalized = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return normalized[:120] or "source.mp4"


def post_inference_callback(callback_url: str, callback_secret: str, payload: dict[str, Any]) -> None:
    headers = {
        "content-type": "application/json",
        "User-Agent": "HoopClipsEditingService/1.0",
        "x-hoops-inference-secret": callback_secret,
        "x-request-id": str(payload.get("requestId") or ""),
        "x-trace-id": str(payload.get("traceId") or ""),
        "x-hoops-upload-trace-id": str(payload.get("uploadTraceId") or ""),
        "x-hoops-inference-attempt-id": str(payload.get("inferenceAttemptId") or ""),
    }
    request = Request(callback_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            if response.status >= 400:
                raise EditingServiceError(502, f"callback_http_{response.status}", "Inference callback was rejected by the control plane.")
    except HTTPError as error:
        raise EditingServiceError(502, f"callback_http_{error.code}", "Inference callback was rejected by the control plane.") from error
    except (URLError, TimeoutError, OSError) as error:
        raise EditingServiceError(502, "callback_failed", "Inference callback could not reach the control plane.") from error


def post_inference_heartbeat(callback_url: str, callback_secret: str, job_id: str, payload: dict[str, Any]) -> None:
    heartbeat_url = urljoin(callback_url, f"/internal/inference/heartbeat/{quote(job_id, safe='')}")
    headers = {
        "content-type": "application/json",
        "User-Agent": "HoopClipsEditingService/1.0",
        "x-hoops-inference-secret": callback_secret,
        "x-request-id": str(payload.get("requestId") or ""),
        "x-trace-id": str(payload.get("traceId") or ""),
        "x-hoops-upload-trace-id": str(payload.get("uploadTraceId") or ""),
        "x-hoops-inference-attempt-id": str(payload.get("inferenceAttemptId") or ""),
    }
    request = Request(heartbeat_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            if response.status >= 400:
                raise EditingServiceError(502, f"heartbeat_http_{response.status}", "Inference heartbeat was rejected by the control plane.")
    except HTTPError as error:
        raise EditingServiceError(502, f"heartbeat_http_{error.code}", "Inference heartbeat was rejected by the control plane.") from error
    except (URLError, TimeoutError, OSError) as error:
        raise EditingServiceError(502, "heartbeat_failed", "Inference heartbeat could not reach the control plane.") from error


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
    gpt_editor_enabled = flag(
        "HOOPS_AI_CLIP_GPT_EDITOR_ENABLED",
        flag(
            "HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED",
            flag("HOOPS_GPT_HIGHLIGHT_RERANK_ENABLED", defaults.aiClipGptEditorEnabled),
        ),
    )
    return AIEditFeatureFlags(
        aiEditEnabled=flag("HOOPS_AI_EDIT_ENABLED", defaults.aiEditEnabled),
        aiEditLiveRenderEnabled=flag("HOOPS_AI_EDIT_LIVE_RENDER_ENABLED", defaults.aiEditLiveRenderEnabled),
        aiEditRevisionEnabled=flag("HOOPS_AI_EDIT_REVISION_ENABLED", defaults.aiEditRevisionEnabled),
        aiEditTemplatePackEnabled=flag("HOOPS_AI_EDIT_TEMPLATE_PACK_ENABLED", defaults.aiEditTemplatePackEnabled),
        aiEditMaxDailyRenders=parsed_max_daily,
        aiEditFreeWatermarkRequired=flag("HOOPS_AI_EDIT_FREE_WATERMARK_REQUIRED", defaults.aiEditFreeWatermarkRequired),
        aiEditProExportsEnabled=flag("HOOPS_AI_EDIT_PRO_EXPORTS_ENABLED", defaults.aiEditProExportsEnabled),
        aiClipGptEditorEnabled=gpt_editor_enabled,
        aiClipGptPlanEditEnabled=flag("HOOPS_AI_CLIP_GPT_PLAN_EDIT_ENABLED", defaults.aiClipGptPlanEditEnabled),
        aiClipGptRevisionEnabled=flag("HOOPS_AI_CLIP_GPT_REVISION_ENABLED", defaults.aiClipGptRevisionEnabled),
        gptHighlightRerankerEnabled=gpt_editor_enabled,
    )


def create_app(settings: Optional[EditingSettings] = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    storage = RenderStorage(resolved_settings)
    render_state_store = DurableRenderStateStore(storage)
    app = FastAPI(title=resolved_settings.service_name, version=resolved_settings.backend_model_version)
    render_jobs: Dict[str, StoredRenderJob] = {}
    render_jobs_by_edit_id: Dict[str, str] = {}
    render_jobs_by_idempotency_key: Dict[str, str] = {}
    render_requests: Dict[str, CreateRenderJobRequest] = {}
    render_recovery_scheduled: set[str] = set()
    render_created_by_install: Dict[str, list] = {}
    edit_jobs: Dict[str, StoredEditJob] = {}
    edit_revisions: Dict[str, list[EditRevisionResponse]] = {}
    edit_revisions_by_id: Dict[str, EditRevisionResponse] = {}
    feature_flags = resolve_feature_flags()
    gpt_reranker_settings = GPTHighlightRerankerSettings.from_env()
    instance_id = f"editing_{uuid4().hex[:12]}"

    def error_response(error: EditingServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=ErrorResponse(errorCode=error.error_code, errorMessage=error.error_message, failureReason=error.error_message).model_dump(exclude_none=True),
        )

    def require_secret(value: Optional[str]) -> None:
        expected = resolved_settings.shared_secret
        if expected and value != expected:
            raise EditingServiceError(401, "invalid_editing_secret", "Invalid editing service secret.")

    def materialize_dispatch_source(
        storage_key: Optional[str],
        source_url: Optional[str],
        filename: str,
        max_file_size_bytes: int,
    ) -> MaterializedSource:
        object_error: Optional[EditingServiceError] = None
        if storage_key:
            try:
                return storage.materialize_source(storage_key)
            except EditingServiceError as error:
                object_error = error
                if not source_url:
                    raise

        if source_url:
            return materialize_team_scan_source(
                source_url,
                filename,
                max_file_size_bytes,
                resolved_settings.upload_root,
            )

        if object_error is not None:
            raise object_error
        raise EditingServiceError(400, "source_missing", "Source video object or signed URL is required.")

    def analysis_result_confidence(result: CloudAnalysisResult) -> float:
        if not result.clips:
            return 0.0
        return round(sum(clip.confidence for clip in result.clips) / len(result.clips), 4)

    def dispatch_job_from_request(request: InferenceDispatchRequest, job_ttl_seconds: int) -> StoredJob:
        created_at = now_utc()
        return StoredJob(
            job_id=request.jobId,
            install_id=request.installId,
            filename=request.filename,
            content_type=request.contentType or "video/mp4",
            file_size_bytes=request.fileSizeBytes or 1,
            duration_seconds=request.durationSeconds,
            app_version=request.appVersion,
            analysis_version=request.analysisVersion,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=job_ttl_seconds),
            object_key=request.sourceObjectKey,
            team_selection=request.teamSelection,
            status=JobStatus.PROCESSING,
            progress=0.62,
            stage="Analyzing in cloud",
        )

    def inference_callback_payload(
        request: InferenceDispatchRequest,
        *,
        status: str,
        stage: str,
        progress: float,
        result: Optional[CloudAnalysisResult] = None,
        failure_reason: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jobId": request.jobId,
            "requestId": request.requestId,
            "status": status,
            "stage": stage,
            "progress": progress,
            "schemaVersion": request.schemaVersion,
            "modelVersion": request.modelVersion,
            "failureReason": failure_reason,
            "uploadTraceId": request.uploadTraceId,
            "inferenceAttemptId": request.inferenceAttemptId,
            "traceId": request.traceId,
            "results": result.model_dump(mode="json", exclude_none=True) if result is not None else None,
        }
        if result is not None:
            result_confidence = analysis_result_confidence(result)
            payload["resultConfidence"] = result_confidence
            payload["confidence"] = result_confidence
        return payload

    def inference_heartbeat_payload(request: InferenceDispatchRequest, *, stage: str) -> dict[str, Any]:
        return {
            "jobId": request.jobId,
            "requestId": request.requestId,
            "stage": stage,
            "schemaVersion": request.schemaVersion,
            "modelVersion": request.modelVersion,
            "uploadTraceId": request.uploadTraceId,
            "inferenceAttemptId": request.inferenceAttemptId,
            "traceId": request.traceId,
        }

    async def post_inference_heartbeat_safe(request: InferenceDispatchRequest, *, stage: str) -> None:
        payload = inference_heartbeat_payload(request, stage=stage)
        try:
            await run_in_threadpool(post_inference_heartbeat, request.callbackUrl, request.callbackSecret, request.jobId, payload)
            emit_event("analysis.heartbeat.sent", jobId=request.jobId, stage=stage, teamMode=request.teamSelection.mode if request.teamSelection else "all")
        except EditingServiceError as error:
            emit_event("analysis.heartbeat.failed", jobId=request.jobId, stage=stage, failureReason=error.__class__.__name__, failureCode=error.error_code)
        except Exception as error:
            emit_event("analysis.heartbeat.failed", jobId=request.jobId, stage=stage, failureReason=error.__class__.__name__)

    async def post_inference_progress_callback_safe(request: InferenceDispatchRequest, *, stage: str, progress: float) -> None:
        payload = inference_callback_payload(
            request,
            status="processing",
            stage=stage,
            progress=progress,
        )
        try:
            await run_in_threadpool(post_inference_callback, request.callbackUrl, request.callbackSecret, payload)
            emit_event("analysis.progress_callback.sent", jobId=request.jobId, stage=stage, progress=progress, teamMode=request.teamSelection.mode if request.teamSelection else "all")
        except EditingServiceError as error:
            emit_event("analysis.progress_callback.failed", jobId=request.jobId, stage=stage, progress=progress, failureReason=error.__class__.__name__, failureCode=error.error_code)
        except Exception as error:
            emit_event("analysis.progress_callback.failed", jobId=request.jobId, stage=stage, progress=progress, failureReason=error.__class__.__name__)

    async def analysis_heartbeat_loop(request: InferenceDispatchRequest, stage_ref: dict[str, str]) -> None:
        try:
            while True:
                await asyncio.sleep(30)
                stage = stage_ref.get("stage") or "Analyzing in cloud"
                await post_inference_heartbeat_safe(request, stage=stage)
                await post_inference_progress_callback_safe(request, stage=stage, progress=0.72)
        except asyncio.CancelledError:
            return

    async def run_inference_dispatch(request: InferenceDispatchRequest) -> None:
        source: Optional[MaterializedSource] = None
        stage_ref = {"stage": "Preparing cloud analysis input"}
        heartbeat_task = asyncio.create_task(analysis_heartbeat_loop(request, stage_ref))
        emit_event("analysis.dispatch.started", jobId=request.jobId, teamMode=request.teamSelection.mode if request.teamSelection else "all", modelVersion=request.modelVersion)
        try:
            await post_inference_heartbeat_safe(request, stage=stage_ref["stage"])
            await post_inference_progress_callback_safe(request, stage=stage_ref["stage"], progress=0.64)
            try:
                analysis_settings = get_analysis_settings()
            except ValueError as error:
                raise EditingServiceError(503, "analysis_unconfigured", "Cloud analysis is not configured.") from error
            source = await run_in_threadpool(
                materialize_dispatch_source,
                request.storageKey or request.sourceObjectKey,
                request.sourceUrl,
                request.filename,
                analysis_settings.max_file_size_bytes,
            )
            stage_ref["stage"] = "Analyzing in cloud"
            emit_event("analysis.source.materialized", jobId=request.jobId, teamMode=request.teamSelection.mode if request.teamSelection else "all")
            await post_inference_heartbeat_safe(request, stage=stage_ref["stage"])
            await post_inference_progress_callback_safe(request, stage=stage_ref["stage"], progress=0.72)
            job = dispatch_job_from_request(request, analysis_settings.job_ttl_seconds)
            emit_event("analysis.run.started", jobId=request.jobId, teamMode=request.teamSelection.mode if request.teamSelection else "all")
            result = await run_in_threadpool(run_analysis, job, analysis_settings, source.local_path)
            emit_event("analysis.run.completed", jobId=request.jobId, teamMode=request.teamSelection.mode if request.teamSelection else "all", clipCount=result.clipCount)
            payload = inference_callback_payload(
                request,
                status="succeeded",
                stage="Finalizing clips",
                progress=0.98,
                result=result,
            )
        except EditingServiceError as error:
            payload = inference_callback_payload(
                request,
                status="failed",
                stage="Inference failed",
                progress=0.77,
                failure_reason=error.error_code,
            )
        except APIError as error:
            payload = inference_callback_payload(
                request,
                status="failed",
                stage="Inference failed",
                progress=0.77,
                failure_reason=error.error_code,
            )
        except PipelineError as error:
            payload = inference_callback_payload(
                request,
                status="failed",
                stage="Inference failed",
                progress=0.77,
                failure_reason=error.error_code,
            )
        except Exception:
            payload = inference_callback_payload(
                request,
                status="failed",
                stage="Inference failed",
                progress=0.77,
                failure_reason="processing_error",
            )
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            if source is not None:
                source.cleanup()

        try:
            await run_in_threadpool(post_inference_callback, request.callbackUrl, request.callbackSecret, payload)
            emit_event("analysis.callback.sent", jobId=request.jobId, status=payload.get("status"), teamMode=request.teamSelection.mode if request.teamSelection else "all")
        except EditingServiceError as error:
            emit_event("analysis.callback.failed", jobId=request.jobId, status=payload.get("status"), failureReason=error.__class__.__name__, failureCode=error.error_code)
        except Exception as error:
            emit_event("analysis.callback.failed", jobId=request.jobId, status=payload.get("status"), failureReason=error.__class__.__name__)

    def cache_job(job: StoredRenderJob) -> StoredRenderJob:
        render_jobs[job.render_job_id] = job
        render_jobs_by_edit_id[job.edit_job_id] = job.render_job_id
        if job.idempotency_key:
            render_jobs_by_idempotency_key[job.idempotency_key] = job.render_job_id
        return job

    def persist_job(job: StoredRenderJob) -> None:
        cache_job(job)
        render_state_store.save_job(job)

    def persist_job_with_lease(job: StoredRenderJob, lease_token: str) -> None:
        if not render_state_store.save_job_if_lease(job, lease_token):
            emit_event("render.lease_conflict", editJobId=job.edit_job_id, renderJobId=job.render_job_id, leaseOwner=job.lease_owner)
            raise EditingServiceError(409, "render_lease_lost", "Render lease was lost before state could be updated.")
        cache_job(job)

    def load_job(render_job_id: str) -> Optional[StoredRenderJob]:
        job = render_jobs.get(render_job_id)
        if job is not None:
            return job
        job = render_state_store.load_job(render_job_id)
        if job is not None:
            return cache_job(job)
        return None

    def load_latest_render_job(edit_job_id: str) -> Optional[StoredRenderJob]:
        render_job_id = render_jobs_by_edit_id.get(edit_job_id)
        if render_job_id:
            job = load_job(render_job_id)
            if job is not None:
                return job
        job = render_state_store.load_latest_for_edit(edit_job_id)
        if job is not None:
            return cache_job(job)
        return None

    def load_idempotent_render_job(idempotency_key: str) -> Optional[StoredRenderJob]:
        render_job_id = render_jobs_by_idempotency_key.get(idempotency_key)
        if render_job_id:
            job = load_job(render_job_id)
            if job is not None:
                return job
        job = render_state_store.load_by_idempotency_key(idempotency_key)
        if job is not None:
            return cache_job(job)
        return None

    def require_job(render_job_id: str) -> StoredRenderJob:
        job = load_job(render_job_id)
        if job is None:
            raise EditingServiceError(404, "render_job_not_found", "Render job was not found.")
        return job

    def edit_job_to_durable_payload(job: StoredEditJob) -> dict[str, object]:
        return {
            "version": "edit-job-state-v1",
            "editJobId": job.edit_job_id,
            "installId": job.install_id,
            "status": job.status,
            "createdAt": job.created_at.isoformat(),
            "updatedAt": job.updated_at.isoformat(),
            "request": job.request.model_dump(mode="json"),
            "plan": job.plan.model_dump(mode="json"),
            "validationErrors": [error.model_dump(mode="json") for error in job.validation_errors],
        }

    def edit_job_from_durable_payload(payload: dict[str, object]) -> StoredEditJob:
        request = CreateEditJobRequest(**payload["request"])  # type: ignore[arg-type]
        plan = EditPlan(**payload["plan"])  # type: ignore[arg-type]
        return StoredEditJob(
            edit_job_id=str(payload["editJobId"]),
            install_id=str(payload.get("installId") or request.installId),
            request=request,
            plan=plan,
            status=str(payload.get("status") or "plan_ready"),
            created_at=parse_datetime(payload.get("createdAt")) or now_utc(),
            updated_at=parse_datetime(payload.get("updatedAt")) or now_utc(),
            validation_errors=[EditPlanValidationIssue(**error) for error in payload.get("validationErrors", [])],  # type: ignore[arg-type]
        )

    def cache_edit_job(job: StoredEditJob) -> StoredEditJob:
        edit_jobs[job.edit_job_id] = job
        return job

    def persist_edit_job(job: StoredEditJob, plan_id: Optional[str] = None) -> None:
        if job.request.idempotencyKey and not render_state_store.reserve_edit_job_idempotency_key(
            job.edit_job_id,
            job.install_id,
            job.request.idempotencyKey,
            job.updated_at,
        ):
            raise EditingServiceError(409, "edit_job_idempotency_conflict", "Edit job idempotency key already belongs to another edit job.")
        cache_edit_job(job)
        render_state_store.save_edit_job_payload(job.edit_job_id, edit_job_to_durable_payload(job))
        if plan_id:
            render_state_store.save_edit_plan_payload(job.edit_job_id, plan_id, job.plan.model_dump(mode="json"))

    def load_edit_job(edit_job_id: str) -> Optional[StoredEditJob]:
        job = edit_jobs.get(edit_job_id)
        if job is not None:
            return job
        payload = render_state_store.load_edit_job_payload(edit_job_id)
        if payload is None:
            return None
        try:
            return cache_edit_job(edit_job_from_durable_payload(payload))
        except Exception:
            return None

    def load_idempotent_edit_job(idempotency_key: str) -> Optional[StoredEditJob]:
        edit_job_id = render_state_store.load_edit_job_id_by_idempotency_key(idempotency_key)
        if not edit_job_id:
            return None
        return load_edit_job(edit_job_id)

    def require_edit_job(edit_job_id: str) -> StoredEditJob:
        job = load_edit_job(edit_job_id)
        if job is None:
            raise EditingServiceError(404, "edit_job_not_found", "Edit job was not found.")
        return job

    def revision_to_durable_payload(revision: EditRevisionResponse, render_job_id: Optional[str] = None) -> dict[str, object]:
        existing = render_state_store.load_revision_payload(revision.editJobId, revision.revisionId)
        created_at = existing.get("createdAt") if isinstance(existing, dict) else now_utc().isoformat()
        existing_render_job_id = existing.get("renderJobId") if isinstance(existing, dict) else None
        return {
            "version": "edit-revision-state-v1",
            "revisionId": revision.revisionId,
            "editJobId": revision.editJobId,
            "basePlanId": revision.basePlanId,
            "revisedPlanId": revision.newPlanId,
            "revisionIntent": revision.command,
            "patch": revision.patch.model_dump(mode="json"),
            "validationResult": revision.validationResult.model_dump(mode="json"),
            "status": revision.status,
            "createdAt": created_at,
            "updatedAt": now_utc().isoformat(),
            "renderJobId": render_job_id or (existing_render_job_id if isinstance(existing_render_job_id, str) else None),
            "revision": revision.model_dump(mode="json"),
        }

    def revision_from_durable_payload(payload: dict[str, object]) -> Optional[EditRevisionResponse]:
        revision_payload = payload.get("revision")
        if isinstance(revision_payload, dict):
            try:
                return EditRevisionResponse(**revision_payload)
            except Exception:
                return None
        try:
            return EditRevisionResponse(**payload)
        except Exception:
            return None

    def persist_revision(revision: EditRevisionResponse, revised_job: StoredEditJob, render_job_id: Optional[str] = None) -> None:
        edit_revisions.setdefault(revision.editJobId, [])
        if not any(existing.revisionId == revision.revisionId for existing in edit_revisions[revision.editJobId]):
            edit_revisions[revision.editJobId].append(revision)
        edit_revisions_by_id[revision.revisionId] = revision
        render_state_store.save_revision_payload(revision.editJobId, revision.revisionId, revision_to_durable_payload(revision, render_job_id))
        render_state_store.save_edit_plan_payload(revision.editJobId, revision.newPlanId, revision.revisedPlan.model_dump(mode="json"))
        persist_edit_job(revised_job)

    def load_revisions(edit_job_id: str) -> list[EditRevisionResponse]:
        cached = edit_revisions.get(edit_job_id)
        if cached is not None:
            return cached
        revisions: list[EditRevisionResponse] = []
        for payload in render_state_store.load_revision_payloads(edit_job_id):
            revision = revision_from_durable_payload(payload)
            if revision is None:
                continue
            revisions.append(revision)
            edit_revisions_by_id[revision.revisionId] = revision
        edit_revisions[edit_job_id] = revisions
        return revisions

    def load_revision(edit_job_id: str, revision_id: str) -> Optional[EditRevisionResponse]:
        revision = edit_revisions_by_id.get(revision_id)
        if revision is not None and revision.editJobId == edit_job_id:
            return revision
        payload = render_state_store.load_revision_payload(edit_job_id, revision_id)
        if payload is None:
            return None
        revision = revision_from_durable_payload(payload)
        if revision is None:
            return None
        edit_revisions_by_id[revision.revisionId] = revision
        edit_revisions.setdefault(edit_job_id, [])
        if not any(existing.revisionId == revision.revisionId for existing in edit_revisions[edit_job_id]):
            edit_revisions[edit_job_id].append(revision)
        return revision

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
            "ai_edit_live_render_disabled",
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

    def request_for_render_job(job: StoredRenderJob) -> Optional[CreateRenderJobRequest]:
        request = render_requests.get(job.render_job_id)
        if request is not None:
            return request
        durable_request = render_state_store.load_render_request_payload(job.render_job_id)
        if durable_request is not None:
            try:
                request = CreateRenderJobRequest(**durable_request)
                render_requests[job.render_job_id] = request
                return request
            except Exception:
                pass
        edit_job = load_edit_job(job.edit_job_id)
        if edit_job is None:
            return None
        if not edit_job.request.sourceObjectKey:
            return None
        plan = edit_job.plan
        if job.revision_id:
            revision = load_revision(job.edit_job_id, job.revision_id)
            if revision is not None:
                plan = revision.revisedPlan
        request = CreateRenderJobRequest(
            editJobId=job.edit_job_id,
            revisionId=job.revision_id,
            installId=job.install_id,
            sourceObjectKey=job.source_object_key or edit_job.request.sourceObjectKey,
            planTier=job.plan_tier,
            revenueCatAppUserID=edit_job.request.revenueCatAppUserID,
            editPlan=plan,
            sourceClips=source_clips_for_edit_request(edit_job.request),
            gptRerankSummary=edit_job.request.gptRerankSummary,
            idempotencyKey=job.idempotency_key,
        )
        render_requests[job.render_job_id] = request
        return request

    def work_timeline_for_render_job(job: StoredRenderJob, request: Optional[CreateRenderJobRequest] = None) -> AIWorkTimeline:
        resolved_request = request or request_for_render_job(job)
        return build_ai_work_timeline(
            job,
            resolved_request.editPlan if resolved_request is not None else None,
            resolved_request.sourceClips if resolved_request is not None else None,
            resolved_request.gptRerankSummary if resolved_request is not None else None,
        )

    def work_receipt_for_render_job(job: StoredRenderJob, request: Optional[CreateRenderJobRequest] = None) -> AIWorkReceipt:
        resolved_request = request or request_for_render_job(job)
        return build_ai_work_receipt(
            job,
            resolved_request.editPlan if resolved_request is not None else None,
            resolved_request.sourceClips if resolved_request is not None else None,
            resolved_request.gptRerankSummary if resolved_request is not None else None,
        )

    def render_job_response(job: StoredRenderJob, request: Optional[CreateRenderJobRequest] = None) -> RenderJobResponse:
        timeline = work_timeline_for_render_job(job, request)
        receipt = work_receipt_for_render_job(job, request) if job.status == "rendered" else None
        return job.to_response(work_timeline=timeline, work_receipt=receipt)

    def stored_edit_job_event_fields(edit_job_id: str, **extra_fields: object) -> dict[str, object]:
        job = load_edit_job(edit_job_id)
        fields: dict[str, object] = {"editJobId": edit_job_id, **extra_fields}
        if job is not None:
            fields.update(planTier=job.request.planTier, templateId=job.plan.templateId)
        return fields

    def active_render_statuses() -> set[str]:
        return {"render_requested", "created", "queued", "rendering"}

    def daily_quota_statuses() -> set[str]:
        return active_render_statuses() | {"rendered"}

    def is_returnable_existing(job: StoredRenderJob) -> bool:
        return job.status in active_render_statuses() or job.status == "rendered"

    def render_lease_is_active(job: StoredRenderJob) -> bool:
        return bool(job.lease_token and job.lease_expires_at and job.lease_expires_at > now_utc())

    def recover_render_request(
        job: StoredRenderJob,
        fallback_request: Optional[CreateRenderJobRequest] = None,
    ) -> Optional[CreateRenderJobRequest]:
        request = request_for_render_job(job)
        if request is not None:
            return request
        if fallback_request is None:
            return None
        render_requests[job.render_job_id] = fallback_request
        render_state_store.save_render_request_payload(job.render_job_id, fallback_request.model_dump(mode="json"))
        return fallback_request

    def schedule_render_recovery_if_needed(
        job: StoredRenderJob,
        background_tasks: BackgroundTasks,
        fallback_request: Optional[CreateRenderJobRequest] = None,
    ) -> Optional[CreateRenderJobRequest]:
        if job.status not in active_render_statuses():
            return request_for_render_job(job)
        request = recover_render_request(job, fallback_request)
        if request is None:
            mark_failed(job, "failed_timeout" if render_job_is_stale(job) else "missing_render_request")
            return None
        if job.status == "rendering" and render_lease_is_active(job):
            return request
        if job.render_job_id in render_recovery_scheduled:
            return request
        render_recovery_scheduled.add(job.render_job_id)
        emit_event(
            "render.recovery_scheduled",
            editJobId=job.edit_job_id,
            renderJobId=job.render_job_id,
            templateId=job.template_id,
            planTier=job.plan_tier,
            status=job.status,
        )
        background_tasks.add_task(run_render_job, job.render_job_id)
        return request

    def render_job_is_stale(job: StoredRenderJob) -> bool:
        if job.status not in active_render_statuses():
            return False
        timeout_seconds = effective_policy(job.plan_tier).staleRenderTimeoutSeconds
        lease_expired = bool(job.lease_expires_at and job.lease_expires_at <= now_utc())
        return lease_expired or (now_utc() - job.updated_at).total_seconds() > timeout_seconds

    def mark_stale_job(job: StoredRenderJob) -> None:
        if render_job_is_stale(job):
            mark_failed(job, "failed_timeout")

    def mark_stale_renders() -> None:
        for job in list(render_jobs.values()):
            mark_stale_job(job)

    def canonical_render_request_for_stored_edit(request: CreateRenderJobRequest) -> CreateRenderJobRequest:
        stored_edit_job = load_edit_job(request.editJobId)
        if stored_edit_job is None:
            return request
        require_edit_owner(stored_edit_job, request.installId)
        if not stored_edit_job.request.sourceObjectKey:
            raise EditingServiceError(400, "missing_source_object_key", "Render requires a source video object key.")

        edit_plan = stored_edit_job.plan
        if request.revisionId:
            revision = load_revision(request.editJobId, request.revisionId)
            if revision is None or revision.editJobId != request.editJobId:
                raise EditingServiceError(404, "revision_not_found", "Edit revision was not found.")
            edit_plan = revision.revisedPlan

        return CreateRenderJobRequest(
            editJobId=stored_edit_job.edit_job_id,
            revisionId=request.revisionId,
            installId=request.installId,
            sourceObjectKey=stored_edit_job.request.sourceObjectKey,
            planTier=stored_edit_job.request.planTier,
            revenueCatAppUserID=stored_edit_job.request.revenueCatAppUserID,
            editPlan=edit_plan,
            sourceClips=source_clips_for_edit_request(stored_edit_job.request),
            gptRerankSummary=stored_edit_job.request.gptRerankSummary,
            idempotencyKey=request.idempotencyKey,
        )

    def render_expires_at(job: StoredRenderJob):
        metadata = job.retention_metadata or {}
        return job.expires_at or parse_datetime(metadata.get("expiresAt"))

    def require_downloadable_output(job: StoredRenderJob) -> str:
        if job.status != "rendered" or not job.output_object_key:
            raise EditingServiceError(409, "render_not_ready", "Render output is not ready for download yet.")
        expires_at = render_expires_at(job)
        if expires_at is not None and expires_at <= now_utc():
            raise EditingServiceError(410, "render_expired", "Render output expired. Request a fresh cloud render from My AI Edits.")
        return job.output_object_key

    def load_render_history_for_install(install_id: str, limit: int) -> list[StoredRenderJob]:
        jobs_by_id: dict[str, StoredRenderJob] = {}
        for job in render_state_store.load_jobs_for_install(install_id):
            jobs_by_id[job.render_job_id] = cache_job(job)
        for job in render_jobs.values():
            if job.install_id == install_id:
                jobs_by_id[job.render_job_id] = job
        jobs = list(jobs_by_id.values())
        for job in jobs:
            mark_stale_job(job)
        jobs.sort(key=lambda job: job.updated_at or job.created_at, reverse=True)
        return jobs[:limit]

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

    def revenuecat_rest_api_key() -> Optional[str]:
        return os.getenv("HOOPS_REVENUECAT_REST_API_KEY") or os.getenv("REVENUECAT_REST_API_KEY")

    def revenuecat_entitlement_id() -> str:
        return os.getenv("HOOPS_REVENUECAT_PRO_ENTITLEMENT_ID", "pro").strip() or "pro"

    def revenuecat_api_base_url() -> str:
        base_url = os.getenv("HOOPS_REVENUECAT_API_BASE_URL", "https://api.revenuecat.com").rstrip("/")
        return base_url.removesuffix("/v1")

    def verify_revenuecat_pro_entitlement(app_user_id: Optional[str]) -> None:
        if not app_user_id:
            raise EditingServiceError(403, "pro_entitlement_required", "Pro templates require an active HoopClips Pro entitlement.")

        api_key = revenuecat_rest_api_key()
        if not api_key:
            raise EditingServiceError(503, "revenuecat_verifier_unconfigured", "Pro entitlement verification is not configured.")

        entitlement_id = revenuecat_entitlement_id()
        url = f"{revenuecat_api_base_url()}/v1/subscribers/{quote(app_user_id, safe='')}"
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "HoopClipsEditingService/1.0",
            },
        )
        try:
            with urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise EditingServiceError(403, "pro_entitlement_unverified", "HoopClips could not verify an active Pro entitlement.") from error
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise EditingServiceError(503, "revenuecat_verifier_unavailable", "Pro entitlement verification is temporarily unavailable.") from error

        entitlement = payload.get("subscriber", {}).get("entitlements", {}).get(entitlement_id)
        if not isinstance(entitlement, dict):
            raise EditingServiceError(403, "pro_entitlement_required", "Pro templates require an active HoopClips Pro entitlement.")
        expires_date = entitlement.get("expires_date")
        grace_period_expires_date = entitlement.get("grace_period_expires_date")
        if not _revenuecat_expiration_is_active(expires_date, grace_period_expires_date):
            raise EditingServiceError(403, "pro_entitlement_required", "Pro templates require an active HoopClips Pro entitlement.")

    def _revenuecat_expiration_is_active(expires_date: object, grace_period_expires_date: object) -> bool:
        if expires_date is None:
            return True
        for value in (expires_date, grace_period_expires_date):
            if not isinstance(value, str) or not value:
                continue
            parsed = parse_datetime(value)
            if parsed is not None and parsed > now_utc():
                return True
        return False

    def enforce_template_policy(template_id: Optional[str], plan_tier: str, revenuecat_app_user_id: Optional[str]) -> None:
        template = get_template_pack(template_id)
        if not template.premiumOnly:
            return
        policy = effective_policy(plan_tier)
        if not policy.premiumTemplatesAllowed:
            raise EditingServiceError(403, "premium_template_required", "Selected template requires HoopClips Pro.")
        if plan_tier == "pro":
            if not feature_flags.aiEditProExportsEnabled:
                raise EditingServiceError(403, "pro_exports_unavailable", "Pro AI exports are not enabled yet.")
            verify_revenuecat_pro_entitlement(revenuecat_app_user_id)

    def enforce_render_quota(request: CreateRenderJobRequest) -> None:
        policy = effective_policy(request.planTier)
        install_jobs = render_state_store.load_jobs_for_install(request.installId)
        for job in install_jobs:
            cache_job(job)
            mark_stale_job(job)
        prune_daily_render_counts(request.installId)
        cutoff = now_utc() - timedelta(days=1)
        quota_statuses = daily_quota_statuses()
        durable_daily_count = sum(1 for job in install_jobs if job.created_at >= cutoff and job.status in quota_statuses)
        memory_daily_count = sum(
            1
            for job in render_jobs.values()
            if job.install_id == request.installId and job.created_at >= cutoff and job.status in quota_statuses
        )
        if max(durable_daily_count, memory_daily_count) >= policy.maxDailyRenders:
            raise EditingServiceError(429, "daily_render_limit", "Daily AI edit render limit reached for this plan.")
        active_ids = {
            job.render_job_id
            for job in list(render_jobs.values()) + install_jobs
            if job.install_id == request.installId and job.status in active_render_statuses()
        }
        active_count = len(active_ids)
        if active_count >= policy.maxActiveRenders:
            raise EditingServiceError(429, "active_render_limit", "Too many AI edit renders are active for this plan.")

    def record_render_quota_usage(job: StoredRenderJob) -> None:
        render_created_by_install.setdefault(job.install_id, []).append(job.created_at)

    def validate_create_request_policy(request: CreateEditJobRequest) -> None:
        if not feature_flags.aiEditEnabled:
            raise EditingServiceError(403, "ai_edit_disabled", "AI Edit is temporarily unavailable.")
        if request.templateId and not feature_flags.aiEditTemplatePackEnabled:
            raise EditingServiceError(403, "ai_edit_template_pack_disabled", "AI Edit templates are temporarily unavailable.")
        enforce_template_policy(request.templateId, request.planTier, request.revenueCatAppUserID)
        if request.planTier == "pro" and not feature_flags.aiEditProExportsEnabled:
            raise EditingServiceError(403, "pro_exports_unavailable", "Pro AI exports are not enabled yet.")
        policy = effective_policy(request.planTier)
        estimated_source_seconds = max((clip.end for clip in request.clips), default=0.0)
        if estimated_source_seconds > policy.maxSourceVideoSeconds:
            raise EditingServiceError(400, "source_video_too_long", "Source video exceeds the plan tier source duration limit.")
        if request.targetDurationSeconds > policy.maxRenderSeconds:
            raise EditingServiceError(400, "render_duration_limit", "Requested AI edit length exceeds this plan's render limit.")

    def validate_live_render_policy() -> None:
        if not feature_flags.aiEditLiveRenderEnabled:
            raise EditingServiceError(403, "ai_edit_live_render_disabled", "AI Edit rendering is temporarily unavailable.")

    def maybe_apply_gpt_highlight_rerank(request: CreateEditJobRequest) -> CreateEditJobRequest:
        source = None
        source_context_request = request
        if request.sourceObjectKey:
            try:
                source = storage.materialize_source(request.sourceObjectKey)
                source_context_request = expand_shot_candidate_windows_from_source_path(request, source.local_path)
            except EditingServiceError:
                source = None

        if not feature_flags.gptHighlightRerankerEnabled:
            fallback = with_gpt_fallback_summary(
                source_context_request,
                status="disabled",
                model=gpt_reranker_settings.model,
                reason="feature_flag_disabled",
            )
            if source is not None:
                source.cleanup()
            return fallback
        if not request.sourceObjectKey:
            return rerank_edit_request_with_gpt(source_context_request, Path("__missing_source__"), gpt_reranker_settings)
        if not gpt_reranker_settings.configured:
            if source is not None:
                source.cleanup()
            return rerank_edit_request_with_gpt(source_context_request, Path("__missing_key__"), gpt_reranker_settings)

        try:
            if source is None:
                reranked = rerank_edit_request_with_gpt(source_context_request, Path("__missing_source__"), gpt_reranker_settings)
            else:
                reranked = rerank_edit_request_with_gpt(source_context_request, source.local_path, gpt_reranker_settings)
        finally:
            if source is not None:
                source.cleanup()

        summary = reranked.gptRerankSummary
        if summary is not None:
            event_name = "gpt_highlight_rerank.applied" if summary.status == "applied" else "gpt_highlight_rerank.fallback"
            emit_event(
                event_name,
                sampledClipCount=summary.sampledClipCount,
                sampledFrameCount=summary.sampledFrameCount,
                returnedDecisionCount=summary.returnedDecisionCount,
                keptClipCount=len(summary.keptClipIds),
                rejectedClipCount=len(summary.rejectedClipIds),
                uncertainReviewClipCount=len(summary.uncertainReviewClipIds),
                fallbackReason=summary.fallbackReason,
            )
        return reranked

    def validate_revision_policy(edit_job_id: str, request: ReviseEditJobRequest) -> None:
        if not feature_flags.aiEditRevisionEnabled:
            raise EditingServiceError(403, "ai_edit_revision_disabled", "AI Edit revisions are temporarily unavailable.")
        job = require_edit_job(edit_job_id)
        policy = effective_policy(job.request.planTier)
        if len(load_revisions(edit_job_id)) >= policy.maxRevisionsPerEdit:
            raise EditingServiceError(429, "revision_limit", "Revision limit reached for this edit.")
        if request.targetDurationSeconds is not None and request.targetDurationSeconds > policy.maxRenderSeconds:
            raise EditingServiceError(400, "render_duration_limit", "Requested revision length exceeds this plan's render limit.")

    def build_retention_metadata(job: StoredRenderJob, request: Optional[CreateRenderJobRequest], output_bytes: int, duration_seconds: float, status: str) -> Dict[str, Any]:
        plan_tier = request.planTier if request is not None else job.plan_tier
        template_id = request.editPlan.templateId if request is not None else job.template_id
        policy = get_plan_tier_policy(plan_tier)
        retention_days = policy.renderRetentionDays if status == "rendered" else policy.failedRenderRetentionDays
        expires_at = now_utc() + timedelta(days=retention_days)
        return {
            "expiresAt": expires_at.isoformat(),
            "retentionClass": f"{plan_tier}_{'final_render' if status == 'rendered' else 'failed_render'}",
            "deleteEligible": True,
            "planTier": plan_tier,
            "editJobId": job.edit_job_id,
            "revisionId": job.revision_id,
            "renderJobId": job.render_job_id,
            "templateId": template_id,
            "outputBytes": output_bytes,
            "durationSeconds": duration_seconds,
        }

    def mark_failed(job: StoredRenderJob, reason: str, validation_errors: Optional[list] = None, lease_token: Optional[str] = None) -> None:
        job.status = "failed_timeout" if reason == "failed_timeout" else "failed"
        job.failure_reason = reason
        job.validation_errors = validation_errors or []
        job.render_log_object_key = f"edits/{job.edit_job_id}/render_jobs/{job.render_job_id}/render_log.json"
        request = render_requests.get(job.render_job_id)
        job.retention_metadata = build_retention_metadata(job, request, 0, 0.0, job.status)
        job.completed_at = now_utc()
        job.expires_at = parse_datetime(job.retention_metadata.get("expiresAt") if job.retention_metadata else None)
        job.updated_at = now_utc()
        emit_event("render.failed", editJobId=job.edit_job_id, renderJobId=job.render_job_id, planTier=job.plan_tier, failureReason=reason)
        if lease_token:
            try:
                persist_job_with_lease(job, lease_token)
            except EditingServiceError:
                return
        else:
            persist_job(job)
        try:
            work_timeline = work_timeline_for_render_job(job, request)
            storage.put_json(
                job.render_log_object_key,
                render_log_payload(
                    job,
                    job.status,
                    {
                        "failureReason": reason,
                        "planTier": job.plan_tier,
                        "policy": policy_summary_for_client(job.plan_tier),
                        "retentionMetadata": job.retention_metadata,
                        "validationErrors": [error.model_dump() for error in job.validation_errors],
                        "workTimeline": work_timeline.model_dump(mode="json"),
                    },
                ),
            )
        except Exception:
            pass

    def acquire_render_lease(render_job_id: str) -> tuple[StoredRenderJob, str]:
        now = now_utc()
        ttl_seconds = max(30, effective_policy(require_job(render_job_id).plan_tier).staleRenderTimeoutSeconds)
        lease_token = "lease_" + uuid4().hex
        leased_job = render_state_store.acquire_render_lease(render_job_id, instance_id, lease_token, now, ttl_seconds)
        if leased_job is None:
            emit_event("render.lease_conflict", renderJobId=render_job_id, leaseOwner=instance_id)
            raise EditingServiceError(409, "render_lease_active", "Render job already has an active execution lease.")
        cache_job(leased_job)
        emit_event("render.lease_acquired", editJobId=leased_job.edit_job_id, renderJobId=leased_job.render_job_id, leaseOwner=instance_id)
        return leased_job, lease_token

    def run_render_job(render_job_id: str) -> None:
        job: Optional[StoredRenderJob] = None
        request: Optional[CreateRenderJobRequest] = None
        source = None
        lease_token: Optional[str] = None
        try:
            job, lease_token = acquire_render_lease(render_job_id)
            request = request_for_render_job(job)
            if request is None:
                raise EditingServiceError(409, "missing_render_request", "Render job request could not be reconstructed after restart.")
            render_requests[render_job_id] = request
            emit_event("render.started", editJobId=job.edit_job_id, renderJobId=job.render_job_id, templateId=request.editPlan.templateId, planTier=request.planTier)
            source = storage.materialize_source(request.sourceObjectKey)
            with tempfile.TemporaryDirectory(prefix="hoopclips-edit-render-", dir=str(resolved_settings.upload_root)) as temp_dir:
                result = FfmpegRenderer().render(request.editPlan, source.local_path, Path(temp_dir))
                plan_key = f"edits/{request.editJobId}/plans/{request.editPlan.editJobId}.json"
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
                job.completed_at = now_utc()
                job.expires_at = parse_datetime(retention_metadata.get("expiresAt"))
                job.heartbeat_at = now_utc()
                job.updated_at = now_utc()
                work_timeline = work_timeline_for_render_job(job, request)
                work_receipt = work_receipt_for_render_job(job, request)
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
                            "workTimeline": work_timeline.model_dump(mode="json"),
                            "workReceipt": work_receipt.model_dump(mode="json"),
                            "ffmpeg": result.render_log,
                        },
                    ),
                )
                persist_job_with_lease(job, lease_token)
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
            if job is not None:
                mark_failed(job, error.error_code, lease_token=lease_token)
        except EditingServiceError as error:
            if job is not None and error.error_code != "render_lease_active":
                mark_failed(job, error.error_code, lease_token=lease_token)
        except Exception:
            if job is not None:
                mark_failed(job, "render_failed", lease_token=lease_token)
        finally:
            render_recovery_scheduled.discard(render_job_id)
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
            "gptHighlightReranker": gpt_reranker_settings.public_status(),
        }

    @app.post("/v1/analyze", status_code=202, responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}})
    async def analyze_source(
        request: InferenceDispatchRequest,
        background_tasks: BackgroundTasks,
        x_hoops_inference_secret: Optional[str] = Header(default=None),
        x_hoops_internal_secret: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_inference_secret or x_hoops_internal_secret or x_hoops_editing_secret)
            background_tasks.add_task(run_inference_dispatch, request)
            return {"jobId": request.jobId, "status": "accepted"}
        except EditingServiceError as error:
            return error_response(error)

    @app.post("/v1/team-scan", response_model=ScanCloudAnalysisTeamsResponse, responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}})
    async def scan_source_teams(
        request: ScanCloudAnalysisSourceRequest,
        x_hoops_inference_secret: Optional[str] = Header(default=None),
        x_hoops_internal_secret: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        source: Optional[MaterializedSource] = None
        try:
            require_secret(x_hoops_inference_secret or x_hoops_internal_secret or x_hoops_editing_secret)
            try:
                analysis_settings = get_analysis_settings()
            except ValueError as error:
                raise EditingServiceError(503, "team_scan_unconfigured", "Team scan is not configured.") from error
            prescan_settings = team_quick_prescan_settings(analysis_settings)
            source = await run_in_threadpool(
                materialize_dispatch_source,
                request.storageKey or request.sourceObjectKey,
                request.sourceUrl,
                request.filename,
                prescan_settings.max_file_size_bytes,
            )
            _, detected_teams, applied = await run_in_threadpool(
                apply_team_quick_scan,
                source.local_path,
                request.durationSeconds,
                [],
                prescan_settings,
            )
            status = "scanned" if applied and detected_teams else "unavailable"
            return ScanCloudAnalysisTeamsResponse(jobId=request.jobId, status=status, detectedTeams=detected_teams)
        except EditingServiceError as error:
            return error_response(error)
        except APIError as error:
            return JSONResponse(
                status_code=error.status_code,
                content=ErrorResponse(errorCode=error.error_code, errorMessage=error.error_message, failureReason=error.error_message).model_dump(exclude_none=True),
            )
        finally:
            if source is not None:
                source.cleanup()

    def enqueue_render_job(request: CreateRenderJobRequest, background_tasks: BackgroundTasks, force_new: bool = False) -> RenderJobResponse:
        mark_stale_renders()
        validate_live_render_policy()
        enforce_template_policy(request.editPlan.templateId, request.planTier, request.revenueCatAppUserID)
        default_idempotency_key = f"{request.installId}:{request.editJobId}:{request.editPlan.editJobId}:{request.editPlan.templateId}:{len(request.editPlan.clips)}"
        if request.idempotencyKey:
            idempotency_key = request.idempotencyKey
        elif force_new:
            idempotency_key = f"{default_idempotency_key}:force:{uuid4().hex}"
        else:
            idempotency_key = default_idempotency_key
        existing_by_key = load_idempotent_render_job(idempotency_key)
        if existing_by_key is not None:
            recovered_request = schedule_render_recovery_if_needed(existing_by_key, background_tasks, request)
            if existing_by_key.status in active_render_statuses():
                return render_job_response(existing_by_key, recovered_request or request)
            mark_stale_job(existing_by_key)
            if is_returnable_existing(existing_by_key):
                return render_job_response(existing_by_key, request)
        existing = load_latest_render_job(request.editJobId)
        if existing is not None and not force_new:
            recovered_request = schedule_render_recovery_if_needed(existing, background_tasks, request)
            if existing.status in active_render_statuses():
                return render_job_response(existing, recovered_request or request)
            mark_stale_job(existing)
            if is_returnable_existing(existing):
                return render_job_response(existing, request)
            if existing.status in {"failed", "failed_timeout"} and existing.retry_count >= get_plan_tier_policy(request.planTier).maxRenderRetries:
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
            source_object_key=request.sourceObjectKey,
            plan_version=request.editPlan.version,
            template_id=request.editPlan.templateId,
            plan_tier=request.planTier,
            retry_count=(existing.retry_count + 1) if existing is not None else 0,
            idempotency_key=idempotency_key,
            revision_id=request.revisionId,
        )
        if not render_state_store.reserve_idempotency_key(job):
            existing_after_reservation = load_idempotent_render_job(idempotency_key)
            if existing_after_reservation is not None:
                mark_stale_job(existing_after_reservation)
                return render_job_response(existing_after_reservation, request)
            raise EditingServiceError(409, "render_idempotency_conflict", "A render already reserved this idempotency key.")
        persist_job(job)
        render_requests[render_job_id] = request
        render_state_store.save_render_request_payload(render_job_id, request.model_dump(mode="json"))

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
            return render_job_response(job, request)

        record_render_quota_usage(job)
        emit_event("render.requested", editJobId=job.edit_job_id, renderJobId=job.render_job_id, templateId=request.editPlan.templateId, planTier=request.planTier)
        background_tasks.add_task(run_render_job, render_job_id)
        return render_job_response(job, request)

    @app.post("/v1/edit-jobs", responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}})
    async def create_edit_job(
        request: CreateEditJobRequest,
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            if request.idempotencyKey:
                existing_job = load_idempotent_edit_job(request.idempotencyKey)
                if existing_job is not None:
                    require_edit_owner(existing_job, request.installId)
                    emit_event(
                        "edit_plan.replayed",
                        editJobId=existing_job.edit_job_id,
                        templateId=existing_job.plan.templateId,
                        planTier=existing_job.request.planTier,
                    )
                    return existing_job.to_response()
            validate_create_request_policy(request)
            edit_job_id = "edit_" + uuid4().hex
            effective_request = maybe_apply_gpt_highlight_rerank(request)
            job = build_edit_job(effective_request, edit_job_id)
            if job.validation_errors:
                first_error = job.validation_errors[0]
                raise EditingServiceError(400, first_error.code, first_error.message)
            persist_edit_job(job, plan_id=edit_job_id)
            emit_event("edit_plan.created", editJobId=edit_job_id, templateId=job.plan.templateId, planTier=effective_request.planTier)
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
            emit_policy_failed(error, **stored_edit_job_event_fields(edit_job_id))
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
            emit_policy_failed(error, **stored_edit_job_event_fields(edit_job_id))
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
            gpt_patch_status = "disabled"
            gpt_patch_fallback_reason = "feature_flag_disabled"
            proposed_patch = None
            if feature_flags.aiClipGptRevisionEnabled:
                gpt_patch_attempt = request_gpt_edit_plan_patch_attempt(job, request, gpt_reranker_settings)
                proposed_patch = gpt_patch_attempt.patch
                gpt_patch_status = gpt_patch_attempt.status
                gpt_patch_fallback_reason = gpt_patch_attempt.fallback_reason
            revised_job, revision_response = build_revision_response(
                job,
                request,
                revision_id,
                proposed_patch=proposed_patch,
                gpt_revision_patch_status=gpt_patch_status,
                gpt_revision_patch_fallback_reason=gpt_patch_fallback_reason,
            )
            if not revision_response.validationResult.valid:
                first_error = revision_response.validationResult.errors[0]
                raise EditingServiceError(400, first_error.code, first_error.message)
            persist_revision(revision_response, revised_job)
            emit_event("edit_revision.created", editJobId=edit_job_id, revisionId=revision_id, templateId=revision_response.revisedPlan.templateId, planTier=revised_job.request.planTier)
            return revision_response
        except EditingServiceError as error:
            emit_policy_failed(error, **stored_edit_job_event_fields(edit_job_id))
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
            return EditRevisionListResponse(editJobId=edit_job_id, revisions=load_revisions(edit_job_id))
        except EditingServiceError as error:
            emit_policy_failed(error, **stored_edit_job_event_fields(edit_job_id))
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
            revision = load_revision(edit_job_id, revision_id)
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
            revision = load_revision(edit_job_id, revision_id)
            if revision is None or revision.editJobId != edit_job_id:
                raise EditingServiceError(404, "revision_not_found", "Edit revision was not found.")
            if not stored_edit_job.request.sourceObjectKey:
                raise EditingServiceError(400, "missing_source_object_key", "Revision render requires a source video object key.")
            render_response = enqueue_render_job(
                CreateRenderJobRequest(
                    editJobId=edit_job_id,
                    installId=request.installId,
                    sourceObjectKey=stored_edit_job.request.sourceObjectKey,
                    planTier=stored_edit_job.request.planTier,
                    revenueCatAppUserID=stored_edit_job.request.revenueCatAppUserID,
                    editPlan=revision.revisedPlan,
                    sourceClips=source_clips_for_edit_request(stored_edit_job.request),
                    gptRerankSummary=stored_edit_job.request.gptRerankSummary,
                    revisionId=revision_id,
                    idempotencyKey=request.idempotencyKey or f"{edit_job_id}:{revision_id}:render",
                ),
                background_tasks,
                force_new=True,
            )
            persist_revision(revision, stored_edit_job, render_response.renderJobId)
            return render_response
        except EditingServiceError as error:
            emit_policy_failed(error, **stored_edit_job_event_fields(edit_job_id, revisionId=revision_id))
            return error_response(error)

    @app.post("/v1/render-jobs", response_model=RenderJobResponse, responses={401: {"model": ErrorResponse}})
    async def create_render_job(
        request: CreateRenderJobRequest,
        background_tasks: BackgroundTasks,
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            canonical_request = canonical_render_request_for_stored_edit(request)
            return enqueue_render_job(canonical_request, background_tasks)
        except EditingServiceError as error:
            emit_policy_failed(error, editJobId=request.editJobId, templateId=request.editPlan.templateId, planTier=request.planTier)
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
            stored_edit_job = load_edit_job(edit_job_id)
            if stored_edit_job is not None:
                require_edit_owner(stored_edit_job, request.installId)

            if stored_edit_job is not None:
                edit_plan = stored_edit_job.plan
                source_clips = source_clips_for_edit_request(stored_edit_job.request)
                source_object_key = stored_edit_job.request.sourceObjectKey
                plan_tier = stored_edit_job.request.planTier
                revenuecat_app_user_id = stored_edit_job.request.revenueCatAppUserID
            else:
                edit_plan = request.editPlan
                source_clips = request.sourceClips
                source_object_key = request.sourceObjectKey
                plan_tier = request.planTier or "free"
                revenuecat_app_user_id = request.revenueCatAppUserID
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
                    revenueCatAppUserID=revenuecat_app_user_id,
                    editPlan=edit_plan,
                    sourceClips=source_clips,
                    gptRerankSummary=stored_edit_job.request.gptRerankSummary if stored_edit_job is not None else None,
                    idempotencyKey=request.idempotencyKey,
                ),
                background_tasks,
                force_new=request.forceNew,
            )
        except EditingServiceError as error:
            emit_policy_failed(error, **stored_edit_job_event_fields(edit_job_id))
            return error_response(error)

    @app.get("/v1/render-jobs", response_model=RenderJobListResponse, responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}})
    async def list_render_jobs(
        background_tasks: BackgroundTasks,
        installId: Optional[str] = Query(default=None),
        limit: int = Query(default=20, ge=1, le=50),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            install_id = installId or x_hoops_install_id
            if not install_id:
                raise EditingServiceError(400, "missing_install_id", "Install ID is required to list render history.")
            mark_stale_renders()
            jobs = load_render_history_for_install(install_id, limit)
            for job in jobs:
                if job.status in active_render_statuses():
                    schedule_render_recovery_if_needed(job, background_tasks)
                    if job.status in active_render_statuses():
                        continue
                mark_stale_job(job)
            emit_event("render_history.listed", renderCount=len(jobs), limit=limit)
            return RenderJobListResponse(
                installId=install_id,
                generatedAt=now_utc(),
                renders=[render_job_response(job) for job in jobs],
            )
        except EditingServiceError as error:
            return error_response(error)

    @app.get("/v1/render-jobs/{render_job_id}", response_model=RenderJobResponse, responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
    async def get_render_job(
        render_job_id: str,
        background_tasks: BackgroundTasks,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            mark_stale_renders()
            job = require_job(render_job_id)
            require_owner(job, installId or x_hoops_install_id)
            recovered_request = schedule_render_recovery_if_needed(job, background_tasks)
            if job.status not in active_render_statuses():
                mark_stale_job(job)
            return render_job_response(job, recovered_request)
        except EditingServiceError as error:
            return error_response(error)

    @app.get("/v1/edit-jobs/{edit_job_id}/render-status", response_model=RenderJobResponse, responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
    async def get_edit_render_status(
        edit_job_id: str,
        background_tasks: BackgroundTasks,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            mark_stale_renders()
            job = load_latest_render_job(edit_job_id)
            if job is None:
                raise EditingServiceError(404, "render_job_not_found", "Render job was not found.")
            require_owner(job, installId or x_hoops_install_id)
            recovered_request = schedule_render_recovery_if_needed(job, background_tasks)
            if job.status not in active_render_statuses():
                mark_stale_job(job)
            return render_job_response(job, recovered_request)
        except EditingServiceError as error:
            return error_response(error)

    @app.get("/v1/render-jobs/{render_job_id}/download-url", response_model=DownloadUrlResponse, responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 410: {"model": ErrorResponse}})
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
            mark_stale_job(job)
            require_owner(job, installId or x_hoops_install_id)
            output_object_key = require_downloadable_output(job)
            download_url, expires_at = storage.presigned_get_url(output_object_key, job.render_job_id)
            emit_event("download_url.created", editJobId=job.edit_job_id, renderJobId=job.render_job_id, planTier=job.plan_tier)
            return DownloadUrlResponse(
                editJobId=job.edit_job_id,
                renderJobId=job.render_job_id,
                downloadUrl=download_url,
                outputObjectKey=output_object_key,
                expiresAt=expires_at,
            )
        except EditingServiceError as error:
            return error_response(error)

    @app.get("/v1/edit-jobs/{edit_job_id}/download-url", response_model=DownloadUrlResponse, responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 410: {"model": ErrorResponse}})
    async def get_edit_download_url(
        edit_job_id: str,
        installId: Optional[str] = Query(default=None),
        x_hoops_install_id: Optional[str] = Header(default=None),
        x_hoops_editing_secret: Optional[str] = Header(default=None),
    ):
        try:
            require_secret(x_hoops_editing_secret)
            mark_stale_renders()
            job = load_latest_render_job(edit_job_id)
            if job is None:
                raise EditingServiceError(404, "render_job_not_found", "Render job was not found.")
            mark_stale_job(job)
            require_owner(job, installId or x_hoops_install_id)
            output_object_key = require_downloadable_output(job)
            download_url, expires_at = storage.presigned_get_url(output_object_key, job.render_job_id)
            emit_event("download_url.created", editJobId=job.edit_job_id, renderJobId=job.render_job_id, planTier=job.plan_tier)
            return DownloadUrlResponse(
                editJobId=job.edit_job_id,
                renderJobId=job.render_job_id,
                downloadUrl=download_url,
                outputObjectKey=output_object_key,
                expiresAt=expires_at,
            )
        except EditingServiceError as error:
            return error_response(error)

    @app.get("/v1/internal/render-downloads/{render_job_id}/final.mp4")
    async def download_local_render(render_job_id: str):
        try:
            job = require_job(render_job_id)
            if storage.provider != "local":
                raise EditingServiceError(404, "render_output_not_found", "Render output was not found.")
            output_object_key = require_downloadable_output(job)
            if job.status != "rendered" or not output_object_key:
                raise EditingServiceError(404, "render_output_not_found", "Render output was not found.")
            output_path = storage.local_path_for_object(output_object_key)
            if not output_path.exists():
                raise EditingServiceError(404, "render_output_not_found", "Render output was not found.")
            return FileResponse(output_path, media_type="video/mp4", filename="Hoopclips.mp4")
        except EditingServiceError as error:
            return error_response(error)

    return app


app = create_app()
