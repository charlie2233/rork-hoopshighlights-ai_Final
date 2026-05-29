from pathlib import Path
import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "services" / "editing"))
sys.path.insert(0, str(REPO_ROOT / "ios" / "backend"))

from app.editing import CreateEditJobRequest, GPTHighlightClipDecision, GPTHighlightSuggestedEdit, ReviseEditJobRequest, apply_gpt_highlight_rerank, build_edit_job
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


def _labeled_clip(clip_id: str, start: float, score: float, label: str) -> dict:
    return {
        **_clip(clip_id, start, score),
        "label": label,
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


def _team_targeted_request() -> CreateEditJobRequest:
    return CreateEditJobRequest(
        videoId="video_123",
        analysisJobId="analysis_123",
        installId="install-123",
        sourceObjectKey="uploads/source.mp4",
        preset="personal_highlight",
        targetDurationSeconds=30,
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
                **_clip("dark_make", 0.0, 0.98),
                "teamAttribution": {
                    "teamId": "team_dark",
                    "label": "Dark jerseys",
                    "colorLabel": "black",
                    "confidence": 0.92,
                    "source": "quick_scan",
                    "evidenceFrameRefs": ["clip_0_release", "clip_0_result"],
                    "evidenceRoleGroups": ["action", "outcome"],
                },
            },
            {
                **_clip("light_make", 7.0, 0.97),
                "teamAttribution": {
                    "teamId": "team_light",
                    "label": "Light jerseys",
                    "colorLabel": "white",
                    "confidence": 0.94,
                    "source": "quick_scan",
                    "evidenceFrameRefs": ["clip_1_release", "clip_1_result"],
                    "evidenceRoleGroups": ["action", "outcome"],
                },
            },
            {
                **_clip("uncertain_make", 14.0, 0.76),
                "teamAttribution": {
                    "teamId": "team_light",
                    "label": "Light jerseys",
                    "colorLabel": "white",
                    "confidence": 0.64,
                    "source": "quick_scan",
                },
            },
        ],
    )


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
                "userReviewDecision",
                "teamAttribution",
                "teamAttributionStatus",
                "teamEvidence",
                "templateId",
                "planTier",
                "qualityHints",
                "nativeShotSignals",
                "outcomeEvidenceSource",
                "outcomeReliabilityScore",
                "sampledKeyframes",
            },
        )
        self.assertEqual(compact_clip["sampledKeyframes"], [{"role": "start", "time": 0.0}])
        self.assertIsNone(compact_clip["userReviewDecision"])
        self.assertEqual(compact_clip["nativeShotSignals"]["outcome"], "made")
        self.assertTrue(compact_clip["nativeShotSignals"]["timingWindowOk"])
        self.assertEqual(compact_clip["qualityHints"]["nativeShotSignals"]["outcome"], "made")
        self.assertEqual(compact_clip["outcomeEvidenceSource"], "label_only")
        self.assertEqual(compact_clip["qualityHints"]["outcomeEvidenceSource"], "label_only")
        self.assertGreater(compact_clip["outcomeReliabilityScore"], 0.0)
        self.assertEqual(compact_clip["qualityHints"]["outcomeReliabilityScore"], compact_clip["outcomeReliabilityScore"])
        self.assertEqual(compact_clip["teamEvidence"]["status"], "missing_attribution")
        self.assertFalse(compact_clip["teamEvidence"]["evidenceBacked"])
        self.assertTrue(compact_input["shotTrackerRules"]["treatLabelOnlyOutcomeEvidenceAsUnverified"])
        self.assertIn("outcomeEvidenceSource=label_only", payload["instructions"])
        self.assertEqual(agent_cookbook["templateId"], "personal_highlight_v1")
        self.assertIn("templateCookbookRules", agent_cookbook)
        self.assertEqual(agent_cookbook["templateCookbookRules"]["captionRules"]["tone"], "hype")
        self.assertEqual(agent_cookbook["candidateClips"][0]["clipId"], "c0")
        self.assertEqual(agent_cookbook["candidateClips"][0]["nativeShotSignals"]["contextQualityScore"], 1.0)
        self.assertEqual(agent_cookbook["candidateClips"][0]["outcomeEvidenceSource"], "label_only")
        self.assertEqual(len(image_items), 1)
        self.assertTrue(image_items[0]["image_url"].startswith("data:image/jpeg;base64,"))
        self.assertNotIn("c999", json.dumps(payload))
        self.assertNotIn("sourceObjectKey", str(payload))
        self.assertNotIn("uploads/source.mp4", str(payload))
        self.assertNotIn("https://", str(payload))

    def test_payload_includes_team_targeting_and_excludes_confident_opponent_clips(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        request = _team_targeted_request()
        frames = [
            SampledFrame(clip_id="dark_make", role="start", time_seconds=0.0, data_url="data:image/jpeg;base64,ZA=="),
            SampledFrame(clip_id="uncertain_make", role="start", time_seconds=14.0, data_url="data:image/jpeg;base64,dQ=="),
            SampledFrame(clip_id="light_make", role="start", time_seconds=7.0, data_url="data:image/jpeg;base64,bA=="),
        ]

        payload = _build_openai_payload(request, request.clips, frames, settings)
        compact_input = json.loads(payload["input"][0]["content"][0]["text"])
        compact_clip_ids = [clip["clipId"] for clip in compact_input["clips"]]
        by_id = {clip["clipId"]: clip for clip in compact_input["clips"]}

        self.assertEqual(compact_input["teamTargeting"]["mode"], "team")
        self.assertEqual(compact_input["teamTargeting"]["confidenceThreshold"], 0.85)
        self.assertTrue(compact_input["teamTargeting"]["includeUncertain"])
        self.assertIn("dark_make", compact_clip_ids)
        self.assertIn("uncertain_make", compact_clip_ids)
        self.assertNotIn("light_make", compact_clip_ids)
        self.assertEqual(by_id["dark_make"]["teamAttributionStatus"], "matched")
        self.assertEqual(by_id["dark_make"]["teamEvidence"]["status"], "evidence_backed")
        self.assertEqual(by_id["uncertain_make"]["teamAttributionStatus"], "uncertain")
        self.assertEqual(by_id["uncertain_make"]["teamEvidence"]["status"], "weak_evidence")
        self.assertIn("insufficient_evidence_frame_refs", by_id["uncertain_make"]["teamEvidence"]["reasons"])
        self.assertIn("Keep uncertain team-attribution clips", payload["instructions"])
        self.assertIn("teamEvidence.status=evidence_backed", payload["instructions"])
        self.assertIn("must never be promoted to a confident selected-team match", payload["instructions"])
        self.assertIn("raw teamAttribution.confidence", payload["instructions"])

    def test_disabled_gpt_fallback_preserves_uncertain_team_review_ids(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=False,
            api_key=None,
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

        result = gpt_reranker.rerank_edit_request_with_gpt(
            _team_targeted_request(),
            Path("/tmp/hoopclips-missing-source.mp4"),
            settings,
        )

        self.assertIsNotNone(result.gptRerankSummary)
        self.assertEqual(result.gptRerankSummary.status, "disabled")
        self.assertEqual(result.gptRerankSummary.fallbackReason, "disabled")
        self.assertEqual(result.gptRerankSummary.keptClipIds, ["dark_make"])
        self.assertEqual(result.gptRerankSummary.uncertainReviewClipIds, ["uncertain_make"])
        self.assertNotIn("light_make", result.gptRerankSummary.uncertainReviewClipIds)
        self.assertEqual(result.gptRerankSummary.rejectedReasonCounts["opponent_team_candidate"], 1)
        self.assertEqual(result.gptRerankSummary.rejectedReasonCounts["needs_manual_team_review"], 1)

    def test_disabled_gpt_fallback_receipt_reports_quality_rejections(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=False,
            api_key=None,
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
        request = CreateEditJobRequest(
            videoId="video_disabled_quality",
            analysisJobId="analysis_disabled_quality",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {**_clip("tiny", 0.0, 0.99), "end": 0.1, "eventCenter": 0.05},
                {**_clip("pre_basket", 10.0, 0.98), "end": 16.0, "eventCenter": 10.1},
                _clip("complete_make", 20.0, 0.78),
                _labeled_clip("clear_block", 32.0, 0.74, "Block"),
            ],
        )

        result = gpt_reranker.rerank_edit_request_with_gpt(
            request,
            Path("/tmp/hoopclips-missing-source.mp4"),
            settings,
        )

        self.assertEqual(result.gptRerankSummary.status, "disabled")
        self.assertEqual(result.gptRerankSummary.keptClipIds, ["complete_make", "clear_block"])
        self.assertEqual(set(result.gptRerankSummary.rejectedClipIds), {"tiny", "pre_basket"})
        self.assertEqual(
            result.gptRerankSummary.rejectedReasonCounts["candidate_missing_minimum_quality_context"],
            2,
        )

    def test_payload_preserves_explicit_uncertain_team_status(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        request = CreateEditJobRequest(
            videoId="video_123",
            analysisJobId="analysis_123",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
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
                    **_clip("review_block", 0.0, 0.9),
                    "label": "Blocked Shot",
                    "teamAttribution": {
                        "teamId": "team_dark",
                        "label": "Dark jerseys",
                        "colorLabel": "black",
                        "confidence": 0.91,
                        "source": "quick_scan",
                    },
                    "teamAttributionStatus": "uncertain",
                }
            ],
        )
        frames = [SampledFrame(clip_id="review_block", role="start", time_seconds=0.0, data_url="data:image/jpeg;base64,ZA==")]

        payload = _build_openai_payload(request, request.clips, frames, settings)
        compact_input = json.loads(payload["input"][0]["content"][0]["text"])

        self.assertEqual(compact_input["clips"][0]["clipId"], "review_block")
        self.assertEqual(compact_input["clips"][0]["teamAttributionStatus"], "uncertain")

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
        decision_properties = decision_schema["properties"]

        self.assertEqual(compact_clip["qualityHints"]["leadInSeconds"], 3.0)
        self.assertEqual(compact_clip["qualityHints"]["followThroughSeconds"], 3.0)
        self.assertTrue(compact_clip["qualityHints"]["timingWindowOk"])
        self.assertEqual(compact_clip["nativeShotSignals"]["setupContextScore"], 1.0)
        self.assertEqual(compact_clip["nativeShotSignals"]["outcomeContextScore"], 1.0)
        self.assertEqual(
            shot_rules["requiredShotContextKeyframes"],
            ["belowRim", "preEvent", "release", "rimApproach", "rimEntry", "shotArcEarly", "shotArcLate"],
        )
        self.assertIn("qualitySignals", decision_properties)
        self.assertIn("qualitySignals", decision_schema["required"])
        quality_required = decision_properties["qualitySignals"]["required"]
        self.assertIn("releaseVisible", quality_required)
        self.assertIn("shotArcVisible", quality_required)
        self.assertIn("rimResultVisible", quality_required)
        self.assertIn("shotResultEvidence", decision_properties)
        self.assertIn("shotResultEvidence", decision_schema["required"])
        result_evidence = decision_properties["shotResultEvidence"]
        self.assertEqual(
            result_evidence["properties"]["rimResultEvidence"]["enum"],
            ["made_visible", "clear_miss", "blocked", "unclear"],
        )
        self.assertIn("rimEntrySequence", result_evidence["required"])
        self.assertIn("ballApproachFrameRole", result_evidence["required"])
        self.assertIn("rimEntryFrameRole", result_evidence["required"])
        self.assertIn("ballBelowRimOrNetFrameRole", result_evidence["required"])
        self.assertEqual(result_evidence["properties"]["rimEntrySequence"]["enum"], ["visible_entry", "visible_miss", "blocked", "unclear"])
        self.assertIn("shotTrackingEvidence", decision_properties)
        self.assertIn("shotTrackingEvidence", decision_schema["required"])
        tracking_evidence = decision_properties["shotTrackingEvidence"]
        self.assertEqual(
            tracking_evidence["properties"]["ballEntersRimFrameRole"]["anyOf"][0]["enum"],
            [
                "start",
                "preEvent",
                "release",
                "shotArcEarly",
                "eventCenter",
                "outcome",
                "shotArcLate",
                "rimApproach",
                "rim",
                "rimEntry",
                "belowRim",
                "postOutcome",
                "finish",
                "midAction",
                "defenseSetup",
                "challenge",
                "possessionChange",
                "recovery",
                "defenseOutcome",
            ],
        )
        self.assertTrue(shot_rules["madeShotRequiresFrameRoleTrackingEvidence"])
        self.assertTrue(shot_rules["madeShotRequiresRimEntrySequenceEvidence"])
        self.assertEqual(shot_rules["requiredMadeShotTracking"]["trajectoryContinuity"], "continuous")
        self.assertEqual(shot_rules["requiredMadeShotTracking"]["rimEntrySequence"], "visible_entry")
        self.assertEqual(shot_rules["requiredMadeShotTracking"]["dedicatedRimEntryPathRoles"], ["rimApproach", "rimEntry", "belowRim"])
        self.assertTrue(shot_rules["missedShotRequiresExplicitMissResultEvidence"])
        self.assertTrue(shot_rules["missedShotRequiresVisibleMissSequenceEvidence"])
        self.assertEqual(shot_rules["requiredMissedShotTracking"]["rimResultEvidence"], "clear_miss")
        self.assertEqual(shot_rules["requiredMissedShotTracking"]["rimEntrySequence"], "visible_miss")
        self.assertIsNone(shot_rules["requiredMissedShotTracking"]["ballEntersRimFrameRole"])
        self.assertTrue(shot_rules["netOrRimReactionDoesNotReplaceEntryFrameRoles"])
        self.assertEqual(shot_rules["nonScoringDefensiveOutcomes"], ["steal", "forced_turnover", "defensive_stop"])
        self.assertTrue(shot_rules["madeOrMissedShotRequiresVisibleBallPath"])
        self.assertTrue(shot_rules["defensiveOutcomeRequiresEventOutcomePlayerControlBallAndCleanCamera"])
        self.assertEqual(
            shot_rules["requiredDefensiveTracking"]["minimumOutcomeConfidence"],
            gpt_reranker.MIN_GPT_DEFENSIVE_OUTCOME_CONFIDENCE,
        )
        self.assertTrue(shot_rules["blockedShotRequiresVisibleChallengeBallPathPlayerControlAndOutcome"])
        self.assertTrue(shot_rules["richSampledShotRoleRules"]["ifRimEntryIsSampledUseItAsBallEntersRimFrameRole"])
        self.assertTrue(shot_rules["madeOrMissedShotRequiresVisibleReleaseAndRimResult"])
        self.assertTrue(shot_rules["madeOrMissedShotRequiresVisibleShotArc"])
        self.assertTrue(shot_rules["madeShotRequiresExplicitMadeResultEvidence"])
        self.assertIn("rimEntrySequence=visible_entry", payload["instructions"])
        self.assertIn("rimEntrySequence=visible_miss", payload["instructions"])
        self.assertIn("ballEntersRimFrameRole", payload["instructions"])
        self.assertIn("must not replace", payload["instructions"])
        self.assertIn("shot-tracker", payload["instructions"])
        self.assertIn("reject clips that start right before the basket", payload["instructions"])
        self.assertIn("outcome=steal", payload["instructions"])
        self.assertIn("forced_turnover", payload["instructions"])
        self.assertIn("defensive_stop", payload["instructions"])
        self.assertIn("shotResultEvidence.outcomeConfidence >= 0.65", payload["instructions"])
        self.assertIn("ball path/control", payload["instructions"])
        self.assertEqual(
            decision_properties["outcome"]["enum"],
            ["made", "missed", "blocked", "steal", "forced_turnover", "defensive_stop", "unclear", "not_basketball"],
        )

    def test_payload_preserves_native_uncertain_outcome_over_provider_made_label(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        clip = {
            **_clip("provider_overclaimed_make", 12.0, 0.92),
            "nativeShotSignals": {
                "isShotLike": True,
                "leadInSeconds": 3.0,
                "followThroughSeconds": 3.0,
                "setupContextScore": 1.0,
                "outcomeContextScore": 1.0,
                "eventCenterQuality": 1.0,
                "contextQualityScore": 1.0,
                "timingWindowOk": True,
                "outcome": "uncertain",
                "outcomeConfidence": 0.0,
            },
        }
        request = CreateEditJobRequest(
            videoId="video_123",
            analysisJobId="analysis_123",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[clip],
        )
        frames = [
            SampledFrame(clip_id="provider_overclaimed_make", role="start", time_seconds=12.0, data_url="data:image/jpeg;base64,ZmFrZQ=="),
            SampledFrame(clip_id="provider_overclaimed_make", role="eventCenter", time_seconds=15.0, data_url="data:image/jpeg;base64,ZmFrZQ=="),
            SampledFrame(clip_id="provider_overclaimed_make", role="finish", time_seconds=17.95, data_url="data:image/jpeg;base64,ZmFrZQ=="),
        ]

        payload = _build_openai_payload(request, request.clips, frames, settings)
        compact_input = json.loads(payload["input"][0]["content"][0]["text"])
        compact_clip = compact_input["clips"][0]

        self.assertEqual(compact_clip["existingLabel"], "Made Shot")
        self.assertEqual(compact_clip["nativeShotSignals"]["outcome"], "uncertain")
        self.assertEqual(compact_clip["qualityHints"]["nativeShotSignals"]["outcome"], "uncertain")

    def test_payload_does_not_treat_ambiguous_layup_label_as_made(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        request = CreateEditJobRequest(
            videoId="video_ambiguous_layup",
            analysisJobId="analysis_ambiguous_layup",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[{**_clip("ambiguous_layup", 12.0, 0.9), "label": "Layup"}],
        )
        frames = [
            SampledFrame(clip_id="ambiguous_layup", role="start", time_seconds=12.0, data_url="data:image/jpeg;base64,ZmFrZQ=="),
            SampledFrame(clip_id="ambiguous_layup", role="eventCenter", time_seconds=15.0, data_url="data:image/jpeg;base64,ZmFrZQ=="),
            SampledFrame(clip_id="ambiguous_layup", role="finish", time_seconds=17.95, data_url="data:image/jpeg;base64,ZmFrZQ=="),
        ]

        payload = _build_openai_payload(request, request.clips, frames, settings)
        compact_clip = json.loads(payload["input"][0]["content"][0]["text"])["clips"][0]

        self.assertEqual(compact_clip["existingLabel"], "Layup")
        self.assertEqual(compact_clip["nativeShotSignals"]["outcome"], "uncertain")
        self.assertEqual(compact_clip["nativeShotSignals"]["outcomeConfidence"], 0.0)

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

    def test_quality_filter_excludes_barely_contextual_shot_windows_before_gpt(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_barely_contextual_filter",
            analysisJobId="analysis_barely_contextual_filter",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {
                    **_clip("barely_contextual_make", 8.0, 0.98),
                    "end": 11.3,
                    "eventCenter": 9.0,
                },
                _clip("complete_make", 18.0, 0.82),
            ],
        )

        sampled = gpt_reranker._quality_filtered_sampled_clips(request.clips, max_clips=2)
        hints = [gpt_reranker._candidate_quality_hints(clip) for clip in request.clips]

        self.assertEqual([clip.id for clip in sampled], ["complete_make"])
        self.assertFalse(hints[0]["timingWindowOk"])
        self.assertFalse(hints[0]["nativeShotSignals"]["timingWindowOk"])
        self.assertLess(hints[0]["nativeShotSignals"]["contextQualityScore"], hints[1]["nativeShotSignals"]["contextQualityScore"])

    def test_quality_filter_keeps_defensive_window_with_event_context_before_gpt(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_defensive_event_context_filter",
            analysisJobId="analysis_defensive_event_context_filter",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {
                    **_clip("contextual_block", 20.0, 0.88),
                    "label": "Block",
                    "end": 22.4,
                    "eventCenter": 20.7,
                },
                {
                    **_clip("same_window_make", 30.0, 0.92),
                    "label": "Made Shot",
                    "end": 32.4,
                    "eventCenter": 30.7,
                },
            ],
        )

        sampled = gpt_reranker._quality_filtered_sampled_clips(request.clips, max_clips=2)
        block_hints = gpt_reranker._candidate_quality_hints(request.clips[0])
        shot_hints = gpt_reranker._candidate_quality_hints(request.clips[1])

        self.assertEqual([clip.id for clip in sampled], ["contextual_block"])
        self.assertTrue(block_hints["defensiveEventLike"])
        self.assertTrue(block_hints["timingWindowOk"])
        self.assertEqual(block_hints["minLeadInSeconds"], gpt_reranker.MIN_GPT_DEFENSIVE_LEAD_IN_SECONDS)
        self.assertEqual(block_hints["minFollowThroughSeconds"], gpt_reranker.MIN_GPT_DEFENSIVE_FOLLOW_THROUGH_SECONDS)
        self.assertFalse(shot_hints["defensiveEventLike"])
        self.assertFalse(shot_hints["timingWindowOk"])
        self.assertEqual(shot_hints["minLeadInSeconds"], gpt_reranker.MIN_GPT_CANDIDATE_LEAD_IN_SECONDS)
        self.assertEqual(shot_hints["minFollowThroughSeconds"], gpt_reranker.MIN_GPT_CANDIDATE_FOLLOW_THROUGH_SECONDS)

    def test_quality_filter_keeps_generic_non_shot_on_strict_context_floor(self) -> None:
        clip = CreateEditJobRequest(
            videoId="video_generic_non_shot_floor",
            analysisJobId="analysis_generic_non_shot_floor",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {
                    **_clip("generic_moment", 40.0, 0.88),
                    "label": "Highlight",
                    "end": 43.0,
                    "eventCenter": 40.8,
                },
            ],
        ).clips[0]

        hints = gpt_reranker._candidate_quality_hints(clip)

        self.assertFalse(hints["defensiveEventLike"])
        self.assertFalse(hints["shotLike"])
        self.assertEqual(hints["minLeadInSeconds"], gpt_reranker.MIN_GPT_CANDIDATE_LEAD_IN_SECONDS)
        self.assertEqual(hints["minFollowThroughSeconds"], gpt_reranker.MIN_GPT_CANDIDATE_FOLLOW_THROUGH_SECONDS)
        self.assertFalse(hints["timingWindowOk"])

    def test_quality_filter_excludes_native_not_shot_overclaimed_provider_clip(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_native_not_shot_filter",
            analysisJobId="analysis_native_not_shot_filter",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {
                    **_clip("provider_false_make", 0.0, 0.99),
                    "nativeShotSignals": {
                        "isShotLike": True,
                        "leadInSeconds": 3.0,
                        "followThroughSeconds": 3.0,
                        "setupContextScore": 1.0,
                        "outcomeContextScore": 1.0,
                        "eventCenterQuality": 1.0,
                        "contextQualityScore": 1.0,
                        "timingWindowOk": True,
                        "outcome": "not_shot",
                        "outcomeConfidence": 1.0,
                    },
                },
                _clip("good_context", 8.0, 0.72),
            ],
        )

        sampled = gpt_reranker._quality_filtered_sampled_clips(request.clips, max_clips=3)

        self.assertEqual([clip.id for clip in sampled], ["good_context"])

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
                    "label": "Crowd Reaction",
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

    def test_source_context_expansion_salvages_thin_defensive_windows_before_gpt(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_expand_defense",
            analysisJobId="analysis_expand_defense",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {
                    **_clip("thin_steal", 20.4, 0.91),
                    "label": "Steal",
                    "end": 20.95,
                    "eventCenter": 20.5,
                    "watchability": 0.9,
                    "motionScore": 0.92,
                    "audioPeak": 0.62,
                },
            ],
        )

        expanded = expand_shot_candidate_windows_for_source_context(request, source_duration_seconds=60.0)
        steal = expanded.clips[0]
        hints = gpt_reranker._candidate_quality_hints(steal)
        sampled = gpt_reranker._quality_filtered_sampled_clips(expanded.clips, max_clips=1)
        sampled_roles = [role for role, _ in gpt_reranker._sample_times_for_clip(steal, 6)]

        self.assertLess(steal.start, 20.4)
        self.assertGreater(steal.end, 20.95)
        self.assertGreaterEqual(steal.eventCenter - steal.start, 1.6)
        self.assertGreaterEqual(steal.end - steal.eventCenter, 1.2)
        self.assertTrue(hints["defensiveEventLike"])
        self.assertTrue(hints["timingWindowOk"])
        self.assertEqual([clip.id for clip in sampled], ["thin_steal"])
        self.assertIn("possessionChange", sampled_roles)

    def test_blocked_shot_uses_defensive_context_and_keyframes_before_gpt(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_expand_blocked_shot",
            analysisJobId="analysis_expand_blocked_shot",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {
                    **_clip("thin_blocked_shot", 32.4, 0.91),
                    "label": "Blocked Shot",
                    "end": 33.05,
                    "eventCenter": 32.55,
                    "watchability": 0.9,
                    "motionScore": 0.93,
                    "audioPeak": 0.64,
                },
            ],
        )

        expanded = expand_shot_candidate_windows_for_source_context(request, source_duration_seconds=60.0)
        block = expanded.clips[0]
        hints = gpt_reranker._candidate_quality_hints(block)
        sampled_roles = [role for role, _ in gpt_reranker._sample_times_for_clip(block, 10)]

        self.assertLess(block.start, 32.4)
        self.assertGreater(block.end, 33.05)
        self.assertGreaterEqual(block.eventCenter - block.start, 1.6)
        self.assertGreaterEqual(block.end - block.eventCenter, 1.2)
        self.assertTrue(hints["shotLike"])
        self.assertTrue(hints["defensiveEventLike"])
        self.assertTrue(hints["timingWindowOk"])
        self.assertIn("challenge", sampled_roles)
        self.assertIn("defenseOutcome", sampled_roles)
        self.assertNotIn("shotArcEarly", sampled_roles)
        self.assertNotIn("rimEntry", sampled_roles)

    def test_mixed_defensive_shot_labels_use_defensive_context_before_gpt(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_expand_mixed_defense",
            analysisJobId="analysis_expand_mixed_defense",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[
                {
                    **_clip("steal_finish", 24.3, 0.91),
                    "label": "Steal Finish",
                    "end": 24.95,
                    "eventCenter": 24.42,
                    "watchability": 0.91,
                    "motionScore": 0.93,
                    "audioPeak": 0.62,
                },
            ],
        )

        expanded = expand_shot_candidate_windows_for_source_context(request, source_duration_seconds=60.0)
        steal_finish = expanded.clips[0]
        hints = gpt_reranker._candidate_quality_hints(steal_finish)
        sampled = gpt_reranker._quality_filtered_sampled_clips(expanded.clips, max_clips=1)
        sample_times = gpt_reranker._sample_times_for_clip(steal_finish, 10)
        sampled_roles = [role for role, _ in sample_times]
        sampled_frames = [
            SampledFrame(clip_id="steal_finish", role=role, time_seconds=second, data_url="data:image/jpeg;base64,ZA==")
            for role, second in sample_times
        ]

        self.assertLess(steal_finish.start, 24.3)
        self.assertGreater(steal_finish.end, 24.95)
        self.assertTrue(hints["shotLike"])
        self.assertTrue(hints["defensiveEventLike"])
        self.assertTrue(hints["timingWindowOk"])
        self.assertEqual([clip.id for clip in sampled], ["steal_finish"])
        self.assertIn("challenge", sampled_roles)
        self.assertIn("possessionChange", sampled_roles)
        self.assertIn("defenseOutcome", sampled_roles)
        self.assertNotIn("shotArcEarly", sampled_roles)
        self.assertNotIn("rimEntry", sampled_roles)
        self.assertEqual(gpt_reranker._missing_shot_context_keyframes([steal_finish], sampled_frames, 10), {})

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

    def test_revision_patch_payload_filters_selected_team_candidates(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        request = _team_targeted_request()
        job = build_edit_job(request, "edit_revision_team_payload")

        payload = _build_revision_patch_payload(job, ReviseEditJobRequest(command="make_more_hype"), settings)
        compact_input = json.loads(payload["input"][0]["content"][0]["text"])
        compact_clip_ids = [clip["clipId"] for clip in compact_input["candidateClips"]]
        by_id = {clip["clipId"]: clip for clip in compact_input["candidateClips"]}

        self.assertEqual(compact_input["teamTargeting"]["teamId"], "team_dark")
        self.assertIn("dark_make", compact_clip_ids)
        self.assertNotIn("uncertain_make", compact_clip_ids)
        self.assertNotIn("light_make", compact_clip_ids)
        self.assertEqual(by_id["dark_make"]["teamAttributionStatus"], "matched")
        self.assertEqual(by_id["dark_make"]["teamEvidence"]["status"], "evidence_backed")
        self.assertEqual(compact_input["agentTemplateCookbook"]["teamTargeting"]["teamId"], "team_dark")
        self.assertIn("teamEvidence.status=evidence_backed", payload["instructions"])
        self.assertIn("render-eligible clip IDs", payload["instructions"])
        self.assertIn("weak or uncertain team-attribution clips only as review-worthy candidates", payload["instructions"])

    def test_revision_patch_request_rejects_opponent_clip_for_selected_team(self) -> None:
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
        request = _team_targeted_request()
        job = build_edit_job(request, "edit_revision_team_patch_guard")
        opponent_clip = next(clip for clip in job.request.clips if clip.id == "light_make")
        opponent_plan_clip = job.plan.clips[0].model_dump(mode="json")
        opponent_plan_clip.update(
            {
                "clipId": opponent_clip.id,
                "sourceStart": opponent_clip.start,
                "sourceEnd": opponent_clip.end,
                "eventCenter": opponent_clip.eventCenter,
                "label": opponent_clip.label,
                "caption": "BUCKET",
                "timelineStart": 0.0,
                "timelineEnd": opponent_clip.duration,
            }
        )

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            compact_input = json.loads(payload["input"][0]["content"][0]["text"])
            self.assertNotIn("light_make", [clip["clipId"] for clip in compact_input["candidateClips"]])
            return {
                "output_text": json.dumps(
                    {
                        "version": "edit-plan-patch-v1",
                        "baseEditPlanId": job.edit_job_id,
                        "revisionIntent": "make_more_hype",
                        "summary": "Invalid opponent clip should be rejected.",
                        "operations": [
                            {
                                "op": "replace",
                                "path": "/clips",
                                "value": [opponent_plan_clip],
                                "reason": "Use the strongest-looking clip.",
                            }
                        ],
                        "requiresRerender": True,
                    }
                )
            }

        patch = request_gpt_edit_plan_patch(job, ReviseEditJobRequest(command="make_more_hype"), settings, fake_response_client)

        self.assertIsNone(patch)

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
                "shotResultEvidence",
                "shotTrackingEvidence",
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

    def test_pro_sampling_adds_shot_setup_and_rim_entry_path_roles(self) -> None:
        request = _request()
        clip = request.clips[0]

        pro_samples = gpt_reranker._sample_times_for_clip(clip, 10)
        roles = [role for role, _ in pro_samples]

        self.assertIn("preEvent", roles)
        self.assertIn("release", roles)
        self.assertIn("shotArcEarly", roles)
        self.assertIn("shotArcLate", roles)
        self.assertIn("rimApproach", roles)
        self.assertIn("rimEntry", roles)
        self.assertIn("belowRim", roles)
        self.assertLess(dict(pro_samples)["preEvent"], clip.eventCenter)
        self.assertLess(dict(pro_samples)["release"], clip.eventCenter)
        self.assertLess(dict(pro_samples)["shotArcEarly"], clip.eventCenter)
        self.assertLess(dict(pro_samples)["shotArcLate"], clip.eventCenter)
        self.assertLessEqual(dict(pro_samples)["rimApproach"], clip.eventCenter)
        self.assertGreaterEqual(clip.eventCenter - dict(pro_samples)["release"], 0.9)
        self.assertGreater(dict(pro_samples)["shotArcLate"], dict(pro_samples)["shotArcEarly"])
        self.assertGreaterEqual(dict(pro_samples)["rimApproach"], dict(pro_samples)["shotArcLate"])
        self.assertGreater(dict(pro_samples)["rimEntry"], dict(pro_samples)["rimApproach"])
        self.assertLessEqual(dict(pro_samples)["rimEntry"], clip.eventCenter + 0.2)
        self.assertGreater(dict(pro_samples)["belowRim"], dict(pro_samples)["rimEntry"])
        sample_times = [second for _, second in pro_samples]
        self.assertEqual(sample_times, sorted(sample_times))

    def test_shot_sampling_treats_event_center_as_rim_result_anchor(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_result_anchor",
            analysisJobId="analysis_result_anchor",
            installId="install-123",
            preset="personal_highlight",
            targetDurationSeconds=15,
            planTier="pro",
            clips=[{**_clip("result_anchor", 8.0, 0.98), "end": 12.5, "eventCenter": 10.0}],
        )
        clip = request.clips[0]

        samples = dict(gpt_reranker._sample_times_for_clip(clip, 10))

        self.assertGreaterEqual(clip.eventCenter - samples["release"], 0.9)
        self.assertLess(samples["shotArcEarly"], clip.eventCenter)
        self.assertLess(samples["shotArcLate"], clip.eventCenter)
        self.assertLessEqual(samples["rimApproach"], clip.eventCenter)
        self.assertGreater(samples["rimEntry"], samples["rimApproach"])
        self.assertLessEqual(samples["rimEntry"], clip.eventCenter + 0.2)
        self.assertGreater(samples["belowRim"], samples["rimEntry"])

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
                                "shotResultEvidence": _shot_result_evidence(),
                                "shotTrackingEvidence": _shot_tracking_evidence(
                                    ballVisibleFrameRoles=["eventCenter", "finish"],
                                    rimVisibleFrameRoles=["finish"],
                                    releaseFrameRole="eventCenter",
                                    resultFrameRole="finish",
                                    ballEntersRimFrameRole="finish",
                                ),
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

    def test_gpt_decision_citing_unsampled_frame_roles_is_rejected(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=1,
            paid_max_clips=24,
            free_frames_per_clip=3,
            paid_frames_per_clip=5,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            clip = clips[0]
            return [
                SampledFrame(clip_id=clip.id, role="start", time_seconds=clip.start, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clip.id, role="eventCenter", time_seconds=clip.eventCenter, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clip.id, role="finish", time_seconds=clip.end - 0.05, data_url="data:image/jpeg;base64,ZmFrZQ=="),
            ]

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
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
                                "reason": "Claims rim proof that was not actually sampled.",
                                "storyRole": "peak",
                                "qualitySignals": _quality_signals(),
                                "shotResultEvidence": _shot_result_evidence(
                                    ballApproachFrameRole="rimApproach",
                                    rimEntryFrameRole="rimEntry",
                                    ballBelowRimOrNetFrameRole="belowRim",
                                ),
                                "shotTrackingEvidence": _shot_tracking_evidence(
                                    ballVisibleFrameRoles=["release", "shotArcEarly", "rim"],
                                    rimVisibleFrameRoles=["rim", "postOutcome"],
                                    releaseFrameRole="release",
                                    resultFrameRole="rim",
                                    ballEntersRimFrameRole="rim",
                                ),
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
                        "summary": "ok",
                    }
                )
            }

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 1), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(result.gptRerankSummary.status, "applied")
        self.assertEqual(result.gptRerankSummary.keptClipIds, [])
        self.assertEqual(result.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(result.gptRerankSummary.rejectedReasonCounts.get("gpt_cited_unsampled_frame_role"), 1)

    def test_gpt_decision_must_use_rich_sampled_shot_roles_when_available(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=1,
            paid_max_clips=24,
            free_frames_per_clip=10,
            paid_frames_per_clip=10,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            clip = clips[0]
            return [
                SampledFrame(clip_id=clip.id, role=role, time_seconds=second, data_url="data:image/jpeg;base64,ZmFrZQ==")
                for role, second in gpt_reranker._sample_times_for_clip(clip, frames_per_clip)
            ]

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            compact_input = json.loads(payload["input"][0]["content"][0]["text"])
            self.assertTrue(compact_input["shotTrackerRules"]["mustUseRichSampledShotRolesWhenPresent"])
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
                                "reason": "Claims a made shot but ignores the sampled release/rim roles.",
                                "storyRole": "peak",
                                "qualitySignals": _quality_signals(),
                                "shotResultEvidence": _shot_result_evidence(
                                    ballApproachFrameRole="rimApproach",
                                    rimEntryFrameRole="rimEntry",
                                    ballBelowRimOrNetFrameRole="belowRim",
                                ),
                                "shotTrackingEvidence": _shot_tracking_evidence(),
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
                        "summary": "ok",
                    }
                )
            }

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 1), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(result.gptRerankSummary.status, "applied")
        self.assertEqual(result.gptRerankSummary.keptClipIds, [])
        self.assertEqual(result.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(result.gptRerankSummary.rejectedReasonCounts.get("gpt_ignored_sampled_release_frame"), 1)

    def test_gpt_decision_must_use_sampled_rim_entry_path_roles_when_available(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=1,
            paid_max_clips=24,
            free_frames_per_clip=10,
            paid_frames_per_clip=10,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            clip = clips[0]
            return [
                SampledFrame(clip_id=clip.id, role=role, time_seconds=second, data_url="data:image/jpeg;base64,ZmFrZQ==")
                for role, second in gpt_reranker._sample_times_for_clip(clip, frames_per_clip)
            ]

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            compact_input = json.loads(payload["input"][0]["content"][0]["text"])
            self.assertEqual(compact_input["shotTrackerRules"]["requiredMadeShotTracking"]["dedicatedRimEntryPathRoles"], ["rimApproach", "rimEntry", "belowRim"])
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
                                "reason": "Claims the make but ignores the sampled rim-entry frame.",
                                "storyRole": "peak",
                                "qualitySignals": _quality_signals(),
                                "shotResultEvidence": _shot_result_evidence(
                                    ballApproachFrameRole="rimApproach",
                                    rimEntryFrameRole="finish",
                                    ballBelowRimOrNetFrameRole="belowRim",
                                ),
                                "shotTrackingEvidence": _shot_tracking_evidence(
                                    ballVisibleFrameRoles=["release", "shotArcLate", "rimApproach", "rimEntry", "belowRim"],
                                    rimVisibleFrameRoles=["rimEntry", "belowRim"],
                                    releaseFrameRole="release",
                                    resultFrameRole="rimEntry",
                                    ballEntersRimFrameRole="rimEntry",
                                ),
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
                        "summary": "ok",
                    }
                )
            }

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 1), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(result.gptRerankSummary.status, "applied")
        self.assertEqual(result.gptRerankSummary.keptClipIds, [])
        self.assertEqual(result.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(result.gptRerankSummary.rejectedReasonCounts.get("gpt_ignored_sampled_rim_entry_frame"), 1)

    def test_gpt_decision_without_rim_entry_sequence_is_rejected(self) -> None:
        settings = GPTHighlightRerankerSettings(
            enabled=True,
            api_key="unit-test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=1.0,
            max_output_tokens=512,
            free_max_clips=1,
            paid_max_clips=24,
            free_frames_per_clip=3,
            paid_frames_per_clip=5,
            frame_width=512,
            jpeg_quality=5,
            max_image_bytes=180_000,
            image_detail="low",
        )
        original_extract = gpt_reranker._extract_candidate_keyframes

        def fake_extract(source_path, clips, frames_per_clip, rerank_settings):
            clip = clips[0]
            return [
                SampledFrame(clip_id=clip.id, role="start", time_seconds=clip.start, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clip.id, role="eventCenter", time_seconds=clip.eventCenter, data_url="data:image/jpeg;base64,ZmFrZQ=="),
                SampledFrame(clip_id=clip.id, role="finish", time_seconds=clip.end - 0.05, data_url="data:image/jpeg;base64,ZmFrZQ=="),
            ]

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
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
                                "reason": "Claims a made shot without an entry sequence.",
                                "storyRole": "peak",
                                "qualitySignals": _quality_signals(),
                                "shotResultEvidence": _shot_result_evidence(
                                    rimEntrySequence="unclear",
                                    ballApproachFrameRole=None,
                                    rimEntryFrameRole=None,
                                    ballBelowRimOrNetFrameRole=None,
                                    rimEntrySequenceConfidence=0.25,
                                ),
                                "shotTrackingEvidence": _shot_tracking_evidence(),
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
                        "summary": "ok",
                    }
                )
            }

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                result = gpt_reranker.rerank_edit_request_with_gpt(_request("free", 1), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(result.gptRerankSummary.status, "applied")
        self.assertEqual(result.gptRerankSummary.keptClipIds, [])
        self.assertEqual(result.gptRerankSummary.fallbackReason, "all_clips_rejected")
        self.assertEqual(result.gptRerankSummary.rejectedReasonCounts.get("made_rim_entry_sequence_not_visible"), 1)

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
                    roles.insert(5, "postOutcome")
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
                                    "releaseVisible": True,
                                    "shotArcVisible": True,
                                    "eventVisible": True,
                                    "outcomeVisible": True,
                                    "rimResultVisible": True,
                                    "ballPathVisible": True,
                                    "playerControlVisible": True,
                                    "cleanCamera": True,
                                    "fullPlayContext": True,
                                    "reason": "Complete shot context.",
                                },
                                "shotResultEvidence": _shot_result_evidence(
                                    ballApproachFrameRole="release",
                                    rimEntryFrameRole="rim",
                                    ballBelowRimOrNetFrameRole="postOutcome",
                                ),
                                "shotTrackingEvidence": _shot_tracking_evidence(
                                    ballVisibleFrameRoles=["release", "outcome", "rim"],
                                    rimVisibleFrameRoles=["rim", "postOutcome"],
                                    releaseFrameRole="release",
                                    resultFrameRole="rim",
                                    ballEntersRimFrameRole="rim",
                                ),
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

    def test_incomplete_gpt_decisions_fallback_without_dropping_sampled_candidates(self) -> None:
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
                                "shotResultEvidence": _shot_result_evidence(),
                                "shotTrackingEvidence": _shot_tracking_evidence(),
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

        self.assertEqual(result.gptRerankSummary.status, "fallback")
        self.assertEqual(result.gptRerankSummary.fallbackReason, "incomplete_gpt_decisions")
        self.assertEqual(result.gptRerankSummary.keptClipIds, observed_clip_ids)
        self.assertEqual(result.gptRerankSummary.rejectedClipIds, [])
        self.assertEqual([clip.id for clip in result.clips], observed_clip_ids)

    def test_unsampled_existing_clip_decision_falls_back_without_applying_gpt(self) -> None:
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
                "shotResultEvidence": _shot_result_evidence(),
                "shotTrackingEvidence": _shot_tracking_evidence(),
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
        self.assertEqual(result.gptRerankSummary.status, "fallback")
        self.assertEqual(result.gptRerankSummary.fallbackReason, "incomplete_gpt_decisions")
        self.assertEqual(result.gptRerankSummary.keptClipIds, ["c0", "c1", "c2"])
        self.assertEqual(result.gptRerankSummary.rejectedClipIds, [])
        self.assertEqual([clip.id for clip in result.clips], ["c0", "c1", "c2"])

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
                "shotResultEvidence": _shot_result_evidence(),
                "shotTrackingEvidence": _shot_tracking_evidence(),
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
                                    "releaseVisible": True,
                                    "shotArcVisible": True,
                                    "eventVisible": True,
                                    "outcomeVisible": True,
                                    "rimResultVisible": True,
                                    "ballPathVisible": True,
                                    "playerControlVisible": True,
                                    "cleanCamera": True,
                                    "fullPlayContext": True,
                                    "reason": "Shows the play before and after the make.",
                                },
                                "shotResultEvidence": _shot_result_evidence(),
                                "shotTrackingEvidence": _shot_tracking_evidence(),
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

    def test_sampling_reserves_buried_defensive_candidates_for_gpt_review(self) -> None:
        scoring_clips = [_clip(f"make_{index}", float(index * 7), 0.99 - (index * 0.001)) for index in range(27)]
        defensive_clips = [
            {**_clip("late_block", 222.0, 0.69), "label": "Block"},
            {**_clip("late_steal", 230.0, 0.68), "label": "Steal"},
            {**_clip("late_stop", 238.0, 0.66), "label": "Defensive Stop"},
        ]
        request = CreateEditJobRequest(
            videoId="video_defense_pool",
            analysisJobId="analysis_defense_pool",
            installId="install-123",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            userPrompt="focus on defense",
            clips=[*scoring_clips, *defensive_clips],
        )

        sampled = gpt_reranker._quality_filtered_sampled_clips(
            gpt_reranker.rank_clips(request.clips),
            20,
            request=request,
        )
        sampled_ids = [clip.id for clip in sampled]

        self.assertEqual(len(sampled), 20)
        self.assertIn("late_block", sampled_ids)
        self.assertIn("late_steal", sampled_ids)
        self.assertIn("late_stop", sampled_ids)
        self.assertLess(len([clip_id for clip_id in sampled_ids if clip_id.startswith("make_")]), 20)

    def test_defensive_candidates_use_possession_change_keyframes(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_defense_roles",
            analysisJobId="analysis_defense_roles",
            installId="install-123",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[{**_clip("steal", 10.0, 0.86), "label": "Steal"}],
        )

        roles = [role for role, _ in gpt_reranker._sample_times_for_clip(request.clips[0], 10)]

        self.assertIn("eventCenter", roles)
        self.assertIn("challenge", roles)
        self.assertIn("possessionChange", roles)
        self.assertIn("recovery", roles)
        self.assertIn("defenseOutcome", roles)
        self.assertNotIn("shotArcEarly", roles)
        self.assertNotIn("rimEntry", roles)

    def test_block_candidates_use_defensive_challenge_keyframes(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_block_roles",
            analysisJobId="analysis_block_roles",
            installId="install-123",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[{**_clip("block", 10.0, 0.86), "label": "Block"}],
        )

        roles = [role for role, _ in gpt_reranker._sample_times_for_clip(request.clips[0], 10)]

        self.assertIn("challenge", roles)
        self.assertIn("defenseOutcome", roles)
        self.assertNotIn("shotArcEarly", roles)
        self.assertNotIn("rimEntry", roles)

    def test_blocked_shot_candidates_use_defensive_challenge_keyframes(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_blocked_shot_roles",
            analysisJobId="analysis_blocked_shot_roles",
            installId="install-123",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[{**_clip("blocked_shot", 10.0, 0.86), "label": "Blocked Shot"}],
        )

        roles = [role for role, _ in gpt_reranker._sample_times_for_clip(request.clips[0], 10)]

        self.assertIn("challenge", roles)
        self.assertIn("defenseOutcome", roles)
        self.assertNotIn("shotArcEarly", roles)
        self.assertNotIn("rimEntry", roles)

    def test_defensive_keep_requires_sampled_possession_change_roles(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_defense_validation",
            analysisJobId="analysis_defense_validation",
            installId="install-123",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[{**_clip("steal", 10.0, 0.86), "label": "Steal"}],
        )
        sampled_roles = ["start", "eventCenter", "finish", "challenge", "possessionChange", "recovery"]
        weak_decision = GPTHighlightClipDecision(
            clipId="steal",
            keep=True,
            highlightScore=0.88,
            watchabilityScore=0.82,
            basketballEvent="Steal",
            outcome="steal",
            caption="COOKIES",
            reason="GPT says the defender takes the ball but omits the possession-change frame.",
            qualitySignals=_quality_signals(
                releaseVisible=False,
                shotArcVisible=False,
                rimResultVisible=False,
                reason="Defender and ball are visible.",
            ),
            shotResultEvidence=_shot_result_evidence(
                releaseToRimContinuity="missing",
                rimResultEvidence="unclear",
                outcomeConfidence=0.0,
                rimEntrySequence="unclear",
                ballApproachFrameRole=None,
                rimEntryFrameRole=None,
                ballBelowRimOrNetFrameRole=None,
                rimEntrySequenceConfidence=0.0,
            ),
            shotTrackingEvidence=_shot_tracking_evidence(
                ballVisibleFrameRoles=["challenge"],
                rimVisibleFrameRoles=[],
                releaseFrameRole=None,
                resultFrameRole=None,
                ballEntersRimFrameRole=None,
                trajectoryContinuity="partial",
            ),
            suggestedEdit=GPTHighlightSuggestedEdit(cropFocus="ball"),
        )
        complete_decision = GPTHighlightClipDecision(
            **{
                **weak_decision.model_dump(mode="json"),
                "shotResultEvidence": _shot_result_evidence(
                    releaseToRimContinuity="missing",
                    rimResultEvidence="unclear",
                    outcomeConfidence=0.82,
                    rimEntrySequence="unclear",
                    ballApproachFrameRole=None,
                    rimEntryFrameRole=None,
                    ballBelowRimOrNetFrameRole=None,
                    rimEntrySequenceConfidence=0.0,
                ),
                "shotTrackingEvidence": _shot_tracking_evidence(
                    ballVisibleFrameRoles=["challenge", "possessionChange", "recovery"],
                    rimVisibleFrameRoles=[],
                    releaseFrameRole=None,
                    resultFrameRole="recovery",
                    ballEntersRimFrameRole=None,
                    trajectoryContinuity="partial",
                ),
            }
        )
        low_confidence_decision = GPTHighlightClipDecision(
            **{
                **complete_decision.model_dump(mode="json"),
                "shotResultEvidence": _shot_result_evidence(
                    releaseToRimContinuity="missing",
                    rimResultEvidence="unclear",
                    outcomeConfidence=0.41,
                    rimEntrySequence="unclear",
                    ballApproachFrameRole=None,
                    rimEntryFrameRole=None,
                    ballBelowRimOrNetFrameRole=None,
                    rimEntrySequenceConfidence=0.0,
                ),
            }
        )
        rejected = apply_gpt_highlight_rerank(
            request,
            [weak_decision],
            "gpt-test",
            1,
            len(sampled_roles),
            sampled_frame_roles_by_clip={"steal": sampled_roles},
        )
        rejected_low_confidence = apply_gpt_highlight_rerank(
            request,
            [low_confidence_decision],
            "gpt-test",
            1,
            len(sampled_roles),
            sampled_frame_roles_by_clip={"steal": sampled_roles},
        )
        kept = apply_gpt_highlight_rerank(
            request,
            [complete_decision],
            "gpt-test",
            1,
            len(sampled_roles),
            sampled_frame_roles_by_clip={"steal": sampled_roles},
        )

        self.assertEqual(rejected.clips, [])
        self.assertEqual(rejected.gptRerankSummary.rejectedReasonCounts["missing_defensive_possession_change_frame"], 1)
        self.assertEqual(rejected_low_confidence.clips, [])
        self.assertEqual(rejected_low_confidence.gptRerankSummary.rejectedReasonCounts["low_defensive_outcome_confidence"], 1)
        self.assertEqual([clip.id for clip in kept.clips], ["steal"])

    def test_blocked_keep_requires_sampled_challenge_and_outcome_roles(self) -> None:
        request = CreateEditJobRequest(
            videoId="video_block_validation",
            analysisJobId="analysis_block_validation",
            installId="install-123",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=[{**_clip("block", 10.0, 0.86), "label": "Block"}],
        )
        sampled_roles = ["start", "eventCenter", "finish", "challenge", "defenseOutcome"]
        weak_decision = GPTHighlightClipDecision(
            clipId="block",
            keep=True,
            highlightScore=0.88,
            watchabilityScore=0.82,
            basketballEvent="Block",
            outcome="blocked",
            caption="LOCKDOWN",
            reason="GPT says the shot was blocked but omits the challenge frame.",
            qualitySignals=_quality_signals(
                releaseVisible=False,
                shotArcVisible=False,
                reason="The block event and outcome are visible.",
            ),
            shotResultEvidence=_shot_result_evidence(
                releaseToRimContinuity="partial",
                rimResultEvidence="blocked",
                outcomeConfidence=0.82,
                rimEntrySequence="blocked",
                ballApproachFrameRole=None,
                rimEntryFrameRole=None,
                ballBelowRimOrNetFrameRole=None,
                rimEntrySequenceConfidence=0.0,
            ),
            shotTrackingEvidence=_shot_tracking_evidence(
                ballVisibleFrameRoles=["eventCenter"],
                rimVisibleFrameRoles=[],
                releaseFrameRole=None,
                resultFrameRole=None,
                ballEntersRimFrameRole=None,
                trajectoryContinuity="partial",
            ),
            suggestedEdit=GPTHighlightSuggestedEdit(cropFocus="ball"),
        )
        complete_decision = GPTHighlightClipDecision(
            **{
                **weak_decision.model_dump(mode="json"),
                "shotTrackingEvidence": _shot_tracking_evidence(
                    ballVisibleFrameRoles=["challenge", "defenseOutcome"],
                    rimVisibleFrameRoles=[],
                    releaseFrameRole=None,
                    resultFrameRole="defenseOutcome",
                    ballEntersRimFrameRole=None,
                    trajectoryContinuity="partial",
                ),
            }
        )
        no_ball_path_decision = GPTHighlightClipDecision(
            **{
                **complete_decision.model_dump(mode="json"),
                "qualitySignals": _quality_signals(
                    releaseVisible=False,
                    shotArcVisible=False,
                    ballPathVisible=False,
                    reason="The challenge is visible, but the ball path is not.",
                ),
            }
        )

        rejected = apply_gpt_highlight_rerank(
            request,
            [weak_decision],
            "gpt-test",
            1,
            len(sampled_roles),
            sampled_frame_roles_by_clip={"block": sampled_roles},
        )
        rejected_no_ball_path = apply_gpt_highlight_rerank(
            request,
            [no_ball_path_decision],
            "gpt-test",
            1,
            len(sampled_roles),
            sampled_frame_roles_by_clip={"block": sampled_roles},
        )
        kept = apply_gpt_highlight_rerank(
            request,
            [complete_decision],
            "gpt-test",
            1,
            len(sampled_roles),
            sampled_frame_roles_by_clip={"block": sampled_roles},
        )

        self.assertEqual(rejected.clips, [])
        self.assertEqual(rejected.gptRerankSummary.rejectedReasonCounts["missing_block_challenge_frame"], 1)
        self.assertEqual(rejected_no_ball_path.clips, [])
        self.assertEqual(rejected_no_ball_path.gptRerankSummary.rejectedReasonCounts["missing_block_ball_control"], 1)
        self.assertEqual([clip.id for clip in kept.clips], ["block"])

    def test_free_and_pro_sampling_limits(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()

        self.assertEqual(settings.limits_for("free"), (60, 10))
        self.assertGreaterEqual(settings.limits_for("pro")[0], 20)
        self.assertLessEqual(settings.limits_for("pro")[0], 60)
        self.assertGreaterEqual(settings.limits_for("pro")[1], 5)
        self.assertLessEqual(settings.limits_for("pro")[1], 10)
        self.assertEqual(settings.timeout_seconds, 60.0)
        self.assertEqual(settings.max_output_tokens, 12000)

    def test_free_sampling_reviews_full_analysis_pool_by_default(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()
        max_clips, _ = settings.limits_for("free")
        request = _request("free", 60)

        sampled = gpt_reranker._quality_filtered_sampled_clips(
            gpt_reranker.rank_clips(request.clips),
            max_clips,
        )

        self.assertEqual(max_clips, 60)
        self.assertEqual(len(sampled), 60)
        self.assertEqual(sampled[0].id, "c0")
        self.assertEqual(sampled[-1].id, "c59")

    def test_free_sampling_candidate_cap_is_generous_but_bounded(self) -> None:
        env_keys = ("HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE", "HOOPS_GPT_HIGHLIGHT_RERANK_FREE_MAX_CLIPS")
        old_values = {key: os.environ.get(key) for key in env_keys}
        os.environ["HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE"] = "999"
        os.environ["HOOPS_GPT_HIGHLIGHT_RERANK_FREE_MAX_CLIPS"] = "999"
        try:
            settings = GPTHighlightRerankerSettings.from_env()
        finally:
            for key, old_value in old_values.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

        self.assertEqual(settings.limits_for("free")[0], 60)

    def test_sampling_reserves_block_and_steal_families_for_gpt_review(self) -> None:
        scoring = [
            _clip(f"score_{index}", float(index * 7), 0.99 - (index * 0.01))
            for index in range(8)
        ]
        clips = [
            *scoring,
            _labeled_clip("block_1", 80.0, 0.91, "Block"),
            _labeled_clip("block_2", 87.0, 0.90, "Blocked shot"),
            _labeled_clip("block_3", 94.0, 0.89, "Contest block"),
            _labeled_clip("steal_1", 101.0, 0.70, "Steal"),
        ]
        request = CreateEditJobRequest(
            videoId="video_123",
            analysisJobId="analysis_123",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            clips=clips,
        )

        sampled = gpt_reranker._quality_filtered_sampled_clips(
            gpt_reranker.rank_clips(request.clips),
            8,
            request=request,
        )
        sampled_ids = {clip.id for clip in sampled}

        self.assertIn("block_1", sampled_ids)
        self.assertIn("steal_1", sampled_ids)
        self.assertIn("block_2", sampled_ids)
        self.assertNotIn("block_3", sampled_ids)
        self.assertNotIn("score_5", sampled_ids)

    def test_selected_team_sampling_bounds_unreviewed_uncertain_clip_reserve(self) -> None:
        uncertain = [
            {
                **_clip(f"uncertain_{index}", float(index * 7), 0.99 - (index * 0.001)),
                "teamAttribution": {
                    "teamId": "team_dark",
                    "label": "Dark jerseys",
                    "colorLabel": "black",
                    "confidence": 0.7,
                    "source": "quick_scan",
                },
            }
            for index in range(10)
        ]
        matched = [
            {
                **_clip(f"matched_{index}", 100.0 + float(index * 7), 0.86 - (index * 0.001)),
                "teamAttribution": {
                    "teamId": "team_dark",
                    "label": "Dark jerseys",
                    "colorLabel": "black",
                    "confidence": 0.93,
                    "source": "quick_scan",
                    "evidenceFrameRefs": [f"matched_{index}_setup", f"matched_{index}_result"],
                    "evidenceRoleGroups": ["setup", "outcome"],
                },
            }
            for index in range(8)
        ]
        request = CreateEditJobRequest(
            videoId="video_team_sampling",
            analysisJobId="analysis_team_sampling",
            installId="install-123",
            sourceObjectKey="uploads/source.mp4",
            preset="personal_highlight",
            targetDurationSeconds=30,
            planTier="free",
            teamSelection={
                "mode": "team",
                "teamId": "team_dark",
                "label": "Dark jerseys",
                "colorLabel": "black",
                "confidenceThreshold": 0.85,
                "includeUncertain": True,
            },
            clips=[*uncertain, *matched],
        )

        sampled = gpt_reranker._quality_filtered_sampled_clips(
            gpt_reranker.rank_clips(request.clips),
            8,
            request=request,
        )
        sampled_ids = [clip.id for clip in sampled]

        self.assertEqual(len(sampled), 8)
        self.assertEqual(len([clip_id for clip_id in sampled_ids if clip_id.startswith("uncertain_")]), 2)
        self.assertEqual(len([clip_id for clip_id in sampled_ids if clip_id.startswith("matched_")]), 6)

    def test_default_model_prioritizes_full_quality_vision_editor(self) -> None:
        model_env_keys = ("HOOPS_AI_CLIP_GPT_MODEL", "HOOPS_GPT_HIGHLIGHT_RERANK_MODEL")
        old_values = {key: os.environ.get(key) for key in model_env_keys}
        for key in model_env_keys:
            os.environ.pop(key, None)
        try:
            settings = GPTHighlightRerankerSettings.from_env()
        finally:
            for key, old_value in old_values.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

        self.assertEqual(settings.model, "gpt-4.1")

    def test_default_visual_sampling_prioritizes_ball_and_rim_detail(self) -> None:
        env_keys = ("HOOPS_GPT_HIGHLIGHT_RERANK_FRAME_WIDTH", "HOOPS_GPT_HIGHLIGHT_RERANK_MAX_IMAGE_BYTES")
        old_values = {key: os.environ.get(key) for key in env_keys}
        for key in env_keys:
            os.environ.pop(key, None)
        try:
            settings = GPTHighlightRerankerSettings.from_env()
        finally:
            for key, old_value in old_values.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

        self.assertGreaterEqual(settings.frame_width, 1024)
        self.assertGreaterEqual(settings.max_image_bytes, 750_000)

    def test_visual_sampling_env_allows_quality_beta_high_resolution_cap(self) -> None:
        env_keys = ("HOOPS_GPT_HIGHLIGHT_RERANK_FRAME_WIDTH", "HOOPS_GPT_HIGHLIGHT_RERANK_MAX_IMAGE_BYTES")
        old_values = {key: os.environ.get(key) for key in env_keys}
        os.environ["HOOPS_GPT_HIGHLIGHT_RERANK_FRAME_WIDTH"] = "4096"
        os.environ["HOOPS_GPT_HIGHLIGHT_RERANK_MAX_IMAGE_BYTES"] = "9999999"
        try:
            settings = GPTHighlightRerankerSettings.from_env()
        finally:
            for key, old_value in old_values.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

        self.assertEqual(settings.frame_width, 1280)
        self.assertEqual(settings.max_image_bytes, 1_000_000)

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
            compact_input = json.loads(payload["input"][0]["content"][0]["text"])
            required_roles = set(compact_input["shotTrackerRules"]["requiredShotContextKeyframes"])
            result_evidence = _shot_result_evidence()
            tracking_evidence = _shot_tracking_evidence()
            if "outcome" in required_roles:
                result_evidence = _shot_result_evidence(
                    ballApproachFrameRole="eventCenter",
                    rimEntryFrameRole="outcome",
                    ballBelowRimOrNetFrameRole="finish",
                )
                tracking_evidence = _shot_tracking_evidence(
                    ballVisibleFrameRoles=["eventCenter", "outcome", "finish"],
                    rimVisibleFrameRoles=["outcome"],
                    resultFrameRole="outcome",
                    ballEntersRimFrameRole="outcome",
                )
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
                    "shotResultEvidence": result_evidence,
                    "shotTrackingEvidence": tracking_evidence,
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
