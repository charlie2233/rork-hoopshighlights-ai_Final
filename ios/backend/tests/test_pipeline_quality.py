from __future__ import annotations

from datetime import timedelta
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.pipeline import (
    _build_candidate_windows,
    _detect_shot_boundaries,
    _merge_hybrid_detection_clips,
    _normalize_clip_for_analysis_context,
    _shot_context_score_for_window,
    _visual_event_boundaries_from_signals,
    run_analysis,
)
from app.classifier import classify_window
from app.models import CandidateWindow, CloudClip, StoredJob, now_utc


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        min_clip_duration_seconds=2.0,
        max_clip_duration_seconds=4.5,
        clip_padding_seconds=0.0,
        max_returned_clips=8,
    )


def _analysis_settings(detection_provider: str = "hybrid") -> SimpleNamespace:
    return SimpleNamespace(
        detection_provider=detection_provider,
        hoopcut_repo_path=None,
        hoopcut_python_bin=None,
        post_ranking_provider="native",
        autohighlight_repo_path=None,
        autohighlight_python_bin=None,
        min_clip_duration_seconds=2.0,
        max_clip_duration_seconds=4.5,
        clip_padding_seconds=0.0,
        max_returned_clips=4,
        max_file_size_bytes=500 * 1024 * 1024,
        max_duration_seconds=60.0,
        backend_model_version="test-cloud",
        use_gemini_relabeling=False,
    )


def _job(duration_seconds: float = 30.0) -> StoredJob:
    created = now_utc()
    return StoredJob(
        job_id="job_quality",
        install_id="install_quality",
        filename="source.mp4",
        content_type="video/mp4",
        file_size_bytes=128,
        duration_seconds=duration_seconds,
        app_version="1.0",
        analysis_version="test",
        created_at=created,
        expires_at=created + timedelta(hours=1),
        object_key="uploads/source.mp4",
    )


def _clip(
    *,
    start: float,
    end: float,
    label: str,
    combined: float,
    confidence: float = 0.74,
    event_center: float | None = None,
    auto_keep: bool = True,
) -> CloudClip:
    return CloudClip(
        startTime=start,
        endTime=end,
        eventCenter=event_center,
        confidence=confidence,
        label=label,
        action=label,
        audioScore=0.55,
        visualScore=0.7,
        motionScore=0.68,
        combinedScore=combined,
        detectionMethod="cloud",
        shouldAutoKeep=auto_keep,
        shouldEnableSlowMotion=False,
    )


class PipelineQualityTests(unittest.TestCase):
    def test_run_analysis_hybrid_merges_native_pool_when_provider_returns_limited_clips(self) -> None:
        external = [
            _clip(start=18.0, end=22.0, label="Defense", combined=0.62, event_center=20.0, auto_keep=True)
        ]
        native = [
            _clip(start=7.5, end=12.0, label="Three Pointer", combined=0.86, event_center=10.0, auto_keep=True),
            _clip(start=24.0, end=28.5, label="Fast Break", combined=0.74, event_center=26.0, auto_keep=True),
        ]

        with tempfile.TemporaryDirectory(prefix="hoopclips-hybrid-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with (
                patch("app.pipeline._probe_duration", return_value=30.0),
                patch("app.pipeline.detect_with_optional_external_provider", return_value=(external, "hoopcut")),
                patch("app.pipeline._run_native_candidate_detection", return_value=(native, len(native))),
            ):
                result = run_analysis(_job(), _analysis_settings("hybrid"), source_path)

        labels = [clip.label for clip in result.clips]
        self.assertIn("Three Pointer", labels)
        self.assertIn("Defense", labels)
        self.assertEqual(result.diagnostics.candidateSegments, 3)
        self.assertEqual(result.diagnostics.backendModelVersion, "test-cloud+hoopcut")

    def test_run_analysis_filters_tiny_provider_clip_before_rerank(self) -> None:
        tiny = _clip(
            start=10.0,
            end=10.1,
            label="Made Shot",
            combined=0.99,
            confidence=0.98,
            event_center=None,
            auto_keep=True,
        )

        def assert_no_tiny_clips(clips, source_path, settings):
            self.assertEqual(clips, [])
            return [], None

        with tempfile.TemporaryDirectory(prefix="hoopclips-tiny-provider-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with (
                patch("app.pipeline._probe_duration", return_value=30.0),
                patch("app.pipeline.detect_with_optional_external_provider", return_value=([tiny], "hoopcut")),
                patch("app.pipeline.rerank_with_optional_external_provider", side_effect=assert_no_tiny_clips),
            ):
                result = run_analysis(_job(), _analysis_settings("hoopcut"), source_path)

        self.assertEqual(result.clips, [])

    def test_run_analysis_hybrid_drops_non_overlapping_tiny_clip_after_merge(self) -> None:
        tiny = _clip(
            start=2.0,
            end=2.1,
            label="Made Shot",
            combined=0.99,
            confidence=0.98,
            event_center=None,
            auto_keep=True,
        )
        native = [
            _clip(start=7.5, end=12.0, label="Three Pointer", combined=0.86, event_center=10.0, auto_keep=True)
        ]

        with tempfile.TemporaryDirectory(prefix="hoopclips-tiny-hybrid-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with (
                patch("app.pipeline._probe_duration", return_value=30.0),
                patch("app.pipeline.detect_with_optional_external_provider", return_value=([tiny], "hoopcut")),
                patch("app.pipeline._run_native_candidate_detection", return_value=(native, len(native))),
            ):
                result = run_analysis(_job(), _analysis_settings("hybrid"), source_path)

        self.assertEqual([clip.label for clip in result.clips], ["Three Pointer"])
        self.assertGreaterEqual(result.clips[0].endTime - result.clips[0].startTime, 2.0)

    def test_run_analysis_hoopcut_mode_keeps_successful_provider_external_only(self) -> None:
        external = [
            _clip(start=18.0, end=22.0, label="Defense", combined=0.62, event_center=20.0, auto_keep=True)
        ]

        with tempfile.TemporaryDirectory(prefix="hoopclips-hoopcut-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with (
                patch("app.pipeline._probe_duration", return_value=30.0),
                patch("app.pipeline.detect_with_optional_external_provider", return_value=(external, "hoopcut")),
                patch("app.pipeline._run_native_candidate_detection") as native_detection,
            ):
                result = run_analysis(_job(), _analysis_settings("hoopcut"), source_path)

        native_detection.assert_not_called()
        self.assertEqual([clip.label for clip in result.clips], ["Defense"])
        self.assertEqual(result.diagnostics.candidateSegments, 1)

    def test_hybrid_merge_prefers_complete_native_context_over_overlapping_provider_clip(self) -> None:
        weak_provider_clip = _clip(
            start=8.2,
            end=11.2,
            label="Made Shot",
            combined=0.92,
            confidence=0.9,
            event_center=None,
            auto_keep=True,
        )
        complete_native_clip = _clip(
            start=7.5,
            end=12.0,
            label="Three Pointer",
            combined=0.78,
            confidence=0.72,
            event_center=10.0,
            auto_keep=True,
        )

        clips = _merge_hybrid_detection_clips(
            external_clips=[weak_provider_clip],
            native_clips=[complete_native_clip],
            clip_limit=4,
        )

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].label, "Three Pointer")
        self.assertEqual(clips[0].eventCenter, 10.0)

    def test_analysis_normalization_expands_tiny_shot_clip_with_event_center(self) -> None:
        tiny = _clip(
            start=10.05,
            end=10.15,
            label="Made Shot",
            combined=0.86,
            confidence=0.82,
            event_center=10.0,
            auto_keep=True,
        )

        normalized = _normalize_clip_for_analysis_context(tiny, duration_seconds=30.0, settings=_settings())

        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertLessEqual(normalized.startTime, 8.0)
        self.assertGreaterEqual(normalized.endTime, 11.25)
        self.assertGreaterEqual(normalized.endTime - normalized.startTime, _settings().min_clip_duration_seconds)
        self.assertTrue(normalized.shouldAutoKeep)

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

    def test_shot_context_score_requires_setup_and_outcome_follow_through(self) -> None:
        pre_basket_score, pre_basket_event = _shot_context_score_for_window(
            start_time=9.0,
            end_time=13.5,
            center_time=11.25,
            shot_boundaries=[10.0],
        )
        no_outcome_score, no_outcome_event = _shot_context_score_for_window(
            start_time=6.0,
            end_time=10.3,
            center_time=8.15,
            shot_boundaries=[10.0],
        )

        self.assertEqual(pre_basket_score, 0.0)
        self.assertIsNone(pre_basket_event)
        self.assertEqual(no_outcome_score, 0.0)
        self.assertIsNone(no_outcome_event)

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

    def test_native_recall_fallback_returns_configured_candidate_pool(self) -> None:
        audio_profile = [0.08] * 60
        windows = _build_candidate_windows(
            duration_seconds=30.0,
            audio_profile=audio_profile,
            shot_boundaries=[],
            settings=_settings(),
        )

        self.assertEqual(len(windows), _settings().max_returned_clips)
        self.assertTrue(all(window.end_time - window.start_time >= _settings().min_clip_duration_seconds for window in windows))

    def test_visual_event_detector_prefers_shot_motion_over_audio_only_spike(self) -> None:
        audio_profile = [0.08] * 50
        for index in range(18, 22):
            audio_profile[index] = 0.62
        for index in range(34, 37):
            audio_profile[index] = 0.98
        frame_signals = [
            (7.5, 0.1, 0.12, 0.1),
            (9.5, 0.62, 0.82, 0.6),
            (10.0, 0.58, 0.78, 0.62),
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

        self.assertEqual(boundaries, [10.0])
        self.assertEqual(windows[0].peak_time, 10.0)
        self.assertLessEqual(windows[0].start_time, 7.5)
        self.assertGreaterEqual(windows[0].end_time, 11.25)

    def test_visual_event_detector_prefers_rim_outcome_over_release_in_sequence(self) -> None:
        audio_profile = [0.08] * 40
        for index in range(18, 22):
            audio_profile[index] = 0.64
        frame_signals = [
            (8.5, 0.2, 0.34, 0.22),
            (9.5, 0.68, 0.9, 0.62),
            (10.0, 0.62, 0.84, 0.7),
            (10.5, 0.34, 0.38, 0.32),
        ]

        boundaries = _visual_event_boundaries_from_signals(
            frame_signals,
            audio_profile,
            duration_seconds=20.0,
        )

        self.assertEqual(boundaries, [10.0])

    def test_visual_event_detector_does_not_shift_to_dead_aftermath(self) -> None:
        audio_profile = [0.08] * 40
        for index in range(18, 22):
            audio_profile[index] = 0.64
        frame_signals = [
            (8.5, 0.2, 0.34, 0.22),
            (9.5, 0.7, 0.92, 0.64),
            (10.0, 0.6, 0.82, 0.68),
            (10.5, 0.12, 0.14, 0.12),
        ]

        boundaries = _visual_event_boundaries_from_signals(
            frame_signals,
            audio_profile,
            duration_seconds=20.0,
        )

        self.assertEqual(boundaries, [10.0])

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

    def test_classifier_does_not_call_audio_only_window_a_shot(self) -> None:
        audio_only_window = CandidateWindow(
            start_time=12.0,
            end_time=16.5,
            peak_time=14.25,
            audio_score=0.86,
            visual_score=0.42,
            motion_score=0.58,
            combined_score=0.78,
            event_context_score=0.0,
        )
        shot_context_window = CandidateWindow(
            start_time=8.0,
            end_time=12.5,
            peak_time=10.0,
            audio_score=0.86,
            visual_score=0.62,
            motion_score=0.58,
            combined_score=0.78,
            event_context_score=0.72,
        )

        audio_clip = classify_window(audio_only_window)
        shot_clip = classify_window(shot_context_window)

        self.assertEqual(audio_clip.label, "Highlight")
        self.assertFalse(audio_clip.shouldAutoKeep)
        self.assertEqual(shot_clip.label, "Three Pointer")
        self.assertTrue(shot_clip.shouldAutoKeep)

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

        self.assertTrue(any(3.8 <= boundary <= 4.2 for boundary in boundaries))


if __name__ == "__main__":
    unittest.main()
