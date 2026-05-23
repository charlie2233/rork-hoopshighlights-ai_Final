import importlib.util
import unittest
from pathlib import Path


class SmokeLogRedactionTests(unittest.TestCase):
    def test_ios_backend_smoke_redacts_bearer_urls_and_storage_fields(self) -> None:
        module = load_module("ios_backend_live_render_smoke", "ios/backend/scripts/live_render_smoke.py")

        redacted = module.sanitize_for_log(secret_payload())

        self.assertEqual(redacted["downloadUrl"], "[redacted]")
        self.assertEqual(redacted["nested"]["sourceObjectKey"], "[redacted]")
        self.assertEqual(redacted["nested"]["authorization"], "[redacted]")
        self.assertEqual(redacted["events"][0]["callbackUrl"], "[redacted]")
        self.assertEqual(redacted["safe"], "ok")

    def test_editing_smoke_redacts_bearer_urls_and_storage_fields(self) -> None:
        module = load_module("editing_live_render_smoke", "services/editing/scripts/live_render_smoke.py")

        redacted = module.sanitize_for_log(secret_payload())

        self.assertEqual(redacted["downloadUrl"], "[redacted]")
        self.assertEqual(redacted["nested"]["sourceObjectKey"], "[redacted]")
        self.assertEqual(redacted["nested"]["authorization"], "[redacted]")
        self.assertEqual(redacted["events"][0]["callbackUrl"], "[redacted]")
        self.assertEqual(redacted["safe"], "ok")


def secret_payload() -> dict[str, object]:
    return {
        "downloadUrl": "https://r2.example.test/render.mp4?X-Amz-Signature=abc&X-Amz-Credential=key",
        "nested": {
            "sourceObjectKey": "sources/private-game.mp4",
            "authorization": "Bearer secret-token",
            "message": "kept",
        },
        "events": [
            {
                "callbackUrl": "https://example.test/callback?token=secret",
                "status": "failed",
            }
        ],
        "safe": "ok",
    }


def load_module(name: str, relative_path: str):
    repo_root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(name, repo_root / relative_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
