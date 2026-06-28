from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import subprocess
import tempfile
from typing import Dict, Optional

from .config import Settings
from .models import StoredAsset
from .upload_storage import UploadStorageAdapter


@dataclass(frozen=True)
class PostUploadArtifacts:
    proxy_storage_key: str
    thumbnail_storage_key: str
    waveform_storage_key: str
    metadata: Dict[str, object]


async def generate_post_upload_artifacts(
    asset: StoredAsset,
    settings: Settings,
    storage: UploadStorageAdapter,
) -> PostUploadArtifacts:
    proxy_key = f"assets/{asset.asset_id}/proxy/proxy.mp4"
    thumbnail_key = f"assets/{asset.asset_id}/thumbnails/preview_0001.jpg"
    waveform_key = f"assets/{asset.asset_id}/metadata/waveform.json"

    source = await storage.materialize_storage_key(asset.storage_key, asset.filename)
    try:
        with tempfile.TemporaryDirectory(prefix="hoops-post-upload-", dir=str(settings.upload_root)) as temp_dir:
            work_dir = Path(temp_dir)
            proxy_path = work_dir / "proxy.mp4"
            thumbnail_path = work_dir / "preview_0001.jpg"
            metadata = _probe_metadata(source.local_path)
            try:
                _generate_proxy(source.local_path, proxy_path)
                storage.put_file(proxy_key, proxy_path, "video/mp4")
                thumbnail_generated = _generate_thumbnail(source.local_path, thumbnail_path, metadata)
                if thumbnail_generated:
                    storage.put_file(thumbnail_key, thumbnail_path, "image/jpeg")
                else:
                    storage.put_bytes(thumbnail_key, _placeholder_thumbnail(asset), "image/jpeg")
                metadata["postUploadMode"] = "ffmpeg"
            except Exception as error:
                storage.copy_object(asset.storage_key, proxy_key, "video/mp4")
                storage.put_bytes(thumbnail_key, _placeholder_thumbnail(asset), "image/jpeg")
                metadata["postUploadMode"] = "fallback_copy"
                metadata["fallbackReason"] = type(error).__name__

            waveform = _waveform_metadata(asset, metadata)
            storage.put_json(waveform_key, waveform)
            return PostUploadArtifacts(
                proxy_storage_key=proxy_key,
                thumbnail_storage_key=thumbnail_key,
                waveform_storage_key=waveform_key,
                metadata=waveform,
            )
    finally:
        source.cleanup()


def _probe_metadata(source_path: Path) -> Dict[str, object]:
    ffprobe = os.getenv("HOOPS_FFPROBE_BINARY", "ffprobe")
    command = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(source_path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        payload = json.loads(result.stdout or "{}")
    except Exception:
        return {"durationSeconds": None, "hasAudio": None, "hasVideo": None, "probeOk": False}

    streams = payload.get("streams") if isinstance(payload, dict) else []
    format_payload = payload.get("format") if isinstance(payload, dict) else {}
    duration = None
    if isinstance(format_payload, dict):
        try:
            duration = float(format_payload.get("duration"))
        except (TypeError, ValueError):
            duration = None
    return {
        "durationSeconds": duration,
        "hasAudio": any(stream.get("codec_type") == "audio" for stream in streams if isinstance(stream, dict)),
        "hasVideo": any(stream.get("codec_type") == "video" for stream in streams if isinstance(stream, dict)),
        "probeOk": True,
    }


def _generate_proxy(source_path: Path, proxy_path: Path) -> None:
    ffmpeg = os.getenv("HOOPS_FFMPEG_BINARY", "ffmpeg")
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        "scale='min(960,iw)':-2",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(proxy_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)


def _generate_thumbnail(source_path: Path, thumbnail_path: Path, metadata: Dict[str, object]) -> bool:
    ffmpeg = os.getenv("HOOPS_FFMPEG_BINARY", "ffmpeg")
    duration = metadata.get("durationSeconds")
    try:
        seek_seconds = max(0.0, min(float(duration or 0.0) / 2.0, 3.0))
    except (TypeError, ValueError):
        seek_seconds = 0.0
    command = [
        ffmpeg,
        "-y",
        "-ss",
        f"{seek_seconds:.3f}",
        "-i",
        str(source_path),
        "-frames:v",
        "1",
        str(thumbnail_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
    except Exception:
        return False
    return thumbnail_path.exists() and thumbnail_path.stat().st_size > 0


def _waveform_metadata(asset: StoredAsset, metadata: Dict[str, object]) -> Dict[str, object]:
    return {
        "assetId": asset.asset_id,
        "storageKey": asset.storage_key,
        "durationSeconds": metadata.get("durationSeconds") or asset.duration_seconds,
        "hasAudio": metadata.get("hasAudio"),
        "hasVideo": metadata.get("hasVideo"),
        "probeOk": metadata.get("probeOk"),
        "postUploadMode": metadata.get("postUploadMode"),
        "fallbackReason": metadata.get("fallbackReason"),
        "peaks": [],
        "schemaVersion": "waveform-metadata-v1",
    }


def _placeholder_thumbnail(asset: StoredAsset) -> bytes:
    return f"HoopClips thumbnail placeholder for {asset.asset_id}\n".encode("utf-8")
