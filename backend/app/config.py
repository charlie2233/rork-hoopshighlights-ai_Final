from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional
import os


@dataclass(frozen=True)
class Settings:
    service_name: str
    host_base_url: str
    upload_root: Path
    internal_process_secret: Optional[str]
    daily_quota: int
    rolling_quota_hours: int
    default_poll_after_seconds: int
    job_ttl_seconds: int
    max_file_size_bytes: int
    max_duration_seconds: float
    min_clip_duration_seconds: float
    max_clip_duration_seconds: float
    clip_padding_seconds: float
    max_returned_clips: int
    backend_model_version: str
    use_gemini_relabeling: bool

    @property
    def upload_url_template(self) -> str:
        return f"{self.host_base_url}/v1/internal/uploads/{{job_id}}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    host_base_url = os.getenv("HOOPS_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    upload_root = Path(os.getenv("HOOPS_UPLOAD_ROOT", "/tmp/hoops-ai")).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)

    return Settings(
        service_name="hoops-ai-api",
        host_base_url=host_base_url,
        upload_root=upload_root,
        internal_process_secret=os.getenv("HOOPS_INTERNAL_PROCESS_SECRET") or None,
        daily_quota=int(os.getenv("HOOPS_DAILY_QUOTA", "3")),
        rolling_quota_hours=int(os.getenv("HOOPS_ROLLING_QUOTA_HOURS", "24")),
        default_poll_after_seconds=int(os.getenv("HOOPS_POLL_AFTER_SECONDS", "2")),
        job_ttl_seconds=int(os.getenv("HOOPS_JOB_TTL_SECONDS", "3600")),
        max_file_size_bytes=int(os.getenv("HOOPS_MAX_FILE_SIZE_BYTES", str(500 * 1024 * 1024))),
        max_duration_seconds=float(os.getenv("HOOPS_MAX_DURATION_SECONDS", "1800")),
        min_clip_duration_seconds=float(os.getenv("HOOPS_MIN_CLIP_SECONDS", "2.0")),
        max_clip_duration_seconds=float(os.getenv("HOOPS_MAX_CLIP_SECONDS", "15.0")),
        clip_padding_seconds=float(os.getenv("HOOPS_CLIP_PADDING_SECONDS", "0.35")),
        max_returned_clips=int(os.getenv("HOOPS_MAX_RETURNED_CLIPS", "8")),
        backend_model_version=os.getenv("HOOPS_BACKEND_MODEL_VERSION", "cloud-v1"),
        use_gemini_relabeling=(os.getenv("HOOPS_USE_GEMINI_RELABELING", "false").lower() == "true"),
    )
