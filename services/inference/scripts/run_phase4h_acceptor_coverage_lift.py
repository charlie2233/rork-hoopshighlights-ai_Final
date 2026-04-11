from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


HARD_NEGATIVE_BUCKETS = {
    "replay_or_reaction",
    "dead_ball",
    "setup",
    "true_negative_non_event",
}
EVENT_FAMILIES = {"shot_attempt", "transition", "defensive_event", "turnover"}
DEFAULT_ARTIFACT_DIR = Path("services/inference/evals/phase4h_acceptor_coverage_lift")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    args.docs_dir.mkdir(parents=True, exist_ok=True)

    staging_report = load_json(args.staging_report)
    smoke_report = load_json(args.smoke_report)
    audit_queue = load_json(args.audit_queue) if args.audit_queue.exists() else {}
    accepted_debug = load_json(args.accepted_debug) if args.accepted_debug.exists() else {}

    rows = build_acceptance_dataset(
        staging_report=staging_report,
        smoke_report=smoke_report,
        audit_queue=audit_queue,
        accepted_debug=accepted_debug,
    )
    sweeps = run_acceptor_sweeps(rows, baseline_acceptance_rate=args.baseline_acceptance_rate)
    recommended = recommend_sweep(sweeps)
    manifest = build_dataset_manifest(rows, baseline_acceptance_rate=args.baseline_acceptance_rate)
    retrain_payload = build_retrain_payload(rows, recommended)

    dataset_path = args.artifact_dir / "acceptance_calibration_dataset.jsonl"
    manifest_path = args.artifact_dir / "acceptance_calibration_manifest.json"
    sweep_path = args.artifact_dir / "acceptor_sweep.json"
    retrain_path = args.artifact_dir / "proposal_acceptor_retrain_config.json"

    dataset_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    sweep_payload = {
        "baselineAcceptanceRate": args.baseline_acceptance_rate,
        "fullRowsIncluded": bool(args.write_full_sweep),
        "sweepRowCount": len(sweeps),
        "selectedRows": select_sweep_rows(sweeps, recommended),
        "recommendedConfig": recommended,
    }
    if args.write_full_sweep:
        sweep_payload["rows"] = sweeps
    sweep_path.write_text(json.dumps(sweep_payload, indent=2, sort_keys=True), encoding="utf-8")
    retrain_path.write_text(json.dumps(retrain_payload, indent=2, sort_keys=True), encoding="utf-8")

    (args.docs_dir / "phase4h_acceptor_calibration_plan.md").write_text(
        render_calibration_plan(
            manifest=manifest,
            dataset_path=dataset_path,
            retrain_path=retrain_path,
        ),
        encoding="utf-8",
    )
    (args.docs_dir / "phase4h_acceptor_sweep_report.md").write_text(
        render_sweep_report(
            sweeps=sweeps,
            recommended=recommended,
            manifest=manifest,
            sweep_path=sweep_path,
        ),
        encoding="utf-8",
    )
    (args.docs_dir / "phase4h_acceptor_retrain_report.md").write_text(
        render_retrain_report(retrain_payload=retrain_payload, manifest=manifest),
        encoding="utf-8",
    )

    print(dataset_path)
    print(args.docs_dir / "phase4h_acceptor_calibration_plan.md")
    print(args.docs_dir / "phase4h_acceptor_sweep_report.md")
    print(args.docs_dir / "phase4h_acceptor_retrain_report.md")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 4h acceptor coverage-lift dataset, replay sweeps, and reports."
    )
    parser.add_argument(
        "--staging-report",
        type=Path,
        default=Path("services/inference/evals/phase4h_staging_eval/shadow_eval_report.json"),
    )
    parser.add_argument(
        "--smoke-report",
        type=Path,
        default=Path("services/inference/evals/phase4h_smoke/shadow_eval_report.json"),
    )
    parser.add_argument(
        "--audit-queue",
        type=Path,
        default=Path("services/inference/evals/phase4h_staging_eval/phase4h_audit_queue.json"),
    )
    parser.add_argument(
        "--accepted-debug",
        type=Path,
        default=Path("services/inference/evals/phase4h_staging_eval/family_gate_accepted_debug.json"),
    )
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--docs-dir", type=Path, default=Path("docs"))
    parser.add_argument("--baseline-acceptance-rate", type=float, default=0.127)
    parser.add_argument(
        "--write-full-sweep",
        action="store_true",
        help="Persist every sweep row instead of the recommended row plus a compact review slice.",
    )
    return parser.parse_args(argv)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_acceptance_dataset(
    *,
    staging_report: dict[str, Any],
    smoke_report: dict[str, Any],
    audit_queue: dict[str, Any],
    accepted_debug: dict[str, Any],
) -> list[dict[str, Any]]:
    audit_by_clip = {
        str(item.get("clipId")): item
        for item in audit_queue.get("items", [])
        if item.get("clipId") is not None
    }
    debug_by_clip = {
        str(item.get("clipId")): item
        for item in accepted_debug.get("rows", [])
        if item.get("clipId") is not None
    }
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source_name, report in (
        ("phase4h_staging_eval_63clip", staging_report),
        ("phase4h_gate_unblock_smoke_18clip", smoke_report),
    ):
        for clip in report.get("clips", []):
            row = normalize_clip_row(
                source_name=source_name,
                clip=clip,
                audit=audit_by_clip.get(str(clip.get("clipId")), {}),
                debug=debug_by_clip.get(str(clip.get("clipId")), {}),
            )
            key = (str(row["datasetSource"]), str(row["clipId"]))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows


def normalize_clip_row(
    *,
    source_name: str,
    clip: dict[str, Any],
    audit: dict[str, Any],
    debug: dict[str, Any],
) -> dict[str, Any]:
    expected_family = first_present(clip, audit, key="expectedEventFamily")
    expected_outcome = first_present(clip, audit, key="expectedOutcome")
    expected_subtype = first_present(clip, audit, key="expectedShotSubtype")
    predicted_family = first_present(audit, clip, key="predictedEventFamily") or clip.get("eventFamily")
    predicted_outcome = first_present(audit, clip, key="predictedOutcome") or clip.get("outcome")
    predicted_subtype = first_present(audit, clip, key="predictedShotSubtype") or clip.get("shotSubtype")
    split_other = first_present(audit, clip, key="splitOtherBucket") or clip.get("otherBucket")
    manual_audit = first_present(audit, clip, key="manualAuditLabel") or derive_manual_audit_label(
        expected_family=expected_family,
        predicted_family=predicted_family,
        family_gate_open=as_bool(clip.get("familyGateOpen")),
        shot_head_invoked=as_bool(clip.get("shotHeadInvoked")),
    )
    hard_negative_bucket = derive_hard_negative_bucket(
        split_other_bucket=split_other,
        manual_audit_label=manual_audit,
    )
    acceptance_label, acceptance_label_source = derive_acceptance_label(
        expected_family=expected_family,
        manual_audit_label=manual_audit,
        hard_negative_bucket=hard_negative_bucket,
    )
    event_family_label = expected_family or predicted_family or "unknown"
    outcome_label = expected_outcome or predicted_outcome or "uncertain"
    acceptance_score = coerce_float(
        first_present(audit, clip, key="rawAcceptanceScore")
        or first_present(audit, clip, key="acceptanceScore")
        or clip.get("proposalAcceptanceRawScore")
        or clip.get("proposalScore")
        or clip.get("proposalEventScore")
    )
    acceptance_probability = coerce_float(
        first_present(audit, clip, key="calibratedAcceptanceProbability")
        or clip.get("proposalAcceptanceProbability")
        or clip.get("proposalAcceptanceProbabilityCalibrated")
    )
    energy_score = coerce_float(first_present(audit, clip, key="energyScore") or clip.get("proposalEnergyScore"))
    family_debug = debug.get("shadowRelaxedFamilyEval") or {}
    would_family_open = bool(clip.get("familyGateOpen")) or bool(family_debug.get("familyGateWouldOpen"))
    would_shot_invoke = bool(clip.get("shotHeadInvoked")) or bool(family_debug.get("shotHeadWouldInvoke"))
    shot_attempt = str(event_family_label) == "shot_attempt"
    if acceptance_label == "accept" and shot_attempt:
        would_family_open = True
        would_shot_invoke = True
    return {
        "datasetSource": source_name,
        "clipId": clip.get("clipId"),
        "jobId": clip.get("jobId"),
        "requestId": clip.get("requestId") or audit.get("requestId"),
        "uploadTraceId": clip.get("uploadTraceId") or audit.get("uploadTraceId"),
        "inferenceAttemptId": clip.get("inferenceAttemptId") or audit.get("inferenceAttemptId"),
        "modelVersion": clip.get("modelVersion") or audit.get("modelVersion"),
        "sourceDomain": clip.get("sourceDomain") or audit.get("sourceDomain"),
        "eventFamily": event_family_label,
        "expectedEventFamily": expected_family,
        "predictedEventFamily": predicted_family,
        "outcome": outcome_label,
        "expectedOutcome": expected_outcome,
        "predictedOutcome": predicted_outcome,
        "shotSubtype": expected_subtype or predicted_subtype,
        "expectedShotSubtype": expected_subtype,
        "predictedShotSubtype": predicted_subtype,
        "splitOtherBucket": split_other,
        "manualAuditLabel": manual_audit,
        "shotAttempt": shot_attempt,
        "proposalAccepted": bool(clip.get("proposalAccepted") or audit.get("proposalAccepted")),
        "familyGateOpen": bool(clip.get("familyGateOpen") or audit.get("familyGateOpen")),
        "shotHeadInvoked": bool(clip.get("shotHeadInvoked") or audit.get("shotHeadInvoked")),
        "wouldFamilyGateOpenIfAccepted": bool(would_family_open),
        "wouldShotHeadInvokeIfAccepted": bool(would_shot_invoke),
        "acceptanceScore": acceptance_score,
        "calibratedAcceptanceProbability": acceptance_probability,
        "energyScore": energy_score,
        "acceptanceLabel": acceptance_label,
        "acceptanceLabelSource": acceptance_label_source,
        "hardNegativeBucket": hard_negative_bucket,
        "requiresHumanReview": acceptance_label == "unknown",
        "predictedFlatLabel": clip.get("flatLabel") or audit.get("predictedFlatLabel"),
        "rejectionRationale": (
            clip.get("familyGateRejectionReason")
            or audit.get("rejectionRationale")
            or clip.get("proposalRejectionReason")
        ),
    }


def derive_manual_audit_label(
    *,
    expected_family: Any,
    predicted_family: Any,
    family_gate_open: bool,
    shot_head_invoked: bool,
) -> str:
    if expected_family in EVENT_FAMILIES and (family_gate_open or shot_head_invoked):
        return "real_event_reached_shot_stack"
    if expected_family in EVENT_FAMILIES and predicted_family == "other":
        return "real_event_missed_by_model"
    if expected_family == "other":
        return "true_negative_non_event"
    return "ambiguous_clip"


def derive_hard_negative_bucket(*, split_other_bucket: Any, manual_audit_label: Any) -> str | None:
    split_value = normalize_bucket(split_other_bucket)
    manual_value = normalize_bucket(manual_audit_label)
    if split_value in HARD_NEGATIVE_BUCKETS:
        return split_value
    if manual_value in HARD_NEGATIVE_BUCKETS or manual_value == "true_negative":
        return "true_negative_non_event"
    if manual_value == "true_negative_non_event":
        return "true_negative_non_event"
    return None


def derive_acceptance_label(
    *,
    expected_family: Any,
    manual_audit_label: Any,
    hard_negative_bucket: str | None,
) -> tuple[str, str]:
    if str(expected_family or "") in EVENT_FAMILIES:
        return "accept", "expected_event_family"
    if str(manual_audit_label or "") in {"real_event_missed_by_model", "real_event_reached_shot_stack"}:
        return "accept", "manual_audit_real_event"
    if hard_negative_bucket:
        return "reject", f"hard_negative:{hard_negative_bucket}"
    return "unknown", "ambiguous_or_unlabeled"


def run_acceptor_sweeps(rows: list[dict[str, Any]], *, baseline_acceptance_rate: float) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    temperatures = (0.75, 1.0, 1.25, 1.5, 2.0)
    thresholds = (0.06, 0.08, 0.1, 0.2, 0.3, 0.35, 0.42, 0.5, 0.58, 0.65)
    energy_thresholds: tuple[float | None, ...] = (None, -1.5, -1.25, -1.0, -0.8, -0.6)
    loss_configs = (
        "focal_class_balanced:g1.75:a0.50",
        "focal_class_balanced:g2.00:a0.65",
        "class_balanced:g0.00:a0.65",
    )
    for temperature in temperatures:
        for threshold in thresholds:
            for energy_threshold in energy_thresholds:
                for loss_config in loss_configs:
                    outputs.append(
                        evaluate_acceptor_sweep(
                            rows,
                            temperature=temperature,
                            threshold=threshold,
                            energy_threshold=energy_threshold,
                            loss_config=loss_config,
                            baseline_acceptance_rate=baseline_acceptance_rate,
                        )
                    )
    return outputs


def evaluate_acceptor_sweep(
    rows: list[dict[str, Any]],
    *,
    temperature: float,
    threshold: float,
    energy_threshold: float | None,
    loss_config: str,
    baseline_acceptance_rate: float,
) -> dict[str, Any]:
    accepted_rows = [
        row for row in rows if acceptor_sweep_accepts(row, temperature=temperature, threshold=threshold, energy_threshold=energy_threshold)
    ]
    family_open_rows = [row for row in accepted_rows if row.get("wouldFamilyGateOpenIfAccepted")]
    shot_rows = [row for row in accepted_rows if row.get("wouldShotHeadInvokeIfAccepted")]
    flat_labels = [replay_flat_label(row, accepted=row in accepted_rows) for row in rows]
    family_labels = [
        str(row.get("eventFamily") or "other")
        if row in family_open_rows
        else "other"
        for row in rows
    ]
    accepted_labeled = [row for row in accepted_rows if row.get("acceptanceLabel") in {"accept", "reject"}]
    accepted_unknown = [row for row in accepted_rows if row.get("acceptanceLabel") == "unknown"]
    accepted_rejects = [row for row in accepted_labeled if row.get("acceptanceLabel") == "reject"]
    source_acceptance = {}
    for source in sorted({str(row.get("datasetSource")) for row in rows}):
        source_rows = [row for row in rows if str(row.get("datasetSource")) == source]
        source_accepted = [row for row in accepted_rows if str(row.get("datasetSource")) == source]
        source_acceptance[source] = {
            "acceptedCount": len(source_accepted),
            "rowCount": len(source_rows),
            "acceptanceRate": round(len(source_accepted) / max(len(source_rows), 1), 4),
        }
    accepted_precision = None
    if accepted_labeled:
        accepted_precision = round(
            sum(1 for row in accepted_labeled if row.get("acceptanceLabel") == "accept") / len(accepted_labeled),
            4,
        )
    miss_to_made = sum(
        1
        for row in accepted_rows
        if row.get("expectedOutcome") == "missed" and replay_flat_label(row, accepted=True) == "Made Shot"
    )
    dunk_made_signal = sum(
        1
        for row in accepted_rows
        if row.get("predictedFlatLabel") == "Dunk" or row.get("predictedShotSubtype") == "dunk"
    )
    label_counts = Counter(flat_labels)
    family_counts = Counter(family_labels)
    dominant_label, dominant_count = label_counts.most_common(1)[0] if label_counts else ("none", 0)
    total = max(len(rows), 1)
    return {
        "temperature": temperature,
        "calibratedAcceptanceProbabilityThreshold": threshold,
        "energyThreshold": energy_threshold,
        "trainingLossConfig": loss_config,
        "proposalAcceptedCount": len(accepted_rows),
        "proposalAcceptanceRate": round(len(accepted_rows) / total, 4),
        "acceptanceLiftOverBaseline": round((len(accepted_rows) / total) - baseline_acceptance_rate, 4),
        "familyGateOpenCount": len(family_open_rows),
        "shotHeadInvocationCount": len(shot_rows),
        "rawEventFamilyOtherRate": round(family_counts.get("other", 0) / total, 4),
        "dominantFlatLabel": dominant_label,
        "dominantFlatLabelShare": round(dominant_count / total, 4),
        "missToMadeDrift": miss_to_made,
        "dunkMadeHallucinationSignal": dunk_made_signal,
        "acceptedPrecisionOnAuditedClips": accepted_precision,
        "acceptedAuditedRejectCount": len(accepted_rejects),
        "acceptedUnknownCount": len(accepted_unknown),
        "sourceAcceptance": source_acceptance,
        "flatLabelDistribution": dict(sorted(label_counts.items())),
        "eventFamilyDistribution": dict(sorted(family_counts.items())),
    }


def acceptor_sweep_accepts(
    row: dict[str, Any],
    *,
    temperature: float,
    threshold: float,
    energy_threshold: float | None,
) -> bool:
    score = row.get("acceptanceScore")
    if score is None:
        return False
    calibrated = calibrate_probability(float(score), temperature=temperature)
    if calibrated < threshold:
        return False
    if energy_threshold is None:
        return True
    energy = row.get("energyScore")
    if energy is None:
        return True
    return float(energy) >= float(energy_threshold)


def calibrate_probability(score: float, *, temperature: float) -> float:
    score = min(max(float(score), 1e-6), 1.0 - 1e-6)
    logit = math.log(score / (1.0 - score))
    scaled = logit / max(float(temperature), 1e-6)
    return 1.0 / (1.0 + math.exp(-scaled))


def replay_flat_label(row: dict[str, Any], *, accepted: bool) -> str:
    if not accepted or not row.get("wouldFamilyGateOpenIfAccepted"):
        return "Highlight"
    family = str(row.get("eventFamily") or "other")
    outcome = str(row.get("outcome") or "uncertain")
    if family == "shot_attempt":
        if outcome == "made":
            return "Made Shot"
        return "Shot Attempt"
    if family == "transition":
        return "Fast Break"
    if family == "defensive_event":
        return "Block"
    if family == "turnover":
        return "Steal"
    return "Highlight"


def recommend_sweep(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    viable = [
        row
        for row in rows
        if row["acceptanceLiftOverBaseline"] > 0.03
        and row["familyGateOpenCount"] > 0
        and row["shotHeadInvocationCount"] > 0
        and row["missToMadeDrift"] == 0
        and row["dunkMadeHallucinationSignal"] == 0
        and row["dominantFlatLabelShare"] <= 0.8
        and row["acceptedAuditedRejectCount"] == 0
    ]
    if not viable:
        return None
    viable.sort(
        key=lambda row: (
            row["acceptedUnknownCount"],
            -row["proposalAcceptanceRate"],
            row["dominantFlatLabelShare"],
            abs(row["temperature"] - 1.0),
            abs(row["calibratedAcceptanceProbabilityThreshold"] - 0.42),
            str(row["energyThreshold"]),
        )
    )
    return viable[0]


def select_sweep_rows(rows: list[dict[str, Any]], recommended: dict[str, Any] | None) -> list[dict[str, Any]]:
    selected = sorted(
        rows,
        key=lambda row: (
            row["acceptedUnknownCount"],
            row["acceptedAuditedRejectCount"],
            row["missToMadeDrift"],
            row["dunkMadeHallucinationSignal"],
            row["dominantFlatLabelShare"],
            -row["proposalAcceptanceRate"],
        ),
    )[:24]
    if recommended:
        selected = [recommended] + [row for row in selected if row != recommended][:23]
    return selected


def build_dataset_manifest(rows: list[dict[str, Any]], *, baseline_acceptance_rate: float) -> dict[str, Any]:
    label_counts = Counter(str(row.get("acceptanceLabel")) for row in rows)
    source_counts = Counter(str(row.get("datasetSource")) for row in rows)
    hard_negative_counts = Counter(
        str(row.get("hardNegativeBucket")) for row in rows if row.get("hardNegativeBucket")
    )
    event_counts = Counter(str(row.get("eventFamily") or "unknown") for row in rows)
    outcome_counts = Counter(str(row.get("outcome") or "uncertain") for row in rows)
    accepted_count = sum(1 for row in rows if row.get("proposalAccepted"))
    return {
        "rowCount": len(rows),
        "baselineAcceptanceRate": baseline_acceptance_rate,
        "proposalAcceptedCountInSourceArtifacts": accepted_count,
        "proposalAcceptanceRateInSourceArtifacts": round(accepted_count / max(len(rows), 1), 4),
        "datasetSourceDistribution": dict(sorted(source_counts.items())),
        "acceptanceLabelDistribution": dict(sorted(label_counts.items())),
        "eventFamilyDistribution": dict(sorted(event_counts.items())),
        "outcomeDistribution": dict(sorted(outcome_counts.items())),
        "hardNegativeDistribution": dict(sorted(hard_negative_counts.items())),
        "missingHardNegativeBuckets": sorted(HARD_NEGATIVE_BUCKETS - set(hard_negative_counts)),
        "requiresHumanReviewCount": sum(1 for row in rows if row.get("requiresHumanReview")),
        "acceptedProposalsWithGateOpenCount": sum(
            1 for row in rows if row.get("proposalAccepted") and row.get("familyGateOpen")
        ),
        "acceptedProposalsWithShotHeadCount": sum(
            1 for row in rows if row.get("proposalAccepted") and row.get("shotHeadInvoked")
        ),
    }


def build_retrain_payload(
    rows: list[dict[str, Any]],
    recommended: dict[str, Any] | None,
) -> dict[str, Any]:
    manifest = build_dataset_manifest(rows, baseline_acceptance_rate=0.127)
    hard_negative_count = sum(1 for row in rows if row.get("acceptanceLabel") == "reject")
    status = "ready_for_small_smoke_config_only"
    if hard_negative_count < 8:
        status = "blocked_by_missing_curated_hard_negatives"
    return {
        "status": status,
        "reason": (
            "The standing dataset has labeled positives and unknown demo clips, but too few confirmed hard negatives "
            "for a safe acceptor weight update."
        ),
        "datasetSummary": manifest,
        "recommendedReplayConfig": recommended,
        "trainingConfig": {
            "proposalRejectorLossMode": "focal_class_balanced",
            "proposalRejectorFocalGamma": 1.75,
            "proposalRejectorClassBalanceAlpha": 0.5,
            "proposalAcceptorLossMode": "focal_class_balanced",
            "proposalAcceptorFocalGamma": 2.0,
            "proposalAcceptorClassBalanceAlpha": 0.65,
            "temperatureScaling": True,
            "energyScoreReporting": True,
            "outlierExposureBuckets": sorted(HARD_NEGATIVE_BUCKETS),
        },
        "guardrails": {
            "doNotChangeFamilyRescueThresholds": True,
            "doNotChangeDetectorFamily": True,
            "doNotUseSpaceJam": True,
            "missToMadeDriftMustRemain": 0,
            "rejectIfDominantFlatLabelShareIncreases": True,
        },
    }


def render_calibration_plan(
    *,
    manifest: dict[str, Any],
    dataset_path: Path,
    retrain_path: Path,
) -> str:
    return "\n".join(
        [
            "# Phase 4h Acceptor Calibration Plan",
            "",
            "## Scope",
            "",
            "- Branch: `codex/phase4h-acceptor-coverage-lift`.",
            "- Goal: lift proposal acceptance coverage without touching family rescue thresholds, detector family, SpaceJam, or outcome mapping.",
            "- Contract posture: additive-only replay artifacts and training config; no app-facing payload fields are removed or renamed.",
            "",
            "## Standing Dataset",
            "",
            f"- Artifact: `{dataset_path}`.",
            f"- Rows: `{manifest['rowCount']}`.",
            f"- Source distribution: `{json.dumps(manifest['datasetSourceDistribution'], sort_keys=True)}`.",
            f"- Acceptance labels: `{json.dumps(manifest['acceptanceLabelDistribution'], sort_keys=True)}`.",
            f"- Event families: `{json.dumps(manifest['eventFamilyDistribution'], sort_keys=True)}`.",
            f"- Outcomes: `{json.dumps(manifest['outcomeDistribution'], sort_keys=True)}`.",
            f"- Source accepted proposals: `{manifest['proposalAcceptedCountInSourceArtifacts']}`.",
            f"- Source acceptance rate: `{manifest['proposalAcceptanceRateInSourceArtifacts']}`.",
            "",
            "## Hard-Negative Coverage",
            "",
            f"- Present hard-negative buckets: `{json.dumps(manifest['hardNegativeDistribution'], sort_keys=True)}`.",
            f"- Missing hard-negative buckets: `{json.dumps(manifest['missingHardNegativeBuckets'])}`.",
            f"- Human-review rows still required: `{manifest['requiresHumanReviewCount']}`.",
            "- The current artifacts do not contain enough confirmed replay/dead-ball/setup/non-event labels to safely write a new acceptor checkpoint.",
            "",
            "## Calibration Path",
            "",
            "- Use raw acceptance score as the replay control signal because the 63-clip staging artifact lacks calibrated acceptance probability and energy score.",
            "- Treat smoke `proposalAcceptanceProbability` as diagnostic telemetry only; raw acceptance score remains the sweep input for consistency with staging.",
            "- Report accepted precision on audited rows separately from accepted unknown rows so unlabeled demo clips cannot masquerade as safe positives.",
            f"- Proposed retrain config artifact: `{retrain_path}`.",
            "",
            "## Required Next Labels",
            "",
            "- Confirm whether high-scoring unlabeled demo clips are real events, setup, replay/reaction, or true non-events.",
            "- Add at least one confirmed row for each required hard-negative bucket before writing an acceptor checkpoint.",
            "- Keep accepted -> family gate -> shot head smoke coverage as the first guardrail after any acceptor threshold or checkpoint change.",
        ]
    ) + "\n"


def render_sweep_report(
    *,
    sweeps: list[dict[str, Any]],
    recommended: dict[str, Any] | None,
    manifest: dict[str, Any],
    sweep_path: Path,
) -> str:
    top_rows = select_sweep_rows(sweeps, recommended)[:12]
    lines = [
        "# Phase 4h Acceptor Sweep Report",
        "",
        "## Summary",
        "",
        f"- Sweep artifact: `{sweep_path}`.",
        f"- Baseline staging acceptance rate: `{manifest['baselineAcceptanceRate']}`.",
        f"- Source artifact acceptance rate across bootstrap rows: `{manifest['proposalAcceptanceRateInSourceArtifacts']}`.",
        f"- Bootstrap rows: `{manifest['rowCount']}`.",
        f"- Confirmed hard-negative rows: `{sum(manifest['hardNegativeDistribution'].values())}`.",
        "",
        "## Recommendation",
        "",
    ]
    if recommended:
        lines.extend(
            [
                "- Recommendation: rerun a small smoke only, not a 60-80 clip medium batch.",
                f"- Temperature: `{recommended['temperature']}`.",
                f"- Calibrated acceptance probability threshold: `{recommended['calibratedAcceptanceProbabilityThreshold']}`.",
                f"- Energy threshold: `{recommended['energyThreshold']}`.",
                f"- Training loss config tag: `{recommended['trainingLossConfig']}`.",
                f"- Replay proposal acceptance rate: `{recommended['proposalAcceptanceRate']}`.",
                f"- Replay family gate opens: `{recommended['familyGateOpenCount']}`.",
                f"- Replay shot head invocations: `{recommended['shotHeadInvocationCount']}`.",
                f"- Replay dominant flat-label share: `{recommended['dominantFlatLabelShare']}`.",
                f"- Replay miss-to-made drift: `{recommended['missToMadeDrift']}`.",
                f"- Accepted unknown rows: `{recommended['acceptedUnknownCount']}`.",
                "- This is a smoke-safety recommendation only because confirmed hard negatives are still missing.",
                f"- Source-specific replay acceptance: `{json.dumps(recommended['sourceAcceptance'], sort_keys=True)}`.",
            ]
        )
    else:
        lines.extend(
            [
                "- Recommendation: hold for more labeling before changing the acceptor.",
                "- No replay row both lifted acceptance beyond the baseline and stayed within the dominance/unknown-risk guardrails.",
            ]
        )
    lines.extend(
        [
            "",
            "## Top Replay Rows",
            "",
            "| temp | prob threshold | energy threshold | loss config | accept rate | gate opens | shot head | raw other | dominant share | unknown accepted | audited rejects accepted | miss->made |",
            "| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in top_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["temperature"]),
                    str(row["calibratedAcceptanceProbabilityThreshold"]),
                    str(row["energyThreshold"]),
                    str(row["trainingLossConfig"]),
                    str(row["proposalAcceptanceRate"]),
                    str(row["familyGateOpenCount"]),
                    str(row["shotHeadInvocationCount"]),
                    str(row["rawEventFamilyOtherRate"]),
                    str(row["dominantFlatLabelShare"]),
                    str(row["acceptedUnknownCount"]),
                    str(row["acceptedAuditedRejectCount"]),
                    str(row["missToMadeDrift"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Guardrail Readout",
            "",
            "- Acceptance lift can be achieved on replay, but the medium-batch target of `0.35-0.75` is not justified until unknown high-scoring clips receive hard-negative or event labels.",
            "- Accepted rows continue to model family-gate opening and shot-head invocation because this branch does not alter the now-working family-gate rescue path.",
            "- Replay emits `Shot Attempt` for missed/uncertain accepted shot attempts, preventing miss-to-made drift in the sweep model.",
            "- The sweep does not validate real shot-head outcome quality; live smoke remains required before any medium batch.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_retrain_report(*, retrain_payload: dict[str, Any], manifest: dict[str, Any]) -> str:
    config = retrain_payload["trainingConfig"]
    lines = [
        "# Phase 4h Acceptor Retrain Report",
        "",
        "## Decision",
        "",
        f"- Status: `{retrain_payload['status']}`.",
        f"- Reason: {retrain_payload['reason']}",
        "- No new detector family, SpaceJam input, family rescue threshold, or outcome mapping change is included in this branch.",
        "",
        "## Available Supervision",
        "",
        f"- Dataset rows: `{manifest['rowCount']}`.",
        f"- Acceptance labels: `{json.dumps(manifest['acceptanceLabelDistribution'], sort_keys=True)}`.",
        f"- Hard-negative distribution: `{json.dumps(manifest['hardNegativeDistribution'], sort_keys=True)}`.",
        f"- Missing hard-negative buckets: `{json.dumps(manifest['missingHardNegativeBuckets'])}`.",
        "",
        "## Retrain Config",
        "",
        f"- Proposal rejector loss: `{config['proposalRejectorLossMode']}` with gamma `{config['proposalRejectorFocalGamma']}` and alpha `{config['proposalRejectorClassBalanceAlpha']}`.",
        f"- Proposal acceptor loss: `{config['proposalAcceptorLossMode']}` with gamma `{config['proposalAcceptorFocalGamma']}` and alpha `{config['proposalAcceptorClassBalanceAlpha']}`.",
        f"- Temperature scaling enabled: `{config['temperatureScaling']}`.",
        f"- Energy-score reporting enabled: `{config['energyScoreReporting']}`.",
        f"- Outlier exposure buckets: `{json.dumps(config['outlierExposureBuckets'])}`.",
        "",
        "## Training Command",
        "",
        "```bash",
        "uv run --with-requirements services/inference/requirements.txt \\",
        "  python3 services/inference/scripts/train_temporal_event_detector_candidates.py \\",
        "  --output-dir services/inference/evals/phase4h_acceptor_coverage_lift/retrain_candidate \\",
        "  --proposal-rejector-loss-mode focal_class_balanced \\",
        "  --proposal-rejector-focal-gamma 1.75 \\",
        "  --proposal-rejector-class-balance-alpha 0.5 \\",
        "  --proposal-acceptor-loss-mode focal_class_balanced \\",
        "  --proposal-acceptor-focal-gamma 2.0 \\",
        "  --proposal-acceptor-class-balance-alpha 0.65",
        "```",
        "",
        "## Recommendation",
        "",
        "- Rerun a small smoke only after the acceptor threshold/config change is applied behind the existing shadow path.",
        "- Hold medium-batch approval until at least the high-scoring unknown demo clips are audited and the required hard-negative buckets are represented.",
    ]
    return "\n".join(lines) + "\n"


def first_present(*items: dict[str, Any], key: str) -> Any:
    for item in items:
        value = item.get(key)
        if value is not None:
            return value
    return None


def coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> bool:
    return bool(value)


def normalize_bucket(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def iter_rows(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


if __name__ == "__main__":
    raise SystemExit(main())
