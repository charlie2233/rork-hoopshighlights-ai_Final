from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from typing import Dict, Optional

from .config import Settings
from .models import APIError, MaterializedSource


@dataclass(frozen=True)
class StoredRenderObject:
    object_key: str
    local_path: Optional[Path] = None


class RenderStorage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider = self._env("HOOPS_RENDER_STORAGE_PROVIDER", "local").strip().lower()
        if self._provider not in {"local", "r2"}:
            raise RuntimeError("HOOPS_RENDER_STORAGE_PROVIDER must be either 'local' or 'r2'.")
        self._download_ttl_seconds = int(self._env("HOOPS_RENDER_DOWNLOAD_TTL_SECONDS", "900"))

    @property
    def provider(self) -> str:
        return self._provider

    def source_exists(self, object_key: Optional[str]) -> bool:
        if not object_key:
            return False
        if self._provider == "r2":
            return self._r2_object_exists(object_key)
        return self._local_object_path(object_key).exists()

    def materialize_source(self, object_key: Optional[str]) -> MaterializedSource:
        if not object_key:
            raise APIError(400, "source_missing", "Edit job does not include a sourceObjectKey.")
        if self._provider == "r2":
            return self._materialize_r2_source(object_key)
        path = self._local_object_path(object_key)
        if not path.exists() or not path.is_file():
            raise APIError(400, "source_missing", "Source video object was not found.")
        return MaterializedSource(local_path=path, cleanup_after_use=False)

    def put_json(self, object_key: str, payload: str) -> StoredRenderObject:
        if self._provider == "r2":
            client = self._r2_client()
            client.put_object(
                Bucket=self._required_env("HOOPS_R2_BUCKET"),
                Key=object_key,
                Body=payload.encode("utf-8"),
                ContentType="application/json",
            )
            return StoredRenderObject(object_key=object_key)
        path = self._local_object_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        return StoredRenderObject(object_key=object_key, local_path=path)

    def put_file(self, object_key: str, source_path: Path, content_type: str) -> StoredRenderObject:
        if not source_path.exists() or source_path.stat().st_size <= 0:
            raise APIError(500, "render_output_missing", "Renderer did not produce a usable output file.")
        if self._provider == "r2":
            client = self._r2_client()
            client.upload_file(
                str(source_path),
                self._required_env("HOOPS_R2_BUCKET"),
                object_key,
                ExtraArgs={"ContentType": content_type},
            )
            return StoredRenderObject(object_key=object_key)
        target = self._local_object_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        return StoredRenderObject(object_key=object_key, local_path=target)

    def presigned_get_url(self, object_key: str, token: Optional[str] = None) -> str:
        if self._provider == "r2":
            client = self._r2_client()
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._required_env("HOOPS_R2_BUCKET"), "Key": object_key},
                ExpiresIn=self._download_ttl_seconds,
            )
        base = self._settings.host_base_url.rstrip("/")
        rendered_token = token or "local"
        return f"{base}/v1/internal/render-downloads/{rendered_token}/final.mp4"

    def local_path_for_object(self, object_key: str) -> Path:
        return self._local_object_path(object_key)

    def diagnostics(self) -> Dict[str, object]:
        upload_root = self._settings.upload_root
        upload_root.mkdir(parents=True, exist_ok=True)
        provider_ready = True
        r2_config = None
        if self._provider == "r2":
            required = {
                "bucket": bool(self._env("HOOPS_R2_BUCKET", "")),
                "endpoint": bool(self._env("HOOPS_R2_ENDPOINT_URL", "")),
                "accessKey": bool(self._env("HOOPS_R2_ACCESS_KEY_ID", "")),
                "secretKey": bool(self._env("HOOPS_R2_SECRET_ACCESS_KEY", "")),
            }
            provider_ready = all(required.values())
            r2_config = required
        return {
            "provider": self._provider,
            "providerReady": provider_ready,
            "downloadTtlSeconds": self._download_ttl_seconds,
            "uploadRootWritable": self._upload_root_writable(),
            "r2Config": r2_config,
        }

    def _materialize_r2_source(self, object_key: str) -> MaterializedSource:
        client = self._r2_client()
        temp_dir = Path(tempfile.mkdtemp(prefix="hoops-render-source-", dir=str(self._settings.upload_root)))
        local_path = temp_dir / Path(object_key).name
        try:
            client.download_file(self._required_env("HOOPS_R2_BUCKET"), object_key, str(local_path))
        except Exception as error:
            raise APIError(400, "source_missing", "Source video object was not found.") from error
        return MaterializedSource(local_path=local_path, cleanup_after_use=True)

    def _r2_object_exists(self, object_key: str) -> bool:
        client = self._r2_client()
        try:
            response = client.head_object(Bucket=self._required_env("HOOPS_R2_BUCKET"), Key=object_key)
        except Exception:
            return False
        content_length = int(response.get("ContentLength") or 0)
        return content_length > 0

    def _r2_client(self):
        try:
            import boto3
        except ImportError as error:
            raise RuntimeError("boto3 is required when HOOPS_RENDER_STORAGE_PROVIDER=r2.") from error

        return boto3.client(
            "s3",
            endpoint_url=self._required_env("HOOPS_R2_ENDPOINT_URL"),
            aws_access_key_id=self._required_env("HOOPS_R2_ACCESS_KEY_ID"),
            aws_secret_access_key=self._required_env("HOOPS_R2_SECRET_ACCESS_KEY"),
            region_name=self._env("HOOPS_R2_REGION", "auto"),
        )

    def _upload_root_writable(self) -> bool:
        try:
            self._settings.upload_root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix=".hoops-render-ready-", dir=str(self._settings.upload_root), delete=True):
                return True
        except Exception:
            return False

    def _local_object_path(self, object_key: str) -> Path:
        safe_parts = [part for part in Path(object_key).parts if part not in {"", ".", ".."}]
        if not safe_parts:
            raise APIError(400, "invalid_object_key", "Object key is empty.")
        return self._settings.upload_root.joinpath(*safe_parts)

    def _required_env(self, key: str) -> str:
        value = self._env(key, "")
        if not value:
            raise RuntimeError(f"{key} is required for R2 render storage.")
        return value

    def _env(self, key: str, default: str) -> str:
        import os

        return os.getenv(key, default)
