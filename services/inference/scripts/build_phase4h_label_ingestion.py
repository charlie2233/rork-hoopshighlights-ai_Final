from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


DEFAULT_EXPANDED_QUEUE = Path(
    "services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue_expanded.csv"
)
DEFAULT_OUTPUT_DIR = Path("services/inference/evals/phase4h_acceptor_coverage_lift")
DEFAULT_REVIEW_PACK_01 = DEFAULT_OUTPUT_DIR / "review_pack_01_accepted_proposals.csv"
DEFAULT_REVIEW_PACK_02 = DEFAULT_OUTPUT_DIR / "review_pack_02_hard_negatives_priority.csv"
DEFAULT_REVIEW_PACK_03 = DEFAULT_OUTPUT_DIR / "review_pack_03_remaining_predicted_other.csv"
DEFAULT_CONFIRMED_CSV = DEFAULT_OUTPUT_DIR / "confirmed_phase4h_labels.csv"
DEFAULT_CONFIRMED_JSONL = DEFAULT_OUTPUT_DIR / "confirmed_phase4h_labels.jsonl"
DEFAULT_CONFLICTS_CSV = DEFAULT_OUTPUT_DIR / "conflicts_report.csv"
DEFAULT_TRAINING_SEED_JSONL = DEFAULT_OUTPUT_DIR / "phase4h_acceptor_training_seed.jsonl"
DEFAULT_READINESS_JSON = DEFAULT_OUTPUT_DIR / "phase4h_retrain_readiness_summary.json"
DEFAULT_READINESS_DOC = Path("docs/phase4h_retrain_readiness_report.md")

HARD_NEGATIVE_BUCKETS = (
    "dead_ball",
    "replay_or_reaction",
    "setup",
    "true_negative_non_event",
)
LOCAL_UNLOCK_BARS = {
    "dead_ball": 20,
    "replay_or_reaction": 20,
    "setup": 20,
    "true_negative_non_event": 20,
    "accepted_proposal_light_labels": 25,
}
ROADMAP_TARGET_TAGGED_CLIPS = 300

ALLOWED_SPLIT_OTHER_BUCKETS = {
    "",
    "dead_ball",
    "replay_or_reaction",
    "setup",
    "true_negative_non_event",
    "ambiguous_event",
    "other_true_unknown",
}
ALLOWED_MANUAL_AUDIT_LABELS = {
    "",
    "true_negative_non_event",
    "real_event_missed_by_model",
    "ambiguous_clip",
    "data_sampling_issue",
    "accepted_proposal_valid",
    "accepted_proposal_false_positive",
}
ALLOWED_SHOT_ATTEMPT = {"", "true", "false", "uncertain"}
ALLOWED_OUTCOMES = {"", "made", "missed", "blocked", "uncertain"}
ALLOWED_REVIEW_STATUSES = {"needs_review", "reviewed", "needs_qa", "qa_reviewed", "rejected", "skip"}
ALLOWED_QA_STATUSES = {"not_started", "needs_qa", "passed", "failed", "needs_rework"}

REVIEWER_FIELDS = (
    "reviewer_split_other_bucket",
    "reviewer_manual_audit_label",
    "reviewer_shot_attempt",
    "reviewer_outcome",
)

PACK_COLUMNS = (
    "pack_name",
    "pack_rank",
    "clip_id",
    "row_id",
    "source_batch",
    "candidate_bucket",
    "candidate_reason",
    "reviewer_split_other_bucket",
    "reviewer_manual_audit_label",
    "reviewer_shot_attempt",
    "reviewer_outcome",
    "review_status",
    "reviewed_by",
    "review_timestamp",
    "qa_status",
    "notes",
    "queue_source",
    "source_artifact_path",
    "supporting_audit_artifact_path",
    "batch_type",
    "review_task_type",
    "source_domain",
    "job_id",
    "request_id",
    "upload_trace_id",
    "inference_attempt_id",
    "model_version",
    "predicted_flat_label",
    "predicted_event_family",
    "predicted_outcome",
    "predicted_shot_subtype",
    "proposal_accepted",
    "family_gate_open",
    "shot_head_invoked",
    "acceptance_score",
    "calibrated_acceptance_probability",
    "energy_score",
    "artifact_split_other_bucket",
    "artifact_manual_audit_label",
    "expected_event_family",
    "expected_outcome",
    "expected_shot_subtype",
    "priority_score",
    "pack_priority_reason",
)

CONFIRMED_COLUMNS = PACK_COLUMNS + (
    "duplicate_count",
    "duplicate_row_ids",
    "confirmed_truth_signature",
)

CONFLICT_COLUMNS = (
    "clip_id",
    "conflict_type",
    "row_ids",
    "source_batches",
    "truth_signatures",
    "notes",
)


class LabelIngestionError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode in {"all", "packs"}:
        expanded_rows = load_csv(args.expanded_queue)
        packs = build_review_packs(expanded_rows)
        write_review_packs(packs, args.output_dir)

    if args.mode in {"all", "ingest"}:
        reviewed_pack_paths = args.reviewed_pack or [
            args.output_dir / DEFAULT_REVIEW_PACK_01.name,
            args.output_dir / DEFAULT_REVIEW_PACK_02.name,
            args.output_dir / DEFAULT_REVIEW_PACK_03.name,
        ]
        expanded_rows = load_csv(args.expanded_queue)
        try:
            confirmed_rows, conflicts = ingest_reviewed_rows(load_many_csv(reviewed_pack_paths))
        except LabelIngestionError as error:
            for message in error.errors:
                print(f"label-ingestion-error: {message}", file=sys.stderr)
            return 2
        training_seed = build_training_seed(confirmed_rows)
        readiness = compute_retrain_readiness(
            confirmed_rows=confirmed_rows,
            expanded_rows=expanded_rows,
            conflicts=conflicts,
        )
        write_csv(args.confirmed_csv, confirmed_rows, CONFIRMED_COLUMNS)
        write_jsonl(args.confirmed_jsonl, confirmed_rows)
        write_jsonl(args.training_seed_jsonl, training_seed)
        write_json(args.readiness_json, readiness)
        write_text(args.readiness_doc, render_readiness_report(readiness))
        if conflicts:
            write_csv(args.conflicts_csv, conflicts, CONFLICT_COLUMNS)
        elif args.conflicts_csv.exists():
            args.conflicts_csv.unlink()

    print(json.dumps({"mode": args.mode, "outputDir": str(args.output_dir)}, indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Slice Phase 4h review packs and ingest confirmed reviewer labels."
    )
    parser.add_argument("--mode", choices=("all", "packs", "ingest"), default="all")
    parser.add_argument("--expanded-queue", type=Path, default=DEFAULT_EXPANDED_QUEUE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--reviewed-pack", type=Path, action="append")
    parser.add_argument("--confirmed-csv", type=Path, default=DEFAULT_CONFIRMED_CSV)
    parser.add_argument("--confirmed-jsonl", type=Path, default=DEFAULT_CONFIRMED_JSONL)
    parser.add_argument("--conflicts-csv", type=Path, default=DEFAULT_CONFLICTS_CSV)
    parser.add_argument("--training-seed-jsonl", type=Path, default=DEFAULT_TRAINING_SEED_JSONL)
    parser.add_argument("--readiness-json", type=Path, default=DEFAULT_READINESS_JSON)
    parser.add_argument("--readiness-doc", type=Path, default=DEFAULT_READINESS_DOC)
    return parser.parse_args(argv)


def build_review_packs(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    assigned_clips: set[str] = set()
    accepted = sorted(
        [row for row in rows if normalize(row.get("candidate_bucket")) == "accepted_proposal_light_label"],
        key=lambda row: (-safe_float(row.get("priority_score")), row.get("source_batch", ""), row.get("clip_id", "")),
    )
    accepted_pack = pack_rows("review_pack_01_accepted_proposals", accepted)
    assigned_clips.update(row.get("clip_id", "") for row in accepted_pack)

    hard_negative_candidates = [
        row
        for row in rows
        if is_hard_negative_candidate(row) and row.get("clip_id", "") not in assigned_clips
    ]
    hard_negative_candidates = sorted(hard_negative_candidates, key=hard_negative_sort_key)
    hard_negative_pack = pack_rows("review_pack_02_hard_negatives_priority", hard_negative_candidates)
    assigned_clips.update(row.get("clip_id", "") for row in hard_negative_pack)

    remaining = [
        row
        for row in rows
        if row.get("clip_id", "") not in assigned_clips and is_predicted_other_or_miss_candidate(row)
    ]
    remaining = sorted(
        remaining,
        key=lambda row: (
            row.get("source_batch", ""),
            -safe_float(row.get("priority_score")),
            row.get("clip_id", ""),
        ),
    )
    remaining_pack = pack_rows("review_pack_03_remaining_predicted_other", remaining)
    return {
        "review_pack_01_accepted_proposals": accepted_pack,
        "review_pack_02_hard_negatives_priority": hard_negative_pack,
        "review_pack_03_remaining_predicted_other": remaining_pack,
    }


def pack_rows(pack_name: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    packed = []
    for index, row in enumerate(rows, start=1):
        packed_row = {column: "" for column in PACK_COLUMNS}
        for column in PACK_COLUMNS:
            if column in row:
                packed_row[column] = row.get(column, "")
        packed_row["pack_name"] = pack_name
        packed_row["pack_rank"] = str(index)
        packed_row["review_timestamp"] = row.get("review_timestamp", "")
        packed_row["pack_priority_reason"] = pack_priority_reason(row)
        for reviewer_field in REVIEWER_FIELDS:
            packed_row[reviewer_field] = row.get(reviewer_field, "")
        packed.append(packed_row)
    return packed


def ingest_reviewed_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors = validate_rows(rows)
    if errors:
        raise LabelIngestionError(errors)

    confirmed_candidates = [canonical_confirmed_row(row) for row in rows if has_confirmed_truth(row)]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in confirmed_candidates:
        grouped[row.get("clip_id", "")].append(row)

    confirmed_rows: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    for clip_id, clip_rows in grouped.items():
        signatures = {truth_signature(row) for row in clip_rows}
        if len(signatures) > 1:
            conflicts.append(
                {
                    "clip_id": clip_id,
                    "conflict_type": "conflicting_labels_for_clip",
                    "row_ids": "|".join(row.get("row_id", "") for row in clip_rows),
                    "source_batches": "|".join(sorted({row.get("source_batch", "") for row in clip_rows})),
                    "truth_signatures": "|".join(sorted(signatures)),
                    "notes": "Conflicting reviewer truth; excluded from confirmed labels until resolved.",
                }
            )
            continue

        merged = choose_canonical_row(clip_rows)
        merged["duplicate_count"] = str(len(clip_rows))
        merged["duplicate_row_ids"] = "|".join(row.get("row_id", "") for row in clip_rows)
        merged["confirmed_truth_signature"] = next(iter(signatures))
        confirmed_rows.append(merged)

    return sorted(confirmed_rows, key=lambda row: (row.get("source_batch", ""), row.get("clip_id", ""))), conflicts


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    seen_row_ids: Counter[str] = Counter()
    for index, row in enumerate(rows, start=2):
        row_id = str(row.get("row_id") or "")
        if row_id:
            seen_row_ids[row_id] += 1
        validate_vocab(errors, row, index, "reviewer_split_other_bucket", ALLOWED_SPLIT_OTHER_BUCKETS)
        validate_vocab(errors, row, index, "reviewer_manual_audit_label", ALLOWED_MANUAL_AUDIT_LABELS)
        validate_vocab(errors, row, index, "reviewer_shot_attempt", ALLOWED_SHOT_ATTEMPT)
        validate_vocab(errors, row, index, "reviewer_outcome", ALLOWED_OUTCOMES)
        validate_vocab(errors, row, index, "review_status", ALLOWED_REVIEW_STATUSES, default="needs_review")
        validate_vocab(errors, row, index, "qa_status", ALLOWED_QA_STATUSES, default="not_started")

        if normalize(row.get("reviewer_manual_audit_label")) == "ambiguous_clip":
            continue
        if normalize(row.get("reviewer_split_other_bucket")) == "ambiguous_event":
            continue
        if normalize(row.get("reviewer_shot_attempt")) == "uncertain":
            continue
        if normalize(row.get("reviewer_outcome")) == "uncertain":
            continue

    duplicate_row_ids = [row_id for row_id, count in seen_row_ids.items() if count > 1]
    for row_id in duplicate_row_ids:
        errors.append(f"duplicate row_id '{row_id}' appears in reviewed inputs")
    return errors


def validate_vocab(
    errors: list[str],
    row: dict[str, str],
    line_number: int,
    field: str,
    allowed: set[str],
    *,
    default: str = "",
) -> None:
    value = normalize(row.get(field) if row.get(field) not in (None, "") else default)
    if value not in allowed:
        errors.append(
            f"line {line_number} clip_id={row.get('clip_id', '')}: invalid {field}={row.get(field)!r}; "
            f"allowed={sorted(value for value in allowed if value)}"
        )


def has_confirmed_truth(row: dict[str, str]) -> bool:
    review_status = normalize(row.get("review_status") or "needs_review")
    qa_status = normalize(row.get("qa_status") or "not_started")
    if review_status not in {"reviewed", "qa_reviewed"}:
        return False
    if qa_status in {"failed", "needs_rework"}:
        return False
    return any(normalize(row.get(field)) for field in REVIEWER_FIELDS)


def canonical_confirmed_row(row: dict[str, str]) -> dict[str, str]:
    canonical = {column: "" for column in CONFIRMED_COLUMNS}
    for column in PACK_COLUMNS:
        canonical[column] = str(row.get(column, "") or "")
    canonical["reviewer_split_other_bucket"] = normalize(canonical["reviewer_split_other_bucket"])
    canonical["reviewer_manual_audit_label"] = normalize(canonical["reviewer_manual_audit_label"])
    canonical["reviewer_shot_attempt"] = normalize(canonical["reviewer_shot_attempt"])
    canonical["reviewer_outcome"] = normalize(canonical["reviewer_outcome"])
    canonical["review_status"] = normalize(canonical["review_status"] or "reviewed")
    canonical["qa_status"] = normalize(canonical["qa_status"] or "not_started")
    return canonical


def choose_canonical_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return sorted(
        rows,
        key=lambda row: (
            normalize(row.get("qa_status")) != "passed",
            row.get("review_timestamp", ""),
            -safe_float(row.get("priority_score")),
            row.get("row_id", ""),
        ),
    )[0]


def build_training_seed(confirmed_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    seed_rows = []
    for row in confirmed_rows:
        acceptor_label = acceptor_label_for(row)
        seed_rows.append(
            {
                "clipId": row.get("clip_id", ""),
                "sourceBatch": row.get("source_batch", ""),
                "sourceDomain": row.get("source_domain", ""),
                "sourceArtifactPath": row.get("source_artifact_path", ""),
                "jobId": row.get("job_id", ""),
                "requestId": row.get("request_id", ""),
                "uploadTraceId": row.get("upload_trace_id", ""),
                "inferenceAttemptId": row.get("inference_attempt_id", ""),
                "candidateBucket": row.get("candidate_bucket", ""),
                "acceptorLabel": acceptor_label,
                "useForTraining": acceptor_label in {"accept", "reject"},
                "hardNegativeBucket": hard_negative_bucket_for(row),
                "manualAuditLabel": row.get("reviewer_manual_audit_label", ""),
                "shotAttempt": row.get("reviewer_shot_attempt", ""),
                "outcome": row.get("reviewer_outcome", ""),
                "qaStatus": row.get("qa_status", ""),
                "reviewedBy": row.get("reviewed_by", ""),
                "reviewTimestamp": row.get("review_timestamp", ""),
                "notes": row.get("notes", ""),
            }
        )
    return seed_rows


def compute_retrain_readiness(
    *,
    confirmed_rows: list[dict[str, str]],
    expanded_rows: list[dict[str, str]],
    conflicts: list[dict[str, str]],
) -> dict[str, Any]:
    confirmed_by_bucket = {
        bucket: sum(1 for row in confirmed_rows if row.get("reviewer_split_other_bucket") == bucket)
        for bucket in HARD_NEGATIVE_BUCKETS
    }
    accepted_light_label_count = sum(1 for row in confirmed_rows if is_accepted_proposal_light_label(row))
    ambiguous_count = sum(1 for row in confirmed_rows if is_ambiguous_truth(row))
    unique_reviewed = {row.get("clip_id", "") for row in confirmed_rows if row.get("clip_id", "")}
    expanded_clip_ids = {row.get("clip_id", "") for row in expanded_rows if row.get("clip_id", "")}
    local_requirements = {
        **{
            bucket: {
                "confirmed": confirmed_by_bucket[bucket],
                "required": LOCAL_UNLOCK_BARS[bucket],
                "met": confirmed_by_bucket[bucket] >= LOCAL_UNLOCK_BARS[bucket],
            }
            for bucket in HARD_NEGATIVE_BUCKETS
        },
        "accepted_proposal_light_labels": {
            "confirmed": accepted_light_label_count,
            "required": LOCAL_UNLOCK_BARS["accepted_proposal_light_labels"],
            "met": accepted_light_label_count >= LOCAL_UNLOCK_BARS["accepted_proposal_light_labels"],
        },
    }
    local_unlocked = all(item["met"] for item in local_requirements.values())
    roadmap_tagged_clip_count = len(unique_reviewed)
    return {
        "generatedAt": "2026-04-13",
        "inputExpandedRows": len(expanded_rows),
        "inputExpandedUniqueClips": len(expanded_clip_ids),
        "confirmedRows": len(confirmed_rows),
        "uniqueClipsReviewed": len(unique_reviewed),
        "confirmedCountsByBucket": confirmed_by_bucket,
        "acceptedProposalLightLabelCount": accepted_light_label_count,
        "ambiguousCount": ambiguous_count,
        "unlabeledRemainingCount": max(len(expanded_clip_ids - unique_reviewed), 0),
        "conflictCount": len(conflicts),
        "localPreRetrainRequirements": local_requirements,
        "localPreRetrainUnlocked": local_unlocked,
        "roadmapContextTarget": {
            "taggedPhase4hClips": roadmap_tagged_clip_count,
            "required": ROADMAP_TARGET_TAGGED_CLIPS,
            "met": roadmap_tagged_clip_count >= ROADMAP_TARGET_TAGGED_CLIPS,
        },
        "recommendation": recommendation_for(local_unlocked, confirmed_by_bucket, accepted_light_label_count),
    }


def render_readiness_report(readiness: dict[str, Any]) -> str:
    lines = [
        "# Phase 4h Retrain Readiness Report",
        "",
        "## Scope",
        "",
        "- Branch: `codex/phase4h-label-ingestion-and-retrain-gate`.",
        "- Purpose: ingest human-reviewed Phase 4h labels and decide whether acceptor retrain prep is unlocked.",
        "- This branch does not retrain a checkpoint, run a smoke batch, run a medium batch, or change runtime thresholds.",
        "",
        "## Current Status",
        "",
        f"- Expanded input rows: `{readiness['inputExpandedRows']}`.",
        f"- Expanded input unique clips: `{readiness['inputExpandedUniqueClips']}`.",
        f"- Confirmed rows: `{readiness['confirmedRows']}`.",
        f"- Unique clips reviewed: `{readiness['uniqueClipsReviewed']}`.",
        f"- Ambiguous confirmed rows: `{readiness['ambiguousCount']}`.",
        f"- Unlabeled remaining unique clips: `{readiness['unlabeledRemainingCount']}`.",
        f"- Conflicts: `{readiness['conflictCount']}`.",
        "",
        "## Local Pre-Retrain Bars",
        "",
    ]
    requirements = readiness["localPreRetrainRequirements"]
    for name, item in requirements.items():
        status = "met" if item["met"] else "blocked"
        lines.append(f"- {name}: `{item['confirmed']}` / `{item['required']}` ({status}).")
    lines.extend(
        [
            "",
            "## Roadmap Context",
            "",
            f"- Tagged Phase 4h clips: `{readiness['roadmapContextTarget']['taggedPhase4hClips']}` / "
            f"`{readiness['roadmapContextTarget']['required']}`.",
            "",
            "## Recommendation",
            "",
            f"- `{readiness['recommendation']}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def recommendation_for(
    local_unlocked: bool,
    confirmed_by_bucket: dict[str, int],
    accepted_light_label_count: int,
) -> str:
    if local_unlocked:
        return "approve acceptor retrain prep"
    missing_buckets = [
        bucket for bucket, required in LOCAL_UNLOCK_BARS.items()
        if bucket != "accepted_proposal_light_labels" and confirmed_by_bucket.get(bucket, 0) < required
    ]
    if accepted_light_label_count < LOCAL_UNLOCK_BARS["accepted_proposal_light_labels"]:
        missing_buckets.append("accepted_proposal_light_labels")
    if missing_buckets:
        return "continue labeling"
    return "hold for label QA"


def is_hard_negative_candidate(row: dict[str, str]) -> bool:
    buckets = set(normalize(row.get("candidate_bucket")).split("|"))
    return any(bucket in buckets for bucket in HARD_NEGATIVE_BUCKETS)


def is_predicted_other_or_miss_candidate(row: dict[str, str]) -> bool:
    return (
        normalize(row.get("predicted_event_family")) == "other"
        or normalize(row.get("candidate_bucket")) == "possible_real_event_miss"
        or normalize(row.get("predicted_flat_label")) == "highlight"
    )


def hard_negative_sort_key(row: dict[str, str]) -> tuple[float, int, int, str, str]:
    return (
        -safe_float(row.get("priority_score")),
        -provenance_score(row),
        clean_bucket_rank(row),
        row.get("source_batch", ""),
        row.get("clip_id", ""),
    )


def clean_bucket_rank(row: dict[str, str]) -> int:
    reason = normalize(row.get("candidate_reason"))
    artifact_bucket = normalize(row.get("artifact_split_other_bucket"))
    if artifact_bucket in HARD_NEGATIVE_BUCKETS:
        return 0
    if "needs_human_bucket_assignment" in reason:
        return 1
    return 2


def provenance_score(row: dict[str, str]) -> int:
    fields = (
        "job_id",
        "request_id",
        "upload_trace_id",
        "inference_attempt_id",
        "source_artifact_path",
        "source_batch",
    )
    return sum(1 for field in fields if row.get(field))


def pack_priority_reason(row: dict[str, str]) -> str:
    parts = [
        f"priority_score={row.get('priority_score', '')}",
        f"provenance_score={provenance_score(row)}",
    ]
    if row.get("artifact_split_other_bucket"):
        parts.append(f"artifact_split_other={row['artifact_split_other_bucket']}")
    if row.get("proposal_accepted"):
        parts.append(f"proposal_accepted={row['proposal_accepted']}")
    if row.get("candidate_reason"):
        parts.append(f"candidate_reason={row['candidate_reason']}")
    return "|".join(parts)


def truth_signature(row: dict[str, str]) -> str:
    return json.dumps(
        {
            "splitOtherBucket": normalize(row.get("reviewer_split_other_bucket")),
            "manualAuditLabel": normalize(row.get("reviewer_manual_audit_label")),
            "shotAttempt": normalize(row.get("reviewer_shot_attempt")),
            "outcome": normalize(row.get("reviewer_outcome")),
        },
        sort_keys=True,
    )


def is_ambiguous_truth(row: dict[str, str]) -> bool:
    return (
        row.get("reviewer_manual_audit_label") == "ambiguous_clip"
        or row.get("reviewer_split_other_bucket") == "ambiguous_event"
        or row.get("reviewer_shot_attempt") == "uncertain"
        or row.get("reviewer_outcome") == "uncertain"
    )


def is_accepted_proposal_light_label(row: dict[str, str]) -> bool:
    return (
        row.get("candidate_bucket") == "accepted_proposal_light_label"
        and (bool(row.get("reviewer_shot_attempt")) or bool(row.get("reviewer_outcome")))
    )


def hard_negative_bucket_for(row: dict[str, str]) -> str:
    bucket = row.get("reviewer_split_other_bucket", "")
    if bucket in HARD_NEGATIVE_BUCKETS:
        return bucket
    if row.get("reviewer_manual_audit_label") == "true_negative_non_event":
        return "true_negative_non_event"
    return ""


def acceptor_label_for(row: dict[str, str]) -> str:
    if hard_negative_bucket_for(row):
        return "reject"
    if row.get("reviewer_manual_audit_label") == "real_event_missed_by_model":
        return "accept"
    if row.get("reviewer_shot_attempt") == "true":
        return "accept"
    if row.get("reviewer_shot_attempt") == "false":
        return "reject"
    return "ambiguous"


def write_review_packs(packs: dict[str, list[dict[str, str]]], output_dir: Path) -> None:
    write_csv(output_dir / DEFAULT_REVIEW_PACK_01.name, packs["review_pack_01_accepted_proposals"], PACK_COLUMNS)
    write_csv(
        output_dir / DEFAULT_REVIEW_PACK_02.name,
        packs["review_pack_02_hard_negatives_priority"],
        PACK_COLUMNS,
    )
    write_csv(
        output_dir / DEFAULT_REVIEW_PACK_03.name,
        packs["review_pack_03_remaining_predicted_other"],
        PACK_COLUMNS,
    )


def load_many_csv(paths: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        if not path.exists():
            continue
        rows.extend(load_csv(path))
    return rows


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(fieldnames)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


if __name__ == "__main__":
    raise SystemExit(main())
