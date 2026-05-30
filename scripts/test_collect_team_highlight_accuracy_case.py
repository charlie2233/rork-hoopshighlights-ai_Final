import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from scripts import collect_team_highlight_accuracy_case as collector


class CollectTeamHighlightAccuracyCaseTests(unittest.TestCase):
    def test_collect_selected_team_case_writes_analysis_labels_and_manifest_without_url_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "game_clip.mp4"
            video_path.write_bytes(b"fake video")
            output_dir = root / "accuracy"
            manifest_path = root / "manifest.json"
            calls: list[tuple[str, str, dict[str, object] | None]] = []

            def fake_request(method: str, _base_url: str, path: str, payload: dict[str, object] | None = None, trace_id: str = "") -> dict[str, object]:
                calls.append((method, path, payload))
                if path == "v1/analysis/jobs":
                    return {
                        "jobId": "job_123",
                        "uploadUrl": "https://r2.example.test/upload?X-Amz-Signature=secret",
                        "uploadHeaders": {"content-type": "video/mp4"},
                    }
                if path == "v1/analysis/jobs/job_123/team-scan":
                    return {
                        "status": "scanned",
                        "detectedTeams": [
                            {
                                "teamId": "team_dark",
                                "label": "Dark jerseys",
                                "colorLabel": "black",
                                "confidence": 0.93,
                            }
                        ],
                    }
                if path == "v1/analysis/jobs/job_123/start":
                    return {"status": "queued"}
                if path == "v1/analysis/jobs/job_123":
                    return completed_job()
                raise AssertionError(f"Unexpected path: {path}")

            args = make_args(video_path, output_dir, manifest_path)
            with patch.object(collector, "request_json", side_effect=fake_request), patch.object(collector, "upload_video") as upload_video:
                result = collector.collect_case(args)

            upload_video.assert_called_once()
            serialized = json.dumps(collector.sanitize_for_log(result), sort_keys=True)
            self.assertNotIn("uploadUrl", serialized)
            self.assertNotIn("X-Amz", serialized)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["selectedTeamId"], "team_dark")
            self.assertEqual(result["clipCount"], 2)

            start_payload = calls[2][2]
            self.assertIsNotNone(start_payload)
            team_selection = start_payload["teamSelection"]  # type: ignore[index]
            self.assertEqual(team_selection["mode"], "team")
            self.assertTrue(team_selection["includeUncertain"])

            analysis = json.loads((output_dir / "case_a" / "analysis_result.json").read_text())
            labels = json.loads((output_dir / "case_a" / "manual_labels_template.json").read_text())
            manifest = json.loads(manifest_path.read_text())

            self.assertEqual(analysis["jobId"], "job_123")
            self.assertEqual(labels["source"], "real_cloud_analysis_label_template")
            self.assertTrue(labels["clips"][0]["needsLabel"])
            self.assertEqual(manifest["cases"][0]["analysisResult"], "accuracy/case_a/analysis_result.json")
            self.assertEqual(manifest["cases"][0]["labels"], "accuracy/case_a/manual_labels_template.json")

    def test_collect_all_teams_case_skips_team_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "game_clip.mp4"
            video_path.write_bytes(b"fake video")
            paths: list[str] = []

            def fake_request(method: str, _base_url: str, path: str, payload: dict[str, object] | None = None, trace_id: str = "") -> dict[str, object]:
                paths.append(path)
                if path == "v1/analysis/jobs":
                    return {"jobId": "job_123", "uploadUrl": "https://r2.example.test/upload?X-Amz-Signature=secret"}
                if path == "v1/analysis/jobs/job_123/start":
                    return {"status": "queued"}
                if path == "v1/analysis/jobs/job_123":
                    return completed_job(team_selection={"mode": "all"})
                raise AssertionError(f"Unexpected path: {path}")

            args = make_args(video_path, root / "accuracy", root / "manifest.json", team_mode="all")
            with patch.object(collector, "request_json", side_effect=fake_request), patch.object(collector, "upload_video"):
                result = collector.collect_case(args)

            self.assertNotIn("v1/analysis/jobs/job_123/team-scan", paths)
            self.assertEqual(result["teamMode"], "all")
            self.assertIsNone(result["selectedTeamId"])


def make_args(video_path: Path, output_dir: Path, manifest_path: Path, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "worker_url": "https://worker.example.test",
        "video_path": str(video_path),
        "duration_seconds": 12.0,
        "case_id": "case_a",
        "video_id": "video_a",
        "team_mode": "team",
        "selected_team_id": None,
        "selected_color_label": None,
        "confidence_threshold": 0.85,
        "allow_scan_unavailable": False,
        "poll_interval_seconds": 0.01,
        "timeout_seconds": 1.0,
        "install_id": "accuracy-install",
        "app_version": "accuracy-test",
        "analysis_version": "accuracy-test",
        "output_dir": str(output_dir),
        "manifest": str(manifest_path),
        "no_manifest": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def completed_job(team_selection: dict[str, object] | None = None) -> dict[str, object]:
    if team_selection is None:
        team_selection = {
            "mode": "team",
            "teamId": "team_dark",
            "label": "Dark jerseys",
            "colorLabel": "black",
            "confidenceThreshold": 0.85,
            "includeUncertain": True,
        }
    return {
        "jobId": "job_123",
        "status": "completed",
        "results": {
            "clipCount": 2,
            "teamSelection": team_selection,
            "detectedTeams": [
                {
                    "teamId": "team_dark",
                    "label": "Dark jerseys",
                    "colorLabel": "black",
                    "confidence": 0.93,
                }
            ],
            "clips": [
                {
                    "id": "clip_1",
                    "startTime": 1.0,
                    "endTime": 5.0,
                    "eventCenter": 3.0,
                    "label": "Made Shot",
                    "confidence": 0.91,
                    "shouldAutoKeep": True,
                    "teamAttribution": {"teamId": "team_dark", "confidence": 0.9},
                    "teamAttributionStatus": "matched",
                },
                {
                    "id": "clip_2",
                    "startTime": 8.0,
                    "endTime": 11.0,
                    "eventCenter": 9.5,
                    "label": "Steal",
                    "confidence": 0.87,
                    "shouldAutoKeep": True,
                    "teamAttribution": {"teamId": "team_dark", "confidence": 0.88},
                    "teamAttributionStatus": "matched",
                    "nativeShotSignals": {"outcome": "not_shot"},
                },
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
