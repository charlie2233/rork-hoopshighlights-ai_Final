from __future__ import annotations

import unittest

from services.inference.app.windowing import (
    WINDOW_POLICY_VERSION,
    BasketballClipWindower,
    WindowedClipDraft,
    window_and_merge_clips,
)


def make_draft(
    clip_id: str,
    *,
    label: str = "jumper",
    canonical_label: str | None = None,
    source_start: float,
    source_end: float,
    event_center: float,
    rank_score: float = 0.7,
) -> WindowedClipDraft:
    return WindowedClipDraft(
        clipId=clip_id,
        sourceStartSeconds=source_start,
        sourceEndSeconds=source_end,
        label=label,
        action=label,
        canonicalLabel=canonical_label or label,
        eventType="play",
        shotType="shot",
        makeMiss="make",
        confidence=0.82,
        resultConfidence=0.78,
        audioScore=0.3,
        visualScore=0.6,
        motionScore=0.55,
        combinedScore=0.7,
        rankScore=rank_score,
        detectionMethod="model",
        shouldAutoKeep=True,
        shouldEnableSlowMotion=False,
        metadata={"event_center_seconds": event_center},
    )


class WindowingTests(unittest.TestCase):
    def test_sub_minimum_windows_expand_to_policy_floor(self) -> None:
        clips = window_and_merge_clips(
            [
                make_draft(
                    "clip-1",
                    label="miss",
                    source_start=0.2,
                    source_end=0.9,
                    event_center=0.4,
                )
            ],
            source_duration_seconds=5.0,
        )

        self.assertEqual(len(clips), 1)
        clip = clips[0]
        self.assertGreaterEqual(clip.clipDurationSeconds, 3.5)
        self.assertEqual(clip.windowPolicyVersion, WINDOW_POLICY_VERSION)
        self.assertFalse(clip.wasMerged)
        self.assertEqual(clip.sourceEventCount, 1)

    def test_short_source_keeps_full_duration(self) -> None:
        clips = window_and_merge_clips(
            [
                make_draft(
                    "clip-1",
                    label="layup",
                    source_start=0.0,
                    source_end=2.5,
                    event_center=1.2,
                )
            ],
            source_duration_seconds=2.75,
        )

        self.assertEqual(len(clips), 1)
        clip = clips[0]
        self.assertAlmostEqual(clip.startTime, 0.0, places=3)
        self.assertAlmostEqual(clip.endTime, 2.75, places=3)
        self.assertAlmostEqual(clip.clipDurationSeconds, 2.75, places=3)

    def test_near_start_boundary_expands_on_available_side(self) -> None:
        clips = window_and_merge_clips(
            [
                make_draft(
                    "clip-start",
                    label="dunk",
                    source_start=0.1,
                    source_end=0.8,
                    event_center=0.35,
                )
            ],
            source_duration_seconds=5.0,
        )

        clip = clips[0]
        self.assertAlmostEqual(clip.startTime, 0.0, places=3)
        self.assertAlmostEqual(clip.endTime, 4.5, places=3)
        self.assertGreaterEqual(clip.clipDurationSeconds, 4.5)
        self.assertGreaterEqual(clip.postRollSeconds, clip.preRollSeconds)

    def test_near_end_boundary_expands_to_preserve_minimum(self) -> None:
        clips = window_and_merge_clips(
            [
                make_draft(
                    "clip-end",
                    label="miss",
                    source_start=4.4,
                    source_end=4.9,
                    event_center=4.7,
                )
            ],
            source_duration_seconds=5.0,
        )

        clip = clips[0]
        self.assertAlmostEqual(clip.endTime, 5.0, places=3)
        self.assertAlmostEqual(clip.startTime, 0.5, places=3)
        self.assertAlmostEqual(clip.clipDurationSeconds, 4.5, places=3)
        self.assertGreaterEqual(clip.preRollSeconds, 4.0)

    def test_adjacent_events_merge_into_one_coherent_clip(self) -> None:
        clips = window_and_merge_clips(
            [
                make_draft("clip-a", label="dunk", source_start=4.8, source_end=5.2, event_center=5.0, rank_score=0.84),
                make_draft("clip-b", label="layup", source_start=7.8, source_end=8.2, event_center=8.0, rank_score=0.81),
            ],
            source_duration_seconds=15.0,
        )

        self.assertEqual(len(clips), 1)
        clip = clips[0]
        self.assertTrue(clip.wasMerged)
        self.assertEqual(clip.sourceEventCount, 2)
        self.assertLessEqual(clip.clipDurationSeconds, 8.0)
        self.assertEqual(clip.windowPolicyVersion, WINDOW_POLICY_VERSION)

    def test_short_basketball_sequence_does_not_fragment(self) -> None:
        clips = window_and_merge_clips(
            [
                make_draft("clip-1", label="jumper", source_start=2.1, source_end=2.9, event_center=2.5, rank_score=0.76),
                make_draft("clip-2", label="layup", source_start=4.0, source_end=4.9, event_center=4.5, rank_score=0.79),
                make_draft("clip-3", label="dunk", source_start=5.8, source_end=6.8, event_center=6.4, rank_score=0.83),
            ],
            source_duration_seconds=8.0,
        )

        self.assertEqual(len(clips), 1)
        clip = clips[0]
        self.assertTrue(clip.wasMerged)
        self.assertEqual(clip.sourceEventCount, 3)
        self.assertGreaterEqual(clip.clipDurationSeconds, 4.5)
        self.assertLessEqual(clip.clipDurationSeconds, 8.0)

    def test_basketball_clip_windower_helper_matches_wrapper(self) -> None:
        windower = BasketballClipWindower()
        via_helper = windower.apply(
            [
                make_draft("clip-1", label="jumper", source_start=1.0, source_end=1.6, event_center=1.3),
            ],
            source_duration_seconds=6.0,
        )
        via_wrapper = window_and_merge_clips(
            [
                make_draft("clip-1", label="jumper", source_start=1.0, source_end=1.6, event_center=1.3),
            ],
            source_duration_seconds=6.0,
        )

        self.assertEqual(via_helper[0].clipId, via_wrapper[0].clipId)
        self.assertEqual(via_helper[0].metadata["window_policy_version"], WINDOW_POLICY_VERSION)


if __name__ == "__main__":
    unittest.main()
