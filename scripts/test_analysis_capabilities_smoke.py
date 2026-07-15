import unittest
from unittest.mock import patch

from scripts.analysis_capabilities_smoke import SMOKE_USER_AGENT, request_json_response


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        return False

    def read(self) -> bytes:
        return b"{}"


class AnalysisCapabilitiesSmokeTests(unittest.TestCase):
    def test_request_uses_named_smoke_user_agent(self) -> None:
        with patch("scripts.analysis_capabilities_smoke.urlopen", return_value=_FakeResponse()) as opener:
            status, payload = request_json_response(
                "GET",
                "https://worker.test/v1/analysis/capabilities",
                timeout_seconds=5,
            )

        request = opener.call_args.args[0]
        self.assertEqual(status, 200)
        self.assertEqual(payload, {})
        self.assertEqual(request.get_header("User-agent"), SMOKE_USER_AGENT)


if __name__ == "__main__":
    unittest.main()
