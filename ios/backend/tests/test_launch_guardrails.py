from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class LaunchGuardrailTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = Path(tempfile.mkdtemp(prefix="hoops-backend-guardrails-"))

    def tearDown(self) -> None:
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _managed_settings(self, **overrides) -> Settings:
        values = dict(
            service_name="hoops-ai-api",
            environment="local",
            host_base_url="http://127.0.0.1:8080",
            cloud_run_base_url="http://127.0.0.1:8080",
            upload_root=self._temp_dir,
            external_repo_root=self._temp_dir / "external",
            internal_process_secret="internal-secret",
            public_api_enabled=False,
            gcp_project_id="project-id",
            gcp_region="us-central1",
            gcs_bucket_name="bucket",
            firestore_jobs_collection="analysisJobs",
            firestore_usage_collection="usageCounters",
            cloud_tasks_queue="analysis-jobs",
            enable_local_upload_emulation=False,
            detection_provider="hybrid",
            post_ranking_provider="native",
            hoopcut_repo_path=None,
            hoopcut_python_bin=None,
            autohighlight_repo_path=None,
            autohighlight_python_bin=None,
            daily_quota=3,
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
        values.update(overrides)
        return Settings(**values)

    def test_managed_mode_requires_internal_secret(self) -> None:
        settings = self._managed_settings(environment="staging", internal_process_secret=None)
        with self.assertRaises(ValueError):
            create_app(settings)

    def test_public_analysis_routes_are_disabled_when_public_api_is_off(self) -> None:
        app = create_app(self._managed_settings(public_api_enabled=False))
        client = TestClient(app)

        response = client.post(
            "/v1/analysis/jobs",
            json={
                "filename": "game.mov",
                "contentType": "video/quicktime",
                "fileSizeBytes": 1024,
                "durationSeconds": 12.0,
                "installId": "install-123",
                "appVersion": "1.0",
                "analysisVersion": "cloud-v1",
            },
        )

        self.assertEqual(response.status_code, 404)

    def test_readyz_reports_ffmpeg_and_render_storage_without_secrets(self) -> None:
        app = create_app(self._managed_settings(public_api_enabled=True))
        client = TestClient(app)

        response = client.get("/readyz")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(payload["status"], {"ok", "degraded"})
        self.assertEqual(payload["service"], "hoops-ai-api")
        self.assertIn("ffmpegAvailable", payload["ffmpeg"])
        self.assertIn("ffprobeAvailable", payload["ffmpeg"])
        self.assertIn("drawtextAvailable", payload["ffmpeg"])
        self.assertEqual(payload["renderStorage"]["provider"], "local")
        self.assertTrue(payload["renderStorage"]["providerReady"])
        self.assertTrue(payload["renderStorage"]["uploadRootWritable"])
        self.assertNotIn("secret", repr(payload).lower())


if __name__ == "__main__":
    unittest.main()
