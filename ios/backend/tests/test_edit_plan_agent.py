from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.editing import (
    AGENT_TEMPLATE_COOKBOOK_REGISTRY,
    CreateEditJobRequest,
    EditPlanPatch,
    EditPlanPatchOperation,
    EditPlan,
    GPTHighlightClipDecision,
    GPTPlanEdit,
    GPTPlanEditCaption,
    GPTPlanEditSlowMotionMoment,
    GPTHighlightSuggestedEdit,
    ReviseEditJobRequest,
    TEMPLATE_PACK_REGISTRY,
    apply_gpt_highlight_rerank,
    apply_edit_plan_patch,
    build_agent_editing_context,
    build_edit_context,
    build_revision_response,
    build_edit_job,
    build_edit_plan,
    get_template_pack_for_plan,
    remove_duplicate_moments,
    repair_edit_plan,
    revise_edit_job,
    validate_agent_template_cookbook_registry,
    validate_edit_plan,
    validate_edit_plan_patch,
    validate_template_pack,
    validate_template_registry,
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

    def test_personal_highlight_plan_has_free_watermark_and_outro(self) -> None:
        request = CreateEditJobRequest(**_request_payload())

        job = build_edit_job(request, "edit_test")

        self.assertEqual(job.status, "plan_ready")
        self.assertEqual(job.plan.renderMode, "cloud_ffmpeg")
        self.assertTrue(job.plan.watermark.enabled)
        self.assertTrue(job.plan.outro.enabled)
        self.assertEqual(job.plan.aspectRatio, "9:16")
        self.assertEqual(job.plan.templateId, "personal_highlight_v1")
        self.assertEqual(job.plan.captionStyle, "bold_hype")
        self.assertEqual(job.validation_errors, [])

    def test_user_prompt_is_sanitized_and_included_in_edit_context(self) -> None:
        request = CreateEditJobRequest(**_request_payload(userPrompt="  Make it more hype   and focus on defense.  "))

        context = build_edit_context(request)

        self.assertEqual(request.userPrompt, "Make it more hype and focus on defense.")
        self.assertEqual(context.userIntent.userPrompt, "Make it more hype and focus on defense.")

    def test_user_prompt_rejects_urls_and_storage_markers(self) -> None:
        unsafe_prompts = [
            "Use https://storage.example.test/render.mp4",
            "try X-Amz-Signature=abc123",
            "copy this downloadUrl into the plan",
            "read sourceObjectKey uploads/private/source.mp4",
            "use uploads/private/source.mp4",
        ]

        for prompt in unsafe_prompts:
            with self.subTest(prompt=prompt):
                with self.assertRaises(ValidationError):
                    CreateEditJobRequest(**_request_payload(userPrompt=prompt))

    def test_template_registry_has_base_and_pro_packs(self) -> None:
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
        self.assertEqual(TEMPLATE_PACK_REGISTRY["full_game_highlight_v1"].captionStyle.styleId, "clean_scorebug")
        self.assertTrue(TEMPLATE_PACK_REGISTRY["cinematic_mixtape_pro_v1"].premiumOnly)

    def test_agent_template_cookbook_registry_matches_template_packs(self) -> None:
        validation = validate_agent_template_cookbook_registry()

        self.assertEqual(set(validation.keys()), set(TEMPLATE_PACK_REGISTRY.keys()))
        self.assertEqual(set(AGENT_TEMPLATE_COOKBOOK_REGISTRY.keys()), set(TEMPLATE_PACK_REGISTRY.keys()))
        self.assertTrue(all(not errors for errors in validation.values()))
        self.assertFalse(AGENT_TEMPLATE_COOKBOOK_REGISTRY["recruiting_reel_pro_v1"].enabledForFree)
        self.assertTrue(AGENT_TEMPLATE_COOKBOOK_REGISTRY["personal_highlight_v1"].enabledForFree)
        self.assertIn("clear individual skill", AGENT_TEMPLATE_COOKBOOK_REGISTRY["recruiting_reel_pro_v1"].selectionRules.prefer)

    def test_pro_agent_cookbooks_preserve_director_briefs(self) -> None:
        recruiting = AGENT_TEMPLATE_COOKBOOK_REGISTRY["recruiting_reel_pro_v1"]
        cinematic = AGENT_TEMPLATE_COOKBOOK_REGISTRY["cinematic_mixtape_pro_v1"]
        nba = AGENT_TEMPLATE_COOKBOOK_REGISTRY["nba_recap_pro_v1"]
        team = AGENT_TEMPLATE_COOKBOOK_REGISTRY["team_highlight_pro_v1"]

        self.assertEqual(
            (recruiting.enabledForFree, recruiting.enabledForPro, recruiting.enabledForInternal),
            (False, True, True),
        )
        self.assertIn("clear individual skill", recruiting.selectionRules.prefer)
        self.assertIn("unclear team chaos", recruiting.rejectionRules.reject)
        self.assertIn("TOUGH TAKE", recruiting.captionRules.examples)
        self.assertEqual(recruiting.orderingRules.strategy, "best_first_skill_showcase")

        self.assertIn("top 5 to 8 clips", cinematic.selectionRules.prioritize)
        self.assertEqual(cinematic.orderingRules.opener, "one_of_top_2_clips")
        self.assertEqual(cinematic.orderingRules.closer, "high_energy_finish")
        self.assertTrue(cinematic.effectRules.punchZoom)
        self.assertTrue(cinematic.effectRules.speedRamp)

        self.assertEqual(nba.targetDurationRules.defaultAspectRatio, "16:9")
        self.assertIn("game narrative", nba.selectionRules.prioritize)
        self.assertIn("meme captions", nba.rejectionRules.reject)
        self.assertTrue(nba.effectRules.lowerThird)
        self.assertGreater(nba.audioRules.gameAudioVolume, nba.audioRules.musicVolume)

        self.assertIn("team variety", team.selectionRules.prioritize)
        self.assertIn("offense and defense balance", team.selectionRules.prioritize)
        self.assertIn("one-player domination unless requested", team.rejectionRules.reject)
        self.assertEqual(team.cropRules.defaultFocus, "team")

    def test_default_template_lookup_does_not_promote_free_presets_to_pro_templates(self) -> None:
        self.assertEqual(get_template_pack_for_plan("personal_highlight").templateId, "personal_highlight_v1")
        self.assertEqual(get_template_pack_for_plan("full_game_highlight").templateId, "full_game_highlight_v1")
        self.assertEqual(get_template_pack_for_plan("coach_review").templateId, "coach_review_v1")

    def test_agent_editing_context_is_compact_and_template_specific(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                templateId="cinematic_mixtape_pro_v1",
                targetDurationSeconds=45,
                planTier="internal",
            )
        )

        context = build_agent_editing_context(
            request.templateId,
            {"clipCount": len(request.clips), "totalCandidateDuration": 35.0, "topLabels": ["Dunk"], "duplicateGroups": 1},
            request.clips,
        )

        self.assertEqual(context["templateId"], "cinematic_mixtape_pro_v1")
        self.assertEqual(context["rendererTemplateDefaults"]["captionStyle"], "cinematic_hype")
        self.assertEqual(context["templateCookbookRules"]["orderingRules"]["opener"], "one_of_top_2_clips")
        self.assertIn("COLD.", context["templateCookbookRules"]["captionRules"]["examples"])
        self.assertEqual(context["candidateClips"][0]["clipId"], "c1")
        serialized = str(context)
        self.assertNotIn("sourceObjectKey", serialized)
        self.assertNotIn("downloadUrl", serialized)
        self.assertNotIn("presigned", serialized.lower())

    def test_free_plan_rejects_premium_template_pack(self) -> None:
        request = CreateEditJobRequest(**_request_payload(templateId="cinematic_mixtape_pro_v1", targetDurationSeconds=30))

        job = build_edit_job(request, "edit_free_premium")

        self.assertEqual(job.status, "failed")
        self.assertTrue(any(error.code == "premium_template_required" for error in job.validation_errors))

    def test_internal_plan_can_build_all_pro_templates_as_clean_exports(self) -> None:
        cases = [
            ("personal_highlight", "recruiting_reel_pro_v1", 60, "9:16", "recruiting_clean_hype"),
            ("personal_highlight", "cinematic_mixtape_pro_v1", 45, "9:16", "cinematic_hype"),
            ("full_game_highlight", "nba_recap_pro_v1", 120, "16:9", "broadcast_scorebug"),
            ("full_game_highlight", "team_highlight_pro_v1", 120, "16:9", "team_clean"),
        ]

        for preset, template_id, duration, aspect_ratio, caption_style in cases:
            with self.subTest(template_id=template_id):
                request = CreateEditJobRequest(
                    **_request_payload(
                        preset=preset,
                        templateId=template_id,
                        targetDurationSeconds=duration,
                        aspectRatio=aspect_ratio,
                        planTier="internal",
                    )
                )

                job = build_edit_job(request, f"edit_{template_id}")

                self.assertEqual(job.status, "plan_ready")
                self.assertEqual(job.validation_errors, [])
                self.assertEqual(job.plan.templateId, template_id)
                self.assertEqual(job.plan.captionStyle, caption_style)
                self.assertEqual(job.plan.aspectRatio, aspect_ratio)
                self.assertFalse(job.plan.watermark.enabled)
                self.assertFalse(job.plan.outro.enabled)

    def test_more_hype_revision_preserves_premium_template(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                preset="personal_highlight",
                templateId="cinematic_mixtape_pro_v1",
                targetDurationSeconds=45,
                planTier="internal",
            )
        )
        job = build_edit_job(request, "edit_premium_revision")

        revised, response = build_revision_response(job, ReviseEditJobRequest(command="make_more_hype"), "rev_premium")

        self.assertEqual(revised.plan.templateId, "cinematic_mixtape_pro_v1")
        self.assertEqual(response.revisedPlan.templateId, "cinematic_mixtape_pro_v1")
        self.assertTrue(response.validationResult.valid)

    def test_duplicate_groups_keep_only_best_clip(self) -> None:
        request = CreateEditJobRequest(**_request_payload())

        clips = remove_duplicate_moments(request.clips)

        grouped = [clip for clip in clips if clip.duplicateGroup == "g1"]
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0].id, "c1")

    def test_gpt_highlight_rerank_uses_existing_clip_ids_only(self) -> None:
        request = CreateEditJobRequest(**_request_payload())
        decisions = [
            GPTHighlightClipDecision(
                clipId="c3",
                keep=True,
                highlightScore=0.98,
                watchabilityScore=0.96,
                basketballEvent="Dunk",
                outcome="made",
                caption="BIG FINISH",
                reason="Clear finish and strong watchability.",
                suggestedEdit=GPTHighlightSuggestedEdit(
                    slowMotion=True,
                    slowMotionCenter=15.4,
                    captionMoment=15.4,
                    cropFocus="rim",
                    extendBeforeSeconds=0.4,
                    extendAfterSeconds=0.6,
                ),
            ),
            GPTHighlightClipDecision(
                clipId="c999",
                keep=True,
                highlightScore=1.0,
                watchabilityScore=1.0,
                basketballEvent="Invented clip",
                outcome="unclear",
                caption="NOPE",
                reason="Should be ignored because it is not in the candidate pool.",
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
            GPTHighlightClipDecision(
                clipId="c1",
                keep=False,
                highlightScore=0.1,
                watchabilityScore=0.2,
                basketballEvent="Boring duplicate",
                outcome="unclear",
                caption="SKIP",
                reason="Duplicate was less clear.",
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 3, 9)
        plan = build_edit_plan(reranked, "edit_gpt_reranked")

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertIn("c3", reranked.gptRerankSummary.keptClipIds)
        self.assertIn("c1", reranked.gptRerankSummary.rejectedClipIds)
        self.assertNotIn("c999", [clip.id for clip in reranked.clips])
        self.assertEqual(plan.clips[0].clipId, "c3")
        self.assertEqual(plan.clips[0].caption, "BIG FINISH")
        self.assertEqual(plan.clips[0].captionMoment, 15.4)
        self.assertEqual(plan.clips[0].cropMode, "rim")
        self.assertTrue(any(effect.type == "slow_motion" for effect in plan.clips[0].effects))

    def test_gpt_highlight_rerank_applies_story_order_to_edit_plan(self) -> None:
        request = CreateEditJobRequest(**_request_payload(targetDurationSeconds=45))
        decisions = [
            GPTHighlightClipDecision(
                clipId=clip_id,
                keep=True,
                highlightScore=score,
                watchabilityScore=0.9,
                basketballEvent=label,
                outcome="made",
                caption=caption,
                reason="Clear event from an existing candidate clip.",
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
            for clip_id, score, label, caption in [
                ("c1", 0.88, "Fast Break", "RUNOUT"),
                ("c3", 0.96, "Dunk", "BIG FINISH"),
                ("c4", 0.92, "Made Shot", "BUCKET"),
            ]
        ]

        reranked = apply_gpt_highlight_rerank(
            request,
            decisions,
            "gpt-test",
            4,
            12,
            story_order=["c4", "c3", "c999", "c1"],
        )
        plan = build_edit_plan(reranked, "edit_gpt_story_order")

        self.assertEqual(reranked.gptRerankSummary.storyOrderClipIds, ["c4", "c3", "c1"])
        self.assertEqual([clip.gptStoryOrderIndex for clip in reranked.clips if clip.id in {"c1", "c3", "c4"}], [0, 1, 2])
        self.assertEqual([clip.clipId for clip in plan.clips[:3]], ["c4", "c3", "c1"])
        self.assertNotIn("c999", [clip.clipId for clip in plan.clips])

    def test_gpt_plan_edit_controls_order_captions_and_slow_motion(self) -> None:
        request = CreateEditJobRequest(**_request_payload(targetDurationSeconds=45))
        decisions = [
            GPTHighlightClipDecision(
                clipId=clip_id,
                keep=True,
                highlightScore=score,
                watchabilityScore=0.9,
                basketballEvent=label,
                outcome="made",
                caption=caption,
                reason="Clear event from an existing candidate clip.",
                storyRole=story_role,
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
            for clip_id, score, label, caption, story_role in [
                ("c1", 0.88, "Fast Break", "RUNOUT", "opener"),
                ("c3", 0.96, "Dunk", "BIG FINISH", "peak"),
                ("c4", 0.92, "Made Shot", "BUCKET", "closer"),
            ]
        ]

        reranked = apply_gpt_highlight_rerank(
            request,
            decisions,
            "gpt-test",
            3,
            12,
            plan_edit=GPTPlanEdit(
                orderedClipIds=["c4", "c1", "c3"],
                pacing="fast",
                captions=[GPTPlanEditCaption(clipId="c1", caption="RUNOUT!", captionMoment=3.2)],
                slowMotionMoments=[GPTPlanEditSlowMotionMoment(clipId="c3", center=15.1, speed=0.55)],
                summary="Open with the make, then speed, then peak.",
            ),
        )
        plan = build_edit_plan(reranked, "edit_gpt_plan_edit")

        self.assertTrue(reranked.gptRerankSummary.planEditApplied)
        self.assertEqual(reranked.gptRerankSummary.storyOrderClipIds, ["c4", "c1", "c3"])
        self.assertEqual([clip.clipId for clip in plan.clips[:3]], ["c4", "c1", "c3"])
        c1 = next(clip for clip in plan.clips if clip.clipId == "c1")
        c3 = next(clip for clip in plan.clips if clip.clipId == "c3")
        self.assertEqual(c1.caption, "RUNOUT!")
        self.assertEqual(c1.captionMoment, 3.2)
        self.assertTrue(any(effect.type == "slow_motion" for effect in c3.effects))

    def test_gpt_highlight_rerank_clamps_hints_and_biases_source_window(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=12,
                clips=[
                    {
                        "id": "c_window",
                        "start": 0.0,
                        "end": 20.0,
                        "eventCenter": 10.0,
                        "label": "Made Shot",
                        "confidence": 0.8,
                        "excitement": 0.8,
                        "watchability": 0.8,
                        "motionScore": 0.8,
                        "audioPeak": 0.4,
                        "combinedScore": 0.8,
                    }
                ],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="c_window",
                keep=True,
                highlightScore=0.95,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="CLEAN HIT",
                reason="Clear make with usable framing.",
                suggestedEdit=GPTHighlightSuggestedEdit(
                    slowMotion=True,
                    slowMotionCenter=999.0,
                    captionMoment=999.0,
                    cropFocus="shooter",
                    extendBeforeSeconds=3.0,
                    extendAfterSeconds=0.0,
                ),
            )
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 1, 3)
        plan = build_edit_plan(reranked, "edit_gpt_window")

        clip = reranked.clips[0]
        self.assertEqual(clip.suggestedSlowMotionCenter, 20.0)
        self.assertEqual(clip.suggestedCaptionMoment, 20.0)
        self.assertEqual(clip.suggestedExtendBeforeSeconds, 3.0)
        self.assertEqual(plan.clips[0].captionMoment, plan.clips[0].sourceEnd)
        self.assertEqual(plan.clips[0].cropMode, "shooter")
        self.assertLess(plan.clips[0].sourceStart, 6.5)
        self.assertEqual(plan.clips[0].sourceStart, 5.0)

    def test_full_game_highlight_uses_widescreen_and_chronological_selection(self) -> None:
        request = CreateEditJobRequest(**_request_payload(preset="full_game_highlight", targetDurationSeconds=60))

        plan = build_edit_plan(request, "edit_full_game")

        self.assertEqual(plan.aspectRatio, "16:9")
        self.assertEqual(plan.templateId, "full_game_highlight_v1")
        self.assertEqual(plan.audio.gameAudioVolume, 0.62)
        starts = [clip.sourceStart for clip in plan.clips]
        self.assertEqual(starts, sorted(starts))

    def test_invalid_template_rejects_missing_asset(self) -> None:
        template = TEMPLATE_PACK_REGISTRY["personal_highlight_v1"].model_copy(
            update={
                "assets": [
                    asset.model_copy(update={"path": "services/editing/templates/missing/nope.json"})
                    if asset.assetId == "personal_highlight_outro_free_v1"
                    else asset
                    for asset in TEMPLATE_PACK_REGISTRY["personal_highlight_v1"].assets
                ]
            }
        )

        errors = validate_template_pack(template)

        self.assertTrue(any(error.code == "template_asset_missing" for error in errors))

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

    def test_revision_patch_rejects_unsafe_path(self) -> None:
        request = CreateEditJobRequest(**_request_payload())
        job = build_edit_job(request, "edit_patch_safety")
        patch = EditPlanPatch(
            baseEditPlanId=job.edit_job_id,
            revisionIntent="make_more_hype",
            summary="Unsafe path should be rejected.",
            operations=[EditPlanPatchOperation(op="replace", path="/renderMode", value="local_avfoundation")],
        )

        with self.assertRaises(ValueError):
            apply_edit_plan_patch(job.plan, patch)

    def test_gpt_patch_validator_rejects_ffmpeg_commands(self) -> None:
        request = CreateEditJobRequest(**_request_payload())
        job = build_edit_job(request, "edit_patch_no_ffmpeg")
        patch = EditPlanPatch(
            baseEditPlanId=job.edit_job_id,
            revisionIntent="make_more_hype",
            summary="ffmpeg -i source.mp4 output.mp4",
            operations=[EditPlanPatchOperation(op="replace", path="/theme", value="classic")],
        )

        patched, errors = validate_edit_plan_patch(job.plan, patch, job.request.clips, job.request.planTier)

        self.assertIsNone(patched)
        self.assertTrue(any(error.code == "invalid_gpt_patch" for error in errors))

    def test_gpt_patch_validator_rejects_local_render_urls_and_storage_keys(self) -> None:
        request = CreateEditJobRequest(**_request_payload())
        job = build_edit_job(request, "edit_patch_no_storage_leaks")
        unsafe_values = [
            "render locally with AVFoundation",
            "bash -lc render.sh",
            "python -c 'render locally'",
            "os.system('curl https://example.test')",
            "https://storage.example.test/presigned/render.mp4",
            "uploads/private/source.mp4",
            "X-Amz-Signature=abc123",
            "downloadUrl",
            {"caption": "use renderLogObjectKey renders/private/log.json"},
            {"downloadUrl": "redacted"},
        ]

        for index, unsafe_value in enumerate(unsafe_values):
            with self.subTest(index=index):
                patch = EditPlanPatch(
                    baseEditPlanId=job.edit_job_id,
                    revisionIntent="make_more_hype",
                    summary="Unsafe GPT patch should be rejected.",
                    operations=[EditPlanPatchOperation(op="replace", path="/theme", value=unsafe_value)],
                )

                patched, errors = validate_edit_plan_patch(job.plan, patch, job.request.clips, job.request.planTier)

                self.assertIsNone(patched)
                self.assertTrue(any(error.code == "invalid_gpt_patch" for error in errors))

    def test_revision_commands_are_deterministic_patches(self) -> None:
        request = CreateEditJobRequest(**_request_payload())
        job = build_edit_job(request, "edit_revision_patch")

        revised, response = build_revision_response(
            job,
            ReviseEditJobRequest(command="make_more_hype"),
            "rev_test",
        )

        self.assertEqual(response.patch.version, "edit-plan-patch-v1")
        self.assertEqual(response.command, "make_more_hype")
        self.assertTrue(response.validationResult.valid)
        self.assertEqual(revised.plan.aspectRatio, "9:16")
        self.assertEqual(revised.plan.templateId, "personal_highlight_v1")
        self.assertTrue(any(operation.path == "/clips" for operation in response.patch.operations))
        self.assertTrue(any(effect.type == "slow_motion" for clip in revised.plan.clips for effect in clip.effects))

    def test_remove_weak_clips_drops_lowest_scoring_plan_clip(self) -> None:
        request = CreateEditJobRequest(**_request_payload())
        job = build_edit_job(request, "edit_remove_weak")
        original_clip_count = len(job.plan.clips)

        revised = revise_edit_job(job, ReviseEditJobRequest(command="remove_weak_clips"))

        self.assertLess(len(revised.plan.clips), original_clip_count)
        self.assertNotIn("c5", [clip.clipId for clip in revised.plan.clips])

    def test_use_original_audio_removes_music(self) -> None:
        request = CreateEditJobRequest(**_request_payload())
        job = build_edit_job(request, "edit_original_audio")

        revised = revise_edit_job(job, ReviseEditJobRequest(command="use_original_audio"))

        self.assertEqual(revised.plan.audio.musicTrackId, "none")
        self.assertEqual(revised.plan.audio.musicVolume, 0.0)
        self.assertEqual(revised.plan.audio.gameAudioVolume, 1.0)

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
