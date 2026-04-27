from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
import shutil
import tempfile
from typing import Dict, Optional

from .config import EditingSettings
from .models import now_utc


class EditingServiceError(Exception):
    def __init__(self, status_code: int, error_code: str, error_message: str) -> None:
        super().__init__(error_message)
        self.status_code = status_code
        self.error_code = error_code
        self.error_message = error_message


@dataclass
class MaterializedSource:
    local_path: Path
    cleanup_after_use: bool = False

    def cleanup(self) -> None:
        if not self.cleanup_after_use:
            return
        try:
            if self.local_path.exists():
                self.local_path.unlink()
            parent = self.local_path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass


class RenderStorage:
    def __init__(self, settings: EditingSettings) -> None:
        self._settings = settings
        self._provider = settings.render_storage_provider

    @property
    def provider(self) -> str:
        return self._provider

    def source_exists(self, object_key: str) -> bool:
        if self._provider == "r2":
            try:
                response = self._r2_client().head_object(Bucket=self._source_bucket(), Key=object_key)
            except Exception:
                return False
            return int(response.get("ContentLength") or 0) > 0
        path = self._local_object_path(object_key)
        return path.is_file() and path.stat().st_size > 0

    def materialize_source(self, object_key: str) -> MaterializedSource:
        if self._provider == "r2":
            temp_dir = Path(tempfile.mkdtemp(prefix="hoopclips-edit-source-", dir=str(self._settings.upload_root)))
            local_path = temp_dir / Path(object_key).name
            try:
                self._r2_client().download_file(self._source_bucket(), object_key, str(local_path))
            except Exception as error:
                raise EditingServiceError(400, "source_missing", "Source video object was not found.") from error
            return MaterializedSource(local_path=local_path, cleanup_after_use=True)
        path = self._local_object_path(object_key)
        if not path.is_file() or path.stat().st_size <= 0:
            raise EditingServiceError(400, "source_missing", "Source video object was not found.")
        return MaterializedSource(local_path=path, cleanup_after_use=False)

    def put_json(self, object_key: str, payload: str) -> None:
        if self._provider == "r2":
            self._r2_client().put_object(
                Bucket=self._output_bucket(),
                Key=object_key,
                Body=payload.encode("utf-8"),
                ContentType="application/json",
            )
            return
        path = self._local_object_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")

    def put_file(self, object_key: str, source_path: Path, content_type: str) -> None:
        if not source_path.exists() or source_path.stat().st_size <= 0:
            raise EditingServiceError(500, "render_output_missing", "Renderer did not produce a usable output file.")
        if self._provider == "r2":
            client = self._r2_client()
            client.upload_file(
                str(source_path),
                self._output_bucket(),
                object_key,
                ExtraArgs={"ContentType": content_type},
            )
            head = client.head_object(Bucket=self._output_bucket(), Key=object_key)
            if int(head.get("ContentLength") or 0) <= 0:
                raise EditingServiceError(500, "render_upload_unverified", "Uploaded render object could not be verified.")
            return
        target = self._local_object_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)

    def presigned_get_url(self, object_key: str, token: str) -> tuple[str, object]:
        if self._provider == "r2":
            url = self._r2_client().generate_presigned_url(
                "get_object",
                Params={"Bucket": self._output_bucket(), "Key": object_key},
                ExpiresIn=self._settings.render_download_ttl_seconds,
            )
            return url, now_utc() + timedelta(seconds=self._settings.render_download_ttl_seconds)
        base = self._settings.host_base_url.rstrip("/")
        return f"{base}/v1/internal/render-downloads/{token}/final.mp4", now_utc() + timedelta(seconds=self._settings.render_download_ttl_seconds)

    def local_path_for_object(self, object_key: str) -> Path:
        return self._local_object_path(object_key)

    def diagnostics(self) -> Dict[str, object]:
        provider_ready = True
        r2_config = None
        if self._provider == "r2":
            legacy_bucket = bool(self._env("HOOPS_R2_BUCKET", ""))
            source_bucket = bool(self._env("HOOPS_R2_SOURCE_BUCKET", "")) or legacy_bucket
            output_bucket = bool(self._env("HOOPS_R2_OUTPUT_BUCKET", "")) or legacy_bucket
            r2_config = {
                "bucket": legacy_bucket,
                "sourceBucket": source_bucket,
                "outputBucket": output_bucket,
                "endpoint": bool(self._env("HOOPS_R2_ENDPOINT_URL", "")),
                "accessKey": bool(self._env("HOOPS_R2_ACCESS_KEY_ID", "")),
                "secretKey": bool(self._env("HOOPS_R2_SECRET_ACCESS_KEY", "")),
            }
            provider_ready = all(r2_config.values())
        return {
            "provider": self._provider,
            "providerReady": provider_ready,
            "uploadRootWritable": self._upload_root_writable(),
            "downloadTtlSeconds": self._settings.render_download_ttl_seconds,
            "r2Config": r2_config,
        }

    def _r2_client(self):
        try:
            import boto3
        except ImportError as error:
            raise RuntimeError("boto3 is required for R2 render storage.") from error

        return boto3.client(
            "s3",
            endpoint_url=self._required_env("HOOPS_R2_ENDPOINT_URL"),
            aws_access_key_id=self._required_env("HOOPS_R2_ACCESS_KEY_ID"),
            aws_secret_access_key=self._required_env("HOOPS_R2_SECRET_ACCESS_KEY"),
            region_name=self._env("HOOPS_R2_REGION", "auto"),
        )

    def _local_object_path(self, object_key: str) -> Path:
        safe_parts = [part for part in Path(object_key).parts if part not in {"", ".", ".."}]
        if not safe_parts:
            raise EditingServiceError(400, "invalid_object_key", "Object key is empty.")
        return self._settings.upload_root.joinpath(*safe_parts)

    def _required_env(self, key: str) -> str:
        value = self._env(key, "")
        if not value:
            raise RuntimeError(f"{key} is required for R2 render storage.")
        return value

    def _source_bucket(self) -> str:
        return self._env("HOOPS_R2_SOURCE_BUCKET", "") or self._required_env("HOOPS_R2_BUCKET")

    def _output_bucket(self) -> str:
        return self._env("HOOPS_R2_OUTPUT_BUCKET", "") or self._required_env("HOOPS_R2_BUCKET")

    def _upload_root_writable(self) -> bool:
        try:
            self._settings.upload_root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix=".hoopclips-editing-ready-", dir=str(self._settings.upload_root), delete=True):
                return True
        except Exception:
            return False

    def _env(self, key: str, default: str) -> str:
        import os

        return os.getenv(key, default)
