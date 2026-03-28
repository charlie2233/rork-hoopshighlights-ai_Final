from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from services.inference.app.callback import CallbackClient
from services.inference.app.config import InferenceSettings
from services.inference.app.models import InferenceJobRequest
from services.inference.app.pipeline import InferenceService, _resolve_trace_fields


class PipelineSourceResolutionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.settings = InferenceSettings()
        self.service = InferenceService(
            settings=self.settings,
            candidate_proposer=Mock(),
            primary_recognizer=Mock(),
            comparison_recognizer=None,
            event_inferencer=Mock(),
            reranker=Mock(),
            artifact_writer=Mock(),
            callback_client=CallbackClient(timeout_seconds=1.0),
            r2_downloader=None,
        )

    async def test_resolve_source_falls_back_to_source_url_when_r2_is_not_configured(self) -> None:
        request = InferenceJobRequest(
            jobId="job_123",
            sourceObjectKey="uploads/job_123/source.mp4",
            sourceUrl="https://example.com/source.mp4",
            callbackUrl="https://example.com/internal/inference/callback",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "source.mp4"
            self.service._download_source = AsyncMock(return_value=destination)

            resolved = await self.service._resolve_source(request, destination)

            self.assertEqual(resolved, destination)
            self.service._download_source.assert_awaited_once_with("https://example.com/source.mp4", destination)

    async def test_resolve_source_uses_r2_downloader_when_available(self) -> None:
        request = InferenceJobRequest(
            jobId="job_123",
            sourceObjectKey="uploads/job_123/source.mp4",
            sourceUrl="https://example.com/source.mp4",
            callbackUrl="https://example.com/internal/inference/callback",
        )
        downloader = Mock()
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "source.mp4"
            downloader.download.return_value = destination
            self.service.r2_downloader = downloader
            self.service._download_source = AsyncMock(return_value=destination)

            resolved = await self.service._resolve_source(request, destination)

            self.assertEqual(resolved, destination)
            downloader.download.assert_called_once_with("uploads/job_123/source.mp4", destination)
            self.service._download_source.assert_not_awaited()


class PipelineTraceResolutionTests(unittest.TestCase):
    def test_resolve_trace_fields_prefers_distinct_upload_trace_id(self) -> None:
        request = InferenceJobRequest(
            jobId="job_123",
            traceId="trace-123",
            uploadTraceId="upload-456",
            sourceUrl="https://example.com/source.mp4",
            callbackUrl="https://example.com/internal/inference/callback",
        )

        trace_id, upload_trace_id = _resolve_trace_fields(request, "request-789")

        self.assertEqual(trace_id, "trace-123")
        self.assertEqual(upload_trace_id, "upload-456")

    def test_resolve_trace_fields_falls_back_to_trace_id_then_request_id(self) -> None:
        request_with_trace = InferenceJobRequest(
            jobId="job_123",
            traceId="trace-123",
            sourceUrl="https://example.com/source.mp4",
            callbackUrl="https://example.com/internal/inference/callback",
        )
        self.assertEqual(_resolve_trace_fields(request_with_trace, "request-789"), ("trace-123", "trace-123"))

        request_without_trace = InferenceJobRequest(
            jobId="job_123",
            sourceUrl="https://example.com/source.mp4",
            callbackUrl="https://example.com/internal/inference/callback",
        )
        self.assertEqual(_resolve_trace_fields(request_without_trace, "request-789"), ("request-789", "request-789"))


if __name__ == "__main__":
    unittest.main()
