from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.inference.app.api import create_app
from services.inference.app.config import InferenceSettings
from services.inference.app.models import InferenceJobResponse


class FakeService:
    async def run(self, request):
        request_id = request.requestId or "request-test"
        model_version = request.modelVersion or "videomae:test"
        return InferenceJobResponse(
            jobId=request.jobId,
            status="succeeded",
            requestId=request_id,
            modelVersion=model_version,
            confidence=0.91,
            resultConfidence=0.91,
        )


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = InferenceSettings(
            callback_secret="secret",
            ingress_secret="ingress-secret",
            r2_bucket_name="bucket",
            r2_endpoint_url="https://example.com",
            r2_access_key_id="key",
            r2_secret_access_key="secret",
        )

    def test_version_and_ready_endpoints(self) -> None:
        with patch("services.inference.app.api.build_service", return_value=FakeService()):
            client = TestClient(create_app(self.settings))

            version = client.get("/version")
            self.assertEqual(version.status_code, 200)
            self.assertEqual(version.json()["serviceName"], self.settings.service_name)

            ready = client.get("/readyz")
            self.assertEqual(ready.status_code, 200)
            self.assertEqual(ready.json()["status"], "ready")
            self.assertEqual(ready.json()["callback"], "configured")
            self.assertEqual(ready.json()["ingress"], "configured")
            self.assertEqual(ready.json()["r2"], "configured")

    def test_analyze_endpoint_accepts_source_object_key(self) -> None:
        with patch("services.inference.app.api.build_service", return_value=FakeService()):
            client = TestClient(create_app(self.settings))

            response = client.post(
                "/v1/analyze",
                headers={"x-hoops-inference-secret": "ingress-secret"},
                json={
                    "jobId": "job_123",
                    "requestId": "req_123",
                    "sourceObjectKey": "uploads/job_123/source.mp4",
                    "callbackUrl": "https://example.com/callback",
                    "modelVersion": "videomae:test",
                },
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["jobId"], "job_123")
            self.assertEqual(body["requestId"], "req_123")
            self.assertEqual(body["modelVersion"], "videomae:test")

    def test_analyze_endpoint_requires_a_source(self) -> None:
        with patch("services.inference.app.api.build_service", return_value=FakeService()):
            client = TestClient(create_app(self.settings))

            response = client.post(
                "/v1/analyze",
                headers={"x-hoops-inference-secret": "ingress-secret"},
                json={
                    "jobId": "job_123",
                    "requestId": "req_123",
                    "callbackUrl": "https://example.com/callback",
                    "modelVersion": "videomae:test",
                },
            )
            self.assertEqual(response.status_code, 422)

    def test_analyze_endpoint_rejects_missing_ingress_secret(self) -> None:
        with patch("services.inference.app.api.build_service", return_value=FakeService()):
            client = TestClient(create_app(self.settings))

            response = client.post(
                "/v1/analyze",
                json={
                    "jobId": "job_123",
                    "requestId": "req_123",
                    "sourceUrl": "https://example.com/source.mp4",
                    "callbackUrl": "https://example.com/callback",
                },
            )
            self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
