from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit
import json
import shutil
import subprocess
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import Settings
from app.editing import CreateEditJobRequest, EditPlan, build_edit_job
from app.main import create_app
from app.rendering import validate_render_request


def _clip(clip_id: str, start: float, label: str, score: float) -> dict:
    return {
        "id": clip_id,
        "start": start,
        "end": start + 5.0,
        "eventCenter": start + 2.4,
        "label": label,
        "confidence": score,
        "excitement": score,
        "watchability": score,
        "motionScore": score,
        "audioPeak": score / 2.0,
        "combinedScore": score,
    }


class RenderJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = Path(tempfile.mkdtemp(prefix="hoops-render-tests-"))

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
            internal_process_secret="internal-secret",
            public_api_enabled=True,
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
        values.update(overrides)
        return Settings(**values)

    def _source_key(self) -> str:
        source_key = "sources/synthetic_game.mp4"
        source_path = self._temp_dir / source_key
        source_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=640x360:rate=30:duration=18",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=18",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source_path),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return source_key

    def _request_payload(self, **overrides) -> dict:
        payload = {
            "videoId": "video_render_123",
            "analysisJobId": "analysis_render_123",
            "installId": "install-123",
            "sourceObjectKey": self._source_key(),
            "preset": "personal_highlight",
            "targetDurationSeconds": 15,
            "planTier": "free",
            "clips": [
                _clip("c1", 0.0, "Fast Break", 0.95),
                _clip("c2", 8.0, "Made Shot", 0.9),
            ],
        }
        payload.update(overrides)
        return payload

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_render_two_clip_personal_highlight_and_download_url(self) -> None:
        client = TestClient(create_app(self._settings()))
        create_response = client.post("/v1/edit-jobs", json=self._request_payload(aspectRatio="9:16"))
        self.assertEqual(create_response.status_code, 200)
        edit_job_id = create_response.json()["editJobId"]

        render_response = client.post(f"/v1/edit-jobs/{edit_job_id}/render", json={"installId": "install-123"})
        self.assertEqual(render_response.status_code, 200)

        status_response = client.get(f"/v1/edit-jobs/{edit_job_id}/render-status", params={"installId": "install-123"})
        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.json()
        self.assertEqual(status_payload["status"], "rendered")
        self.assertEqual(status_payload["aspectRatio"], "9:16")
        self.assertGreater(status_payload["durationSeconds"], 0)

        output_path = self._temp_dir / status_payload["outputObjectKey"]
        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 0)
        self.assertEqual(self._probe_dimensions(output_path), (720, 1280))
        media_payload = self._probe_media(output_path)
        self.assertTrue(any(stream["codec_type"] == "video" and stream["codec_name"] == "h264" for stream in media_payload["streams"]))
        self.assertTrue(any(stream["codec_type"] == "audio" and stream["codec_name"] == "aac" for stream in media_payload["streams"]))

        log_path = self._temp_dir / status_payload["renderLogObjectKey"]
        self.assertTrue(log_path.exists())
        log_payload = json.loads(log_path.read_text(encoding="utf-8"))
        self.assertEqual(log_payload["status"], "rendered")
        self.assertEqual(log_payload["traceId"], status_payload["traceId"])
        self.assertEqual(log_payload["outputObjectKey"], status_payload["outputObjectKey"])
        self.assertEqual(log_payload["clipCount"], 2)
        self.assertEqual(log_payload["ffmpeg"]["rendererVersion"], "ffmpeg-renderer-v1")
        self.assertGreater(log_payload["ffmpeg"]["segmentCount"], log_payload["clipCount"])
        self.assertTrue(any("setpts=" in command for command in log_payload["ffmpeg"]["commands"]))
        self.assertTrue(any("atempo=" in command for command in log_payload["ffmpeg"]["commands"]))
        self.assertAlmostEqual(float(media_payload["format"]["duration"]), status_payload["durationSeconds"], delta=0.25)

        download_response = client.get(f"/v1/edit-jobs/{edit_job_id}/download-url", params={"installId": "install-123"})
        self.assertEqual(download_response.status_code, 200)
        download_payload = download_response.json()
        self.assertEqual(download_payload["contentType"], "video/mp4")
        rendered_file_response = client.get(urlsplit(download_payload["downloadUrl"]).path)
        self.assertEqual(rendered_file_response.status_code, 200)
        self.assertGreater(len(rendered_file_response.content), 0)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_render_full_game_widescreen(self) -> None:
        client = TestClient(create_app(self._settings()))
        create_response = client.post(
            "/v1/edit-jobs",
            json=self._request_payload(preset="full_game_highlight", targetDurationSeconds=60, aspectRatio="16:9"),
        )
        self.assertEqual(create_response.status_code, 200)
        edit_job_id = create_response.json()["editJobId"]

        render_response = client.post(f"/v1/edit-jobs/{edit_job_id}/render", json={"installId": "install-123"})
        self.assertEqual(render_response.status_code, 200)
        status_payload = client.get(f"/v1/edit-jobs/{edit_job_id}/render-status", params={"installId": "install-123"}).json()

        self.assertEqual(status_payload["status"], "rendered")
        self.assertEqual(self._probe_dimensions(self._temp_dir / status_payload["outputObjectKey"]), (1280, 720))

    def test_download_url_unavailable_before_render(self) -> None:
        client = TestClient(create_app(self._settings()))
        create_response = client.post("/v1/edit-jobs", json=self._request_payload(aspectRatio="9:16"))
        self.assertEqual(create_response.status_code, 200)
        edit_job_id = create_response.json()["editJobId"]

        download_response = client.get(f"/v1/edit-jobs/{edit_job_id}/download-url", params={"installId": "install-123"})

        self.assertEqual(download_response.status_code, 404)
        self.assertEqual(download_response.json()["errorCode"], "render_job_not_found")

    def test_render_request_without_source_fails_before_renderer(self) -> None:
        client = TestClient(create_app(self._settings()))
        payload = self._request_payload()
        payload.pop("sourceObjectKey")
        create_response = client.post("/v1/edit-jobs", json=payload)
        self.assertEqual(create_response.status_code, 200)
        edit_job_id = create_response.json()["editJobId"]

        render_response = client.post(f"/v1/edit-jobs/{edit_job_id}/render", json={"installId": "install-123"})

        self.assertEqual(render_response.status_code, 200)
        payload = render_response.json()
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["failureReason"], "invalid_edit_plan")
        self.assertTrue(any(error["code"] == "source_missing" for error in payload["validationErrors"]))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_render_failure_records_failure_reason_and_log(self) -> None:
        invalid_source_key = "sources/not_a_video.mp4"
        invalid_source_path = self._temp_dir / invalid_source_key
        invalid_source_path.parent.mkdir(parents=True, exist_ok=True)
        invalid_source_path.write_text("this is not a playable mp4", encoding="utf-8")
        client = TestClient(create_app(self._settings()))
        create_response = client.post(
            "/v1/edit-jobs",
            json=self._request_payload(sourceObjectKey=invalid_source_key, aspectRatio="9:16"),
        )
        self.assertEqual(create_response.status_code, 200)
        edit_job_id = create_response.json()["editJobId"]

        render_response = client.post(f"/v1/edit-jobs/{edit_job_id}/render", json={"installId": "install-123"})
        self.assertEqual(render_response.status_code, 200)
        status_payload = client.get(f"/v1/edit-jobs/{edit_job_id}/render-status", params={"installId": "install-123"}).json()

        self.assertEqual(status_payload["status"], "failed")
        self.assertEqual(status_payload["failureReason"], "ffmpeg_render_failed")
        log_path = self._temp_dir / status_payload["renderLogObjectKey"]
        self.assertTrue(log_path.exists())
        log_payload = json.loads(log_path.read_text(encoding="utf-8"))
        self.assertEqual(log_payload["status"], "failed")
        self.assertEqual(log_payload["failureReason"], "ffmpeg_render_failed")

    def test_render_validator_rejects_missing_free_watermark_and_bad_slow_motion(self) -> None:
        request = CreateEditJobRequest(**self._request_payload())
        job = build_edit_job(request, "edit_invalid_render")
        data = job.plan.model_dump()
        data["watermark"]["enabled"] = False
        data["clips"][0]["effects"].append(
            {
                "type": "slow_motion",
                "sourceStart": data["clips"][0]["sourceStart"],
                "sourceEnd": data["clips"][0]["sourceEnd"],
                "speed": 0.25,
            }
        )
        job.plan = EditPlan(**data)

        errors = validate_render_request(job, source_exists=True)

        self.assertTrue(any(error.code == "missing_free_watermark" for error in errors))
        self.assertTrue(any(error.code == "invalid_slow_motion_speed" for error in errors))

    def _probe_dimensions(self, path: Path) -> tuple[int, int]:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        stream = json.loads(result.stdout)["streams"][0]
        return int(stream["width"]), int(stream["height"])

    def _probe_media(self, path: Path) -> dict:
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], check=True, capture_output=True, text=True)
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,format_name:stream=codec_type,codec_name,width,height,pix_fmt",
            "-of",
            "json",
            str(path),
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return json.loads(result.stdout)


if __name__ == "__main__":
    unittest.main()
