from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import Settings
from app.editing import EditCandidateClip
from app.main import create_app
from app.models import CloudAnalysisResult, CloudDiagnostics


class AssetUploadFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = Path(tempfile.mkdtemp(prefix="hoops-asset-foundations-"))

    def tearDown(self) -> None:
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _settings(self) -> Settings:
        return Settings(
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
        )

    def _init_payload(self) -> dict:
        return {
            "filename": "game.mp4",
            "contentType": "video/mp4",
            "fileSizeBytes": 11,
            "durationSeconds": 12.0,
            "installId": "install-123456",
            "appVersion": "1.0",
            "analysisVersion": "cloud-v1",
        }

    def test_asset_upload_lifecycle_starts_analysis_job_without_legacy_upload_url(self) -> None:
        client = TestClient(create_app(self._settings()))

        init_response = client.post("/v1/uploads/init", json=self._init_payload())
        self.assertEqual(init_response.status_code, 200)
        asset = init_response.json()
        self.assertTrue(asset["assetId"].startswith("asset_"))
        self.assertTrue(asset["storageKey"].startswith(f"assets/{asset['assetId']}/source/"))
        self.assertEqual(asset["status"], "initialized")
        self.assertEqual(asset["uploadMode"], "single")
        self.assertIn(f"/v1/internal/assets/{asset['assetId']}/upload", asset["uploadUrl"])

        upload_response = client.put(asset["uploadUrl"], content=b"video-bytes")
        self.assertEqual(upload_response.status_code, 204)

        uploaded = client.get(f"/v1/assets/{asset['assetId']}", params={"installId": "install-123456"}).json()
        self.assertEqual(uploaded["status"], "uploaded")
        self.assertEqual(uploaded["uploadedBytes"], len(b"video-bytes"))

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
        completed = complete_response.json()
        self.assertEqual(completed["status"], "proxy_ready")
        self.assertTrue(completed["artifacts"]["proxyStorageKey"].endswith("/proxy/proxy.mp4"))

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

    def test_edit_candidate_accepts_five_review_feedback_tags(self) -> None:
        clip = EditCandidateClip(
            id="clip_1",
            start=1.0,
            end=4.0,
            eventCenter=2.5,
            label="made_shot",
            reviewFeedbackTags=["duplicate", "wrong_team", "bad_window", "wrong_label", "low_quality"],
        )

        self.assertEqual(
            clip.reviewFeedbackTags,
            ["duplicate", "wrong_team", "bad_window", "wrong_label", "low_quality"],
        )


if __name__ == "__main__":
    unittest.main()
