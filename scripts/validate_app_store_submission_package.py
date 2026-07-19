#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


DEFAULT_METADATA_PATH = Path("ios/docs/app-store/app-store-metadata-en-US.json")
DEFAULT_PROJECT_FILE = Path("ios/HoopsClips.xcodeproj/project.pbxproj")
EXPECTED_SCHEMA_VERSION = "hoopclips-app-store-metadata-v1"
TEXT_LIMITS = {
    "name": 30,
    "subtitle": 30,
    "promotionalText": 170,
    "description": 4000,
}
ALLOWED_SCREENSHOT_DIMENSIONS = {
    "iphone_6_9": {
        (1260, 2736),
        (1290, 2796),
        (1320, 2868),
        (2736, 1260),
        (2796, 1290),
        (2868, 1320),
    },
    "ipad_13": {
        (2048, 2732),
        (2064, 2752),
        (2732, 2048),
        (2752, 2064),
    },
}
READY_STATUS = "ready"
CANONICAL_PUBLIC_URLS = {
    "marketingURL": "https://atrak.dev/apps/hoopsclips/",
    "supportURL": "https://atrak.dev/apps/hoopsclips/support.html",
    "privacyPolicyURL": "https://atrak.dev/apps/hoopsclips/privacy.html",
    "termsOfServiceURL": "https://atrak.dev/apps/hoopsclips/terms.html",
}
EXPECTED_CATEGORIES = {
    "primary": "Photo & Video",
    "secondary": "Sports",
}
EXPECTED_PRIVACY_DATA_TYPES = {
    "Email Address": True,
    "Photos or Videos": True,
    "User ID": True,
    "Device ID": True,
    "Purchase History": False,
    "Customer Support": True,
    "Product Interaction": False,
    "Other Diagnostic Data": False,
}
EXPECTED_AGE_FEATURES = {
    "parentalControls",
    "ageAssurance",
    "unrestrictedWebAccess",
    "broadUserGeneratedContentDistribution",
    "socialMedia",
    "messagingAndChat",
    "advertising",
}
REQUIRED_OPERATOR_GATES = {
    "app_review_account",
    "app_store_listing",
    "app_store_screenshots",
    "build_selection",
    "pricing_availability",
    "app_privacy",
    "age_rating",
    "content_rights",
    "digital_services_act",
    "first_subscription_review",
    "installed_testflight_smoke",
    "shared_backend_accuracy",
    "final_add_for_review",
}


@dataclass(frozen=True)
class Finding:
    status: str
    check: str
    detail: str


class PackageValidationError(ValueError):
    pass


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PackageValidationError(f"{field} must be an object")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise PackageValidationError(f"{field} must be an array")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PackageValidationError(f"{field} must be a non-empty string")
    return value.strip()


def resolve_repo_path(repo_root: Path, raw_path: Any, field: str) -> Path:
    if isinstance(raw_path, Path):
        relative = raw_path
    else:
        relative = Path(_text(raw_path, field))
    if relative.is_absolute():
        raise PackageValidationError(f"{field} must be repository-relative")
    resolved_root = repo_root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise PackageValidationError(f"{field} escapes the repository root")
    return resolved


def read_png_info(path: Path) -> tuple[int, int, bool]:
    data = path.read_bytes()
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise PackageValidationError(f"{path} is not a valid PNG")
    ihdr_length = struct.unpack(">I", data[8:12])[0]
    if data[12:16] != b"IHDR" or ihdr_length != 13:
        raise PackageValidationError(f"{path} has an invalid PNG header")
    width, height = struct.unpack(">II", data[16:24])
    color_type = data[25]
    has_alpha = color_type in {4, 6} or b"tRNS" in data
    return width, height, has_alpha


def validate_package(
    repo_root: Path,
    metadata_path: Path = DEFAULT_METADATA_PATH,
) -> list[Finding]:
    findings: list[Finding] = []
    resolved_metadata_path = resolve_repo_path(repo_root, metadata_path, "metadataPath")
    try:
        metadata = json.loads(resolved_metadata_path.read_text(encoding="utf-8"))
        root = _mapping(metadata, "metadata")
    except (OSError, json.JSONDecodeError, PackageValidationError) as error:
        return [Finding("error", "metadata", str(error))]

    if root.get("schemaVersion") != EXPECTED_SCHEMA_VERSION:
        findings.append(
            Finding(
                "error",
                "schemaVersion",
                f"Expected {EXPECTED_SCHEMA_VERSION!r}.",
            )
        )

    try:
        listing = _mapping(root.get("listing"), "listing")
        for field, limit in TEXT_LIMITS.items():
            value = _text(listing.get(field), f"listing.{field}")
            if len(value) > limit:
                findings.append(
                    Finding(
                        "error",
                        f"listing.{field}",
                        f"{len(value)} characters exceeds the {limit}-character limit.",
                    )
                )
        keywords = _text(listing.get("keywords"), "listing.keywords")
        keyword_bytes = len(keywords.encode("utf-8"))
        if keyword_bytes > 100:
            findings.append(
                Finding(
                    "error",
                    "listing.keywords",
                    f"{keyword_bytes} UTF-8 bytes exceeds the 100-byte limit.",
                )
            )
        elif any(not keyword.strip() for keyword in keywords.split(",")):
            findings.append(
                Finding("error", "listing.keywords", "Keywords contain an empty entry.")
            )
        else:
            findings.append(
                Finding("pass", "listing", "App Store text fields fit their declared limits.")
            )
    except PackageValidationError as error:
        findings.append(Finding("error", "listing", str(error)))

    try:
        categories = _mapping(root.get("categories"), "categories")
        category_errors: list[str] = []
        for field, expected in EXPECTED_CATEGORIES.items():
            if _text(categories.get(field), f"categories.{field}") != expected:
                category_errors.append(f"{field} must be {expected}")
        if _text(categories.get("status"), "categories.status") != READY_STATUS:
            category_errors.append("category selection must be marked ready")
        if category_errors:
            findings.append(Finding("error", "categories", "; ".join(category_errors) + "."))
        else:
            findings.append(
                Finding("pass", "categories", "Photo & Video primary and Sports secondary categories are finalized.")
            )
    except PackageValidationError as error:
        findings.append(Finding("error", "categories", str(error)))

    try:
        brand = _mapping(root.get("brand"), "brand")
        app_icon = resolve_repo_path(repo_root, brand.get("appIconPath"), "brand.appIconPath")
        brand_mark = resolve_repo_path(repo_root, brand.get("brandMarkPath"), "brand.brandMarkPath")
        icon_width, icon_height, icon_alpha = read_png_info(app_icon)
        mark_width, mark_height, mark_alpha = read_png_info(brand_mark)
        if (icon_width, icon_height) != (1024, 1024) or icon_alpha:
            findings.append(
                Finding("error", "brand.appIcon", "App icon must be a 1024 x 1024 PNG without alpha.")
            )
        elif mark_width != mark_height or mark_alpha:
            findings.append(
                Finding("error", "brand.brandMark", "Brand mark must be a square PNG without alpha.")
            )
        else:
            findings.append(
                Finding("pass", "brand", "Canonical iOS AppIcon and BrandMark assets are valid PNGs.")
            )
    except (OSError, PackageValidationError) as error:
        findings.append(Finding("error", "brand", str(error)))

    try:
        urls = _mapping(root.get("urls"), "urls")
        url_errors: list[str] = []
        for field, expected in CANONICAL_PUBLIC_URLS.items():
            entry = _mapping(urls.get(field), f"urls.{field}")
            value = _text(entry.get("value"), f"urls.{field}.value")
            status = _text(entry.get("status"), f"urls.{field}.status")
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
                url_errors.append(f"{field} must be a plain public HTTPS URL")
            if value != expected:
                url_errors.append(f"{field} must use the canonical HoopClips page")
            if status != READY_STATUS:
                url_errors.append(f"{field} must be marked ready after live verification")
        if url_errors:
            findings.append(Finding("error", "urls", "; ".join(url_errors) + "."))
        else:
            findings.append(
                Finding(
                    "pass",
                    "urls",
                    "Canonical HoopClips product, support, privacy, and terms URLs are ready.",
                )
            )
    except PackageValidationError as error:
        findings.append(Finding("error", "urls", str(error)))

    try:
        privacy = _mapping(root.get("privacyDeclaration"), "privacyDeclaration")
        privacy_manifest_path = resolve_repo_path(
            repo_root,
            privacy.get("privacyManifestPath"),
            "privacyDeclaration.privacyManifestPath",
        )
        if not privacy_manifest_path.is_file():
            findings.append(
                Finding("error", "privacyDeclaration", "The first-party privacy manifest is missing.")
            )
        privacy_errors: list[str] = []
        if privacy.get("collectsData") is not True:
            privacy_errors.append("collectsData must be true")
        if privacy.get("tracking") is not False:
            privacy_errors.append("tracking must be false")
        declared_types: dict[str, bool] = {}
        for index, raw_entry in enumerate(_list(privacy.get("dataTypes"), "privacyDeclaration.dataTypes")):
            entry = _mapping(raw_entry, f"privacyDeclaration.dataTypes[{index}]")
            data_type = _text(entry.get("type"), f"privacyDeclaration.dataTypes[{index}].type")
            if data_type in declared_types:
                privacy_errors.append(f"duplicate data type {data_type}")
                continue
            linked = entry.get("linkedToUser")
            if not isinstance(linked, bool):
                privacy_errors.append(f"{data_type} linkedToUser must be boolean")
                continue
            declared_types[data_type] = linked
            if entry.get("tracking") is not False:
                privacy_errors.append(f"{data_type} must not be marked for tracking")
            purposes = _list(entry.get("purposes"), f"privacyDeclaration.dataTypes[{index}].purposes")
            if purposes != ["App Functionality"]:
                privacy_errors.append(f"{data_type} must use App Functionality only")
        if declared_types != EXPECTED_PRIVACY_DATA_TYPES:
            missing = sorted(set(EXPECTED_PRIVACY_DATA_TYPES) - set(declared_types))
            extra = sorted(set(declared_types) - set(EXPECTED_PRIVACY_DATA_TYPES))
            mismatched = sorted(
                data_type
                for data_type in set(declared_types) & set(EXPECTED_PRIVACY_DATA_TYPES)
                if declared_types[data_type] != EXPECTED_PRIVACY_DATA_TYPES[data_type]
            )
            if missing:
                privacy_errors.append(f"missing data types: {', '.join(missing)}")
            if extra:
                privacy_errors.append(f"unexpected data types: {', '.join(extra)}")
            if mismatched:
                privacy_errors.append(f"incorrect linked-to-user values: {', '.join(mismatched)}")
        if privacy_errors:
            findings.append(Finding("error", "privacyDeclaration", "; ".join(privacy_errors) + "."))
        else:
            findings.append(
                Finding(
                    "pass",
                    "privacyDeclaration",
                    "No-tracking App Privacy data map matches the iOS and RevenueCat manifests.",
                )
            )
    except (OSError, PackageValidationError) as error:
        findings.append(Finding("error", "privacyDeclaration", str(error)))

    try:
        pricing = _mapping(root.get("pricingAvailabilityDraft"), "pricingAvailabilityDraft")
        content_rights = _mapping(root.get("contentRightsDraft"), "contentRightsDraft")
        age_rating = _mapping(root.get("ageRatingDraft"), "ageRatingDraft")
        age_features = _mapping(age_rating.get("features"), "ageRatingDraft.features")
        draft_errors: list[str] = []
        if pricing.get("appPrice") != "Free":
            draft_errors.append("appPrice must be Free")
        if pricing.get("availability") != "all_countries_or_regions":
            draft_errors.append("availability must be all_countries_or_regions")
        if content_rights.get("containsOrAccessesThirdPartyContent") is not True:
            draft_errors.append("content-rights draft must acknowledge user-uploaded content")
        if content_rights.get("necessaryRightsRequired") is not True:
            draft_errors.append("content-rights draft must require necessary rights")
        if set(age_features) != EXPECTED_AGE_FEATURES:
            draft_errors.append("age-rating feature set is incomplete or contains unexpected keys")
        if any(value is not False for value in age_features.values()):
            draft_errors.append("all declared age-rating capability flags must be false")
        if age_rating.get("contentFrequency") != "none":
            draft_errors.append("age-rating content frequency must be none")
        if draft_errors:
            findings.append(Finding("error", "submissionDrafts", "; ".join(draft_errors) + "."))
        else:
            findings.append(
                Finding(
                    "pass",
                    "submissionDrafts",
                    "Free pricing, content-rights, and age-rating answers are explicitly prepared for operator confirmation.",
                )
            )
    except PackageValidationError as error:
        findings.append(Finding("error", "submissionDrafts", str(error)))

    seen_device_classes: set[str] = set()
    try:
        screenshot_sets = _list(root.get("screenshots"), "screenshots")
        for index, raw_set in enumerate(screenshot_sets):
            screenshot_set = _mapping(raw_set, f"screenshots[{index}]")
            device_class = _text(
                screenshot_set.get("deviceClass"),
                f"screenshots[{index}].deviceClass",
            )
            if device_class not in ALLOWED_SCREENSHOT_DIMENSIONS:
                findings.append(
                    Finding("error", "screenshots", f"Unsupported device class {device_class!r}.")
                )
                continue
            if device_class in seen_device_classes:
                findings.append(
                    Finding("error", "screenshots", f"Duplicate device class {device_class!r}.")
                )
            seen_device_classes.add(device_class)
            paths = _list(screenshot_set.get("paths"), f"screenshots[{index}].paths")
            if not 1 <= len(paths) <= 10:
                findings.append(
                    Finding(
                        "error",
                        "screenshots",
                        f"{device_class} must include between 1 and 10 screenshots.",
                    )
                )
            for path_index, raw_path in enumerate(paths):
                screenshot_path = resolve_repo_path(
                    repo_root,
                    raw_path,
                    f"screenshots[{index}].paths[{path_index}]",
                )
                width, height, has_alpha = read_png_info(screenshot_path)
                if (width, height) not in ALLOWED_SCREENSHOT_DIMENSIONS[device_class]:
                    findings.append(
                        Finding(
                            "error",
                            "screenshots",
                            f"{screenshot_path.relative_to(repo_root.resolve())} has unsupported dimensions {width} x {height} for {device_class}.",
                        )
                    )
                if has_alpha:
                    findings.append(
                        Finding(
                            "error",
                            "screenshots",
                            f"{screenshot_path.relative_to(repo_root.resolve())} contains an alpha channel.",
                        )
                    )
        missing = sorted(set(ALLOWED_SCREENSHOT_DIMENSIONS) - seen_device_classes)
        if missing:
            findings.append(
                Finding("error", "screenshots", f"Missing required device sets: {', '.join(missing)}.")
            )
        elif not any(item.status == "error" and item.check == "screenshots" for item in findings):
            findings.append(
                Finding("pass", "screenshots", "Required iPhone 6.9-inch and iPad 13-inch PNG sets are valid.")
            )
    except (OSError, PackageValidationError) as error:
        findings.append(Finding("error", "screenshots", str(error)))

    try:
        screenshot_review = _mapping(root.get("screenshotContentReview"), "screenshotContentReview")
        status = _text(screenshot_review.get("status"), "screenshotContentReview.status")
        _text(screenshot_review.get("reviewedAt"), "screenshotContentReview.reviewedAt")
        _text(screenshot_review.get("evidence"), "screenshotContentReview.evidence")
        if status != READY_STATUS:
            findings.append(Finding("error", "screenshotContentReview", "Screenshot content review must be ready."))
        else:
            findings.append(Finding("pass", "screenshotContentReview", "Screenshot order and content review are recorded."))
    except PackageValidationError as error:
        findings.append(Finding("error", "screenshotContentReview", str(error)))

    try:
        release = _mapping(root.get("release"), "release")
        release_version = _text(release.get("version"), "release.version")
        release_build = _text(release.get("build"), "release.build")
        release_config_path = resolve_repo_path(
            repo_root,
            release.get("configurationPath"),
            "release.configurationPath",
        )
        release_config = release_config_path.read_text(encoding="utf-8")
        if release.get("backendMode") != "production_cloud_only":
            findings.append(
                Finding("error", "release.backendMode", "Release must remain production_cloud_only.")
            )
        if release.get("localRenderFallback") is not False:
            findings.append(
                Finding("error", "release.localRenderFallback", "Local render fallback must remain disabled.")
            )
        if "HOOPS_APP_ENV = production" not in release_config:
            findings.append(
                Finding("error", "release.configuration", "Release.xcconfig must select the production environment.")
            )
        if "HOOPS_CLOUD_LAUNCH_MODE = enabled" not in release_config:
            findings.append(
                Finding("error", "release.configuration", "Release.xcconfig must require enabled cloud launch mode.")
            )
        project_text = (repo_root / DEFAULT_PROJECT_FILE).read_text(encoding="utf-8")
        marketing_versions = set(re.findall(r"MARKETING_VERSION\s*=\s*([^;\s]+)\s*;", project_text))
        build_versions = set(re.findall(r"CURRENT_PROJECT_VERSION\s*=\s*([^;\s]+)\s*;", project_text))
        if release_version not in marketing_versions:
            findings.append(
                Finding("error", "release.version", "Metadata version does not match an Xcode target marketing version.")
            )
        if release_build not in build_versions:
            findings.append(
                Finding("error", "release.build", "Metadata build does not match an Xcode target build number.")
            )
        if not any(item.status == "error" and item.check.startswith("release.") for item in findings):
            findings.append(
                Finding(
                    "pass",
                    "release",
                    f"Listing matches Xcode version/build {release_version} ({release_build}) and declares cloud-only mode.",
                )
            )
    except (OSError, PackageValidationError) as error:
        findings.append(Finding("error", "release", str(error)))

    try:
        audit = _mapping(root.get("appStoreConnectAudit"), "appStoreConnectAudit")
        audit_build = _mapping(audit.get("testFlightBuild"), "appStoreConnectAudit.testFlightBuild")
        dsa = _mapping(audit.get("digitalServicesAct"), "appStoreConnectAudit.digitalServicesAct")
        subscription = _mapping(audit.get("subscription"), "appStoreConnectAudit.subscription")
        release = _mapping(root.get("release"), "release")
        audit_errors: list[str] = []
        if audit.get("versionState") != "prepare_for_submission":
            audit_errors.append("version state must remain prepare_for_submission until review submission")
        if audit_build.get("version") != release.get("version") or audit_build.get("build") != release.get("build"):
            audit_errors.append("TestFlight build evidence must match the release version and build")
        if audit_build.get("processingState") != "valid":
            audit_errors.append("TestFlight build must be valid")
        if dsa != {"status": "ready", "declaration": "non_trader"}:
            audit_errors.append("DSA non-trader declaration must be recorded as ready")
        if subscription.get("productId") != "monthly_premium":
            audit_errors.append("monthly_premium subscription evidence is missing")
        if subscription.get("basePriceUSD") != "9.99":
            audit_errors.append("subscription base price evidence must be USD 9.99")
        if subscription.get("availability") != "all_countries_or_regions":
            audit_errors.append("subscription availability evidence must cover all countries or regions")
        if audit_errors:
            findings.append(Finding("error", "appStoreConnectAudit", "; ".join(audit_errors) + "."))
        else:
            findings.append(
                Finding(
                    "pass",
                    "appStoreConnectAudit",
                    "Live build, DSA, and subscription evidence is recorded without credentials.",
                )
            )
    except PackageValidationError as error:
        findings.append(Finding("error", "appStoreConnectAudit", str(error)))

    try:
        operator_gates = _list(root.get("operatorGates"), "operatorGates")
        if not operator_gates:
            findings.append(Finding("error", "operatorGates", "At least one explicit operator gate is required."))
        seen_gate_ids: set[str] = set()
        for index, raw_gate in enumerate(operator_gates):
            gate = _mapping(raw_gate, f"operatorGates[{index}]")
            gate_id = _text(gate.get("id"), f"operatorGates[{index}].id")
            status = _text(gate.get("status"), f"operatorGates[{index}].status")
            detail = _text(gate.get("detail"), f"operatorGates[{index}].detail")
            if gate_id in seen_gate_ids:
                findings.append(Finding("error", "operatorGates", f"Duplicate operator gate {gate_id}."))
            seen_gate_ids.add(gate_id)
            if status not in {READY_STATUS, "operator_review_required"}:
                findings.append(
                    Finding("error", "operatorGates", f"Gate {gate_id} has unsupported status {status}.")
                )
            if status != READY_STATUS:
                findings.append(Finding("blocked", gate_id, detail))
        missing_gate_ids = sorted(REQUIRED_OPERATOR_GATES - seen_gate_ids)
        if missing_gate_ids:
            findings.append(
                Finding(
                    "error",
                    "operatorGates",
                    f"Missing required operator gates: {', '.join(missing_gate_ids)}.",
                )
            )
    except PackageValidationError as error:
        findings.append(Finding("error", "operatorGates", str(error)))

    return findings


def has_errors(findings: list[Finding]) -> bool:
    return any(finding.status == "error" for finding in findings)


def has_blockers(findings: list[Finding]) -> bool:
    return any(finding.status == "blocked" for finding in findings)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the HoopClips App Store submission package.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Fail while any external/operator gate remains unresolved.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    findings = validate_package(args.repo_root, args.metadata)
    for finding in findings:
        print(f"[{finding.status.upper()}] {finding.check}: {finding.detail}")
    if has_errors(findings):
        return 1
    if args.require_ready and has_blockers(findings):
        return 2
    print("App Store package is structurally valid.")
    if has_blockers(findings):
        print("External/operator gates remain; this is not App Store submission proof.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
