from __future__ import annotations

import unittest
from unittest.mock import patch

from ios.backend.scripts import upload_benchmark


class _FakeResponse:
    def __init__(self, body: bytes = b"{}", headers: dict[str, str] | None = None) -> None:
        self._body = body
        self.headers = headers or {}

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class UploadBenchmarkClientIdentityTests(unittest.TestCase):
    def test_json_request_uses_explicit_hoopclips_identity(self) -> None:
        captured_request = None

        def fake_urlopen(request, timeout):
            nonlocal captured_request
            captured_request = request
            self.assertEqual(timeout, 120)
            return _FakeResponse()

        with patch.object(upload_benchmark.urlrequest, "urlopen", side_effect=fake_urlopen):
            upload_benchmark._json_request("POST", "https://worker.example/v1/uploads/init", {"asset": "test"})

        self.assertIsNotNone(captured_request)
        self.assertEqual(captured_request.get_header("User-agent"), upload_benchmark.USER_AGENT)
        self.assertEqual(captured_request.get_header("Accept"), "application/json")
        self.assertEqual(captured_request.get_header("Content-type"), "application/json")

    def test_put_request_uses_identity_and_preserves_upload_headers(self) -> None:
        captured_request = None

        def fake_urlopen(request, timeout):
            nonlocal captured_request
            captured_request = request
            self.assertEqual(timeout, 180)
            return _FakeResponse(headers={"ETag": "etag-1"})

        with patch.object(upload_benchmark.urlrequest, "urlopen", side_effect=fake_urlopen):
            headers = upload_benchmark._put_bytes(
                "https://r2.example/upload",
                b"video",
                {"content-type": "video/mp4"},
            )

        self.assertIsNotNone(captured_request)
        self.assertEqual(captured_request.get_header("User-agent"), upload_benchmark.USER_AGENT)
        self.assertEqual(captured_request.get_header("Content-type"), "video/mp4")
        self.assertEqual(headers["ETag"], "etag-1")


if __name__ == "__main__":
    unittest.main()
