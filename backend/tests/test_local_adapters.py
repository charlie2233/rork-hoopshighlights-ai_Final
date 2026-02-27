from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from app.config import Settings
from app.job_store import InMemoryJobStore
from app.models import APIError, CreateCloudAnalysisJobRequest
from app.storage import LocalStorageProvider


class LocalAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._temp_dir = Path(tempfile.mkdtemp(prefix="hoops-backend-tests-"))
        self.settings = Settings(
            service_name="hoops-ai-api",
            environment="local",
            host_base_url="http://127.0.0.1:8080",
            cloud_run_base_url="http://127.0.0.1:8080",
            upload_root=self._temp_dir,
            internal_process_secret=None,
            gcp_project_id=None,
            gcp_region="us-central1",
            gcs_bucket_name="charlie-hoops-ai-analysis-temp",
            firestore_jobs_collection="analysisJobs",
            firestore_usage_collection="usageCounters",
            cloud_tasks_queue="analysis-jobs",
            enable_local_upload_emulation=True,
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
        self.store = InMemoryJobStore(self.settings)
        self.storage = LocalStorageProvider(self.settings)

    def tearDown(self) -> None:
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    async def test_reserve_quota_tracks_rolling_window(self) -> None:
        self.assertEqual(await self.store.reserve_quota("install-123456"), 2)
        self.assertEqual(await self.store.reserve_quota("install-123456"), 1)
        self.assertEqual(await self.store.reserve_quota("install-123456"), 0)

        with self.assertRaises(APIError) as context:
            await self.store.reserve_quota("install-123456")

        self.assertEqual(context.exception.error_code, "quota_exceeded")
        self.assertEqual(context.exception.status_code, 429)

    async def test_local_upload_round_trip_and_cleanup(self) -> None:
        request = CreateCloudAnalysisJobRequest(
            filename="session.mov",
            contentType="video/quicktime",
            fileSizeBytes=4,
            durationSeconds=12.0,
            installId="install-123456",
            appVersion="1.0",
            analysisVersion="cloud-v1",
        )
        upload = self.storage.prepare_upload("job123", request.filename, request.contentType)
        job = await self.store.create_job("job123", request, upload, quota_remaining_today=2)

        storage_path = self.storage.accept_local_upload(job, b"test")
        await self.store.mark_uploaded(job.job_id, storage_path)
        stored_job = await self.store.get_job(job.job_id)
        self.assertIsNotNone(stored_job)
        assert stored_job is not None

        self.assertTrue(await self.storage.object_exists(stored_job))
        source = await self.storage.materialize_source(stored_job)
        self.assertEqual(source.local_path.read_bytes(), b"test")

        self.storage.cleanup(stored_job)
        self.assertFalse(Path(storage_path).exists())


if __name__ == "__main__":
    unittest.main()
