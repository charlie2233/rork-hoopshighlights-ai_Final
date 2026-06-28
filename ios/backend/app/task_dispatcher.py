from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Protocol

from .config import Settings
from .models import StoredAsset, StoredJob


class TaskDispatcher(Protocol):
    async def enqueue_process(self, job: StoredJob) -> None:
        ...

    async def enqueue_post_upload(self, asset: StoredAsset) -> None:
        ...


class InlineTaskDispatcher:
    def __init__(
        self,
        process_callback: Callable[[str], Awaitable[object]],
        post_upload_callback: Callable[[str], Awaitable[object]],
    ) -> None:
        self._process_callback = process_callback
        self._post_upload_callback = post_upload_callback

    async def enqueue_process(self, job: StoredJob) -> None:
        await self._process_callback(job.job_id)

    async def enqueue_post_upload(self, asset: StoredAsset) -> None:
        await self._post_upload_callback(asset.asset_id)


class CloudTasksDispatcher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        tasks_module = self._import_tasks_module()
        self._tasks_module = tasks_module
        self._client = tasks_module.CloudTasksClient()

    async def enqueue_process(self, job: StoredJob) -> None:
        await asyncio.to_thread(self._enqueue_path_sync, f"/v1/internal/process/{job.job_id}")

    async def enqueue_post_upload(self, asset: StoredAsset) -> None:
        await asyncio.to_thread(self._enqueue_path_sync, f"/v1/internal/assets/{asset.asset_id}/process")

    def _enqueue_path_sync(self, path: str) -> None:
        parent = self._settings.cloud_tasks_parent
        if not parent:
            raise RuntimeError("HOOPS_GCP_PROJECT_ID must be configured for Cloud Tasks dispatch.")

        process_url = f"{self._settings.cloud_run_base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self._settings.internal_process_secret:
            headers["X-Hoops-Internal-Secret"] = self._settings.internal_process_secret

        task = self._tasks_module.Task(
            http_request=self._tasks_module.HttpRequest(
                http_method=self._tasks_module.HttpMethod.POST,
                url=process_url,
                headers=headers,
            )
        )
        self._client.create_task(parent=parent, task=task)

    def _import_tasks_module(self):
        try:
            from google.cloud import tasks_v2
        except ImportError as error:
            raise RuntimeError(
                "google-cloud-tasks is required for staging/production backend mode. "
                "Install backend requirements before starting the managed runtime."
            ) from error
        return tasks_v2
