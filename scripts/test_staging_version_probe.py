import json
import io
import unittest
from urllib.error import HTTPError
from urllib.request import Request

from scripts.staging_version_probe import render_text, run_probe


FEATURE_FLAGS = {
    "aiEditEnabled": True,
    "aiEditLiveRenderEnabled": True,
    "aiEditRevisionEnabled": True,
    "aiEditTemplatePackEnabled": True,
}


class StagingVersionProbeTests(unittest.TestCase):
    def test_detects_stale_worker_when_direct_editing_is_reachable(self) -> None:
        def opener(request: Request, _timeout_seconds: float) -> tuple[int, bytes]:
            url = request.full_url
            if "worker.test" in url:
                raise HTTPError(url, 404, "Not Found", hdrs=None, fp=io.BytesIO())
            return 200, json.dumps({"featureFlags": FEATURE_FLAGS}).encode("utf-8")

        report = run_probe(
            worker_base_url="https://worker.test",
            editing_version_url="https://editing.test/version",
            opener=opener,
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.diagnosis, "worker_route_stale_or_not_deployed")
        self.assertEqual(report.worker.httpStatus, 404)
        self.assertEqual(report.editing.status, "pass")

    def test_passes_when_both_endpoints_return_required_feature_flags(self) -> None:
        def opener(_request: Request, _timeout_seconds: float) -> tuple[int, bytes]:
            return 200, json.dumps({"featureFlags": FEATURE_FLAGS}).encode("utf-8")

        report = run_probe(
            worker_base_url="https://worker.test",
            editing_version_url="https://editing.test/version",
            opener=opener,
        )

        self.assertEqual(report.status, "pass")
        self.assertEqual(report.diagnosis, "staging_version_ready")
        self.assertEqual(report.worker.featureFlagKeys, sorted(FEATURE_FLAGS.keys()))

    def test_fails_when_feature_flags_are_missing(self) -> None:
        def opener(_request: Request, _timeout_seconds: float) -> tuple[int, bytes]:
            return 200, json.dumps({"featureFlags": {"aiEditEnabled": True}}).encode("utf-8")

        report = run_probe(
            worker_base_url="https://worker.test",
            editing_version_url="https://editing.test/version",
            opener=opener,
        )

        self.assertEqual(report.status, "fail")
        self.assertIn("Missing feature flag", report.worker.detail)
        self.assertIn("Missing feature flag", report.editing.detail)

    def test_text_output_redacts_query_values_and_body_values(self) -> None:
        def opener(_request: Request, _timeout_seconds: float) -> tuple[int, bytes]:
            return 200, json.dumps({"featureFlags": FEATURE_FLAGS, "secret": "do-not-print"}).encode("utf-8")

        report = run_probe(
            worker_base_url="https://worker.test?token=secret-token",
            editing_version_url="https://editing.test/version?token=secret-token",
            opener=opener,
        )
        text = render_text(report)

        self.assertIn("worker.test/v1/editing/version", text)
        self.assertIn("editing.test/version", text)
        self.assertNotIn("secret-token", text)
        self.assertNotIn("do-not-print", text)


if __name__ == "__main__":
    unittest.main()
