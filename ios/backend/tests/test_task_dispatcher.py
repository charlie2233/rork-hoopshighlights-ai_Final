from __future__ import annotations

import asyncio
from types import SimpleNamespace
import unittest

from app.task_dispatcher import CloudTasksDispatcher


class _FakeHttpMethod:
    POST = "POST"


class _FakeHttpRequest:
    def __init__(self, *, http_method: str, url: str, headers: dict[str, str]) -> None:
        self.http_method = http_method
        self.url = url
        self.headers = headers


class _FakeTask:
    def __init__(self, *, http_request: _FakeHttpRequest) -> None:
        self.http_request = http_request


class _FakeCloudTasksClient:
    created_tasks: list[dict[str, object]] = []

    def create_task(self, *, parent: str, task: _FakeTask) -> None:
        self.created_tasks.append({"parent": parent, "task": task})


class _FakeTasksModule:
    CloudTasksClient = _FakeCloudTasksClient
    HttpMethod = _FakeHttpMethod
    HttpRequest = _FakeHttpRequest
    Task = _FakeTask


class _Settings:
    cloud_run_base_url = "https://hoops-api.example.test"
    gcp_project_id = "project-123"
    gcp_region = "us-central1"
    cloud_tasks_queue = "analysis-jobs"
    internal_process_secret = "secret-123"

    @property
    def cloud_tasks_parent(self) -> str:
        return (
            f"projects/{self.gcp_project_id}/locations/"
            f"{self.gcp_region}/queues/{self.cloud_tasks_queue}"
        )


class _TestCloudTasksDispatcher(CloudTasksDispatcher):
    def _import_tasks_module(self):
        return _FakeTasksModule


class CloudTasksDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        _FakeCloudTasksClient.created_tasks = []

    def test_enqueues_analysis_and_post_upload_tasks(self) -> None:
        dispatcher = _TestCloudTasksDispatcher(_Settings())

        asyncio.run(dispatcher.enqueue_process(SimpleNamespace(job_id="job_123")))
        asyncio.run(dispatcher.enqueue_post_upload(SimpleNamespace(asset_id="asset_123")))

        self.assertEqual(len(_FakeCloudTasksClient.created_tasks), 2)
        analysis_task = _FakeCloudTasksClient.created_tasks[0]["task"]
        asset_task = _FakeCloudTasksClient.created_tasks[1]["task"]
        self.assertEqual(
            analysis_task.http_request.url,
            "https://hoops-api.example.test/v1/internal/process/job_123",
        )
        self.assertEqual(
            asset_task.http_request.url,
            "https://hoops-api.example.test/v1/internal/assets/asset_123/process",
        )
        self.assertEqual(
            asset_task.http_request.headers["X-Hoops-Internal-Secret"],
            "secret-123",
        )
        self.assertEqual(
            _FakeCloudTasksClient.created_tasks[1]["parent"],
            "projects/project-123/locations/us-central1/queues/analysis-jobs",
        )


if __name__ == "__main__":
    unittest.main()
