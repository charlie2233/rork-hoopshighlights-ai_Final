import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from scripts import worker_team_scan_smoke as smoke


class WorkerTeamScanSmokeTests(unittest.TestCase):
    def test_sanitize_redacts_presigned_urls_and_storage_fields(self) -> None:
        payload = {
            "workerUrl": "https://worker.example.test",
            "uploadUrl": "https://r2.example.test/upload?X-Amz-Signature=secret&X-Amz-Credential=key",
            "sourceObjectKey": "sources/private-game.mp4",
            "nested": {
                "sourceUrl": "https://r2.example.test/source?Signature=secret",
                "resultObjectKey": "results/private.json",
                "credential": "abc",
                "message": "kept",
            },
        }

        redacted = smoke.sanitize_for_log(payload)

        self.assertEqual(redacted["workerUrl"], "https://worker.example.test")
        self.assertEqual(redacted["uploadUrl"], "[redacted]")
        self.assertEqual(redacted["sourceObjectKey"], "[redacted]")
        self.assertEqual(redacted["nested"]["sourceUrl"], "[redacted]")
        self.assertEqual(redacted["nested"]["resultObjectKey"], "[redacted]")
        self.assertEqual(redacted["nested"]["credential"], "[redacted]")
        self.assertEqual(redacted["nested"]["message"], "kept")

    def test_run_smoke_uploads_scans_and_can_start_selected_team_without_printing_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "team-scan.mp4"
            video_path.write_bytes(b"fake-video")
            calls: list[tuple[str, str, dict[str, object] | None]] = []

            def fake_request(method: str, base_url: str, path: str, payload: dict[str, object] | None = None, trace_id: str = "") -> dict[str, object]:
                calls.append((method, path, payload))
                if path == "v1/analysis/jobs":
                    return {
                        "jobId": "job_123",
                        "uploadUrl": "https://r2.example.test/upload?X-Amz-Signature=secret",
                        "uploadHeaders": {"content-type": "video/mp4"},
                        "sourceObjectKey": "sources/private-game.mp4",
                    }
                if path == "v1/analysis/jobs/job_123/team-scan":
                    return {
                        "status": "ready",
                        "detectedTeams": [
                            {
                                "teamId": "team_red",
                                "label": "Red Team",
                                "colorLabel": "red",
                                "confidence": 0.91,
                                "source": "vision",
                            }
                        ],
                    }
                if path == "v1/analysis/jobs/job_123/start":
                    return {
                        "status": "queued",
                        "downloadUrl": "https://r2.example.test/final.mp4?X-Amz-Signature=secret",
                    }
                raise AssertionError(f"Unexpected path: {path}")

            args = make_args(video_path, start_selected_team=True)
            with patch.object(smoke, "request_json", side_effect=fake_request), patch.object(smoke, "upload_video") as upload_video:
                result = smoke.run_smoke(args)

        upload_video.assert_called_once()
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn("uploadUrl", serialized)
        self.assertNotIn("sourceObjectKey", serialized)
        self.assertNotIn("X-Amz", serialized)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["detectedTeamCount"], 1)
        self.assertEqual(result["analysisStart"]["mode"], "team")
        self.assertEqual(result["analysisStart"]["teamId"], "team_red")

        start_payload = calls[-1][2]
        self.assertIsNotNone(start_payload)
        team_selection = start_payload["teamSelection"]  # type: ignore[index]
        self.assertEqual(team_selection["mode"], "team")
        self.assertTrue(team_selection["includeUncertain"])
        self.assertEqual(team_selection["confidenceThreshold"], 0.85)

    def test_run_smoke_fails_when_scan_unavailable_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "team-scan.mp4"
            video_path.write_bytes(b"fake-video")

            def fake_request(method: str, base_url: str, path: str, payload: dict[str, object] | None = None, trace_id: str = "") -> dict[str, object]:
                if path == "v1/analysis/jobs":
                    return {"jobId": "job_123", "uploadUrl": "https://r2.example.test/upload?X-Amz-Signature=secret"}
                if path == "v1/analysis/jobs/job_123/team-scan":
                    return {"status": "unavailable", "detectedTeams": []}
                raise AssertionError(f"Unexpected path: {path}")

            with patch.object(smoke, "request_json", side_effect=fake_request), patch.object(smoke, "upload_video"):
                with self.assertRaises(smoke.SmokeError) as context:
                    smoke.run_smoke(make_args(video_path))

        self.assertIn("no selectable teams", str(context.exception))
        self.assertEqual(smoke.sanitize_for_log(context.exception.payload)["scan"]["status"], "unavailable")


def make_args(video_path: Path, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "worker_url": "https://worker.example.test",
        "video_path": str(video_path),
        "duration_seconds": 12.0,
        "install_id": "team-scan-smoke-install",
        "app_version": "worker-team-scan-smoke",
        "analysis_version": "worker-team-scan-smoke",
        "allow_unavailable": False,
        "start_selected_team": False,
        "start_all_teams": False,
        "selected_team_id": None,
        "selected_color_label": None,
        "confidence_threshold": 0.85,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


if __name__ == "__main__":
    unittest.main()
