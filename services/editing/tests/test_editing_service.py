from __future__ import annotations

from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
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

from app.editing import CreateEditJobRequest, GPTHighlightClipDecision, GPTHighlightSuggestedEdit, TEMPLATE_PACK_REGISTRY, apply_gpt_highlight_rerank, build_edit_job, get_plan_tier_policy, validate_template_registry  # noqa: E402
import editing_app.main as editing_main  # noqa: E402
from editing_app.config import EditingSettings  # noqa: E402
from editing_app.main import create_app  # noqa: E402
from editing_app.models import StoredRenderJob, now_utc  # noqa: E402
from editing_app.render_state import DurableRenderStateStore  # noqa: E402
from editing_app.render_storage import RenderStorage  # noqa: E402
from editing_app.retention_cleanup import run_cleanup  # noqa: E402


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

    def test_edit_job_error_routes_return_error_responses(self) -> None:
        client = TestClient(create_app(self._settings()))

        job_response = client.get("/v1/edit-jobs/edit_missing", params={"installId": "install-123"})
        plan_response = client.get("/v1/edit-jobs/edit_missing/plan", params={"installId": "install-123"})
        revisions_response = client.get("/v1/edit-jobs/edit_missing/revisions", params={"installId": "install-123"})

        self.assertEqual(job_response.status_code, 404)
        self.assertEqual(job_response.json()["errorCode"], "edit_job_not_found")
        self.assertEqual(plan_response.status_code, 404)
        self.assertEqual(plan_response.json()["errorCode"], "edit_job_not_found")
        self.assertEqual(revisions_response.status_code, 404)
        self.assertEqual(revisions_response.json()["errorCode"], "edit_job_not_found")

    def test_render_history_lists_install_scoped_metadata_without_presigned_urls(self) -> None:
        settings = self._settings()
        store = DurableRenderStateStore(RenderStorage(settings))
        expires_at = now_utc() + timedelta(days=7)
        store.save_job(
            StoredRenderJob(
                edit_job_id="edit_history_1",
                render_job_id="render_history_1",
                install_id="install-123",
                trace_id="trace_history_1",
                status="rendered",
                aspect_ratio="9:16",
                created_at=now_utc() - timedelta(minutes=10),
                updated_at=now_utc() - timedelta(minutes=5),
                source_object_key="sources/synthetic_game.mp4",
                output_object_key="edits/edit_history_1/render_jobs/render_history_1/final.mp4",
                render_log_object_key="edits/edit_history_1/render_jobs/render_history_1/render_log.json",
                plan_version="edit-plan-v1",
                template_id="personal_highlight_v1",
                duration_seconds=14.5,
                plan_tier="free",
                output_bytes=12345,
                retention_metadata={
                    "expiresAt": expires_at.isoformat(),
                    "retentionClass": "free_final_render",
                    "deleteEligible": False,
                    "planTier": "free",
                    "editJobId": "edit_history_1",
                    "renderJobId": "render_history_1",
                    "templateId": "personal_highlight_v1",
                    "outputBytes": 12345,
                    "durationSeconds": 14.5,
                },
            )
        )
        store.save_job(
            StoredRenderJob(
                edit_job_id="edit_history_other",
                render_job_id="render_history_other",
                install_id="install-other",
                trace_id="trace_history_other",
                status="rendered",
                aspect_ratio="9:16",
                created_at=now_utc() - timedelta(minutes=8),
                updated_at=now_utc() - timedelta(minutes=4),
                output_object_key="edits/edit_history_other/render_jobs/render_history_other/final.mp4",
                plan_version="edit-plan-v1",
                template_id="personal_highlight_v1",
                plan_tier="free",
            )
        )
        client = TestClient(create_app(settings))

        response = client.get("/v1/render-jobs", params={"installId": "install-123", "limit": 10})
        missing_response = client.get("/v1/render-jobs")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["installId"], "install-123")
        self.assertEqual([render["renderJobId"] for render in payload["renders"]], ["render_history_1"])
        self.assertEqual(payload["renders"][0]["retentionMetadata"]["expiresAt"], expires_at.isoformat())
        serialized = json.dumps(payload)
        self.assertNotIn("downloadUrl", serialized)
        self.assertNotIn("leaseToken", serialized)
        self.assertNotIn("render_history_other", serialized)
        self.assertEqual(missing_response.status_code, 400)
        self.assertEqual(missing_response.json()["errorCode"], "missing_install_id")

    def test_template_registry_loads_and_validates(self) -> None:
        validation = validate_template_registry()

        self.assertEqual(
            set(validation.keys()),
            {
                "personal_highlight_v1",
                "full_game_highlight_v1",
                "coach_review_v1",
                "recruiting_reel_pro_v1",
                "cinematic_mixtape_pro_v1",
                "nba_recap_pro_v1",
                "team_highlight_pro_v1",
            },
        )
        self.assertTrue(all(not errors for errors in validation.values()))
        self.assertEqual(TEMPLATE_PACK_REGISTRY["personal_highlight_v1"].watermarkProfile.assetId, "hoopclips_app_icon_v1")
        self.assertTrue(TEMPLATE_PACK_REGISTRY["recruiting_reel_pro_v1"].premiumOnly)

    def test_free_user_cannot_create_premium_template_edit_job(self) -> None:
        client = TestClient(create_app(self._settings()))
        request = self._edit_request().model_copy(update={"templateId": "cinematic_mixtape_pro_v1", "targetDurationSeconds": 30})

        response = client.post("/v1/edit-jobs", json=request.model_dump())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["errorCode"], "premium_template_required")

    def test_pro_premium_template_requires_revenuecat_verifier(self) -> None:
        previous_exports = os.environ.get("HOOPS_AI_EDIT_PRO_EXPORTS_ENABLED")
        previous_key = os.environ.get("HOOPS_REVENUECAT_REST_API_KEY")
        os.environ["HOOPS_AI_EDIT_PRO_EXPORTS_ENABLED"] = "true"
        os.environ.pop("HOOPS_REVENUECAT_REST_API_KEY", None)
        try:
            client = TestClient(create_app(self._settings()))
            request = self._edit_request().model_copy(
                update={
                    "templateId": "recruiting_reel_pro_v1",
                    "targetDurationSeconds": 60,
                    "planTier": "pro",
                    "revenueCatAppUserID": "hoops_email_test",
                }
            )

            response = client.post("/v1/edit-jobs", json=request.model_dump())

            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["errorCode"], "revenuecat_verifier_unconfigured")
        finally:
            if previous_exports is None:
                os.environ.pop("HOOPS_AI_EDIT_PRO_EXPORTS_ENABLED", None)
            else:
                os.environ["HOOPS_AI_EDIT_PRO_EXPORTS_ENABLED"] = previous_exports
            if previous_key is None:
                os.environ.pop("HOOPS_REVENUECAT_REST_API_KEY", None)
            else:
                os.environ["HOOPS_REVENUECAT_REST_API_KEY"] = previous_key

    def test_internal_plan_can_create_premium_template_edit_job(self) -> None:
        client = TestClient(create_app(self._settings()))
        request = self._edit_request().model_copy(
            update={
                "preset": "personal_highlight",
                "templateId": "cinematic_mixtape_pro_v1",
                "targetDurationSeconds": 45,
                "planTier": "internal",
            }
        )

        response = client.post("/v1/edit-jobs", json=request.model_dump())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["templateId"], "cinematic_mixtape_pro_v1")
        self.assertEqual(payload["planTier"], "internal")

    def test_renderer_writes_premium_template_signature(self) -> None:
        client = TestClient(create_app(self._settings()))
        edit_request = self._edit_request().model_copy(
            update={
                "preset": "personal_highlight",
                "templateId": "cinematic_mixtape_pro_v1",
                "targetDurationSeconds": 30,
                "planTier": "internal",
            }
        )
        payload = self._render_payload(edit_request)
        payload["planTier"] = "internal"

        response = client.post("/v1/render-jobs", json=payload)

        self.assertEqual(response.status_code, 200)
        render_job_id = response.json()["renderJobId"]
        status_response = client.get(f"/v1/render-jobs/{render_job_id}", params={"installId": edit_request.installId})
        self.assertEqual(status_response.status_code, 200)
        render_payload = status_response.json()
        self.assertEqual(render_payload["status"], "rendered")
        self.assertEqual(render_payload["templateId"], "cinematic_mixtape_pro_v1")
        render_log_key = render_payload["renderLogObjectKey"]
        log_path = self._temp_dir / render_log_key
        self.assertTrue(log_path.exists())
        render_log = json.loads(log_path.read_text(encoding="utf-8"))
        signature = render_log["ffmpeg"]["templateSignature"]
        self.assertEqual(render_log["ffmpeg"]["templateId"], "cinematic_mixtape_pro_v1")
        self.assertEqual(signature["templateId"], "cinematic_mixtape_pro_v1")
        self.assertEqual(signature["captionStyle"], "cinematic_hype")
        self.assertEqual(signature["effectProfile"], "cinematic_mixtape_effects")
        self.assertEqual(signature["audioProfile"], "cinematic_mixtape")
        self.assertEqual(signature["outroProfile"], "pro_clean_no_outro")
        self.assertTrue(signature["premiumOnly"])

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

    def test_version_reports_live_render_kill_switch(self) -> None:
        previous = os.environ.get("HOOPS_AI_EDIT_LIVE_RENDER_ENABLED")
        os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = "false"
        try:
            client = TestClient(create_app(self._settings()))

            response = client.get("/version")

            self.assertEqual(response.status_code, 200)
            flags = response.json()["featureFlags"]
            self.assertTrue(flags["aiEditEnabled"])
            self.assertFalse(flags["aiEditLiveRenderEnabled"])
            self.assertTrue(flags["aiEditRevisionEnabled"])
            self.assertTrue(flags["aiEditTemplatePackEnabled"])
        finally:
            if previous is None:
                os.environ.pop("HOOPS_AI_EDIT_LIVE_RENDER_ENABLED", None)
            else:
                os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = previous

    def test_live_render_kill_switch_rejects_render_without_local_fallback(self) -> None:
        previous = os.environ.get("HOOPS_AI_EDIT_LIVE_RENDER_ENABLED")
        os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = "false"
        try:
            client = TestClient(create_app(self._settings()))
            payload = self._render_payload(self._edit_request())

            response = client.post("/v1/render-jobs", json=payload)

            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["errorCode"], "ai_edit_live_render_disabled")
            self.assertFalse((self._temp_dir / "render_state").exists())
        finally:
            if previous is None:
                os.environ.pop("HOOPS_AI_EDIT_LIVE_RENDER_ENABLED", None)
            else:
                os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = previous

    def test_live_render_kill_switch_rejects_revision_render(self) -> None:
        previous = os.environ.get("HOOPS_AI_EDIT_LIVE_RENDER_ENABLED")
        os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = "true"
        try:
            client = TestClient(create_app(self._settings()))
            edit_request = self._edit_request()
            create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()
            revision_payload = client.post(
                f"/v1/edit-jobs/{create_payload['editJobId']}/revise",
                json={"installId": edit_request.installId, "command": "make_more_hype"},
            ).json()

            os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = "false"
            disabled_client = TestClient(create_app(self._settings()))
            render_response = disabled_client.post(
                f"/v1/edit-jobs/{create_payload['editJobId']}/revisions/{revision_payload['revisionId']}/render",
                json={"installId": edit_request.installId},
            )

            self.assertEqual(render_response.status_code, 403)
            self.assertEqual(render_response.json()["errorCode"], "ai_edit_live_render_disabled")
        finally:
            if previous is None:
                os.environ.pop("HOOPS_AI_EDIT_LIVE_RENDER_ENABLED", None)
            else:
                os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = previous

    def test_live_render_kill_switch_rejects_stored_edit_render_route(self) -> None:
        previous = os.environ.get("HOOPS_AI_EDIT_LIVE_RENDER_ENABLED")
        os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = "true"
        try:
            client = TestClient(create_app(self._settings()))
            edit_request = self._edit_request()
            create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()

            os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = "false"
            disabled_client = TestClient(create_app(self._settings()))
            render_response = disabled_client.post(
                f"/v1/edit-jobs/{create_payload['editJobId']}/render",
                json={"installId": edit_request.installId},
            )

            self.assertEqual(render_response.status_code, 403)
            self.assertEqual(render_response.json()["errorCode"], "ai_edit_live_render_disabled")
        finally:
            if previous is None:
                os.environ.pop("HOOPS_AI_EDIT_LIVE_RENDER_ENABLED", None)
            else:
                os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = previous

    def test_live_render_kill_switch_emits_safe_policy_failed_event(self) -> None:
        previous = os.environ.get("HOOPS_AI_EDIT_LIVE_RENDER_ENABLED")
        os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = "false"
        try:
            client = TestClient(create_app(self._settings()))
            payload = self._render_payload(self._edit_request())
            output = StringIO()

            with redirect_stdout(output):
                response = client.post("/v1/render-jobs", json=payload)

            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["errorCode"], "ai_edit_live_render_disabled")
            events = [json.loads(line) for line in output.getvalue().splitlines() if line.startswith("{")]
            policy_event = next(event for event in events if event.get("event") == "policy.failed")
            self.assertEqual(policy_event["failureReason"], "ai_edit_live_render_disabled")
            self.assertEqual(policy_event["planTier"], "free")
            self.assertEqual(policy_event["templateId"], "personal_highlight_v1")
            self.assertFalse(any("url" in key.lower() or "secret" in key.lower() for key in policy_event))
        finally:
            if previous is None:
                os.environ.pop("HOOPS_AI_EDIT_LIVE_RENDER_ENABLED", None)
            else:
                os.environ["HOOPS_AI_EDIT_LIVE_RENDER_ENABLED"] = previous

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

    def test_revision_definition_and_revised_plan_survive_app_reload(self) -> None:
        settings = self._settings()
        client = TestClient(create_app(settings))
        edit_request = self._edit_request()
        create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()

        revision_payload = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revise",
            json={"installId": edit_request.installId, "command": "make_more_hype"},
        ).json()

        reloaded_client = TestClient(create_app(settings))
        list_response = reloaded_client.get(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revisions",
            params={"installId": edit_request.installId},
        )
        get_response = reloaded_client.get(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revisions/{revision_payload['revisionId']}",
            params={"installId": edit_request.installId},
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["revisions"]), 1)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["revisionId"], revision_payload["revisionId"])
        self.assertEqual(get_response.json()["newPlanId"], revision_payload["newPlanId"])
        self.assertTrue((self._temp_dir / f"edits/{create_payload['editJobId']}/revisions/{revision_payload['revisionId']}.json").exists())
        self.assertTrue((self._temp_dir / f"edits/{create_payload['editJobId']}/plans/{revision_payload['newPlanId']}.json").exists())

    def test_render_lease_prevents_double_execution_and_stale_overwrite(self) -> None:
        settings = self._settings()
        store = DurableRenderStateStore(RenderStorage(settings))
        created_at = now_utc()
        job = StoredRenderJob(
            edit_job_id="edit_lease_state",
            render_job_id="render_lease_state",
            install_id="install-123",
            trace_id="trace_lease_state",
            status="queued",
            aspect_ratio="9:16",
            created_at=created_at,
            updated_at=created_at,
            source_object_key="sources/synthetic_game.mp4",
            plan_version="edit-plan-v1",
            template_id="personal_highlight_v1",
            plan_tier="free",
            idempotency_key="idem-lease-state",
        )
        store.save_job(job)

        first = store.acquire_render_lease("render_lease_state", "instance-a", "lease-a", created_at, ttl_seconds=300)
        second = store.acquire_render_lease("render_lease_state", "instance-b", "lease-b", created_at, ttl_seconds=300)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        leased = store.load_job("render_lease_state")
        self.assertIsNotNone(leased)
        assert leased is not None
        stale_completion = leased
        stale_completion.status = "rendered"
        stale_completion.output_object_key = "edits/edit_lease_state/render_jobs/render_lease_state/final.mp4"
        stale_completion.render_log_object_key = "edits/edit_lease_state/render_jobs/render_lease_state/render_log.json"
        self.assertFalse(store.save_job_if_lease(stale_completion, "wrong-lease"))

        expired = store.load_job("render_lease_state")
        self.assertIsNotNone(expired)
        assert expired is not None
        expired.lease_expires_at = created_at - timedelta(seconds=1)
        store.save_job(expired)
        reclaimed = store.acquire_render_lease("render_lease_state", "instance-b", "lease-b", created_at, ttl_seconds=300)
        self.assertIsNotNone(reclaimed)
        assert reclaimed is not None
        self.assertEqual(reclaimed.lease_owner, "instance-b")
        self.assertEqual(reclaimed.lease_token, "lease-b")

        stale_completion.lease_token = "lease-a"
        stale_completion.status = "rendered"
        self.assertFalse(store.save_job_if_lease(stale_completion, "lease-a"))
        self.assertEqual(store.load_job("render_lease_state").status, "rendering")  # type: ignore[union-attr]

    def test_retention_cleanup_dry_run_lists_expired_delete_eligible_artifacts(self) -> None:
        settings = self._settings()
        storage = RenderStorage(settings)
        store = DurableRenderStateStore(storage)
        expired_at = now_utc() - timedelta(days=1)
        job = StoredRenderJob(
            edit_job_id="edit_cleanup_state",
            render_job_id="render_cleanup_state",
            install_id="install-123",
            trace_id="trace_cleanup_state",
            status="rendered",
            aspect_ratio="9:16",
            created_at=expired_at - timedelta(days=1),
            updated_at=expired_at,
            output_object_key="edits/edit_cleanup_state/render_jobs/render_cleanup_state/final.mp4",
            render_log_object_key="edits/edit_cleanup_state/render_jobs/render_cleanup_state/render_log.json",
            source_object_key="sources/synthetic_game.mp4",
            plan_version="edit-plan-v1",
            template_id="personal_highlight_v1",
            plan_tier="free",
            expires_at=expired_at,
            output_bytes=1234,
            duration_seconds=15.0,
            retention_metadata={
                "expiresAt": expired_at.isoformat(),
                "retentionClass": "free_final_render",
                "deleteEligible": True,
                "planTier": "free",
                "editJobId": "edit_cleanup_state",
                "renderJobId": "render_cleanup_state",
                "templateId": "personal_highlight_v1",
                "outputBytes": 1234,
                "durationSeconds": 15.0,
            },
        )
        store.save_job(job)
        output_path = self._temp_dir / job.output_object_key
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"mp4")
        storage.put_json(job.render_log_object_key or "", "{}")

        report = run_cleanup(storage, store, execute=False, now=now_utc())

        self.assertEqual(report["mode"], "dry-run")
        self.assertEqual(report["candidateCount"], 1)
        self.assertEqual(report["objectKeyCount"], 3)
        self.assertEqual(report["estimatedOutputBytes"], 1234)
        candidate = report["candidates"][0]
        self.assertEqual(candidate["renderJobId"], "render_cleanup_state")
        self.assertEqual(candidate["outputBytes"], 1234)
        self.assertEqual(candidate["durationSeconds"], 15.0)
        self.assertIn(job.output_object_key, candidate["objectKeys"])
        self.assertIn(job.render_log_object_key, candidate["objectKeys"])
        self.assertIn("render_state/render_jobs/render_cleanup_state.json", candidate["objectKeys"])
        self.assertTrue(output_path.exists())

    def test_policy_rejection_emits_safe_policy_failed_event(self) -> None:
        client = TestClient(create_app(self._settings()))
        request = self._edit_request().model_copy(update={"targetDurationSeconds": 120, "templateId": "personal_highlight_v1"})
        output = StringIO()

        with redirect_stdout(output):
            response = client.post("/v1/edit-jobs", json=request.model_dump())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errorCode"], "render_duration_limit")
        events = [json.loads(line) for line in output.getvalue().splitlines() if line.startswith("{")]
        policy_event = next(event for event in events if event.get("event") == "policy.failed")
        self.assertEqual(policy_event["failureReason"], "render_duration_limit")
        self.assertEqual(policy_event["planTier"], "free")
        self.assertEqual(policy_event["templateId"], "personal_highlight_v1")
        self.assertFalse(any("url" in key.lower() or "secret" in key.lower() for key in policy_event))

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
        self.assertEqual(render_payload["workTimeline"]["renderJobId"], render_job_id)
        self.assertEqual(render_payload["workTimeline"]["status"], "rendered")
        step_ids = [step["stepId"] for step in render_payload["workTimeline"]["steps"]]
        self.assertEqual(
            step_ids,
            [
                "video_uploaded",
                "finding_highlights",
                "selecting_best_clips",
                "removing_duplicates",
                "applying_template",
                "adding_slow_motion",
                "adding_watermark_outro",
                "rendering_mp4",
                "finalizing_download",
            ],
        )
        self.assertTrue(all(step["status"] in {"complete", "running", "pending", "failed"} for step in render_payload["workTimeline"]["steps"]))
        self.assertEqual(render_payload["workReceipt"]["selectedClipCount"], 2)
        self.assertEqual(render_payload["workReceipt"]["candidateClipCount"], 2)
        self.assertEqual(render_payload["workReceipt"]["templateId"], "personal_highlight_v1")
        self.assertEqual(render_payload["workReceipt"]["outputResolution"], "720p")
        self.assertTrue(render_payload["workReceipt"]["watermarkIncluded"])
        self.assertTrue(render_payload["workReceipt"]["outroIncluded"])
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
        self.assertEqual(render_log["workTimeline"]["steps"][0]["stepId"], "video_uploaded")
        self.assertEqual(render_log["workReceipt"]["candidateClipCount"], 2)
        self.assertFalse(render_log["workReceipt"]["gptRerankApplied"])

        download_response = client.get(f"/v1/render-jobs/{render_payload['renderJobId']}/download-url", params={"installId": "install-123"})
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.json()["contentType"], "video/mp4")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_gpt_highlight_rerank_summary_feeds_render_receipt(self) -> None:
        original_reranker = editing_main.rerank_edit_request_with_gpt
        old_enabled = os.environ.get("HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED")
        old_key = os.environ.get("HOOPS_OPENAI_API_KEY")

        def fake_reranker(request, source_path, settings):
            decisions = [
                GPTHighlightClipDecision(
                    clipId="c2",
                    keep=True,
                    highlightScore=0.99,
                    watchabilityScore=0.95,
                    basketballEvent="Made Shot",
                    outcome="made",
                    caption="BUCKET",
                    reason="Clean shot outcome and watchable finish.",
                    suggestedEdit=GPTHighlightSuggestedEdit(
                        slowMotion=True,
                        slowMotionCenter=10.4,
                        captionMoment=10.4,
                        cropFocus="shooter",
                        extendBeforeSeconds=0.3,
                        extendAfterSeconds=0.5,
                    ),
                ),
                GPTHighlightClipDecision(
                    clipId="c1",
                    keep=False,
                    highlightScore=0.2,
                    watchabilityScore=0.3,
                    basketballEvent="Unclear",
                    outcome="unclear",
                    caption="SKIP",
                    reason="Less clear than the made shot.",
                    suggestedEdit=GPTHighlightSuggestedEdit(),
                ),
            ]
            return apply_gpt_highlight_rerank(request, decisions, "gpt-test", 2, 6)

        try:
            os.environ["HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED"] = "true"
            os.environ["HOOPS_OPENAI_API_KEY"] = "test-key"
            editing_main.rerank_edit_request_with_gpt = fake_reranker
            client = TestClient(editing_main.create_app(self._settings()))
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
            self.assertTrue(render_payload["workReceipt"]["gptRerankApplied"])
            self.assertEqual(render_payload["workReceipt"]["gptRerankModel"], "gpt-test")
            self.assertEqual(render_payload["workReceipt"]["gptRerankSampledClipCount"], 2)
            self.assertEqual(render_payload["workReceipt"]["gptRerankSampledFrameCount"], 6)
            self.assertEqual(render_payload["workReceipt"]["gptRerankKeptClipCount"], 1)
            self.assertEqual(render_payload["workReceipt"]["gptRerankRejectedClipCount"], 1)
            self.assertIn("GPT reranked 2 clips from 6 keyframes.", render_payload["workReceipt"]["summaryRows"])
        finally:
            editing_main.rerank_edit_request_with_gpt = original_reranker
            if old_enabled is None:
                os.environ.pop("HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED", None)
            else:
                os.environ["HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED"] = old_enabled
            if old_key is None:
                os.environ.pop("HOOPS_OPENAI_API_KEY", None)
            else:
                os.environ["HOOPS_OPENAI_API_KEY"] = old_key

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

        rerender_response = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/render",
            json={
                "installId": edit_request.installId,
                "forceNew": True,
                "idempotencyKey": "ios-locker-rerender-001",
            },
        )
        self.assertEqual(rerender_response.status_code, 200)
        self.assertNotEqual(rerender_response.json()["renderJobId"], render_job_id)

        history_response = client.get("/v1/render-jobs", params={"installId": edit_request.installId, "limit": 10})
        self.assertEqual(history_response.status_code, 200)
        history_payload = history_response.json()
        history_ids = [render["renderJobId"] for render in history_payload["renders"]]
        self.assertIn(render_job_id, history_ids)
        self.assertIn(rerender_response.json()["renderJobId"], history_ids)
        self.assertNotIn("downloadUrl", json.dumps(history_payload))

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
        self.assertEqual(render_payload["revisionId"], revision_payload["revisionId"])
        self.assertEqual(render_payload["aspectRatio"], "16:9")
        self.assertEqual(render_payload["retentionMetadata"]["revisionId"], revision_payload["revisionId"])
        log_path = self._temp_dir / render_payload["renderLogObjectKey"]
        render_log = json.loads(log_path.read_text(encoding="utf-8"))
        self.assertEqual(render_log["revisionId"], revision_payload["revisionId"])
        download_response = client.get(
            f"/v1/edit-jobs/{create_payload['editJobId']}/download-url",
            params={"installId": edit_request.installId},
        )
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.json()["renderJobId"], render_payload["renderJobId"])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_render_revision_after_reload_uses_persisted_revised_plan(self) -> None:
        settings = self._settings()
        client = TestClient(create_app(settings))
        edit_request = self._edit_request()
        create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()
        revision_payload = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revise",
            json={"installId": edit_request.installId, "command": "switch_format_widescreen"},
        ).json()

        reloaded_client = TestClient(create_app(settings))
        render_response = reloaded_client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revisions/{revision_payload['revisionId']}/render",
            json={"installId": edit_request.installId},
        )

        self.assertEqual(render_response.status_code, 200)
        status_response = reloaded_client.get(
            f"/v1/render-jobs/{render_response.json()['renderJobId']}",
            params={"installId": edit_request.installId},
        )
        self.assertEqual(status_response.status_code, 200)
        render_payload = status_response.json()
        self.assertEqual(render_payload["status"], "rendered")
        self.assertEqual(render_payload["revisionId"], revision_payload["revisionId"])
        self.assertEqual(render_payload["aspectRatio"], "16:9")
        durable_state = DurableRenderStateStore(RenderStorage(settings)).load_job(render_payload["renderJobId"])
        self.assertIsNotNone(durable_state)
        assert durable_state is not None
        self.assertEqual(durable_state.revision_id, revision_payload["revisionId"])
        self.assertEqual(durable_state.status, "rendered")
        self.assertIsNotNone(durable_state.lease_token)
        self.assertNotIn("leaseToken", render_payload)

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
    def test_render_state_survives_app_reload_for_status_and_idempotency(self) -> None:
        settings = self._settings()
        client = TestClient(create_app(settings))
        payload = self._render_payload(self._edit_request())
        payload["idempotencyKey"] = "idem-render-reload-001"

        first_response = client.post("/v1/render-jobs", json=payload)
        self.assertEqual(first_response.status_code, 200)
        render_job_id = first_response.json()["renderJobId"]

        reloaded_client = TestClient(create_app(settings))
        status_response = reloaded_client.get(f"/v1/render-jobs/{render_job_id}", params={"installId": "install-123"})
        edit_status_response = reloaded_client.get(f"/v1/edit-jobs/{payload['editJobId']}/render-status", params={"installId": "install-123"})
        duplicate_response = reloaded_client.post("/v1/render-jobs", json=payload)

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "rendered")
        self.assertTrue(status_response.json()["outputObjectKey"].endswith("/final.mp4"))
        self.assertTrue(status_response.json()["renderLogObjectKey"].endswith("/render_log.json"))
        self.assertEqual(edit_status_response.status_code, 200)
        self.assertEqual(edit_status_response.json()["renderJobId"], render_job_id)
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(duplicate_response.json()["renderJobId"], render_job_id)

    def test_stale_render_state_transitions_to_failed_timeout_after_reload(self) -> None:
        settings = self._settings()
        old_time = now_utc() - timedelta(seconds=get_plan_tier_policy("free").staleRenderTimeoutSeconds + 5)
        job = StoredRenderJob(
            edit_job_id="edit_stale_state",
            render_job_id="render_stale_state",
            install_id="install-123",
            trace_id="trace_stale_state",
            status="rendering",
            aspect_ratio="9:16",
            created_at=old_time,
            updated_at=old_time,
            source_object_key="sources/synthetic_game.mp4",
            plan_version="edit-plan-v1",
            template_id="personal_highlight_v1",
            plan_tier="free",
            idempotency_key="idem-stale-state",
        )
        DurableRenderStateStore(RenderStorage(settings)).save_job(job)

        response = TestClient(create_app(settings)).get("/v1/render-jobs/render_stale_state", params={"installId": "install-123"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "failed_timeout")
        self.assertEqual(payload["failureReason"], "failed_timeout")
        self.assertEqual(payload["retentionMetadata"]["retentionClass"], "free_failed_render")

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
