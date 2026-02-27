from __future__ import annotations

from datetime import timedelta
import asyncio
from typing import Optional

from .config import Settings
from .models import APIError, JobStatus, PreparedUpload, StoredJob, now_utc


class InMemoryJobStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jobs: dict[str, StoredJob] = {}
        self._usage_events: dict[str, list] = {}
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
        request,
        upload: PreparedUpload,
    ) -> StoredJob:
        async with self._lock:
            job = StoredJob(
                job_id=job_id,
                install_id=request.installId,
                filename=request.filename,
                content_type=request.contentType,
                file_size_bytes=request.fileSizeBytes,
                duration_seconds=request.durationSeconds,
                app_version=request.appVersion,
                analysis_version=request.analysisVersion,
                created_at=now_utc(),
                expires_at=now_utc() + timedelta(seconds=self._settings.job_ttl_seconds),
                object_key=upload.object_key,
                upload_headers=upload.upload_headers,
            )
            self._jobs[job_id] = job
            return job

    async def get_job(self, job_id: str) -> Optional[StoredJob]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_job(self, job_id: str, **updates) -> StoredJob:
        async with self._lock:
            job = self._jobs[job_id]
            for key, value in updates.items():
                setattr(job, key, value)
            return job

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

    async def mark_succeeded(self, job_id: str, results) -> StoredJob:
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
