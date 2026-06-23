from __future__ import annotations

from datetime import timedelta
import asyncio
from typing import Any, Dict, Optional, Protocol

from .config import Settings
from .models import (
    APIError,
    CloudAnalysisResult,
    CreateCloudAnalysisJobRequest,
    JobStatus,
    PreparedUpload,
    StoredJob,
    TeamOption,
    TeamSelection,
    now_utc,
)


class JobStore(Protocol):
    async def reserve_quota(self, install_id: str) -> int:
        ...

    async def create_job(
        self,
        job_id: str,
        request: CreateCloudAnalysisJobRequest,
        upload: PreparedUpload,
        quota_remaining_today: int,
    ) -> StoredJob:
        ...

    async def get_job(self, job_id: str) -> Optional[StoredJob]:
        ...

    async def update_job(self, job_id: str, **updates: Any) -> StoredJob:
        ...

    async def mark_uploaded(self, job_id: str, storage_path: str) -> StoredJob:
        ...

    async def mark_queued(self, job_id: str) -> StoredJob:
        ...

    async def mark_processing(self, job_id: str, stage: str, progress: float) -> StoredJob:
        ...

    async def mark_failed(self, job_id: str, error_code: str, error_message: str) -> StoredJob:
        ...

    async def mark_succeeded(self, job_id: str, results: CloudAnalysisResult) -> StoredJob:
        ...

    async def mark_expired(self, job_id: str) -> StoredJob:
        ...


class JobStoreBase:
    async def mark_uploaded(self, job_id: str, storage_path: str) -> StoredJob:
        return await self.update_job(job_id, storage_path=storage_path, progress=0.12, stage="Upload complete")

    async def mark_queued(self, job_id: str) -> StoredJob:
        return await self.update_job(job_id, status=JobStatus.QUEUED, progress=0.28, stage="Queued on server")

    async def mark_processing(self, job_id: str, stage: str, progress: float) -> StoredJob:
        return await self.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            stage=stage,
            progress=progress,
            error_code=None,
            error_message=None,
        )

    async def mark_failed(self, job_id: str, error_code: str, error_message: str) -> StoredJob:
        return await self.update_job(
            job_id,
            status=JobStatus.FAILED,
            progress=1.0,
            stage="Analysis failed",
            error_code=error_code,
            error_message=error_message,
        )

    async def mark_succeeded(self, job_id: str, results: CloudAnalysisResult) -> StoredJob:
        return await self.update_job(
            job_id,
            status=JobStatus.SUCCEEDED,
            progress=1.0,
            stage="Finalizing clips",
            results=results,
            error_code=None,
            error_message=None,
        )

    async def mark_expired(self, job_id: str) -> StoredJob:
        return await self.update_job(
            job_id,
            status=JobStatus.EXPIRED,
            progress=1.0,
            stage="Expired",
            error_code="expired",
            error_message="Cloud analysis job expired.",
        )


class InMemoryJobStore(JobStoreBase):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jobs: Dict[str, StoredJob] = {}
        self._usage_events: Dict[str, list] = {}
        self._lock = asyncio.Lock()

    async def reserve_quota(self, install_id: str) -> int:
        async with self._lock:
            current_time = now_utc()
            window_start = current_time - timedelta(hours=self._settings.rolling_quota_hours)
            events = [event for event in self._usage_events.get(install_id, []) if event >= window_start]

            if len(events) >= self._settings.daily_quota:
                raise APIError(
                    status_code=429,
                    error_code="quota_exceeded",
                    error_message="Cloud analysis quota exceeded for this install.",
                    quota_remaining_today=0,
                )

            events.append(current_time)
            self._usage_events[install_id] = events
            return max(self._settings.daily_quota - len(events), 0)

    async def create_job(
        self,
        job_id: str,
        request: CreateCloudAnalysisJobRequest,
        upload: PreparedUpload,
        quota_remaining_today: int,
    ) -> StoredJob:
        async with self._lock:
            created_at = now_utc()
            job = StoredJob(
                job_id=job_id,
                install_id=request.installId,
                filename=request.filename,
                content_type=request.contentType,
                file_size_bytes=request.fileSizeBytes,
                duration_seconds=request.durationSeconds,
                app_version=request.appVersion,
                analysis_version=request.analysisVersion,
                created_at=created_at,
                expires_at=created_at + timedelta(seconds=self._settings.job_ttl_seconds),
                object_key=upload.object_key,
                upload_headers=upload.upload_headers,
                asset_id=request.assetId,
                storage_key=request.storageKey or upload.object_key,
                team_selection=request.teamSelection,
                quota_remaining_today=quota_remaining_today,
            )
            self._jobs[job_id] = job
            return job

    async def get_job(self, job_id: str) -> Optional[StoredJob]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_job(self, job_id: str, **updates: Any) -> StoredJob:
        async with self._lock:
            job = self._jobs[job_id]
            for key, value in updates.items():
                setattr(job, key, value)
            self._jobs[job_id] = job
            return job


class FirestoreJobStore(JobStoreBase):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._firestore = self._import_firestore()
        project = settings.gcp_project_id or None
        self._client = self._firestore.Client(project=project)

    async def reserve_quota(self, install_id: str) -> int:
        return await asyncio.to_thread(self._reserve_quota_sync, install_id)

    def _reserve_quota_sync(self, install_id: str) -> int:
        firestore = self._firestore
        transaction = self._client.transaction()
        document = self._usage_ref(install_id)
        current_time = now_utc()
        window_span = timedelta(hours=self._settings.rolling_quota_hours)

        @firestore.transactional
        def _run(transaction_obj, reference):
            snapshot = reference.get(transaction=transaction_obj)
            payload = snapshot.to_dict() if snapshot.exists else {}
            window_started_at = payload.get("windowStartedAt")
            window_ends_at = payload.get("windowEndsAt")
            usage_count = int(payload.get("usageCount") or 0)

            if not window_started_at or not window_ends_at or window_ends_at <= current_time:
                window_started_at = current_time
                window_ends_at = current_time + window_span
                usage_count = 0

            if usage_count >= self._settings.daily_quota:
                raise APIError(
                    status_code=429,
                    error_code="quota_exceeded",
                    error_message="Cloud analysis quota exceeded for this install.",
                    quota_remaining_today=0,
                )

            usage_count += 1
            transaction_obj.set(
                reference,
                {
                    "installId": install_id,
                    "windowStartedAt": window_started_at,
                    "windowEndsAt": window_ends_at,
                    "usageCount": usage_count,
                    "updatedAt": current_time,
                },
            )
            return max(self._settings.daily_quota - usage_count, 0)

        return _run(transaction, document)

    async def create_job(
        self,
        job_id: str,
        request: CreateCloudAnalysisJobRequest,
        upload: PreparedUpload,
        quota_remaining_today: int,
    ) -> StoredJob:
        created_at = now_utc()
        job = StoredJob(
            job_id=job_id,
            install_id=request.installId,
            filename=request.filename,
            content_type=request.contentType,
            file_size_bytes=request.fileSizeBytes,
            duration_seconds=request.durationSeconds,
            app_version=request.appVersion,
            analysis_version=request.analysisVersion,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=self._settings.job_ttl_seconds),
            object_key=upload.object_key,
            upload_headers=upload.upload_headers,
            asset_id=request.assetId,
            storage_key=request.storageKey or upload.object_key,
            team_selection=request.teamSelection,
            quota_remaining_today=quota_remaining_today,
        )
        await asyncio.to_thread(self._job_ref(job_id).set, self._serialize_job(job))
        return job

    async def get_job(self, job_id: str) -> Optional[StoredJob]:
        snapshot = await asyncio.to_thread(self._job_ref(job_id).get)
        if not snapshot.exists:
            return None
        return self._deserialize_job(snapshot.to_dict())

    async def update_job(self, job_id: str, **updates: Any) -> StoredJob:
        job = await self.get_job(job_id)
        if job is None:
            raise KeyError(job_id)

        for key, value in updates.items():
            setattr(job, key, value)

        await asyncio.to_thread(self._job_ref(job_id).set, self._serialize_job(job), merge=False)
        return job

    def _job_ref(self, job_id: str):
        return self._client.collection(self._settings.firestore_jobs_collection).document(job_id)

    def _usage_ref(self, install_id: str):
        return self._client.collection(self._settings.firestore_usage_collection).document(install_id)

    def _serialize_job(self, job: StoredJob) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "jobId": job.job_id,
            "installId": job.install_id,
            "filename": job.filename,
            "contentType": job.content_type,
            "fileSizeBytes": job.file_size_bytes,
            "durationSeconds": job.duration_seconds,
            "appVersion": job.app_version,
            "analysisVersion": job.analysis_version,
            "createdAt": job.created_at,
            "expiresAt": job.expires_at,
            "ttlAt": job.expires_at,
            "objectKey": job.object_key,
            "uploadHeaders": job.upload_headers,
            "assetId": job.asset_id,
            "storageKey": job.storage_key,
            "teamSelection": job.team_selection.model_dump(mode="json") if job.team_selection is not None else None,
            "detectedTeams": [team.model_dump(mode="json") for team in job.detected_teams],
            "teamScanStatus": job.team_scan_status,
            "status": job.status.value,
            "progress": job.progress,
            "stage": job.stage,
            "errorCode": job.error_code,
            "errorMessage": job.error_message,
            "storagePath": job.storage_path,
            "quotaRemainingToday": job.quota_remaining_today,
        }
        if job.results is not None:
            payload["results"] = job.results.model_dump(mode="json")
        else:
            payload["results"] = None
        return payload

    def _deserialize_job(self, payload: Dict[str, Any]) -> StoredJob:
        results_payload = payload.get("results")
        results = CloudAnalysisResult.model_validate(results_payload) if results_payload else None
        status_value = payload.get("status") or JobStatus.CREATED.value
        return StoredJob(
            job_id=payload["jobId"],
            install_id=payload["installId"],
            filename=payload["filename"],
            content_type=payload["contentType"],
            file_size_bytes=int(payload["fileSizeBytes"]),
            duration_seconds=float(payload["durationSeconds"]),
            app_version=payload["appVersion"],
            analysis_version=payload["analysisVersion"],
            created_at=payload["createdAt"],
            expires_at=payload["expiresAt"],
            object_key=payload["objectKey"],
            upload_headers=dict(payload.get("uploadHeaders") or {}),
            asset_id=payload.get("assetId"),
            storage_key=payload.get("storageKey") or payload.get("objectKey"),
            team_selection=TeamSelection.model_validate(payload.get("teamSelection")) if payload.get("teamSelection") else None,
            detected_teams=[TeamOption.model_validate(team) for team in payload.get("detectedTeams") or []],
            team_scan_status=payload.get("teamScanStatus"),
            status=JobStatus(status_value),
            progress=float(payload.get("progress") or 0.0),
            stage=payload.get("stage") or "Preparing upload",
            error_code=payload.get("errorCode"),
            error_message=payload.get("errorMessage"),
            results=results,
            storage_path=payload.get("storagePath"),
            quota_remaining_today=int(payload.get("quotaRemainingToday") or 0),
        )

    def _import_firestore(self):
        try:
            from google.cloud import firestore
        except ImportError as error:
            raise RuntimeError(
                "google-cloud-firestore is required for staging/production backend mode. "
                "Install backend requirements before starting the managed runtime."
            ) from error
        return firestore
