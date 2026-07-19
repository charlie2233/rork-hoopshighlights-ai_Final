import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from scripts.validate_app_store_submission_package import (
    DEFAULT_METADATA_PATH,
    REQUIRED_OPERATOR_GATES,
    has_blockers,
    has_errors,
    main,
    validate_package,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class AppStoreSubmissionPackageTests(unittest.TestCase):
    def test_repo_package_is_structurally_valid_and_truthfully_blocked(self) -> None:
        findings = validate_package(REPO_ROOT)

        self.assertFalse(has_errors(findings), findings)
        self.assertTrue(has_blockers(findings))
        self.assertTrue(any(item.check == "categories" and item.status == "pass" for item in findings))
        self.assertTrue(any(item.check == "brand" and item.status == "pass" for item in findings))
        self.assertTrue(any(item.check == "urls" and item.status == "pass" for item in findings))
        self.assertTrue(any(item.check == "screenshots" and item.status == "pass" for item in findings))
        self.assertTrue(any(item.check == "screenshotContentReview" and item.status == "pass" for item in findings))
        self.assertTrue(any(item.check == "privacyDeclaration" and item.status == "pass" for item in findings))
        self.assertTrue(any(item.check == "submissionDrafts" and item.status == "pass" for item in findings))
        self.assertTrue(any(item.check == "appStoreConnectAudit" and item.status == "pass" for item in findings))
        self.assertFalse(
            any(
                item.check in {
                    "support_url",
                    "privacy_terms_scope",
                    "listing_categories",
                    "screenshot_content_review",
                }
                for item in findings
            )
        )

    def test_require_ready_fails_while_operator_gates_remain(self) -> None:
        self.assertEqual(main(["--repo-root", str(REPO_ROOT), "--require-ready"]), 2)

    def test_alpha_screenshot_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            metadata = create_fixture(repo_root, screenshot_color_type=6)

            findings = validate_package(repo_root, metadata)

        self.assertTrue(has_errors(findings))
        self.assertTrue(any("alpha channel" in item.detail for item in findings))

    def test_wrong_screenshot_dimensions_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            metadata = create_fixture(repo_root, iphone_dimensions=(100, 100))

            findings = validate_package(repo_root, metadata)

        self.assertTrue(has_errors(findings))
        self.assertTrue(any("unsupported dimensions" in item.detail for item in findings))

    def test_generic_legal_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            metadata = create_fixture(repo_root)
            metadata_path = repo_root / metadata
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            payload["urls"]["privacyPolicyURL"]["value"] = "https://rork.com/privacy"
            metadata_path.write_text(json.dumps(payload), encoding="utf-8")

            findings = validate_package(repo_root, metadata)

        self.assertTrue(has_errors(findings))
        self.assertTrue(any(item.check == "urls" for item in findings))

    def test_stale_store_build_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            metadata = create_fixture(repo_root)
            metadata_path = repo_root / metadata
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            payload["release"]["build"] = "999"
            metadata_path.write_text(json.dumps(payload), encoding="utf-8")

            findings = validate_package(repo_root, metadata)

        self.assertTrue(has_errors(findings))
        self.assertTrue(any(item.check == "release.build" for item in findings))

    def test_missing_privacy_data_type_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            metadata = create_fixture(repo_root)
            metadata_path = repo_root / metadata
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            payload["privacyDeclaration"]["dataTypes"] = [
                entry
                for entry in payload["privacyDeclaration"]["dataTypes"]
                if entry["type"] != "Purchase History"
            ]
            metadata_path.write_text(json.dumps(payload), encoding="utf-8")

            findings = validate_package(repo_root, metadata)

        self.assertTrue(has_errors(findings))
        self.assertTrue(any(item.check == "privacyDeclaration" for item in findings))

    def test_missing_required_operator_gate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            metadata = create_fixture(repo_root)
            metadata_path = repo_root / metadata
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            payload["operatorGates"] = [
                gate for gate in payload["operatorGates"] if gate["id"] != "app_privacy"
            ]
            metadata_path.write_text(json.dumps(payload), encoding="utf-8")

            findings = validate_package(repo_root, metadata)

        self.assertTrue(has_errors(findings))
        self.assertTrue(any(item.check == "operatorGates" for item in findings))


def create_fixture(
    repo_root: Path,
    screenshot_color_type: int = 2,
    iphone_dimensions: tuple[int, int] = (1320, 2868),
) -> Path:
    icon_path = repo_root / "assets/icon.png"
    mark_path = repo_root / "assets/mark.png"
    iphone_path = repo_root / "screens/iphone.png"
    ipad_path = repo_root / "screens/ipad.png"
    release_config_path = repo_root / "config/Release.xcconfig"
    privacy_manifest_path = repo_root / "config/PrivacyInfo.xcprivacy"
    project_path = repo_root / "ios/HoopsClips.xcodeproj/project.pbxproj"
    write_png(icon_path, 1024, 1024)
    write_png(mark_path, 512, 512)
    write_png(iphone_path, *iphone_dimensions, color_type=screenshot_color_type)
    write_png(ipad_path, 2064, 2752)
    release_config_path.parent.mkdir(parents=True, exist_ok=True)
    release_config_path.write_text(
        "HOOPS_APP_ENV = production\nHOOPS_CLOUD_LAUNCH_MODE = enabled\n",
        encoding="utf-8",
    )
    privacy_manifest_path.write_text("<plist><dict/></plist>\n", encoding="utf-8")
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_text(
        "MARKETING_VERSION = 1.0.0;\nCURRENT_PROJECT_VERSION = 54;\n",
        encoding="utf-8",
    )
    metadata_path = repo_root / DEFAULT_METADATA_PATH
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "schemaVersion": "hoopclips-app-store-metadata-v1",
                "listing": {
                    "name": "HoopClips",
                    "subtitle": "AI Basketball Highlight Reels",
                    "promotionalText": "Cloud-rendered basketball highlights.",
                    "description": "Create, revise, preview, and share basketball highlight reels.",
                    "keywords": "basketball,highlights,reels",
                },
                "categories": {
                    "primary": "Photo & Video",
                    "secondary": "Sports",
                    "status": "ready",
                },
                "brand": {
                    "appIconPath": "assets/icon.png",
                    "brandMarkPath": "assets/mark.png",
                },
                "urls": {
                    "marketingURL": {
                        "value": "https://atrak.dev/apps/hoopsclips/",
                        "status": "ready",
                    },
                    "supportURL": {
                        "value": "https://atrak.dev/apps/hoopsclips/support.html",
                        "status": "ready",
                    },
                    "privacyPolicyURL": {
                        "value": "https://atrak.dev/apps/hoopsclips/privacy.html",
                        "status": "ready",
                    },
                    "termsOfServiceURL": {
                        "value": "https://atrak.dev/apps/hoopsclips/terms.html",
                        "status": "ready",
                    },
                },
                "screenshots": [
                    {"deviceClass": "iphone_6_9", "paths": ["screens/iphone.png"]},
                    {"deviceClass": "ipad_13", "paths": ["screens/ipad.png"]},
                ],
                "screenshotContentReview": {
                    "status": "ready",
                    "reviewedAt": "2026-07-19",
                    "evidence": "Fixture screenshots reviewed.",
                },
                "privacyDeclaration": {
                    "collectsData": True,
                    "tracking": False,
                    "privacyManifestPath": "config/PrivacyInfo.xcprivacy",
                    "dataTypes": [
                        {
                            "type": data_type,
                            "linkedToUser": linked,
                            "tracking": False,
                            "purposes": ["App Functionality"],
                        }
                        for data_type, linked in {
                            "Email Address": True,
                            "Photos or Videos": True,
                            "User ID": True,
                            "Device ID": True,
                            "Purchase History": False,
                            "Customer Support": True,
                            "Product Interaction": False,
                            "Other Diagnostic Data": False,
                        }.items()
                    ],
                },
                "pricingAvailabilityDraft": {
                    "appPrice": "Free",
                    "availability": "all_countries_or_regions",
                },
                "contentRightsDraft": {
                    "containsOrAccessesThirdPartyContent": True,
                    "necessaryRightsRequired": True,
                },
                "ageRatingDraft": {
                    "features": {
                        "parentalControls": False,
                        "ageAssurance": False,
                        "unrestrictedWebAccess": False,
                        "broadUserGeneratedContentDistribution": False,
                        "socialMedia": False,
                        "messagingAndChat": False,
                        "advertising": False,
                    },
                    "contentFrequency": "none",
                },
                "appStoreConnectAudit": {
                    "versionState": "prepare_for_submission",
                    "testFlightBuild": {
                        "version": "1.0.0",
                        "build": "54",
                        "processingState": "valid",
                    },
                    "digitalServicesAct": {
                        "status": "ready",
                        "declaration": "non_trader",
                    },
                    "subscription": {
                        "productId": "monthly_premium",
                        "basePriceUSD": "9.99",
                        "availability": "all_countries_or_regions",
                    },
                },
                "release": {
                    "version": "1.0.0",
                    "build": "54",
                    "configurationPath": "config/Release.xcconfig",
                    "backendMode": "production_cloud_only",
                    "localRenderFallback": False,
                },
                "operatorGates": [
                    {
                        "id": gate_id,
                        "status": "operator_review_required" if gate_id == "final_add_for_review" else "ready",
                        "detail": "Fixture operator gate.",
                    }
                    for gate_id in sorted(REQUIRED_OPERATOR_GATES)
                ],
            }
        ),
        encoding="utf-8",
    )
    return metadata_path.relative_to(repo_root)


def write_png(path: Path, width: int, height: int, color_type: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    signature = b"\x89PNG\r\n\x1a\n"
    path.write_bytes(signature + png_chunk(b"IHDR", ihdr) + png_chunk(b"IEND", b""))


def png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", checksum)


if __name__ == "__main__":
    unittest.main()
