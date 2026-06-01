from __future__ import annotations

from datetime import timedelta
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.config import get_settings
from app.pipeline import (
    TEAM_SELECTION_PREFILTER_MULTIPLIER,
    _analysis_team_diagnostic_counts,
    _build_candidate_windows,
    _annotate_analysis_team_status,
    _analysis_candidate_pool_limit,
    _detect_shot_boundaries,
    _detected_teams_from_clips,
    _is_defensive_label,
    _merge_hybrid_detection_clips,
    _native_shot_signals_for_analysis_clip,
    _normalize_clip_for_analysis_context,
    _shot_context_score_for_window,
    build_team_quick_scan_candidate_clips,
    _trim_analysis_clips_for_review,
    _visual_event_boundaries_from_signals,
    run_analysis,
)
from app.classifier import classify_window
from app.models import CandidateWindow, ClipTeamAttribution, CloudClip, StoredJob, TeamOption, TeamSelection, now_utc


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
        team_quick_scan_enabled=True,
        team_quick_scan_api_key="test-key",
        team_quick_scan_model="gpt-4.1",
        team_quick_scan_endpoint="https://api.openai.com/v1/responses",
        team_quick_scan_timeout_seconds=12.0,
        team_quick_scan_video_frame_count=6,
        team_quick_scan_clip_frames_per_clip=3,
        team_quick_scan_frame_width=720,
        team_quick_scan_jpeg_quality=4,
        team_quick_scan_max_image_bytes=500_000,
        team_quick_scan_min_team_confidence=0.55,
    )


def _job(duration_seconds: float = 30.0, team_selection: TeamSelection | None = None) -> StoredJob:
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
        team_selection=team_selection,
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


def _team_attr(
    *,
    team_id: str | None,
    label: str,
    color_label: str,
    confidence: float,
    source: str = "gpt_frame_review",
    evidence: bool = True,
) -> ClipTeamAttribution:
    return ClipTeamAttribution(
        teamId=team_id,
        label=label,
        colorLabel=color_label,
        confidence=confidence,
        source=source,
        evidenceFrameRefs=["clip_0_setup", "clip_0_result"] if evidence else [],
        evidenceRoleGroups=["setup", "outcome"] if evidence else [],
    )


class PipelineQualityTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_default_backend_candidate_pool_feeds_gpt_internal_top_two_twenty(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-settings-") as temp_dir:
            with patch.dict(os.environ, {"HOOPS_ENVIRONMENT": "local", "HOOPS_UPLOAD_ROOT": temp_dir}, clear=True):
                get_settings.cache_clear()
                settings = get_settings()

        self.assertEqual(settings.max_returned_clips, 220)
        self.assertEqual(settings.team_quick_scan_clip_frames_per_clip, 8)
        self.assertEqual(settings.team_quick_scan_rich_candidate_clips, 160)
        self.assertEqual(settings.team_quick_scan_max_total_clip_frames, 1760)
        self.assertEqual(settings.team_quick_scan_max_candidate_clips, 220)

    def test_backend_candidate_pool_env_is_clamped_for_review_safety(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-settings-") as temp_dir:
            with patch.dict(
                os.environ,
                {"HOOPS_ENVIRONMENT": "local", "HOOPS_UPLOAD_ROOT": temp_dir, "HOOPS_MAX_RETURNED_CLIPS": "999"},
                clear=True,
            ):
                get_settings.cache_clear()
                high_settings = get_settings()

            with patch.dict(
                os.environ,
                {"HOOPS_ENVIRONMENT": "local", "HOOPS_UPLOAD_ROOT": temp_dir, "HOOPS_MAX_RETURNED_CLIPS": "2"},
                clear=True,
            ):
                get_settings.cache_clear()
                low_settings = get_settings()

        self.assertEqual(high_settings.max_returned_clips, 220)
        self.assertEqual(low_settings.max_returned_clips, 8)

    def test_run_analysis_applies_quick_scan_before_selected_team_filter(self) -> None:
        native = [
            _clip(start=7.5, end=12.0, label="Three Pointer", combined=0.86, event_center=10.0, auto_keep=True),
            _clip(start=16.0, end=20.5, label="Steal", combined=0.82, event_center=18.0, auto_keep=True),
            _clip(start=24.0, end=28.5, label="Block", combined=0.8, event_center=26.0, auto_keep=True),
        ]
        detected = [
            TeamOption(teamId="team_dark", label="Dark jerseys", colorLabel="black", confidence=0.93, source="quick_scan"),
            TeamOption(teamId="team_light", label="Light jerseys", colorLabel="white", confidence=0.91, source="quick_scan"),
        ]
        attributed = [
            native[0].model_copy(
                update={
                    "teamAttribution": ClipTeamAttribution(
                        teamId="team_dark",
                        label="Dark jerseys",
                        colorLabel="black",
                        confidence=0.92,
                        source="gpt_frame_review",
                        evidenceFrameRefs=["clip_0_setup", "clip_0_result"],
                        evidenceRoleGroups=["setup", "outcome"],
                    )
                }
            ),
            native[1].model_copy(
                update={
                    "teamAttribution": ClipTeamAttribution(
                        teamId="team_light",
                        label="Light jerseys",
                        colorLabel="white",
                        confidence=0.93,
                        source="gpt_frame_review",
                        evidenceFrameRefs=["clip_1_setup", "clip_1_result"],
                        evidenceRoleGroups=["setup", "outcome"],
                    )
                }
            ),
            native[2].model_copy(
                update={
                    "teamAttribution": ClipTeamAttribution(
                        teamId="team_dark",
                        label="Dark jerseys",
                        colorLabel="black",
                        confidence=0.62,
                        source="gpt_frame_review",
                    )
                }
            ),
        ]
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=True)

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with (
                patch("app.pipeline._probe_duration", return_value=30.0),
                patch("app.pipeline.detect_with_optional_external_provider", return_value=([], None)),
                patch("app.pipeline._run_native_candidate_detection", return_value=(native, len(native))),
                patch("app.pipeline.apply_team_quick_scan", return_value=(attributed, detected, True)),
            ):
                result = run_analysis(_job(team_selection=team_selection), _analysis_settings("hybrid"), source_path)

        labels = [clip.label for clip in result.clips]
        self.assertIn("Three Pointer", labels)
        self.assertIn("Block", labels)
        self.assertNotIn("Steal", labels)
        status_by_label = {clip.label: clip.teamAttributionStatus for clip in result.clips}
        self.assertEqual(status_by_label["Three Pointer"], "matched")
        self.assertEqual(status_by_label["Block"], "uncertain")
        self.assertEqual([team.teamId for team in result.detectedTeams], ["team_dark", "team_light"])
        self.assertEqual(result.diagnostics.backendModelVersion, "test-cloud+team-scan")

    def test_analysis_team_status_marks_missing_attribution_uncertain_for_review(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=True)
        clips = [
            _clip(start=8.0, end=12.5, label="Possible block", combined=0.76, event_center=10.2, auto_keep=True)
        ]

        annotated = _annotate_analysis_team_status(clips, team_selection)

        self.assertEqual(annotated[0].teamAttributionStatus, "uncertain")
        self.assertIsNone(annotated[0].teamAttribution)

    def test_analysis_team_status_requires_scan_evidence_for_confident_match(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=True)
        clips = [
            _clip(start=8.0, end=12.5, label="Weak evidence make", combined=0.88, event_center=10.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_dark",
                        label="Dark jerseys",
                        color_label="black",
                        confidence=0.94,
                        evidence=False,
                    )
                }
            ),
            _clip(start=14.0, end=18.5, label="Evidence-backed make", combined=0.86, event_center=16.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_dark",
                        label="Dark jerseys",
                        color_label="black",
                        confidence=0.91,
                    )
                }
            ),
        ]

        annotated = _annotate_analysis_team_status(clips, team_selection)

        self.assertEqual(annotated[0].teamAttributionStatus, "uncertain")
        self.assertEqual(annotated[1].teamAttributionStatus, "matched")

    def test_analysis_team_status_requires_evidence_for_unknown_and_provider_sources(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=True)
        clips = [
            _clip(start=8.0, end=12.5, label="Missing source make", combined=0.88, event_center=10.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": ClipTeamAttribution(
                        teamId="team_dark",
                        label="Dark jerseys",
                        colorLabel="black",
                        confidence=0.94,
                    )
                }
            ),
            _clip(start=14.0, end=18.5, label="Provider make", combined=0.87, event_center=16.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_dark",
                        label="Dark jerseys",
                        color_label="black",
                        confidence=0.93,
                        source="provider",
                        evidence=False,
                    )
                }
            ),
            _clip(start=20.0, end=24.5, label="Provider steal", combined=0.86, event_center=22.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_dark",
                        label="Dark jerseys",
                        color_label="black",
                        confidence=0.92,
                        source="provider",
                    )
                }
            ),
            _clip(start=26.0, end=30.5, label="Manual block", combined=0.85, event_center=28.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_dark",
                        label="Dark jerseys",
                        color_label="black",
                        confidence=0.91,
                        source="manual",
                        evidence=False,
                    )
                }
            ),
        ]

        annotated = _annotate_analysis_team_status(clips, team_selection)

        self.assertEqual(annotated[0].teamAttributionStatus, "uncertain")
        self.assertEqual(annotated[1].teamAttributionStatus, "uncertain")
        self.assertEqual(annotated[2].teamAttributionStatus, "matched")
        self.assertEqual(annotated[3].teamAttributionStatus, "matched")

    def test_analysis_team_status_preserves_explicit_uncertain_scan_status(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=True)
        clips = [
            _clip(start=8.0, end=12.5, label="Review-only block", combined=0.88, event_center=10.2, auto_keep=True).model_copy(
                update={
                    "teamAttributionStatus": "uncertain",
                    "teamAttribution": _team_attr(
                        team_id="team_dark",
                        label="Dark jerseys",
                        color_label="black",
                        confidence=0.94,
                    ),
                }
            ),
            _clip(start=14.0, end=18.5, label="Evidence-backed make", combined=0.86, event_center=16.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_dark",
                        label="Dark jerseys",
                        color_label="black",
                        confidence=0.91,
                    )
                }
            ),
        ]

        annotated = _annotate_analysis_team_status(clips, team_selection)

        self.assertEqual(annotated[0].teamAttributionStatus, "uncertain")
        self.assertEqual(annotated[1].teamAttributionStatus, "matched")

    def test_detected_team_fallback_requires_confident_evidence_backed_attribution(self) -> None:
        clips = [
            _clip(start=8.0, end=12.5, label="Weak unknown team", combined=0.88, event_center=10.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": ClipTeamAttribution(
                        teamId="team_dark",
                        label="Dark jerseys",
                        colorLabel="black",
                        confidence=0.94,
                    )
                }
            ),
            _clip(start=14.0, end=18.5, label="Explicit uncertain team", combined=0.87, event_center=16.2, auto_keep=True).model_copy(
                update={
                    "teamAttributionStatus": "uncertain",
                    "teamAttribution": _team_attr(
                        team_id="team_light",
                        label="Light jerseys",
                        color_label="white",
                        confidence=0.94,
                    ),
                }
            ),
            _clip(start=20.0, end=24.5, label="Low confidence team", combined=0.86, event_center=22.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_red",
                        label="Red jerseys",
                        color_label="red",
                        confidence=0.72,
                    )
                }
            ),
            _clip(start=26.0, end=30.5, label="Manual team", combined=0.85, event_center=28.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_blue",
                        label="Blue jerseys",
                        color_label="blue",
                        confidence=0.91,
                        source="manual",
                        evidence=False,
                    )
                }
            ),
            _clip(start=32.0, end=36.5, label="Provider evidence team", combined=0.84, event_center=34.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_green",
                        label="Green jerseys",
                        color_label="green",
                        confidence=0.9,
                        source="provider",
                    )
                }
            ),
        ]

        detected = _detected_teams_from_clips(clips)

        self.assertEqual([team.teamId for team in detected], ["team_blue", "team_green"])

    def test_analysis_team_status_rejects_conflicting_team_id_even_when_color_matches(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=True)
        clips = [
            _clip(start=8.0, end=12.5, label="Wrong color alias", combined=0.88, event_center=10.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_light",
                        label="Light jerseys",
                        color_label="black",
                        confidence=0.94,
                    )
                }
            ),
            _clip(start=14.0, end=18.5, label="Color fallback", combined=0.86, event_center=16.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id=None,
                        label="Dark jerseys",
                        color_label="black",
                        confidence=0.91,
                    )
                }
            ),
        ]

        annotated = _annotate_analysis_team_status(clips, team_selection)

        self.assertEqual(annotated[0].teamAttributionStatus, "opponent")
        self.assertEqual(annotated[1].teamAttributionStatus, "matched")

    def test_analysis_team_status_matches_jersey_color_alias_team_ids(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", label="Dark jerseys", colorLabel="black", includeUncertain=True)
        clips = [
            _clip(start=8.0, end=12.5, label="Black jersey bucket", combined=0.88, event_center=10.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_black",
                        label="Black jerseys",
                        color_label="black",
                        confidence=0.94,
                    )
                }
            )
        ]

        annotated = _annotate_analysis_team_status(clips, team_selection)

        self.assertEqual(annotated[0].teamAttributionStatus, "matched")

    def test_analysis_team_status_rejects_exact_team_id_with_color_conflict(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", label="Dark jerseys", colorLabel="black", includeUncertain=True)
        clips = [
            _clip(start=8.0, end=12.5, label="Bad exact id", combined=0.88, event_center=10.2, auto_keep=True).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_dark",
                        label="Light jerseys",
                        color_label="white",
                        confidence=0.94,
                    )
                }
            )
        ]

        annotated = _annotate_analysis_team_status(clips, team_selection)

        self.assertEqual(annotated[0].teamAttributionStatus, "opponent")

    def test_selected_team_analysis_expands_pool_before_filtering(self) -> None:
        native = [
            _clip(start=0.0, end=4.5, label="Made Shot", combined=0.96, event_center=2.4, auto_keep=True),
            _clip(start=6.0, end=10.5, label="Made Shot", combined=0.95, event_center=8.4, auto_keep=True),
            _clip(start=12.0, end=16.5, label="Made Shot", combined=0.94, event_center=14.4, auto_keep=True),
            _clip(start=18.0, end=22.5, label="Made Shot", combined=0.93, event_center=20.4, auto_keep=True),
            _clip(start=24.0, end=28.5, label="Three Pointer", combined=0.82, event_center=26.4, auto_keep=True),
            _clip(start=30.0, end=34.5, label="Steal", combined=0.8, event_center=32.0, auto_keep=True),
            _clip(start=36.0, end=40.5, label="Block", combined=0.76, event_center=38.0, auto_keep=True),
        ]
        attributed = []
        for index, clip in enumerate(native):
            if index < 4:
                attribution = _team_attr(team_id="team_light", label="Light jerseys", color_label="white", confidence=0.94)
            elif index == 6:
                attribution = _team_attr(team_id="team_light", label="Light jerseys", color_label="white", confidence=0.62, evidence=False)
            else:
                attribution = _team_attr(team_id="team_dark", label="Dark jerseys", color_label="black", confidence=0.93)
            attributed.append(clip.model_copy(update={"teamAttribution": attribution}))
        detected = [
            TeamOption(teamId="team_dark", label="Dark jerseys", colorLabel="black", confidence=0.93, source="quick_scan"),
            TeamOption(teamId="team_light", label="Light jerseys", colorLabel="white", confidence=0.91, source="quick_scan"),
        ]
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=True)
        settings = _analysis_settings("hybrid")
        external_limits: list[int] = []
        native_limits: list[int | None] = []

        def fake_external_detection(source_path, duration_seconds, settings):
            external_limits.append(settings.max_returned_clips)
            return [], None

        def fake_native_detection(source_path, duration_seconds, native_settings, clip_limit=None):
            native_limits.append(clip_limit)
            return native[: clip_limit or native_settings.max_returned_clips], len(native)

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-prefilter-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with (
                patch("app.pipeline._probe_duration", return_value=60.0),
                patch("app.pipeline.detect_with_optional_external_provider", side_effect=fake_external_detection),
                patch("app.pipeline._run_native_candidate_detection", side_effect=fake_native_detection),
                patch("app.pipeline.apply_team_quick_scan", return_value=(attributed, detected, True)),
            ):
                result = run_analysis(_job(team_selection=team_selection), settings, source_path)

        self.assertEqual(external_limits, [settings.max_returned_clips * TEAM_SELECTION_PREFILTER_MULTIPLIER])
        self.assertEqual(native_limits, [settings.max_returned_clips * TEAM_SELECTION_PREFILTER_MULTIPLIER])
        self.assertLessEqual(len(result.clips), settings.max_returned_clips)
        self.assertEqual([clip.label for clip in result.clips], ["Three Pointer", "Steal", "Block"])
        self.assertTrue(any(clip.teamAttribution and clip.teamAttribution.confidence < 0.85 for clip in result.clips))
        self.assertTrue(result.diagnostics.usedTeamQuickScan)
        self.assertEqual(result.diagnostics.preTeamFilterSegments, 7)
        self.assertEqual(result.diagnostics.teamMatchedCandidateSegments, 2)
        self.assertEqual(result.diagnostics.teamUncertainCandidateSegments, 1)
        self.assertEqual(result.diagnostics.teamOpponentFilteredSegments, 4)
        self.assertEqual(result.diagnostics.teamMatchedReviewSegments, 2)
        self.assertEqual(result.diagnostics.teamUncertainReviewSegments, 1)
        self.assertEqual(result.diagnostics.defensiveReviewSegments, 2)
        self.assertEqual(result.diagnostics.blockReviewSegments, 1)
        self.assertEqual(result.diagnostics.stealReviewSegments, 1)

    def test_all_teams_analysis_expands_pool_before_review_trim_for_defense(self) -> None:
        native = [
            _clip(start=0.0, end=4.5, label="Made Shot 0", combined=0.96, event_center=2.4, auto_keep=True),
            _clip(start=6.0, end=10.5, label="Made Shot 1", combined=0.95, event_center=8.4, auto_keep=True),
            _clip(start=12.0, end=16.5, label="Made Shot 2", combined=0.94, event_center=14.4, auto_keep=True),
            _clip(start=18.0, end=22.5, label="Made Shot 3", combined=0.93, event_center=20.4, auto_keep=True),
            _clip(start=24.0, end=28.5, label="Steal", combined=0.82, event_center=26.0, auto_keep=True),
            _clip(start=30.0, end=34.5, label="Block", combined=0.8, event_center=32.0, auto_keep=True),
        ]
        settings = _analysis_settings("hybrid")
        external_limits: list[int] = []
        native_limits: list[int | None] = []

        def fake_external_detection(source_path, duration_seconds, settings):
            external_limits.append(settings.max_returned_clips)
            return [], None

        def fake_native_detection(source_path, duration_seconds, native_settings, clip_limit=None):
            native_limits.append(clip_limit)
            return native[: clip_limit or native_settings.max_returned_clips], len(native)

        with tempfile.TemporaryDirectory(prefix="hoopclips-all-teams-prefilter-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with (
                patch("app.pipeline._probe_duration", return_value=60.0),
                patch("app.pipeline.detect_with_optional_external_provider", side_effect=fake_external_detection),
                patch("app.pipeline._run_native_candidate_detection", side_effect=fake_native_detection),
                patch("app.pipeline.apply_team_quick_scan", return_value=(native, [], False)),
            ):
                result = run_analysis(_job(team_selection=TeamSelection(mode="all")), settings, source_path)

        self.assertEqual(external_limits, [settings.max_returned_clips * TEAM_SELECTION_PREFILTER_MULTIPLIER])
        self.assertEqual(native_limits, [settings.max_returned_clips * TEAM_SELECTION_PREFILTER_MULTIPLIER])
        self.assertEqual(len(result.clips), settings.max_returned_clips)
        self.assertIn("Steal", [clip.label for clip in result.clips])
        self.assertIn("Block", [clip.label for clip in result.clips])

    def test_selected_team_visible_results_reserve_uncertain_review_clips(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=True)
        clips = [
            _clip(
                start=float(index * 5),
                end=float(index * 5 + 4),
                label=f"Made Shot {index}",
                combined=0.95 - (index * 0.01),
                event_center=float(index * 5 + 2),
                auto_keep=True,
            ).model_copy(
                update={
                    "teamAttribution": ClipTeamAttribution(
                        teamId="team_dark",
                        label="Dark jerseys",
                        colorLabel="black",
                        confidence=0.94,
                        source="gpt_frame_review",
                        evidenceFrameRefs=["clip_0_setup", "clip_0_result"],
                        evidenceRoleGroups=["setup", "outcome"],
                    )
                }
            )
            for index in range(5)
        ]
        clips.append(
            _clip(start=30.0, end=34.0, label="Uncertain block", combined=0.7, event_center=32.0, auto_keep=True).model_copy(
                update={
                    "teamAttribution": ClipTeamAttribution(
                        teamId="team_dark",
                        label="Dark jerseys",
                        colorLabel="black",
                        confidence=0.62,
                        source="gpt_frame_review",
                    )
                }
            )
        )

        trimmed = _trim_analysis_clips_for_review(clips, team_selection, max_clips=4)

        self.assertEqual(len(trimmed), 4)
        self.assertIn("Uncertain block", [clip.label for clip in trimmed])
        self.assertNotIn("Made Shot 4", [clip.label for clip in trimmed])

    def test_selected_team_visible_results_reserve_best_uncertain_review_clip(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=True)
        matched = [
            _clip(
                start=float(index * 5),
                end=float(index * 5 + 4),
                label=f"Made Shot {index}",
                combined=0.95 - (index * 0.01),
                event_center=float(index * 5 + 2),
                auto_keep=True,
            ).model_copy(
                update={
                    "teamAttribution": ClipTeamAttribution(
                        teamId="team_dark",
                        label="Dark jerseys",
                        colorLabel="black",
                        confidence=0.94,
                        source="gpt_frame_review",
                        evidenceFrameRefs=["clip_0_setup", "clip_0_result"],
                        evidenceRoleGroups=["setup", "outcome"],
                    )
                }
            )
            for index in range(5)
        ]
        weak_uncertain = _clip(
            start=30.0,
            end=34.0,
            label="Uncertain weak rebound",
            combined=0.52,
            confidence=0.54,
            event_center=32.0,
            auto_keep=False,
        ).model_copy(
            update={
                "teamAttribution": ClipTeamAttribution(
                    teamId="team_dark",
                    label="Dark jerseys",
                    colorLabel="black",
                    confidence=0.55,
                    source="gpt_frame_review",
                )
            }
        )
        strong_uncertain = _clip(
            start=35.0,
            end=39.0,
            label="Uncertain steal",
            combined=0.82,
            confidence=0.76,
            event_center=37.0,
            auto_keep=True,
        ).model_copy(
            update={
                "teamAttribution": ClipTeamAttribution(
                    teamId="team_dark",
                    label="Dark jerseys",
                    colorLabel="black",
                    confidence=0.64,
                    source="gpt_frame_review",
                )
            }
        )

        trimmed = _trim_analysis_clips_for_review([*matched, weak_uncertain, strong_uncertain], team_selection, max_clips=4)
        labels = [clip.label for clip in trimmed]

        self.assertIn("Uncertain steal", labels)
        self.assertNotIn("Uncertain weak rebound", labels)
        self.assertNotIn("Made Shot 4", labels)

    def test_uncertain_selected_team_review_clip_is_not_auto_kept(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=True)
        matched = _clip(
            start=0.0,
            end=4.0,
            label="Made Shot",
            combined=0.95,
            event_center=2.0,
            auto_keep=True,
        ).model_copy(
            update={
                "teamAttribution": _team_attr(
                    team_id="team_dark",
                    label="Dark jerseys",
                    color_label="black",
                    confidence=0.94,
                )
            }
        )
        uncertain = _clip(
            start=5.0,
            end=9.0,
            label="Uncertain steal",
            combined=0.86,
            event_center=7.0,
            auto_keep=True,
        ).model_copy(
            update={
                "teamAttribution": ClipTeamAttribution(
                    teamId="team_dark",
                    label="Dark jerseys",
                    colorLabel="black",
                    confidence=0.64,
                    source="gpt_frame_review",
                ),
                "shouldEnableSlowMotion": True,
            }
        )

        annotated = _annotate_analysis_team_status([matched, uncertain], team_selection)

        self.assertEqual(annotated[0].teamAttributionStatus, "matched")
        self.assertTrue(annotated[0].shouldAutoKeep)
        self.assertEqual(annotated[1].teamAttributionStatus, "uncertain")
        self.assertFalse(annotated[1].shouldAutoKeep)
        self.assertFalse(annotated[1].shouldEnableSlowMotion)

    def test_selected_team_visible_results_reserve_multiple_uncertain_review_clips(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=True)
        matched = [
            _clip(
                start=float(index * 5),
                end=float(index * 5 + 4),
                label=f"Made Shot {index}",
                combined=0.97 - (index * 0.01),
                event_center=float(index * 5 + 2),
                auto_keep=True,
            ).model_copy(
                update={
                    "teamAttribution": _team_attr(
                        team_id="team_dark",
                        label="Dark jerseys",
                        color_label="black",
                        confidence=0.94,
                    )
                }
            )
            for index in range(8)
        ]
        uncertain = [
            _clip(start=45.0, end=49.0, label="Uncertain block", combined=0.92, event_center=47.0, auto_keep=True),
            _clip(start=50.0, end=54.0, label="Uncertain steal", combined=0.88, event_center=52.0, auto_keep=True),
            _clip(start=55.0, end=59.0, label="Uncertain finish", combined=0.84, event_center=57.0, auto_keep=True),
            _clip(start=60.0, end=64.0, label="Uncertain rebound", combined=0.66, event_center=62.0, auto_keep=True),
        ]
        uncertain = [
            clip.model_copy(
                update={
                    "teamAttribution": ClipTeamAttribution(
                        teamId="team_dark",
                        label="Dark jerseys",
                        colorLabel="black",
                        confidence=0.64,
                        source="gpt_frame_review",
                    )
                }
            )
            for clip in uncertain
        ]

        trimmed = _trim_analysis_clips_for_review([*matched, *uncertain], team_selection, max_clips=8)
        labels = [clip.label for clip in trimmed]

        self.assertEqual(len(trimmed), 8)
        self.assertIn("Uncertain block", labels)
        self.assertIn("Uncertain steal", labels)
        self.assertIn("Uncertain finish", labels)
        self.assertNotIn("Uncertain rebound", labels)
        self.assertNotIn("Made Shot 7", labels)

    def test_review_trim_reserves_strong_defensive_clip_when_scoring_fills_cap(self) -> None:
        scoring = [
            _clip(
                start=float(index * 5),
                end=float(index * 5 + 4),
                label=f"Made Shot {index}",
                combined=0.95 - (index * 0.01),
                event_center=float(index * 5 + 2),
                auto_keep=True,
            )
            for index in range(5)
        ]
        weak_defense = _clip(
            start=30.0,
            end=34.0,
            label="Weak block",
            combined=0.5,
            confidence=0.5,
            event_center=32.0,
            auto_keep=False,
        )
        strong_defense = _clip(
            start=35.0,
            end=39.5,
            label="Steal",
            combined=0.84,
            confidence=0.82,
            event_center=37.0,
            auto_keep=True,
        )

        trimmed = _trim_analysis_clips_for_review([*scoring, weak_defense, strong_defense], None, max_clips=4)
        labels = [clip.label for clip in trimmed]

        self.assertIn("Steal", labels)
        self.assertNotIn("Weak block", labels)
        self.assertNotIn("Made Shot 4", labels)

    def test_review_trim_reserves_block_and_steal_families_when_available(self) -> None:
        scoring = [
            _clip(
                start=float(index * 5),
                end=float(index * 5 + 4),
                label=f"Made Shot {index}",
                combined=0.99 - (index * 0.01),
                event_center=float(index * 5 + 2),
                auto_keep=True,
            )
            for index in range(9)
        ]
        block_one = _clip(start=50.0, end=54.0, label="Block", combined=0.91, event_center=52.0, auto_keep=True)
        block_two = _clip(start=55.0, end=59.0, label="Blocked shot", combined=0.90, event_center=57.0, auto_keep=True)
        block_three = _clip(start=60.0, end=64.0, label="Contest block", combined=0.89, event_center=62.0, auto_keep=True)
        steal = _clip(start=65.0, end=69.0, label="Steal", combined=0.70, event_center=67.0, auto_keep=True)

        trimmed = _trim_analysis_clips_for_review(
            [*scoring, block_one, block_two, block_three, steal],
            None,
            max_clips=8,
        )
        labels = [clip.label for clip in trimmed]

        self.assertIn("Block", labels)
        self.assertIn("Steal", labels)
        self.assertNotIn("Blocked shot", labels)
        self.assertNotIn("Contest block", labels)
        self.assertNotIn("Made Shot 6", labels)

    def test_defensive_label_classifier_ignores_stop_and_pop_jumpers(self) -> None:
        self.assertFalse(_is_defensive_label("Stop and Pop Jumper"))
        self.assertTrue(_is_defensive_label("Blocked Shot"))
        self.assertTrue(_is_defensive_label("Defensive Stop"))
        self.assertTrue(_is_defensive_label("Steal Finish"))
        self.assertTrue(_is_defensive_label("Deflection To Fast Break"))
        self.assertTrue(_is_defensive_label("Loose Ball Recovery"))
        self.assertTrue(_is_defensive_label("Takeaway"))
        self.assertTrue(_is_defensive_label("Poked Loose"))
        self.assertTrue(_is_defensive_label("Took Charge"))

    def test_defensive_label_classifier_requires_forced_turnover_context(self) -> None:
        self.assertFalse(_is_defensive_label("Turnover"))
        self.assertFalse(_is_defensive_label("Unforced Turnover"))
        self.assertTrue(_is_defensive_label("Forced Turnover"))
        self.assertTrue(_is_defensive_label("Defensive Turnover"))

    def test_selected_team_visible_results_can_exclude_uncertain_when_requested(self) -> None:
        team_selection = TeamSelection(mode="team", teamId="team_dark", colorLabel="black", includeUncertain=False)
        clips = [
            _clip(start=0.0, end=4.0, label="Made Shot", combined=0.95, event_center=2.0, auto_keep=True),
            _clip(start=5.0, end=9.0, label="Uncertain steal", combined=0.7, event_center=7.0, auto_keep=True),
        ]

        trimmed = _trim_analysis_clips_for_review(clips, team_selection, max_clips=1)

        self.assertEqual([clip.label for clip in trimmed], ["Made Shot"])

    def test_analysis_candidate_pool_limit_is_expanded_for_quality_but_bounded(self) -> None:
        self.assertEqual(_analysis_candidate_pool_limit(_analysis_settings("hybrid"), None), 16)
        self.assertEqual(_analysis_candidate_pool_limit(_analysis_settings("hybrid"), TeamSelection(mode="all")), 16)
        selected = TeamSelection(mode="team", teamId="team_dark", colorLabel="black")
        self.assertEqual(_analysis_candidate_pool_limit(_analysis_settings("hybrid"), selected), 16)
        large_settings = _analysis_settings("hybrid")
        large_settings.max_returned_clips = 60
        self.assertEqual(_analysis_candidate_pool_limit(large_settings, selected), 220)

    def test_team_quick_scan_uses_action_anchored_candidate_pool(self) -> None:
        settings = _analysis_settings("hybrid")
        settings.team_quick_scan_max_candidate_clips = 6
        native = [
            _clip(start=8.0, end=12.5, label="Three Pointer", combined=0.9, event_center=10.2, auto_keep=True),
            _clip(start=16.0, end=20.5, label="Steal", combined=0.82, event_center=18.0, auto_keep=True),
            _clip(start=24.0, end=24.1, label="Made Shot", combined=0.99, event_center=None, auto_keep=True),
        ]
        clip_limits: list[int | None] = []

        def fake_native_detection(source_path, duration_seconds, native_settings, clip_limit=None):
            clip_limits.append(clip_limit)
            return native, len(native)

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-candidates-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with (
                patch("app.pipeline._probe_duration", return_value=45.0),
                patch("app.pipeline._run_native_candidate_detection", side_effect=fake_native_detection),
            ):
                candidates = build_team_quick_scan_candidate_clips(source_path, 45.0, settings)

        self.assertEqual(clip_limits, [6])
        self.assertEqual([clip.label for clip in candidates], ["Three Pointer", "Steal"])
        self.assertTrue(all(clip.endTime - clip.startTime >= settings.min_clip_duration_seconds for clip in candidates))

    def test_analysis_team_diagnostics_split_forced_turnovers_and_defensive_stops(self) -> None:
        clips = [
            _clip(start=0.0, end=4.0, label="Block", combined=0.9, event_center=2.0, auto_keep=True),
            _clip(start=5.0, end=9.0, label="Steal", combined=0.88, event_center=7.0, auto_keep=True),
            _clip(start=10.0, end=14.0, label="Forced Turnover", combined=0.86, event_center=12.0, auto_keep=True),
            _clip(start=15.0, end=19.0, label="Defensive Stop", combined=0.84, event_center=17.0, auto_keep=True),
        ]

        diagnostics = _analysis_team_diagnostic_counts(
            candidate_clips=clips,
            review_clips=clips,
            team_selection=None,
            used_team_quick_scan=True,
        )

        self.assertEqual(diagnostics.get("defensiveReviewSegments"), 4)
        self.assertEqual(diagnostics.get("blockReviewSegments"), 1)
        self.assertEqual(diagnostics.get("stealReviewSegments"), 1)
        self.assertEqual(diagnostics.get("forcedTurnoverReviewSegments"), 1)
        self.assertEqual(diagnostics.get("defensiveStopReviewSegments"), 1)

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
        self.assertIsNotNone(normalized.nativeShotSignals)
        assert normalized.nativeShotSignals is not None
        self.assertTrue(normalized.nativeShotSignals.timingWindowOk)
        self.assertEqual(normalized.nativeShotSignals.outcome, "made")
        self.assertEqual(normalized.nativeShotSignals.outcomeEvidenceSource, "label_only")
        self.assertGreater(normalized.nativeShotSignals.outcomeReliabilityScore, 0.0)
        self.assertLessEqual(normalized.nativeShotSignals.outcomeReliabilityScore, 0.68)
        self.assertGreaterEqual(normalized.nativeShotSignals.setupContextScore, 1.0)
        self.assertGreaterEqual(normalized.nativeShotSignals.outcomeContextScore, 1.0)

    def test_analysis_normalization_expands_tiny_defensive_clip_with_event_center(self) -> None:
        tiny_steal = _clip(
            start=20.42,
            end=20.8,
            label="Steal",
            combined=0.84,
            confidence=0.82,
            event_center=20.5,
            auto_keep=True,
        )

        normalized = _normalize_clip_for_analysis_context(tiny_steal, duration_seconds=40.0, settings=_settings())

        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertLessEqual(normalized.startTime, 19.0)
        self.assertGreaterEqual(normalized.endTime, 21.7)
        self.assertGreaterEqual(normalized.endTime - normalized.startTime, _settings().min_clip_duration_seconds)
        self.assertTrue(normalized.shouldAutoKeep)
        self.assertIsNotNone(normalized.nativeShotSignals)
        assert normalized.nativeShotSignals is not None
        self.assertFalse(normalized.nativeShotSignals.isShotLike)
        self.assertTrue(normalized.nativeShotSignals.timingWindowOk)
        self.assertEqual(normalized.nativeShotSignals.outcome, "not_shot")
        self.assertEqual(normalized.nativeShotSignals.outcomeEvidenceSource, "defensive_event")
        self.assertGreaterEqual(normalized.nativeShotSignals.outcomeReliabilityScore, 0.9)

    def test_analysis_normalization_keeps_early_blocked_shot_as_defensive_context(self) -> None:
        early_block = _clip(
            start=1.15,
            end=1.25,
            label="Blocked Shot",
            combined=0.86,
            confidence=0.84,
            event_center=1.2,
            auto_keep=True,
        )

        normalized = _normalize_clip_for_analysis_context(early_block, duration_seconds=8.0, settings=_settings())

        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.startTime, 0.0)
        self.assertGreaterEqual(normalized.endTime, 3.0)
        self.assertTrue(normalized.shouldAutoKeep)
        self.assertIsNotNone(normalized.nativeShotSignals)
        assert normalized.nativeShotSignals is not None
        self.assertTrue(normalized.nativeShotSignals.isShotLike)
        self.assertTrue(normalized.nativeShotSignals.timingWindowOk)
        self.assertEqual(normalized.nativeShotSignals.outcome, "blocked")
        self.assertEqual(normalized.nativeShotSignals.outcomeEvidenceSource, "defensive_event")
        self.assertGreater(normalized.nativeShotSignals.outcomeReliabilityScore, 0.7)

    def test_analysis_normalization_keeps_early_steal_finish_as_defensive_context(self) -> None:
        early_steal_finish = _clip(
            start=0.6,
            end=0.78,
            label="Steal Finish",
            combined=0.83,
            confidence=0.8,
            event_center=0.65,
            auto_keep=True,
        )

        normalized = _normalize_clip_for_analysis_context(early_steal_finish, duration_seconds=8.0, settings=_settings())

        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.startTime, 0.0)
        self.assertGreaterEqual(normalized.endTime, 3.0)
        self.assertTrue(normalized.shouldAutoKeep)
        self.assertIsNotNone(normalized.nativeShotSignals)
        assert normalized.nativeShotSignals is not None
        self.assertTrue(normalized.nativeShotSignals.isShotLike)
        self.assertTrue(normalized.nativeShotSignals.timingWindowOk)
        self.assertEqual(normalized.nativeShotSignals.outcome, "uncertain")
        self.assertEqual(normalized.nativeShotSignals.outcomeEvidenceSource, "uncertain")
        self.assertEqual(normalized.nativeShotSignals.outcomeReliabilityScore, 0.35)

    def test_native_outcome_hints_do_not_treat_ambiguous_finishes_as_makes(self) -> None:
        for label in ("Layup", "Tough Finish"):
            with self.subTest(label=label):
                clip = _clip(
                    start=8.0,
                    end=12.5,
                    label=label,
                    combined=0.86,
                    confidence=0.9,
                    event_center=10.0,
                    auto_keep=True,
                )

                signals = _native_shot_signals_for_analysis_clip(clip)

                self.assertTrue(signals.isShotLike)
                self.assertTrue(signals.timingWindowOk)
                self.assertEqual(signals.outcome, "uncertain")
                self.assertEqual(signals.outcomeConfidence, 0.0)
                self.assertEqual(signals.outcomeEvidenceSource, "uncertain")
                self.assertEqual(signals.outcomeReliabilityScore, 0.35)

    def test_native_outcome_hints_keep_explicit_made_labels(self) -> None:
        for label in ("Made Layup", "Bucket", "Basket", "Dunk"):
            with self.subTest(label=label):
                clip = _clip(
                    start=8.0,
                    end=12.5,
                    label=label,
                    combined=0.86,
                    confidence=0.9,
                    event_center=10.0,
                    auto_keep=True,
                )

                signals = _native_shot_signals_for_analysis_clip(clip)

                self.assertEqual(signals.outcome, "made")
                self.assertGreaterEqual(signals.outcomeConfidence, 0.8)
                self.assertEqual(signals.outcomeEvidenceSource, "label_only")
                self.assertLessEqual(signals.outcomeReliabilityScore, 0.68)

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

    def test_native_candidate_backfill_keeps_review_pool_when_hysteresis_finds_few_sequences(self) -> None:
        audio_profile = [0.08] * 60
        for index in range(18, 22):
            audio_profile[index] = 0.72

        windows = _build_candidate_windows(
            duration_seconds=30.0,
            audio_profile=audio_profile,
            shot_boundaries=[10.0],
            settings=_settings(),
        )

        self.assertEqual(len(windows), _settings().max_returned_clips)
        self.assertEqual(windows[0].peak_time, 10.0)
        self.assertGreater(windows[0].event_context_score, 0.0)
        self.assertGreaterEqual(len({round(window.start_time, 1) for window in windows}), 4)

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
            (10.5, 0.32, 0.4, 0.3),
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

    def test_visual_event_detector_prefers_rim_result_over_release_spike_with_follow_through(self) -> None:
        audio_profile = [0.08] * 40
        for index in range(18, 22):
            audio_profile[index] = 0.62
        frame_signals = [
            (8.5, 0.2, 0.34, 0.22),
            (9.5, 0.82, 0.95, 0.8),
            (10.0, 0.55, 0.72, 0.58),
            (10.5, 0.36, 0.45, 0.35),
        ]

        boundaries = _visual_event_boundaries_from_signals(
            frame_signals,
            audio_profile,
            duration_seconds=20.0,
        )

        self.assertEqual(boundaries, [10.0])

    def test_visual_event_detector_uses_below_rim_result_lane_over_release_motion(self) -> None:
        audio_profile = [0.08] * 40
        for index in range(18, 22):
            audio_profile[index] = 0.62
        frame_signals = [
            (8.5, 0.18, 0.32, 0.22, 0.08),
            (9.5, 0.76, 0.95, 0.55, 0.08),
            (10.0, 0.52, 0.48, 0.66, 0.88),
            (10.5, 0.33, 0.22, 0.38, 0.68),
        ]

        boundaries = _visual_event_boundaries_from_signals(
            frame_signals,
            audio_profile,
            duration_seconds=20.0,
        )

        self.assertEqual(boundaries, [10.0])

    def test_visual_event_detector_rejects_release_only_spike_without_followthrough(self) -> None:
        audio_profile = [0.08] * 40
        for index in range(18, 22):
            audio_profile[index] = 0.62
        frame_signals = [
            (8.0, 0.2, 0.32, 0.2),
            (9.0, 0.22, 0.36, 0.22),
            (9.5, 0.88, 0.96, 0.84),
            (10.5, 0.05, 0.06, 0.05),
        ]

        boundaries = _visual_event_boundaries_from_signals(
            frame_signals,
            audio_profile,
            duration_seconds=20.0,
        )

        self.assertEqual(boundaries, [])

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

    def test_classifier_keeps_shot_candidate_without_claiming_made_outcome_from_motion_only_context(self) -> None:
        shot_attempt_window = CandidateWindow(
            start_time=8.0,
            end_time=12.5,
            peak_time=10.0,
            audio_score=0.48,
            visual_score=0.66,
            motion_score=0.5,
            combined_score=0.7,
            event_context_score=0.72,
        )

        clip = classify_window(shot_attempt_window)

        self.assertEqual(clip.label, "Shot Attempt")
        self.assertTrue(clip.shouldAutoKeep)

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
                    ",".join(
                        [
                            "drawbox=x=72:y=14:w=36:h=36:color=white@1:t=fill:enable='between(t,2.5,3.2)'",
                            "drawbox=x=72:y=28:w=36:h=20:color=white@1:t=fill:enable='between(t,3.5,4.2)'",
                            "drawbox=x=76:y=44:w=28:h=14:color=white@1:t=fill:enable='between(t,4.5,5.2)'",
                        ]
                    ),
                    "-pix_fmt",
                    "yuv420p",
                    str(video_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            boundaries = _detect_shot_boundaries(video_path, duration_seconds=8.0, audio_profile=[0.05] * 16)

        self.assertTrue(any(4.0 <= boundary <= 4.8 for boundary in boundaries))


if __name__ == "__main__":
    unittest.main()
