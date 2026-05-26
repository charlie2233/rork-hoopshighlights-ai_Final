from pathlib import Path
import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "services" / "editing"))
sys.path.insert(0, str(REPO_ROOT / "ios" / "backend"))

from app.editing import CreateEditJobRequest, ReviseEditJobRequest, build_edit_job
import editing_app.gpt_reranker as gpt_reranker
from editing_app.gpt_reranker import (
    GPTHighlightRerankerSettings,
    SampledFrame,
    _build_openai_payload,
    _build_revision_patch_payload,
    expand_shot_candidate_windows_for_source_context,
    request_gpt_edit_plan_patch,
)


def _clip(clip_id: str, start: float, score: float) -> dict:
    return {
        "id": clip_id,
        "start": start,
        "end": start + 6.0,
        "eventCenter": start + 3.0,
        "label": "Made Shot",
        "confidence": score,
        "excitement": score,
        "watchability": score,
        "motionScore": score,
        "audioPeak": score / 2.0,
        "combinedScore": score,
    }


def _request(plan_tier: str = "free", clip_count: int = 10) -> CreateEditJobRequest:
    return CreateEditJobRequest(
        videoId="video_123",
        analysisJobId="analysis_123",
        installId="install-123",
        sourceObjectKey="uploads/source.mp4",
        preset="personal_highlight",
        targetDurationSeconds=30,
        planTier=plan_tier,
        clips=[_clip(f"c{index}", float(index * 7), 1.0 - (index * 0.01)) for index in range(clip_count)],
    )


def _quality_signals(**overrides) -> dict:
    payload = {
        "setupVisible": True,
        "eventVisible": True,
        "outcomeVisible": True,
        "ballPathVisible": True,
        "playerControlVisible": True,
        "cleanCamera": True,
        "fullPlayContext": True,
        "reason": "Complete play context.",
    }
    payload.update(overrides)
    return payload


class GPTHighlightRerankerTests(unittest.TestCase):
    def test_payload_is_strict_structured_output_and_not_stored(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        request = _request()
        frame = SampledFrame(
            clip_id="c0",
            role="start",
            time_seconds=0.0,
            data_url="data:image/jpeg;base64,ZmFrZQ==",
        )
        rogue_frame = SampledFrame(
            clip_id="c999",
            role="start",
            time_seconds=999.0,
            data_url="data:image/jpeg;base64,cm9ndWU=",
        )

        payload = _build_openai_payload(request, request.clips[:1], [frame, rogue_frame], settings)
        user_content = payload["input"][0]["content"]
        compact_input = json.loads(user_content[0]["text"])
        compact_clip = compact_input["clips"][0]
        agent_cookbook = compact_input["agentTemplateCookbook"]
        image_items = [item for item in user_content if item["type"] == "input_image"]

        self.assertIs(payload["store"], False)
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(payload["text"]["format"]["schema"]["required"], ["decisions", "storyOrder", "planEdit", "summary"])
        self.assertEqual(
            set(compact_clip),
            {
                "clipId",
                "start",
                "end",
                "duration",
                "eventCenter",
                "existingLabel",
                "motionScore",
                "audioPeak",
                "confidence",
                "watchabilityScore",
                "duplicateGroup",
                "templateId",
                "planTier",
                "qualityHints",
                "nativeShotSignals",
                "sampledKeyframes",
            },
        )
        self.assertEqual(compact_clip["sampledKeyframes"], [{"role": "start", "time": 0.0}])
        self.assertEqual(compact_clip["nativeShotSignals"]["outcome"], "made")
        self.assertTrue(compact_clip["nativeShotSignals"]["timingWindowOk"])
        self.assertEqual(compact_clip["qualityHints"]["nativeShotSignals"]["outcome"], "made")
        self.assertEqual(agent_cookbook["templateId"], "personal_highlight_v1")
        self.assertIn("templateCookbookRules", agent_cookbook)
        self.assertEqual(agent_cookbook["templateCookbookRules"]["captionRules"]["tone"], "hype")
        self.assertEqual(agent_cookbook["candidateClips"][0]["clipId"], "c0")
        self.assertEqual(agent_cookbook["candidateClips"][0]["nativeShotSignals"]["contextQualityScore"], 1.0)
        self.assertEqual(len(image_items), 1)
        self.assertTrue(image_items[0]["image_url"].startswith("data:image/jpeg;base64,"))
        self.assertNotIn("c999", json.dumps(payload))
        self.assertNotIn("sourceObjectKey", str(payload))
        self.assertNotIn("uploads/source.mp4", str(payload))
        self.assertNotIn("https://", str(payload))

    def test_payload_requires_shot_quality_signals_and_context_judgment(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        request = _request()
        frames = [
            SampledFrame(clip_id="c0", role="start", time_seconds=0.0, data_url="data:image/jpeg;base64,ZmFrZQ=="),
            SampledFrame(clip_id="c0", role="eventCenter", time_seconds=3.0, data_url="data:image/jpeg;base64,ZmFrZQ=="),
            SampledFrame(clip_id="c0", role="finish", time_seconds=5.95, data_url="data:image/jpeg;base64,ZmFrZQ=="),
        ]

        payload = _build_openai_payload(request, request.clips[:1], frames, settings)
        compact_input = json.loads(payload["input"][0]["content"][0]["text"])
        compact_clip = compact_input["clips"][0]
        shot_rules = compact_input["shotTrackerRules"]
        decision_schema = payload["text"]["format"]["schema"]["properties"]["decisions"]["items"]

        self.assertEqual(compact_clip["qualityHints"]["leadInSeconds"], 3.0)
        self.assertEqual(compact_clip["qualityHints"]["followThroughSeconds"], 3.0)
        self.assertTrue(compact_clip["qualityHints"]["timingWindowOk"])
        self.assertEqual(compact_clip["nativeShotSignals"]["setupContextScore"], 1.0)
        self.assertEqual(compact_clip["nativeShotSignals"]["outcomeContextScore"], 1.0)
        self.assertEqual(shot_rules["requiredShotContextKeyframes"], ["outcome", "preEvent", "release", "rim"])
        self.assertIn("qualitySignals", decision_schema["properties"])
        self.assertIn("qualitySignals", decision_schema["required"])
        self.assertIn("shot-tracker", payload["instructions"])
        self.assertIn("reject clips that start right before the basket", payload["instructions"])

    def test_quality_filter_excludes_tiny_and_late_shot_windows_before_gpt(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_quality_filter",
            analysisJobId="analysis_quality_filter",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {**_clip("late_make", 0.0, 0.99), "end": 6.0, "eventCenter": 0.9},
                {**_clip("tiny_make", 8.0, 0.98), "end": 10.5, "eventCenter": 9.4},
                _clip("complete_make", 18.0, 0.82),
            ],
        )

        sampled = gpt_reranker._quality_filtered_sampled_clips(request.clips, max_clips=3)
        hints = [gpt_reranker._candidate_quality_hints(clip) for clip in request.clips]

        self.assertEqual([clip.id for clip in sampled], ["complete_make"])
        self.assertFalse(hints[0]["timingWindowOk"])
        self.assertFalse(hints[1]["timingWindowOk"])
        self.assertTrue(hints[2]["timingWindowOk"])
        self.assertGreaterEqual(hints[2]["minRecommendedDurationSeconds"], 3.0)

    def test_quality_filter_excludes_weak_generic_non_shot_candidates_before_gpt(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_weak_non_shot_filter",
            analysisJobId="analysis_weak_non_shot_filter",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {
                    **_clip("audio_only_filler", 0.0, 0.42),
                    "label": "Highlight",
                    "watchability": 0.2,
                    "motionScore": 0.22,
                    "audioPeak": 0.95,
                },
                {
                    **_clip("clear_defense", 10.0, 0.66),
                    "label": "Defense",
                    "watchability": 0.62,
                    "motionScore": 0.7,
                },
            ],
        )

        sampled = gpt_reranker._quality_filtered_sampled_clips(request.clips, max_clips=2)
        hints = [gpt_reranker._candidate_quality_hints(clip) for clip in request.clips]

        self.assertEqual([clip.id for clip in sampled], ["clear_defense"])
        self.assertTrue(hints[0]["timingWindowOk"])
        self.assertTrue(hints[1]["timingWindowOk"])

    def test_source_context_expansion_salvages_thin_shot_windows_before_gpt(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_expand_context",
            analysisJobId="analysis_expand_context",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {
                    **_clip("thin_make", 8.8, 0.96),
                    "end": 10.5,
                    "eventCenter": 9.1,
                    "duplicateGroup": "shot_1",
                },
                {
                    **_clip("non_shot_context", 20.0, 0.8),
                    "label": "Defense",
                    "end": 21.8,
                    "eventCenter": 20.9,
                },
            ],
        )

        expanded = expand_shot_candidate_windows_for_source_context(request, source_duration_seconds=60.0)
        thin_make = expanded.clips[0]
        non_shot = expanded.clips[1]
        hints = gpt_reranker._candidate_quality_hints(thin_make)
        sampled = gpt_reranker._quality_filtered_sampled_clips(expanded.clips, max_clips=2)
        plan = build_edit_job(expanded, "edit_expanded_context").plan

        self.assertLess(thin_make.start, 8.8)
        self.assertGreater(thin_make.end, 10.5)
        self.assertGreaterEqual(thin_make.eventCenter - thin_make.start, 2.0)
        self.assertGreaterEqual(thin_make.end - thin_make.eventCenter, 1.25)
        self.assertTrue(hints["timingWindowOk"])
        self.assertEqual(non_shot.start, 20.0)
        self.assertEqual(non_shot.end, 21.8)
        self.assertIn("thin_make", [clip.id for clip in sampled])
        self.assertEqual(plan.clips[0].clipId, "thin_make")
        self.assertLessEqual(plan.clips[0].sourceStart, 8.8)

    def test_payload_resolves_preset_default_template_for_agent_cookbook(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        request = _request().model_copy(update={"preset": "full_game_highlight", "templateId": None, "targetDurationSeconds": 60})
        frame = SampledFrame(
            clip_id="c0",
            role="start",
            time_seconds=0.0,
            data_url="data:image/jpeg;base64,ZmFrZQ==",
        )

        payload = _build_openai_payload(request, request.clips[:1], [frame], settings)
        compact_input = json.loads(payload["input"][0]["content"][0]["text"])

        self.assertEqual(compact_input["templateContext"]["templateId"], "full_game_highlight_v1")
        self.assertEqual(compact_input["agentTemplateCookbook"]["templateId"], "full_game_highlight_v1")
        self.assertEqual(compact_input["clips"][0]["templateId"], "full_game_highlight_v1")

    def test_payload_includes_structured_user_edit_intent_without_raw_prompt(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        request = _request().model_copy(update={"userPrompt": "Make it more hype and focus on defense."})
        frame = SampledFrame(
            clip_id="c0",
            role="start",
            time_seconds=0.0,
            data_url="data:image/jpeg;base64,ZmFrZQ==",
        )

        payload = _build_openai_payload(request, request.clips[:1], [frame], settings)
        compact_input = json.loads(payload["input"][0]["content"][0]["text"])
        intent = compact_input["userEditIntent"]

        self.assertIn("more_hype", intent["styleIntents"])
        self.assertIn("defense_focus", intent["styleIntents"])
        self.assertIn("defense", intent["focusAreas"])
        self.assertEqual(intent["tone"], "hype")
        self.assertEqual(compact_input["templateContext"]["userEditIntent"], intent)
        self.assertIn("Honor userEditIntent", payload["instructions"])
        self.assertNotIn("Make it more hype", json.dumps(payload))
        self.assertNotIn("userCreativeDirection", json.dumps(payload))
        self.assertNotIn("sourceObjectKey", str(payload))
        self.assertNotIn("uploads/source.mp4", str(payload))

    def test_revision_patch_payload_uses_agent_template_cookbook(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        request = _request("internal").model_copy(
            update={
                "templateId": "cinematic_mixtape_pro_v1",
                "targetDurationSeconds": 45,
            }
        )
        job = build_edit_job(request, "edit_revision_payload")

        payload = _build_revision_patch_payload(job, ReviseEditJobRequest(command="make_more_hype"), settings)
        compact_input = json.loads(payload["input"][0]["content"][0]["text"])
        agent_cookbook = compact_input["agentTemplateCookbook"]

        self.assertIs(payload["store"], False)
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(compact_input["templateId"], "cinematic_mixtape_pro_v1")
        self.assertEqual(agent_cookbook["templateId"], "cinematic_mixtape_pro_v1")
        self.assertEqual(agent_cookbook["templateCookbookRules"]["captionRules"]["tone"], "dramatic_hype")
        self.assertEqual(agent_cookbook["templateCookbookRules"]["orderingRules"]["closer"], "high_energy_finish")
        self.assertEqual(compact_input["candidateClips"][0]["clipId"], "c0")
        serialized = json.dumps(payload)
        self.assertNotIn("sourceObjectKey", serialized)
        self.assertNotIn("uploads/source.mp4", serialized)
        self.assertNotIn("downloadUrl", serialized)
        self.assertNotIn("https://", serialized)

    def test_revision_patch_request_rejects_unsafe_gpt_output(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=8,
            paid_max_clips=24,
            free_frames_per_clip=3,
            paid_frames_per_clip=5,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
            revision_enabled=True,
        )
        request = _request()
        job = build_edit_job(request, "edit_unsafe_revision_patch")

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            return {
                "output_text": json.dumps(
                    {
                        "version": "edit-plan-patch-v1",
                        "baseEditPlanId": job.edit_job_id,
                        "revisionIntent": "make_more_hype",
                        "summary": "Unsafe patch should fall back.",
                        "operations": [
                            {
                                "op": "replace",
                                "path": "/theme",
                                "value": {"downloadUrl": "https://storage.example.test/presigned/render.mp4"},
                                "reason": "Use the presigned render URL directly.",
                            }
                        ],
                        "requiresRerender": True,
                    }
                )
            }

        patch = request_gpt_edit_plan_patch(job, ReviseEditJobRequest(command="make_more_hype"), settings, fake_response_client)

        self.assertIsNone(patch)

    def test_schema_matches_highlight_decision_contract(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        request = _request()
        frame = SampledFrame(
            clip_id="c0",
            role="start",
            time_seconds=0.0,
            data_url="data:image/jpeg;base64,ZmFrZQ==",
        )

        payload = _build_openai_payload(request, request.clips[:1], [frame], settings)
        decision_schema = payload["text"]["format"]["schema"]["properties"]["decisions"]["items"]
        suggested_edit_schema = decision_schema["properties"]["suggestedEdit"]

        self.assertFalse(decision_schema["additionalProperties"])
        self.assertEqual(
            decision_schema["required"],
            [
                "clipId",
                "keep",
                "rejectReason",
                "highlightScore",
                "watchabilityScore",
                "basketballEvent",
                "outcome",
                "caption",
                "reason",
                "storyRole",
                "qualitySignals",
                "suggestedEdit",
            ],
        )
        self.assertFalse(suggested_edit_schema["additionalProperties"])
        self.assertEqual(
            suggested_edit_schema["required"],
            [
                "slowMotion",
                "slowMotionCenter",
                "captionMoment",
                "cropFocus",
                "extendBeforeSeconds",
                "extendAfterSeconds",
            ],
        )

    def test_revision_patch_schema_is_strict_for_all_objects(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        request = _request()
        job = build_edit_job(request, "edit_schema_strictness")

        payload = _build_revision_patch_payload(job, ReviseEditJobRequest(command="make_more_hype"), settings)
        schema = payload["text"]["format"]["schema"]

        def assert_strict_objects(node: object) -> None:
            if isinstance(node, dict):
                if node.get("type") == "object":
                    self.assertIs(node.get("additionalProperties"), False)
                    properties = node.get("properties", {})
                    self.assertEqual(set(node.get("required", [])), set(properties.keys()))
                for value in node.values():
                    assert_strict_objects(value)
            elif isinstance(node, list):
                for value in node:
                    assert_strict_objects(value)

        assert_strict_objects(schema)

    def test_sampling_includes_start_event_center_and_finish_roles(self) -> None:
        request = _request()
        clip = request.clips[0]

        free_samples = gpt_reranker._sample_times_for_clip(clip, 3)
        pro_samples = gpt_reranker._sample_times_for_clip(clip, 5)

        self.assertEqual(free_samples, [("start", 0.0), ("eventCenter", 3.0), ("finish", 5.95)])
        self.assertEqual(len(pro_samples), 5)
        self.assertIn("start", [role for role, _ in pro_samples])
        self.assertIn("eventCenter", [role for role, _ in pro_samples])
        self.assertIn("finish", [role for role, _ in pro_samples])

    def test_pro_sampling_adds_shot_setup_and_outcome_roles(self) -> None:
        request = _request()
        clip = request.clips[0]

        pro_samples = gpt_reranker._sample_times_for_clip(clip, 8)
        roles = [role for role, _ in pro_samples]

        self.assertIn("preEvent", roles)
        self.assertIn("outcome", roles)
        self.assertIn("release", roles)
        self.assertIn("rim", roles)
        self.assertLess(dict(pro_samples)["preEvent"], clip.eventCenter)
        self.assertGreater(dict(pro_samples)["outcome"], clip.eventCenter)

    def test_sampling_preserves_required_roles_for_short_clips(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_short",
            analysisJobId="analysis_short",
            installId="install-123",
            preset="personal_highlight",
            targetDurationSeconds=15,
            planTier="free",
            clips=[{**_clip("c_short", 1.0, 0.9), "end": 1.08, "eventCenter": 1.04}],
        )

        samples = gpt_reranker._sample_times_for_clip(request.clips[0], 3)

        self.assertEqual([role for role, _ in samples], ["start", "eventCenter", "finish"])

    def test_image_detail_env_falls_back_to_high_for_unknown_values(self) -> None:
        old_value = os.environ.get("HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL")
        try:
            for value in ("low", "high", "original", "auto"):
                os.environ["HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL"] = value
                self.assertEqual(GPTHighlightRerankerSettings.from_env().image_detail, value)

            os.environ["HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL"] = "giant"

            settings = GPTHighlightRerankerSettings.from_env()

            self.assertEqual(settings.image_detail, "high")
        finally:
            if old_value is None:
                os.environ.pop("HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL", None)
            else:
                os.environ["HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL"] = old_value

    def test_incomplete_keyframes_fall_back_before_openai_call(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=2,
            paid_max_clips=24,
            free_frames_per_clip=3,
            paid_frames_per_clip=5,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes
        openai_call_count = 0

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            return [
                SampledFrame(clip_id=clips[0].id, role="start", time_seconds=clips[0].start, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clips[0].id, role="eventCenter", time_seconds=clips[0].eventCenter, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clips[1].id, role="start", time_seconds=clips[1].start, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clips[1].id, role="eventCenter", time_seconds=clips[1].eventCenter, data_url="data:image/jpeg;base64,ZmFrZQ=="),
            ]

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            nonlocal openai_call_count
            openai_call_count += 1
            return {"output_text": "{}"}

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 2), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(openai_call_count, 0)
        self.assertEqual(result.gptRerankSummary.status, "fallback")
        self.assertEqual(result.gptRerankSummary.fallbackReason, "keyframe_extraction_incomplete")

    def test_incomplete_keyframes_drop_bad_candidate_without_losing_complete_candidates(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=2,
            paid_max_clips=24,
            free_frames_per_clip=3,
            paid_frames_per_clip=5,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes
        observed_payload_clip_ids: list[str] = []

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            return [
                SampledFrame(clip_id=clips[0].id, role="start", time_seconds=clips[0].start, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clips[0].id, role="eventCenter", time_seconds=clips[0].eventCenter, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clips[0].id, role="finish", time_seconds=clips[0].end - 0.05, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clips[1].id, role="start", time_seconds=clips[1].start, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clips[1].id, role="eventCenter", time_seconds=clips[1].eventCenter, data_url="data:image/jpeg;base64,ZmFrZQ=="),
            ]

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            compact_input = json.loads(payload["input"][0]["content"][0]["text"])
            observed_payload_clip_ids[:] = [clip["clipId"] for clip in compact_input["clips"]]
            return {
                "output_text": json.dumps(
                    {
                        "decisions": [
                            {
                                "clipId": "c0",
                                "keep": True,
                                "rejectReason": None,
                                "highlightScore": 0.91,
                                "watchabilityScore": 0.87,
                                "basketballEvent": "Made Shot",
                                "outcome": "made",
                                "caption": "BUCKET",
                                "reason": "Complete keyframes and clear context.",
                                "storyRole": "peak",
                                "qualitySignals": _quality_signals(),
                                "suggestedEdit": {
                                    "slowMotion": False,
                                    "slowMotionCenter": None,
                                    "captionMoment": None,
                                    "cropFocus": "rim",
                                    "extendBeforeSeconds": 0,
                                    "extendAfterSeconds": 0,
                                },
                            }
                        ],
                        "storyOrder": ["c0"],
                        "planEdit": {
                            "orderedClipIds": ["c0"],
                            "pacing": "fast",
                            "captions": [],
                            "slowMotionMoments": [],
                            "summary": "ok",
                        },
                        "summary": "ok",
                    }
                )
            }

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 2), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(observed_payload_clip_ids, ["c0"])
        self.assertEqual(result.gptRerankSummary.status, "applied")
        self.assertEqual(result.gptRerankSummary.keptClipIds, ["c0"])
        self.assertIn("c1", result.gptRerankSummary.rejectedClipIds)

    def test_shot_candidates_require_setup_and_outcome_keyframes_before_openai_call(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=1,
            paid_max_clips=24,
            free_frames_per_clip=8,
            paid_frames_per_clip=8,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes
        openai_call_count = 0

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            clip = clips[0]
            return [
                SampledFrame(clip_id=clip.id, role="start", time_seconds=clip.start, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clip.id, role="preEvent", time_seconds=clip.eventCenter - 0.8, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clip.id, role="release", time_seconds=clip.eventCenter - 0.3, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clip.id, role="rim", time_seconds=clip.eventCenter + 0.9, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clip.id, role="eventCenter", time_seconds=clip.eventCenter, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clip.id, role="finish", time_seconds=clip.end - 0.05, data_url="data:image/jpeg;base64,ZmFrZQ=="),
            ]

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            nonlocal openai_call_count
            openai_call_count += 1
            return {"output_text": "{}"}

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 1), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(openai_call_count, 0)
        self.assertEqual(result.gptRerankSummary.status, "fallback")
        self.assertEqual(result.gptRerankSummary.fallbackReason, "shot_keyframe_extraction_incomplete")

    def test_shot_candidates_missing_context_are_dropped_without_losing_complete_candidates(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=2,
            paid_max_clips=24,
            free_frames_per_clip=8,
            paid_frames_per_clip=8,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes
        observed_payload_clip_ids: list[str] = []

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            frames = []
            for clip in clips:
                roles = ["start", "preEvent", "release", "rim", "eventCenter", "finish"]
                if clip.id == "c1":
                    roles.insert(3, "outcome")
                for role in roles:
                    frames.append(SampledFrame(clip_id=clip.id, role=role, time_seconds=clip.eventCenter, data_url="data:image/jpeg;base64,ZmFrZQ=="))
            return frames

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            compact_input = json.loads(payload["input"][0]["content"][0]["text"])
            observed_payload_clip_ids[:] = [clip["clipId"] for clip in compact_input["clips"]]
            return {
                "output_text": json.dumps(
                    {
                        "decisions": [
                            {
                                "clipId": "c1",
                                "keep": True,
                                "rejectReason": None,
                                "highlightScore": 0.92,
                                "watchabilityScore": 0.88,
                                "basketballEvent": "Made Shot",
                                "outcome": "made",
                                "caption": "BUCKET",
                                "reason": "Complete setup, release, rim, and outcome.",
                                "storyRole": "peak",
                                "qualitySignals": {
                                    "setupVisible": True,
                                    "eventVisible": True,
                                    "outcomeVisible": True,
                                    "ballPathVisible": True,
                                    "playerControlVisible": True,
                                    "cleanCamera": True,
                                    "fullPlayContext": True,
                                    "reason": "Complete shot context.",
                                },
                                "suggestedEdit": {
                                    "slowMotion": False,
                                    "slowMotionCenter": None,
                                    "captionMoment": None,
                                    "cropFocus": "rim",
                                    "extendBeforeSeconds": 0,
                                    "extendAfterSeconds": 0,
                                },
                            }
                        ],
                        "storyOrder": ["c1"],
                        "planEdit": {
                            "orderedClipIds": ["c1"],
                            "pacing": "fast",
                            "captions": [],
                            "slowMotionMoments": [],
                            "summary": "ok",
                        },
                        "summary": "ok",
                    }
                )
            }

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 2), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(observed_payload_clip_ids, ["c1"])
        self.assertEqual(result.gptRerankSummary.status, "applied")
        self.assertEqual(result.gptRerankSummary.keptClipIds, ["c1"])
        self.assertIn("c0", result.gptRerankSummary.rejectedClipIds)

    def test_incomplete_gpt_decisions_apply_valid_subset_without_reintroducing_missing_candidates(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=2,
            paid_max_clips=24,
            free_frames_per_clip=3,
            paid_frames_per_clip=5,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes
        observed_clip_ids: list[str] = []

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            observed_clip_ids[:] = [clip.id for clip in clips]
            frames = []
            for clip in clips:
                for role, second in gpt_reranker._sample_times_for_clip(clip, frames_per_clip):
                    frames.append(SampledFrame(clip_id=clip.id, role=role, time_seconds=second, data_url="data:image/jpeg;base64,ZmFrZQ=="))
            return frames

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            return {
                "output_text": json.dumps(
                    {
                        "decisions": [
                            {
                                "clipId": observed_clip_ids[0],
                                "keep": True,
                                "rejectReason": None,
                                "highlightScore": 0.9,
                                "watchabilityScore": 0.8,
                                "basketballEvent": "Made Shot",
                                "outcome": "made",
                                "caption": "BUCKET",
                                "reason": "Clear outcome.",
                                "storyRole": "filler",
                                "qualitySignals": _quality_signals(),
                                "suggestedEdit": {
                                    "slowMotion": False,
                                    "slowMotionCenter": None,
                                    "captionMoment": None,
                                    "cropFocus": "center_action",
                                    "extendBeforeSeconds": 0,
                                    "extendAfterSeconds": 0,
                                },
                            }
                        ],
                        "storyOrder": [observed_clip_ids[0]],
                        "planEdit": {
                            "orderedClipIds": [observed_clip_ids[0]],
                            "pacing": "fast",
                            "captions": [],
                            "slowMotionMoments": [],
                            "summary": "ok",
                        },
                        "summary": "ok",
                    }
                )
            }

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 2), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(result.gptRerankSummary.status, "applied")
        self.assertEqual(result.gptRerankSummary.keptClipIds, [observed_clip_ids[0]])
        self.assertIn(observed_clip_ids[1], result.gptRerankSummary.rejectedClipIds)
        self.assertEqual([clip.id for clip in result.clips], [observed_clip_ids[0]])

    def test_unsampled_existing_clip_decision_is_rejected(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=2,
            paid_max_clips=24,
            free_frames_per_clip=3,
            paid_frames_per_clip=5,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes
        observed_clip_ids: list[str] = []

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            observed_clip_ids[:] = [clip.id for clip in clips]
            frames = []
            for clip in clips:
                for role, second in gpt_reranker._sample_times_for_clip(clip, frames_per_clip):
                    frames.append(SampledFrame(clip_id=clip.id, role=role, time_seconds=second, data_url="data:image/jpeg;base64,ZmFrZQ=="))
            return frames

        def decision(clip_id: str, score: float) -> dict:
            return {
                "clipId": clip_id,
                "keep": True,
                "rejectReason": None,
                "highlightScore": score,
                "watchabilityScore": score,
                "basketballEvent": "Made Shot",
                "outcome": "made",
                "caption": "BUCKET",
                "reason": "Clear outcome.",
                "storyRole": "peak",
                "qualitySignals": _quality_signals(),
                "suggestedEdit": {
                    "slowMotion": False,
                    "slowMotionCenter": None,
                    "captionMoment": None,
                    "cropFocus": "center_action",
                    "extendBeforeSeconds": 0,
                    "extendAfterSeconds": 0,
                },
            }

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            return {
                "output_text": json.dumps(
                    {
                        "decisions": [
                            decision(observed_clip_ids[0], 0.9),
                            decision("c2", 1.0),
                        ],
                        "storyOrder": ["c2", observed_clip_ids[0]],
                        "planEdit": {
                            "orderedClipIds": ["c2", observed_clip_ids[0]],
                            "pacing": "fast",
                            "captions": [],
                            "slowMotionMoments": [],
                            "summary": "ok",
                        },
                        "summary": "ok",
                    }
                )
            }

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 3), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(observed_clip_ids, ["c0", "c1"])
        self.assertEqual(result.gptRerankSummary.status, "applied")
        self.assertEqual(result.gptRerankSummary.keptClipIds, ["c0"])
        self.assertIn("c1", result.gptRerankSummary.rejectedClipIds)
        self.assertIn("c2", result.gptRerankSummary.rejectedClipIds)
        self.assertEqual([clip.id for clip in result.clips], ["c0"])

    def test_duplicate_gpt_decisions_fall_back(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=2,
            paid_max_clips=24,
            free_frames_per_clip=3,
            paid_frames_per_clip=5,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes
        observed_clip_ids: list[str] = []

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            observed_clip_ids[:] = [clip.id for clip in clips]
            frames = []
            for clip in clips:
                for role, second in gpt_reranker._sample_times_for_clip(clip, frames_per_clip):
                    frames.append(SampledFrame(clip_id=clip.id, role=role, time_seconds=second, data_url="data:image/jpeg;base64,ZmFrZQ=="))
            return frames

        def decision(clip_id: str, caption: str) -> dict:
            return {
                "clipId": clip_id,
                "keep": True,
                "rejectReason": None,
                "highlightScore": 0.9,
                "watchabilityScore": 0.8,
                "basketballEvent": "Made Shot",
                "outcome": "made",
                "caption": caption,
                "reason": "Clear outcome.",
                "storyRole": "filler",
                "qualitySignals": _quality_signals(),
                "suggestedEdit": {
                    "slowMotion": False,
                    "slowMotionCenter": None,
                    "captionMoment": None,
                    "cropFocus": "center_action",
                    "extendBeforeSeconds": 0,
                    "extendAfterSeconds": 0,
                },
            }

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            return {
                "output_text": json.dumps(
                    {
                        "decisions": [
                            decision(observed_clip_ids[0], "FIRST"),
                            decision(observed_clip_ids[0], "DUPLICATE"),
                        ],
                        "storyOrder": [observed_clip_ids[0]],
                        "planEdit": {
                            "orderedClipIds": [observed_clip_ids[0]],
                            "pacing": "fast",
                            "captions": [],
                            "slowMotionMoments": [],
                            "summary": "duplicate",
                        },
                        "summary": "duplicate",
                    }
                )
            }

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 2), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(result.gptRerankSummary.status, "fallback")
        self.assertEqual(result.gptRerankSummary.fallbackReason, "duplicate_gpt_decisions")

    def test_tiny_and_pre_basket_candidates_are_not_sent_to_gpt(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=3,
            paid_max_clips=24,
            free_frames_per_clip=3,
            paid_frames_per_clip=8,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        request = CreateEditJobRequest(
            videoId="video_quality",
            analysisJobId="analysis_quality",
            installId="install-123",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {**_clip("tiny", 0.0, 1.0), "end": 0.1, "eventCenter": 0.05},
                {**_clip("pre_basket", 10.0, 0.99), "end": 16.0, "eventCenter": 10.1},
                _clip("good_context", 20.0, 0.72),
            ],
        )
        original_extract = gpt_reranker._extract_candidate_keyframes
        observed_clip_ids: list[str] = []

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            observed_clip_ids[:] = [clip.id for clip in clips]
            frames = []
            for clip in clips:
                for role, second in gpt_reranker._sample_times_for_clip(clip, frames_per_clip):
                    frames.append(SampledFrame(clip_id=clip.id, role=role, time_seconds=second, data_url="data:image/jpeg;base64,ZmFrZQ=="))
            return frames

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            return {
                "output_text": json.dumps(
                    {
                        "decisions": [
                            {
                                "clipId": "good_context",
                                "keep": True,
                                "rejectReason": None,
                                "highlightScore": 0.9,
                                "watchabilityScore": 0.85,
                                "basketballEvent": "Made Shot",
                                "outcome": "made",
                                "caption": "BUCKET",
                                "reason": "Clear setup, shot, and outcome.",
                                "storyRole": "peak",
                                "qualitySignals": {
                                    "setupVisible": True,
                                    "eventVisible": True,
                                    "outcomeVisible": True,
                                    "ballPathVisible": True,
                                    "playerControlVisible": True,
                                    "cleanCamera": True,
                                    "fullPlayContext": True,
                                    "reason": "Shows the play before and after the make.",
                                },
                                "suggestedEdit": {
                                    "slowMotion": False,
                                    "slowMotionCenter": None,
                                    "captionMoment": None,
                                    "cropFocus": "center_action",
                                    "extendBeforeSeconds": 0,
                                    "extendAfterSeconds": 0,
                                },
                            }
                        ],
                        "storyOrder": ["good_context"],
                        "planEdit": {
                            "orderedClipIds": ["good_context"],
                            "pacing": "fast",
                            "captions": [],
                            "slowMotionMoments": [],
                            "summary": "Use the only complete play.",
                        },
                        "summary": "ok",
                    }
                )
            }

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(request, Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(observed_clip_ids, ["good_context"])
        self.assertEqual(result.gptRerankSummary.status, "applied")
        self.assertEqual(result.gptRerankSummary.keptClipIds, ["good_context"])

    def test_free_and_pro_sampling_limits(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()

        self.assertEqual(settings.limits_for("free"), (8, 8))
        self.assertGreaterEqual(settings.limits_for("pro")[0], 20)
        self.assertLessEqual(settings.limits_for("pro")[0], 30)
        self.assertGreaterEqual(settings.limits_for("pro")[1], 5)
        self.assertLessEqual(settings.limits_for("pro")[1], 8)

    def test_sampling_caps_are_applied_before_openai_call(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=8,
            paid_max_clips=24,
            free_frames_per_clip=3,
            paid_frames_per_clip=5,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes
        observed_calls: list[tuple[int, int]] = []
        observed_clip_ids: list[str] = []

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            observed_calls.append((len(clips), frames_per_clip))
            observed_clip_ids[:] = [clip.id for clip in clips]
            frames = []
            for clip in clips:
                for role, second in gpt_reranker._sample_times_for_clip(clip, frames_per_clip):
                    frames.append(
                        SampledFrame(
                            clip_id=clip.id,
                            role=role,
                            time_seconds=second,
                            data_url="data:image/jpeg;base64,ZmFrZQ==",
                        )
                    )
            return frames

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            decisions = [
                {
                    "clipId": clip_id,
                    "keep": True,
                    "rejectReason": None,
                    "highlightScore": 0.9,
                    "watchabilityScore": 0.8,
                    "basketballEvent": "Made Shot",
                    "outcome": "made",
                    "caption": "BUCKET",
                    "reason": "Clear outcome.",
                    "storyRole": "filler",
                    "qualitySignals": _quality_signals(),
                    "suggestedEdit": {
                        "slowMotion": False,
                        "slowMotionCenter": None,
                        "captionMoment": None,
                        "cropFocus": "center_action",
                        "extendBeforeSeconds": 0,
                        "extendAfterSeconds": 0,
                    },
                }
                for clip_id in observed_clip_ids
            ]
            return {
                "output_text": json.dumps(
                    {
                        "decisions": decisions,
                        "storyOrder": observed_clip_ids,
                        "planEdit": {
                            "orderedClipIds": observed_clip_ids,
                            "pacing": "fast",
                            "captions": [],
                            "slowMotionMoments": [],
                            "summary": "ok",
                        },
                        "summary": "ok",
                    }
                )
            }

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                free_result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 12), Path(source.name), settings, fake_response_client)
                pro_result = gpt_reranker.rerank_edit_request_with_gpt(_request("pro", 30), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(observed_calls, [(8, 3), (24, 5)])
        self.assertEqual(len(free_result.gptRerankSummary.storyOrderClipIds), 8)
        self.assertEqual(len(pro_result.gptRerankSummary.storyOrderClipIds), 24)
        self.assertTrue(set(free_result.gptRerankSummary.storyOrderClipIds).issubset({clip.id for clip in free_result.clips}))
        self.assertTrue(set(pro_result.gptRerankSummary.storyOrderClipIds).issubset({clip.id for clip in pro_result.clips}))


if __name__ == "__main__":
    unittest.main()
