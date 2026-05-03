from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

from .models import StoredRenderJob
from .render_storage import RenderStorage


class DurableRenderStateStore:
    """Persist render state and lookup indexes in the configured render storage."""

    def __init__(self, storage: RenderStorage) -> None:
        self._storage = storage

    def save_job(self, job: StoredRenderJob) -> None:
        self._storage.put_json(self._job_key(job.render_job_id), json.dumps(job.to_durable_dict(), indent=2, sort_keys=True))
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
            self._storage.put_json(
                self._idempotency_key(job.idempotency_key),
                json.dumps(
                    {
                        "version": "render-state-idempotency-v1",
                        "idempotencyKeyHash": self._hash(job.idempotency_key),
                        "editJobId": job.edit_job_id,
                        "renderJobId": job.render_job_id,
                        "revisionId": job.revision_id,
                        "updatedAt": job.updated_at.isoformat(),
                    },
                    indent=2,
                    sort_keys=True,
                ),
            )
        self._append_install_index(job)

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

    @staticmethod
    def _job_key(render_job_id: str) -> str:
        return f"render_state/render_jobs/{render_job_id}.json"

    @staticmethod
    def _latest_edit_key(edit_job_id: str) -> str:
        return f"render_state/edit_jobs/{edit_job_id}/latest.json"

    @classmethod
    def _idempotency_key(cls, idempotency_key: str) -> str:
        return f"render_state/idempotency/{cls._hash(idempotency_key)}.json"

    @classmethod
    def _install_key(cls, install_id: str) -> str:
        return f"render_state/installs/{cls._hash(install_id)}.json"

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
