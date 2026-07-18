#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_ARTIFACTS_DIR = Path("artifacts")
LABEL_STATUS_GLOB = "team_highlight_labeling_bundle*/label_status.json"
REPORT_GLOB = "team_highlight_labeling_bundle*/team_highlight_accuracy_report.json"


def main() -> int:
    args = parse_args()
    artifacts_dir = Path(args.artifacts_dir).expanduser().resolve()
    summary = build_accuracy_gate_summary(artifacts_dir)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_human_summary(summary)
    return 0 if summary["status"] == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize local HoopClips team/highlight accuracy gate artifacts. "
            "This is status reporting only; it does not mark labels reviewed or weaken launch thresholds."
        )
    )
    parser.add_argument(
        "--artifacts-dir",
        default=str(DEFAULT_ARTIFACTS_DIR),
        help="Directory containing ignored/generated accuracy artifacts. Defaults to ./artifacts.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def build_accuracy_gate_summary(artifacts_dir: Path) -> dict[str, Any]:
    label_statuses = [label_status_summary(path, artifacts_dir) for path in sorted(artifacts_dir.glob(LABEL_STATUS_GLOB))]
    reports = [accuracy_report_summary(path, artifacts_dir) for path in sorted(artifacts_dir.glob(REPORT_GLOB))]

    eligible_label_statuses = [item for item in label_statuses if item.get("launchEvidenceEligible") is True]
    passing_reports = [item for item in reports if item.get("status") == "pass"]
    best_review_bundle = best_label_status(label_statuses)
    best_report = best_accuracy_report(reports)

    blockers: list[str] = []
    if not artifacts_dir.exists():
        blockers.append("artifacts_dir_missing")
    if not label_statuses:
        blockers.append("no_label_status_files")
    elif not eligible_label_statuses:
        blockers.append("manual_labels_incomplete")
    if not reports:
        blockers.append("no_accuracy_reports")
    elif not passing_reports:
        blockers.append("no_passing_launch_grade_report")

    status = "pass" if passing_reports and eligible_label_statuses else "blocked"
    return {
        "schemaVersion": "team-highlight-accuracy-gate-summary-v1",
        "status": status,
        "artifactsDir": str(artifacts_dir),
        "blockers": blockers,
        "labelStatusCount": len(label_statuses),
        "accuracyReportCount": len(reports),
        "bestReviewBundle": best_review_bundle,
        "bestAccuracyReport": best_report,
        "labelStatuses": label_statuses,
        "accuracyReports": reports,
        "nextActions": next_actions(blockers, best_review_bundle, best_report),
    }


def label_status_summary(path: Path, artifacts_dir: Path) -> dict[str, Any]:
    payload = load_json(path)
    return {
        "path": relative_path(path, artifacts_dir),
        "status": string_or_none(payload.get("status")) or "unknown",
        "launchEvidenceEligible": payload.get("launchEvidenceEligible") is True,
        "caseCount": int_or_zero(payload.get("caseCount")),
        "clipCount": int_or_zero(payload.get("clipCount")),
        "completeClipCount": int_or_zero(payload.get("completeClipCount")),
        "incompleteClipCount": int_or_zero(payload.get("incompleteClipCount")),
        "missingFieldCounts": payload.get("missingFieldCounts") if isinstance(payload.get("missingFieldCounts"), dict) else {},
    }


def accuracy_report_summary(path: Path, artifacts_dir: Path) -> dict[str, Any]:
    payload = load_json(path)
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    failures = payload.get("failures") if isinstance(payload.get("failures"), list) else []
    return {
        "path": relative_path(path, artifacts_dir),
        "status": string_or_none(payload.get("status")) or "unknown",
        "caseCount": int_or_zero(metrics.get("caseCount")),
        "clipCount": int_or_zero(metrics.get("clipCount")),
        "selectedTeamPrecision": metrics.get("selectedTeamPrecision"),
        "highlightPrecision": metrics.get("highlightPrecision"),
        "shotOutcomeEvidenceQuality": metrics.get("shotOutcomeEvidenceQuality"),
        "inputSource": string_or_none(evidence.get("inputSource")),
        "distinctVideoCount": int_or_zero(evidence.get("distinctVideoCount")),
        "failureCount": len(failures),
        "failures": [str(item) for item in failures[:8]],
    }


def best_label_status(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    return max(items, key=lambda item: (int_or_zero(item.get("completeClipCount")), int_or_zero(item.get("clipCount"))))


def best_accuracy_report(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    return min(items, key=lambda item: (item.get("status") != "pass", int_or_zero(item.get("failureCount"))))


def next_actions(blockers: list[str], best_review_bundle: dict[str, Any] | None, best_report: dict[str, Any] | None) -> list[str]:
    actions: list[str] = []
    if "artifacts_dir_missing" in blockers:
        actions.append("Generate or restore the ignored local accuracy artifacts directory.")
    if "no_label_status_files" in blockers:
        actions.append("Prepare a labeling bundle with scripts/prepare_team_highlight_labeling_bundle.py.")
    if "manual_labels_incomplete" in blockers:
        if best_review_bundle:
            actions.append(
                "Finish human review for "
                f"{best_review_bundle['path']} "
                f"({best_review_bundle['incompleteClipCount']} clips remaining)."
            )
        else:
            actions.append("Finish human review for every label bundle clip.")
    if "no_accuracy_reports" in blockers:
        actions.append("Build a launch accuracy report with scripts/build_launch_team_accuracy_report.py after labels are complete.")
    if "no_passing_launch_grade_report" in blockers:
        if best_report:
            actions.append(
                "Use the current failing report to target more real cases or fix labels; "
                f"{best_report['failureCount']} threshold failure(s) remain in {best_report['path']}."
            )
        else:
            actions.append("Build and evaluate a launch-grade report with default thresholds.")
    if not actions:
        actions.append("Pass the report path to scripts/submission_readiness_preflight.py with --team-accuracy-report.")
    return actions


def print_human_summary(summary: dict[str, Any]) -> None:
    print(f"status={summary['status']}")
    print(f"artifactsDir={summary['artifactsDir']}")
    print(f"labelStatusCount={summary['labelStatusCount']}")
    print(f"accuracyReportCount={summary['accuracyReportCount']}")
    if summary["blockers"]:
        print("blockers:")
        for blocker in summary["blockers"]:
            print(f"- {blocker}")
    best_review_bundle = summary.get("bestReviewBundle")
    if best_review_bundle:
        print(
            "bestReviewBundle="
            f"{best_review_bundle['path']} "
            f"({best_review_bundle['completeClipCount']}/{best_review_bundle['clipCount']} complete)"
        )
    best_report = summary.get("bestAccuracyReport")
    if best_report:
        print(
            "bestAccuracyReport="
            f"{best_report['path']} "
            f"(status={best_report['status']}, failures={best_report['failureCount']})"
        )
    print("nextActions:")
    for action in summary["nextActions"]:
        print(f"- {action}")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_path(path: Path, artifacts_dir: Path) -> str:
    try:
        return str(path.relative_to(artifacts_dir))
    except ValueError:
        return str(path)


def string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def int_or_zero(value: Any) -> int:
    return value if isinstance(value, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
