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

from app.editing import CreateEditJobRequest, TEMPLATE_PACK_REGISTRY, build_edit_job, get_plan_tier_policy, validate_template_registry  # noqa: E402
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

    def test_create_edit_job_and_fetch_plan(self) -> None:
        client = TestClient(create_app(self._settings()))
        edit_request = self._edit_request()

        create_response = client.post("/v1/edit-jobs", json=edit_request.model_dump())

        self.assertEqual(create_response.status_code, 200)
        create_payload = create_response.json()
        self.assertEqual(create_payload["status"], "plan_ready")
        self.assertEqual(create_payload["preset"], "personal_highlight")
        self.assertEqual(create_payload["clipCount"], 2)

        plan_response = client.get(
            f"/v1/edit-jobs/{create_payload['editJobId']}/plan",
            params={"installId": edit_request.installId},
        )
        self.assertEqual(plan_response.status_code, 200)
        plan_payload = plan_response.json()
        self.assertEqual(plan_payload["editJobId"], create_payload["editJobId"])
        self.assertEqual(plan_payload["plan"]["renderMode"], "cloud_ffmpeg")
        self.assertEqual(plan_payload["plan"]["templateId"], "personal_highlight_v1")
        self.assertEqual(plan_payload["plan"]["captionStyle"], "bold_hype")
        self.assertEqual(plan_payload["plan"]["aspectRatio"], "9:16")

    def test_template_registry_loads_and_validates(self) -> None:
        validation = validate_template_registry()

        self.assertEqual(set(validation.keys()), {"personal_highlight_v1", "full_game_highlight_v1", "coach_review_v1"})
        self.assertTrue(all(not errors for errors in validation.values()))
        self.assertEqual(TEMPLATE_PACK_REGISTRY["personal_highlight_v1"].watermarkProfile.assetId, "hoopclips_app_icon_v1")

    def test_plan_tier_policy_defaults_are_safe_without_statsig(self) -> None:
        free_policy = get_plan_tier_policy("free")
        pro_policy = get_plan_tier_policy("pro")
        internal_policy = get_plan_tier_policy("internal")
        dev_policy = get_plan_tier_policy("dev")

        self.assertEqual(free_policy.maxDailyRenders, 3)
        self.assertEqual(free_policy.maxRenderSeconds, 45)
        self.assertTrue(free_policy.watermarkRequired)
        self.assertTrue(free_policy.outroRequired)
        self.assertFalse(free_policy.premiumTemplatesAllowed)
        self.assertGreater(pro_policy.maxRenderSeconds, free_policy.maxRenderSeconds)
        self.assertTrue(internal_policy.premiumTemplatesAllowed)
        self.assertGreater(dev_policy.maxDailyRenders, internal_policy.maxDailyRenders)

    def test_revise_edit_job_returns_patch_and_revised_plan(self) -> None:
        client = TestClient(create_app(self._settings()))
        edit_request = self._edit_request()
        create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()

        revise_response = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revise",
            json={"installId": edit_request.installId, "command": "make_nba_style"},
        )

        self.assertEqual(revise_response.status_code, 200)
        revision_payload = revise_response.json()
        self.assertEqual(revision_payload["status"], "revision_ready")
        self.assertEqual(revision_payload["command"], "make_nba_style")
        self.assertEqual(revision_payload["patch"]["version"], "edit-plan-patch-v1")
        self.assertTrue(revision_payload["patch"]["operations"])
        self.assertEqual(revision_payload["revisedPlan"]["aspectRatio"], "16:9")
        self.assertEqual(revision_payload["revisedPlan"]["templateId"], "full_game_highlight_v1")
        self.assertEqual(revision_payload["revisedPlan"]["captionStyle"], "clean_scorebug")
        self.assertTrue(revision_payload["validationResult"]["valid"])

        revisions_response = client.get(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revisions",
            params={"installId": edit_request.installId},
        )
        self.assertEqual(revisions_response.status_code, 200)
        self.assertEqual(len(revisions_response.json()["revisions"]), 1)

    def test_revision_command_preserves_free_watermark_and_outro(self) -> None:
        client = TestClient(create_app(self._settings()))
        edit_request = self._edit_request()
        create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()

        revise_response = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revise",
            json={"installId": edit_request.installId, "command": "use_original_audio"},
        )

        self.assertEqual(revise_response.status_code, 200)
        plan = revise_response.json()["revisedPlan"]
        self.assertEqual(plan["audio"]["musicTrackId"], "none")
        self.assertEqual(plan["audio"]["musicVolume"], 0.0)
        self.assertTrue(plan["watermark"]["enabled"])
        self.assertTrue(plan["outro"]["enabled"])

    def test_revision_limit_enforced_for_free_plan(self) -> None:
        client = TestClient(create_app(self._settings()))
        edit_request = self._edit_request()
        create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()

        for _ in range(3):
            response = client.post(
                f"/v1/edit-jobs/{create_payload['editJobId']}/revise",
                json={"installId": edit_request.installId, "command": "make_more_hype"},
            )
            self.assertEqual(response.status_code, 200)

        rejected = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revise",
            json={"installId": edit_request.installId, "command": "make_more_hype"},
        )

        self.assertEqual(rejected.status_code, 429)
        self.assertEqual(rejected.json()["errorCode"], "revision_limit")

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
        self.assertEqual(render_payload["planTier"], "free")
        self.assertEqual(render_payload["policy"]["maxDailyRenders"], 3)
        self.assertGreater(render_payload["outputBytes"], 0)
        self.assertEqual(render_payload["retentionMetadata"]["retentionClass"], "free_final_render")
        output_path = self._temp_dir / render_payload["outputObjectKey"]
        log_path = self._temp_dir / render_payload["renderLogObjectKey"]
        metadata_path = output_path.with_suffix(output_path.suffix + ".metadata.json")
        self.assertTrue(output_path.exists())
        self.assertTrue(log_path.exists())
        self.assertTrue(metadata_path.exists())
        render_log = json.loads(log_path.read_text(encoding="utf-8"))
        self.assertEqual(render_log["status"], "rendered")
        self.assertEqual(render_log["planTier"], "free")
        self.assertEqual(render_log["policy"]["maxRenderSeconds"], 45)
        self.assertEqual(render_log["retentionMetadata"]["retentionClass"], "free_final_render")
        self.assertEqual(render_log["ffmpeg"]["templateId"], "personal_highlight_v1")
        self.assertEqual(render_log["ffmpeg"]["captionStyle"], "bold_hype")
        self.assertEqual(render_log["ffmpeg"]["templateSignature"]["templateVersion"], "v1")
        self.assertEqual(render_log["ffmpeg"]["templateSignature"]["effectProfile"], "hype_effects")
        self.assertEqual(render_log["ffmpeg"]["templateSignature"]["audioProfile"], "hype")
        self.assertEqual(render_log["ffmpeg"]["templateSignature"]["outroProfile"], "free_social_outro")

        download_response = client.get(f"/v1/render-jobs/{render_payload['renderJobId']}/download-url", params={"installId": "install-123"})
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.json()["contentType"], "video/mp4")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_render_existing_edit_job_without_resending_plan(self) -> None:
        client = TestClient(create_app(self._settings()))
        edit_request = self._edit_request()
        create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()

        render_response = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/render",
            json={"installId": edit_request.installId},
        )

        self.assertEqual(render_response.status_code, 200)
        render_job_id = render_response.json()["renderJobId"]
        status_response = client.get(f"/v1/render-jobs/{render_job_id}", params={"installId": edit_request.installId})
        self.assertEqual(status_response.status_code, 200)
        render_payload = status_response.json()
        self.assertEqual(render_payload["status"], "rendered")
        self.assertEqual(render_payload["aspectRatio"], "9:16")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_render_revision_produces_latest_download_url(self) -> None:
        client = TestClient(create_app(self._settings()))
        edit_request = self._edit_request()
        create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()
        revision_payload = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revise",
            json={"installId": edit_request.installId, "command": "switch_format_widescreen"},
        ).json()

        render_response = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revisions/{revision_payload['revisionId']}/render",
            json={"installId": edit_request.installId},
        )

        self.assertEqual(render_response.status_code, 200)
        render_job_id = render_response.json()["renderJobId"]
        status_response = client.get(f"/v1/render-jobs/{render_job_id}", params={"installId": edit_request.installId})
        self.assertEqual(status_response.status_code, 200)
        render_payload = status_response.json()
        self.assertEqual(render_payload["status"], "rendered")
        self.assertEqual(render_payload["aspectRatio"], "16:9")
        download_response = client.get(
            f"/v1/edit-jobs/{create_payload['editJobId']}/download-url",
            params={"installId": edit_request.installId},
        )
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.json()["renderJobId"], render_payload["renderJobId"])

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

    def test_render_over_free_policy_duration_rejected_before_render(self) -> None:
        client = TestClient(create_app(self._settings()))
        payload = self._render_payload(self._edit_request())
        payload["editPlan"]["targetDurationSeconds"] = 120

        render_response = client.post("/v1/render-jobs", json=payload)

        self.assertEqual(render_response.status_code, 200)
        render_payload = render_response.json()
        self.assertEqual(render_payload["status"], "failed")
        self.assertEqual(render_payload["failureReason"], "invalid_edit_plan")
        self.assertTrue(any(error["code"] == "render_duration_limit" for error in render_payload["validationErrors"]))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_duplicate_render_request_is_idempotent(self) -> None:
        client = TestClient(create_app(self._settings()))
        payload = self._render_payload(self._edit_request())
        payload["idempotencyKey"] = "idem-render-001"

        first_response = client.post("/v1/render-jobs", json=payload)
        second_response = client.post("/v1/render-jobs", json=payload)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(first_response.json()["renderJobId"], second_response.json()["renderJobId"])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_daily_render_limit_uses_feature_flag_default_override(self) -> None:
        os.environ["HOOPS_AI_EDIT_MAX_DAILY_RENDERS"] = "1"
        try:
            client = TestClient(create_app(self._settings()))
            first_payload = self._render_payload(self._edit_request())
            second_request = self._edit_request(source_key=first_payload["sourceObjectKey"])
            second_request = second_request.model_copy(update={"videoId": "video_render_456", "analysisJobId": "analysis_render_456"})
            second_payload = self._render_payload(second_request)
            second_payload["editJobId"] = "edit_service_test_2"
            second_payload["editPlan"]["editJobId"] = "edit_service_test_2"

            first_response = client.post("/v1/render-jobs", json=first_payload)
            second_response = client.post("/v1/render-jobs", json=second_payload)

            self.assertEqual(first_response.status_code, 200)
            self.assertEqual(second_response.status_code, 429)
            self.assertEqual(second_response.json()["errorCode"], "daily_render_limit")
        finally:
            os.environ.pop("HOOPS_AI_EDIT_MAX_DAILY_RENDERS", None)

    def test_download_url_unavailable_before_render_job_exists(self) -> None:
        client = TestClient(create_app(self._settings()))

        response = client.get("/v1/render-jobs/render_missing/download-url", params={"installId": "install-123"})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["errorCode"], "render_job_not_found")


if __name__ == "__main__":
    unittest.main()
