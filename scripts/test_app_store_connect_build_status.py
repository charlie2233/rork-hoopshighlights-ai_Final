import argparse
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from scripts.app_store_connect_build_status import (
    find_app,
    find_build,
    inspect_build,
    terminal_failure,
    wait_for_build,
)


class AppStoreConnectBuildStatusTests(unittest.TestCase):
    def test_find_app_requires_exact_bundle_id(self) -> None:
        payload = {
            "data": [
                {
                    "id": "app-id",
                    "type": "apps",
                    "attributes": {"name": "HoopClips", "bundleId": "atrak.charlie.hoopsclips"},
                }
            ]
        }
        with patch("scripts.app_store_connect_build_status.api_request", return_value=payload) as request:
            app = find_app("token", "atrak.charlie.hoopsclips")

        self.assertEqual(app["id"], "app-id")
        query = parse_qs(urlsplit(request.call_args.args[1]).query)
        self.assertEqual(query["filter[bundleId]"], ["atrak.charlie.hoopsclips"])

    def test_find_build_scopes_version_platform_and_app(self) -> None:
        with patch(
            "scripts.app_store_connect_build_status.api_request",
            return_value={"data": [], "included": []},
        ) as request:
            build, included = find_build("token", "app-id", "1.0.0", "46")

        self.assertIsNone(build)
        self.assertEqual(included, [])
        query = parse_qs(urlsplit(request.call_args.args[1]).query)
        self.assertEqual(query["filter[app]"], ["app-id"])
        self.assertEqual(query["filter[version]"], ["46"])
        self.assertEqual(query["filter[preReleaseVersion.version]"], ["1.0.0"])
        self.assertEqual(query["filter[preReleaseVersion.platform]"], ["IOS"])

    def test_inspect_build_accepts_valid_internal_testing_build(self) -> None:
        build = {
            "id": "build-id",
            "type": "builds",
            "attributes": {
                "version": "46",
                "uploadedDate": "2026-07-15T19:18:00Z",
                "expirationDate": "2026-10-13T19:18:00Z",
                "expired": False,
                "minOsVersion": "17.0",
                "processingState": "VALID",
                "buildAudienceType": "INTERNAL_ONLY",
                "usesNonExemptEncryption": False,
            },
            "relationships": {
                "buildBetaDetail": {"data": {"type": "buildBetaDetails", "id": "detail-id"}},
                "preReleaseVersion": {"data": {"type": "preReleaseVersions", "id": "version-id"}},
            },
        }
        included = [
            {
                "id": "detail-id",
                "type": "buildBetaDetails",
                "attributes": {
                    "internalBuildState": "IN_BETA_TESTING",
                    "externalBuildState": "READY_FOR_BETA_SUBMISSION",
                },
            },
            {
                "id": "version-id",
                "type": "preReleaseVersions",
                "attributes": {"version": "1.0.0", "platform": "IOS"},
            },
        ]
        app = {
            "id": "app-id",
            "attributes": {"name": "HoopClips", "bundleId": "atrak.charlie.hoopsclips"},
        }

        with patch("scripts.app_store_connect_build_status.create_token", return_value="token"), patch(
            "scripts.app_store_connect_build_status.find_app", return_value=app
        ), patch("scripts.app_store_connect_build_status.find_build", return_value=(build, included)):
            status = inspect_build(
                key_path=Path("key.p8"),
                key_id="key-id",
                issuer_id="issuer-id",
                bundle_id="atrak.charlie.hoopsclips",
                marketing_version="1.0.0",
                build_version="46",
            )

        self.assertTrue(status["readyForInternalTesting"])
        self.assertEqual(status["processingState"], "VALID")
        self.assertEqual(status["internalBuildState"], "IN_BETA_TESTING")
        self.assertFalse(status["expired"])

    def test_wait_for_build_polls_until_ready(self) -> None:
        args = argparse.Namespace(
            key_path="key.p8",
            key_id="key-id",
            issuer_id="issuer-id",
            bundle_id="atrak.charlie.hoopsclips",
            marketing_version="1.0.0",
            build_version="46",
            wait_seconds=60,
            poll_seconds=30,
        )
        statuses = iter(
            [
                {"buildFound": False, "readyForInternalTesting": False},
                {
                    "buildFound": True,
                    "processingState": "VALID",
                    "internalBuildState": "READY_FOR_BETA_TESTING",
                    "readyForInternalTesting": True,
                },
            ]
        )
        clock = iter([0, 0, 30])
        sleeps: list[float] = []

        status = wait_for_build(
            args,
            inspect=lambda **_: next(statuses),
            sleep=sleeps.append,
            monotonic=lambda: next(clock),
        )

        self.assertTrue(status["readyForInternalTesting"])
        self.assertEqual(sleeps, [30])

    def test_terminal_failure_stops_polling(self) -> None:
        self.assertTrue(terminal_failure({"processingState": "INVALID"}))
        self.assertTrue(terminal_failure({"internalBuildState": "PROCESSING_EXCEPTION"}))
        self.assertFalse(terminal_failure({"processingState": "PROCESSING"}))


if __name__ == "__main__":
    unittest.main()
