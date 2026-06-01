from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import CloudAnalysisResult, CloudClip, CloudDiagnostics, ClipTeamAttribution, MaterializedSource, TeamOption, TeamSelection
from app.pipeline import (
    _annotate_analysis_team_status,
    _filter_analysis_clips_for_team_selection,
    _trim_analysis_clips_for_review,
)
from app.team_quick_scan import (
    QuickScanFrame,
    _clip_sample_times,
    _extract_quick_scan_frames,
    _max_quick_scan_total_clip_frames,
    apply_team_quick_scan,
    team_quick_prescan_settings,
)


def _settings(**overrides):
    values = {
        "team_quick_scan_enabled": True,
        "team_quick_scan_api_key": "test-key",
        "team_quick_scan_model": "gpt-4.1",
        "team_quick_scan_endpoint": "https://api.openai.com/v1/responses",
        "team_quick_scan_timeout_seconds": 12.0,
        "team_quick_scan_video_frame_count": 6,
        "team_quick_scan_clip_frames_per_clip": 8,
        "team_quick_scan_rich_candidate_clips": 220,
        "team_quick_scan_max_total_clip_frames": 2560,
        "team_quick_scan_frame_width": 720,
        "team_quick_scan_jpeg_quality": 4,
        "team_quick_scan_max_image_bytes": 500_000,
        "team_quick_scan_min_team_confidence": 0.55,
        "team_quick_scan_max_candidate_clips": 320,
        "team_quick_scan_max_output_tokens": 18000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _clip(label: str, start: float, end: float, event_center: float, combined: float = 0.82) -> CloudClip:
    return CloudClip(
        startTime=start,
        endTime=end,
        eventCenter=event_center,
        confidence=0.86,
        label=label,
        action=label,
        audioScore=0.6,
        visualScore=0.78,
        motionScore=0.74,
        combinedScore=combined,
        detectionMethod="cloud",
        shouldAutoKeep=True,
        shouldEnableSlowMotion=False,
    )


def _team_clip(
    label: str,
    start: float,
    team_id: str,
    color_label: str,
    confidence: float,
    *,
    status: str | None = None,
) -> CloudClip:
    return _clip(label, start, start + 4.5, start + 2.1).model_copy(
        update={
            "teamAttribution": ClipTeamAttribution(
                teamId=team_id,
                label=f"{color_label.title()} jerseys",
                colorLabel=color_label,
                confidence=confidence,
                source="quick_scan",
                evidenceFrameRefs=[f"{team_id}_{label}_setup", f"{team_id}_{label}_outcome"],
                evidenceRoleGroups=["setup", "outcome"],
            ),
            "teamAttributionStatus": status,
        }
    )


def _response(payload: dict) -> dict:
    return {"output": [{"content": [{"type": "output_text", "text": json.dumps(payload)}]}]}


def _local_settings(upload_root: Path) -> Settings:
    return Settings(
        service_name="hoops-ai-api",
        environment="local",
        host_base_url="http://127.0.0.1:8080",
        cloud_run_base_url="http://127.0.0.1:8080",
        upload_root=upload_root,
        external_repo_root=upload_root / "external",
        internal_process_secret=None,
        public_api_enabled=True,
        gcp_project_id=None,
        gcp_region="us-central1",
        gcs_bucket_name="charlie-hoops-ai-analysis-temp",
        firestore_jobs_collection="analysisJobs",
        firestore_usage_collection="usageCounters",
        cloud_tasks_queue="analysis-jobs",
        enable_local_upload_emulation=True,
        detection_provider="hybrid",
        post_ranking_provider="native",
        hoopcut_repo_path=None,
        hoopcut_python_bin=None,
        autohighlight_repo_path=None,
        autohighlight_python_bin=None,
        daily_quota=3,
        rolling_quota_hours=24,
        default_poll_after_seconds=1,
        job_ttl_seconds=3600,
        signed_upload_ttl_seconds=900,
        max_file_size_bytes=500 * 1024 * 1024,
        max_duration_seconds=1800.0,
        min_clip_duration_seconds=2.0,
        max_clip_duration_seconds=15.0,
        clip_padding_seconds=0.35,
        max_returned_clips=8,
        backend_model_version="cloud-v1",
        use_gemini_relabeling=False,
        team_quick_scan_enabled=True,
        team_quick_scan_api_key="test-key",
    )


def _create_uploaded_job(client: TestClient, team_selection: dict | None = None) -> dict:
    request_payload = {
        "filename": "game.mp4",
        "contentType": "video/mp4",
        "fileSizeBytes": 9,
        "durationSeconds": 30.0,
        "installId": "install-123456",
        "appVersion": "1.0",
        "analysisVersion": "cloud-v1",
    }
    if team_selection is not None:
        request_payload["teamSelection"] = team_selection
    create_response = client.post(
        "/v1/analysis/jobs",
        json=request_payload,
    )
    assert create_response.status_code == 200
    created = create_response.json()
    upload_response = client.put(created["uploadUrl"], content=b"fakevideo")
    assert upload_response.status_code == 204
    return created


def _poll_analysis_job_until_terminal(client: TestClient, job_id: str, *, attempts: int = 240) -> dict:
    payload: dict | None = None
    for _ in range(attempts):
        poll_response = client.get(f"/v1/analysis/jobs/{job_id}")
        assert poll_response.status_code == 200
        payload = poll_response.json()
        if payload["status"] in {"succeeded", "failed", "expired"}:
            return payload
        time.sleep(0.05)
    assert payload is not None
    return payload


class TeamQuickScanTests(unittest.TestCase):
    def test_prescan_settings_keep_interactive_team_scan_bounded(self) -> None:
        settings = _local_settings(Path("/tmp/hoopclips-prescan")).__dict__.copy()
        full_settings = Settings(
            **{
                **settings,
                "team_quick_scan_timeout_seconds": 24.0,
                "team_quick_scan_max_candidate_clips": 320,
                "team_quick_scan_rich_candidate_clips": 220,
                "team_quick_scan_clip_frames_per_clip": 8,
                "team_quick_scan_max_total_clip_frames": 2560,
            }
        )

        prescan = team_quick_prescan_settings(full_settings)

        self.assertEqual(prescan.team_quick_scan_max_candidate_clips, 12)
        self.assertEqual(prescan.team_quick_scan_rich_candidate_clips, 8)
        self.assertEqual(prescan.team_quick_scan_clip_frames_per_clip, 4)
        self.assertEqual(prescan.team_quick_scan_max_total_clip_frames, 56)
        self.assertEqual(prescan.team_quick_scan_timeout_seconds, 60.0)
        self.assertEqual(full_settings.team_quick_scan_max_candidate_clips, 320)

    def test_disabled_scan_falls_back_without_calling_gpt(self) -> None:
        clips = [_clip("Three Pointer", 8.0, 12.5, 10.2)]

        def fail_client(*_args):
            raise AssertionError("GPT quick scan should not be called when disabled")

        scanned, teams, applied = apply_team_quick_scan(
            Path("/tmp/source.mp4"),
            30.0,
            clips,
            _settings(team_quick_scan_enabled=False),
            response_client=fail_client,
        )

        self.assertEqual(scanned, clips)
        self.assertEqual(teams, [])
        self.assertFalse(applied)

    def test_payload_uses_sampled_frames_not_full_video_and_applies_attribution(self) -> None:
        clips = [
            _clip("Three Pointer", 8.0, 12.5, 10.2),
            _clip("Steal", 18.0, 22.0, 20.0),
        ]
        frames = [
            QuickScanFrame(frame_ref="video_0", role="videoContext", time_seconds=3.0, data_url="data:image/jpeg;base64,aaa"),
            QuickScanFrame(frame_ref="clip_0_event", role="eventCenter", time_seconds=10.2, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_1_event", role="eventCenter", time_seconds=20.0, data_url="data:image/jpeg;base64,ccc", clip_ref="clip_1"),
        ]
        captured_payload = {}

        def fake_client(payload, api_key, endpoint, timeout):
            captured_payload.update(payload)
            self.assertEqual(api_key, "test-key")
            self.assertEqual(endpoint, "https://api.openai.com/v1/responses")
            self.assertEqual(timeout, 12.0)
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "primaryColorHex": "#111111",
                            "confidence": 0.92,
                            "reason": "Most sampled players wear black jerseys.",
                        },
                        {
                            "teamId": "team_light",
                            "label": "Light jerseys",
                            "colorLabel": "white",
                            "primaryColorHex": "#f2f2f2",
                            "confidence": 0.9,
                            "reason": "Opponent mostly wears white jerseys.",
                        },
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.91,
                            "reason": "Shooter in black controls the play.",
                        },
                        {
                            "clipRef": "clip_1",
                            "teamId": "team_light",
                            "label": "Light jerseys",
                            "colorLabel": "white",
                            "confidence": 0.88,
                            "reason": "Defender in white creates the steal.",
                        },
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-test-") as temp_dir:
            source_path = Path(temp_dir) / "full-game.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, teams, applied = apply_team_quick_scan(
                    source_path,
                    30.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        serialized_payload = json.dumps(captured_payload)
        self.assertIn("data:image/jpeg;base64,aaa", serialized_payload)
        self.assertNotIn("/private/tmp/full-game.mp4", serialized_payload)
        self.assertNotIn("videoUrl", serialized_payload)
        self.assertFalse(captured_payload["store"])
        self.assertEqual(captured_payload["text"]["format"]["type"], "json_schema")
        self.assertTrue(captured_payload["text"]["format"]["strict"])
        self.assertEqual([team.teamId for team in teams], ["team_dark", "team_light"])
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_dark")
        self.assertEqual(scanned[0].teamAttribution.source, "gpt_frame_review")
        self.assertEqual(scanned[1].teamAttribution.colorLabel, "white")

    def test_payload_can_attribute_expanded_selected_team_candidate_pool(self) -> None:
        clips = [
            _clip("Steal" if index == 74 else "Made Shot", index * 4.0, (index * 4.0) + 3.5, (index * 4.0) + 2.0)
            for index in range(75)
        ]
        frames = [
            QuickScanFrame(
                frame_ref=f"clip_{index}_event",
                role="eventCenter",
                time_seconds=clip.eventCenter or clip.startTime,
                data_url=f"data:image/jpeg;base64,{index}",
                clip_ref=f"clip_{index}",
            )
            for index, clip in enumerate(clips)
        ]
        captured_payload = {}

        def fake_client(payload, *_args):
            captured_payload.update(payload)
            context = json.loads(payload["input"][0]["content"][0]["text"])
            self.assertEqual(len(context["candidateClips"]), 75)
            self.assertEqual(context["candidateClips"][-1]["clipRef"], "clip_74")
            self.assertIn("scoringFrameRoles", context["rules"])
            self.assertIn("defensiveFrameRoles", context["rules"])
            self.assertIn("evidencePolicy", context["rules"])
            self.assertEqual(payload["text"]["format"]["schema"]["properties"]["clipAttributions"]["maxItems"], 75)
            attribution_schema = payload["text"]["format"]["schema"]["properties"]["clipAttributions"]["items"]
            self.assertIn("evidenceFrameRefs", attribution_schema["properties"])
            self.assertIn("evidenceFrameRefs", attribution_schema["required"])
            self.assertEqual(payload["max_output_tokens"], 18000)
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "primaryColorHex": "#111111",
                            "confidence": 0.92,
                            "reason": "Dark jerseys are visible across sampled clips.",
                        }
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_74",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.88,
                            "reason": "Defender in black creates the steal.",
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-expanded-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, teams, applied = apply_team_quick_scan(
                    source_path,
                    360.0,
                    clips,
                    _settings(team_quick_scan_max_candidate_clips=75),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual(teams[0].teamId, "team_dark")
        self.assertIsNotNone(scanned[74].teamAttribution)
        self.assertEqual(scanned[74].teamAttribution.teamId, "team_dark")
        self.assertNotIn("videoUrl", json.dumps(captured_payload))

    def test_detected_team_options_are_normalized_to_jersey_colors(self) -> None:
        clips = [
            _clip("Made Shot", 8.0, 12.5, 10.0),
            _clip("Steal", 18.0, 22.0, 20.0),
        ]
        frames = [
            QuickScanFrame(frame_ref="clip_0_release", role="release", time_seconds=9.0, data_url="data:image/jpeg;base64,aaa", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_1_possession", role="possessionChange", time_seconds=20.0, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_1"),
        ]

        def fake_client(*_args):
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "home",
                            "label": "Home team",
                            "colorLabel": None,
                            "primaryColorHex": None,
                            "confidence": 0.99,
                            "reason": "This is not a jersey-color label and should not be selectable.",
                        },
                        {
                            "teamId": "home",
                            "label": "Home team",
                            "colorLabel": "black",
                            "primaryColorHex": "#111111",
                            "confidence": 0.94,
                            "reason": "Home players wear black jerseys.",
                        },
                        {
                            "teamId": "away",
                            "label": "Away team",
                            "colorLabel": "white",
                            "primaryColorHex": "#ffffff",
                            "confidence": 0.91,
                            "reason": "Away players wear white jerseys.",
                        },
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "home",
                            "label": "Home team",
                            "colorLabel": None,
                            "confidence": 0.93,
                            "reason": "Shooter is on the home team.",
                        },
                        {
                            "clipRef": "clip_1",
                            "teamId": "away",
                            "label": "Away team",
                            "colorLabel": "white",
                            "confidence": 0.9,
                            "reason": "Defender in white steals the ball.",
                        },
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-colors-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, teams, applied = apply_team_quick_scan(
                    source_path,
                    30.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual([team.teamId for team in teams], ["team_black", "team_white"])
        self.assertEqual([team.label for team in teams], ["Black jerseys", "White jerseys"])
        self.assertEqual([team.colorLabel for team in teams], ["black", "white"])
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_black")
        self.assertEqual(scanned[0].teamAttribution.label, "Black jerseys")
        self.assertEqual(scanned[0].teamAttribution.colorLabel, "black")
        self.assertEqual(scanned[1].teamAttribution.teamId, "team_white")

    def test_defensive_quick_scan_samples_possession_change_roles(self) -> None:
        steal = _clip("Steal", 18.0, 22.0, 20.0)
        block = _clip("Block", 6.0, 10.5, 8.0)
        forced_turnover = _clip("Forced Turnover", 32.0, 36.5, 34.0)

        steal_roles = [role for role, _ in _clip_sample_times(steal, 3)]
        block_roles = [role for role, _ in _clip_sample_times(block, 3)]
        turnover_roles = [role for role, _ in _clip_sample_times(forced_turnover, 3)]

        self.assertEqual(steal_roles, ["defenseSetup", "possessionChange", "recovery"])
        self.assertEqual(block_roles, ["defenseSetup", "challenge", "defenseOutcome"])
        self.assertEqual(turnover_roles, ["defenseSetup", "possessionChange", "recovery"])

    def test_rich_defensive_quick_scan_samples_full_ownership_roles(self) -> None:
        steal = _clip("Steal", 18.0, 22.0, 20.0)
        block = _clip("Block", 6.0, 10.5, 8.0)

        steal_roles = [role for role, _ in _clip_sample_times(steal, 8)]
        block_roles = [role for role, _ in _clip_sample_times(block, 8)]

        self.assertEqual(
            steal_roles,
            [
                "defenseSetup",
                "prePossessionChange",
                "possessionPressure",
                "possessionChange",
                "ballControlChange",
                "recovery",
                "defenseOutcome",
                "finishContext",
            ],
        )
        self.assertEqual(
            block_roles,
            [
                "defenseSetup",
                "preChallenge",
                "challenge",
                "ballDeflection",
                "defenseOutcome",
                "recovery",
                "finishContext",
                "aftermath",
            ],
        )

    def test_scoring_quick_scan_samples_shooter_release_roles(self) -> None:
        made_shot = _clip("Made Shot", 8.0, 12.5, 10.0)

        roles = [role for role, _ in _clip_sample_times(made_shot, 4)]

        self.assertEqual(roles, ["ballHandlerSetup", "release", "rimResult", "followThrough"])

    def test_stop_and_pop_jumper_uses_scoring_roles_not_defensive_stop(self) -> None:
        jumper = _clip("Stop and Pop Jumper", 8.0, 12.5, 10.0)

        roles = [role for role, _ in _clip_sample_times(jumper, 4)]

        self.assertEqual(roles, ["ballHandlerSetup", "release", "rimResult", "followThrough"])

    def test_plain_turnover_uses_generic_roles_not_defensive_ownership(self) -> None:
        turnover = _clip("Turnover", 8.0, 12.5, 10.0)

        roles = [role for role, _ in _clip_sample_times(turnover, 4)]

        self.assertEqual(roles, ["startContext", "eventCenter", "finishContext", "midAction"])

    def test_rich_scoring_quick_scan_samples_full_shooter_and_result_roles(self) -> None:
        made_shot = _clip("Made Shot", 8.0, 12.5, 10.0)

        roles = [role for role, _ in _clip_sample_times(made_shot, 8)]

        self.assertEqual(
            roles,
            [
                "ballHandlerSetup",
                "preRelease",
                "release",
                "shotArc",
                "rimApproach",
                "rimResult",
                "followThrough",
                "finishContext",
            ],
        )

    def test_frame_extraction_respects_configurable_candidate_limit(self) -> None:
        clips = [_clip("Highlight", index * 4.0, (index * 4.0) + 3.0, (index * 4.0) + 1.5) for index in range(50)]
        settings = _settings(
            team_quick_scan_max_candidate_clips=12,
            team_quick_scan_video_frame_count=2,
            team_quick_scan_clip_frames_per_clip=1,
        )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-limit-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_frame_data_url", return_value="data:image/jpeg;base64,frame"):
                frames = _extract_quick_scan_frames(source_path, 240.0, clips, settings)

        clip_refs = {frame.clip_ref for frame in frames if frame.clip_ref is not None}
        self.assertIn("clip_11", clip_refs)
        self.assertNotIn("clip_12", clip_refs)
        self.assertEqual(len([frame for frame in frames if frame.clip_ref is not None]), 12)

    def test_frame_extraction_uses_defensive_roles_for_blocks_and_steals(self) -> None:
        clips = [
            _clip("Steal", 18.0, 22.0, 20.0),
            _clip("Block", 26.0, 30.0, 28.0),
        ]

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-defense-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_frame_data_url", return_value="data:image/jpeg;base64,frame"):
                frames = _extract_quick_scan_frames(
                    source_path,
                    40.0,
                    clips,
                    _settings(team_quick_scan_video_frame_count=0, team_quick_scan_clip_frames_per_clip=3),
                )

        roles_by_clip = {}
        for frame in frames:
            if frame.clip_ref is not None:
                roles_by_clip.setdefault(frame.clip_ref, []).append(frame.role)

        self.assertEqual(roles_by_clip["clip_0"], ["defenseSetup", "possessionChange", "recovery"])
        self.assertEqual(roles_by_clip["clip_1"], ["defenseSetup", "challenge", "defenseOutcome"])

    def test_frame_extraction_uses_scoring_roles_for_made_shots(self) -> None:
        clips = [_clip("Made Shot", 8.0, 12.5, 10.0)]

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-scoring-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_frame_data_url", return_value="data:image/jpeg;base64,frame"):
                frames = _extract_quick_scan_frames(
                    source_path,
                    40.0,
                    clips,
                    _settings(team_quick_scan_video_frame_count=0, team_quick_scan_clip_frames_per_clip=4),
                )

        roles = [frame.role for frame in frames if frame.clip_ref == "clip_0"]

        self.assertEqual(roles, ["ballHandlerSetup", "release", "rimResult", "followThrough"])

    def test_frame_extraction_uses_rich_frames_for_top_candidates_and_compact_frames_for_tail(self) -> None:
        clips = [_clip("Made Shot", float(index * 5), float(index * 5 + 4), float(index * 5 + 2)) for index in range(5)]

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-rich-budget-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_frame_data_url", return_value="data:image/jpeg;base64,frame"):
                frames = _extract_quick_scan_frames(
                    source_path,
                    40.0,
                    clips,
                    _settings(
                        team_quick_scan_video_frame_count=0,
                        team_quick_scan_clip_frames_per_clip=6,
                        team_quick_scan_rich_candidate_clips=2,
                        team_quick_scan_max_total_clip_frames=21,
                    ),
                )

        roles_by_clip = {}
        for frame in frames:
            if frame.clip_ref is not None:
                roles_by_clip.setdefault(frame.clip_ref, []).append(frame.role)

        self.assertEqual(
            roles_by_clip["clip_0"],
            ["ballHandlerSetup", "preRelease", "release", "rimApproach", "rimResult", "followThrough"],
        )
        self.assertEqual(
            roles_by_clip["clip_1"],
            ["ballHandlerSetup", "preRelease", "release", "rimApproach", "rimResult", "followThrough"],
        )
        self.assertEqual(roles_by_clip["clip_2"], ["ballHandlerSetup", "release", "rimResult"])
        self.assertEqual(roles_by_clip["clip_3"], ["ballHandlerSetup", "release", "rimResult"])
        self.assertEqual(roles_by_clip["clip_4"], ["ballHandlerSetup", "release", "rimResult"])
        self.assertEqual(len([frame for frame in frames if frame.clip_ref is not None]), 21)

    def test_total_clip_frame_budget_allows_configured_beta_ceiling(self) -> None:
        self.assertEqual(_max_quick_scan_total_clip_frames(_settings(team_quick_scan_max_total_clip_frames=600)), 600)
        self.assertEqual(_max_quick_scan_total_clip_frames(_settings(team_quick_scan_max_total_clip_frames=720)), 720)
        self.assertEqual(_max_quick_scan_total_clip_frames(_settings(team_quick_scan_max_total_clip_frames=1200)), 1200)
        self.assertEqual(_max_quick_scan_total_clip_frames(_settings(team_quick_scan_max_total_clip_frames=2000)), 2000)
        self.assertEqual(_max_quick_scan_total_clip_frames(_settings(team_quick_scan_max_total_clip_frames=9999)), 3200)

    def test_low_confidence_clip_attribution_is_kept_as_uncertain_signal(self) -> None:
        clips = [_clip("Block", 6.0, 10.5, 8.0)]
        frames = [
            QuickScanFrame(frame_ref="video_0", role="videoContext", time_seconds=2.0, data_url="data:image/jpeg;base64,aaa"),
            QuickScanFrame(frame_ref="clip_0_event", role="eventCenter", time_seconds=8.0, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_0"),
        ]

        def fake_client(*_args):
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "primaryColorHex": None,
                            "confidence": 0.89,
                            "reason": "Dark jerseys are visible.",
                        }
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.64,
                            "reason": "Block ownership is partially occluded.",
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-test-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, teams, applied = apply_team_quick_scan(
                    source_path,
                    18.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual(teams[0].teamId, "team_dark")
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_dark")
        self.assertLess(scanned[0].teamAttribution.confidence, 0.85)

    def test_clip_attribution_is_capped_by_detected_team_confidence(self) -> None:
        clips = [_clip("Made Shot", 8.0, 12.5, 10.0)]
        frames = [
            QuickScanFrame(frame_ref="clip_0_release", role="release", time_seconds=9.0, data_url="data:image/jpeg;base64,aaa", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_0_result", role="rimResult", time_seconds=10.0, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_0"),
        ]

        def fake_client(*_args):
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "primaryColorHex": None,
                            "confidence": 0.62,
                            "reason": "Dark jerseys are visible but several frames are blurry.",
                        }
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.96,
                            "reason": "Shooter appears to wear black.",
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-teamcap-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, teams, applied = apply_team_quick_scan(
                    source_path,
                    18.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual(teams[0].confidence, 0.62)
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_dark")
        self.assertEqual(scanned[0].teamAttribution.confidence, 0.62)

    def test_high_confidence_clip_attribution_requires_sampled_frame_evidence(self) -> None:
        clips = [_clip("Made Shot", 8.0, 12.5, 10.0)]
        frames = [
            QuickScanFrame(frame_ref="clip_0_release", role="release", time_seconds=9.0, data_url="data:image/jpeg;base64,aaa", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_0_result", role="rimResult", time_seconds=10.0, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_0"),
        ]

        def fake_client(*_args):
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "primaryColorHex": None,
                            "confidence": 0.93,
                            "reason": "Dark jerseys are visible.",
                        }
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.96,
                            "reason": "Shooter appears to wear black but cites an unsampled clip frame.",
                            "evidenceFrameRefs": ["clip_99_release"],
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-evidencecap-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, teams, applied = apply_team_quick_scan(
                    source_path,
                    18.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual(teams[0].confidence, 0.93)
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_dark")
        self.assertLess(scanned[0].teamAttribution.confidence, 0.85)
        self.assertEqual(scanned[0].teamAttribution.evidenceFrameRefs, [])
        self.assertEqual(scanned[0].teamAttribution.evidenceRoleGroups, [])

    def test_high_confidence_clip_attribution_accepts_matching_sampled_frame_evidence(self) -> None:
        clips = [_clip("Made Shot", 8.0, 12.5, 10.0)]
        frames = [
            QuickScanFrame(frame_ref="clip_0_release", role="release", time_seconds=9.0, data_url="data:image/jpeg;base64,aaa", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_0_result", role="rimResult", time_seconds=10.0, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_0"),
        ]

        def fake_client(*_args):
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "primaryColorHex": None,
                            "confidence": 0.93,
                            "reason": "Dark jerseys are visible.",
                        }
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.91,
                            "reason": "Release and rim-result frames show the shooter in black.",
                            "evidenceFrameRefs": ["clip_0_release", "clip_0_result"],
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-evidencepass-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, _teams, applied = apply_team_quick_scan(
                    source_path,
                    18.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_dark")
        self.assertEqual(scanned[0].teamAttribution.confidence, 0.91)
        self.assertEqual(scanned[0].teamAttribution.evidenceFrameRefs, ["clip_0_release", "clip_0_result"])
        self.assertEqual(scanned[0].teamAttribution.evidenceRoleGroups, ["action", "outcome"])

    def test_high_confidence_steal_attribution_requires_possession_change_evidence(self) -> None:
        clips = [_clip("Steal", 18.0, 22.0, 20.0)]
        frames = [
            QuickScanFrame(frame_ref="clip_0_setup", role="defenseSetup", time_seconds=18.4, data_url="data:image/jpeg;base64,aaa", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_0_outcome", role="defenseOutcome", time_seconds=21.4, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_0"),
        ]

        def fake_client(*_args):
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "primaryColorHex": None,
                            "confidence": 0.93,
                            "reason": "Dark jerseys are visible.",
                        }
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.92,
                            "reason": "Dark jerseys are defending, but the cited frames miss the steal action.",
                            "evidenceFrameRefs": ["clip_0_setup", "clip_0_outcome"],
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-steal-missingaction-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, _teams, applied = apply_team_quick_scan(
                    source_path,
                    24.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_dark")
        self.assertLess(scanned[0].teamAttribution.confidence, 0.85)
        self.assertEqual(scanned[0].teamAttribution.evidenceFrameRefs, ["clip_0_setup", "clip_0_outcome"])
        self.assertEqual(scanned[0].teamAttribution.evidenceRoleGroups, ["setup", "outcome"])

    def test_high_confidence_steal_attribution_accepts_possession_change_evidence(self) -> None:
        clips = [_clip("Steal", 18.0, 22.0, 20.0)]
        frames = [
            QuickScanFrame(frame_ref="clip_0_change", role="possessionChange", time_seconds=20.0, data_url="data:image/jpeg;base64,aaa", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_0_outcome", role="defenseOutcome", time_seconds=21.4, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_0"),
        ]

        def fake_client(*_args):
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "primaryColorHex": None,
                            "confidence": 0.93,
                            "reason": "Dark jerseys are visible.",
                        }
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.92,
                            "reason": "Possession-change and outcome frames show the steal by the dark jerseys.",
                            "evidenceFrameRefs": ["clip_0_change", "clip_0_outcome"],
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-steal-action-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, _teams, applied = apply_team_quick_scan(
                    source_path,
                    24.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_dark")
        self.assertEqual(scanned[0].teamAttribution.confidence, 0.92)
        self.assertEqual(scanned[0].teamAttribution.evidenceFrameRefs, ["clip_0_change", "clip_0_outcome"])
        self.assertEqual(scanned[0].teamAttribution.evidenceRoleGroups, ["action", "outcome"])

    def test_high_confidence_scoring_attribution_requires_shooter_ownership_frame(self) -> None:
        clips = [_clip("Made Shot", 8.0, 12.5, 10.0)]
        frames = [
            QuickScanFrame(frame_ref="clip_0_arc", role="shotArc", time_seconds=9.5, data_url="data:image/jpeg;base64,aaa", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_0_result", role="rimResult", time_seconds=10.0, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_0"),
        ]

        def fake_client(*_args):
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "primaryColorHex": None,
                            "confidence": 0.93,
                            "reason": "Dark jerseys are visible.",
                        }
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.91,
                            "reason": "Shot arc and rim result show a make, but not the shooter jersey.",
                            "evidenceFrameRefs": ["clip_0_arc", "clip_0_result"],
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-shotownership-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, _teams, applied = apply_team_quick_scan(
                    source_path,
                    18.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_dark")
        self.assertLess(scanned[0].teamAttribution.confidence, 0.85)
        self.assertEqual(scanned[0].teamAttribution.evidenceFrameRefs, ["clip_0_arc", "clip_0_result"])
        self.assertEqual(scanned[0].teamAttribution.evidenceRoleGroups, ["action", "outcome"])

    def test_high_confidence_clip_attribution_requires_two_sampled_frame_refs(self) -> None:
        clips = [_clip("Made Shot", 8.0, 12.5, 10.0)]
        frames = [
            QuickScanFrame(frame_ref="clip_0_release", role="release", time_seconds=9.0, data_url="data:image/jpeg;base64,aaa", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_0_result", role="rimResult", time_seconds=10.0, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_0"),
        ]

        def fake_client(*_args):
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "primaryColorHex": None,
                            "confidence": 0.93,
                            "reason": "Dark jerseys are visible.",
                        }
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.91,
                            "reason": "Only the release frame supports team ownership.",
                            "evidenceFrameRefs": ["clip_0_release"],
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-oneevidence-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, _teams, applied = apply_team_quick_scan(
                    source_path,
                    18.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_dark")
        self.assertLess(scanned[0].teamAttribution.confidence, 0.85)
        self.assertEqual(scanned[0].teamAttribution.evidenceFrameRefs, ["clip_0_release"])
        self.assertEqual(scanned[0].teamAttribution.evidenceRoleGroups, ["action"])

    def test_high_confidence_clip_attribution_requires_distinct_evidence_role_groups(self) -> None:
        clips = [_clip("Made Shot", 8.0, 12.5, 10.0)]
        frames = [
            QuickScanFrame(frame_ref="clip_0_release", role="release", time_seconds=9.0, data_url="data:image/jpeg;base64,aaa", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_0_arc", role="shotArc", time_seconds=9.5, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_0_result", role="rimResult", time_seconds=10.0, data_url="data:image/jpeg;base64,ccc", clip_ref="clip_0"),
        ]

        def fake_client(*_args):
            return _response(
                {
                    "teams": [
                        {
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "primaryColorHex": None,
                            "confidence": 0.93,
                            "reason": "Dark jerseys are visible.",
                        }
                    ],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.91,
                            "reason": "Only action-phase frames are cited.",
                            "evidenceFrameRefs": ["clip_0_release", "clip_0_arc"],
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-samephase-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, _teams, applied = apply_team_quick_scan(
                    source_path,
                    18.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_dark")
        self.assertLess(scanned[0].teamAttribution.confidence, 0.85)
        self.assertEqual(scanned[0].teamAttribution.evidenceFrameRefs, ["clip_0_release", "clip_0_arc"])
        self.assertEqual(scanned[0].teamAttribution.evidenceRoleGroups, ["action"])

    def test_clip_attribution_without_detected_team_stays_uncertain(self) -> None:
        clips = [_clip("Made Shot", 8.0, 12.5, 10.0)]
        frames = [
            QuickScanFrame(frame_ref="clip_0_release", role="release", time_seconds=9.0, data_url="data:image/jpeg;base64,aaa", clip_ref="clip_0"),
            QuickScanFrame(frame_ref="clip_0_result", role="rimResult", time_seconds=10.0, data_url="data:image/jpeg;base64,bbb", clip_ref="clip_0"),
        ]

        def fake_client(*_args):
            return _response(
                {
                    "teams": [],
                    "clipAttributions": [
                        {
                            "clipRef": "clip_0",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "confidence": 0.96,
                            "reason": "Shooter appears to wear black, but team list was not detected.",
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-missingteam-") as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"video")
            with patch("app.team_quick_scan._extract_quick_scan_frames", return_value=frames):
                scanned, teams, applied = apply_team_quick_scan(
                    source_path,
                    18.0,
                    clips,
                    _settings(),
                    response_client=fake_client,
                )

        self.assertTrue(applied)
        self.assertEqual(teams, [])
        self.assertEqual(scanned[0].teamAttribution.teamId, "team_dark")
        self.assertLess(scanned[0].teamAttribution.confidence, 0.85)

    def test_start_rejects_selected_team_without_scan_backed_option(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-required-") as temp_dir:
            settings = _local_settings(Path(temp_dir))
            app = create_app(settings)
            client = TestClient(app)
            created = _create_uploaded_job(client)

            start_response = client.post(
                f"/v1/analysis/jobs/{created['jobId']}/start",
                json={
                    "installId": "install-123456",
                    "teamSelection": {
                        "mode": "team",
                        "teamId": "team_dark",
                        "label": "Dark jerseys",
                        "colorLabel": "black",
                        "includeUncertain": True,
                    },
                },
            )

            self.assertEqual(start_response.status_code, 400)
            self.assertEqual(start_response.json()["errorCode"], "team_scan_required")

    def test_start_rejects_selected_team_not_returned_by_scan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-mismatch-") as temp_dir:
            settings = _local_settings(Path(temp_dir))
            app = create_app(settings)
            client = TestClient(app)
            created = _create_uploaded_job(client)
            detected = [
                TeamOption(teamId="team_dark", label="Dark jerseys", colorLabel="black", confidence=0.92, source="quick_scan"),
            ]

            with (
                patch("app.api.build_team_quick_scan_candidate_clips", return_value=[_clip("Block", 12.0, 16.5, 14.0)]),
                patch("app.api.apply_team_quick_scan", return_value=([], detected, True)),
            ):
                scan_response = client.post(
                    f"/v1/analysis/jobs/{created['jobId']}/team-scan",
                    json={"installId": "install-123456"},
                )

            self.assertEqual(scan_response.status_code, 200)
            self.assertEqual(scan_response.json()["detectedTeams"][0]["teamId"], "team_dark")

            start_response = client.post(
                f"/v1/analysis/jobs/{created['jobId']}/start",
                json={
                    "installId": "install-123456",
                    "teamSelection": {
                        "mode": "team",
                        "teamId": "team_light",
                        "label": "Light jerseys",
                        "colorLabel": "white",
                        "includeUncertain": True,
                    },
                },
            )

            self.assertEqual(start_response.status_code, 400)
            self.assertEqual(start_response.json()["errorCode"], "team_selection_unavailable")

    def test_start_accepts_selected_team_with_equivalent_jersey_color_alias(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-color-alias-start-") as temp_dir:
            settings = _local_settings(Path(temp_dir))
            app = create_app(settings)
            client = TestClient(app)
            created = _create_uploaded_job(client)
            detected = [
                TeamOption(teamId="team_black", label="Black jerseys", colorLabel="black", confidence=0.92, source="quick_scan"),
            ]

            with (
                patch("app.api.build_team_quick_scan_candidate_clips", return_value=[_clip("Made Shot", 12.0, 16.5, 14.0)]),
                patch("app.api.apply_team_quick_scan", return_value=([], detected, True)),
                patch("app.api.run_analysis") as fake_run_analysis,
            ):
                fake_run_analysis.return_value = CloudAnalysisResult(
                    clipCount=0,
                    clips=[],
                    diagnostics=CloudDiagnostics(
                        processingMs=1,
                        backendModelVersion="cloud-v1",
                        usedVideoIntelligence=False,
                        usedGeminiRelabeling=False,
                        candidateSegments=0,
                        finalSegments=0,
                    ),
                    detectedTeams=detected,
                    teamSelection=TeamSelection(mode="team", teamId="team_dark", label="Dark jerseys", colorLabel="black", includeUncertain=True),
                )
                scan_response = client.post(
                    f"/v1/analysis/jobs/{created['jobId']}/team-scan",
                    json={"installId": "install-123456"},
                )
                start_response = client.post(
                    f"/v1/analysis/jobs/{created['jobId']}/start",
                    json={
                        "installId": "install-123456",
                        "teamSelection": {
                            "mode": "team",
                            "teamId": "team_dark",
                            "label": "Dark jerseys",
                            "colorLabel": "black",
                            "includeUncertain": True,
                        },
                    },
                )

            self.assertEqual(scan_response.status_code, 200)
            self.assertEqual(start_response.status_code, 200)

    def test_start_rejects_selected_team_with_conflicting_color_label(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-conflicting-color-start-") as temp_dir:
            settings = _local_settings(Path(temp_dir))
            app = create_app(settings)
            client = TestClient(app)
            created = _create_uploaded_job(client)
            detected = [
                TeamOption(teamId="team_dark", label="Dark jerseys", colorLabel="black", confidence=0.92, source="quick_scan"),
            ]

            with (
                patch("app.api.build_team_quick_scan_candidate_clips", return_value=[_clip("Made Shot", 12.0, 16.5, 14.0)]),
                patch("app.api.apply_team_quick_scan", return_value=([], detected, True)),
            ):
                scan_response = client.post(
                    f"/v1/analysis/jobs/{created['jobId']}/team-scan",
                    json={"installId": "install-123456"},
                )
                start_response = client.post(
                    f"/v1/analysis/jobs/{created['jobId']}/start",
                    json={
                        "installId": "install-123456",
                        "teamSelection": {
                            "mode": "team",
                            "teamId": "team_dark",
                            "label": "Light jerseys",
                            "colorLabel": "white",
                            "includeUncertain": True,
                        },
                    },
                )

            self.assertEqual(scan_response.status_code, 200)
            self.assertEqual(start_response.status_code, 400)
            self.assertEqual(start_response.json()["errorCode"], "team_selection_unavailable")

    def test_start_all_teams_does_not_require_team_scan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-all-teams-no-scan-") as temp_dir:
            settings = _local_settings(Path(temp_dir))
            app = create_app(settings)
            client = TestClient(app)
            created = _create_uploaded_job(client)

            with patch("app.api.run_analysis") as fake_run_analysis:
                fake_run_analysis.return_value = CloudAnalysisResult(
                    clipCount=0,
                    clips=[],
                    diagnostics=CloudDiagnostics(
                        processingMs=1,
                        backendModelVersion="cloud-v1",
                        usedVideoIntelligence=False,
                        usedGeminiRelabeling=False,
                        candidateSegments=0,
                        finalSegments=0,
                    ),
                    detectedTeams=[],
                    teamSelection=None,
                )
                start_response = client.post(
                    f"/v1/analysis/jobs/{created['jobId']}/start",
                    json={"installId": "install-123456", "teamSelection": {"mode": "all"}},
                )

            self.assertEqual(start_response.status_code, 200)

    def test_create_time_selected_team_survives_scan_and_start_without_resending_selection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-create-time-team-start-") as temp_dir:
            settings = _local_settings(Path(temp_dir))
            app = create_app(settings)
            client = TestClient(app)
            created = _create_uploaded_job(
                client,
                team_selection={
                    "mode": "team",
                    "teamId": "team_dark",
                    "label": "Dark jerseys",
                    "colorLabel": "black",
                    "includeUncertain": True,
                },
            )
            detected = [
                TeamOption(teamId="team_dark", label="Dark jerseys", colorLabel="black", confidence=0.92, source="quick_scan"),
                TeamOption(teamId="team_light", label="Light jerseys", colorLabel="white", confidence=0.9, source="quick_scan"),
            ]

            def fake_run_analysis(job, _settings, _source_path):
                self.assertIsNotNone(job.team_selection)
                self.assertEqual(job.team_selection.teamId, "team_dark")
                return CloudAnalysisResult(
                    clipCount=0,
                    clips=[],
                    diagnostics=CloudDiagnostics(
                        processingMs=1,
                        backendModelVersion="cloud-v1+team-scan",
                        usedVideoIntelligence=False,
                        usedGeminiRelabeling=False,
                        candidateSegments=0,
                        finalSegments=0,
                    ),
                    detectedTeams=detected,
                    teamSelection=job.team_selection,
                )

            job_payload = None
            with (
                patch("app.api.build_team_quick_scan_candidate_clips", return_value=[_clip("Block", 12.0, 16.5, 14.0)]),
                patch("app.api.apply_team_quick_scan", return_value=([], detected, True)),
                patch("app.api.run_analysis", side_effect=fake_run_analysis),
            ):
                scan_response = client.post(
                    f"/v1/analysis/jobs/{created['jobId']}/team-scan",
                    json={"installId": "install-123456"},
                )
                start_response = client.post(
                    f"/v1/analysis/jobs/{created['jobId']}/start",
                    json={"installId": "install-123456"},
                )

                self.assertEqual(scan_response.status_code, 200)
                self.assertEqual(start_response.status_code, 200)
                job_payload = _poll_analysis_job_until_terminal(client, created["jobId"])

            self.assertIsNotNone(job_payload)
            assert job_payload is not None
            self.assertEqual(job_payload["status"], "succeeded")
            self.assertEqual(job_payload["results"]["teamSelection"]["teamId"], "team_dark")

    def test_create_time_all_teams_starts_without_scan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-create-time-all-teams-start-") as temp_dir:
            settings = _local_settings(Path(temp_dir))
            app = create_app(settings)
            client = TestClient(app)
            created = _create_uploaded_job(client, team_selection={"mode": "all"})

            def fake_run_analysis(job, _settings, _source_path):
                self.assertIsNotNone(job.team_selection)
                self.assertEqual(job.team_selection.mode, "all")
                return CloudAnalysisResult(
                    clipCount=0,
                    clips=[],
                    diagnostics=CloudDiagnostics(
                        processingMs=1,
                        backendModelVersion="cloud-v1",
                        usedVideoIntelligence=False,
                        usedGeminiRelabeling=False,
                        candidateSegments=0,
                        finalSegments=0,
                    ),
                    detectedTeams=[],
                    teamSelection=job.team_selection,
                )

            with patch("app.api.run_analysis", side_effect=fake_run_analysis):
                start_response = client.post(
                    f"/v1/analysis/jobs/{created['jobId']}/start",
                    json={"installId": "install-123456"},
                )

            self.assertEqual(start_response.status_code, 200)

    def test_selected_team_filter_keeps_defensive_clips_and_excludes_uncertain_when_disabled(self) -> None:
        selection = TeamSelection(
            mode="team",
            teamId="team_dark",
            label="Dark jerseys",
            colorLabel="black",
            includeUncertain=False,
        )
        clips = [
            _team_clip("Block", 10.0, "team_dark", "black", 0.94),
            _team_clip("Steal", 20.0, "team_dark", "black", 0.93),
            _team_clip("Made Shot", 30.0, "team_light", "white", 0.94),
            _team_clip("Possible Steal", 40.0, "team_light", "white", 0.62, status="uncertain"),
        ]

        filtered = _filter_analysis_clips_for_team_selection(clips, selection)
        trimmed = _trim_analysis_clips_for_review(filtered, selection, 8)
        annotated = _annotate_analysis_team_status(trimmed, selection)

        self.assertEqual([clip.label for clip in annotated], ["Block", "Steal"])
        self.assertEqual([clip.teamAttributionStatus for clip in annotated], ["matched", "matched"])

    def test_selected_team_filter_keeps_uncertain_for_review_but_disables_auto_keep(self) -> None:
        selection = TeamSelection(
            mode="team",
            teamId="team_dark",
            label="Dark jerseys",
            colorLabel="black",
            includeUncertain=True,
        )
        clips = [
            _team_clip("Block", 10.0, "team_dark", "black", 0.94),
            _team_clip("Possible Steal", 20.0, "team_light", "white", 0.62, status="uncertain"),
        ]

        filtered = _filter_analysis_clips_for_team_selection(clips, selection)
        trimmed = _trim_analysis_clips_for_review(filtered, selection, 8)
        annotated = _annotate_analysis_team_status(trimmed, selection)

        by_label = {clip.label: clip for clip in annotated}
        self.assertEqual(set(by_label), {"Block", "Possible Steal"})
        self.assertEqual(by_label["Block"].teamAttributionStatus, "matched")
        self.assertTrue(by_label["Block"].shouldAutoKeep)
        self.assertEqual(by_label["Possible Steal"].teamAttributionStatus, "uncertain")
        self.assertFalse(by_label["Possible Steal"].shouldAutoKeep)
        self.assertFalse(by_label["Possible Steal"].shouldEnableSlowMotion)

    def test_team_scan_endpoint_runs_before_start_and_start_accepts_selection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-api-") as temp_dir:
            settings = _local_settings(Path(temp_dir))
            app = create_app(settings)

            with TestClient(app) as client:
                create_response = client.post(
                    "/v1/analysis/jobs",
                    json={
                        "filename": "game.mp4",
                        "contentType": "video/mp4",
                        "fileSizeBytes": 9,
                        "durationSeconds": 30.0,
                        "installId": "install-123456",
                        "appVersion": "1.0",
                        "analysisVersion": "cloud-v1",
                    },
                )
                self.assertEqual(create_response.status_code, 200)
                created = create_response.json()
                upload_response = client.put(created["uploadUrl"], content=b"fakevideo")
                self.assertEqual(upload_response.status_code, 204)

                detected = [
                    TeamOption(teamId="team_dark", label="Dark jerseys", colorLabel="black", confidence=0.92, source="quick_scan"),
                    TeamOption(teamId="team_light", label="Light jerseys", colorLabel="white", confidence=0.9, source="quick_scan"),
                ]

                def fake_run_analysis(job, _settings, _source_path):
                    self.assertEqual(job.team_selection.teamId, "team_dark")
                    return CloudAnalysisResult(
                        clipCount=0,
                        clips=[],
                        diagnostics=CloudDiagnostics(
                            processingMs=1,
                            backendModelVersion="cloud-v1+team-scan",
                            usedVideoIntelligence=False,
                            usedGeminiRelabeling=False,
                            candidateSegments=0,
                            finalSegments=0,
                        ),
                        detectedTeams=detected,
                        teamSelection=job.team_selection,
                    )

                quick_scan_candidates = [_clip("Block", 12.0, 16.5, 14.0)]
                helper_calls = []

                def fake_candidate_helper(source_path, duration_seconds, helper_settings):
                    helper_calls.append((source_path.name, duration_seconds, helper_settings.max_returned_clips))
                    return quick_scan_candidates

                def fake_team_scan(source_path, duration_seconds, clips, scan_settings):
                    self.assertEqual(clips, quick_scan_candidates)
                    return [], detected, True

                job_payload = None
                with (
                    patch("app.api.build_team_quick_scan_candidate_clips", side_effect=fake_candidate_helper),
                    patch("app.api.apply_team_quick_scan", side_effect=fake_team_scan),
                    patch("app.api.run_analysis", side_effect=fake_run_analysis),
                ):
                    scan_response = client.post(
                        f"/v1/analysis/jobs/{created['jobId']}/team-scan",
                        json={"installId": "install-123456"},
                    )
                    self.assertEqual(scan_response.status_code, 200)
                    self.assertEqual(scan_response.json()["status"], "scanned")
                    self.assertEqual(scan_response.json()["detectedTeams"][0]["teamId"], "team_dark")
                    self.assertEqual(helper_calls, [("game.mp4", 30.0, 8)])

                    start_response = client.post(
                        f"/v1/analysis/jobs/{created['jobId']}/start",
                        json={
                            "installId": "install-123456",
                            "teamSelection": {
                                "mode": "team",
                                "teamId": "team_dark",
                                "label": "Dark jerseys",
                                "colorLabel": "black",
                                "includeUncertain": True,
                            },
                        },
                    )
                    self.assertEqual(start_response.status_code, 200)

                    job_payload = _poll_analysis_job_until_terminal(client, created["jobId"])

                self.assertIsNotNone(job_payload)
                assert job_payload is not None
                self.assertEqual(job_payload["status"], "succeeded")
                self.assertEqual(job_payload["results"]["teamSelection"]["teamId"], "team_dark")

    def test_scan_source_endpoint_uses_presigned_source_url_without_job_store(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-source-") as temp_dir:
            root = Path(temp_dir)
            settings = replace(_local_settings(root), internal_process_secret="scan-secret")
            app = create_app(settings)
            client = TestClient(app)
            source_path = root / "downloaded-source.mp4"
            source_path.write_bytes(b"fakevideo")
            detected = [
                TeamOption(teamId="team_dark", label="Dark jerseys", colorLabel="black", confidence=0.92, source="quick_scan"),
                TeamOption(teamId="team_light", label="Light jerseys", colorLabel="white", confidence=0.9, source="quick_scan"),
            ]
            materialize_calls = []

            async def fake_materialize_remote_source(source_url, filename, max_file_size_bytes, upload_root):
                materialize_calls.append((source_url, filename, max_file_size_bytes, upload_root))
                return MaterializedSource(local_path=source_path, cleanup_after_use=False)

            with (
                patch("app.api.materialize_remote_source", side_effect=fake_materialize_remote_source),
                patch("app.api.build_team_quick_scan_candidate_clips", return_value=[_clip("Steal", 4.0, 8.0, 6.0)]),
                patch("app.api.apply_team_quick_scan", return_value=([], detected, True)),
            ):
                response = client.post(
                    "/v1/team-scan",
                    json={
                        "jobId": "job_worker_scan",
                        "installId": "install-123456",
                        "sourceUrl": "https://r2.local/hoopsclips-uploads/uploads/job_worker_scan/game.mp4?signature=redacted",
                        "sourceObjectKey": "uploads/job_worker_scan/game.mp4",
                        "filename": "game.mp4",
                        "contentType": "video/mp4",
                        "durationSeconds": 30.0,
                        "appVersion": "1.0",
                        "analysisVersion": "cloud-v1",
                    },
                    headers={"x-hoops-inference-secret": "scan-secret"},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["jobId"], "job_worker_scan")
            self.assertEqual(payload["status"], "scanned")
            self.assertEqual([team["teamId"] for team in payload["detectedTeams"]], ["team_dark", "team_light"])
            self.assertEqual(len(materialize_calls), 1)
            self.assertEqual(materialize_calls[0][1], "game.mp4")

    def test_analyze_source_endpoint_accepts_worker_dispatch_and_posts_callback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-worker-analyze-") as temp_dir:
            root = Path(temp_dir)
            settings = replace(_local_settings(root), internal_process_secret="dispatch-secret")
            app = create_app(settings)
            client = TestClient(app)
            source_path = root / "downloaded-source.mp4"
            source_path.write_bytes(b"fakevideo")
            captured_callbacks = []
            team_selection = {
                "mode": "team",
                "teamId": "team_dark",
                "label": "Dark jerseys",
                "colorLabel": "black",
                "confidenceThreshold": 0.85,
                "includeUncertain": True,
            }

            async def fake_materialize_remote_source(source_url, filename, max_file_size_bytes, upload_root):
                self.assertEqual(filename, "selected-team.mp4")
                self.assertTrue(source_url.startswith("https://r2.local/"))
                return MaterializedSource(local_path=source_path, cleanup_after_use=False)

            def fake_run_analysis(job, _settings, local_path):
                self.assertEqual(local_path, source_path)
                self.assertEqual(job.job_id, "job_worker_analyze")
                self.assertEqual(job.filename, "selected-team.mp4")
                self.assertEqual(job.duration_seconds, 30.0)
                self.assertIsNotNone(job.team_selection)
                assert job.team_selection is not None
                self.assertEqual(job.team_selection.teamId, "team_dark")
                return CloudAnalysisResult(
                    clipCount=1,
                    clips=[
                        _team_clip(
                            "Steal",
                            4.0,
                            "team_dark",
                            "black",
                            0.91,
                            status="matched",
                        )
                    ],
                    diagnostics=CloudDiagnostics(
                        processingMs=1200,
                        backendModelVersion="cloud-v1",
                        usedVideoIntelligence=False,
                        usedGeminiRelabeling=False,
                        candidateSegments=1,
                        finalSegments=1,
                        usedTeamQuickScan=True,
                    ),
                    detectedTeams=[
                        TeamOption(teamId="team_dark", label="Dark jerseys", colorLabel="black", confidence=0.93, source="quick_scan")
                    ],
                    teamSelection=TeamSelection.model_validate(team_selection),
                )

            async def fake_post_inference_callback(callback_url, callback_secret, payload):
                captured_callbacks.append(
                    {
                        "callbackUrl": callback_url,
                        "callbackSecret": callback_secret,
                        "payload": payload,
                    }
                )

            with (
                patch("app.api.materialize_remote_source", side_effect=fake_materialize_remote_source),
                patch("app.api.run_analysis", side_effect=fake_run_analysis),
                patch("app.api._post_inference_callback", side_effect=fake_post_inference_callback),
            ):
                response = client.post(
                    "/v1/analyze",
                    json={
                        "jobId": "job_worker_analyze",
                        "requestId": "req_worker_analyze",
                        "uploadTraceId": "upload_trace_worker",
                        "inferenceAttemptId": "attempt_worker",
                        "traceId": "trace_worker",
                        "filename": "selected-team.mp4",
                        "contentType": "video/mp4",
                        "fileSizeBytes": 9,
                        "durationSeconds": 30.0,
                        "sourceObjectKey": "uploads/job_worker_analyze/selected-team.mp4",
                        "sourceUrl": "https://r2.local/hoopsclips-uploads/uploads/job_worker_analyze/selected-team.mp4?signature=redacted",
                        "resultObjectKey": "results/job_worker_analyze/result.json",
                        "callbackUrl": "https://control-plane.local/internal/inference/callback",
                        "callbackSecret": "callback-secret",
                        "schemaVersion": "v1",
                        "modelVersion": "editing-cloud-v1",
                        "installId": "install-123456",
                        "appVersion": "1.0",
                        "analysisVersion": "cloud-v1",
                        "teamSelection": team_selection,
                        "requestedModel": "videomae",
                    },
                    headers={"x-hoops-inference-secret": "dispatch-secret"},
                )

            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["status"], "accepted")
            self.assertEqual(len(captured_callbacks), 1)
            callback = captured_callbacks[0]
            self.assertEqual(callback["callbackSecret"], "callback-secret")
            payload = callback["payload"]
            self.assertEqual(payload["jobId"], "job_worker_analyze")
            self.assertEqual(payload["requestId"], "req_worker_analyze")
            self.assertEqual(payload["status"], "succeeded")
            self.assertEqual(payload["inferenceAttemptId"], "attempt_worker")
            self.assertEqual(payload["results"]["teamSelection"]["teamId"], "team_dark")
            self.assertEqual(payload["results"]["clips"][0]["teamAttributionStatus"], "matched")
            serialized_callback = json.dumps(payload)
            self.assertNotIn("sourceUrl", serialized_callback)
            self.assertNotIn("signature=redacted", serialized_callback)

    def test_scan_source_endpoint_requires_internal_secret_when_configured(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-secret-") as temp_dir:
            settings = replace(_local_settings(Path(temp_dir)), internal_process_secret="scan-secret")
            app = create_app(settings)
            client = TestClient(app)

            response = client.post(
                "/v1/team-scan",
                json={
                    "jobId": "job_worker_scan",
                    "installId": "install-123456",
                    "sourceUrl": "https://r2.local/source.mp4",
                    "filename": "game.mp4",
                    "durationSeconds": 30.0,
                },
            )

            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["errorCode"], "forbidden")


if __name__ == "__main__":
    unittest.main()
