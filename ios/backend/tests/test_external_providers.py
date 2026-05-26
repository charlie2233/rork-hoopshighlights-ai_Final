from __future__ import annotations

import unittest

from app.external_providers import apply_autohighlight_boosts, parse_external_clips_from_payload
from app.models import CloudClip


class ExternalProviderTests(unittest.TestCase):
    def test_parse_external_clips_clamps_duration_and_dedupes(self) -> None:
        payload = {
            "clips": [
                {
                    "startTime": 0.0,
                    "endTime": 30.0,
                    "confidence": 0.92,
                    "label": "Made Shot",
                    "action": "Made Shot",
                    "audioScore": 0.6,
                    "visualScore": 0.9,
                    "motionScore": 0.8,
                    "combinedScore": 0.95,
                    "shouldAutoKeep": True,
                    "shouldEnableSlowMotion": False,
                },
                {
                    "startTime": 1.0,
                    "endTime": 6.0,
                    "confidence": 0.75,
                    "label": "Made Shot",
                    "action": "Made Shot",
                    "audioScore": 0.55,
                    "visualScore": 0.82,
                    "motionScore": 0.72,
                    "combinedScore": 0.8,
                    "shouldAutoKeep": True,
                    "shouldEnableSlowMotion": False,
                },
            ]
        }

        clips = parse_external_clips_from_payload(
            payload,
            duration_seconds=60.0,
            max_clip_duration=8.0,
            clip_limit=8,
        )

        self.assertEqual(len(clips), 1)
        self.assertAlmostEqual(clips[0].endTime - clips[0].startTime, 8.0)
        self.assertEqual(clips[0].label, "Made Shot")

    def test_parse_external_shot_clip_expands_around_provider_event_center(self) -> None:
        payload = {
            "clips": [
                {
                    "startTime": 10.2,
                    "endTime": 10.4,
                    "eventCenter": 10.0,
                    "confidence": 0.91,
                    "label": "Made Shot",
                    "action": "Made Shot",
                    "audioScore": 0.6,
                    "visualScore": 0.9,
                    "motionScore": 0.8,
                    "combinedScore": 0.94,
                    "shouldAutoKeep": True,
                    "shouldEnableSlowMotion": False,
                }
            ]
        }

        clips = parse_external_clips_from_payload(
            payload,
            duration_seconds=60.0,
            max_clip_duration=8.0,
            clip_limit=8,
        )

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].eventCenter, 10.0)
        self.assertLessEqual(clips[0].startTime, 8.0)
        self.assertGreaterEqual(clips[0].endTime, 11.25)

    def test_parse_external_clips_rejects_tiny_provider_windows_without_context(self) -> None:
        payload = {
            "clips": [
                {
                    "startTime": 10.0,
                    "endTime": 10.1,
                    "confidence": 0.99,
                    "label": "Made Shot",
                    "action": "Made Shot",
                    "audioScore": 0.9,
                    "visualScore": 0.9,
                    "motionScore": 0.9,
                    "combinedScore": 0.99,
                    "shouldAutoKeep": True,
                    "shouldEnableSlowMotion": True,
                },
                {
                    "startTime": 14.0,
                    "endTime": 16.7,
                    "confidence": 0.72,
                    "label": "Defense",
                    "action": "Defense",
                    "audioScore": 0.4,
                    "visualScore": 0.62,
                    "motionScore": 0.68,
                    "combinedScore": 0.7,
                    "shouldAutoKeep": True,
                    "shouldEnableSlowMotion": False,
                },
            ]
        }

        clips = parse_external_clips_from_payload(
            payload,
            duration_seconds=60.0,
            min_clip_duration=2.0,
            max_clip_duration=8.0,
            clip_limit=8,
        )

        self.assertEqual([clip.label for clip in clips], ["Defense"])
        self.assertGreaterEqual(clips[0].endTime - clips[0].startTime, 2.0)

    def test_external_dedupe_prefers_complete_event_context_over_thin_overlap(self) -> None:
        payload = {
            "clips": [
                {
                    "startTime": 8.0,
                    "endTime": 10.05,
                    "confidence": 0.99,
                    "label": "Made Shot",
                    "action": "Made Shot",
                    "audioScore": 0.9,
                    "visualScore": 0.85,
                    "motionScore": 0.8,
                    "combinedScore": 0.99,
                    "shouldAutoKeep": True,
                    "shouldEnableSlowMotion": True,
                },
                {
                    "startTime": 9.55,
                    "endTime": 10.25,
                    "eventCenter": 10.0,
                    "confidence": 0.82,
                    "label": "Made Shot",
                    "action": "Made Shot",
                    "audioScore": 0.6,
                    "visualScore": 0.78,
                    "motionScore": 0.72,
                    "combinedScore": 0.74,
                    "shouldAutoKeep": True,
                    "shouldEnableSlowMotion": False,
                },
            ]
        }

        clips = parse_external_clips_from_payload(
            payload,
            duration_seconds=60.0,
            min_clip_duration=2.0,
            max_clip_duration=8.0,
            clip_limit=8,
        )

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].eventCenter, 10.0)
        self.assertLessEqual(clips[0].startTime, 8.0)
        self.assertGreaterEqual(clips[0].endTime, 11.25)

    def test_external_missing_scores_default_to_conservative_non_autokeep(self) -> None:
        payload = {
            "clips": [
                {
                    "startTime": 20.0,
                    "endTime": 24.5,
                    "label": "Highlight",
                    "action": "Highlight",
                }
            ]
        }

        clips = parse_external_clips_from_payload(
            payload,
            duration_seconds=60.0,
            min_clip_duration=2.0,
            max_clip_duration=8.0,
            clip_limit=8,
        )

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].confidence, 0.52)
        self.assertEqual(clips[0].combinedScore, 0.5)
        self.assertFalse(clips[0].shouldAutoKeep)

    def test_apply_autohighlight_boosts_updates_scores(self) -> None:
        clips = [
            CloudClip(
                startTime=0.0,
                endTime=5.0,
                confidence=0.62,
                label="Highlight",
                action="Highlight",
                audioScore=0.5,
                visualScore=0.6,
                motionScore=0.55,
                combinedScore=0.58,
                detectionMethod="cloud",
                shouldAutoKeep=False,
                shouldEnableSlowMotion=False,
            ),
            CloudClip(
                startTime=8.0,
                endTime=13.0,
                confidence=0.7,
                label="Highlight",
                action="Highlight",
                audioScore=0.5,
                visualScore=0.6,
                motionScore=0.55,
                combinedScore=0.66,
                detectionMethod="cloud",
                shouldAutoKeep=True,
                shouldEnableSlowMotion=False,
            ),
        ]

        boosted = apply_autohighlight_boosts(clips, [0.95, 0.1])

        self.assertEqual(len(boosted), 2)
        self.assertGreaterEqual(boosted[0].combinedScore, boosted[1].combinedScore)
        self.assertTrue(any(clip.confidence > 0.62 for clip in boosted))
        self.assertTrue(boosted[0].shouldAutoKeep)

    def test_autohighlight_boost_cannot_autokeep_tiny_or_context_poor_clip(self) -> None:
        clips = [
            CloudClip(
                startTime=10.0,
                endTime=10.1,
                confidence=0.9,
                label="Highlight",
                action="Highlight",
                audioScore=0.5,
                visualScore=0.6,
                motionScore=0.55,
                combinedScore=0.58,
                detectionMethod="cloud",
                shouldAutoKeep=False,
                shouldEnableSlowMotion=True,
            ),
            CloudClip(
                startTime=20.0,
                endTime=24.5,
                eventCenter=22.0,
                confidence=0.7,
                label="Defense",
                action="Defense",
                audioScore=0.5,
                visualScore=0.7,
                motionScore=0.7,
                combinedScore=0.68,
                detectionMethod="cloud",
                shouldAutoKeep=False,
                shouldEnableSlowMotion=False,
            ),
        ]

        boosted = apply_autohighlight_boosts(clips, [1.0, 0.1])

        tiny = next(clip for clip in boosted if clip.endTime - clip.startTime < 1.0)
        self.assertFalse(tiny.shouldAutoKeep)
        self.assertFalse(tiny.shouldEnableSlowMotion)
        self.assertEqual(boosted[0].label, "Defense")


if __name__ == "__main__":
    unittest.main()
