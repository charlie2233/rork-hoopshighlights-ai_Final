from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class EditingSettings:
    service_name: str
    environment: str
    host_base_url: str
    upload_root: Path
    shared_secret: Optional[str]
    render_storage_provider: str
    render_download_ttl_seconds: int
    backend_model_version: str
    git_sha: str

    @property
    def is_local(self) -> bool:
        return self.environment == "local"

    def validate(self) -> None:
        if self.render_storage_provider not in {"local", "r2"}:
            raise ValueError("HOOPS_RENDER_STORAGE_PROVIDER must be either 'local' or 'r2'.")
        if not self.is_local and not self.shared_secret:
            raise ValueError("HOOPS_EDITING_SERVICE_SECRET is required outside local mode.")
        if not self.is_local and self.render_storage_provider != "r2":
            raise ValueError("Cloud editing service must use R2 render storage outside local mode.")


def get_settings() -> EditingSettings:
    environment = os.getenv("HOOPS_ENVIRONMENT", os.getenv("ENV", "local")).strip().lower() or "local"
    host_base_url = os.getenv("HOOPS_PUBLIC_BASE_URL", "http://127.0.0.1:8090").rstrip("/")
    upload_root = Path(os.getenv("HOOPS_UPLOAD_ROOT", "/tmp/hoopclips-editing")).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    provider = os.getenv("HOOPS_RENDER_STORAGE_PROVIDER", "local" if environment == "local" else "r2").strip().lower()
    settings = EditingSettings(
        service_name=os.getenv("HOOPS_EDITING_SERVICE_NAME", "hoopclips-editing"),
        environment=environment,
        host_base_url=host_base_url,
        upload_root=upload_root,
        shared_secret=os.getenv("HOOPS_EDITING_SERVICE_SECRET") or None,
        render_storage_provider=provider,
        render_download_ttl_seconds=int(os.getenv("HOOPS_RENDER_DOWNLOAD_TTL_SECONDS", "900")),
        backend_model_version=os.getenv("HOOPS_BACKEND_MODEL_VERSION", "editing-cloud-v1"),
        git_sha=os.getenv("HOOPS_GIT_SHA", "local"),
    )
    settings.validate()
    return settings
