#!/usr/bin/env python3
"""Build a sanitized markdown packet from HoopClips phone upload proof."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def load_checker() -> Any:
    checker_path = Path(__file__).with_name("verify_background_upload_phone_proof.py")
    spec = importlib.util.spec_from_file_location(
        "verify_background_upload_phone_proof", checker_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load proof checker from {checker_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a sanitized background-upload phone proof packet."
    )
    parser.add_argument("proof_path", help="Path to copied phone proof text/JSON.")
    parser.add_argument(
        "--out",
        help="Where to write the markdown packet. Defaults to stdout.",
    )
    parser.add_argument(
        "--label",
        default="real-device-background-upload",
        help="Short label for this proof run.",
    )
    parser.add_argument(
        "--commit",
        help="Git commit tested on the phone/TestFlight build, if known.",
    )
    parser.add_argument(
        "--build",
        help="TestFlight build number, if known.",
    )
    return parser.parse_args()


def yes_no(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "missing"
    return str(value)


def bullet_list(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def build_packet(args: argparse.Namespace, result: dict[str, Any]) -> str:
    created_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    blockers = result.get("blockers") or []
    sensitive_hits = result.get("sensitiveHitKinds") or []
    status = result.get("status", "blocked")
    proof_ready = result.get("backgroundUploadPhoneProofReady") is True

    return f"""# HoopClips Background Upload Phone Proof

Label: `{args.label}`
Created at: `{created_at}`
Commit tested: `{args.commit or "unknown"}`
TestFlight build: `{args.build or "unknown"}`

## Result

```text
status: {status}
backgroundUploadPhoneProofReady: {str(proof_ready).lower()}
privacyScanPassed: {str(result.get("privacyScanPassed") is True).lower()}
```

## Parsed signals

```text
parsedFieldCount: {result.get("parsedFieldCount", 0)}
pipelineStage: {result.get("pipelineStage") or "missing"}
uploadComplete: {yes_no(result.get("uploadComplete"))}
activeUploadSessions: {yes_no(result.get("activeUploadSessions"))}
nextAction: {result.get("nextAction") or "missing"}
staleWithoutActiveSession: {yes_no(result.get("staleWithoutActiveSession"))}
appSwitchEvidence: {yes_no(result.get("appSwitchEvidence"))}
continuationReady: {yes_no(result.get("continuationReady"))}
```

## Blockers

{bullet_list(blockers)}

## Privacy scan

Sensitive hit kinds:

{bullet_list(sensitive_hits)}

## Launch interpretation

```text
If status is pass, this packet supports the claim that the tested TestFlight build preserved or safely resumed upload across app switching.

If status is blocked, do not call background upload complete. Fix the listed evidence gap or capture stronger phone proof.
```

## Safety note

This packet intentionally does not include raw phone proof, presigned URLs, local file paths, raw upload IDs, job IDs, object keys, or upload headers.
"""


def main() -> int:
    args = parse_args()
    proof_text = Path(args.proof_path).read_text(encoding="utf-8")
    checker = load_checker()
    result = checker.evaluate(proof_text)
    packet = build_packet(args, result)

    if args.out:
        Path(args.out).write_text(packet, encoding="utf-8")
    else:
        print(packet, end="")
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
