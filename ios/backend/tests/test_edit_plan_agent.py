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
    MIN_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS,
    MIN_SHOT_CONTEXT_LEAD_IN_SECONDS,
    ReviseEditJobRequest,
    TEMPLATE_PACK_REGISTRY,
    apply_gpt_highlight_rerank,
    apply_edit_plan_patch,
    build_agent_editing_context,
    build_edit_context,
    derive_user_prompt_intent,
    build_revision_response,
    build_edit_job,
    build_edit_plan,
    clip_outcome_reliability_score,
    clip_context_quality_score,
    filter_clips_for_team_selection,
    get_template_pack_for_plan,
    is_defensive_event_like_clip,
    is_plan_quality_eligible_clip,
    native_shot_signals_for_clip,
    rank_clips,
    remove_duplicate_moments,
    repair_edit_plan,
    revise_edit_job,
    summarize_clip_pool,
    team_attribution_status,
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


def _defensive_result_evidence(**overrides) -> dict:
    payload = {
        "releaseToRimContinuity": "missing",
        "rimResultEvidence": "unclear",
        "outcomeConfidence": 0.86,
        "rimEntrySequence": "unclear",
        "ballApproachFrameRole": None,
        "rimEntryFrameRole": None,
        "ballBelowRimOrNetFrameRole": None,
        "rimEntrySequenceConfidence": 0.0,
        "reason": "Non-scoring defensive event with visible ball control change.",
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

    def test_user_prompt_is_sanitized_and_mapped_to_structured_edit_intent(self) -> None:
        request = CreateEditJobRequest(**_request_payload(userPrompt="  Make it more hype   and focus on defense.  "))

        context = build_edit_context(request)

        self.assertEqual(request.userPrompt, "Make it more hype and focus on defense.")
        self.assertIsNotNone(context.userIntent.userPromptIntent)
        intent = context.userIntent.userPromptIntent
        assert intent is not None
        self.assertIn("more_hype", intent.styleIntents)
        self.assertIn("defense_focus", intent.styleIntents)
        self.assertIn("defense", intent.focusAreas)
        self.assertEqual(intent.tone, "hype")
        self.assertEqual(intent.pacing, "fast")
        self.assertEqual(intent.effectIntensity, "high")
        self.assertNotIn("Make it more hype", context.model_dump_json())

    def test_user_prompt_intent_is_policy_gated_and_structured_only(self) -> None:
        free_intent = derive_user_prompt_intent("make it NBA recap 30s vertical mixtape", "free")
        pro_intent = derive_user_prompt_intent("make it NBA recap 30s vertical mixtape", "pro")

        assert free_intent is not None
        assert pro_intent is not None
        self.assertIn("nba_recap", free_intent.styleIntents)
        self.assertIn("vertical_mixtape", free_intent.styleIntents)
        self.assertEqual(free_intent.requestedDurationSeconds, 30)
        self.assertEqual(free_intent.requestedAspectRatio, "9:16")
        self.assertIsNone(free_intent.templateHint)
        self.assertEqual(pro_intent.templateHint, "nba_recap_pro_v1")

    def test_user_prompt_rejects_urls_and_storage_markers(self) -> None:
        unsafe_prompts = [
            "Use https://storage.example.test/render.mp4",
            "try X-Amz-Signature=abc123",
            "copy this downloadUrl into the plan",
            "read sourceObjectKey uploads/private/source.mp4",
            "use uploads/private/source.mp4",
            "run ffmpeg -i source.mp4",
            "use a shell command for the renderer",
        ]

        for prompt in unsafe_prompts:
            with self.subTest(prompt=prompt):
                with self.assertRaises(ValidationError):
                    CreateEditJobRequest(**_request_payload(userPrompt=prompt))

    def test_selected_team_filter_keeps_matching_and_uncertain_clips_for_review(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
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
                        **_clip("dark_bucket", 0.0, "Made Shot", 0.93),
                        "teamAttribution": {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.91,
                            "source": "quick_scan",
                        },
                    },
                    {
                        **_clip("light_bucket", 9.0, "Made Shot", 0.94),
                        "teamAttribution": {
                            "teamId": "team_light",
                            "label": "Light jerseys",
                            "colorLabel": "white",
                            "confidence": 0.92,
                            "source": "quick_scan",
                        },
                    },
                    {
                        **_clip("uncertain_bucket", 18.0, "Made Shot", 0.75),
                        "teamAttribution": {
                            "teamId": "team_light",
                            "label": "Light jerseys",
                            "colorLabel": "white",
                            "confidence": 0.61,
                            "source": "quick_scan",
                        },
                    },
                ],
            )
        )

        filtered = filter_clips_for_team_selection(request.clips, request.teamSelection)

        self.assertEqual([clip.id for clip in filtered], ["dark_bucket", "uncertain_bucket"])

    def test_selected_team_filter_rejects_conflicting_team_id_even_when_color_matches(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
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
                        **_clip("bad_color_alias", 0.0, "Made Shot", 0.93),
                        "teamAttribution": {
                            "teamId": "team_light",
                            "label": "Light jerseys",
                            "colorLabel": "black",
                            "confidence": 0.95,
                            "source": "quick_scan",
                        },
                    },
                    {
                        **_clip("missing_id_color_match", 9.0, "Made Shot", 0.91),
                        "teamAttribution": {
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.91,
                            "source": "quick_scan",
                        },
                    },
                ],
            )
        )

        filtered = filter_clips_for_team_selection(request.clips, request.teamSelection)

        self.assertEqual(team_attribution_status(request.clips[0], request.teamSelection), "opponent")
        self.assertEqual(team_attribution_status(request.clips[1], request.teamSelection), "matched")
        self.assertEqual([clip.id for clip in filtered], ["missing_id_color_match"])

    def test_selected_team_filter_matches_jersey_color_alias_team_ids(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
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
                        **_clip("black_alias_bucket", 0.0, "Made Shot", 0.93),
                        "teamAttribution": {
                            "teamId": "team_black",
                            "label": "Black jerseys",
                            "colorLabel": "black",
                            "confidence": 0.91,
                            "source": "quick_scan",
                        },
                    }
                ],
            )
        )

        filtered = filter_clips_for_team_selection(request.clips, request.teamSelection)

        self.assertEqual(team_attribution_status(request.clips[0], request.teamSelection), "matched")
        self.assertEqual([clip.id for clip in filtered], ["black_alias_bucket"])

    def test_selected_team_filter_rejects_exact_team_id_with_color_conflict(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
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
                        **_clip("bad_exact_id", 0.0, "Made Shot", 0.93),
                        "teamAttribution": {
                            "teamId": "team_dark",
                            "label": "Light jerseys",
                            "colorLabel": "white",
                            "confidence": 0.95,
                            "source": "quick_scan",
                        },
                    }
                ],
            )
        )

        filtered = filter_clips_for_team_selection(request.clips, request.teamSelection)

        self.assertEqual(team_attribution_status(request.clips[0], request.teamSelection), "opponent")
        self.assertEqual(filtered, [])

    def test_explicit_uncertain_team_status_survives_edit_context(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
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
                        **_clip("review_block", 0.0, "Blocked Shot", 0.9),
                        "teamAttribution": {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.91,
                            "source": "quick_scan",
                        },
                        "teamAttributionStatus": "uncertain",
                    },
                    {
                        **_clip("claimed_match", 9.0, "Made Shot", 0.88),
                        "teamAttributionStatus": "matched",
                    },
                ],
            )
        )

        self.assertEqual(team_attribution_status(request.clips[0], request.teamSelection), "uncertain")
        self.assertEqual(team_attribution_status(request.clips[1], request.teamSelection), "uncertain")
        context = build_agent_editing_context(
            request.templateId,
            summarize_clip_pool(request.clips),
            request.clips,
            teamSelection=request.teamSelection,
        )
        by_id = {clip["clipId"]: clip for clip in context["candidateClips"]}

        self.assertEqual(by_id["review_block"]["teamAttributionStatus"], "uncertain")
        self.assertEqual(by_id["claimed_match"]["teamAttributionStatus"], "uncertain")

    def test_all_teams_selection_does_not_filter_opponent_clips(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                teamSelection={"mode": "all"},
                clips=[
                    {
                        **_clip("dark_bucket", 0.0, "Made Shot", 0.93),
                        "teamAttribution": {"teamId": "team_dark", "colorLabel": "black", "confidence": 0.94},
                    },
                    {
                        **_clip("light_bucket", 9.0, "Made Shot", 0.94),
                        "teamAttribution": {"teamId": "team_light", "colorLabel": "white", "confidence": 0.94},
                    },
                ],
            )
        )

        filtered = filter_clips_for_team_selection(request.clips, request.teamSelection)

        self.assertEqual([clip.id for clip in filtered], ["dark_bucket", "light_bucket"])

    def test_selected_team_plan_keeps_defensive_blocks_and_steals(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                teamSelection={
                    "mode": "team",
                    "teamId": "team_dark",
                    "label": "Dark jerseys",
                    "colorLabel": "black",
                    "confidenceThreshold": 0.85,
                },
                clips=[
                    {
                        **_clip("dark_block", 0.0, "Blocked Shot", 0.92),
                        "teamAttribution": {"teamId": "team_dark", "colorLabel": "black", "confidence": 0.91},
                    },
                    {
                        **_clip("dark_steal", 9.0, "Steal", 0.89),
                        "teamAttribution": {"teamId": "team_dark", "colorLabel": "black", "confidence": 0.9},
                    },
                    {
                        **_clip("light_bucket", 18.0, "Made Shot", 0.97),
                        "teamAttribution": {"teamId": "team_light", "colorLabel": "white", "confidence": 0.96},
                    },
                ],
            )
        )

        plan = build_edit_plan(request, "edit_team_defense")

        planned_clip_ids = [clip.clipId for clip in plan.clips]
        self.assertIn("dark_block", planned_clip_ids)
        self.assertIn("dark_steal", planned_clip_ids)
        self.assertNotIn("light_bucket", planned_clip_ids)

    def test_agent_editing_context_includes_team_targeting_and_attribution(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
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
                        **_clip("dark_bucket", 0.0, "Made Shot", 0.93),
                        "teamAttribution": {"teamId": "team_dark", "colorLabel": "black", "confidence": 0.91},
                    }
                ],
            )
        )

        context = build_agent_editing_context(
            request.templateId,
            summarize_clip_pool(request.clips),
            request.clips,
            teamSelection=request.teamSelection,
        )

        self.assertEqual(context["teamTargeting"]["mode"], "team")
        self.assertEqual(context["teamTargeting"]["confidenceThreshold"], 0.85)
        self.assertTrue(context["teamTargeting"]["includeUncertain"])
        self.assertEqual(context["candidateClips"][0]["teamAttribution"]["teamId"], "team_dark")
        self.assertEqual(context["candidateClips"][0]["teamAttributionStatus"], "matched")

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
        self.assertEqual(context["candidateClips"][0]["clipId"], "c3")
        self.assertEqual(context["candidateClips"][0]["nativeShotSignals"]["outcome"], "made")
        serialized = str(context)
        self.assertNotIn("sourceObjectKey", serialized)
        self.assertNotIn("downloadUrl", serialized)
        self.assertNotIn("presigned", serialized.lower())

    def test_native_shot_signals_preserve_analysis_outcome_hint_without_relaxing_timing(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                clips=[
                    {
                        **_clip("late_block", 10.0, "Blocked Shot", 0.91),
                        "eventCenter": 10.2,
                        "nativeShotSignals": {
                            "isShotLike": True,
                            "leadInSeconds": 3.4,
                            "followThroughSeconds": 3.6,
                            "setupContextScore": 1.0,
                            "outcomeContextScore": 1.0,
                            "eventCenterQuality": 1.0,
                            "contextQualityScore": 1.0,
                            "timingWindowOk": True,
                            "outcome": "blocked",
                            "outcomeConfidence": 0.88,
                        },
                    }
                ],
            )
        )

        signals = native_shot_signals_for_clip(request.clips[0])

        self.assertEqual(signals.outcome, "blocked")
        self.assertEqual(signals.leadInSeconds, 0.2)
        self.assertFalse(signals.timingWindowOk)
        self.assertLess(signals.setupContextScore, 1.0)

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

    def test_ordinary_selector_rejects_shot_clip_without_setup_context(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[
                    {
                        **_clip("pre_basket", 0.0, "Made Shot", 0.99),
                        "eventCenter": 0.2,
                    },
                    _clip("complete_shot", 12.0, "Made Shot", 0.72),
                ],
            )
        )

        plan = build_edit_plan(request, "edit_ordinary_quality")

        self.assertNotIn("pre_basket", [clip.clipId for clip in plan.clips])
        self.assertIn("complete_shot", [clip.clipId for clip in plan.clips])

    def test_duplicate_group_prefers_complete_shot_context_over_higher_scored_pre_basket_window(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[
                    {
                        **_clip("late_duplicate", 8.0, "Made Shot", 0.99, "shot_1"),
                        "end": 10.2,
                        "eventCenter": 8.1,
                    },
                    _clip("complete_duplicate", 6.0, "Made Shot", 0.82, "shot_1"),
                ],
            )
        )

        plan = build_edit_plan(request, "edit_duplicate_quality")

        self.assertEqual([clip.clipId for clip in plan.clips], ["complete_duplicate"])

    def test_rank_clips_rewards_complete_shot_context_over_thin_late_window(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                clips=[
                    {
                        **_clip("thin_late_make", 8.0, "Made Shot", 0.99),
                        "end": 11.0,
                        "eventCenter": 8.92,
                    },
                    _clip("complete_make", 18.0, "Made Shot", 0.82),
                ],
            )
        )

        ranked = rank_clips(request.clips)

        self.assertEqual(ranked[0].id, "complete_make")
        self.assertGreater(clip_context_quality_score(ranked[0]), clip_context_quality_score(request.clips[0]))

    def test_rank_clips_prefers_supported_outcome_over_higher_scored_uncertain_shot(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                clips=[
                    {
                        **_clip("provider_overclaimed_uncertain_make", 6.0, "Made Shot", 0.99),
                        "nativeShotSignals": {
                            "isShotLike": True,
                            "leadInSeconds": 3.4,
                            "followThroughSeconds": 3.6,
                            "setupContextScore": 1.0,
                            "outcomeContextScore": 1.0,
                            "eventCenterQuality": 1.0,
                            "contextQualityScore": 1.0,
                            "timingWindowOk": True,
                            "outcome": "uncertain",
                            "outcomeConfidence": 0.0,
                        },
                    },
                    _clip("native_supported_make", 18.0, "Made Shot", 0.82),
                ],
            )
        )

        ranked = rank_clips(request.clips)

        self.assertEqual(ranked[0].id, "native_supported_make")
        self.assertGreater(
            clip_outcome_reliability_score(ranked[0]),
            clip_outcome_reliability_score(request.clips[0]),
        )

    def test_duplicate_cleanup_prefers_supported_outcome_over_overclaimed_duplicate(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                clips=[
                    {
                        **_clip("overclaimed_duplicate", 6.0, "Made Shot", 0.99, "same_play"),
                        "nativeShotSignals": {
                            "isShotLike": True,
                            "leadInSeconds": 3.4,
                            "followThroughSeconds": 3.6,
                            "setupContextScore": 1.0,
                            "outcomeContextScore": 1.0,
                            "eventCenterQuality": 1.0,
                            "contextQualityScore": 1.0,
                            "timingWindowOk": True,
                            "outcome": "uncertain",
                            "outcomeConfidence": 0.0,
                        },
                    },
                    _clip("supported_duplicate", 6.2, "Made Shot", 0.82, "same_play"),
                ],
            )
        )

        clips = remove_duplicate_moments(request.clips)

        self.assertEqual([clip.id for clip in clips], ["supported_duplicate"])

    def test_deterministic_plan_rejects_weak_generic_filler_when_gpt_falls_back(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                clips=[
                    {
                        **_clip("audio_only_filler", 0.0, "Highlight", 0.42),
                        "watchability": 0.2,
                        "motionScore": 0.22,
                        "audioPeak": 0.95,
                    }
                ],
            )
        )

        job = build_edit_job(request, "edit_weak_fallback")

        self.assertFalse(is_plan_quality_eligible_clip(request.clips[0]))
        self.assertEqual(job.status, "failed")
        self.assertIn("empty_clip_list", [error.code for error in job.validation_errors])

    def test_deterministic_plan_keeps_clear_non_shot_defense_clip(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                clips=[
                    {
                        **_clip("defense_stop", 4.0, "Defense", 0.66),
                        "watchability": 0.62,
                        "motionScore": 0.7,
                    }
                ],
            )
        )

        job = build_edit_job(request, "edit_defense_non_shot")

        self.assertTrue(is_plan_quality_eligible_clip(request.clips[0]))
        self.assertEqual(job.status, "plan_ready")
        self.assertEqual([clip.clipId for clip in job.plan.clips], ["defense_stop"])

    def test_deterministic_plan_does_not_caption_uncertain_shot_attempt_as_bucket(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("uncertain_jump_shot", 12.0, "Shot Attempt", 0.82)],
            )
        )

        plan = build_edit_plan(request, "edit_uncertain_shot_caption")

        self.assertEqual([clip.clipId for clip in plan.clips], ["uncertain_jump_shot"])
        self.assertEqual(plan.clips[0].caption, "GOOD LOOK")
        self.assertNotEqual(plan.clips[0].caption, "BUCKET")

    def test_native_shot_signals_do_not_treat_ambiguous_finish_labels_as_made(self) -> None:
        for label in ("Layup", "Tough Finish"):
            with self.subTest(label=label):
                request = CreateEditJobRequest(
                    **_request_payload(
                        targetDurationSeconds=15,
                        clips=[_clip("ambiguous_finish", 12.0, label, 0.86)],
                    )
                )

                signals = native_shot_signals_for_clip(request.clips[0])

                self.assertTrue(signals.isShotLike)
                self.assertTrue(signals.timingWindowOk)
                self.assertEqual(signals.outcome, "uncertain")
                self.assertEqual(signals.outcomeConfidence, 0.0)

    def test_deterministic_plan_trusts_native_uncertain_outcome_over_provider_made_label(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[
                    {
                        **_clip("provider_overclaimed_make", 12.0, "Made Shot", 0.92),
                        "nativeShotSignals": {
                            "isShotLike": True,
                            "leadInSeconds": 3.4,
                            "followThroughSeconds": 3.6,
                            "setupContextScore": 1.0,
                            "outcomeContextScore": 1.0,
                            "eventCenterQuality": 1.0,
                            "contextQualityScore": 1.0,
                            "timingWindowOk": True,
                            "outcome": "uncertain",
                            "outcomeConfidence": 0.0,
                        },
                    }
                ],
            )
        )

        signals = native_shot_signals_for_clip(request.clips[0])
        plan = build_edit_plan(request, "edit_native_uncertain_caption")

        self.assertEqual(signals.outcome, "uncertain")
        self.assertEqual([clip.clipId for clip in plan.clips], ["provider_overclaimed_make"])
        self.assertEqual(plan.clips[0].caption, "GOOD LOOK")
        self.assertNotEqual(plan.clips[0].caption, "BUCKET")

    def test_deterministic_plan_rejects_provider_shot_when_native_says_not_shot(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[
                    {
                        **_clip("provider_false_make", 12.0, "Made Shot", 0.96),
                        "nativeShotSignals": {
                            "isShotLike": True,
                            "leadInSeconds": 3.4,
                            "followThroughSeconds": 3.6,
                            "setupContextScore": 1.0,
                            "outcomeContextScore": 1.0,
                            "eventCenterQuality": 1.0,
                            "contextQualityScore": 1.0,
                            "timingWindowOk": True,
                            "outcome": "not_shot",
                            "outcomeConfidence": 1.0,
                        },
                    },
                    _clip("defense_stop", 24.0, "Defense", 0.74),
                ],
            )
        )

        self.assertFalse(is_plan_quality_eligible_clip(request.clips[0]))
        plan = build_edit_plan(request, "edit_native_not_shot_reject")

        self.assertEqual([clip.clipId for clip in plan.clips], ["defense_stop"])

    def test_deterministic_plan_captions_blocked_shot_as_lockdown_not_bucket(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("clean_block", 12.0, "Blocked Shot", 0.9)],
            )
        )

        plan = build_edit_plan(request, "edit_block_caption")

        self.assertEqual([clip.clipId for clip in plan.clips], ["clean_block"])
        self.assertEqual(plan.clips[0].caption, "LOCKDOWN")

    def test_build_edit_plan_enforces_template_minimum_clip_length(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[
                    {
                        **_clip("tiny_make", 0.0, "Made Shot", 0.99),
                        "end": 2.8,
                        "eventCenter": 1.4,
                    },
                    _clip("complete_make", 12.0, "Made Shot", 0.75),
                ],
            )
        )

        plan = build_edit_plan(request, "edit_template_min_clip")

        self.assertNotIn("tiny_make", [clip.clipId for clip in plan.clips])
        self.assertEqual([clip.clipId for clip in plan.clips], ["complete_make"])

    def test_build_edit_plan_keeps_shot_render_window_from_shifting_too_late(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[
                    {
                        **_clip("late_shift_make", 20.0, "Made Shot", 0.93),
                        "end": 27.0,
                        "eventCenter": 22.0,
                        "suggestedExtendAfterSeconds": 3.0,
                    },
                ],
            )
        )

        plan = build_edit_plan(request, "edit_shot_window_clamp")

        self.assertEqual([clip.clipId for clip in plan.clips], ["late_shift_make"])
        planned_clip = plan.clips[0]
        self.assertGreaterEqual(planned_clip.eventCenter - planned_clip.sourceStart, MIN_SHOT_CONTEXT_LEAD_IN_SECONDS)
        self.assertGreaterEqual(planned_clip.sourceEnd - planned_clip.eventCenter, MIN_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS)

    def test_validate_edit_plan_rejects_shot_render_window_without_setup_context(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("manual_late_make", 20.0, "Made Shot", 0.93)],
            )
        )
        plan = build_edit_plan(request, "edit_manual_late_window")
        clipped = plan.clips[0].model_copy(
            update={
                "sourceStart": round(plan.clips[0].eventCenter - 0.2, 3),
                "sourceEnd": round(plan.clips[0].eventCenter + 3.3, 3),
            }
        )
        invalid_plan = plan.model_copy(update={"clips": [clipped]})

        errors = validate_edit_plan(invalid_plan, request.clips, request.planTier)

        self.assertIn("shot_context_missing_setup", [error.code for error in errors])

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
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
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
                qualitySignals=_quality_signals(outcomeVisible=False, ballPathVisible=False, fullPlayContext=False),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
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
                qualitySignals=_quality_signals(outcomeVisible=False, ballPathVisible=False, fullPlayContext=False),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
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

    def test_gpt_highlight_rerank_keeps_selected_and_uncertain_team_steals(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
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
                        **_clip("dark_steal", 0.0, "Steal", 0.93),
                        "teamAttribution": {"teamId": "team_dark", "colorLabel": "black", "confidence": 0.93},
                    },
                    {
                        **_clip("uncertain_steal", 9.0, "Steal", 0.82),
                        "teamAttribution": {"teamId": "team_light", "colorLabel": "white", "confidence": 0.62},
                    },
                    {
                        **_clip("light_steal", 18.0, "Steal", 0.96),
                        "teamAttribution": {"teamId": "team_light", "colorLabel": "white", "confidence": 0.96},
                    },
                ],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId=clip.id,
                keep=True,
                highlightScore=0.9,
                watchabilityScore=0.84,
                basketballEvent="Steal",
                outcome="steal",
                caption="COOKIES",
                reason="Shows the defender taking possession cleanly.",
                qualitySignals=_quality_signals(
                    releaseVisible=False,
                    shotArcVisible=False,
                    rimResultVisible=False,
                    reason="Ball and defender control are visible through the steal.",
                ),
                shotResultEvidence=_defensive_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(
                    ballVisibleFrameRoles=["eventCenter", "finish"],
                    rimVisibleFrameRoles=[],
                    releaseFrameRole=None,
                    resultFrameRole=None,
                    ballEntersRimFrameRole=None,
                    trajectoryContinuity="partial",
                    reason="Ball control is visible before and after the steal.",
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(cropFocus="ball"),
            )
            for clip in request.clips
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 3, 12)

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual([clip.id for clip in reranked.clips], ["dark_steal", "uncertain_steal"])
        self.assertNotIn("light_steal", reranked.gptRerankSummary.keptClipIds)

    def test_gpt_highlight_rerank_keeps_mixed_steal_finish_as_defensive_outcome(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("steal_finish", 6.0, "Steal Finish", 0.93)],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="steal_finish",
                keep=True,
                highlightScore=0.9,
                watchabilityScore=0.86,
                basketballEvent="Steal",
                outcome="steal",
                caption="COOKIES",
                reason="Shows a clean steal before the finish attempt.",
                qualitySignals=_quality_signals(
                    releaseVisible=False,
                    shotArcVisible=False,
                    rimResultVisible=False,
                    reason="Defender takes the ball cleanly before the finish.",
                ),
                shotResultEvidence=_defensive_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(
                    ballVisibleFrameRoles=["challenge", "possessionChange", "finish"],
                    rimVisibleFrameRoles=[],
                    releaseFrameRole=None,
                    resultFrameRole="possessionChange",
                    ballEntersRimFrameRole=None,
                    trajectoryContinuity="partial",
                    reason="Sampled defensive frames show the challenge and possession change.",
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(cropFocus="ball"),
            )
        ]

        reranked = apply_gpt_highlight_rerank(
            request,
            decisions,
            "gpt-test",
            1,
            8,
            sampled_frame_roles_by_clip={"steal_finish": ["start", "eventCenter", "finish", "challenge", "possessionChange", "recovery"]},
        )

        self.assertTrue(is_defensive_event_like_clip(request.clips[0]))
        self.assertTrue(is_plan_quality_eligible_clip(request.clips[0]))
        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual([clip.id for clip in reranked.clips], ["steal_finish"])
        self.assertEqual(reranked.clips[0].label, "Steal (steal)")

    def test_gpt_defensive_decision_citing_unsampled_shot_role_is_rejected(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("steal_finish", 6.0, "Steal Finish", 0.93)],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="steal_finish",
                keep=True,
                highlightScore=0.9,
                watchabilityScore=0.86,
                basketballEvent="Steal",
                outcome="steal",
                caption="COOKIES",
                reason="Claims a release frame that was never sampled for this defensive clip.",
                qualitySignals=_quality_signals(
                    releaseVisible=False,
                    shotArcVisible=False,
                    rimResultVisible=False,
                    reason="Defender takes the ball cleanly before the finish.",
                ),
                shotResultEvidence=_defensive_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(
                    ballVisibleFrameRoles=["release", "possessionChange", "finish"],
                    rimVisibleFrameRoles=[],
                    releaseFrameRole="release",
                    resultFrameRole="possessionChange",
                    ballEntersRimFrameRole=None,
                    trajectoryContinuity="partial",
                    reason="The GPT response cites a role outside the sampled frame set.",
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(cropFocus="ball"),
            )
        ]

        reranked = apply_gpt_highlight_rerank(
            request,
            decisions,
            "gpt-test",
            1,
            8,
            sampled_frame_roles_by_clip={"steal_finish": ["start", "eventCenter", "finish", "challenge", "possessionChange", "recovery"]},
        )

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual(reranked.gptRerankSummary.keptClipIds, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("gpt_cited_unsampled_frame_role"), 1)

    def test_defensive_event_classifier_ignores_stop_and_pop_shot_label(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("stop_pop", 6.0, "Stop and Pop Jumper", 0.93)],
            )
        )

        self.assertFalse(is_defensive_event_like_clip(request.clips[0]))
        self.assertTrue(is_plan_quality_eligible_clip(request.clips[0]))

    def test_gpt_highlight_rerank_rejects_missed_shot_without_ball_path(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("miss_no_ball_path", 12.0, "Missed Shot", 0.9)],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="miss_no_ball_path",
                keep=True,
                highlightScore=0.86,
                watchabilityScore=0.82,
                basketballEvent="Missed shot",
                outcome="missed",
                caption="GOOD LOOK",
                reason="GPT claims a miss but cannot see the ball path.",
                qualitySignals=_quality_signals(ballPathVisible=False, reason="Release and rim are visible, but ball path is not."),
                shotResultEvidence=_shot_result_evidence(
                    rimResultEvidence="clear_miss",
                    outcomeConfidence=0.78,
                    rimEntrySequence="visible_miss",
                    rimEntrySequenceConfidence=0.76,
                ),
                shotTrackingEvidence=_shot_tracking_evidence(
                    ballVisibleFrameRoles=["eventCenter", "finish"],
                    rimVisibleFrameRoles=["finish"],
                    releaseFrameRole="eventCenter",
                    resultFrameRole="finish",
                    ballEntersRimFrameRole=None,
                    trajectoryContinuity="partial",
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 1, 5)

        self.assertEqual(reranked.clips, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts["missing_missed_shot_ball_path"], 1)

    def test_gpt_highlight_rerank_rejects_block_without_visible_ball_control(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("block_no_ball_path", 12.0, "Block", 0.9)],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="block_no_ball_path",
                keep=True,
                highlightScore=0.88,
                watchabilityScore=0.82,
                basketballEvent="Block",
                outcome="blocked",
                caption="LOCKDOWN",
                reason="GPT claims a block but cannot see the ball path.",
                qualitySignals=_quality_signals(
                    releaseVisible=False,
                    shotArcVisible=False,
                    ballPathVisible=False,
                    reason="The challenge is visible, but the ball path is not.",
                ),
                shotResultEvidence=_shot_result_evidence(
                    releaseToRimContinuity="partial",
                    rimResultEvidence="blocked",
                    outcomeConfidence=0.78,
                    rimEntrySequence="blocked",
                    ballApproachFrameRole=None,
                    rimEntryFrameRole=None,
                    ballBelowRimOrNetFrameRole=None,
                    rimEntrySequenceConfidence=0.0,
                ),
                shotTrackingEvidence=_shot_tracking_evidence(
                    ballVisibleFrameRoles=["eventCenter", "finish"],
                    rimVisibleFrameRoles=[],
                    releaseFrameRole=None,
                    resultFrameRole="finish",
                    ballEntersRimFrameRole=None,
                    trajectoryContinuity="partial",
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(cropFocus="ball"),
            )
        ]

        reranked = apply_gpt_highlight_rerank(
            request,
            decisions,
            "gpt-test",
            1,
            5,
            sampled_frame_roles_by_clip={"block_no_ball_path": ["start", "eventCenter", "finish"]},
        )

        self.assertEqual(reranked.clips, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts["missing_block_ball_control"], 1)

    def test_gpt_highlight_decision_requires_quality_signals(self) -> None:
        with self.assertRaises(ValidationError):
            GPTHighlightClipDecision(
                clipId="missing_signals",
                keep=True,
                highlightScore=0.95,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="This must not default visual quality to true.",
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )

    def test_gpt_highlight_decision_rejects_partial_quality_signals(self) -> None:
        with self.assertRaises(ValidationError):
            GPTHighlightClipDecision(
                clipId="partial_signals",
                keep=True,
                highlightScore=0.95,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="Partial visual evidence must not default unknown checks to true.",
                qualitySignals={"outcomeVisible": True, "reason": "Only the outcome was claimed."},
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )

    def test_gpt_highlight_rerank_rejects_kept_clips_without_full_shot_context(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=30,
                clips=[
                    {
                        **_clip("pre_basket", 0.0, "Made Shot", 0.99),
                        "eventCenter": 0.2,
                    },
                    _clip("unclear_outcome", 12.0, "Made Shot", 0.97),
                    _clip("missing_release", 18.0, "Made Shot", 0.96),
                    _clip("missing_shot_arc", 19.5, "Made Shot", 0.955),
                    _clip("missing_rim_result", 21.0, "Made Shot", 0.95),
                    _clip("weak_made_evidence", 22.5, "Made Shot", 0.94),
                    _clip("weak_tracking_evidence", 23.2, "Made Shot", 0.93),
                    _clip("complete_make", 24.0, "Made Shot", 0.8),
                ],
            )
        )
        base_signal = {
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
        decisions = [
            GPTHighlightClipDecision(
                clipId="pre_basket",
                keep=True,
                highlightScore=0.99,
                watchabilityScore=0.95,
                basketballEvent="Made Shot",
                outcome="made",
                caption="TOO LATE",
                reason="The basket is visible, but the setup is missing.",
                qualitySignals={**base_signal, "setupVisible": False, "fullPlayContext": False, "reason": "Clip starts right before the make."},
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
            GPTHighlightClipDecision(
                clipId="unclear_outcome",
                keep=True,
                highlightScore=0.97,
                watchabilityScore=0.92,
                basketballEvent="Made Shot",
                outcome="made",
                caption="UNCLEAR",
                reason="The release is visible but the result is not.",
                qualitySignals={**base_signal, "outcomeVisible": False, "ballPathVisible": False, "reason": "No clear rim or make/miss frame."},
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
            GPTHighlightClipDecision(
                clipId="missing_release",
                keep=True,
                highlightScore=0.96,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="NO RELEASE",
                reason="The aftermath is visible, but the shooting release is not.",
                qualitySignals={**base_signal, "releaseVisible": False, "reason": "No visible shot release."},
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
            GPTHighlightClipDecision(
                clipId="missing_rim_result",
                keep=True,
                highlightScore=0.95,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="NO RESULT",
                reason="The ball path is visible, but the rim result is not.",
                qualitySignals={**base_signal, "rimResultVisible": False, "reason": "No visible rim result."},
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
            GPTHighlightClipDecision(
                clipId="missing_shot_arc",
                keep=True,
                highlightScore=0.955,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="NO ARC",
                reason="The release and rim are visible, but the ball flight is not.",
                qualitySignals={**base_signal, "shotArcVisible": False, "reason": "No visible ball arc."},
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
            GPTHighlightClipDecision(
                clipId="weak_made_evidence",
                keep=True,
                highlightScore=0.94,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="NO PROOF",
                reason="GPT saw a late rim frame but could not prove the ball went in.",
                qualitySignals=base_signal,
                shotResultEvidence=_shot_result_evidence(
                    rimResultEvidence="unclear",
                    outcomeConfidence=0.58,
                    reason="No clear net reaction or ball entering the rim.",
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
            GPTHighlightClipDecision(
                clipId="weak_tracking_evidence",
                keep=True,
                highlightScore=0.93,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="NO ENTRY",
                reason="GPT claims a make but cannot anchor ball entry to a sampled frame.",
                qualitySignals=base_signal,
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(
                    ballEntersRimFrameRole=None,
                    netOrRimReactionVisible=False,
                    reason="Release and rim are visible, but no sampled frame proves ball entry.",
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
            GPTHighlightClipDecision(
                clipId="complete_make",
                keep=True,
                highlightScore=0.82,
                watchabilityScore=0.86,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="Shows setup, release, ball path, and made outcome.",
                qualitySignals=base_signal,
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 3, 15)
        plan = build_edit_plan(reranked, "edit_quality_context")

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual(reranked.gptRerankSummary.keptClipIds, ["complete_make"])
        self.assertIn("pre_basket", reranked.gptRerankSummary.rejectedClipIds)
        self.assertIn("unclear_outcome", reranked.gptRerankSummary.rejectedClipIds)
        self.assertIn("missing_release", reranked.gptRerankSummary.rejectedClipIds)
        self.assertIn("missing_shot_arc", reranked.gptRerankSummary.rejectedClipIds)
        self.assertIn("missing_rim_result", reranked.gptRerankSummary.rejectedClipIds)
        self.assertIn("weak_made_evidence", reranked.gptRerankSummary.rejectedClipIds)
        self.assertIn("weak_tracking_evidence", reranked.gptRerankSummary.rejectedClipIds)
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("missing_shot_release"), 1)
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("missing_shot_arc"), 1)
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("missing_rim_result"), 1)
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("made_outcome_not_visible"), 1)
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("missing_made_shot_entry_frame"), 1)
        self.assertEqual([clip.clipId for clip in plan.clips], ["complete_make"])

    def test_gpt_highlight_rerank_rejects_tracking_roles_that_were_not_sampled(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("claimed_make", 24.0, "Made Shot", 0.9)],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="claimed_make",
                keep=True,
                highlightScore=0.92,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="Claims a clean make.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(
                    ballVisibleFrameRoles=["release", "shotArcEarly", "rim"],
                    rimVisibleFrameRoles=["rim", "postOutcome"],
                    releaseFrameRole="release",
                    resultFrameRole="rim",
                    ballEntersRimFrameRole="rim",
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
        ]

        reranked = apply_gpt_highlight_rerank(
            request,
            decisions,
            "gpt-test",
            1,
            3,
            sampled_frame_roles_by_clip={"claimed_make": ["start", "eventCenter", "finish"]},
        )

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual(reranked.gptRerankSummary.keptClipIds, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertIn("claimed_make", reranked.gptRerankSummary.rejectedClipIds)
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("gpt_cited_unsampled_frame_role"), 1)

    def test_gpt_highlight_rerank_rejects_made_shot_without_rim_entry_sequence(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("late_rim_claim", 24.0, "Made Shot", 0.9)],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="late_rim_claim",
                keep=True,
                highlightScore=0.92,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="Claims a made shot from a late rim view.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(
                    rimEntrySequence="unclear",
                    ballApproachFrameRole=None,
                    rimEntryFrameRole=None,
                    ballBelowRimOrNetFrameRole=None,
                    rimEntrySequenceConfidence=0.2,
                    reason="The sampled frames do not show the ball entering or passing through the rim.",
                ),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 1, 3)

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual(reranked.gptRerankSummary.keptClipIds, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("made_rim_entry_sequence_not_visible"), 1)

    def test_gpt_highlight_rerank_rejects_generic_entry_when_rim_path_was_sampled(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("generic_entry_claim", 24.0, "Made Shot", 0.9)],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="generic_entry_claim",
                keep=True,
                highlightScore=0.92,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="Claims a made shot but uses a generic finish frame for entry.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(
                    ballApproachFrameRole="rimApproach",
                    rimEntryFrameRole="finish",
                    ballBelowRimOrNetFrameRole="belowRim",
                ),
                shotTrackingEvidence=_shot_tracking_evidence(
                    ballVisibleFrameRoles=["release", "shotArcLate", "rimApproach", "rimEntry", "belowRim"],
                    rimVisibleFrameRoles=["rimEntry", "belowRim"],
                    releaseFrameRole="release",
                    resultFrameRole="rimEntry",
                    ballEntersRimFrameRole="rimEntry",
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
        ]

        reranked = apply_gpt_highlight_rerank(
            request,
            decisions,
            "gpt-test",
            1,
            10,
            sampled_frame_roles_by_clip={
                "generic_entry_claim": [
                    "start",
                    "preEvent",
                    "release",
                    "eventCenter",
                    "shotArcEarly",
                    "shotArcLate",
                    "rimApproach",
                    "rimEntry",
                    "belowRim",
                    "finish",
                ]
            },
        )

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual(reranked.gptRerankSummary.keptClipIds, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("gpt_ignored_sampled_rim_entry_frame"), 1)

    def test_gpt_highlight_rerank_rejects_generic_ball_entry_tracking_when_rim_path_was_sampled(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("generic_ball_entry_claim", 24.0, "Made Shot", 0.9)],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="generic_ball_entry_claim",
                keep=True,
                highlightScore=0.92,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="Claims a made shot but uses a generic finish frame for ball entry tracking.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(
                    ballApproachFrameRole="rimApproach",
                    rimEntryFrameRole="rimEntry",
                    ballBelowRimOrNetFrameRole="belowRim",
                ),
                shotTrackingEvidence=_shot_tracking_evidence(
                    ballVisibleFrameRoles=["release", "shotArcLate", "rimApproach", "rimEntry", "belowRim"],
                    rimVisibleFrameRoles=["rimEntry", "belowRim"],
                    releaseFrameRole="release",
                    resultFrameRole="rimEntry",
                    ballEntersRimFrameRole="finish",
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
        ]

        reranked = apply_gpt_highlight_rerank(
            request,
            decisions,
            "gpt-test",
            1,
            10,
            sampled_frame_roles_by_clip={
                "generic_ball_entry_claim": [
                    "start",
                    "preEvent",
                    "release",
                    "eventCenter",
                    "shotArcEarly",
                    "shotArcLate",
                    "rimApproach",
                    "rimEntry",
                    "belowRim",
                    "finish",
                ]
            },
        )

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual(reranked.gptRerankSummary.keptClipIds, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("gpt_ignored_sampled_ball_entry_frame"), 1)

    def test_gpt_highlight_rerank_rejects_made_shot_without_followthrough_frame_even_with_net_reaction(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("reaction_only_make", 24.0, "Made Shot", 0.9)],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="reaction_only_make",
                keep=True,
                highlightScore=0.92,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="Claims a made shot from a reaction without a cited follow-through frame.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(
                    ballApproachFrameRole="release",
                    rimEntryFrameRole="finish",
                    ballBelowRimOrNetFrameRole=None,
                ),
                shotTrackingEvidence=_shot_tracking_evidence(
                    ballVisibleFrameRoles=["release", "eventCenter", "finish"],
                    rimVisibleFrameRoles=["finish"],
                    releaseFrameRole="release",
                    resultFrameRole="finish",
                    ballEntersRimFrameRole="finish",
                    netOrRimReactionVisible=True,
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 1, 3)

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual(reranked.gptRerankSummary.keptClipIds, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("missing_rim_entry_followthrough_frame"), 1)

    def test_gpt_highlight_rerank_rejects_generic_tracking_when_rich_roles_were_sampled(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("generic_claim", 24.0, "Made Shot", 0.9)],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="generic_claim",
                keep=True,
                highlightScore=0.92,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="Claims a clean make using only generic base frames.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
        ]

        reranked = apply_gpt_highlight_rerank(
            request,
            decisions,
            "gpt-test",
            1,
            10,
            sampled_frame_roles_by_clip={
                "generic_claim": [
                    "start",
                    "preEvent",
                    "release",
                    "shotArcEarly",
                    "eventCenter",
                    "outcome",
                    "shotArcLate",
                    "rim",
                    "postOutcome",
                    "finish",
                ]
            },
        )

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual(reranked.gptRerankSummary.keptClipIds, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts.get("gpt_ignored_sampled_release_frame"), 1)

    def test_gpt_highlight_rerank_all_rejected_does_not_fallback_to_original_clips(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[
                    _clip("boring_walkup", 0.0, "Highlight", 0.62),
                    _clip("late_basket", 12.0, "Made Shot", 0.95),
                ],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="boring_walkup",
                keep=False,
                rejectReason="boring",
                highlightScore=0.18,
                watchabilityScore=0.34,
                basketballEvent="Dead ball",
                outcome="not_basketball",
                caption="SKIP",
                reason="No clear basketball outcome.",
                qualitySignals=_quality_signals(
                    eventVisible=False,
                    outcomeVisible=False,
                    ballPathVisible=False,
                    playerControlVisible=False,
                    fullPlayContext=False,
                ),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
            GPTHighlightClipDecision(
                clipId="late_basket",
                keep=False,
                rejectReason="missing_setup_context",
                highlightScore=0.42,
                watchabilityScore=0.72,
                basketballEvent="Made Shot",
                outcome="made",
                caption="SKIP",
                reason="The clip starts too late and misses the setup.",
                qualitySignals=_quality_signals(setupVisible=False, fullPlayContext=False),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 2, 6)
        job = build_edit_job(reranked, "edit_all_gpt_rejected")

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(reranked.gptRerankSummary.keptClipIds, [])
        self.assertEqual(set(reranked.gptRerankSummary.rejectedClipIds), {"boring_walkup", "late_basket"})
        self.assertEqual(reranked.clips, [])
        self.assertEqual(job.status, "failed")
        self.assertIn("empty_clip_list", [error.code for error in job.validation_errors])

    def test_gpt_highlight_rerank_rejects_generic_audio_only_scoring_claim(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[
                    {
                        **_clip("audio_only_hype", 0.0, "Highlight", 0.9),
                        "watchability": 0.51,
                        "motionScore": 0.35,
                        "audioPeak": 1.0,
                    }
                ],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="audio_only_hype",
                keep=True,
                highlightScore=0.95,
                watchabilityScore=0.9,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="GPT overclaimed a made shot from a generic audio-heavy moment.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 1, 8)
        job = build_edit_job(reranked, "edit_generic_audio_claim")

        self.assertEqual(reranked.clips, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertIn("audio_only_hype", reranked.gptRerankSummary.rejectedClipIds)
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts["gpt_outcome_unsupported_by_source"], 1)
        self.assertEqual(job.status, "failed")

    def test_gpt_highlight_rerank_rejects_outcome_conflicting_with_native_shot_signal(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[
                    {
                        **_clip("native_missed_jump_shot", 12.0, "Jump Shot", 0.92),
                        "nativeShotSignals": {
                            "isShotLike": True,
                            "leadInSeconds": 3.4,
                            "followThroughSeconds": 3.6,
                            "setupContextScore": 1.0,
                            "outcomeContextScore": 1.0,
                            "eventCenterQuality": 1.0,
                            "contextQualityScore": 1.0,
                            "timingWindowOk": True,
                            "outcome": "missed",
                            "outcomeConfidence": 0.86,
                        },
                    }
                ],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="native_missed_jump_shot",
                keep=True,
                highlightScore=0.95,
                watchabilityScore=0.91,
                basketballEvent="Jump shot",
                outcome="made",
                caption="BUCKET",
                reason="GPT claims the shot went in even though native signals saw a miss.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 1, 8)

        self.assertEqual(reranked.clips, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertIn("native_missed_jump_shot", reranked.gptRerankSummary.rejectedClipIds)
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts["gpt_outcome_conflicts_with_native_signal"], 1)

    def test_gpt_highlight_rerank_rejects_forbidden_render_command_content(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[_clip("unsafe_caption_make", 12.0, "Made Shot", 0.92)],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="unsafe_caption_make",
                keep=True,
                highlightScore=0.95,
                watchabilityScore=0.91,
                basketballEvent="Made Shot",
                outcome="made",
                caption="ffmpeg -i source.mp4",
                reason="Clear clip, but this text includes a renderer command.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 1, 8)

        self.assertEqual(reranked.clips, [])
        self.assertEqual(reranked.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertIn("unsafe_caption_make", reranked.gptRerankSummary.rejectedClipIds)
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts["forbidden_gpt_output_content"], 1)

    def test_gpt_highlight_rerank_duplicate_cleanup_prefers_complete_context(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[
                    {
                        **_clip("barely_contextual_make", 8.0, "Made Shot", 0.99, "shot_dup"),
                        "end": 11.3,
                        "eventCenter": 9.0,
                    },
                    _clip("complete_context_make", 18.0, "Made Shot", 0.82, "shot_dup"),
                ],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="barely_contextual_make",
                keep=True,
                highlightScore=0.99,
                watchabilityScore=0.96,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="The make is visible, but the window is thin.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
            GPTHighlightClipDecision(
                clipId="complete_context_make",
                keep=True,
                highlightScore=0.84,
                watchabilityScore=0.88,
                basketballEvent="Made Shot",
                outcome="made",
                caption="COMPLETE",
                reason="Shows setup, action, and outcome clearly.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 2, 16)
        plan = build_edit_plan(reranked, "edit_gpt_duplicate_context")

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual(reranked.gptRerankSummary.keptClipIds, ["complete_context_make"])
        self.assertGreater(
            clip_context_quality_score(next(clip for clip in request.clips if clip.id == "complete_context_make")),
            clip_context_quality_score(next(clip for clip in request.clips if clip.id == "barely_contextual_make")),
        )
        self.assertEqual([clip.clipId for clip in plan.clips], ["complete_context_make"])

    def test_gpt_highlight_rerank_dedupes_overlapping_kept_clips_without_duplicate_group(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
                targetDurationSeconds=15,
                clips=[
                    {
                        **_clip("same_make_a", 8.0, "Made Shot", 0.88),
                        "end": 15.0,
                        "eventCenter": 11.0,
                        "duplicateGroup": None,
                    },
                    {
                        **_clip("same_make_b", 8.4, "Made Shot", 0.9),
                        "end": 15.4,
                        "eventCenter": 11.2,
                        "duplicateGroup": None,
                    },
                ],
            )
        )
        decisions = [
            GPTHighlightClipDecision(
                clipId="same_make_a",
                keep=True,
                highlightScore=0.86,
                watchabilityScore=0.88,
                basketballEvent="Made Shot",
                outcome="made",
                caption="BUCKET",
                reason="Same scoring moment from a slightly weaker window.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
            GPTHighlightClipDecision(
                clipId="same_make_b",
                keep=True,
                highlightScore=0.94,
                watchabilityScore=0.91,
                basketballEvent="Made Shot",
                outcome="made",
                caption="CLEAN",
                reason="Same scoring moment with better watchability.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            ),
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 2, 16)
        plan = build_edit_plan(reranked, "edit_overlap_dedupe")

        self.assertEqual(len(reranked.clips), 1)
        self.assertEqual(len(plan.clips), 1)
        self.assertEqual(set(reranked.gptRerankSummary.keptClipIds + reranked.gptRerankSummary.rejectedClipIds), {"same_make_a", "same_make_b"})
        self.assertEqual(reranked.gptRerankSummary.rejectedReasonCounts["duplicate_moment"], 1)

    def test_gpt_highlight_rerank_drops_unjudged_candidates(self) -> None:
        request = CreateEditJobRequest(**_request_payload(targetDurationSeconds=30))
        decisions = [
            GPTHighlightClipDecision(
                clipId="c3",
                keep=True,
                highlightScore=0.98,
                watchabilityScore=0.95,
                basketballEvent="Dunk",
                outcome="made",
                caption="BIG FINISH",
                reason="Clear finish and outcome.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
        ]

        reranked = apply_gpt_highlight_rerank(request, decisions, "gpt-test", 5, 15)

        self.assertEqual(reranked.gptRerankSummary.status, "applied")
        self.assertEqual([clip.id for clip in reranked.clips], ["c3"])
        self.assertEqual(reranked.gptRerankSummary.keptClipIds, ["c3"])
        self.assertIn("c1", reranked.gptRerankSummary.rejectedClipIds)
        self.assertIn("c5", reranked.gptRerankSummary.rejectedClipIds)

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
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
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

    def test_gpt_story_order_opener_and_closer_survive_short_reel_cutoff(self) -> None:
        request = CreateEditJobRequest(**_request_payload(targetDurationSeconds=15))
        decisions = [
            GPTHighlightClipDecision(
                clipId=clip_id,
                keep=True,
                highlightScore=score,
                watchabilityScore=score,
                basketballEvent=label,
                outcome="made",
                caption=caption,
                reason="Clear event from an existing candidate clip.",
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
                suggestedEdit=GPTHighlightSuggestedEdit(),
            )
            for clip_id, score, label, caption in [
                ("c1", 0.99, "Fast Break", "RUNOUT"),
                ("c3", 0.98, "Dunk", "BIG FINISH"),
                ("c4", 0.74, "Made Shot", "CLOSER"),
            ]
        ]

        reranked = apply_gpt_highlight_rerank(
            request,
            decisions,
            "gpt-test",
            3,
            9,
            story_order=["c1", "c3", "c4"],
        )
        plan = build_edit_plan(reranked, "edit_gpt_story_order_short")

        self.assertEqual(reranked.gptRerankSummary.storyOrderClipIds, ["c1", "c3", "c4"])
        self.assertEqual([clip.clipId for clip in plan.clips], ["c1", "c4"])
        self.assertNotIn("c3", [clip.clipId for clip in plan.clips])

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
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
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
                slowMotionMoments=[GPTPlanEditSlowMotionMoment(clipId="c3", center=13.2, speed=0.55)],
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
        slow_motion = next(effect for effect in c3.effects if effect.type == "slow_motion")
        self.assertAlmostEqual(((slow_motion.sourceStart or 0.0) + (slow_motion.sourceEnd or 0.0)) / 2.0, 13.2, delta=0.05)

    def test_gpt_plan_edit_ignores_invalid_clip_references(self) -> None:
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
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
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
                orderedClipIds=["c999"],
                pacing="fast",
                captions=[GPTPlanEditCaption(clipId="c999", caption="INVALID", captionMoment=3.2)],
                slowMotionMoments=[GPTPlanEditSlowMotionMoment(clipId="c999", center=15.1, speed=0.55)],
                summary="References a clip outside the validated candidate pool.",
            ),
        )
        plan = build_edit_plan(reranked, "edit_invalid_gpt_plan_edit")

        self.assertFalse(reranked.gptRerankSummary.planEditApplied)
        self.assertEqual(reranked.gptRerankSummary.storyOrderClipIds, [])
        self.assertNotIn("c999", [clip.clipId for clip in plan.clips])
        self.assertEqual(next(clip for clip in plan.clips if clip.clipId == "c1").caption, "RUNOUT")

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
                qualitySignals=_quality_signals(),
                shotResultEvidence=_shot_result_evidence(),
                shotTrackingEvidence=_shot_tracking_evidence(),
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

    def test_gpt_revision_patch_rejects_opponent_clip_for_selected_team(self) -> None:
        request = CreateEditJobRequest(
            **_request_payload(
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
                        **_clip("dark_make", 0.0, "Made Shot", 0.95),
                        "teamAttribution": {"teamId": "team_dark", "colorLabel": "black", "confidence": 0.94},
                    },
                    {
                        **_clip("light_make", 8.0, "Made Shot", 0.98),
                        "teamAttribution": {"teamId": "team_light", "colorLabel": "white", "confidence": 0.96},
                    },
                ],
            )
        )
        job = build_edit_job(request, "edit_selected_team_patch_guard")
        opponent = next(clip for clip in job.request.clips if clip.id == "light_make")
        opponent_plan_clip = job.plan.clips[0].model_dump()
        opponent_plan_clip.update(
            {
                "clipId": opponent.id,
                "sourceStart": opponent.start,
                "sourceEnd": opponent.end,
                "eventCenter": opponent.eventCenter,
                "label": opponent.label,
                "caption": "BUCKET",
                "timelineStart": 0.0,
                "timelineEnd": opponent.duration,
            }
        )
        patch = EditPlanPatch(
            baseEditPlanId=job.edit_job_id,
            revisionIntent="make_more_hype",
            summary="GPT tried to add a confident opponent clip.",
            operations=[EditPlanPatchOperation(op="replace", path="/clips", value=[opponent_plan_clip])],
        )

        revised, response = build_revision_response(
            job,
            ReviseEditJobRequest(command="make_more_hype"),
            "rev_selected_team_patch_guard",
            proposed_patch=patch,
        )

        self.assertEqual(revised.status, "failed")
        self.assertEqual(response.status, "revision_failed")
        self.assertTrue(any(error.code == "unknown_clip" for error in response.validationResult.errors))

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
