from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import asyncio
import re
import tempfile
from typing import Optional, Protocol

from .config import Settings
from .models import APIError, MaterializedSource, PreparedUpload, StoredJob, now_utc


class StorageProvider(Protocol):
    def prepare_upload(self, job_id: str, filename: str, content_type: str) -> PreparedUpload:
        ...

    def accept_local_upload(self, job: StoredJob, payload: bytes) -> str:
        ...

    async def object_exists(self, job: StoredJob) -> bool:
        ...

    async def materialize_source(self, job: StoredJob) -> MaterializedSource:
        ...

    def cleanup(self, job: StoredJob) -> None:
        ...


class LocalStorageProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def prepare_upload(self, job_id: str, filename: str, content_type: str) -> PreparedUpload:
        safe_name = self._sanitize_filename(filename)
        object_key = "uploads/{job_id}/{name}".format(job_id=job_id, name=safe_name)
        expires_at = now_utc() + timedelta(seconds=self._settings.signed_upload_ttl_seconds)
        return PreparedUpload(
            object_key=object_key,
            upload_url=self._settings.local_upload_url_template.format(job_id=job_id),
            upload_headers={"Content-Type": content_type},
            expires_at=expires_at,
        )

    def accept_local_upload(self, job: StoredJob, payload: bytes) -> str:
        target_path = self._settings.upload_root / (job.storage_key or job.object_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(payload)
        return str(target_path)

    async def object_exists(self, job: StoredJob) -> bool:
        path = self._local_path(job)
        return path is not None and path.exists() and path.is_file() and path.stat().st_size > 0

    async def materialize_source(self, job: StoredJob) -> MaterializedSource:
        path = self._local_path(job)
        if path is None or not path.exists() or not path.is_file():
            raise APIError(400, "upload_missing", "Upload is missing. Complete the signed upload before starting analysis.")
        return MaterializedSource(local_path=path, cleanup_after_use=False)

    def cleanup(self, job: StoredJob) -> None:
        path = self._local_path(job)
        if path is None:
            return
        try:
            if path.exists():
                path.unlink()
            parent = path.parent
            while parent != self._settings.upload_root and parent.exists():
                parent.rmdir()
                parent = parent.parent
        except OSError:
            pass

    def _local_path(self, job: StoredJob) -> Optional[Path]:
        if job.storage_path:
            return Path(job.storage_path)

        fallback = self._settings.upload_root / (job.storage_key or job.object_key)
        if fallback.exists():
            return fallback
        return None

    def _sanitize_filename(self, filename: str) -> str:
        name = Path(filename).name or "upload.mp4"
        normalized = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        return normalized[:120] or "upload.mp4"


class GCSStorageProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        storage_module = self._import_storage()
        project = settings.gcp_project_id or None
        self._client = storage_module.Client(project=project)
        self._bucket = self._client.bucket(settings.gcs_bucket_name)

    def prepare_upload(self, job_id: str, filename: str, content_type: str) -> PreparedUpload:
        safe_name = self._sanitize_filename(filename)
        object_key = "uploads/{job_id}/{name}".format(job_id=job_id, name=safe_name)
        blob = self._bucket.blob(object_key)
        expires_at = now_utc() + timedelta(seconds=self._settings.signed_upload_ttl_seconds)
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=self._settings.signed_upload_ttl_seconds),
            method="PUT",
            content_type=content_type,
        )
        return PreparedUpload(
            object_key=object_key,
            upload_url=upload_url,
            upload_headers={"Content-Type": content_type},
            expires_at=expires_at,
        )

    def accept_local_upload(self, job: StoredJob, payload: bytes) -> str:
        _ = job, payload
        raise APIError(404, "unsupported_upload", "Local upload emulation is disabled in managed backend mode.")

    async def object_exists(self, job: StoredJob) -> bool:
        return await asyncio.to_thread(self._object_exists_sync, job)

    async def materialize_source(self, job: StoredJob) -> MaterializedSource:
        return await asyncio.to_thread(self._materialize_source_sync, job)

    def cleanup(self, job: StoredJob) -> None:
        try:
            blob = self._bucket.blob(job.storage_key or job.object_key)
            blob.delete()
        except Exception:
            pass

    def _object_exists_sync(self, job: StoredJob) -> bool:
        blob = self._bucket.get_blob(job.storage_key or job.object_key)
        if blob is None:
            return False
        if blob.size is None or int(blob.size) <= 0:
            return False
        if blob.content_type and job.content_type and blob.content_type != job.content_type:
            return False
        return True

    def _materialize_source_sync(self, job: StoredJob) -> MaterializedSource:
        blob = self._bucket.get_blob(job.storage_key or job.object_key)
        if blob is None or blob.size is None or int(blob.size) <= 0:
            raise APIError(400, "upload_missing", "Upload is missing. Complete the signed upload before starting analysis.")
        if blob.content_type and job.content_type and blob.content_type != job.content_type:
            raise APIError(400, "invalid_upload", "Uploaded object content type did not match the analysis job.")

        temp_dir = Path(tempfile.mkdtemp(prefix="hoops-source-", dir=str(self._settings.upload_root)))
        local_path = temp_dir / self._sanitize_filename(job.filename)
        blob.download_to_filename(str(local_path))
        return MaterializedSource(local_path=local_path, cleanup_after_use=True)

    def _sanitize_filename(self, filename: str) -> str:
        name = Path(filename).name or "upload.mp4"
        normalized = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        return normalized[:120] or "upload.mp4"

    def _import_storage(self):
        try:
            from google.cloud import storage
        except ImportError as error:
            raise RuntimeError(
                "google-cloud-storage is required for staging/production backend mode. "
                "Install backend requirements before starting the managed runtime."
            ) from error
        return storage
