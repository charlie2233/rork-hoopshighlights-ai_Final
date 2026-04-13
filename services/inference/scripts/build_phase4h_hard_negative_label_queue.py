from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


HARD_NEGATIVE_BUCKETS = (
    "dead_ball",
    "replay_or_reaction",
    "setup",
    "true_negative_non_event",
)
DEFAULT_DATASET = Path("services/inference/evals/phase4h_acceptor_coverage_lift/acceptance_calibration_dataset.jsonl")
DEFAULT_SHADOW_REPORTS = (
    Path("services/inference/evals/phase4h_acceptor_smoke/shadow_eval_report.json"),
)
DEFAULT_QUEUE = Path("services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue.csv")
DEFAULT_DOC = Path("docs/phase4h_hard_negative_labeling_plan.md")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = list(load_jsonl(args.dataset))
    rows.extend(load_shadow_report_rows(args.shadow_report))
    queue_rows = build_label_queue(rows)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_csv.write_text(render_csv(queue_rows), encoding="utf-8")
    args.output_doc.parent.mkdir(parents=True, exist_ok=True)
    args.output_doc.write_text(
        render_labeling_plan(
            rows=rows,
            queue_rows=queue_rows,
            output_csv=args.output_csv,
        ),
        encoding="utf-8",
    )
    print(args.output_csv)
    print(args.output_doc)
    print(json.dumps(queue_summary(queue_rows), indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 4h hard-negative and accepted-shot labeling queue.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--shadow-report",
        type=Path,
        action="append",
        default=list(DEFAULT_SHADOW_REPORTS),
        help="Optional shadow eval report(s) to append to the labeling queue source rows.",
    )
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--output-doc", type=Path, default=DEFAULT_DOC)
    return parser.parse_args(argv)


def load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def load_shadow_report_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        clips = payload.get("clips")
        if not isinstance(clips, list):
            continue
        dataset_source = dataset_source_for_report(path)
        for clip in clips:
            if isinstance(clip, dict):
                rows.append(row_from_shadow_clip(clip, dataset_source=dataset_source))
    return rows


def dataset_source_for_report(path: Path) -> str:
    parts = set(path.parts)
    if "phase4h_acceptor_smoke" in parts:
        return "phase4h_acceptor_smoke_15clip"
    return path.parent.name or "shadow_eval_report"


def row_from_shadow_clip(clip: dict[str, Any], *, dataset_source: str) -> dict[str, Any]:
    event_family = clip.get("eventFamily")
    acceptance_probability = first_present(
        clip.get("proposalAcceptanceProbability"),
        clip.get("proposalAcceptanceProbabilityCalibrated"),
    )
    return {
        "clipId": clip.get("clipId"),
        "datasetSource": dataset_source,
        "sourceDomain": clip.get("sourceDomain"),
        "jobId": clip.get("jobId"),
        "requestId": clip.get("requestId"),
        "uploadTraceId": clip.get("uploadTraceId"),
        "inferenceAttemptId": clip.get("inferenceAttemptId"),
        "modelVersion": clip.get("modelVersion"),
        "predictedFlatLabel": clip.get("flatLabel"),
        "predictedEventFamily": event_family,
        "eventFamily": event_family,
        "outcome": clip.get("outcome"),
        "shotSubtype": clip.get("shotSubtype"),
        "proposalAccepted": clip.get("proposalAccepted"),
        "familyGateOpen": clip.get("familyGateOpen"),
        "shotHeadInvoked": clip.get("shotHeadInvoked"),
        "acceptanceScore": first_present(clip.get("proposalAcceptanceRawScore"), acceptance_probability),
        "calibratedAcceptanceProbability": acceptance_probability,
        "energyScore": clip.get("proposalEnergyScore"),
        "manualAuditLabel": clip.get("manualAuditLabel"),
        "splitOtherBucket": clip.get("otherBucket"),
        "acceptanceLabel": "unknown",
        "shotAttempt": normalize(event_family) == "shot_attempt",
    }


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def build_label_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for row in rows:
        if should_queue_hard_negative(row):
            queue.append(queue_row(row, queue_type="hard_negative_bucket_assignment"))
        if should_queue_accepted_proposal(row):
            queue.append(queue_row(row, queue_type="accepted_proposal_light_label"))
    queue.sort(
        key=lambda item: (
            item["queueType"] != "hard_negative_bucket_assignment",
            -float(item["priorityScore"]),
            str(item["datasetSource"]),
            str(item["clipId"]),
        )
    )
    return queue


def should_queue_hard_negative(row: dict[str, Any]) -> bool:
    if row.get("acceptanceLabel") == "reject":
        return True
    if row.get("acceptanceLabel") != "unknown":
        return False
    predicted_flat = normalize(row.get("predictedFlatLabel"))
    predicted_family = normalize(row.get("predictedEventFamily"))
    event_family = normalize(row.get("eventFamily"))
    return predicted_flat == "highlight" or predicted_family == "other" or event_family == "other"


def should_queue_accepted_proposal(row: dict[str, Any]) -> bool:
    if not row.get("proposalAccepted"):
        return False
    return bool(row.get("shotAttempt") or normalize(row.get("eventFamily")) == "shot_attempt")


def queue_row(row: dict[str, Any], *, queue_type: str) -> dict[str, Any]:
    hard_negative = queue_type == "hard_negative_bucket_assignment"
    known_bucket = row.get("hardNegativeBucket") if row.get("acceptanceLabel") == "reject" else None
    priority_score = priority(row, queue_type=queue_type)
    return {
        "queueId": f"{queue_type}:{row.get('datasetSource')}:{row.get('clipId')}",
        "queueType": queue_type,
        "clipId": row.get("clipId"),
        "datasetSource": row.get("datasetSource"),
        "sourceDomain": row.get("sourceDomain"),
        "jobId": row.get("jobId"),
        "requestId": row.get("requestId"),
        "uploadTraceId": row.get("uploadTraceId"),
        "inferenceAttemptId": row.get("inferenceAttemptId"),
        "modelVersion": row.get("modelVersion"),
        "predictedFlatLabel": row.get("predictedFlatLabel"),
        "predictedEventFamily": row.get("predictedEventFamily"),
        "eventFamily": row.get("eventFamily"),
        "outcome": row.get("outcome"),
        "shotSubtype": row.get("shotSubtype"),
        "proposalAccepted": row.get("proposalAccepted"),
        "familyGateOpen": row.get("familyGateOpen"),
        "shotHeadInvoked": row.get("shotHeadInvoked"),
        "acceptanceScore": row.get("acceptanceScore"),
        "calibratedAcceptanceProbability": row.get("calibratedAcceptanceProbability"),
        "energyScore": row.get("energyScore"),
        "existingManualAuditLabel": row.get("manualAuditLabel"),
        "existingSplitOtherBucket": row.get("splitOtherBucket"),
        "confirmedHardNegativeBucket": known_bucket,
        "candidateHardNegativeBuckets": "|".join(HARD_NEGATIVE_BUCKETS) if hard_negative and known_bucket is None else known_bucket,
        "manualHardNegativeBucket": "",
        "manualAuditLabel": "",
        "manualShotAttempt": "",
        "manualOutcome": "",
        "manualNotes": "",
        "priorityScore": priority_score,
        "priorityReason": priority_reason(row, queue_type=queue_type),
    }


def priority(row: dict[str, Any], *, queue_type: str) -> float:
    score = 0.2
    if queue_type == "hard_negative_bucket_assignment":
        score += 0.35
    if normalize(row.get("predictedFlatLabel")) == "highlight":
        score += 0.2
    if normalize(row.get("eventFamily")) == "other" or normalize(row.get("predictedEventFamily")) == "other":
        score += 0.2
    if row.get("proposalAccepted"):
        score += 0.1
    acceptance_score = row.get("acceptanceScore")
    if acceptance_score is not None:
        score += min(float(acceptance_score), 1.0) * 0.15
    return round(min(score, 1.0), 4)


def priority_reason(row: dict[str, Any], *, queue_type: str) -> str:
    reasons = [queue_type]
    if normalize(row.get("predictedFlatLabel")) == "highlight":
        reasons.append("predicted_highlight")
    if normalize(row.get("eventFamily")) == "other" or normalize(row.get("predictedEventFamily")) == "other":
        reasons.append("event_family_other")
    if row.get("proposalAccepted"):
        reasons.append("accepted_proposal")
    if row.get("acceptanceLabel") == "unknown":
        reasons.append("needs_human_bucket_assignment")
    return "|".join(reasons)


def render_csv(rows: list[dict[str, Any]]) -> str:
    fieldnames = [
        "queueId",
        "queueType",
        "clipId",
        "datasetSource",
        "sourceDomain",
        "jobId",
        "requestId",
        "uploadTraceId",
        "inferenceAttemptId",
        "modelVersion",
        "predictedFlatLabel",
        "predictedEventFamily",
        "eventFamily",
        "outcome",
        "shotSubtype",
        "proposalAccepted",
        "familyGateOpen",
        "shotHeadInvoked",
        "acceptanceScore",
        "calibratedAcceptanceProbability",
        "energyScore",
        "existingManualAuditLabel",
        "existingSplitOtherBucket",
        "confirmedHardNegativeBucket",
        "candidateHardNegativeBuckets",
        "manualHardNegativeBucket",
        "manualAuditLabel",
        "manualShotAttempt",
        "manualOutcome",
        "manualNotes",
        "priorityScore",
        "priorityReason",
    ]
    from io import StringIO

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def render_labeling_plan(
    *,
    rows: list[dict[str, Any]],
    queue_rows: list[dict[str, Any]],
    output_csv: Path,
) -> str:
    summary = queue_summary(queue_rows)
    confirmed_counts = {bucket: 0 for bucket in HARD_NEGATIVE_BUCKETS}
    for row in rows:
        bucket = row.get("hardNegativeBucket")
        if bucket in confirmed_counts:
            confirmed_counts[bucket] += 1
    lines = [
        "# Phase 4h Hard-Negative Labeling Plan",
        "",
        "## Scope",
        "",
        "- Build labels needed for a future acceptor retrain; do not retrain from this queue yet.",
        "- Do not invent hard-negative labels. Blank manual fields require human review before training use.",
        "- Prioritize clips currently collapsing to `Highlight` / `eventFamily=other`, then accepted proposals that need lightweight shot labels.",
        "",
        "## Queue Artifact",
        "",
        f"- CSV: `{output_csv}`.",
        f"- Total queue rows: `{summary['totalRows']}`.",
        f"- Queue type distribution: `{json.dumps(summary['byQueueType'], sort_keys=True)}`.",
        f"- Candidate hard-negative rows: `{summary['hardNegativeCandidateRows']}`.",
        f"- Accepted proposal light-label rows: `{summary['acceptedProposalRows']}`.",
        "",
        "## Confirmed Hard-Negative Counts",
        "",
        f"- dead_ball: `{confirmed_counts['dead_ball']}`.",
        f"- replay_or_reaction: `{confirmed_counts['replay_or_reaction']}`.",
        f"- setup: `{confirmed_counts['setup']}`.",
        f"- true_negative_non_event: `{confirmed_counts['true_negative_non_event']}`.",
        "",
        "## Manual Review Fields",
        "",
        "- `manualHardNegativeBucket`: one of `dead_ball`, `replay_or_reaction`, `setup`, `true_negative_non_event`, or blank if not a hard negative.",
        "- `manualAuditLabel`: `true_negative_non_event`, `real_event_missed_by_model`, `ambiguous_clip`, or `data_sampling_issue`.",
        "- `manualShotAttempt`: `yes`, `no`, or `uncertain`.",
        "- `manualOutcome`: `made`, `missed`, `blocked`, `uncertain`, or blank when not visible.",
        "",
        "## Stop Rule",
        "",
        "- Do not train a new acceptor until each required hard-negative bucket has confirmed rows and high-scoring unknown clips are resolved.",
    ]
    return "\n".join(lines) + "\n"


def queue_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_type = Counter(str(row.get("queueType")) for row in rows)
    return {
        "totalRows": len(rows),
        "byQueueType": dict(sorted(by_type.items())),
        "hardNegativeCandidateRows": by_type.get("hard_negative_bucket_assignment", 0),
        "acceptedProposalRows": by_type.get("accepted_proposal_light_label", 0),
        "confirmedHardNegativeBuckets": dict(
            sorted(
                Counter(
                    str(row.get("confirmedHardNegativeBucket"))
                    for row in rows
                    if row.get("confirmedHardNegativeBucket")
                ).items()
            )
        ),
    }


def normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


if __name__ == "__main__":
    raise SystemExit(main())
