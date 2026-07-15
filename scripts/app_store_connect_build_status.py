#!/usr/bin/env python3
"""Verify that a specific App Store Connect build is ready for internal TestFlight."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

try:
    from scripts.app_store_connect_certificates import api_request, create_token
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repo root, to sys.path.
    from app_store_connect_certificates import api_request, create_token


READY_INTERNAL_STATES = {"READY_FOR_BETA_TESTING", "IN_BETA_TESTING"}
TERMINAL_FAILURE_STATES = {"FAILED", "INVALID", "PROCESSING_EXCEPTION"}


def response_data(payload: dict[str, Any] | None, resource: str) -> list[dict[str, Any]]:
    data = payload.get("data") if payload else None
    if not isinstance(data, list):
        raise RuntimeError(f"App Store Connect {resource} response is missing data")
    return data


def find_app(token: str, bundle_id: str) -> dict[str, Any]:
    query = urlencode(
        {
            "filter[bundleId]": bundle_id,
            "fields[apps]": "name,bundleId",
            "limit": "2",
        }
    )
    apps = response_data(api_request("GET", f"/v1/apps?{query}", token), "apps")
    exact_matches = [app for app in apps if app.get("attributes", {}).get("bundleId") == bundle_id]
    if len(exact_matches) != 1:
        raise RuntimeError(f"Expected one App Store Connect app for {bundle_id}; found {len(exact_matches)}")
    return exact_matches[0]


def find_build(
    token: str,
    app_id: str,
    marketing_version: str,
    build_version: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    query = urlencode(
        {
            "filter[app]": app_id,
            "filter[version]": build_version,
            "filter[preReleaseVersion.version]": marketing_version,
            "filter[preReleaseVersion.platform]": "IOS",
            "fields[builds]": (
                "version,uploadedDate,expirationDate,expired,minOsVersion,processingState,"
                "buildAudienceType,usesNonExemptEncryption,buildBetaDetail,preReleaseVersion"
            ),
            "include": "buildBetaDetail,preReleaseVersion",
            "fields[buildBetaDetails]": "autoNotifyEnabled,internalBuildState,externalBuildState,build",
            "fields[preReleaseVersions]": "version,platform",
            "limit": "2",
            "sort": "-uploadedDate",
        }
    )
    payload = api_request("GET", f"/v1/builds?{query}", token)
    builds = response_data(payload, "builds")
    included = payload.get("included", []) if payload else []
    if not isinstance(included, list):
        raise RuntimeError("App Store Connect builds response has invalid included resources")
    return (builds[0] if builds else None), included


def relationship_id(resource: dict[str, Any], name: str) -> str | None:
    linkage = resource.get("relationships", {}).get(name, {}).get("data")
    return linkage.get("id") if isinstance(linkage, dict) and isinstance(linkage.get("id"), str) else None


def included_resource(
    included: list[dict[str, Any]],
    resource_type: str,
    resource_id: str | None,
) -> dict[str, Any] | None:
    if resource_id is None:
        return None
    return next(
        (
            resource
            for resource in included
            if resource.get("type") == resource_type and resource.get("id") == resource_id
        ),
        None,
    )


def inspect_build(
    *,
    key_path: Path,
    key_id: str,
    issuer_id: str,
    bundle_id: str,
    marketing_version: str,
    build_version: str,
) -> dict[str, Any]:
    token = create_token(key_path, key_id, issuer_id)
    app = find_app(token, bundle_id)
    build, included = find_build(token, app["id"], marketing_version, build_version)
    app_attributes = app.get("attributes", {})
    if build is None:
        return {
            "appName": app_attributes.get("name"),
            "bundleId": bundle_id,
            "marketingVersion": marketing_version,
            "buildVersion": build_version,
            "buildFound": False,
            "readyForInternalTesting": False,
        }

    build_attributes = build.get("attributes", {})
    beta_detail = included_resource(
        included,
        "buildBetaDetails",
        relationship_id(build, "buildBetaDetail"),
    )
    prerelease_version = included_resource(
        included,
        "preReleaseVersions",
        relationship_id(build, "preReleaseVersion"),
    )
    beta_attributes = beta_detail.get("attributes", {}) if beta_detail else {}
    prerelease_attributes = prerelease_version.get("attributes", {}) if prerelease_version else {}
    processing_state = build_attributes.get("processingState")
    internal_state = beta_attributes.get("internalBuildState")
    expired = build_attributes.get("expired")
    ready = processing_state == "VALID" and internal_state in READY_INTERNAL_STATES and expired is False

    return {
        "appName": app_attributes.get("name"),
        "bundleId": bundle_id,
        "marketingVersion": prerelease_attributes.get("version", marketing_version),
        "platform": prerelease_attributes.get("platform", "IOS"),
        "buildVersion": build_attributes.get("version", build_version),
        "buildFound": True,
        "uploadedDate": build_attributes.get("uploadedDate"),
        "expirationDate": build_attributes.get("expirationDate"),
        "expired": expired,
        "minimumOsVersion": build_attributes.get("minOsVersion"),
        "processingState": processing_state,
        "internalBuildState": internal_state,
        "externalBuildState": beta_attributes.get("externalBuildState"),
        "buildAudienceType": build_attributes.get("buildAudienceType"),
        "usesNonExemptEncryption": build_attributes.get("usesNonExemptEncryption"),
        "readyForInternalTesting": ready,
    }


def terminal_failure(status: dict[str, Any]) -> bool:
    return (
        status.get("processingState") in TERMINAL_FAILURE_STATES
        or status.get("internalBuildState") in TERMINAL_FAILURE_STATES
    )


def wait_for_build(
    args: argparse.Namespace,
    *,
    inspect: Callable[..., dict[str, Any]] = inspect_build,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    deadline = monotonic() + args.wait_seconds
    while True:
        status = inspect(
            key_path=Path(args.key_path),
            key_id=args.key_id,
            issuer_id=args.issuer_id,
            bundle_id=args.bundle_id,
            marketing_version=args.marketing_version,
            build_version=args.build_version,
        )
        if status.get("readyForInternalTesting") is True or terminal_failure(status):
            return status
        remaining = deadline - monotonic()
        if remaining <= 0:
            return status
        sleep(min(args.poll_seconds, remaining))


def write_status(status: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(status, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-path", required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--issuer-id", required=True)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--marketing-version", required=True)
    parser.add_argument("--build-version", required=True)
    parser.add_argument("--wait-seconds", type=float, default=0)
    parser.add_argument("--poll-seconds", type=float, default=30)
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.wait_seconds < 0 or args.poll_seconds <= 0:
        parser.error("wait seconds must be nonnegative and poll seconds must be positive")
    return args


def main() -> int:
    args = parse_args()
    try:
        status = wait_for_build(args)
    except RuntimeError as error:
        print(f"App Store Connect status check failed: {error}", file=sys.stderr)
        return 1
    write_status(status, args.output)
    if status.get("readyForInternalTesting") is True:
        print("App Store Connect confirms this build is ready for internal TestFlight.")
        return 0
    print("App Store Connect has not made this build ready for internal TestFlight.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
