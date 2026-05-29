from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Protocol

from .config import Settings
from .models import StoredJob


class TaskDispatcher(Protocol):
    async def enqueue_process(self, job: StoredJob) -> None:
        ...


class InlineTaskDispatcher:
    def __init__(self, process_callback: Callable[[str], Awaitable[None]]) -> None:
        self._process_callback = process_callback

    async def enqueue_process(self, job: StoredJob) -> None:
        task = asyncio.create_task(self._process_callback(job.job_id))
        task.add_done_callback(self._consume_background_exception)

    def _consume_background_exception(self, task: "asyncio.Task[None]") -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            pass


class CloudTasksDispatcher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        tasks_module = self._import_tasks_module()
        self._tasks_module = tasks_module
        self._client = tasks_module.CloudTasksClient()

    async def enqueue_process(self, job: StoredJob) -> None:
        await asyncio.to_thread(self._enqueue_process_sync, job)

    def _enqueue_process_sync(self, job: StoredJob) -> None:
        parent = self._settings.cloud_tasks_parent
        if not parent:
            raise RuntimeError("HOOPS_GCP_PROJECT_ID must be configured for Cloud Tasks dispatch.")

        process_url = "{base}/v1/internal/process/{job_id}".format(
            base=self._settings.cloud_run_base_url,
            job_id=job.job_id,
        )
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
