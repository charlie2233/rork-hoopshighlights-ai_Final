#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.build_team_highlight_eval_payload import DEFAULT_MIN_OVERLAP_RATIO, build_eval_payload, load_json, number_or_none, string_or_none
from scripts.evaluate_team_highlight_accuracy import evaluate_accuracy


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    eval_payload = build_launch_eval_payload(
        manifest=load_json(manifest_path),
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
