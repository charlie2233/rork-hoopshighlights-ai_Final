from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import threading
from typing import Dict, List, Optional, Tuple

from .config import EditingSettings
from .models import now_utc

_LOCAL_CONDITIONAL_WRITE_LOCK = threading.Lock()


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

    def put_json_if_absent(self, object_key: str, payload: str) -> bool:
        if self._provider == "r2":
            try:
                self._r2_client().put_object(
                    Bucket=self._output_bucket(),
                    Key=object_key,
                    Body=payload.encode("utf-8"),
                    ContentType="application/json",
                    IfNoneMatch="*",
                )
                return True
            except Exception as error:
                if self._is_precondition_failure(error):
                    return False
                raise
        path = self._local_object_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCAL_CONDITIONAL_WRITE_LOCK:
            if path.exists():
                return False
            path.write_text(payload, encoding="utf-8")
            return True

    def put_json_if_match(self, object_key: str, payload: str, etag: str) -> bool:
        if not etag:
            return False
        if self._provider == "r2":
            try:
                self._r2_client().put_object(
                    Bucket=self._output_bucket(),
                    Key=object_key,
                    Body=payload.encode("utf-8"),
                    ContentType="application/json",
                    IfMatch=etag,
                )
                return True
            except Exception as error:
                if self._is_precondition_failure(error):
                    return False
                raise
        path = self._local_object_path(object_key)
        with _LOCAL_CONDITIONAL_WRITE_LOCK:
            if not path.is_file() or self._local_etag(path) != etag:
                return False
            path.write_text(payload, encoding="utf-8")
            return True

    def get_json(self, object_key: str) -> Optional[Dict[str, object]]:
        payload, _etag = self.get_json_with_etag(object_key)
        return payload

    def get_json_with_etag(self, object_key: str) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
        try:
            if self._provider == "r2":
                response = self._r2_client().get_object(Bucket=self._output_bucket(), Key=object_key)
                body = response["Body"].read().decode("utf-8")
                etag = str(response.get("ETag") or "").strip('"')
                return json.loads(body), etag
            path = self._local_object_path(object_key)
            if not path.is_file():
                return None, None
            return json.loads(path.read_text(encoding="utf-8")), self._local_etag(path)
        except Exception:
            return None, None

    def put_file(self, object_key: str, source_path: Path, content_type: str, metadata: Optional[Dict[str, str]] = None) -> None:
        if not source_path.exists() or source_path.stat().st_size <= 0:
            raise EditingServiceError(500, "render_output_missing", "Renderer did not produce a usable output file.")
        if self._provider == "r2":
            client = self._r2_client()
            extra_args = {"ContentType": content_type}
            if metadata:
                extra_args["Metadata"] = {key: str(value)[:1024] for key, value in metadata.items() if value is not None}
            client.upload_file(
                str(source_path),
                self._output_bucket(),
                object_key,
                ExtraArgs=extra_args,
            )
            head = client.head_object(Bucket=self._output_bucket(), Key=object_key)
            if int(head.get("ContentLength") or 0) <= 0:
                raise EditingServiceError(500, "render_upload_unverified", "Uploaded render object could not be verified.")
            return
        target = self._local_object_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        if metadata:
            metadata_path = target.with_suffix(target.suffix + ".metadata.json")
            metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

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

    def list_object_keys(self, prefix: str) -> List[str]:
        if self._provider == "r2":
            client = self._r2_client()
            keys: List[str] = []
            continuation_token: Optional[str] = None
            while True:
                kwargs = {"Bucket": self._output_bucket(), "Prefix": prefix}
                if continuation_token:
                    kwargs["ContinuationToken"] = continuation_token
                response = client.list_objects_v2(**kwargs)
                for item in response.get("Contents", []):
                    key = item.get("Key")
                    if isinstance(key, str):
                        keys.append(key)
                if not response.get("IsTruncated"):
                    return keys
                continuation_token = response.get("NextContinuationToken")
        root = self._local_object_path(prefix)
        if root.is_file():
            return [prefix]
        if not root.exists():
            return []
        keys: List[str] = []
        for path in root.rglob("*"):
            if path.is_file() and not path.name.endswith(".metadata.json"):
                keys.append(str(path.relative_to(self._settings.upload_root)))
        return sorted(keys)

    def delete_object(self, object_key: str) -> None:
        if self._provider == "r2":
            self._r2_client().delete_object(Bucket=self._output_bucket(), Key=object_key)
            return
        path = self._local_object_path(object_key)
        if path.exists():
            path.unlink()
        metadata_path = path.with_suffix(path.suffix + ".metadata.json")
        if metadata_path.exists():
            metadata_path.unlink()

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

    @staticmethod
    def _is_precondition_failure(error: Exception) -> bool:
        response = getattr(error, "response", None)
        if not isinstance(response, dict):
            return False
        error_payload = response.get("Error")
        code = error_payload.get("Code") if isinstance(error_payload, dict) else None
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return str(code) in {"PreconditionFailed", "ConditionalRequestConflict", "412", "409"} or status in {409, 412}

    def _local_object_path(self, object_key: str) -> Path:
        safe_parts = [part for part in Path(object_key).parts if part not in {"", ".", ".."}]
        if not safe_parts:
            raise EditingServiceError(400, "invalid_object_key", "Object key is empty.")
        return self._settings.upload_root.joinpath(*safe_parts)

    @staticmethod
    def _local_etag(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

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
