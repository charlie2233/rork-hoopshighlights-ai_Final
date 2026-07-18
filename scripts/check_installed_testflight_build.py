#!/usr/bin/env python3
"""Verify the installed HoopClips TestFlight build on a physical iPhone.

This helper is read-only unless --launch is passed. It never installs,
uploads, archives, submits, or prints secrets. The goal is to turn the first
step of the real-device smoke into a repeatable check:

    installed app == atrak.charlie.hoopsclips 1.0.0 (51)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


EXPECTED_BUNDLE_ID = "atrak.charlie.hoopsclips"
EXPECTED_MARKETING_VERSION = "1.0.0"
EXPECTED_BUILD_NUMBER = "51"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check installed HoopClips TestFlight build metadata on a physical iPhone."
    )
    parser.add_argument(
        "--device",
        default=os.environ.get("HOOPS_TESTFLIGHT_DEVICE", ""),
        help="Device UUID, name, DNS name, serial, or ECID. Defaults to HOOPS_TESTFLIGHT_DEVICE or the first available iPhone.",
    )
    parser.add_argument("--bundle-id", default=EXPECTED_BUNDLE_ID)
    parser.add_argument("--marketing-version", default=EXPECTED_MARKETING_VERSION)
    parser.add_argument("--build", default=EXPECTED_BUILD_NUMBER)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--launch",
        action="store_true",
        help="After metadata passes, launch the app on the device. This is the only mutating action.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def parse_device_table(output: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Name ") or line.startswith("----"):
            continue
        parts = line.split()
        identifier_index = next(
            (
                index
                for index, part in enumerate(parts)
                if len(part) == 36 and part.count("-") == 4
            ),
            None,
        )
        if identifier_index is None or len(parts) <= identifier_index + 2:
            continue
        state_tokens = [parts[identifier_index + 1]]
        model_start = identifier_index + 2
        while model_start < len(parts) and parts[model_start].startswith("(") and parts[model_start].endswith(")"):
            state_tokens.append(parts[model_start])
            model_start += 1
        state = " ".join(state_tokens)
        model = " ".join(parts[model_start:])
        devices.append(
            {
                "name": " ".join(parts[: max(0, identifier_index - 1)]),
                "hostname": parts[identifier_index - 1] if identifier_index >= 1 else "",
                "identifier": parts[identifier_index],
                "state": state,
                "model": model,
            }
        )
    return devices


def state_is_available(state: str) -> bool:
    normalized = state.lower().strip()
    return normalized.startswith("available") or normalized == "connected"


def select_device(explicit_device: str, timeout: int) -> tuple[str | None, list[str], list[dict[str, str]]]:
    if explicit_device:
        return explicit_device, [], []

    result = run(["xcrun", "devicectl", "list", "devices"], timeout)
    if result.returncode != 0:
        return None, [safe_error("devicectl list devices failed", result)], []

    devices = parse_device_table(result.stdout)
    available_iphones = [
        device
        for device in devices
        if device["model"].startswith("iPhone") and state_is_available(device["state"])
    ]
    if not available_iphones:
        unavailable = [
            f"{device['name'] or device['identifier']}={device['state']}"
            for device in devices
            if device["model"].startswith("iPhone")
        ]
        detail = ", ".join(unavailable) or "none detected"
        return None, [f"No available physical iPhone found. iPhone states: {detail}."], devices
    return available_iphones[0]["identifier"], [], devices


def load_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("devicectl JSON output was not an object.")
    return parsed


def find_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(find_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(find_dicts(child))
    return found


def value_at(data: dict[str, Any], paths: tuple[tuple[str, ...], ...]) -> str:
    for path in paths:
        current: Any = data
        for part in path:
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current not in (None, ""):
            return str(current)
    return ""


def find_app_record(payload: dict[str, Any], bundle_id: str) -> dict[str, Any] | None:
    for candidate in find_dicts(payload):
        identifier = value_at(
            candidate,
            (
                ("bundleIdentifier",),
                ("bundleID",),
                ("bundleId",),
                ("CFBundleIdentifier",),
                ("applicationIdentifier",),
            ),
        )
        if identifier == bundle_id:
            return candidate
    return None


def extract_app_metadata(app: dict[str, Any]) -> dict[str, str]:
    return {
        "bundleId": value_at(
            app,
            (
                ("bundleIdentifier",),
                ("bundleID",),
                ("bundleId",),
                ("CFBundleIdentifier",),
                ("applicationIdentifier",),
            ),
        ),
        "marketingVersion": value_at(
            app,
            (
                ("shortVersionString",),
                ("bundleShortVersion",),
                ("CFBundleShortVersionString",),
                ("version",),
            ),
        ),
        "buildNumber": value_at(
            app,
            (
                ("bundleVersion",),
                ("CFBundleVersion",),
                ("buildVersion",),
                ("buildNumber",),
            ),
        ),
        "name": value_at(app, (("name",), ("localizedName",), ("displayName",))),
    }


def check_installed_app(args: argparse.Namespace, device: str) -> tuple[dict[str, str], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    with tempfile.NamedTemporaryFile(prefix="hoopclips-installed-app-", suffix=".json", delete=False) as handle:
        json_path = Path(handle.name)
    try:
        result = run(
            [
                "xcrun",
                "devicectl",
                "device",
                "info",
                "apps",
                "--device",
                device,
                "--bundle-id",
                args.bundle_id,
                "--json-output",
                str(json_path),
                "--timeout",
                str(args.timeout),
            ],
            args.timeout + 5,
        )
        if result.returncode != 0:
            blockers.append(safe_error("devicectl app metadata query failed", result))
            return {}, blockers, warnings

        try:
            payload = load_json(json_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            blockers.append(f"Could not read devicectl JSON app metadata: {exc}")
            return {}, blockers, warnings

        if payload.get("error"):
            blockers.append("devicectl JSON reported an error while reading installed app metadata.")
            return {}, blockers, warnings

        app = find_app_record(payload, args.bundle_id)
        if not app:
            blockers.append(f"{args.bundle_id} is not installed on the selected device.")
            return {}, blockers, warnings

        metadata = extract_app_metadata(app)
        if metadata["bundleId"] != args.bundle_id:
            blockers.append(f"Bundle ID mismatch: expected {args.bundle_id}, got {metadata['bundleId'] or 'missing'}.")
        if metadata["marketingVersion"] != args.marketing_version:
            blockers.append(
                f"Marketing version mismatch: expected {args.marketing_version}, got {metadata['marketingVersion'] or 'missing'}."
            )
        if metadata["buildNumber"] != args.build:
            blockers.append(f"Build number mismatch: expected {args.build}, got {metadata['buildNumber'] or 'missing'}.")
        if not metadata["name"]:
            warnings.append("Installed app name was not present in devicectl metadata.")
        return metadata, blockers, warnings
    finally:
        try:
            json_path.unlink()
        except OSError:
            pass


def launch_app(args: argparse.Namespace, device: str) -> list[str]:
    result = run(
        [
            "xcrun",
            "devicectl",
            "device",
            "process",
            "launch",
            "--device",
            device,
            args.bundle_id,
        ],
        args.timeout,
    )
    if result.returncode == 0:
        return []
    return [safe_error("launch failed", result)]


def safe_error(prefix: str, result: subprocess.CompletedProcess[str]) -> str:
    message = (result.stderr or result.stdout or "").strip().splitlines()
    first_line = message[0] if message else f"exit code {result.returncode}"
    detail = f"{prefix}: {first_line}"
    raw_message = "\n".join(message)
    if (
        "CoreDevice.ControlChannelConnectionError" in raw_message
        or "CoreDeviceError error 4000" in raw_message
        or "device disconnected immediately after connecting" in raw_message
        or "Command timeout" in raw_message
        or "Operation timed out" in raw_message
    ):
        detail += (
            " Recovery: unlock the iPhone, connect by USB or restore the same-network device tunnel, "
            "then reopen Xcode Devices and rerun this helper."
        )
    return detail


def print_human(result: dict[str, Any]) -> None:
    print(f"status: {result['status']}")
    print(f"installedTestFlightBuildReady: {str(result['installedTestFlightBuildReady']).lower()}")
    print(f"device: {result.get('device') or 'missing'}")
    metadata = result.get("installedApp") or {}
    if metadata:
        print(f"bundleId: {metadata.get('bundleId') or 'missing'}")
        print(f"marketingVersion: {metadata.get('marketingVersion') or 'missing'}")
        print(f"buildNumber: {metadata.get('buildNumber') or 'missing'}")
    for label in ("blockers", "warnings"):
        items = result.get(label) or []
        if items:
            print(f"{label}:")
            for item in items:
                print(f"- {item}")


def main() -> int:
    args = parse_args()
    blockers: list[str] = []
    warnings: list[str] = []
    device, device_blockers, devices = select_device(args.device, args.timeout)
    blockers.extend(device_blockers)

    metadata: dict[str, str] = {}
    if device:
        metadata, app_blockers, app_warnings = check_installed_app(args, device)
        blockers.extend(app_blockers)
        warnings.extend(app_warnings)
        if args.launch and not blockers:
            blockers.extend(launch_app(args, device))

    ready = not blockers
    result = {
        "status": "ready" if ready else "blocked",
        "installedTestFlightBuildReady": ready,
        "device": device,
        "expected": {
            "bundleId": args.bundle_id,
            "marketingVersion": args.marketing_version,
            "buildNumber": args.build,
        },
        "installedApp": metadata,
        "discoveredDevices": devices,
        "launchAttempted": bool(args.launch),
        "blockers": blockers,
        "warnings": warnings,
        "safetyNote": "Read-only installed-app check unless --launch is supplied. No install, upload, archive, submit, or secret printing.",
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_human(result)
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
