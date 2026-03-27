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


if __name__ == "__main__":
    unittest.main()
