from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .models import StoredRenderJob, now_utc, parse_datetime
from .render_storage import RenderStorage


class DurableRenderStateStore:
    """Persist render state, leases, edit jobs, revisions, and lookup indexes."""

    def __init__(self, storage: RenderStorage) -> None:
        self._storage = storage

    def save_job(self, job: StoredRenderJob) -> None:
        self._storage.put_json(self._job_key(job.render_job_id), json.dumps(job.to_durable_dict(), indent=2, sort_keys=True))
        self._save_indexes(job)

    def _save_indexes(self, job: StoredRenderJob) -> None:
        self._storage.put_json(
            self._latest_edit_key(job.edit_job_id),
            json.dumps(
                {
                    "version": "render-state-index-v1",
                    "editJobId": job.edit_job_id,
                    "renderJobId": job.render_job_id,
                    "revisionId": job.revision_id,
                    "updatedAt": job.updated_at.isoformat(),
                },
                indent=2,
                sort_keys=True,
            ),
        )
        if job.idempotency_key:
            self.reserve_idempotency_key(job)
        self._append_install_index(job)

    def save_job_if_lease(self, job: StoredRenderJob, lease_token: str) -> bool:
        key = self._job_key(job.render_job_id)
        latest_payload, etag = self._storage.get_json_with_etag(key)
        if not isinstance(latest_payload, dict) or not etag:
            return False
        latest = StoredRenderJob.from_durable_dict(latest_payload)
        if latest.status in {"rendered", "failed", "failed_timeout", "cancelled"}:
            return False
        if latest.lease_token != lease_token:
            return False
        if latest.lease_expires_at and latest.lease_expires_at <= now_utc():
            return False
        if not self._storage.put_json_if_match(key, json.dumps(job.to_durable_dict(), indent=2, sort_keys=True), etag):
            return False
        self._save_indexes(job)
        return True

    def reserve_idempotency_key(self, job: StoredRenderJob) -> bool:
        if not job.idempotency_key:
            return True
        key = self._idempotency_key(job.idempotency_key)
        existing = self._storage.get_json(key)
        if isinstance(existing, dict):
            return existing.get("renderJobId") == job.render_job_id
        return self._storage.put_json_if_absent(key, self._idempotency_payload(job))

    def acquire_render_lease(
        self,
        render_job_id: str,
        lease_owner: str,
        lease_token: str,
        acquired_at: Optional[datetime] = None,
        ttl_seconds: int = 300,
    ) -> Optional[StoredRenderJob]:
        key = self._job_key(render_job_id)
        payload, etag = self._storage.get_json_with_etag(key)
        if not isinstance(payload, dict) or not etag:
            return None
        job = StoredRenderJob.from_durable_dict(payload)
        now = acquired_at or now_utc()
        if job.status in {"rendered", "failed", "failed_timeout", "cancelled"}:
            return None
        if job.lease_token and job.lease_expires_at and job.lease_expires_at > now:
            return None
        job.status = "rendering"
        job.lease_owner = lease_owner
        job.lease_token = lease_token
        job.lease_acquired_at = now
        job.lease_expires_at = now + timedelta(seconds=ttl_seconds)
        job.heartbeat_at = now
        job.started_at = job.started_at or now
        job.updated_at = now
        if not self._storage.put_json_if_match(key, json.dumps(job.to_durable_dict(), indent=2, sort_keys=True), etag):
            return None
        confirmed = self.load_job(render_job_id)
        if confirmed is None or confirmed.lease_token != lease_token:
            return None
        return confirmed

    def load_job(self, render_job_id: str) -> Optional[StoredRenderJob]:
        payload = self._storage.get_json(self._job_key(render_job_id))
        if not isinstance(payload, dict):
            return None
        try:
            return StoredRenderJob.from_durable_dict(payload)
        except Exception:
            return None

    def load_latest_for_edit(self, edit_job_id: str) -> Optional[StoredRenderJob]:
        index = self._storage.get_json(self._latest_edit_key(edit_job_id))
        render_job_id = index.get("renderJobId") if isinstance(index, dict) else None
        if not isinstance(render_job_id, str):
            return None
        return self.load_job(render_job_id)

    def load_by_idempotency_key(self, idempotency_key: str) -> Optional[StoredRenderJob]:
        index = self._storage.get_json(self._idempotency_key(idempotency_key))
        render_job_id = index.get("renderJobId") if isinstance(index, dict) else None
        if not isinstance(render_job_id, str):
            return None
        return self.load_job(render_job_id)

    def load_jobs_for_install(self, install_id: str) -> List[StoredRenderJob]:
        index = self._storage.get_json(self._install_key(install_id))
        render_job_ids = index.get("renderJobIds") if isinstance(index, dict) else None
        if not isinstance(render_job_ids, list):
            return []
        jobs: List[StoredRenderJob] = []
        for render_job_id in render_job_ids:
            if not isinstance(render_job_id, str):
                continue
            job = self.load_job(render_job_id)
            if job is not None:
                jobs.append(job)
        return jobs

    def list_render_jobs(self) -> List[StoredRenderJob]:
        jobs: List[StoredRenderJob] = []
        for key in self._storage.list_object_keys("render_state/render_jobs"):
            if not key.endswith(".json"):
                continue
            payload = self._storage.get_json(key)
            if not isinstance(payload, dict):
                continue
            try:
                jobs.append(StoredRenderJob.from_durable_dict(payload))
            except Exception:
                continue
        return jobs

    def save_edit_job_payload(self, edit_job_id: str, payload: Dict[str, object]) -> None:
        self._storage.put_json(self._edit_job_key(edit_job_id), json.dumps(payload, indent=2, sort_keys=True))

    def load_edit_job_payload(self, edit_job_id: str) -> Optional[Dict[str, object]]:
        payload = self._storage.get_json(self._edit_job_key(edit_job_id))
        return payload if isinstance(payload, dict) else None

    def reserve_edit_job_idempotency_key(
        self,
        edit_job_id: str,
        install_id: str,
        idempotency_key: Optional[str],
        updated_at: datetime,
    ) -> bool:
        if not idempotency_key:
            return True
        key = self._edit_job_idempotency_key(idempotency_key)
        existing = self._storage.get_json(key)
        if isinstance(existing, dict):
            return existing.get("editJobId") == edit_job_id
        return self._storage.put_json_if_absent(
            key,
            json.dumps(
                {
                    "version": "edit-job-idempotency-v1",
                    "idempotencyKeyHash": self._hash(idempotency_key),
                    "editJobId": edit_job_id,
                    "installIdHash": self._hash(install_id),
                    "updatedAt": updated_at.isoformat(),
                },
                indent=2,
                sort_keys=True,
            ),
        )

    def load_edit_job_id_by_idempotency_key(self, idempotency_key: str) -> Optional[str]:
        index = self._storage.get_json(self._edit_job_idempotency_key(idempotency_key))
        edit_job_id = index.get("editJobId") if isinstance(index, dict) else None
        return edit_job_id if isinstance(edit_job_id, str) else None

    def save_render_request_payload(self, render_job_id: str, payload: Dict[str, object]) -> None:
        self._storage.put_json(self._render_request_key(render_job_id), json.dumps(payload, indent=2, sort_keys=True))

    def load_render_request_payload(self, render_job_id: str) -> Optional[Dict[str, object]]:
        payload = self._storage.get_json(self._render_request_key(render_job_id))
        return payload if isinstance(payload, dict) else None

    def save_edit_plan_payload(self, edit_job_id: str, plan_id: str, payload: Dict[str, object]) -> None:
        self._storage.put_json(self._edit_plan_key(edit_job_id, plan_id), json.dumps(payload, indent=2, sort_keys=True))

    def load_edit_plan_payload(self, edit_job_id: str, plan_id: str) -> Optional[Dict[str, object]]:
        payload = self._storage.get_json(self._edit_plan_key(edit_job_id, plan_id))
        return payload if isinstance(payload, dict) else None

    def save_revision_payload(self, edit_job_id: str, revision_id: str, payload: Dict[str, object]) -> None:
        self._storage.put_json(self._revision_key(edit_job_id, revision_id), json.dumps(payload, indent=2, sort_keys=True))
        self._append_revision_index(edit_job_id, revision_id)

    def load_revision_payload(self, edit_job_id: str, revision_id: str) -> Optional[Dict[str, object]]:
        payload = self._storage.get_json(self._revision_key(edit_job_id, revision_id))
        return payload if isinstance(payload, dict) else None

    def load_revision_payloads(self, edit_job_id: str) -> List[Dict[str, object]]:
        index = self._storage.get_json(self._revision_index_key(edit_job_id))
        revision_ids = index.get("revisionIds") if isinstance(index, dict) else None
        if not isinstance(revision_ids, list):
            return []
        revisions: List[Dict[str, object]] = []
        for revision_id in revision_ids:
            if not isinstance(revision_id, str):
                continue
            payload = self.load_revision_payload(edit_job_id, revision_id)
            if payload is not None:
                revisions.append(payload)
        return revisions

    def _append_install_index(self, job: StoredRenderJob) -> None:
        key = self._install_key(job.install_id)
        index = self._storage.get_json(key)
        render_job_ids = index.get("renderJobIds") if isinstance(index, dict) else None
        ids = [value for value in render_job_ids if isinstance(value, str)] if isinstance(render_job_ids, list) else []
        if job.render_job_id not in ids:
            ids.append(job.render_job_id)
        self._storage.put_json(
            key,
            json.dumps(
                {
                    "version": "render-state-install-index-v1",
                    "installIdHash": self._hash(job.install_id),
                    "renderJobIds": ids[-200:],
                    "updatedAt": job.updated_at.isoformat(),
                },
                indent=2,
                sort_keys=True,
            ),
        )

    def _append_revision_index(self, edit_job_id: str, revision_id: str) -> None:
        key = self._revision_index_key(edit_job_id)
        index = self._storage.get_json(key)
        revision_ids = index.get("revisionIds") if isinstance(index, dict) else None
        ids = [value for value in revision_ids if isinstance(value, str)] if isinstance(revision_ids, list) else []
        if revision_id not in ids:
            ids.append(revision_id)
        self._storage.put_json(
            key,
            json.dumps(
                {
                    "version": "edit-revision-index-v1",
                    "editJobId": edit_job_id,
                    "revisionIds": ids[-200:],
                    "updatedAt": now_utc().isoformat(),
                },
                indent=2,
                sort_keys=True,
            ),
        )

    def _idempotency_payload(self, job: StoredRenderJob) -> str:
        return json.dumps(
            {
                "version": "render-state-idempotency-v1",
                "idempotencyKeyHash": self._hash(job.idempotency_key or ""),
                "editJobId": job.edit_job_id,
                "renderJobId": job.render_job_id,
                "revisionId": job.revision_id,
                "updatedAt": job.updated_at.isoformat(),
            },
            indent=2,
            sort_keys=True,
        )

    @staticmethod
    def _job_key(render_job_id: str) -> str:
        return f"render_state/render_jobs/{render_job_id}.json"

    @staticmethod
    def _latest_edit_key(edit_job_id: str) -> str:
        return f"render_state/edit_jobs/{edit_job_id}/latest.json"

    @staticmethod
    def _edit_job_key(edit_job_id: str) -> str:
        return f"render_state/edit_jobs/{edit_job_id}/edit_job.json"

    @staticmethod
    def _render_request_key(render_job_id: str) -> str:
        return f"render_state/render_requests/{render_job_id}.json"

    @staticmethod
    def _edit_plan_key(edit_job_id: str, plan_id: str) -> str:
        return f"edits/{edit_job_id}/plans/{plan_id}.json"

    @staticmethod
    def _revision_key(edit_job_id: str, revision_id: str) -> str:
        return f"edits/{edit_job_id}/revisions/{revision_id}.json"

    @staticmethod
    def _revision_index_key(edit_job_id: str) -> str:
        return f"render_state/edit_jobs/{edit_job_id}/revisions.json"

    @classmethod
    def _idempotency_key(cls, idempotency_key: str) -> str:
        return f"render_state/idempotency/{cls._hash(idempotency_key)}.json"

    @classmethod
    def idempotency_index_key(cls, idempotency_key: str) -> str:
        return cls._idempotency_key(idempotency_key)

    @classmethod
    def _edit_job_idempotency_key(cls, idempotency_key: str) -> str:
        return f"render_state/edit_job_idempotency/{cls._hash(idempotency_key)}.json"

    @classmethod
    def _install_key(cls, install_id: str) -> str:
        return f"render_state/installs/{cls._hash(install_id)}.json"

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
