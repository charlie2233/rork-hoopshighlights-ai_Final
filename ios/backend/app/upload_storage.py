from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
import hashlib
import json
import math
import re
import shutil
import tempfile
from typing import Dict, List, Optional, Protocol

from .config import Settings
from .models import APIError, MaterializedSource, StoredAsset, now_utc


@dataclass(frozen=True)
class PreparedUploadPart:
    part_number: int
    upload_url: str
    upload_headers: Dict[str, str]


@dataclass(frozen=True)
class PreparedSingleUpload:
    storage_key: str
    upload_url: str
    upload_headers: Dict[str, str]
    expires_at: object


@dataclass(frozen=True)
class PreparedMultipartUpload:
    storage_key: str
    upload_id: str
    part_size_bytes: int
    part_count: int
    parts: List[PreparedUploadPart]
    expires_at: object


class UploadStorageAdapter(Protocol):
    def storage_key_for(self, asset_id: str, filename: str) -> str:
        ...

    def prepare_single_upload(self, asset_id: str, storage_key: str, content_type: str) -> PreparedSingleUpload:
        ...

    def prepare_multipart_upload(
        self,
        asset_id: str,
        storage_key: str,
        content_type: str,
        file_size_bytes: int,
        part_size_bytes: int,
    ) -> PreparedMultipartUpload:
        ...

    def accept_local_upload(self, asset: StoredAsset, payload: bytes) -> str:
        ...

    def accept_local_part(self, asset: StoredAsset, part_number: int, payload: bytes) -> str:
        ...

    def complete_multipart_upload(self, asset: StoredAsset, parts: Dict[int, str]) -> str:
        ...

    def checksum_sha256_for_storage_key(self, storage_key: str) -> Optional[str]:
        ...

    def size_bytes_for_storage_key(self, storage_key: str) -> Optional[int]:
        ...

    async def object_exists(self, storage_key: str) -> bool:
        ...

    async def materialize_storage_key(self, storage_key: str, filename: str) -> MaterializedSource:
        ...

    def copy_object(self, source_key: str, destination_key: str, content_type: str) -> str:
        ...

    def put_json(self, storage_key: str, payload: dict) -> str:
        ...

    def put_bytes(self, storage_key: str, payload: bytes, content_type: str) -> str:
        ...

    def put_file(self, storage_key: str, source_path: Path, content_type: str) -> str:
        ...


class LocalDiskUploadStorageAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def storage_key_for(self, asset_id: str, filename: str) -> str:
        return "assets/{asset_id}/source/{filename}".format(
            asset_id=asset_id,
            filename=_sanitize_filename(filename),
        )

    def prepare_single_upload(self, asset_id: str, storage_key: str, content_type: str) -> PreparedSingleUpload:
        _ = storage_key
        expires_at = now_utc() + timedelta(seconds=self._settings.signed_upload_ttl_seconds)
        return PreparedSingleUpload(
            storage_key=storage_key,
            upload_url=f"{self._settings.host_base_url}/v1/internal/assets/{asset_id}/upload",
            upload_headers={"Content-Type": content_type},
            expires_at=expires_at,
        )

    def prepare_multipart_upload(
        self,
        asset_id: str,
        storage_key: str,
        content_type: str,
        file_size_bytes: int,
        part_size_bytes: int,
    ) -> PreparedMultipartUpload:
        part_count = max(1, math.ceil(file_size_bytes / part_size_bytes))
        expires_at = now_utc() + timedelta(seconds=self._settings.signed_upload_ttl_seconds)
        parts = [
            PreparedUploadPart(
                part_number=part_number,
                upload_url=f"{self._settings.host_base_url}/v1/internal/assets/{asset_id}/parts/{part_number}",
                upload_headers={"Content-Type": content_type},
            )
            for part_number in range(1, part_count + 1)
        ]
        return PreparedMultipartUpload(
            storage_key=storage_key,
            upload_id=f"local-{asset_id}",
            part_size_bytes=part_size_bytes,
            part_count=part_count,
            parts=parts,
            expires_at=expires_at,
        )

    def accept_local_upload(self, asset: StoredAsset, payload: bytes) -> str:
        target = self._local_path(asset.storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return str(target)

    def accept_local_part(self, asset: StoredAsset, part_number: int, payload: bytes) -> str:
        if part_number < 1:
            raise APIError(400, "invalid_part", "Multipart part numbers start at 1.")
        target = self._part_path(asset.asset_id, part_number)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return hashlib.sha256(payload).hexdigest()

    def complete_multipart_upload(self, asset: StoredAsset, parts: Dict[int, str]) -> str:
        if not parts:
            raise APIError(400, "missing_parts", "Multipart completion requires uploaded parts.")
        expected_count = asset.part_count or len(parts)
        missing = [part for part in range(1, expected_count + 1) if part not in parts]
        if missing:
            raise APIError(400, "missing_parts", "Multipart completion is missing uploaded parts.")

        target = self._local_path(asset.storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as output:
            for part_number in range(1, expected_count + 1):
                part_path = self._part_path(asset.asset_id, part_number)
                if not part_path.exists() or part_path.stat().st_size <= 0:
                    raise APIError(400, "missing_parts", "Multipart completion is missing uploaded part data.")
                with part_path.open("rb") as input_file:
                    shutil.copyfileobj(input_file, output)
        return str(target)

    def checksum_sha256_for_storage_key(self, storage_key: str) -> Optional[str]:
        path = self._local_path(storage_key)
        if not path.exists() or not path.is_file():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def size_bytes_for_storage_key(self, storage_key: str) -> Optional[int]:
        path = self._local_path(storage_key)
        if not path.exists() or not path.is_file():
            return None
        return path.stat().st_size

    async def object_exists(self, storage_key: str) -> bool:
        path = self._local_path(storage_key)
        return path.exists() and path.is_file() and path.stat().st_size > 0

    async def materialize_storage_key(self, storage_key: str, filename: str) -> MaterializedSource:
        _ = filename
        path = self._local_path(storage_key)
        if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
            raise APIError(400, "source_missing", "Source asset storage object was not found.")
        return MaterializedSource(local_path=path, cleanup_after_use=False)

    def copy_object(self, source_key: str, destination_key: str, content_type: str) -> str:
        _ = content_type
        source = self._local_path(source_key)
        if not source.exists() or not source.is_file():
            raise APIError(400, "source_missing", "Source asset storage object was not found.")
        destination = self._local_path(destination_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return destination_key

    def put_json(self, storage_key: str, payload: dict) -> str:
        path = self._local_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return storage_key

    def put_bytes(self, storage_key: str, payload: bytes, content_type: str) -> str:
        _ = content_type
        path = self._local_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return storage_key

    def put_file(self, storage_key: str, source_path: Path, content_type: str) -> str:
        _ = content_type
        if not source_path.exists() or source_path.stat().st_size <= 0:
            raise APIError(500, "artifact_missing", "Post-upload artifact was not generated.")
        target = self._local_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        return storage_key

    def _part_path(self, asset_id: str, part_number: int) -> Path:
        return self._settings.upload_root / "multipart" / asset_id / f"{part_number:05d}.part"

    def _local_path(self, storage_key: str) -> Path:
        safe_parts = [part for part in Path(storage_key).parts if part not in {"", ".", ".."}]
        if not safe_parts:
            raise APIError(400, "invalid_storage_key", "Storage key is empty.")
        return self._settings.upload_root.joinpath(*safe_parts)


class ObjectStorageCompatibleUploadStorageAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def storage_key_for(self, asset_id: str, filename: str) -> str:
        return "assets/{asset_id}/source/{filename}".format(
            asset_id=asset_id,
            filename=_sanitize_filename(filename),
        )

    def prepare_single_upload(self, asset_id: str, storage_key: str, content_type: str) -> PreparedSingleUpload:
        _ = asset_id
        expires_at = now_utc() + timedelta(seconds=self._settings.signed_upload_ttl_seconds)
        upload_url = self._client().generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket(), "Key": storage_key, "ContentType": content_type},
            ExpiresIn=self._settings.signed_upload_ttl_seconds,
        )
        return PreparedSingleUpload(
            storage_key=storage_key,
            upload_url=upload_url,
            upload_headers={"Content-Type": content_type},
            expires_at=expires_at,
        )

    def prepare_multipart_upload(
        self,
        asset_id: str,
        storage_key: str,
        content_type: str,
        file_size_bytes: int,
        part_size_bytes: int,
    ) -> PreparedMultipartUpload:
        _ = asset_id
        client = self._client()
        response = client.create_multipart_upload(Bucket=self._bucket(), Key=storage_key, ContentType=content_type)
        upload_id = response["UploadId"]
        part_count = max(1, math.ceil(file_size_bytes / part_size_bytes))
        expires_at = now_utc() + timedelta(seconds=self._settings.signed_upload_ttl_seconds)
        parts = [
            PreparedUploadPart(
                part_number=part_number,
                upload_url=client.generate_presigned_url(
                    "upload_part",
                    Params={
                        "Bucket": self._bucket(),
                        "Key": storage_key,
                        "UploadId": upload_id,
                        "PartNumber": part_number,
                    },
                    ExpiresIn=self._settings.signed_upload_ttl_seconds,
                ),
                upload_headers={},
            )
            for part_number in range(1, part_count + 1)
        ]
        return PreparedMultipartUpload(
            storage_key=storage_key,
            upload_id=upload_id,
            part_size_bytes=part_size_bytes,
            part_count=part_count,
            parts=parts,
            expires_at=expires_at,
        )

    def accept_local_upload(self, asset: StoredAsset, payload: bytes) -> str:
        _ = asset, payload
        raise APIError(404, "unsupported_upload", "Local upload emulation is disabled for object storage uploads.")

    def accept_local_part(self, asset: StoredAsset, part_number: int, payload: bytes) -> str:
        _ = asset, part_number, payload
        raise APIError(404, "unsupported_upload", "Local multipart upload emulation is disabled for object storage uploads.")

    def complete_multipart_upload(self, asset: StoredAsset, parts: Dict[int, str]) -> str:
        if not asset.upload_id:
            raise APIError(400, "missing_upload_id", "Multipart upload ID is missing.")
        client = self._client()
        completed_parts = [
            {"PartNumber": part_number, "ETag": etag}
            for part_number, etag in sorted(parts.items())
        ]
        client.complete_multipart_upload(
            Bucket=self._bucket(),
            Key=asset.storage_key,
            UploadId=asset.upload_id,
            MultipartUpload={"Parts": completed_parts},
        )
        return asset.storage_key

    def checksum_sha256_for_storage_key(self, storage_key: str) -> Optional[str]:
        _ = storage_key
        return None

    def size_bytes_for_storage_key(self, storage_key: str) -> Optional[int]:
        try:
            response = self._client().head_object(Bucket=self._bucket(), Key=storage_key)
        except Exception:
            return None
        return int(response.get("ContentLength") or 0)

    async def object_exists(self, storage_key: str) -> bool:
        try:
            response = self._client().head_object(Bucket=self._bucket(), Key=storage_key)
        except Exception:
            return False
        return int(response.get("ContentLength") or 0) > 0

    async def materialize_storage_key(self, storage_key: str, filename: str) -> MaterializedSource:
        local_name = _sanitize_filename(filename)
        temp_dir = Path(tempfile.mkdtemp(prefix="hoops-asset-source-", dir=str(self._settings.upload_root)))
        local_path = temp_dir / local_name
        try:
            self._client().download_file(self._bucket(), storage_key, str(local_path))
        except Exception as error:
            raise APIError(400, "source_missing", "Source asset storage object was not found.") from error
        return MaterializedSource(local_path=local_path, cleanup_after_use=True)

    def copy_object(self, source_key: str, destination_key: str, content_type: str) -> str:
        self._client().copy_object(
            Bucket=self._bucket(),
            CopySource={"Bucket": self._bucket(), "Key": source_key},
            Key=destination_key,
            ContentType=content_type,
            MetadataDirective="REPLACE",
        )
        return destination_key

    def put_json(self, storage_key: str, payload: dict) -> str:
        self._client().put_object(
            Bucket=self._bucket(),
            Key=storage_key,
            Body=json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"),
            ContentType="application/json",
        )
        return storage_key

    def put_bytes(self, storage_key: str, payload: bytes, content_type: str) -> str:
        self._client().put_object(Bucket=self._bucket(), Key=storage_key, Body=payload, ContentType=content_type)
        return storage_key

    def put_file(self, storage_key: str, source_path: Path, content_type: str) -> str:
        if not source_path.exists() or source_path.stat().st_size <= 0:
            raise APIError(500, "artifact_missing", "Post-upload artifact was not generated.")
        self._client().upload_file(
            str(source_path),
            self._bucket(),
            storage_key,
            ExtraArgs={"ContentType": content_type},
        )
        return storage_key

    def _client(self):
        import boto3

        return boto3.client(
            "s3",
            endpoint_url=self._env("HOOPS_OBJECT_STORAGE_ENDPOINT_URL") or self._env("HOOPS_R2_ENDPOINT_URL"),
            aws_access_key_id=self._env("HOOPS_OBJECT_STORAGE_ACCESS_KEY_ID") or self._env("HOOPS_R2_ACCESS_KEY_ID"),
            aws_secret_access_key=self._env("HOOPS_OBJECT_STORAGE_SECRET_ACCESS_KEY") or self._env("HOOPS_R2_SECRET_ACCESS_KEY"),
            region_name=self._env("HOOPS_OBJECT_STORAGE_REGION") or self._env("HOOPS_R2_REGION") or "auto",
        )

    def _bucket(self) -> str:
        bucket = self._env("HOOPS_OBJECT_STORAGE_BUCKET") or self._env("HOOPS_R2_BUCKET")
        if not bucket:
            raise RuntimeError("HOOPS_OBJECT_STORAGE_BUCKET or HOOPS_R2_BUCKET is required for object storage uploads.")
        return bucket

    def _env(self, key: str) -> Optional[str]:
        import os

        return os.getenv(key) or None


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name or "source.mp4"
    normalized = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return normalized[:120] or "source.mp4"
