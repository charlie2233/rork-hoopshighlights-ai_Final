from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import Settings
from app.editing import (
    CreateEditJobRequest,
    EditPlan,
    build_edit_job,
    build_edit_plan,
    remove_duplicate_moments,
    repair_edit_plan,
    validate_edit_plan,
)
from app.main import create_app


def _clip(
    clip_id: str,
    start: float,
    label: str,
    score: float,
    duplicate_group: str | None = None,
) -> dict:
    return {
        "id": clip_id,
        "start": start,
        "end": start + 7.0,
        "eventCenter": start + 3.4,
        "label": label,
        "confidence": score,
        "excitement": score,
        "watchability": score,
        "motionScore": score,
        "audioPeak": score / 2.0,
        "combinedScore": score,
        "duplicateGroup": duplicate_group,
    }


def _request_payload(**overrides) -> dict:
    payload = {
        "videoId": "video_123",
        "analysisJobId": "analysis_123",
        "installId": "install-123",
        "preset": "personal_highlight",
        "targetDurationSeconds": 30,
        "planTier": "free",
        "clips": [
            _clip("c1", 0.0, "Fast Break", 0.95, "g1"),
            _clip("c2", 1.0, "Fast Break", 0.72, "g1"),
            _clip("c3", 12.0, "Dunk", 0.9),
            _clip("c4", 24.0, "Made Shot", 0.86),
            _clip("c5", 36.0, "Defense", 0.8),
        ],
    }
    payload.update(overrides)
    return payload


class EditPlanAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = Path(tempfile.mkdtemp(prefix="hoops-edit-agent-"))

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

    def test_personal_highlight_plan_has_free_watermark_and_outro(self) -> None:
        request = CreateEditJobRequest(**_request_payload())

        job = build_edit_job(request, "edit_test")

        self.assertEqual(job.status, "plan_ready")
        self.assertEqual(job.plan.renderMode, "cloud_ffmpeg")
        self.assertTrue(job.plan.watermark.enabled)
        self.assertTrue(job.plan.outro.enabled)
        self.assertEqual(job.plan.aspectRatio, "9:16")
        self.assertEqual(job.validation_errors, [])

    def test_duplicate_groups_keep_only_best_clip(self) -> None:
        request = CreateEditJobRequest(**_request_payload())

        clips = remove_duplicate_moments(request.clips)

        grouped = [clip for clip in clips if clip.duplicateGroup == "g1"]
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0].id, "c1")

    def test_full_game_highlight_uses_widescreen_and_chronological_selection(self) -> None:
        request = CreateEditJobRequest(**_request_payload(preset="full_game_highlight", targetDurationSeconds=60))

        plan = build_edit_plan(request, "edit_full_game")

        self.assertEqual(plan.aspectRatio, "16:9")
        starts = [clip.sourceStart for clip in plan.clips]
        self.assertEqual(starts, sorted(starts))

    def test_validator_rejects_slow_motion_outside_clip_bounds(self) -> None:
        request = CreateEditJobRequest(**_request_payload())
        plan = build_edit_plan(request, "edit_bad_slowmo")
        data = plan.model_dump()
        data["clips"][0]["effects"].append(
            {
                "type": "slow_motion",
                "sourceStart": data["clips"][0]["sourceStart"] - 1.0,
                "sourceEnd": data["clips"][0]["sourceEnd"] + 1.0,
                "speed": 0.5,
            }
        )

        errors = validate_edit_plan(EditPlan(**data), request.clips, "free")

        self.assertTrue(any(error.code == "slow_motion_out_of_bounds" for error in errors))

    def test_repair_restores_free_watermark_and_outro(self) -> None:
        request = CreateEditJobRequest(**_request_payload())
        plan = build_edit_plan(request, "edit_repair")
        data = plan.model_dump()
        data["watermark"]["enabled"] = False
        data["outro"]["enabled"] = False

        repaired = repair_edit_plan(EditPlan(**data), "free")
        errors = validate_edit_plan(repaired, request.clips, "free")

        self.assertTrue(repaired.watermark.enabled)
        self.assertTrue(repaired.outro.enabled)
        self.assertFalse(any(error.code.startswith("missing_free") for error in errors))

    def test_edit_job_api_creates_and_revises_plan(self) -> None:
        app = create_app(self._settings())
        client = TestClient(app)

        create_response = client.post("/v1/edit-jobs", json=_request_payload())
        self.assertEqual(create_response.status_code, 200)
        edit_job_id = create_response.json()["editJobId"]

        plan_response = client.get(f"/v1/edit-jobs/{edit_job_id}/plan")
        self.assertEqual(plan_response.status_code, 200)
        self.assertEqual(plan_response.json()["plan"]["preset"], "personal_highlight")

        revise_response = client.post(
            f"/v1/edit-jobs/{edit_job_id}/revise",
            json={"command": "export_widescreen"},
        )
        self.assertEqual(revise_response.status_code, 200)
        self.assertEqual(revise_response.json()["plan"]["aspectRatio"], "16:9")

    def test_edit_job_api_stays_hidden_when_public_api_is_off(self) -> None:
        app = create_app(self._settings(public_api_enabled=False))
        client = TestClient(app)

        response = client.post("/v1/edit-jobs", json=_request_payload())

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
