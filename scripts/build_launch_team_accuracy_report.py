#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from scripts.build_team_highlight_eval_payload import (
    DEFAULT_MIN_OVERLAP_RATIO,
    build_eval_payload,
    load_json,
    manual_label_completion_missing_fields,
    number_or_none,
    string_or_none,
)
from scripts.evaluate_team_highlight_accuracy import evaluate_accuracy


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    manifest = load_json(manifest_path)
    if args.label_status:
        status_payload = build_label_status(manifest=manifest, manifest_dir=manifest_path.parent)
        if args.json:
            print(json.dumps(status_payload, indent=2, sort_keys=True))
        else:
            print_label_status(status_payload)
        return 0 if status_payload["status"] == "complete" else 1

    status_payload = build_label_status(manifest=manifest, manifest_dir=manifest_path.parent)
    if status_payload["status"] != "complete":
        print_incomplete_label_status(status_payload, as_json=args.json)
        return 1

    eval_payload = build_launch_eval_payload(
        manifest=manifest,
        manifest_dir=manifest_path.parent,
        min_overlap_ratio=args.min_overlap_ratio,
        allow_unlabeled_predictions=args.allow_unlabeled_predictions,
    )
    report = evaluate_accuracy(eval_payload)

    if args.eval_output:
        write_json(Path(args.eval_output), eval_payload)
    if args.report_output:
        write_json(Path(args.report_output), asdict(report))

    if args.json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        print(f"status={report.status}")
        print(f"cases={report.metrics.caseCount}")
        print(f"clips={report.metrics.clipCount}")
        if report.failures:
            print("failures:")
            for failure in report.failures:
                print(f"- {failure}")

    return 0 if report.status == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a launch-grade HoopClips team/highlight accuracy report from multiple real cloud "
            "analysis JSON files and their manual label files. This does not read videos or call providers."
        )
    )
    parser.add_argument("--manifest", required=True, help="JSON manifest listing analysis/label file pairs.")
    parser.add_argument("--eval-output", help="Write the assembled team-highlight-eval-v1 payload here.")
    parser.add_argument("--report-output", help="Write the evaluated accuracy report JSON here.")
    parser.add_argument("--min-overlap-ratio", type=float, default=DEFAULT_MIN_OVERLAP_RATIO)
    parser.add_argument(
        "--allow-unlabeled-predictions",
        action="store_true",
        help="Allow prediction clips that were returned by analysis but not covered by manual labels.",
    )
    parser.add_argument(
        "--label-status",
        action="store_true",
        help="Print completion status for every manual label file in the manifest and exit before building a report.",
    )
    parser.add_argument("--json", action="store_true", help="Print the evaluated accuracy report JSON.")
    return parser.parse_args()


def build_launch_eval_payload(
    *,
    manifest: dict[str, Any],
    manifest_dir: Path,
    min_overlap_ratio: float = DEFAULT_MIN_OVERLAP_RATIO,
    allow_unlabeled_predictions: bool = False,
) -> dict[str, Any]:
    entries = manifest.get("cases")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must contain a non-empty cases array.")

    cases: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"Manifest case {index} must be an object.")
        entry = manifest_case_entry(raw_entry, index, manifest_dir)
        payload = build_eval_payload(
            analysis=load_json(entry.analysis_path),
            labels=load_json(entry.labels_path),
            case_id=entry.case_id,
            selected_team_id=entry.selected_team_id,
            confidence_threshold=entry.confidence_threshold,
            min_overlap_ratio=min_overlap_ratio,
            allow_unlabeled_predictions=allow_unlabeled_predictions or entry.allow_unlabeled_predictions,
        )
        cases.extend(payload.get("cases", []))

    return {
        "schemaVersion": "team-highlight-eval-v1",
        "source": "real_cloud_analysis_with_manual_labels",
        "cases": cases,
    }


def build_label_status(*, manifest: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    entries = manifest.get("cases")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must contain a non-empty cases array.")

    case_statuses: list[dict[str, Any]] = []
    total_clips = 0
    complete_clips = 0
    missing_field_counts: dict[str, int] = {
        "needsLabel=false": 0,
        "reviewedByHuman=true": 0,
        "expected.teamId": 0,
        "expected.isHighlight": 0,
        "expected.eventType": 0,
        "expected.outcome": 0,
    }
    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"Manifest case {index} must be an object.")
        entry = manifest_case_entry(raw_entry, index, manifest_dir)
        labels = load_json(entry.labels_path)
        clips = [clip for clip in labels.get("clips", []) if isinstance(clip, dict)]
        case_missing_field_counts: dict[str, int] = {}
        incomplete_examples: list[dict[str, Any]] = []
        case_complete = 0
        for clip_index, clip in enumerate(clips):
            missing_fields = manual_label_completion_missing_fields(clip)
            if missing_fields:
                for field in missing_fields:
                    missing_field_counts[field] = missing_field_counts.get(field, 0) + 1
                    case_missing_field_counts[field] = case_missing_field_counts.get(field, 0) + 1
                if len(incomplete_examples) < 5:
                    incomplete_examples.append(
                        {
                            "labelId": string_or_none(clip.get("labelId") or clip.get("id") or clip.get("predictionClipId")) or f"clip_{clip_index}",
                            "missingFields": missing_fields,
                        }
                    )
            else:
                case_complete += 1

        total_clips += len(clips)
        complete_clips += case_complete
        case_statuses.append(
            {
                "caseId": entry.case_id or string_or_none(labels.get("caseId")) or f"case_{index + 1}",
                "labelsPath": str(entry.labels_path),
                "clipCount": len(clips),
                "completeClipCount": case_complete,
                "incompleteClipCount": len(clips) - case_complete,
                "missingFieldCounts": dict(sorted(case_missing_field_counts.items())),
                "incompleteExamples": incomplete_examples,
            }
        )

    incomplete_clips = total_clips - complete_clips
    launch_evidence_eligible = incomplete_clips == 0
    warnings = []
    if not launch_evidence_eligible:
        warnings.append(
            "Manual labels are not launch evidence until every clip has needsLabel=false, "
            "reviewedByHuman=true, and required expected fields."
        )
    return {
        "schemaVersion": "team-highlight-label-status-v1",
        "status": "complete" if incomplete_clips == 0 else "incomplete",
        "launchEvidenceEligible": launch_evidence_eligible,
        "warnings": warnings,
        "caseCount": len(case_statuses),
        "clipCount": total_clips,
        "completeClipCount": complete_clips,
        "incompleteClipCount": incomplete_clips,
        "missingFieldCounts": dict(sorted(missing_field_counts.items())),
        "cases": case_statuses,
    }


def print_label_status(status_payload: dict[str, Any]) -> None:
    print(f"status={status_payload['status']}")
    print(f"launchEvidenceEligible={str(status_payload.get('launchEvidenceEligible', False)).lower()}")
    for warning in status_payload.get("warnings", []):
        print(f"warning={warning}")
    print(f"cases={status_payload['caseCount']}")
    print(f"clips={status_payload['completeClipCount']} complete / {status_payload['clipCount']} total")
    if status_payload["missingFieldCounts"]:
        print("missing fields:")
        for field, count in status_payload["missingFieldCounts"].items():
            print(f"- {field}: {count}")
    for case in status_payload["cases"]:
        print(
            f"- {case['caseId']}: {case['completeClipCount']} complete / {case['clipCount']} total "
            f"({case['incompleteClipCount']} incomplete)"
        )


def print_incomplete_label_status(status_payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(
            json.dumps(
                {
                    "schemaVersion": "team-highlight-launch-report-build-v1",
                    "status": "blocked",
                    "reason": "manual_labels_incomplete",
                    "message": "Finish human review before building a launch accuracy report.",
                    "labelStatus": status_payload,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    print("status=blocked")
    print("reason=manual_labels_incomplete")
    print("Finish human review before building a launch accuracy report.")
    print_label_status(status_payload)


class ManifestCaseEntry:
    def __init__(
        self,
        *,
        analysis_path: Path,
        labels_path: Path,
        case_id: str | None,
        selected_team_id: str | None,
        confidence_threshold: float | None,
        allow_unlabeled_predictions: bool,
    ) -> None:
        self.analysis_path = analysis_path
        self.labels_path = labels_path
        self.case_id = case_id
        self.selected_team_id = selected_team_id
        self.confidence_threshold = confidence_threshold
        self.allow_unlabeled_predictions = allow_unlabeled_predictions


def manifest_case_entry(raw_entry: dict[str, Any], index: int, manifest_dir: Path) -> ManifestCaseEntry:
    analysis_value = first_present(raw_entry, ("analysisResult", "analysisResultPath", "analysisPath", "analysis"))
    labels_value = first_present(raw_entry, ("labels", "labelsPath", "manualLabels", "manualLabelsPath"))
    if not analysis_value:
        raise ValueError(f"Manifest case {index} is missing analysisResult.")
    if not labels_value:
        raise ValueError(f"Manifest case {index} is missing labels.")
    return ManifestCaseEntry(
        analysis_path=resolve_manifest_path(analysis_value, manifest_dir),
        labels_path=resolve_manifest_path(labels_value, manifest_dir),
        case_id=string_or_none(raw_entry.get("caseId")),
        selected_team_id=string_or_none(raw_entry.get("selectedTeamId")),
        confidence_threshold=number_or_none(raw_entry.get("confidenceThreshold")),
        allow_unlabeled_predictions=bool(raw_entry.get("allowUnlabeledPredictions", False)),
    )


def first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def resolve_manifest_path(value: Any, manifest_dir: Path) -> Path:
    path = Path(str(value))
    if not path.is_absolute():
        path = manifest_dir / path
    return path.resolve()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
