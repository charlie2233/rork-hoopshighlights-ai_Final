from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import CloudAnalysisResult, CloudDiagnostics


class UploadPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = Path(tempfile.mkdtemp(prefix="hoops-upload-pipeline-tests-"))

    def tearDown(self) -> None:
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _settings(self, **overrides) -> Settings:
        values = dict(
            service_name="hoops-ai-api",
            environment="local",
            host_base_url="http://127.0.0.1:8080",
            cloud_run_base_url="http://127.0.0.1:8080",
            upload_root=self._temp_dir,
            external_repo_root=self._temp_dir / "external",
            internal_process_secret=None,
            public_api_enabled=True,
            gcp_project_id=None,
            gcp_region="us-central1",
            gcs_bucket_name="bucket",
            firestore_jobs_collection="analysisJobs",
            firestore_usage_collection="usageCounters",
            cloud_tasks_queue="analysis-jobs",
            enable_local_upload_emulation=True,
            detection_provider="hybrid",
            post_ranking_provider="native",
            hoopcut_repo_path=None,
            hoopcut_python_bin=None,
            autohighlight_repo_path=None,
            autohighlight_python_bin=None,
            daily_quota=3,
            rolling_quota_hours=24,
            default_poll_after_seconds=1,
            job_ttl_seconds=3600,
            signed_upload_ttl_seconds=900,
            max_file_size_bytes=100 * 1024 * 1024,
            max_duration_seconds=1800.0,
            min_clip_duration_seconds=2.0,
            max_clip_duration_seconds=15.0,
            clip_padding_seconds=0.35,
            max_returned_clips=8,
            backend_model_version="cloud-v1",
            use_gemini_relabeling=False,
            upload_storage_provider="local",
            upload_multipart_part_size_bytes=4,
        )
        values.update(overrides)
        return Settings(**values)

    def _init_payload(self, **overrides) -> dict:
        payload = {
            "filename": "game.mp4",
            "contentType": "video/mp4",
            "fileSizeBytes": 8,
            "durationSeconds": 12.0,
            "installId": "install-123456",
            "appVersion": "1.0",
            "analysisVersion": "cloud-v1",
        }
        payload.update(overrides)
        return payload

    def test_upload_init_contract_returns_asset_and_single_upload_plan(self) -> None:
        client = TestClient(create_app(self._settings(upload_multipart_part_size_bytes=64)))

        response = client.post("/v1/uploads/init", json=self._init_payload(fileSizeBytes=8))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["assetId"].startswith("asset_"))
        self.assertTrue(payload["storageKey"].startswith(f"assets/{payload['assetId']}/source/"))
        self.assertEqual(payload["status"], "initialized")
        self.assertEqual(payload["uploadMode"], "single")
        self.assertEqual(payload["uploadMethod"], "PUT")
        self.assertIn(f"/v1/internal/assets/{payload['assetId']}/upload", payload["uploadUrl"])
        self.assertEqual(payload["uploadState"], "waiting_for_client_upload")
        self.assertIsNone(payload.get("multipart"))

    def test_multipart_completion_assembles_parts_and_marks_proxy_ready(self) -> None:
        client = TestClient(create_app(self._settings(upload_multipart_part_size_bytes=4)))

        init_response = client.post(
            "/v1/uploads/init",
            json=self._init_payload(fileSizeBytes=8, uploadPreference="multipart", partSizeBytes=4),
        )
        self.assertEqual(init_response.status_code, 200)
        init_payload = init_response.json()
        self.assertEqual(init_payload["uploadMode"], "multipart")
        self.assertEqual(init_payload["multipart"]["partCount"], 2)

        etags: list[dict] = []
        for part, body in zip(init_payload["multipart"]["parts"], [b"abcd", b"efgh"]):
            upload_response = client.put(part["uploadUrl"], content=body)
            self.assertEqual(upload_response.status_code, 204)
            etags.append({"partNumber": part["partNumber"], "etag": upload_response.headers["etag"]})

        complete_response = client.post(
            f"/v1/uploads/{init_payload['assetId']}/complete",
            json={
                "installId": "install-123456",
                "uploadId": init_payload["multipart"]["uploadId"],
                "parts": etags,
            },
        )

        self.assertEqual(complete_response.status_code, 200)
        completed = complete_response.json()
        self.assertEqual(completed["status"], "proxy_ready")
        self.assertTrue(completed["artifacts"]["proxyStorageKey"].endswith("/proxy/proxy.mp4"))
        self.assertEqual(len(completed["artifacts"]["thumbnailStorageKeys"]), 1)
        self.assertTrue(completed["artifacts"]["waveformStorageKey"].endswith("/metadata/waveform.json"))

        source_path = self._temp_dir / init_payload["storageKey"]
        self.assertEqual(source_path.read_bytes(), b"abcdefgh")

    def test_asset_status_transitions_from_initialized_to_uploaded_to_proxy_ready(self) -> None:
        client = TestClient(create_app(self._settings(upload_multipart_part_size_bytes=64)))
        init_response = client.post("/v1/uploads/init", json=self._init_payload(fileSizeBytes=8))
        asset = init_response.json()

        initial_status = client.get(f"/v1/assets/{asset['assetId']}", params={"installId": "install-123456"}).json()
        self.assertEqual(initial_status["status"], "initialized")

        upload_response = client.put(asset["uploadUrl"], content=b"video-bytes")
        self.assertEqual(upload_response.status_code, 204)
        uploaded_status = client.get(f"/v1/assets/{asset['assetId']}", params={"installId": "install-123456"}).json()
        self.assertEqual(uploaded_status["status"], "uploaded")
        self.assertEqual(uploaded_status["uploadedBytes"], len(b"video-bytes"))

        complete_response = client.post(
            f"/v1/uploads/{asset['assetId']}/complete",
            json={"installId": "install-123456"},
        )
        self.assertEqual(complete_response.status_code, 200)
        self.assertEqual(complete_response.json()["status"], "proxy_ready")

    def test_asset_analysis_job_waits_for_proxy_ready(self) -> None:
        client = TestClient(create_app(self._settings(upload_multipart_part_size_bytes=64)))
        init_response = client.post("/v1/uploads/init", json=self._init_payload(fileSizeBytes=8))
        asset = init_response.json()
        self.assertEqual(client.put(asset["uploadUrl"], content=b"video-bytes").status_code, 204)

        too_early = client.post(
            f"/v1/assets/{asset['assetId']}/analysis-jobs",
            json={"installId": "install-123456"},
        )
        self.assertEqual(too_early.status_code, 409)
        self.assertEqual(too_early.json()["errorCode"], "asset_not_ready")

        complete_response = client.post(
            f"/v1/uploads/{asset['assetId']}/complete",
            json={"installId": "install-123456"},
        )
        self.assertEqual(complete_response.status_code, 200)

        fake_result = CloudAnalysisResult(
            clipCount=0,
            clips=[],
            diagnostics=CloudDiagnostics(
                processingMs=1,
                backendModelVersion="test-cloud",
                usedVideoIntelligence=False,
                usedGeminiRelabeling=False,
                candidateSegments=0,
                finalSegments=0,
            ),
        )
        with patch("app.api.run_analysis", return_value=fake_result):
            start_response = client.post(
                f"/v1/assets/{asset['assetId']}/analysis-jobs",
                json={"installId": "install-123456"},
            )

        self.assertEqual(start_response.status_code, 200)
        started = start_response.json()
        self.assertEqual(started["assetId"], asset["assetId"])
        self.assertTrue(started["storageKey"].endswith("/proxy/proxy.mp4"))
        poll_response = client.get(f"/v1/analysis/jobs/{started['jobId']}")
        self.assertEqual(poll_response.status_code, 200)
        polled = poll_response.json()
        self.assertEqual(polled["assetId"], asset["assetId"])
        self.assertEqual(polled["storageKey"], started["storageKey"])


if __name__ == "__main__":
    unittest.main()
