from __future__ import annotations

from pathlib import Path
import re
from typing import Optional

from .config import Settings
from .models import PreparedUpload, StoredJob


class StorageManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def prepare_upload(self, job_id: str, filename: str, content_type: str) -> PreparedUpload:
        safe_name = self._sanitize_filename(filename)
        object_key = f"{job_id}/{safe_name}"
        return PreparedUpload(
            object_key=object_key,
            upload_url=self._settings.upload_url_template.format(job_id=job_id),
            upload_headers={"Content-Type": content_type},
        )

    def write_upload(self, job: StoredJob, payload: bytes) -> str:
        target_path = self._settings.upload_root / job.object_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(payload)
        return str(target_path)

    def object_exists(self, job: StoredJob) -> bool:
        path = self.local_path(job)
        return path is not None and path.exists() and path.is_file()

    def local_path(self, job: StoredJob) -> Optional[Path]:
        if not job.storage_path:
            return None
        return Path(job.storage_path)

    def cleanup(self, job: StoredJob) -> None:
        path = self.local_path(job)
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

    def _sanitize_filename(self, filename: str) -> str:
        name = Path(filename).name or "upload.mp4"
        normalized = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        return normalized[:120] or "upload.mp4"
