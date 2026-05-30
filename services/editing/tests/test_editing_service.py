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

from app.editing import (  # noqa: E402
    CreateEditJobRequest,
    EditPlanPatch,
    EditPlanClip,
    EditPlanPatchOperation,
    GPTHighlightClipDecision,
    GPTHighlightRerankSummary,
    GPTHighlightSuggestedEdit,
    TEMPLATE_PACK_REGISTRY,
    apply_gpt_highlight_rerank,
    build_edit_job,
    get_plan_tier_policy,
    validate_edit_plan,
    validate_template_registry,
)
import editing_app.main as editing_main  # noqa: E402
from editing_app.config import EditingSettings  # noqa: E402
from editing_app.gpt_reranker import GPTEditPlanPatchAttempt  # noqa: E402
from editing_app.main import create_app  # noqa: E402
from editing_app.models import StoredRenderJob, build_ai_work_receipt, now_utc  # noqa: E402
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


def _quality_signals(**overrides) -> dict:
    payload = {
        "setupVisible": True,
        "releaseVisible": True,
        "shotArcVisible": True,
        "eventVisible": True,
        "outcomeVisible": True,
        "rimResultVisible": True,
        "ballPathVisible": True,
        "playerControlVisible": True,
        "cleanCamera": True,
        "fullPlayContext": True,
        "reason": "Complete play context.",
    }
    payload.update(overrides)
    return payload


def _shot_result_evidence(**overrides) -> dict:
    payload = {
        "releaseToRimContinuity": "continuous",
        "rimResultEvidence": "made_visible",
        "outcomeConfidence": 0.92,
        "rimEntrySequence": "visible_entry",
        "ballApproachFrameRole": "eventCenter",
        "rimEntryFrameRole": "finish",
        "ballBelowRimOrNetFrameRole": "finish",
        "rimEntrySequenceConfidence": 0.92,
        "reason": "Ball flight and rim result are visible.",
    }
    payload.update(overrides)
    return payload


def _shot_tracking_evidence(**overrides) -> dict:
    payload = {
        "ballVisibleFrameRoles": ["eventCenter", "finish"],
        "rimVisibleFrameRoles": ["finish"],
        "releaseFrameRole": "eventCenter",
        "resultFrameRole": "finish",
        "ballEntersRimFrameRole": "finish",
        "netOrRimReactionVisible": True,
        "trajectoryContinuity": "continuous",
        "reason": "Shot action and rim result are visible in sampled frames.",
    }
    payload.update(overrides)
    return payload


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

    def _persist_queued_render_job(
        self,
        settings: EditingSettings,
        edit_job_id: str,
        install_id: str,
        source_object_key: str,
        idempotency_key: str,
        *,
        render_job_id: str,
        revision_id: str | None = None,
        aspect_ratio: str = "9:16",
    ) -> None:
        now = now_utc()
        DurableRenderStateStore(RenderStorage(settings)).save_job(
            StoredRenderJob(
                edit_job_id=edit_job_id,
                render_job_id=render_job_id,
                install_id=install_id,
                trace_id=f"trace_{render_job_id}",
                status="queued",
                aspect_ratio=aspect_ratio,
                created_at=now,
                updated_at=now,
                source_object_key=source_object_key,
                plan_version="edit-plan-v1",
                template_id="personal_highlight_v1",
                plan_tier="free",
                idempotency_key=idempotency_key,
                revision_id=revision_id,
            )
        )

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

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_create_edit_job_expands_thin_shot_context_even_when_gpt_disabled(self) -> None:
        old_enabled = os.environ.get("HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED")
        os.environ["HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED"] = "false"
        try:
            client = TestClient(create_app(self._settings()))
            edit_request = CreateEditJobRequest(
                videoId="video_context_expand_123",
                analysisJobId="analysis_context_expand_123",
                installId="install-123",
                sourceObjectKey=self._source_key(),
                preset="personal_highlight",
                targetDurationSeconds=15,
                aspectRatio="9:16",
                planTier="free",
                clips=[
                    {
                        **_clip("thin_make", 8.8, "Made Shot", 0.96),
                        "end": 10.5,
                        "eventCenter": 9.1,
                    }
                ],
            )

            create_response = client.post("/v1/edit-jobs", json=edit_request.model_dump())

            self.assertEqual(create_response.status_code, 200)
            create_payload = create_response.json()
            self.assertEqual(create_payload["status"], "plan_ready")
            self.assertEqual(create_payload["clipCount"], 1)
            plan_response = client.get(
                f"/v1/edit-jobs/{create_payload['editJobId']}/plan",
                params={"installId": edit_request.installId},
            )
            self.assertEqual(plan_response.status_code, 200)
            plan_clip = plan_response.json()["plan"]["clips"][0]
            self.assertEqual(plan_clip["clipId"], "thin_make")
            self.assertLess(plan_clip["sourceStart"], 8.8)
            self.assertGreater(plan_clip["sourceEnd"], 10.5)
        finally:
            if old_enabled is None:
                os.environ.pop("HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED", None)
            else:
                os.environ["HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED"] = old_enabled

    def test_create_edit_job_gpt_disabled_drops_weak_generic_fallback_candidate(self) -> None:
        old_enabled = os.environ.get("HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED")
        os.environ["HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED"] = "false"
        try:
            client = TestClient(create_app(self._settings()))
            edit_request = CreateEditJobRequest(
                videoId="video_weak_generic_fallback",
                analysisJobId="analysis_weak_generic_fallback",
                installId="install-123",
                preset="personal_highlight",
                targetDurationSeconds=15,
                aspectRatio="9:16",
                planTier="free",
                clips=[
                    {
                        **_clip("audio_only_filler", 0.0, "Highlight", 0.42),
                        "watchability": 0.2,
                        "motionScore": 0.22,
                        "audioPeak": 0.95,
                    },
                    {
                        **_clip("clear_defense", 8.0, "Defense", 0.66),
                        "watchability": 0.62,
                        "motionScore": 0.7,
                    },
                ],
            )

            create_response = client.post("/v1/edit-jobs", json=edit_request.model_dump())

            self.assertEqual(create_response.status_code, 200)
            create_payload = create_response.json()
            self.assertEqual(create_payload["status"], "plan_ready")
            self.assertEqual(create_payload["clipCount"], 1)
            plan_response = client.get(
                f"/v1/edit-jobs/{create_payload['editJobId']}/plan",
                params={"installId": edit_request.installId},
            )
            self.assertEqual(plan_response.status_code, 200)
            self.assertEqual([clip["clipId"] for clip in plan_response.json()["plan"]["clips"]], ["clear_defense"])
        finally:
            if old_enabled is None:
                os.environ.pop("HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED", None)
            else:
                os.environ["HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED"] = old_enabled

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

    def test_version_reports_required_gpt_editor_flags(self) -> None:
        flag_names = (
            "HOOPS_AI_CLIP_GPT_EDITOR_ENABLED",
            "HOOPS_AI_CLIP_GPT_PLAN_EDIT_ENABLED",
            "HOOPS_AI_CLIP_GPT_REVISION_ENABLED",
        )
        previous = {name: os.environ.get(name) for name in flag_names}
        for name in flag_names:
            os.environ[name] = "true"
        try:
            client = TestClient(create_app(self._settings()))

            response = client.get("/version")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            flags = payload["featureFlags"]
            self.assertTrue(flags["aiClipGptEditorEnabled"])
            self.assertTrue(flags["aiClipGptPlanEditEnabled"])
            self.assertTrue(flags["aiClipGptRevisionEnabled"])
            self.assertTrue(flags["gptHighlightRerankerEnabled"])
            reranker_status = payload["gptHighlightReranker"]
            self.assertTrue(reranker_status["enabled"])
            self.assertTrue(reranker_status["aiClipGptPlanEditEnabled"])
            self.assertTrue(reranker_status["aiClipGptRevisionEnabled"])
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

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
        self.assertEqual(revision_payload["revisionPlanner"], "deterministic_patch")
        self.assertFalse(revision_payload["gptRevisionPatchApplied"])
        self.assertEqual(revision_payload["gptRevisionPatchStatus"], "disabled")
        self.assertEqual(revision_payload["gptRevisionPatchFallbackReason"], "feature_flag_disabled")

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
        self.assertEqual(get_response.json()["revisionPlanner"], "deterministic_patch")
        self.assertTrue((self._temp_dir / f"edits/{create_payload['editJobId']}/revisions/{revision_payload['revisionId']}.json").exists())
        self.assertTrue((self._temp_dir / f"edits/{create_payload['editJobId']}/plans/{revision_payload['newPlanId']}.json").exists())

    def test_revise_edit_job_surfaces_gpt_patch_planner_when_applied(self) -> None:
        previous_revision = os.environ.get("HOOPS_AI_CLIP_GPT_REVISION_ENABLED")
        previous_editor = os.environ.get("HOOPS_AI_CLIP_GPT_EDITOR_ENABLED")
        os.environ["HOOPS_AI_CLIP_GPT_REVISION_ENABLED"] = "true"
        os.environ["HOOPS_AI_CLIP_GPT_EDITOR_ENABLED"] = "true"
        original_attempt = editing_main.request_gpt_edit_plan_patch_attempt
        try:
            client = TestClient(create_app(self._settings()))
            edit_request = self._edit_request()
            create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()

            def fake_gpt_patch_attempt(job, revision, settings):
                patch = EditPlanPatch(
                    baseEditPlanId=job.edit_job_id,
                    revisionIntent=revision.command,
                    summary="GPT added a safe hype timing adjustment.",
                    operations=[
                        EditPlanPatchOperation(
                            op="replace",
                            path="/targetDurationSeconds",
                            value=30,
                            reason="Keep the revision fast and punchy.",
                        )
                    ],
                )
                return GPTEditPlanPatchAttempt(patch=patch, status="applied")

            editing_main.request_gpt_edit_plan_patch_attempt = fake_gpt_patch_attempt
            revise_response = client.post(
                f"/v1/edit-jobs/{create_payload['editJobId']}/revise",
                json={"installId": edit_request.installId, "command": "make_more_hype"},
            )

            self.assertEqual(revise_response.status_code, 200)
            revision_payload = revise_response.json()
            self.assertEqual(revision_payload["revisionPlanner"], "gpt_patch")
            self.assertTrue(revision_payload["gptRevisionPatchApplied"])
            self.assertEqual(revision_payload["gptRevisionPatchStatus"], "applied")
            self.assertIsNone(revision_payload.get("gptRevisionPatchFallbackReason"))
            self.assertEqual(revision_payload["revisedPlan"]["targetDurationSeconds"], 30)
        finally:
            editing_main.request_gpt_edit_plan_patch_attempt = original_attempt
            if previous_revision is None:
                os.environ.pop("HOOPS_AI_CLIP_GPT_REVISION_ENABLED", None)
            else:
                os.environ["HOOPS_AI_CLIP_GPT_REVISION_ENABLED"] = previous_revision
            if previous_editor is None:
                os.environ.pop("HOOPS_AI_CLIP_GPT_EDITOR_ENABLED", None)
            else:
                os.environ["HOOPS_AI_CLIP_GPT_EDITOR_ENABLED"] = previous_editor

    def test_revise_edit_job_surfaces_gpt_patch_fallback_reason(self) -> None:
        previous_revision = os.environ.get("HOOPS_AI_CLIP_GPT_REVISION_ENABLED")
        previous_editor = os.environ.get("HOOPS_AI_CLIP_GPT_EDITOR_ENABLED")
        os.environ["HOOPS_AI_CLIP_GPT_REVISION_ENABLED"] = "true"
        os.environ["HOOPS_AI_CLIP_GPT_EDITOR_ENABLED"] = "true"
        original_attempt = editing_main.request_gpt_edit_plan_patch_attempt
        try:
            client = TestClient(create_app(self._settings()))
            edit_request = self._edit_request()
            create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()

            def fake_gpt_patch_attempt(job, revision, settings):
                return GPTEditPlanPatchAttempt(
                    patch=None,
                    status="fallback",
                    fallback_reason="patch_validation_failed",
                )

            editing_main.request_gpt_edit_plan_patch_attempt = fake_gpt_patch_attempt
            revise_response = client.post(
                f"/v1/edit-jobs/{create_payload['editJobId']}/revise",
                json={"installId": edit_request.installId, "command": "make_more_hype"},
            )

            self.assertEqual(revise_response.status_code, 200)
            revision_payload = revise_response.json()
            self.assertEqual(revision_payload["revisionPlanner"], "deterministic_patch")
            self.assertFalse(revision_payload["gptRevisionPatchApplied"])
            self.assertEqual(revision_payload["gptRevisionPatchStatus"], "fallback")
            self.assertEqual(revision_payload["gptRevisionPatchFallbackReason"], "patch_validation_failed")
        finally:
            editing_main.request_gpt_edit_plan_patch_attempt = original_attempt
            if previous_revision is None:
                os.environ.pop("HOOPS_AI_CLIP_GPT_REVISION_ENABLED", None)
            else:
                os.environ["HOOPS_AI_CLIP_GPT_REVISION_ENABLED"] = previous_revision
            if previous_editor is None:
                os.environ.pop("HOOPS_AI_CLIP_GPT_EDITOR_ENABLED", None)
            else:
                os.environ["HOOPS_AI_CLIP_GPT_EDITOR_ENABLED"] = previous_editor

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

    def test_retention_cleanup_execute_deletes_expired_delete_eligible_artifacts(self) -> None:
        settings = self._settings()
        storage = RenderStorage(settings)
        store = DurableRenderStateStore(storage)
        expired_at = now_utc() - timedelta(days=1)
        job = StoredRenderJob(
            edit_job_id="edit_cleanup_execute",
            render_job_id="render_cleanup_execute",
            install_id="install-123",
            trace_id="trace_cleanup_execute",
            status="rendered",
            aspect_ratio="9:16",
            created_at=expired_at - timedelta(days=1),
            updated_at=expired_at,
            output_object_key="edits/edit_cleanup_execute/render_jobs/render_cleanup_execute/final.mp4",
            render_log_object_key="edits/edit_cleanup_execute/render_jobs/render_cleanup_execute/render_log.json",
            source_object_key="sources/synthetic_game.mp4",
            plan_version="edit-plan-v1",
            template_id="personal_highlight_v1",
            plan_tier="free",
            idempotency_key="idem-cleanup-execute",
            expires_at=expired_at,
            output_bytes=1234,
            duration_seconds=15.0,
            retention_metadata={
                "expiresAt": expired_at.isoformat(),
                "retentionClass": "free_final_render",
                "deleteEligible": True,
                "planTier": "free",
                "editJobId": "edit_cleanup_execute",
                "renderJobId": "render_cleanup_execute",
                "templateId": "personal_highlight_v1",
                "outputBytes": 1234,
                "durationSeconds": 15.0,
            },
        )
        store.save_job(job)
        output_path = self._temp_dir / job.output_object_key
        state_path = self._temp_dir / "render_state/render_jobs/render_cleanup_execute.json"
        idempotency_path = self._temp_dir / store.idempotency_index_key("idem-cleanup-execute")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"mp4")
        storage.put_json(job.render_log_object_key or "", "{}")
        self.assertTrue(idempotency_path.exists())

        report = run_cleanup(storage, store, execute=True, now=now_utc())

        self.assertEqual(report["mode"], "execute")
        self.assertEqual(report["candidateCount"], 1)
        self.assertEqual(report["objectKeyCount"], 4)
        self.assertEqual(set(report["deletedObjectKeys"]), set(report["candidates"][0]["objectKeys"]))
        self.assertFalse(output_path.exists())
        self.assertFalse((self._temp_dir / (job.render_log_object_key or "")).exists())
        self.assertFalse(state_path.exists())
        self.assertFalse(idempotency_path.exists())

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
        self.assertEqual(render_payload["workReceipt"]["timingQualitySelectedClipCount"], 2)
        self.assertEqual(render_payload["workReceipt"]["timingIssueCandidateCount"], 0)
        self.assertEqual(render_payload["workReceipt"]["timingIssueSelectedClipCount"], 0)
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
        self.assertEqual(render_log["workReceipt"]["timingQualitySelectedClipCount"], 2)

        download_response = client.get(f"/v1/render-jobs/{render_payload['renderJobId']}/download-url", params={"installId": "install-123"})
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.json()["contentType"], "video/mp4")

    def test_ai_work_receipt_flags_selected_timing_context_issues(self) -> None:
        base_request = self._edit_request()
        edit_request = base_request.model_copy(
            update={
                "clips": [
                    base_request.clips[0].model_copy(
                        update={
                            "id": "late_steal",
                            "start": 10.0,
                            "end": 13.0,
                            "eventCenter": 10.1,
                            "label": "Steal",
                        }
                    )
                ],
                "targetDurationSeconds": 15,
            }
        )
        edit_job = build_edit_job(edit_request, "edit_timing_receipt")
        self.assertIn("empty_clip_list", [error.code for error in edit_job.validation_errors])
        receipt_plan = edit_job.plan.model_copy(
            update={
                "clips": [
                    EditPlanClip(
                        clipId="late_steal",
                        sourceStart=10.0,
                        sourceEnd=13.0,
                        eventCenter=10.1,
                        timelineStart=1.2,
                        timelineEnd=4.2,
                        label="Steal",
                        caption="STEAL",
                        cropMode="center_action",
                    )
                ]
            }
        )
        created_at = now_utc()
        render_job = StoredRenderJob(
            edit_job_id="edit_timing_receipt",
            render_job_id="render_timing_receipt",
            install_id=edit_request.installId,
            trace_id="trace_timing_receipt",
            status="rendered",
            aspect_ratio="9:16",
            created_at=created_at,
            updated_at=created_at,
            completed_at=created_at,
            source_object_key=edit_request.sourceObjectKey,
            output_object_key="edits/edit_timing_receipt/render_jobs/render_timing_receipt/final.mp4",
            render_log_object_key="edits/edit_timing_receipt/render_jobs/render_timing_receipt/render_log.json",
            duration_seconds=3.0,
            plan_version="edit-plan-v1",
            template_id="personal_highlight_v1",
            plan_tier="free",
            idempotency_key="idem-timing-receipt",
        )

        receipt = build_ai_work_receipt(render_job, receipt_plan, edit_request.clips)

        self.assertEqual(receipt.timingIssueCandidateCount, 1)
        self.assertEqual(receipt.timingIssueSelectedClipCount, 1)
        self.assertEqual(receipt.timingQualitySelectedClipCount, 0)
        self.assertIn("Flagged 1 selected clip with weak timing/context.", receipt.summaryRows)

    def test_edit_plan_validation_rejects_trimmed_defensive_context(self) -> None:
        payload = self._edit_request().model_dump()
        payload["targetDurationSeconds"] = 15
        payload["clips"] = [
            _clip("late_steal", 10.0, "Steal", 0.92),
            _clip("cutoff_steal", 20.0, "Steal", 0.91),
        ]
        edit_request = CreateEditJobRequest(**payload)
        edit_job = build_edit_job(edit_request, "edit_defensive_plan_context")
        self.assertFalse(edit_job.validation_errors)
        trimmed_plan = edit_job.plan.model_copy(
            update={
                "clips": [
                    EditPlanClip(
                        clipId="late_steal",
                        sourceStart=10.0,
                        sourceEnd=13.0,
                        eventCenter=10.1,
                        timelineStart=1.2,
                        timelineEnd=4.2,
                        label="Steal",
                        caption="STEAL",
                        cropMode="center_action",
                    ),
                    EditPlanClip(
                        clipId="cutoff_steal",
                        sourceStart=20.0,
                        sourceEnd=23.0,
                        eventCenter=22.6,
                        timelineStart=4.2,
                        timelineEnd=7.2,
                        label="Steal",
                        caption="STEAL",
                        cropMode="center_action",
                    )
                ]
            }
        )

        errors = validate_edit_plan(trimmed_plan, edit_request.clips, edit_request.planTier)
        codes = [error.code for error in errors]

        self.assertIn("defensive_context_missing_setup", codes)
        self.assertIn("defensive_context_missing_outcome", codes)

    def test_ai_work_receipt_does_not_count_stop_and_pop_jumper_as_defense(self) -> None:
        payload = self._edit_request().model_dump()
        payload["targetDurationSeconds"] = 15
        payload["clips"] = [_clip("stop_pop", 0.0, "Stop and Pop Jumper", 0.92)]
        edit_request = CreateEditJobRequest(**payload)
        edit_job = build_edit_job(edit_request, "edit_stop_pop_receipt")
        self.assertFalse(edit_job.validation_errors)
        created_at = now_utc()
        render_job = StoredRenderJob(
            edit_job_id="edit_stop_pop_receipt",
            render_job_id="render_stop_pop_receipt",
            install_id=edit_request.installId,
            trace_id="trace_stop_pop_receipt",
            status="rendered",
            aspect_ratio="9:16",
            created_at=created_at,
            updated_at=created_at,
            completed_at=created_at,
            source_object_key=edit_request.sourceObjectKey,
            output_object_key="edits/edit_stop_pop_receipt/render_jobs/render_stop_pop_receipt/final.mp4",
            render_log_object_key="edits/edit_stop_pop_receipt/render_jobs/render_stop_pop_receipt/render_log.json",
            duration_seconds=5.0,
            plan_version="edit-plan-v1",
            template_id="personal_highlight_v1",
            plan_tier="free",
            idempotency_key="idem-stop-pop-receipt",
        )

        receipt = build_ai_work_receipt(render_job, edit_job.plan, edit_request.clips)

        self.assertEqual(receipt.defensiveSelectedClipCount, 0)
        self.assertNotIn("Included 1 defensive highlight.", receipt.summaryRows)

    def test_ai_work_receipt_does_not_count_plain_turnover_as_defense(self) -> None:
        payload = self._edit_request().model_dump()
        payload["targetDurationSeconds"] = 15
        payload["clips"] = [_clip("plain_turnover", 0.0, "Turnover", 0.92)]
        edit_request = CreateEditJobRequest(**payload)
        edit_job = build_edit_job(edit_request, "edit_plain_turnover_receipt")
        self.assertFalse(edit_job.validation_errors)
        created_at = now_utc()
        render_job = StoredRenderJob(
            edit_job_id="edit_plain_turnover_receipt",
            render_job_id="render_plain_turnover_receipt",
            install_id=edit_request.installId,
            trace_id="trace_plain_turnover_receipt",
            status="rendered",
            aspect_ratio="9:16",
            created_at=created_at,
            updated_at=created_at,
            completed_at=created_at,
            source_object_key=edit_request.sourceObjectKey,
            output_object_key="edits/edit_plain_turnover_receipt/render_jobs/render_plain_turnover_receipt/final.mp4",
            render_log_object_key="edits/edit_plain_turnover_receipt/render_jobs/render_plain_turnover_receipt/render_log.json",
            duration_seconds=5.0,
            plan_version="edit-plan-v1",
            template_id="personal_highlight_v1",
            plan_tier="free",
            idempotency_key="idem-plain-turnover-receipt",
        )

        receipt = build_ai_work_receipt(render_job, edit_job.plan, edit_request.clips)

        self.assertEqual(receipt.defensiveSelectedClipCount, 0)
        self.assertNotIn("Included 1 defensive highlight.", receipt.summaryRows)

    def test_ai_work_receipt_summarizes_validated_shot_outcome_evidence(self) -> None:
        payload = self._edit_request().model_dump()
        payload["targetDurationSeconds"] = 15
        payload["clips"] = [
            {
                **_clip("gpt_tracked_make", 0.0, "Made Shot", 0.95),
                "nativeShotSignals": {
                    "isShotLike": True,
                    "leadInSeconds": 2.4,
                    "followThroughSeconds": 2.6,
                    "setupContextScore": 1.0,
                    "outcomeContextScore": 1.0,
                    "eventCenterQuality": 1.0,
                    "contextQualityScore": 1.0,
                    "timingWindowOk": True,
                    "outcome": "made",
                    "outcomeConfidence": 0.92,
                    "outcomeEvidenceSource": "gpt_shot_tracking",
                    "outcomeReliabilityScore": 0.93,
                },
            },
            {
                **_clip("label_only_make", 8.0, "Bucket", 0.9),
                "nativeShotSignals": {
                    "isShotLike": True,
                    "leadInSeconds": 2.4,
                    "followThroughSeconds": 2.6,
                    "setupContextScore": 1.0,
                    "outcomeContextScore": 1.0,
                    "eventCenterQuality": 1.0,
                    "contextQualityScore": 1.0,
                    "timingWindowOk": True,
                    "outcome": "made",
                    "outcomeConfidence": 0.82,
                    "outcomeEvidenceSource": "label_only",
                    "outcomeReliabilityScore": 0.58,
                },
            },
        ]
        edit_request = CreateEditJobRequest(**payload)
        edit_job = build_edit_job(edit_request, "edit_outcome_receipt")
        self.assertFalse(edit_job.validation_errors)
        created_at = now_utc()
        render_job = StoredRenderJob(
            edit_job_id="edit_outcome_receipt",
            render_job_id="render_outcome_receipt",
            install_id=edit_request.installId,
            trace_id="trace_outcome_receipt",
            status="rendered",
            aspect_ratio="9:16",
            created_at=created_at,
            updated_at=created_at,
            completed_at=created_at,
            source_object_key=edit_request.sourceObjectKey,
            output_object_key="edits/edit_outcome_receipt/render_jobs/render_outcome_receipt/final.mp4",
            render_log_object_key="edits/edit_outcome_receipt/render_jobs/render_outcome_receipt/render_log.json",
            duration_seconds=10.0,
            plan_version="edit-plan-v1",
            template_id="personal_highlight_v1",
            plan_tier="free",
            idempotency_key="idem-outcome-receipt",
        )

        receipt = build_ai_work_receipt(render_job, edit_job.plan, edit_request.clips)

        self.assertEqual(receipt.shotOutcomeEvidenceSelectedClipCount, 1)
        self.assertEqual(receipt.shotOutcomeIssueSelectedClipCount, 1)
        self.assertEqual(receipt.labelOnlyOutcomeSelectedClipCount, 1)
        self.assertIn("Shot outcome evidence: 1 selected clip passed rim/result tracking checks.", receipt.summaryRows)
        self.assertIn("Needs review: 1 selected shot outcome came from label-only evidence.", receipt.summaryRows)

    def test_ai_work_receipt_summarizes_gpt_fallback_quality_rejections(self) -> None:
        payload = self._edit_request().model_dump()
        payload["targetDurationSeconds"] = 15
        payload["clips"] = [
            {**_clip("tiny", 0.0, "Made Shot", 0.99), "end": 0.1, "eventCenter": 0.05},
            {**_clip("pre_basket", 6.0, "Made Shot", 0.98), "end": 12.0, "eventCenter": 6.1},
            _clip("complete_make", 14.0, "Made Shot", 0.82),
        ]
        edit_request = CreateEditJobRequest(**payload)
        edit_job = build_edit_job(
            edit_request.model_copy(update={"clips": [edit_request.clips[2]]}),
            "edit_fallback_receipt",
        )
        self.assertFalse(edit_job.validation_errors)
        created_at = now_utc()
        render_job = StoredRenderJob(
            edit_job_id="edit_fallback_receipt",
            render_job_id="render_fallback_receipt",
            install_id=edit_request.installId,
            trace_id="trace_fallback_receipt",
            status="rendered",
            aspect_ratio="9:16",
            created_at=created_at,
            updated_at=created_at,
            completed_at=created_at,
            source_object_key=edit_request.sourceObjectKey,
            output_object_key="edits/edit_fallback_receipt/render_jobs/render_fallback_receipt/final.mp4",
            render_log_object_key="edits/edit_fallback_receipt/render_jobs/render_fallback_receipt/render_log.json",
            duration_seconds=5.0,
            plan_version="edit-plan-v1",
            template_id="personal_highlight_v1",
            plan_tier="free",
            idempotency_key="idem-fallback-receipt",
        )
        summary = GPTHighlightRerankSummary(
            status="fallback",
            model="gpt-test",
            keptClipIds=["complete_make"],
            rejectedClipIds=["tiny", "pre_basket"],
            rejectedReasonCounts={"candidate_missing_minimum_quality_context": 2},
            fallbackReason="openai_unavailable",
        )

        receipt = build_ai_work_receipt(render_job, edit_job.plan, edit_request.clips, summary)

        self.assertEqual(receipt.gptRerankKeptClipCount, 1)
        self.assertEqual(receipt.gptRerankRejectedClipCount, 2)
        self.assertIn("GPT rerank fallback: openai_unavailable.", receipt.summaryRows)
        self.assertIn("Fallback kept 1 render-worthy clip after quality checks.", receipt.summaryRows)
        self.assertIn("Fallback rejected clips: candidate_missing_minimum_quality_context x2.", receipt.summaryRows)

    def test_create_edit_job_gpt_all_rejected_returns_empty_clip_validation_error(self) -> None:
        original_reranker = editing_main.rerank_edit_request_with_gpt
        old_enabled = os.environ.get("HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED")
        old_key = os.environ.get("HOOPS_OPENAI_API_KEY")

        def fake_reranker(request, source_path, settings):
            decisions = [
                GPTHighlightClipDecision(
                    clipId=clip.id,
                    keep=False,
                    rejectReason="boring",
                    highlightScore=0.2,
                    watchabilityScore=0.3,
                    basketballEvent="Unclear",
                    outcome="unclear",
                    caption="SKIP",
                    reason="GPT judged this candidate unclear or boring.",
                    qualitySignals=_quality_signals(outcomeVisible=False, ballPathVisible=False, fullPlayContext=False),
                    shotResultEvidence=_shot_result_evidence(),
                    shotTrackingEvidence=_shot_tracking_evidence(),
                    suggestedEdit=GPTHighlightSuggestedEdit(),
                )
                for clip in request.clips
            ]
            return apply_gpt_highlight_rerank(request, decisions, "gpt-test", len(request.clips), len(request.clips) * 3)

        try:
            os.environ["HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED"] = "true"
            os.environ["HOOPS_OPENAI_API_KEY"] = "test-key"
            editing_main.rerank_edit_request_with_gpt = fake_reranker
            client = TestClient(editing_main.create_app(self._settings()))
            edit_request = CreateEditJobRequest(
                videoId="video_gpt_rejects_all",
                analysisJobId="analysis_gpt_rejects_all",
                installId="install-123",
                preset="personal_highlight",
                targetDurationSeconds=15,
                aspectRatio="9:16",
                planTier="free",
                clips=[_clip("c1", 0.0, "Highlight", 0.62), _clip("c2", 8.0, "Made Shot", 0.9)],
            )

            response = client.post("/v1/edit-jobs", json=edit_request.model_dump())

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["errorCode"], "empty_clip_list")
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
                    basketballEvent="Steal",
                    outcome="steal",
                    caption="PICKED",
                    reason="Clean defensive possession change and watchable finish.",
                    qualitySignals=_quality_signals(),
                    shotResultEvidence=_shot_result_evidence(),
                    shotTrackingEvidence=_shot_tracking_evidence(),
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
                    qualitySignals=_quality_signals(outcomeVisible=False, ballPathVisible=False, fullPlayContext=False),
                    shotResultEvidence=_shot_result_evidence(),
                    shotTrackingEvidence=_shot_tracking_evidence(),
                    suggestedEdit=GPTHighlightSuggestedEdit(),
                ),
            ]
            return apply_gpt_highlight_rerank(request, decisions, "gpt-test", 2, 6, story_order=["c2"])

        try:
            os.environ["HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED"] = "true"
            os.environ["HOOPS_OPENAI_API_KEY"] = "test-key"
            editing_main.rerank_edit_request_with_gpt = fake_reranker
            client = TestClient(editing_main.create_app(self._settings()))
            base_request = self._edit_request()
            base_payload = base_request.model_dump(mode="json")
            edit_request = CreateEditJobRequest.model_validate(
                {
                    **base_payload,
                    "teamSelection": {
                        "mode": "team",
                        "teamId": "team_dark",
                        "label": "Dark jerseys",
                        "colorLabel": "black",
                        "confidenceThreshold": 0.85,
                        "includeUncertain": True,
                    },
                    "clips": [
                        {
                            **base_payload["clips"][0],
                            "teamAttribution": {
                                "teamId": "team_dark",
                                "label": "Dark jerseys",
                                "colorLabel": "black",
                                "confidence": 0.92,
                                "source": "quick_scan",
                                "evidenceFrameRefs": ["clip_0_setup", "clip_0_result"],
                                "evidenceRoleGroups": ["setup", "outcome"],
                            },
                        },
                        {
                            **base_payload["clips"][1],
                            "label": "Steal",
                            "teamAttribution": {
                                "teamId": "team_light",
                                "label": "Light jerseys",
                                "colorLabel": "white",
                                "confidence": 0.64,
                                "source": "quick_scan",
                            },
                            "teamAttributionStatus": "uncertain",
                            "userReviewDecision": "kept",
                        },
                    ],
                }
            )
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
            self.assertEqual(render_payload["workReceipt"]["gptUncertainReviewClipCount"], 1)
            self.assertEqual(render_payload["workReceipt"]["gptUncertainReviewClipIds"], ["c2"])
            self.assertEqual(render_payload["workReceipt"]["gptRerankRejectedReasonCounts"]["unclear_or_non_basketball_outcome"], 1)
            self.assertEqual(render_payload["workReceipt"]["gptRerankStoryOrderClipIds"], ["c2"])
            self.assertEqual(render_payload["workReceipt"]["teamUncertainCandidateCount"], 1)
            self.assertEqual(render_payload["workReceipt"]["teamUncertainSelectedClipCount"], 1)
            self.assertEqual(render_payload["workReceipt"]["defensiveSelectedClipCount"], 1)
            self.assertEqual(render_payload["workReceipt"]["timingQualitySelectedClipCount"], 1)
            self.assertEqual(render_payload["workReceipt"]["timingIssueCandidateCount"], 0)
            self.assertEqual(render_payload["workReceipt"]["timingIssueSelectedClipCount"], 0)
            self.assertIn("GPT reranked 2 clips from 6 keyframes.", render_payload["workReceipt"]["summaryRows"])
            self.assertIn("GPT rejected clips: unclear_or_non_basketball_outcome x1.", render_payload["workReceipt"]["summaryRows"])
            self.assertIn("GPT story order applied to 1 candidate clip.", render_payload["workReceipt"]["summaryRows"])
            self.assertIn("Kept 1 uncertain team candidate available for Review.", render_payload["workReceipt"]["summaryRows"])
            self.assertIn("Kept 1 uncertain team clip for review.", render_payload["workReceipt"]["summaryRows"])
            self.assertIn("Included 1 defensive highlight.", render_payload["workReceipt"]["summaryRows"])
            self.assertIn("Timing quality: 1 selected clip passed context checks.", render_payload["workReceipt"]["summaryRows"])
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
        self.assertFalse(render_payload["workReceipt"]["gptRerankApplied"])
        self.assertEqual(render_payload["workReceipt"]["gptRerankFallbackReason"], "feature_flag_disabled")
        self.assertEqual(render_payload["workReceipt"]["gptRerankKeptClipCount"], 2)
        self.assertEqual(render_payload["workReceipt"]["gptRerankRejectedClipCount"], 0)
        self.assertIn("GPT rerank disabled: feature_flag_disabled.", render_payload["workReceipt"]["summaryRows"])
        self.assertIn(
            "Fallback kept 2 render-worthy clips after quality checks.",
            render_payload["workReceipt"]["summaryRows"],
        )

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
        rerender_without_key_response = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/render",
            json={
                "installId": edit_request.installId,
                "forceNew": True,
            },
        )
        self.assertEqual(rerender_without_key_response.status_code, 200)
        self.assertNotEqual(rerender_without_key_response.json()["renderJobId"], render_job_id)
        self.assertNotEqual(rerender_without_key_response.json()["renderJobId"], rerender_response.json()["renderJobId"])
        latest_download_response = client.get(
            f"/v1/edit-jobs/{create_payload['editJobId']}/download-url",
            params={"installId": edit_request.installId},
        )
        self.assertEqual(latest_download_response.status_code, 200)
        self.assertEqual(latest_download_response.json()["renderJobId"], rerender_without_key_response.json()["renderJobId"])

        history_response = client.get("/v1/render-jobs", params={"installId": edit_request.installId, "limit": 10})
        self.assertEqual(history_response.status_code, 200)
        history_payload = history_response.json()
        history_ids = [render["renderJobId"] for render in history_payload["renders"]]
        self.assertIn(render_job_id, history_ids)
        self.assertIn(rerender_response.json()["renderJobId"], history_ids)
        self.assertIn(rerender_without_key_response.json()["renderJobId"], history_ids)
        self.assertNotIn("downloadUrl", json.dumps(history_payload))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_stored_edit_render_uses_cloud_plan_and_render_eligible_source_clips(self) -> None:
        client = TestClient(create_app(self._settings()))
        edit_request = CreateEditJobRequest(
            videoId="video_canonical_render_123",
            analysisJobId="analysis_canonical_render_123",
            installId="install-123",
            sourceObjectKey=self._source_key(),
            preset="personal_highlight",
            targetDurationSeconds=15,
            aspectRatio="9:16",
            planTier="free",
            teamSelection={
                "mode": "team",
                "teamId": "team_dark",
                "label": "Dark jerseys",
                "colorLabel": "black",
                "confidenceThreshold": 0.85,
                "includeUncertain": True,
            },
            clips=[
                {
                    **_clip("dark_make", 0.0, "Made Shot", 0.94),
                    "teamAttribution": {
                        "teamId": "team_dark",
                        "label": "Dark jerseys",
                        "colorLabel": "black",
                        "confidence": 0.93,
                        "source": "quick_scan",
                        "evidenceFrameRefs": ["dark_setup", "dark_result"],
                        "evidenceRoleGroups": ["setup", "outcome"],
                    },
                },
                {
                    **_clip("uncertain_steal", 8.0, "Steal", 0.86),
                    "teamAttribution": {
                        "teamId": "team_light",
                        "label": "Light jerseys",
                        "colorLabel": "white",
                        "confidence": 0.64,
                        "source": "quick_scan",
                    },
                    "teamAttributionStatus": "uncertain",
                },
            ],
        )
        create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()
        plan_payload = client.get(
            f"/v1/edit-jobs/{create_payload['editJobId']}/plan",
            params={"installId": edit_request.installId},
        ).json()
        client_plan_override = dict(plan_payload["plan"])
        client_plan_override["aspectRatio"] = "16:9"

        render_response = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/render",
            json={
                "installId": edit_request.installId,
                "sourceObjectKey": "sources/client-override-should-not-render.mp4",
                "planTier": "pro",
                "editPlan": client_plan_override,
                "sourceClips": [edit_request.clips[1].model_dump(mode="json")],
                "idempotencyKey": "canonical-render-source-001",
                "forceNew": True,
            },
        )

        self.assertEqual(render_response.status_code, 200)
        status_response = client.get(
            f"/v1/render-jobs/{render_response.json()['renderJobId']}",
            params={"installId": edit_request.installId},
        )
        self.assertEqual(status_response.status_code, 200)
        render_payload = status_response.json()
        self.assertEqual(render_payload["status"], "rendered")
        self.assertEqual(render_payload["aspectRatio"], "9:16")
        self.assertEqual(render_payload["planTier"], "free")
        self.assertNotEqual(render_payload.get("failureReason"), "source_missing")
        self.assertEqual(render_payload["workReceipt"]["teamUncertainSelectedClipCount"], 0)
        self.assertEqual(render_payload["workReceipt"]["teamUncertainCandidateCount"], 0)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_raw_render_endpoint_uses_stored_cloud_plan_for_edit_jobs(self) -> None:
        client = TestClient(create_app(self._settings()))
        edit_request = CreateEditJobRequest(
            videoId="video_raw_canonical_render_123",
            analysisJobId="analysis_raw_canonical_render_123",
            installId="install-123",
            sourceObjectKey=self._source_key(),
            preset="personal_highlight",
            targetDurationSeconds=15,
            aspectRatio="9:16",
            planTier="free",
            teamSelection={
                "mode": "team",
                "teamId": "team_dark",
                "label": "Dark jerseys",
                "colorLabel": "black",
                "confidenceThreshold": 0.85,
                "includeUncertain": True,
            },
            clips=[
                {
                    **_clip("dark_make", 0.0, "Made Shot", 0.94),
                    "teamAttribution": {
                        "teamId": "team_dark",
                        "label": "Dark jerseys",
                        "colorLabel": "black",
                        "confidence": 0.93,
                        "source": "quick_scan",
                        "evidenceFrameRefs": ["dark_setup", "dark_result"],
                        "evidenceRoleGroups": ["setup", "outcome"],
                    },
                },
                {
                    **_clip("uncertain_steal", 8.0, "Steal", 0.86),
                    "teamAttribution": {
                        "teamId": "team_light",
                        "label": "Light jerseys",
                        "colorLabel": "white",
                        "confidence": 0.64,
                        "source": "quick_scan",
                    },
                    "teamAttributionStatus": "uncertain",
                },
            ],
        )
        create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()
        plan_payload = client.get(
            f"/v1/edit-jobs/{create_payload['editJobId']}/plan",
            params={"installId": edit_request.installId},
        ).json()
        client_plan_override = dict(plan_payload["plan"])
        client_plan_override["aspectRatio"] = "16:9"

        render_response = client.post(
            "/v1/render-jobs",
            json={
                "editJobId": create_payload["editJobId"],
                "installId": edit_request.installId,
                "sourceObjectKey": "sources/raw-client-override-should-not-render.mp4",
                "planTier": "pro",
                "editPlan": client_plan_override,
                "sourceClips": [edit_request.clips[1].model_dump(mode="json")],
                "idempotencyKey": "raw-canonical-render-source-001",
            },
        )

        self.assertEqual(render_response.status_code, 200)
        status_response = client.get(
            f"/v1/render-jobs/{render_response.json()['renderJobId']}",
            params={"installId": edit_request.installId},
        )
        self.assertEqual(status_response.status_code, 200)
        render_payload = status_response.json()
        self.assertEqual(render_payload["status"], "rendered")
        self.assertEqual(render_payload["aspectRatio"], "9:16")
        self.assertEqual(render_payload["planTier"], "free")
        self.assertNotEqual(render_payload.get("failureReason"), "source_missing")
        self.assertEqual(render_payload["workReceipt"]["teamUncertainSelectedClipCount"], 0)
        self.assertEqual(render_payload["workReceipt"]["teamUncertainCandidateCount"], 0)

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

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_queued_render_after_reload_restarts_from_stored_edit_job_payload(self) -> None:
        settings = self._settings()
        client = TestClient(create_app(settings))
        edit_request = self._edit_request()
        create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()
        render_job_id = "render_recover_queued_reload"
        idempotency_key = "idem-recover-queued-reload"
        self._persist_queued_render_job(
            settings,
            create_payload["editJobId"],
            edit_request.installId,
            edit_request.sourceObjectKey or "",
            idempotency_key,
            render_job_id=render_job_id,
        )

        reloaded_client = TestClient(create_app(settings))
        render_response = reloaded_client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/render",
            json={"installId": edit_request.installId, "idempotencyKey": idempotency_key},
        )
        status_response = reloaded_client.get(f"/v1/render-jobs/{render_job_id}", params={"installId": edit_request.installId})

        self.assertEqual(render_response.status_code, 200)
        self.assertEqual(render_response.json()["renderJobId"], render_job_id)
        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.json()
        self.assertEqual(status_payload["status"], "rendered")
        self.assertEqual(status_payload["renderJobId"], render_job_id)
        self.assertTrue(status_payload["outputObjectKey"].endswith("/final.mp4"))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe are required")
    def test_queued_revision_render_after_reload_restarts_from_persisted_revision_plan(self) -> None:
        settings = self._settings()
        client = TestClient(create_app(settings))
        edit_request = self._edit_request()
        create_payload = client.post("/v1/edit-jobs", json=edit_request.model_dump()).json()
        revision_payload = client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revise",
            json={"installId": edit_request.installId, "command": "switch_format_widescreen"},
        ).json()
        render_job_id = "render_recover_revision_reload"
        idempotency_key = f"{create_payload['editJobId']}:{revision_payload['revisionId']}:render"
        self._persist_queued_render_job(
            settings,
            create_payload["editJobId"],
            edit_request.installId,
            edit_request.sourceObjectKey or "",
            idempotency_key,
            render_job_id=render_job_id,
            revision_id=revision_payload["revisionId"],
            aspect_ratio="16:9",
        )

        reloaded_client = TestClient(create_app(settings))
        render_response = reloaded_client.post(
            f"/v1/edit-jobs/{create_payload['editJobId']}/revisions/{revision_payload['revisionId']}/render",
            json={"installId": edit_request.installId},
        )
        status_response = reloaded_client.get(f"/v1/render-jobs/{render_job_id}", params={"installId": edit_request.installId})

        self.assertEqual(render_response.status_code, 200)
        self.assertEqual(render_response.json()["renderJobId"], render_job_id)
        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.json()
        self.assertEqual(status_payload["status"], "rendered")
        self.assertEqual(status_payload["revisionId"], revision_payload["revisionId"])
        self.assertEqual(status_payload["aspectRatio"], "16:9")

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

    def test_download_url_requires_owner_rendered_output_and_unexpired_retention(self) -> None:
        settings = self._settings()
        store = DurableRenderStateStore(RenderStorage(settings))
        future = now_utc() + timedelta(days=1)
        expired = now_utc() - timedelta(seconds=1)
        store.save_job(
            StoredRenderJob(
                edit_job_id="edit_download_ready",
                render_job_id="render_download_ready",
                install_id="install-123",
                trace_id="trace_download_ready",
                status="rendered",
                aspect_ratio="9:16",
                created_at=now_utc() - timedelta(minutes=2),
                updated_at=now_utc() - timedelta(minutes=1),
                output_object_key="edits/edit_download_ready/render_jobs/render_download_ready/final.mp4",
                plan_version="edit-plan-v1",
                template_id="personal_highlight_v1",
                plan_tier="free",
                expires_at=future,
            )
        )
        store.save_job(
            StoredRenderJob(
                edit_job_id="edit_download_queued",
                render_job_id="render_download_queued",
                install_id="install-123",
                trace_id="trace_download_queued",
                status="queued",
                aspect_ratio="9:16",
                created_at=now_utc() - timedelta(minutes=2),
                updated_at=now_utc() - timedelta(minutes=1),
                output_object_key=None,
                plan_version="edit-plan-v1",
                template_id="personal_highlight_v1",
                plan_tier="free",
            )
        )
        store.save_job(
            StoredRenderJob(
                edit_job_id="edit_download_expired",
                render_job_id="render_download_expired",
                install_id="install-123",
                trace_id="trace_download_expired",
                status="rendered",
                aspect_ratio="9:16",
                created_at=now_utc() - timedelta(days=2),
                updated_at=now_utc() - timedelta(days=1),
                output_object_key="edits/edit_download_expired/render_jobs/render_download_expired/final.mp4",
                plan_version="edit-plan-v1",
                template_id="personal_highlight_v1",
                plan_tier="free",
                retention_metadata={
                    "expiresAt": expired.isoformat(),
                    "retentionClass": "free_final_render",
                    "deleteEligible": True,
                },
            )
        )
        client = TestClient(create_app(settings))

        owner_response = client.get("/v1/render-jobs/render_download_ready/download-url", params={"installId": "install-other"})
        ready_response = client.get("/v1/render-jobs/render_download_ready/download-url", params={"installId": "install-123"})
        queued_response = client.get("/v1/render-jobs/render_download_queued/download-url", params={"installId": "install-123"})
        expired_response = client.get("/v1/render-jobs/render_download_expired/download-url", params={"installId": "install-123"})

        self.assertEqual(owner_response.status_code, 403)
        self.assertEqual(owner_response.json()["errorCode"], "install_mismatch")
        self.assertEqual(ready_response.status_code, 200)
        self.assertEqual(ready_response.json()["renderJobId"], "render_download_ready")
        self.assertNotIn("leaseToken", json.dumps(ready_response.json()))
        self.assertEqual(queued_response.status_code, 409)
        self.assertEqual(queued_response.json()["errorCode"], "render_not_ready")
        self.assertEqual(expired_response.status_code, 410)
        self.assertEqual(expired_response.json()["errorCode"], "render_expired")


if __name__ == "__main__":
    unittest.main()
