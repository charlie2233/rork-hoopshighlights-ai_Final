from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .interfaces import ArtifactWriter


class LocalArtifactWriter(ArtifactWriter):
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write_manifest(self, manifest: dict[str, Any], job_id: str) -> Path:
        job_dir = self.base_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        path = job_dir / "result-manifest.json"
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return path

    def write_artifact(self, job_id: str, name: str, content: bytes, media_type: str = "application/octet-stream") -> Path:
        job_dir = self.base_dir / job_id / "artifacts"
        job_dir.mkdir(parents=True, exist_ok=True)
        path = job_dir / name
        path.write_bytes(content)
        return path


def build_manifest_dict(manifest: Any) -> dict[str, Any]:
    if hasattr(manifest, "model_dump"):
        payload = manifest.model_dump(mode="json", exclude_none=True)
    else:
        payload = dict(manifest)
    payload.setdefault("generatedAt", datetime.now(timezone.utc).isoformat())
    return payload
