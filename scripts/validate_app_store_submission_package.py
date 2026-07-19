#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_METADATA_PATH = Path("ios/docs/app-store/app-store-metadata-en-US.json")
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
        release = _mapping(root.get("release"), "release")
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
        if not any(item.status == "error" and item.check.startswith("release.") for item in findings):
            findings.append(
                Finding("pass", "release", "Listing declares the submitted app as cloud-only.")
            )
    except (OSError, PackageValidationError) as error:
        findings.append(Finding("error", "release", str(error)))

    try:
        operator_gates = _list(root.get("operatorGates"), "operatorGates")
        if not operator_gates:
            findings.append(Finding("error", "operatorGates", "At least one explicit operator gate is required."))
        for index, raw_gate in enumerate(operator_gates):
            gate = _mapping(raw_gate, f"operatorGates[{index}]")
            gate_id = _text(gate.get("id"), f"operatorGates[{index}].id")
            status = _text(gate.get("status"), f"operatorGates[{index}].status")
            detail = _text(gate.get("detail"), f"operatorGates[{index}].detail")
            if status != READY_STATUS:
                findings.append(Finding("blocked", gate_id, detail))
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
