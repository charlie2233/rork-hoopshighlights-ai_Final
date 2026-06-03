#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from scripts.build_launch_team_accuracy_report import manifest_case_entry
from scripts.build_team_highlight_eval_payload import load_json, manual_label_completion_missing_fields, string_or_none


FORBIDDEN_LABEL_KEYS = {
    "downloadUrl",
    "presignedUrl",
    "resultObjectKey",
    "sourceObjectKey",
    "sourceUrl",
    "uploadHeaders",
    "uploadUrl",
}


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    downloads_dir = Path(args.downloads_dir).expanduser().resolve()
    bundle_path = Path(args.bundle).expanduser().resolve() if args.bundle else None
    explicit_sources = parse_label_sources(args.label or [])
    report = apply_manual_labels(
        manifest=load_json(manifest_path),
        manifest_dir=manifest_path.parent,
        downloads_dir=downloads_dir,
        bundle_path=bundle_path,
        explicit_sources=explicit_sources,
        apply=args.apply,
        allow_incomplete=args.allow_incomplete,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(report)
    return 0 if report["status"] == "ready" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and optionally apply manual label JSON files downloaded from the HoopClips "
            "team-highlight review page. This reads/writes metadata JSON only; it does not inspect, "
            "upload, render, or export video."
        )
    )
    parser.add_argument("--manifest", required=True, help="Team-highlight accuracy manifest JSON.")
    parser.add_argument("--downloads-dir", default="~/Downloads", help="Directory containing downloaded *_manual_labels.json files.")
    parser.add_argument(
        "--bundle",
        help="Single team_highlight_manual_labels_bundle.json file downloaded from the local review page.",
    )
    parser.add_argument(
        "--label",
        action="append",
        help="Explicit source mapping as caseId=/absolute/path/to/case_manual_labels.json. Repeat for multiple cases.",
    )
    parser.add_argument("--apply", action="store_true", help="Overwrite manifest label files after validation. Default is dry-run.")
    parser.add_argument("--allow-incomplete", action="store_true", help="Allow incomplete rows to be copied. Not suitable for launch evidence.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable status.")
    return parser.parse_args()


def parse_label_sources(values: list[str]) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--label must use caseId=/absolute/path.json")
        case_id, raw_path = value.split("=", 1)
        case_id = case_id.strip()
        if not case_id:
            raise ValueError("--label is missing a case id.")
        sources[case_id] = Path(raw_path).expanduser().resolve()
    return sources


def apply_manual_labels(
    *,
    manifest: dict[str, Any],
    manifest_dir: Path,
    downloads_dir: Path,
    explicit_sources: dict[str, Path],
    apply: bool,
    allow_incomplete: bool,
    bundle_path: Path | None = None,
) -> dict[str, Any]:
    entries = manifest.get("cases")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must contain a non-empty cases array.")

    bundled_labels = load_label_bundle(bundle_path) if bundle_path is not None else {}
    warnings: list[str] = []
    if allow_incomplete:
        warnings.append(
            "Partial checkpoint mode: --allow-incomplete output is not launch evidence. "
            "After every clip is human-reviewed, reapply the final bundle without --allow-incomplete "
            "before building the launch accuracy report."
        )
    case_reports: list[dict[str, Any]] = []
    total_complete = 0
    total_incomplete = 0
    failure_count = 0
    applied_count = 0
    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"Manifest case {index} must be an object.")
        entry = manifest_case_entry(raw_entry, index, manifest_dir)
        current_labels = load_json(entry.labels_path)
        case_id = entry.case_id or string_or_none(current_labels.get("caseId")) or f"case_{index + 1}"
        explicit_source_path = explicit_sources.get(case_id)
        bundled_payload = bundled_labels.get(case_id) if explicit_source_path is None else None
        source_path = explicit_source_path or (bundle_path if bundled_payload is not None else downloads_dir / f"{case_id}_manual_labels.json")
        case_report = validate_downloaded_labels(
            case_id=case_id,
            current_labels=current_labels,
            source_path=source_path,
            labels_payload=bundled_payload,
            target_path=entry.labels_path,
            allow_incomplete=allow_incomplete,
        )
        if case_report["status"] == "ready" and apply:
            entry.labels_path.write_text(json.dumps(case_report["labelsPayload"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
            case_report["applied"] = True
            applied_count += 1
        else:
            case_report["applied"] = False
        total_complete += int(case_report["completeClipCount"])
        total_incomplete += int(case_report["incompleteClipCount"])
        if case_report["status"] != "ready":
            failure_count += 1
        case_report.pop("labelsPayload", None)
        case_reports.append(case_report)

    status = "ready" if failure_count == 0 else "blocked"
    return {
        "schemaVersion": "team-highlight-manual-label-apply-v1",
        "status": status,
        "mode": "apply" if apply else "dry_run",
        "launchEvidenceEligible": not allow_incomplete and total_incomplete == 0,
        "warnings": warnings,
        "caseCount": len(case_reports),
        "appliedCaseCount": applied_count,
        "completeClipCount": total_complete,
        "incompleteClipCount": total_incomplete,
        "cases": case_reports,
    }


def load_label_bundle(bundle_path: Path) -> dict[str, dict[str, Any]]:
    if not bundle_path.exists():
        raise ValueError(f"Bundle file is missing: {bundle_path}")
    payload = load_json(bundle_path)
    if payload.get("schemaVersion") != "team-highlight-manual-label-bundle-v1":
        raise ValueError("Bundle must use schemaVersion team-highlight-manual-label-bundle-v1.")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Bundle must contain a non-empty cases array.")
    by_case_id: dict[str, dict[str, Any]] = {}
    for index, case_payload in enumerate(cases):
        if not isinstance(case_payload, dict):
            raise ValueError(f"Bundle case {index} must be an object.")
        case_id = string_or_none(case_payload.get("caseId"))
        if not case_id:
            raise ValueError(f"Bundle case {index} is missing caseId.")
        if case_id in by_case_id:
            raise ValueError(f"Bundle contains duplicate caseId {case_id!r}.")
        by_case_id[case_id] = case_payload
    return by_case_id


def validate_downloaded_labels(
    *,
    case_id: str,
    current_labels: dict[str, Any],
    source_path: Path,
    labels_payload: dict[str, Any] | None,
    target_path: Path,
    allow_incomplete: bool,
) -> dict[str, Any]:
    base_report: dict[str, Any] = {
        "caseId": case_id,
        "sourcePath": str(source_path),
        "targetPath": str(target_path),
        "status": "blocked",
        "errors": [],
        "completeClipCount": 0,
        "incompleteClipCount": 0,
        "incompleteExamples": [],
    }
    if labels_payload is None and not source_path.exists():
        base_report["errors"].append("downloaded label file is missing")
        return base_report

    labels = labels_payload if labels_payload is not None else load_json(source_path)
    leak_paths = forbidden_label_paths(labels)
    if leak_paths:
        base_report["errors"].append("downloaded label file contains forbidden URL/object-key fields: " + ", ".join(leak_paths[:8]))
        return base_report
    if "X-Amz-Signature" in json.dumps(labels):
        base_report["errors"].append("downloaded label file contains a signed URL marker")
        return base_report

    downloaded_case_id = string_or_none(labels.get("caseId"))
    if downloaded_case_id and downloaded_case_id != case_id:
        base_report["errors"].append(f"downloaded caseId {downloaded_case_id!r} does not match manifest case {case_id!r}")
        return base_report

    current_clips = [clip for clip in current_labels.get("clips", []) if isinstance(clip, dict)]
    downloaded_clips = [clip for clip in labels.get("clips", []) if isinstance(clip, dict)]
    if len(current_clips) != len(downloaded_clips):
        base_report["errors"].append(f"clip count mismatch: expected {len(current_clips)}, got {len(downloaded_clips)}")
        return base_report

    incomplete_examples: list[dict[str, Any]] = []
    complete_count = 0
    incomplete_count = 0
    for index, (current_clip, downloaded_clip) in enumerate(zip(current_clips, downloaded_clips)):
        identity_error = clip_identity_error(index, current_clip, downloaded_clip)
        if identity_error:
            base_report["errors"].append(identity_error)
            return base_report
        missing_fields = manual_label_completion_missing_fields(downloaded_clip)
        if missing_fields:
            incomplete_count += 1
            if len(incomplete_examples) < 5:
                incomplete_examples.append(
                    {
                        "labelId": string_or_none(downloaded_clip.get("labelId") or downloaded_clip.get("id")) or f"clip_{index}",
                        "missingFields": missing_fields,
                    }
                )
        else:
            complete_count += 1

    base_report["completeClipCount"] = complete_count
    base_report["incompleteClipCount"] = incomplete_count
    base_report["incompleteExamples"] = incomplete_examples
    if incomplete_count and not allow_incomplete:
        base_report["errors"].append(f"{incomplete_count} clip label(s) are incomplete")
        return base_report

    base_report["status"] = "ready"
    base_report["labelsPayload"] = labels
    return base_report


def clip_identity_error(index: int, current_clip: dict[str, Any], downloaded_clip: dict[str, Any]) -> str | None:
    for key in ("labelId", "predictionClipId"):
        current_value = string_or_none(current_clip.get(key))
        downloaded_value = string_or_none(downloaded_clip.get(key))
        if current_value and downloaded_value and current_value != downloaded_value:
            return f"clip {index} {key} mismatch: expected {current_value!r}, got {downloaded_value!r}"
    return None


def forbidden_label_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            if key in FORBIDDEN_LABEL_KEYS or key.lower().endswith("url"):
                paths.append(path)
                continue
            paths.extend(forbidden_label_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(forbidden_label_paths(item, f"{prefix}[{index}]"))
    return paths


def print_text_report(report: dict[str, Any]) -> None:
    print(f"status={report['status']}")
    print(f"mode={report['mode']}")
    print(f"launchEvidenceEligible={str(report.get('launchEvidenceEligible', False)).lower()}")
    for warning in report.get("warnings", []):
        print(f"warning={warning}")
    print(f"cases={report['caseCount']}")
    print(f"clips={report['completeClipCount']} complete / {report['completeClipCount'] + report['incompleteClipCount']} total")
    for case in report["cases"]:
        print(f"- {case['caseId']}: {case['status']} ({case['completeClipCount']} complete, {case['incompleteClipCount']} incomplete)")
        for error in case["errors"]:
            print(f"  error: {error}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
