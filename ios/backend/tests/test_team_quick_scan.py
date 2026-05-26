from __future__ import annotations

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
from app.models import CloudAnalysisResult, CloudClip, CloudDiagnostics, TeamOption
from app.team_quick_scan import QuickScanFrame, _extract_quick_scan_frames, apply_team_quick_scan


def _settings(**overrides):
    values = {
        "team_quick_scan_enabled": True,
        "team_quick_scan_api_key": "test-key",
        "team_quick_scan_model": "gpt-4.1",
        "team_quick_scan_endpoint": "https://api.openai.com/v1/responses",
        "team_quick_scan_timeout_seconds": 12.0,
        "team_quick_scan_video_frame_count": 6,
        "team_quick_scan_clip_frames_per_clip": 3,
        "team_quick_scan_frame_width": 720,
        "team_quick_scan_jpeg_quality": 4,
        "team_quick_scan_max_image_bytes": 500_000,
        "team_quick_scan_min_team_confidence": 0.55,
        "team_quick_scan_max_candidate_clips": 120,
        "team_quick_scan_max_output_tokens": 6000,
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


class TeamQuickScanTests(unittest.TestCase):
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
            self.assertEqual(payload["text"]["format"]["schema"]["properties"]["clipAttributions"]["maxItems"], 75)
            self.assertEqual(payload["max_output_tokens"], 6000)
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

    def test_team_scan_endpoint_runs_before_start_and_start_accepts_selection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-team-scan-api-") as temp_dir:
            settings = _local_settings(Path(temp_dir))
            app = create_app(settings)
            client = TestClient(app)

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

            job_payload = None
            with (
                patch("app.api.apply_team_quick_scan", return_value=([], detected, True)),
                patch("app.api.run_analysis", side_effect=fake_run_analysis),
            ):
                scan_response = client.post(
                    f"/v1/analysis/jobs/{created['jobId']}/team-scan",
                    json={"installId": "install-123456"},
                )
                self.assertEqual(scan_response.status_code, 200)
                self.assertEqual(scan_response.json()["status"], "scanned")
                self.assertEqual(scan_response.json()["detectedTeams"][0]["teamId"], "team_dark")

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

                for _ in range(20):
                    poll_response = client.get(f"/v1/analysis/jobs/{created['jobId']}")
                    self.assertEqual(poll_response.status_code, 200)
                    job_payload = poll_response.json()
                    if job_payload["status"] == "succeeded":
                        break
                    time.sleep(0.05)

            self.assertIsNotNone(job_payload)
            assert job_payload is not None
            self.assertEqual(job_payload["status"], "succeeded")
            self.assertEqual(job_payload["results"]["teamSelection"]["teamId"], "team_dark")


if __name__ == "__main__":
    unittest.main()
