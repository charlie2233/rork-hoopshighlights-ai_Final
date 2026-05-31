from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "ios" / "backend" / "scripts"))

from live_render_smoke import sanitize_for_log  # noqa: E402


class SmokeSanitizationTests(unittest.TestCase):
    def test_success_summary_redacts_storage_keys_and_urls(self) -> None:
        summary = {
            "status": "pass",
            "baseUrl": "https://editing.example.test",
            "editJobId": "edit_123",
            "renderJobId": "render_123",
            "sourceObjectKey": "uploads/install/source.mp4",
            "outputObjectKey": "renders/install/final.mp4",
            "renderLogObjectKey": "render_logs/install/final.json",
            "downloadedPath": "/tmp/hoopclips/final.mp4",
            "media": {"format": "mp4", "duration": 15.0},
        }

        sanitized = sanitize_for_log(summary)

        self.assertEqual(sanitized["status"], "pass")
        self.assertEqual(sanitized["editJobId"], "edit_123")
        self.assertEqual(sanitized["renderJobId"], "render_123")
        self.assertEqual(sanitized["baseUrl"], "[redacted]")
        self.assertEqual(sanitized["sourceObjectKey"], "[redacted]")
        self.assertEqual(sanitized["outputObjectKey"], "[redacted]")
        self.assertEqual(sanitized["renderLogObjectKey"], "[redacted]")
        self.assertEqual(sanitized["downloadedPath"], "/tmp/hoopclips/final.mp4")
        self.assertEqual(sanitized["media"], {"format": "mp4", "duration": 15.0})

    def test_nested_error_payload_redacts_presigned_material_and_unknown_objects(self) -> None:
        class CustomPayload:
            def __str__(self) -> str:
                return "downloadUrl=https://r2.example.test/render.mp4?X-Amz-Signature=abc"

        payload = {
            "body": {
                "message": "Use https://r2.example.test/render.mp4?X-Amz-Credential=abc",
                "safe": "render completed",
                "custom": CustomPayload(),
            },
            "headers": {"authorization": "Bearer secret", "trace": ("ok", "uploads/private/source.mp4")},
        }

        sanitized = sanitize_for_log(payload)

        self.assertEqual(sanitized["body"]["message"], "[redacted]")
        self.assertEqual(sanitized["body"]["safe"], "render completed")
        self.assertEqual(sanitized["body"]["custom"], "[redacted]")
        self.assertEqual(sanitized["headers"]["authorization"], "[redacted]")
        self.assertEqual(sanitized["headers"]["trace"], ["ok", "[redacted]"])


if __name__ == "__main__":
    unittest.main()
