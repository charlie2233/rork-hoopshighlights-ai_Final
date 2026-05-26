from __future__ import annotations

from types import SimpleNamespace
import unittest

from app.pipeline import _build_candidate_windows, _shot_context_score_for_window


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        min_clip_duration_seconds=2.0,
        max_clip_duration_seconds=4.5,
        clip_padding_seconds=0.0,
        max_returned_clips=8,
    )


class PipelineQualityTests(unittest.TestCase):
    def test_shot_context_score_rewards_setup_and_outcome_around_boundary(self) -> None:
        complete_score, event_time = _shot_context_score_for_window(
            start_time=7.5,
            end_time=12.0,
            center_time=9.75,
            shot_boundaries=[10.0],
        )
        aftermath_score, aftermath_event = _shot_context_score_for_window(
            start_time=10.5,
            end_time=15.0,
            center_time=12.75,
            shot_boundaries=[10.0],
        )

        self.assertEqual(event_time, 10.0)
        self.assertIsNone(aftermath_event)
        self.assertGreaterEqual(complete_score, 0.9)
        self.assertEqual(aftermath_score, 0.0)

    def test_native_candidate_ranking_prefers_complete_shot_context_over_later_audio_spike(self) -> None:
        audio_profile = [0.08] * 50
        for index in range(18, 22):
            audio_profile[index] = 0.62
        for index in range(34, 37):
            audio_profile[index] = 0.82

        windows = _build_candidate_windows(
            duration_seconds=25.0,
            audio_profile=audio_profile,
            shot_boundaries=[10.0],
            settings=_settings(),
        )

        self.assertGreaterEqual(len(windows), 2)
        top = windows[0]
        self.assertLessEqual(top.start_time, 8.0)
        self.assertGreaterEqual(top.end_time, 11.25)
        self.assertEqual(top.peak_time, 10.0)
        self.assertGreater(top.event_context_score, 0.0)
        self.assertGreater(
            top.combined_score,
            max(window.combined_score for window in windows if window.start_time > 10.0),
        )


if __name__ == "__main__":
    unittest.main()
