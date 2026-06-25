from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from app.upload_storage import ObjectStorageCompatibleUploadStorageAdapter


REQUIRED_ENV_GROUPS = (
    ("HOOPS_OBJECT_STORAGE_BUCKET", "HOOPS_OBJECT_STORAGE_ENDPOINT_URL", "HOOPS_OBJECT_STORAGE_ACCESS_KEY_ID", "HOOPS_OBJECT_STORAGE_SECRET_ACCESS_KEY"),
    ("HOOPS_R2_BUCKET", "HOOPS_R2_ENDPOINT_URL", "HOOPS_R2_ACCESS_KEY_ID", "HOOPS_R2_SECRET_ACCESS_KEY"),
)


@dataclass(frozen=True)
class SmokeSettings:
    upload_root: Path
    signed_upload_ttl_seconds: int = 900


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the managed object-storage upload adapter without printing secrets.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--allow-missing", action="store_true", help="Return success with skipped status when object-storage env is missing.")
    parser.add_argument("--keep-objects", action="store_true", help="Keep smoke objects for provider-side inspection.")
    args = parser.parse_args()

    env_status = _env_status()
    if not env_status["configured"]:
        payload = {
            "status": "skipped",
            "reason": "object_storage_env_missing",
            "missing": env_status["missing"],
            "checkedAt": _now_iso(),
        }
        _emit(payload, as_json=args.json)
        return 0 if args.allow_missing else 2

    try:
        payload = asyncio.run(_run_smoke(keep_objects=args.keep_objects))
    except Exception as error:
        payload = {
            "status": "failed",
            "reason": error.__class__.__name__,
            "checkedAt": _now_iso(),
        }
        _emit(payload, as_json=args.json)
        return 1

    _emit(payload, as_json=args.json)
    return 0


async def _run_smoke(*, keep_objects: bool) -> dict:
    import boto3

    with tempfile.TemporaryDirectory(prefix="hoops-object-storage-smoke-") as temp_dir:
        settings = SmokeSettings(upload_root=Path(temp_dir))
        adapter = ObjectStorageCompatibleUploadStorageAdapter(settings)  # type: ignore[arg-type]
        smoke_id = uuid4().hex
        prefix = f"smoke/upload-adapter/{smoke_id}"
        source_key = f"{prefix}/source.mp4"
        proxy_key = f"{prefix}/proxy/proxy.mp4"
        metadata_key = f"{prefix}/metadata/waveform.json"
        copied_key = f"{prefix}/copy/source-copy.mp4"
        source_bytes = b"hoopclips managed object storage smoke\n"

        adapter.put_bytes(source_key, source_bytes, "video/mp4")
        if not await adapter.object_exists(source_key):
            raise RuntimeError("source_object_missing_after_put")

        materialized = await adapter.materialize_storage_key(source_key, "source.mp4")
        try:
            if materialized.local_path.read_bytes() != source_bytes:
                raise RuntimeError("materialized_source_mismatch")
        finally:
            materialized.cleanup()

        adapter.copy_object(source_key, copied_key, "video/mp4")
        if not await adapter.object_exists(copied_key):
            raise RuntimeError("copied_object_missing")

        adapter.put_bytes(proxy_key, b"proxy-bytes", "video/mp4")
        adapter.put_json(metadata_key, {"assetId": "smoke", "points": [0.0, 0.5, 1.0]})
        for key in (proxy_key, metadata_key):
            if not await adapter.object_exists(key):
                raise RuntimeError("artifact_object_missing")

        if not keep_objects:
            _delete_objects(boto3, [source_key, copied_key, proxy_key, metadata_key])

        return {
            "status": "passed",
            "checkedAt": _now_iso(),
            "objectCount": 4,
            "keptObjects": keep_objects,
            "prefixHash": _hash_value(prefix),
            "bucketConfigured": bool(os.getenv("HOOPS_OBJECT_STORAGE_BUCKET") or os.getenv("HOOPS_R2_BUCKET")),
            "endpointConfigured": bool(os.getenv("HOOPS_OBJECT_STORAGE_ENDPOINT_URL") or os.getenv("HOOPS_R2_ENDPOINT_URL")),
        }


def _delete_objects(boto3_module, keys: list[str]) -> None:
    bucket = os.getenv("HOOPS_OBJECT_STORAGE_BUCKET") or os.getenv("HOOPS_R2_BUCKET")
    if not bucket:
        return
    client = boto3_module.client(
        "s3",
        endpoint_url=os.getenv("HOOPS_OBJECT_STORAGE_ENDPOINT_URL") or os.getenv("HOOPS_R2_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("HOOPS_OBJECT_STORAGE_ACCESS_KEY_ID") or os.getenv("HOOPS_R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("HOOPS_OBJECT_STORAGE_SECRET_ACCESS_KEY") or os.getenv("HOOPS_R2_SECRET_ACCESS_KEY"),
        region_name=os.getenv("HOOPS_OBJECT_STORAGE_REGION") or os.getenv("HOOPS_R2_REGION") or "auto",
    )
    client.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": key} for key in keys]})


def _env_status() -> dict:
    for group in REQUIRED_ENV_GROUPS:
        missing = [key for key in group if not os.getenv(key)]
        if not missing:
            return {"configured": True, "missing": []}
    missing_by_group = {
        group[0].replace("_BUCKET", "").replace("HOOPS_", "").lower(): [key for key in group if not os.getenv(key)]
        for group in REQUIRED_ENV_GROUPS
    }
    return {"configured": False, "missing": missing_by_group}


def _emit(payload: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"status={payload['status']}")
    if payload.get("reason"):
        print(f"reason={payload['reason']}")
    if payload.get("prefixHash"):
        print(f"prefixHash={payload['prefixHash']}")


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
