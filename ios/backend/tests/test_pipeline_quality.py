from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from app.pipeline import (
    _build_candidate_windows,
    _detect_shot_boundaries,
    _shot_context_score_for_window,
    _visual_event_boundaries_from_signals,
)


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

    def test_visual_event_detector_prefers_shot_motion_over_audio_only_spike(self) -> None:
        audio_profile = [0.08] * 50
        for index in range(18, 22):
            audio_profile[index] = 0.62
        for index in range(34, 37):
            audio_profile[index] = 0.98
        frame_signals = [
            (7.5, 0.1, 0.12, 0.1),
            (9.5, 0.62, 0.82, 0.6),
            (10.0, 0.55, 0.74, 0.58),
            (17.0, 0.08, 0.06, 0.07),
            (17.5, 0.1, 0.08, 0.08),
        ]

        boundaries = _visual_event_boundaries_from_signals(
            frame_signals,
            audio_profile,
            duration_seconds=25.0,
        )
        windows = _build_candidate_windows(
            duration_seconds=25.0,
            audio_profile=audio_profile,
            shot_boundaries=boundaries,
            settings=_settings(),
        )

        self.assertEqual(boundaries, [9.5])
        self.assertEqual(windows[0].peak_time, 9.5)
        self.assertLessEqual(windows[0].start_time, 7.5)
        self.assertGreaterEqual(windows[0].end_time, 10.75)

    def test_visual_event_detector_ignores_low_quality_camera_motion(self) -> None:
        boundaries = _visual_event_boundaries_from_signals(
            [
                (4.0, 0.9, 0.08, 0.1),
                (5.5, 0.75, 0.12, 0.11),
            ],
            [0.95] * 20,
            duration_seconds=12.0,
        )

        self.assertEqual(boundaries, [])

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_detect_shot_boundaries_extracts_visual_event_from_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-visual-event-") as temp_dir:
            video_path = Path(temp_dir) / "synthetic_shot.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=160x90:r=12:d=8",
                    "-vf",
                    "drawbox=x=72:y=14:w=36:h=36:color=white@1:t=fill:enable='between(t,3,3.8)'",
                    "-pix_fmt",
                    "yuv420p",
                    str(video_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            boundaries = _detect_shot_boundaries(video_path, duration_seconds=8.0, audio_profile=[0.05] * 16)

        self.assertTrue(any(2.8 <= boundary <= 3.2 for boundary in boundaries))


if __name__ == "__main__":
    unittest.main()
