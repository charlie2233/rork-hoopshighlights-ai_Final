from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.models import CloudClip
from app.team_quick_scan import QuickScanFrame, apply_team_quick_scan


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


if __name__ == "__main__":
    unittest.main()
