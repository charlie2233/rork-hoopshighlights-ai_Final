from __future__ import annotations

from datetime import datetime
import asyncio
from typing import Any, Dict, Optional, Protocol

from .config import Settings
from .models import AssetStatus, StoredAsset, UploadMode, now_utc


class AssetStore(Protocol):
    async def create_asset(self, asset: StoredAsset) -> StoredAsset:
        ...

    async def get_asset(self, asset_id: str) -> Optional[StoredAsset]:
        ...

    async def update_asset(self, asset_id: str, **updates: Any) -> StoredAsset:
        ...


class InMemoryAssetStore:
    def __init__(self) -> None:
        self._assets: Dict[str, StoredAsset] = {}
        self._lock = asyncio.Lock()

    async def create_asset(self, asset: StoredAsset) -> StoredAsset:
        async with self._lock:
            self._assets[asset.asset_id] = asset
            return asset

    async def get_asset(self, asset_id: str) -> Optional[StoredAsset]:
        async with self._lock:
            return self._assets.get(asset_id)

    async def update_asset(self, asset_id: str, **updates: Any) -> StoredAsset:
        async with self._lock:
            asset = self._assets[asset_id]
            for key, value in updates.items():
                setattr(asset, key, value)
            asset.updated_at = now_utc()
            self._assets[asset_id] = asset
            return asset


class FirestoreAssetStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._firestore = self._import_firestore()
        project = settings.gcp_project_id or None
        self._client = self._firestore.Client(project=project)

    async def create_asset(self, asset: StoredAsset) -> StoredAsset:
        await asyncio.to_thread(self._asset_ref(asset.asset_id).set, self._serialize_asset(asset))
        return asset

    async def get_asset(self, asset_id: str) -> Optional[StoredAsset]:
        snapshot = await asyncio.to_thread(self._asset_ref(asset_id).get)
        if not snapshot.exists:
            return None
        return self._deserialize_asset(snapshot.to_dict())

    async def update_asset(self, asset_id: str, **updates: Any) -> StoredAsset:
        asset = await self.get_asset(asset_id)
        if asset is None:
            raise KeyError(asset_id)
        for key, value in updates.items():
            setattr(asset, key, value)
        asset.updated_at = now_utc()
        await asyncio.to_thread(self._asset_ref(asset_id).set, self._serialize_asset(asset), merge=False)
        return asset

    def _asset_ref(self, asset_id: str):
        return self._client.collection(self._settings.firestore_assets_collection).document(asset_id)

    def _serialize_asset(self, asset: StoredAsset) -> Dict[str, Any]:
        return {
            "assetId": asset.asset_id,
            "installId": asset.install_id,
            "filename": asset.filename,
            "contentType": asset.content_type,
            "fileSizeBytes": asset.file_size_bytes,
            "durationSeconds": asset.duration_seconds,
            "appVersion": asset.app_version,
            "analysisVersion": asset.analysis_version,
            "storageKey": asset.storage_key,
            "createdAt": asset.created_at,
            "updatedAt": asset.updated_at,
            "expiresAt": asset.expires_at,
            "uploadMode": asset.upload_mode.value,
            "status": asset.status.value,
            "uploadId": asset.upload_id,
            "partSizeBytes": asset.part_size_bytes,
            "partCount": asset.part_count,
            "uploadedBytes": asset.uploaded_bytes,
            "parts": {str(key): value for key, value in asset.parts.items()},
            "proxyStorageKey": asset.proxy_storage_key,
            "thumbnailStorageKeys": asset.thumbnail_storage_keys,
            "waveformStorageKey": asset.waveform_storage_key,
            "failureReason": asset.failure_reason,
        }

    def _deserialize_asset(self, payload: Dict[str, Any]) -> StoredAsset:
        parts = {
            int(part_number): str(etag)
            for part_number, etag in dict(payload.get("parts") or {}).items()
        }
        return StoredAsset(
            asset_id=payload["assetId"],
            install_id=payload["installId"],
            filename=payload["filename"],
            content_type=payload["contentType"],
            file_size_bytes=int(payload["fileSizeBytes"]),
            duration_seconds=float(payload["durationSeconds"]),
            app_version=payload.get("appVersion") or "unknown",
            analysis_version=payload.get("analysisVersion") or "cloud-v1",
            storage_key=payload["storageKey"],
            created_at=_coerce_datetime(payload["createdAt"]),
            updated_at=_coerce_datetime(payload["updatedAt"]),
            expires_at=_coerce_datetime(payload["expiresAt"]),
            upload_mode=UploadMode(payload.get("uploadMode") or UploadMode.SINGLE.value),
            status=AssetStatus(payload.get("status") or AssetStatus.INITIALIZED.value),
            upload_id=payload.get("uploadId"),
            part_size_bytes=payload.get("partSizeBytes"),
            part_count=payload.get("partCount"),
            uploaded_bytes=int(payload.get("uploadedBytes") or 0),
            parts=parts,
            proxy_storage_key=payload.get("proxyStorageKey"),
            thumbnail_storage_keys=list(payload.get("thumbnailStorageKeys") or []),
            waveform_storage_key=payload.get("waveformStorageKey"),
            failure_reason=payload.get("failureReason"),
        )

    def _import_firestore(self):
        try:
            from google.cloud import firestore
        except ImportError as error:
            raise RuntimeError(
                "google-cloud-firestore is required for staging/production asset records."
            ) from error
        return firestore


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError("Expected datetime-compatible Firestore field.")
