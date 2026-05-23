from pathlib import Path
import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "services" / "editing"))
sys.path.insert(0, str(REPO_ROOT / "ios" / "backend"))

from app.editing import CreateEditJobRequest
import editing_app.gpt_reranker as gpt_reranker
from editing_app.gpt_reranker import (
    GPTHighlightRerankerSettings,
    SampledFrame,
    _build_openai_payload,
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
        image_items = [item for item in user_content if item["type"] == "input_image"]

        self.assertIs(payload["store"], False)
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(payload["text"]["format"]["schema"]["required"], ["decisions", "storyOrder", "summary"])
        self.assertEqual(
            set(compact_clip),
            {
                "clipId",
                "start",
                "end",
                "duration",
                "existingLabel",
                "motionScore",
                "audioPeak",
                "confidence",
                "watchability",
                "duplicateGroup",
                "templateContext",
                "sampledFrames",
            },
        )
        self.assertEqual(compact_clip["sampledFrames"], [{"role": "start", "time": 0.0}])
        self.assertEqual(len(image_items), 1)
        self.assertTrue(image_items[0]["image_url"].startswith("data:image/jpeg;base64,"))
        self.assertNotIn("c999", json.dumps(payload))
        self.assertNotIn("sourceObjectKey", str(payload))
        self.assertNotIn("uploads/source.mp4", str(payload))
        self.assertNotIn("https://", str(payload))

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
                "highlightScore",
                "watchabilityScore",
                "basketballEvent",
                "outcome",
                "caption",
                "reason",
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

    def test_sampling_includes_start_event_center_and_finish_roles(self) -> None:
        request = _request()
        clip = request.clips[0]

        free_samples = gpt_reranker._sample_times_for_clip(clip, 3)
        pro_samples = gpt_reranker._sample_times_for_clip(clip, 5)

        self.assertEqual(free_samples, [("start", 0.0), ("event_center", 3.0), ("finish", 5.95)])
        self.assertEqual(len(pro_samples), 5)
        self.assertIn("start", [role for role, _ in pro_samples])
        self.assertIn("event_center", [role for role, _ in pro_samples])
        self.assertIn("finish", [role for role, _ in pro_samples])

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

        self.assertEqual([role for role, _ in samples], ["start", "event_center", "finish"])

    def test_image_detail_env_falls_back_to_low_for_unknown_values(self) -> None:
        old_value = os.environ.get("HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL")
        try:
            for value in ("low", "high", "original", "auto"):
                os.environ["HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL"] = value
                self.assertEqual(GPTHighlightRerankerSettings.from_env().image_detail, value)

            os.environ["HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL"] = "giant"

            settings = GPTHighlightRerankerSettings.from_env()

            self.assertEqual(settings.image_detail, "low")
        finally:
            if old_value is None:
                os.environ.pop("HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL", None)
            else:
                os.environ["HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL"] = old_value

    def test_free_and_pro_sampling_limits(self) -> None:
        settings = GPTHighlightRerankerSettings.from_env()

        self.assertEqual(settings.limits_for("free"), (8, 3))
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
                for index in range(frames_per_clip):
                    frames.append(
                        SampledFrame(
                            clip_id=clip.id,
                            role=f"context_{index}",
                            time_seconds=clip.start + index,
                            data_url="data:image/jpeg;base64,ZmFrZQ==",
                        )
                    )
            return frames

        def fake_response_client(payload, api_key, endpoint, timeout_seconds):
            decisions = [
                {
                    "clipId": clip_id,
                    "keep": True,
                    "highlightScore": 0.9,
                    "watchabilityScore": 0.8,
                    "basketballEvent": "Made Shot",
                    "outcome": "made",
                    "caption": "BUCKET",
                    "reason": "Clear outcome.",
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
            return {"output_text": json.dumps({"decisions": decisions, "storyOrder": observed_clip_ids, "summary": "ok"})}

        try:
            gpt_reranker._extract_candidate_keyframes = fake_extract
            with tempfile.NamedTemporaryFile(suffix=".mp4") as source:
                gpt_reranker.rerank_edit_request_with_gpt(_request("free", 12), Path(source.name), settings, fake_response_client)
                gpt_reranker.rerank_edit_request_with_gpt(_request("pro", 30), Path(source.name), settings, fake_response_client)
        finally:
            gpt_reranker._extract_candidate_keyframes = original_extract

        self.assertEqual(observed_calls, [(8, 3), (24, 5)])


if __name__ == "__main__":
    unittest.main()
