from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

import app.api as api_module
from app.config import Settings
from app.main import create_app
from app.models import CloudAnalysisResult, CloudClip, CloudDiagnostics


class APIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = Path(tempfile.mkdtemp(prefix="hoops-api-contract-"))
        self.settings = Settings(
            service_name="hoops-ai-api",
            environment="local",
            host_base_url="http://127.0.0.1:8080",
            cloud_run_base_url="http://127.0.0.1:8080",
            upload_root=self._temp_dir,
            external_repo_root=self._temp_dir / "external",
            internal_process_secret="secret123",
            gcp_project_id=None,
            gcp_region="us-central1",
            gcs_bucket_name="charlie-hoops-ai-analysis-temp",
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
            daily_quota=5,
            rolling_quota_hours=24,
            default_poll_after_seconds=2,
            job_ttl_seconds=3600,
            signed_upload_ttl_seconds=900,
            max_file_size_bytes=500 * 1024 * 1024,
            max_duration_seconds=1800.0,
            min_clip_duration_seconds=2.0,
            max_clip_duration_seconds=15.0,
            clip_padding_seconds=0.35,
            max_returned_clips=8,
            backend_model_version="cloud-v1",
            use_gemini_relabeling=False,
        )
        self._original_run_analysis = api_module.run_analysis
        api_module.run_analysis = self._fake_run_analysis
        self.client = TestClient(create_app(self.settings))

    def tearDown(self) -> None:
        api_module.run_analysis = self._original_run_analysis
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _fake_run_analysis(self, job, settings, source_path):
        _ = job, settings, source_path
        clip = CloudClip(
            startTime=1.0,
            endTime=4.0,
            confidence=0.88,
            label="Three Pointer",
            action="Three Pointer",
            audioScore=0.71,
            visualScore=0.66,
            motionScore=0.74,
            combinedScore=0.82,
            detectionMethod="cloud",
            shouldAutoKeep=True,
            shouldEnableSlowMotion=False,
            eventType="basketball_highlight",
            shotType="three_pointer",
            makeMiss="make",
            rankScore=0.82,
        )
        diagnostics = CloudDiagnostics(
            processingMs=1250,
            backendModelVersion="cloud-v1+videomae",
            modelVersion="cloud-v1+videomae",
            usedVideoIntelligence=False,
            usedGeminiRelabeling=False,
            candidateSegments=3,
            finalSegments=1,
            failureReason=None,
        )
        return CloudAnalysisResult(
            clipCount=1,
            clips=[clip],
            diagnostics=diagnostics,
            resultConfidence=0.88,
            modelVersion="cloud-v1+videomae",
            failureReason=None,
        )

    def test_create_upload_start_poll_delete_contract_is_additive(self) -> None:
        create_response = self.client.post(
            "/v1/analysis/jobs",
            json={
                "filename": "session.mov",
                "contentType": "video/quicktime",
                "fileSizeBytes": 16,
                "durationSeconds": 12.0,
                "installId": "install-123456",
                "appVersion": "1.0.0",
                "analysisVersion": "cloud-v1",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        create_payload = create_response.json()
        self.assertIn("requestId", create_payload)
        self.assertIsNone(create_payload["modelVersion"])
        self.assertIsNone(create_payload["failureReason"])

        job_id = create_payload["jobId"]
        upload_response = self.client.put(f"/v1/internal/uploads/{job_id}", content=b"video-bytes")
        self.assertEqual(upload_response.status_code, 204)
        self.assertIn("x-request-id", {key.lower() for key in upload_response.headers.keys()})

        start_response = self.client.post(
            f"/v1/analysis/jobs/{job_id}/start",
            json={"installId": "install-123456"},
        )
        self.assertEqual(start_response.status_code, 200)
        start_payload = start_response.json()
        self.assertIn("requestId", start_payload)
        self.assertEqual(start_payload["status"], "queued")

        process_response = self.client.post(
            f"/v1/internal/process/{job_id}",
            headers={"X-Hoops-Internal-Secret": "secret123"},
        )
        self.assertEqual(process_response.status_code, 200)
        process_payload = process_response.json()
        self.assertEqual(process_payload["modelVersion"], "cloud-v1+videomae")
        self.assertIsNone(process_payload["failureReason"])

        job_response = self.client.get(f"/v1/analysis/jobs/{job_id}")
        self.assertEqual(job_response.status_code, 200)
        job_payload = job_response.json()
        self.assertIn("requestId", job_payload)
        self.assertEqual(job_payload["modelVersion"], "cloud-v1+videomae")
        self.assertIsNone(job_payload["failureReason"])
        self.assertEqual(job_payload["results"]["resultConfidence"], 0.88)
        self.assertEqual(job_payload["results"]["modelVersion"], "cloud-v1+videomae")
        self.assertEqual(job_payload["results"]["clips"][0]["shotType"], "three_pointer")
        self.assertEqual(job_payload["results"]["clips"][0]["makeMiss"], "make")

        delete_response = self.client.delete(f"/v1/analysis/jobs/{job_id}")
        self.assertEqual(delete_response.status_code, 204)
        self.assertIn("x-request-id", {key.lower() for key in delete_response.headers.keys()})


if __name__ == "__main__":
    unittest.main()
