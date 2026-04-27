from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "services" / "editing"))
sys.path.insert(0, str(REPO_ROOT / "ios" / "backend"))

from app.editing import CreateEditJobRequest, build_edit_job  # noqa: E402
from editing_app.config import EditingSettings  # noqa: E402
from editing_app.main import create_app  # noqa: E402


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


class EditingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = Path(tempfile.mkdtemp(prefix="hoopclips-editing-tests-"))

    def tearDown(self) -> None:
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _settings(self, **overrides) -> EditingSettings:
        values = dict(
            service_name="hoopclips-editing",
            environment="local",
            host_base_url="http://127.0.0.1:8090",
            upload_root=self._temp_dir,
            shared_secret=None,
            render_storage_provider="local",
            render_download_ttl_seconds=900,
            backend_model_version="editing-cloud-v1",
            git_sha="test",
        )
        values.update(overrides)
        return EditingSettings(**values)

    def _source_key(self) -> str:
        source_key = "sources/synthetic_game.mp4"
        source_path = self._temp_dir / source_key
        source_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
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
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return source_key

    def _edit_request(self, source_key: str | None = None) -> CreateEditJobRequest:
        return CreateEditJobRequest(
            videoId="video_render_123",
            analysisJobId="analysis_render_123",
            installId="install-123",
            sourceObjectKey=source_key or self._source_key(),
            preset="personal_highlight",
            targetDurationSeconds=15,
            aspectRatio="9:16",
            planTier="free",
            clips=[_clip("c1", 0.0, "Fast Break", 0.95), _clip("c2", 8.0, "Made Shot", 0.9)],
        )

    def _render_payload(self, edit_request: CreateEditJobRequest) -> dict:
        edit_job = build_edit_job(edit_request, "edit_service_test")
        self.assertFalse(edit_job.validation_errors)
        return {
            "editJobId": edit_job.edit_job_id,
            "installId": edit_request.installId,
            "sourceObjectKey": edit_request.sourceObjectKey,
            "planTier": edit_request.planTier,
            "editPlan": edit_job.plan.model_dump(),
            "sourceClips": [clip.model_dump() for clip in edit_request.clips],
        }

    def test_readyz_degrades_when_r2_env_is_missing(self) -> None:
        client = TestClient(create_app(self._settings(environment="staging", shared_secret="secret", render_storage_provider="r2")))

        response = client.get("/readyz")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["renderStorage"]["providerReady"])
        self.assertEqual(payload["renderStorage"]["provider"], "r2")

    def test_render_requires_secret_outside_local(self) -> None:
        client = TestClient(create_app(self._settings(environment="staging", shared_secret="secret", render_storage_provider="r2")))

        response = client.post("/v1/render-jobs", json=self._render_payload(self._edit_request()))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["errorCode"], "invalid_editing_secret")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_render_job_writes_output_log_and_download_url(self) -> None:
        client = TestClient(create_app(self._settings()))
        payload = self._render_payload(self._edit_request())

        render_response = client.post("/v1/render-jobs", json=payload)

        self.assertEqual(render_response.status_code, 200)
        render_job_id = render_response.json()["renderJobId"]
        status_response = client.get(f"/v1/render-jobs/{render_job_id}", params={"installId": "install-123"})
        self.assertEqual(status_response.status_code, 200)
        render_payload = status_response.json()
        self.assertEqual(render_payload["status"], "rendered")
        self.assertEqual(render_payload["aspectRatio"], "9:16")
        output_path = self._temp_dir / render_payload["outputObjectKey"]
        log_path = self._temp_dir / render_payload["renderLogObjectKey"]
        self.assertTrue(output_path.exists())
        self.assertTrue(log_path.exists())
        self.assertEqual(json.loads(log_path.read_text(encoding="utf-8"))["status"], "rendered")

        download_response = client.get(f"/v1/render-jobs/{render_payload['renderJobId']}/download-url", params={"installId": "install-123"})
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.json()["contentType"], "video/mp4")

    def test_invalid_plan_rejected_before_render(self) -> None:
        client = TestClient(create_app(self._settings()))
        payload = self._render_payload(self._edit_request())
        payload["editPlan"]["watermark"]["enabled"] = False

        render_response = client.post("/v1/render-jobs", json=payload)

        self.assertEqual(render_response.status_code, 200)
        render_payload = render_response.json()
        self.assertEqual(render_payload["status"], "failed")
        self.assertEqual(render_payload["failureReason"], "invalid_edit_plan")
        self.assertTrue(any(error["code"] == "missing_free_watermark" for error in render_payload["validationErrors"]))

    def test_download_url_unavailable_before_render_job_exists(self) -> None:
        client = TestClient(create_app(self._settings()))

        response = client.get("/v1/render-jobs/render_missing/download-url", params={"installId": "install-123"})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["errorCode"], "render_job_not_found")


if __name__ == "__main__":
    unittest.main()
