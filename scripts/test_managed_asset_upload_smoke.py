from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


def _load_module():
    script_path = Path(__file__).with_name("managed_asset_upload_smoke.py")
    spec = importlib.util.spec_from_file_location("managed_asset_upload_smoke", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ManagedAssetUploadSmokeTests(unittest.TestCase):
    def test_sanitized_managed_asset_upload_evidence_redacts_sensitive_fields(self) -> None:
        smoke = _load_module()
        raw = {
            "status": "pass",
            "baseUrl": "https://analysis.example.test",
            "assetId": "asset_123",
            "storageKey": "assets/asset_123/source/game.mp4",
            "sourceObjectKey": "assets/asset_123/source/game.mp4",
            "proxyKey": "assets/asset_123/proxy/proxy.mp4",
            "nested": {
                "uploadUrl": "https://storage.example.test/object?X-Amz-Signature=secret",
                "uploadHeaders": {"Authorization": "Bearer secret"},
            },
        }

        sanitized = smoke.sanitize_for_shareable_evidence(raw)
        smoke.assert_shareable_evidence(sanitized)

        self.assertNotIn("baseUrl", sanitized)
        self.assertNotIn("assetId", sanitized)
        self.assertNotIn("storageKey", sanitized)
        self.assertNotIn("sourceObjectKey", sanitized)
        self.assertNotIn("proxyKey", sanitized)
        self.assertTrue(sanitized["baseUrlHash"])
        self.assertTrue(sanitized["assetIdHash"])
        self.assertTrue(sanitized["storageKeyHash"])
        self.assertTrue(sanitized["sourceObjectKeyHash"])
        self.assertTrue(sanitized["proxyKeyHash"])
        self.assertTrue(sanitized["nested"]["uploadUrlHash"])
        self.assertTrue(sanitized["nested"]["uploadHeadersRedacted"])


if __name__ == "__main__":
    unittest.main()
