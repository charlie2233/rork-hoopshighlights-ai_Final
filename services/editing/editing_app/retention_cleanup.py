from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, Dict, List

from .models import StoredRenderJob, now_utc, parse_datetime
from .render_state import DurableRenderStateStore
from .render_storage import RenderStorage


@dataclass(frozen=True)
class CleanupCandidate:
    render_job_id: str
    edit_job_id: str
    revision_id: str | None
    retention_class: str
    expires_at: datetime
    object_keys: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "renderJobId": self.render_job_id,
            "editJobId": self.edit_job_id,
            "revisionId": self.revision_id,
            "retentionClass": self.retention_class,
            "expiresAt": self.expires_at.isoformat(),
            "objectKeys": self.object_keys,
        }


def collect_expired_render_artifacts(
    store: DurableRenderStateStore,
    *,
    now: datetime | None = None,
    allowed_retention_classes: set[str] | None = None,
) -> List[CleanupCandidate]:
    cutoff = now or now_utc()
    candidates: List[CleanupCandidate] = []
    for job in store.list_render_jobs():
        candidate = cleanup_candidate_for_job(job, cutoff, allowed_retention_classes)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def cleanup_candidate_for_job(
    job: StoredRenderJob,
    now: datetime,
    allowed_retention_classes: set[str] | None,
) -> CleanupCandidate | None:
    metadata = job.retention_metadata or {}
    if metadata.get("deleteEligible") is not True:
        return None
    retention_class = str(metadata.get("retentionClass") or "")
    if allowed_retention_classes and retention_class not in allowed_retention_classes:
        return None
    expires_at = parse_datetime(metadata.get("expiresAt")) or job.expires_at
    if expires_at is None or expires_at > now:
        return None
    object_keys = [
        key
        for key in [
            job.output_object_key,
            job.render_log_object_key,
            f"render_state/render_jobs/{job.render_job_id}.json",
        ]
        if key
    ]
    if not object_keys:
        return None
    return CleanupCandidate(
        render_job_id=job.render_job_id,
        edit_job_id=job.edit_job_id,
        revision_id=job.revision_id,
        retention_class=retention_class,
        expires_at=expires_at,
        object_keys=object_keys,
    )


def run_cleanup(
    storage: RenderStorage,
    store: DurableRenderStateStore,
    *,
    execute: bool = False,
    now: datetime | None = None,
    allowed_retention_classes: set[str] | None = None,
) -> Dict[str, Any]:
    candidates = collect_expired_render_artifacts(store, now=now, allowed_retention_classes=allowed_retention_classes)
    deleted_keys: List[str] = []
    if execute:
        for candidate in candidates:
            for object_key in candidate.object_keys:
                storage.delete_object(object_key)
                deleted_keys.append(object_key)
    return {
        "mode": "execute" if execute else "dry-run",
        "candidateCount": len(candidates),
        "candidates": [candidate.to_dict() for candidate in candidates],
        "deletedObjectKeys": deleted_keys,
    }


def format_cleanup_report(report: Dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
