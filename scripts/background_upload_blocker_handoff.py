#!/usr/bin/env python3
"""Create a shareable markdown handoff from background-upload blocker state."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


def load_snapshot_module() -> Any:
    snapshot_path = SCRIPT_DIR / "background_upload_blocker_snapshot.py"
    spec = importlib.util.spec_from_file_location("background_upload_blocker_snapshot", snapshot_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load blocker snapshot helper from {snapshot_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a markdown handoff for HoopClips background-upload blockers."
    )
    parser.add_argument("--proof-dir", required=True, help="Directory containing proof files.")
    parser.add_argument("--commit", help="Expected git commit for the proof packet.")
    parser.add_argument("--build", help="Expected TestFlight build for the proof packet.")
    parser.add_argument("--out", help="Write markdown here. Defaults to stdout.")
    return parser.parse_args()


def yes_no(value: Any) -> str:
    if value is True:
        return "pass"
    if value is False:
        return "missing_or_failed"
    if value is None:
        return "missing"
    return str(value)


def markdown_list(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def build_markdown(result: dict[str, Any]) -> str:
    created_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    signals = result.get("readySignals") or {}
    files = result.get("files") or {}
    blockers = result.get("blockers") or []
    ready = result.get("backgroundUploadGoalProofReady") is True

    file_lines: list[str] = []
    for name, info in files.items():
        status = "present" if info.get("exists") else "missing"
        file_lines.append(f"- {name}: {status} ({info.get('path')})")

    signal_lines = [
        f"- {name}: {yes_no(value)}"
        for name, value in signals.items()
    ]

    return f"""# HoopClips Background Upload Blocker Handoff

Created at: `{created_at}`
Proof ready: `{str(ready).lower()}`
Proof dir: `{result.get("proofDir")}`
Expected commit: `{result.get("expectedCommit") or "not provided"}`
Expected build: `{result.get("expectedBuild") or "not provided"}`

## Ready signals

{markdown_list(signal_lines)}

## Evidence files

{markdown_list(file_lines)}

## Remaining blockers

{markdown_list(blockers)}

## Interpretation

```text
If Proof ready is false, do not call background upload complete.
The goal is complete only after the real iPhone/TestFlight/background-upload evidence passes and the final launch evidence is ready.
```

## Next action

```text
Collect the missing evidence files, rerun the launch proof workflow, then rerun this handoff.
```
"""


def main() -> int:
    args = parse_args()
    snapshot = load_snapshot_module()
    result = snapshot.evaluate(args)
    markdown = build_markdown(result)
    if args.out:
        Path(args.out).write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0 if result.get("backgroundUploadGoalProofReady") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
