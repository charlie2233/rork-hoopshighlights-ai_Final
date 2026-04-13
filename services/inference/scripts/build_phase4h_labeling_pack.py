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
DEFAULT_SEED_QUEUE = Path("services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue.csv")
DEFAULT_NORMALIZED_QUEUE = Path(
    "services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue_normalized.csv"
)
DEFAULT_EXPANDED_QUEUE = Path(
    "services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue_expanded.csv"
)
DEFAULT_PROGRESS_JSON = Path(
    "services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_labeling_progress_summary.json"
)
DEFAULT_PROGRESS_DOC = Path("docs/phase4h_labeling_progress_report.md")
DEFAULT_SHADOW_REPORTS = (
    Path("services/inference/evals/phase4h_staging_eval/shadow_eval_report.json"),
    Path("services/inference/evals/phase4h_smoke/shadow_eval_report.json"),
    Path("services/inference/evals/phase4h_acceptor_smoke/shadow_eval_report.json"),
)
DEFAULT_AUDIT_REPORTS = (
    Path("services/inference/evals/phase4h_staging_eval/phase4h_audit_queue.json"),
)

REVIEWER_FIELDS = (
    "reviewer_split_other_bucket",
    "reviewer_manual_audit_label",
    "reviewer_shot_attempt",
    "reviewer_outcome",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seed_rows = list(load_seed_queue(args.seed_queue))
    audit_by_clip = load_audit_rows(args.audit_report)
    normalized = normalize_seed_queue(seed_rows, audit_by_clip=audit_by_clip)
    expanded = expand_queue(normalized, args.shadow_report, audit_by_clip=audit_by_clip)
    progress = progress_summary(normalized=normalized, expanded=expanded)

    write_csv(args.normalized_output, normalized)
    write_csv(args.expanded_output, expanded)
    write_json(args.progress_json, progress)
    write_text(args.progress_doc, render_progress_report(progress))

    print(args.normalized_output)
    print(args.expanded_output)
    print(args.progress_json)
    print(args.progress_doc)
    print(json.dumps(progress["expanded"], indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reviewer-ready Phase 4h hard-negative labeling pack.")
    parser.add_argument("--seed-queue", type=Path, default=DEFAULT_SEED_QUEUE)
    parser.add_argument("--shadow-report", type=Path, action="append", default=list(DEFAULT_SHADOW_REPORTS))
    parser.add_argument("--audit-report", type=Path, action="append", default=list(DEFAULT_AUDIT_REPORTS))
    parser.add_argument("--normalized-output", type=Path, default=DEFAULT_NORMALIZED_QUEUE)
    parser.add_argument("--expanded-output", type=Path, default=DEFAULT_EXPANDED_QUEUE)
    parser.add_argument("--progress-json", type=Path, default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--progress-doc", type=Path, default=DEFAULT_PROGRESS_DOC)
    return parser.parse_args(argv)


def load_seed_queue(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def load_audit_rows(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    audit_by_clip: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("items") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            clip_id = str(item.get("clipId") or "")
            if not clip_id:
                continue
            audit_by_clip[clip_id] = {
                **item,
                "sourceArtifactPath": str(path),
            }
    return audit_by_clip


def normalize_seed_queue(
    rows: list[dict[str, Any]],
    *,
    audit_by_clip: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = [
        normalized_row_from_seed(row, audit_by_clip=audit_by_clip)
        for row in rows
    ]
    return sorted_rows(normalized)


def normalized_row_from_seed(row: dict[str, Any], *, audit_by_clip: dict[str, dict[str, Any]]) -> dict[str, Any]:
    clip_id = str(row.get("clipId") or "")
    audit = audit_by_clip.get(clip_id, {})
    source_batch = str(row.get("datasetSource") or "unknown")
    candidate_bucket = candidate_bucket_for_seed(row)
    candidate_reason = candidate_reason_for_seed(row, audit=audit)
    return base_labeling_row(
        row_id=f"seed:{row.get('queueId') or clip_id}",
        queue_source="seed_queue",
        source_artifact_path=source_artifact_for_batch(source_batch),
        supporting_audit_artifact_path=str(audit.get("sourceArtifactPath") or ""),
        source_batch=source_batch,
        batch_type=batch_type_for(source_batch, row.get("queueType")),
        review_task_type=str(row.get("queueType") or "hard_negative_bucket_assignment"),
        clip_id=clip_id,
        candidate_bucket=candidate_bucket,
        candidate_reason=candidate_reason,
        source_domain=row.get("sourceDomain"),
        job_id=row.get("jobId"),
        request_id=row.get("requestId"),
        upload_trace_id=row.get("uploadTraceId"),
        inference_attempt_id=row.get("inferenceAttemptId"),
        model_version=row.get("modelVersion"),
        predicted_flat_label=row.get("predictedFlatLabel"),
        predicted_event_family=row.get("predictedEventFamily"),
        predicted_outcome=row.get("outcome"),
        predicted_shot_subtype=row.get("shotSubtype"),
        proposal_accepted=row.get("proposalAccepted"),
        family_gate_open=row.get("familyGateOpen"),
        shot_head_invoked=row.get("shotHeadInvoked"),
        acceptance_score=row.get("acceptanceScore"),
        calibrated_acceptance_probability=row.get("calibratedAcceptanceProbability"),
        energy_score=row.get("energyScore"),
        artifact_split_other_bucket=first_present(row.get("existingSplitOtherBucket"), audit.get("splitOtherBucket")),
        artifact_manual_audit_label=first_present(row.get("existingManualAuditLabel"), audit.get("manualAuditLabel")),
        expected_event_family=audit.get("expectedEventFamily"),
        expected_outcome=audit.get("expectedOutcome"),
        expected_shot_subtype=audit.get("expectedShotSubtype"),
        priority_score=row.get("priorityScore"),
    )


def expand_queue(
    normalized: list[dict[str, Any]],
    shadow_reports: Iterable[Path],
    *,
    audit_by_clip: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_key = {dedupe_key(row): row for row in normalized}
    for path in shadow_reports:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        clips = payload.get("clips") if isinstance(payload, dict) else None
        if not isinstance(clips, list):
            continue
        source_batch = source_batch_for_shadow_report(path)
        for clip in clips:
            if not isinstance(clip, dict) or not should_mine_clip(clip):
                continue
            row = normalized_row_from_clip(
                clip,
                source_batch=source_batch,
                source_artifact_path=str(path),
                audit_by_clip=audit_by_clip,
            )
            key = dedupe_key(row)
            if key in rows_by_key:
                rows_by_key[key] = merge_artifact_fields(rows_by_key[key], row)
            else:
                rows_by_key[key] = row
    return sorted_rows(list(rows_by_key.values()))


def normalized_row_from_clip(
    clip: dict[str, Any],
    *,
    source_batch: str,
    source_artifact_path: str,
    audit_by_clip: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    clip_id = str(clip.get("clipId") or "")
    audit = audit_by_clip.get(clip_id, {})
    candidate_bucket = candidate_bucket_for_clip(clip, audit=audit)
    candidate_reason = candidate_reason_for_clip(clip, audit=audit)
    return base_labeling_row(
        row_id=f"expanded:{source_batch}:{clip_id}:{candidate_bucket}",
        queue_source="mined_eval_artifact",
        source_artifact_path=source_artifact_path,
        supporting_audit_artifact_path=str(audit.get("sourceArtifactPath") or ""),
        source_batch=source_batch,
        batch_type=batch_type_for(source_batch, None),
        review_task_type=review_task_type_for_candidate(candidate_bucket),
        clip_id=clip_id,
        candidate_bucket=candidate_bucket,
        candidate_reason=candidate_reason,
        source_domain=clip.get("sourceDomain"),
        job_id=clip.get("jobId"),
        request_id=clip.get("requestId"),
        upload_trace_id=clip.get("uploadTraceId"),
        inference_attempt_id=clip.get("inferenceAttemptId"),
        model_version=clip.get("modelVersion"),
        predicted_flat_label=clip.get("flatLabel"),
        predicted_event_family=clip.get("eventFamily"),
        predicted_outcome=clip.get("outcome"),
        predicted_shot_subtype=clip.get("shotSubtype"),
        proposal_accepted=clip.get("proposalAccepted"),
        family_gate_open=clip.get("familyGateOpen"),
        shot_head_invoked=clip.get("shotHeadInvoked"),
        acceptance_score=first_present(clip.get("proposalAcceptanceRawScore"), clip.get("proposalScore")),
        calibrated_acceptance_probability=clip.get("proposalAcceptanceProbability"),
        energy_score=clip.get("proposalEnergyScore"),
        artifact_split_other_bucket=first_present(clip.get("otherBucket"), audit.get("splitOtherBucket")),
        artifact_manual_audit_label=first_present(clip.get("manualAuditLabel"), audit.get("manualAuditLabel")),
        expected_event_family=first_present(clip.get("expectedEventFamily"), audit.get("expectedEventFamily")),
        expected_outcome=first_present(clip.get("expectedOutcome"), audit.get("expectedOutcome")),
        expected_shot_subtype=first_present(clip.get("expectedShotSubtype"), audit.get("expectedShotSubtype")),
        priority_score=priority_score_for_clip(clip, audit=audit),
    )


def base_labeling_row(**kwargs: Any) -> dict[str, Any]:
    row = {
        "row_id": kwargs["row_id"],
        "clip_id": kwargs["clip_id"],
        "source_batch": kwargs["source_batch"],
        "candidate_bucket": kwargs["candidate_bucket"],
        "candidate_reason": kwargs["candidate_reason"],
        "reviewer_split_other_bucket": "",
        "reviewer_manual_audit_label": "",
        "reviewer_shot_attempt": "",
        "reviewer_outcome": "",
        "review_status": "needs_review",
        "reviewed_by": "",
        "qa_status": "not_started",
        "notes": "",
        "queue_source": kwargs["queue_source"],
        "source_artifact_path": kwargs["source_artifact_path"],
        "supporting_audit_artifact_path": kwargs["supporting_audit_artifact_path"],
        "batch_type": kwargs["batch_type"],
        "review_task_type": kwargs["review_task_type"],
        "source_domain": kwargs.get("source_domain"),
        "job_id": kwargs.get("job_id"),
        "request_id": kwargs.get("request_id"),
        "upload_trace_id": kwargs.get("upload_trace_id"),
        "inference_attempt_id": kwargs.get("inference_attempt_id"),
        "model_version": kwargs.get("model_version"),
        "predicted_flat_label": kwargs.get("predicted_flat_label"),
        "predicted_event_family": kwargs.get("predicted_event_family"),
        "predicted_outcome": kwargs.get("predicted_outcome"),
        "predicted_shot_subtype": kwargs.get("predicted_shot_subtype"),
        "proposal_accepted": kwargs.get("proposal_accepted"),
        "family_gate_open": kwargs.get("family_gate_open"),
        "shot_head_invoked": kwargs.get("shot_head_invoked"),
        "acceptance_score": kwargs.get("acceptance_score"),
        "calibrated_acceptance_probability": kwargs.get("calibrated_acceptance_probability"),
        "energy_score": kwargs.get("energy_score"),
        "artifact_split_other_bucket": kwargs.get("artifact_split_other_bucket"),
        "artifact_manual_audit_label": kwargs.get("artifact_manual_audit_label"),
        "expected_event_family": kwargs.get("expected_event_family"),
        "expected_outcome": kwargs.get("expected_outcome"),
        "expected_shot_subtype": kwargs.get("expected_shot_subtype"),
        "priority_score": kwargs.get("priority_score"),
    }
    for reviewer_field in REVIEWER_FIELDS:
        row[reviewer_field] = ""
    return {key: stringify(value) for key, value in row.items()}


def should_mine_clip(clip: dict[str, Any]) -> bool:
    predicted_other = normalize(clip.get("eventFamily")) == "other"
    predicted_highlight = normalize(clip.get("flatLabel")) == "highlight"
    accepted = as_bool(clip.get("proposalAccepted"))
    likely_shot_attempt = normalize(clip.get("eventFamily")) == "shot_attempt" or normalize(clip.get("expectedEventFamily")) == "shot_attempt"
    return predicted_other or predicted_highlight or (accepted and likely_shot_attempt)


def candidate_bucket_for_seed(row: dict[str, Any]) -> str:
    queue_type = normalize(row.get("queueType"))
    if queue_type == "accepted_proposal_light_label":
        return "accepted_proposal_light_label"
    if normalize(row.get("existingManualAuditLabel")) == "real_event_missed_by_model":
        return "possible_real_event_miss"
    return "|".join(HARD_NEGATIVE_BUCKETS)


def candidate_bucket_for_clip(clip: dict[str, Any], *, audit: dict[str, Any]) -> str:
    if as_bool(clip.get("proposalAccepted")) and normalize(clip.get("eventFamily")) == "shot_attempt":
        return "accepted_proposal_light_label"
    if normalize(audit.get("manualAuditLabel")) == "real_event_missed_by_model":
        return "possible_real_event_miss"
    if normalize(clip.get("expectedEventFamily")) == "shot_attempt" and normalize(clip.get("eventFamily")) == "other":
        return "possible_real_event_miss"
    return "|".join(HARD_NEGATIVE_BUCKETS)


def candidate_reason_for_seed(row: dict[str, Any], *, audit: dict[str, Any]) -> str:
    reasons = compact(
        [
            row.get("priorityReason"),
            f"artifact_manual_audit={audit.get('manualAuditLabel')}" if audit.get("manualAuditLabel") else None,
            f"artifact_split_other={first_present(row.get('existingSplitOtherBucket'), audit.get('splitOtherBucket'))}"
            if first_present(row.get("existingSplitOtherBucket"), audit.get("splitOtherBucket"))
            else None,
            "reviewer_fields_blank",
        ]
    )
    return "|".join(reasons)


def candidate_reason_for_clip(clip: dict[str, Any], *, audit: dict[str, Any]) -> str:
    reasons = []
    if normalize(clip.get("flatLabel")) == "highlight":
        reasons.append("predicted_highlight")
    if normalize(clip.get("eventFamily")) == "other":
        reasons.append("predicted_event_family_other")
    if as_bool(clip.get("proposalAccepted")):
        reasons.append("proposal_accepted")
    if as_bool(clip.get("familyGateOpen")):
        reasons.append("family_gate_open")
    if as_bool(clip.get("shotHeadInvoked")):
        reasons.append("shot_head_invoked")
    if normalize(clip.get("expectedEventFamily")) == "shot_attempt":
        reasons.append("artifact_expected_shot_attempt")
    if audit.get("manualAuditLabel"):
        reasons.append(f"artifact_manual_audit={audit.get('manualAuditLabel')}")
    if first_present(clip.get("otherBucket"), audit.get("splitOtherBucket")):
        reasons.append(f"artifact_split_other={first_present(clip.get('otherBucket'), audit.get('splitOtherBucket'))}")
    reasons.append("reviewer_fields_blank")
    return "|".join(reasons)


def priority_score_for_clip(clip: dict[str, Any], *, audit: dict[str, Any]) -> float:
    score = 0.2
    if normalize(clip.get("flatLabel")) == "highlight":
        score += 0.2
    if normalize(clip.get("eventFamily")) == "other":
        score += 0.2
    if as_bool(clip.get("proposalAccepted")):
        score += 0.15
    if audit.get("manualAuditLabel"):
        score += 0.1
    acceptance_score = first_present(clip.get("proposalAcceptanceRawScore"), clip.get("proposalScore"))
    if acceptance_score not in (None, ""):
        score += min(float(acceptance_score), 1.0) * 0.15
    return round(min(score, 1.0), 4)


def source_batch_for_shadow_report(path: Path) -> str:
    parts = set(path.parts)
    if "phase4h_staging_eval" in parts:
        return "phase4h_staging_eval_63clip"
    if "phase4h_acceptor_smoke" in parts:
        return "phase4h_acceptor_smoke_15clip"
    if "phase4h_smoke" in parts:
        return "phase4h_gate_unblock_smoke_18clip"
    return path.parent.name


def source_artifact_for_batch(source_batch: str) -> str:
    if source_batch == "phase4h_staging_eval_63clip":
        return "services/inference/evals/phase4h_staging_eval/shadow_eval_report.json"
    if source_batch == "phase4h_gate_unblock_smoke_18clip":
        return "services/inference/evals/phase4h_smoke/shadow_eval_report.json"
    if source_batch == "phase4h_acceptor_smoke_15clip":
        return "services/inference/evals/phase4h_acceptor_smoke/shadow_eval_report.json"
    return ""


def batch_type_for(source_batch: str, queue_type: Any) -> str:
    if normalize(queue_type) == "accepted_proposal_light_label":
        return "accepted_proposal_review"
    if "staging" in source_batch:
        return "staging"
    if "smoke" in source_batch:
        return "smoke"
    return "artifact"


def review_task_type_for_candidate(candidate_bucket: str) -> str:
    if candidate_bucket == "accepted_proposal_light_label":
        return "accepted_proposal_review"
    if candidate_bucket == "possible_real_event_miss":
        return "model_miss_review"
    return "hard_negative_bucket_assignment"


def merge_artifact_fields(existing: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    merged = dict(existing)
    for key in ("supporting_audit_artifact_path", "artifact_manual_audit_label", "artifact_split_other_bucket"):
        if not merged.get(key) and incoming.get(key):
            merged[key] = incoming[key]
    existing_reasons = set(filter(None, merged.get("candidate_reason", "").split("|")))
    incoming_reasons = set(filter(None, incoming.get("candidate_reason", "").split("|")))
    merged["candidate_reason"] = "|".join(sorted(existing_reasons | incoming_reasons))
    return merged


def progress_summary(*, normalized: list[dict[str, str]], expanded: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "generatedAt": "2026-04-13",
        "hardNegativeBuckets": list(HARD_NEGATIVE_BUCKETS),
        "normalized": summarize_rows(normalized),
        "expanded": summarize_rows(expanded),
        "recommendation": recommendation_for(summarize_rows(expanded)),
    }


def summarize_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    confirmed_by_bucket = {
        bucket: sum(1 for row in rows if row.get("reviewer_split_other_bucket") == bucket)
        for bucket in HARD_NEGATIVE_BUCKETS
    }
    candidate_by_bucket = Counter(row.get("candidate_bucket", "") for row in rows)
    candidate_option_counts = {
        bucket: sum(1 for row in rows if bucket in row.get("candidate_bucket", "").split("|"))
        for bucket in HARD_NEGATIVE_BUCKETS
    }
    accepted_count = candidate_by_bucket.get("accepted_proposal_light_label", 0)
    remaining = sum(1 for row in rows if row.get("review_status") != "reviewed")
    return {
        "totalRows": len(rows),
        "uniqueClipCount": len({row.get("clip_id", "") for row in rows if row.get("clip_id")}),
        "bySourceBatch": dict(sorted(Counter(row.get("source_batch", "") for row in rows).items())),
        "byBatchType": dict(sorted(Counter(row.get("batch_type", "") for row in rows).items())),
        "byCandidateBucket": dict(sorted(candidate_by_bucket.items())),
        "candidateHardNegativeOptionCounts": candidate_option_counts,
        "confirmedRowsByBucket": confirmed_by_bucket,
        "acceptedProposalLightLabelRows": accepted_count,
        "remainingUnlabeledRows": remaining,
        "reviewStatus": dict(sorted(Counter(row.get("review_status", "") for row in rows).items())),
        "qaStatus": dict(sorted(Counter(row.get("qa_status", "") for row in rows).items())),
    }


def recommendation_for(summary: dict[str, Any]) -> str:
    confirmed = summary["confirmedRowsByBucket"]
    missing = [bucket for bucket, count in confirmed.items() if count == 0]
    if missing:
        return "continue labeling"
    return "approve acceptor retrain prep"


def render_progress_report(progress: dict[str, Any]) -> str:
    normalized = progress["normalized"]
    expanded = progress["expanded"]
    lines = [
        "# Phase 4h Labeling Progress Report",
        "",
        "## Scope",
        "",
        "- Branch: `codex/phase4h-hard-negative-labeling-sprint`.",
        "- Purpose: prepare labels for a future acceptor retrain; no retraining is performed in this branch.",
        "- Truth-label policy: reviewer fields are intentionally blank until human review. Artifact-derived hints remain in `artifact_*` columns only.",
        "",
        "## Queue Outputs",
        "",
        "- Normalized seed queue: `services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue_normalized.csv`.",
        "- Expanded queue: `services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue_expanded.csv`.",
        "- Machine-readable summary: `services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_labeling_progress_summary.json`.",
        "",
        "## Counts",
        "",
        f"- Normalized seed rows: `{normalized['totalRows']}`.",
        f"- Expanded rows: `{expanded['totalRows']}` across `{expanded['uniqueClipCount']}` unique clips.",
        "- Row count can exceed clip count because accepted-proposal review and model-miss review are separate review tasks.",
        f"- Expanded source batches: `{json.dumps(expanded['bySourceBatch'], sort_keys=True)}`.",
        f"- Expanded candidate buckets: `{json.dumps(expanded['byCandidateBucket'], sort_keys=True)}`.",
        f"- Accepted-proposal light-label rows: `{expanded['acceptedProposalLightLabelRows']}`.",
        f"- Remaining unlabeled rows: `{expanded['remainingUnlabeledRows']}`.",
        "",
        "## Candidate Hard-Negative Option Counts",
        "",
    ]
    for bucket in HARD_NEGATIVE_BUCKETS:
        lines.append(f"- {bucket}: `{expanded['candidateHardNegativeOptionCounts'][bucket]}` candidate rows.")
    lines.extend(
        [
            "",
            "## Confirmed Hard-Negative Counts",
            "",
        ]
    )
    for bucket in HARD_NEGATIVE_BUCKETS:
        lines.append(f"- {bucket}: `{expanded['confirmedRowsByBucket'][bucket]}` confirmed rows.")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- `{progress['recommendation']}`.",
            "- Rationale: confirmed hard-negative counts remain zero, so this pack unlocks review, not retraining.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sorted_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            row.get("candidate_bucket") != "|".join(HARD_NEGATIVE_BUCKETS),
            row.get("candidate_bucket") != "possible_real_event_miss",
            row.get("source_batch", ""),
            -float(row.get("priority_score") or 0.0),
            row.get("clip_id", ""),
        ),
    )


def dedupe_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("clip_id", ""),
        row.get("source_batch", ""),
        row.get("candidate_bucket", ""),
    )


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return ""


def compact(values: Iterable[Any]) -> list[str]:
    return [str(value) for value in values if value not in (None, "")]


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return normalize(value) == "true"


if __name__ == "__main__":
    raise SystemExit(main())
