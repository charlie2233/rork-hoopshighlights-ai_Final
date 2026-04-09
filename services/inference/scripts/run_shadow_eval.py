from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from services.inference.app.labels import canonical_to_display_label

EVENT_FAMILIES = ["shot_attempt", "turnover", "defensive_event", "transition", "other"]
OUTCOMES = ["made", "missed", "blocked", "uncertain"]
OTHER_BUCKETS = [
    "non_event",
    "setup",
    "dead_ball",
    "replay_or_reaction",
    "ambiguous_event",
    "other_true_unknown",
]
OTHER_AUDIT_LABELS = [
    "true_negative_non_event",
    "real_event_missed_by_model",
    "ambiguous_clip",
    "data_or_sampling_issue",
]
CANDIDATE_NAMESPACES = (
    "runtimeFusionShadow",
    "runtimeFusionLoRAShadow",
    "runtimeFusionTemporalShadow",
    "runtimeFusionDistilledShadow",
    "runtimeFusionLive",
    "runtimeFusionPrimary",
)


@dataclass
class ShadowClipRecord:
    jobId: str | None
    clipId: str
    requestId: str | None
    uploadTraceId: str | None
    inferenceAttemptId: str | None
    modelVersion: str | None
    flatLabel: str
    eventFamily: str
    eventSpotterFamily: str | None
    otherBucket: str | None
    otherBucketReason: str | None
    shotSubtype: str | None
    outcome: str
    confidence: float
    confidenceBeforeMapping: float | None
    confidenceAfterMapping: float | None
    resultConfidence: float | None
    candidateNamespace: str
    clipDurationSeconds: float | None
    wasMerged: bool
    sourceEventCount: int | None
    isUncertain: bool
    rawVideoMAETopK: list[dict[str, Any]]
    rawXCLIPSuggestions: list[dict[str, Any]]
    expectedLabel: str | None = None
    expectedEventFamily: str | None = None
    expectedOutcome: str | None = None
    expectedShotSubtype: str | None = None
    sourceDomain: str | None = None
    manualAuditLabel: str | None = None
    manualAuditRationale: str | None = None
    proposalAccepted: bool | None = None
    proposalScore: float | None = None
    proposalAcceptanceRawScore: float | None = None
    proposalAcceptanceProbability: float | None = None
    proposalEnergyScore: float | None = None
    proposalRejectorLabel: str | None = None
    proposalRejectorConfidence: float | None = None
    familyGateOpen: bool | None = None
    familyGateRejectionReason: str | None = None
    shotHeadInvoked: bool | None = None
    shotSpecialistUsed: bool | None = None
    shotSpecialistAbstained: bool | None = None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manual_audits = load_manual_audits(args.other_audit)
    records = load_batch_records(args.batch_results, shadow_source=args.shadow_source, manual_audits=manual_audits)
    report = build_shadow_report(records)
    if args.baseline_results:
        baseline_records = load_batch_records(
            args.baseline_results,
            shadow_source=args.shadow_source,
            manual_audits=manual_audits,
        )
        baseline_report = build_shadow_report(baseline_records)
        report["baselineSummary"] = baseline_report["summary"]
        report["baselineCandidateNamespaces"] = baseline_report["summary"].get("candidateNamespaces", {})
        report["comparisonSummary"] = build_shadow_comparison_summary(
            baseline_report["summary"],
            report["summary"],
        )
        report["baselineCollapseExamples"] = baseline_report["collapseExamples"][:8]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "shadow_eval_report.json"
    md_path = args.output_dir / "shadow_eval_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(md_path)
    print(json_path)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a shadow-eval report for staging or local runtime batches.")
    parser.add_argument(
        "--batch-results",
        type=Path,
        nargs="+",
        required=True,
        help="One or more JSON files containing job result payloads or clip-level result arrays.",
    )
    parser.add_argument(
        "--baseline-results",
        type=Path,
        nargs="+",
        help="Optional phase3d baseline batch results to compare against the candidate shadow batch.",
    )
    parser.add_argument(
        "--shadow-source",
        choices=("auto",) + CANDIDATE_NAMESPACES,
        default="auto",
        help="Which shadow payload to normalize when multiple shadow namespaces are present.",
    )
    parser.add_argument(
        "--other-audit",
        type=Path,
        nargs="*",
        default=[],
        help="Optional JSON/JSONL files mapping clipId to manual other-bucket audit labels.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def load_batch_records(
    paths: Iterable[Path],
    *,
    shadow_source: str = "auto",
    manual_audits: dict[str, dict[str, str | None]] | None = None,
) -> list[ShadowClipRecord]:
    records: list[ShadowClipRecord] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        top_level_items = _extract_top_level_items(payload)
        for top_level in top_level_items:
            records.extend(
                _normalize_batch_item(
                    top_level,
                    shadow_source=shadow_source,
                    manual_audits=manual_audits or {},
                )
            )
    return records


def build_shadow_report(records: list[ShadowClipRecord]) -> dict[str, Any]:
    flat_label_distribution = distribution(record.flatLabel for record in records)
    event_family_distribution = distribution(record.eventFamily for record in records)
    shot_subtype_distribution = distribution(record.shotSubtype for record in records)
    outcome_distribution = distribution(record.outcome for record in records)
    source_domain_distribution = distribution(record.sourceDomain for record in records)
    uncertainty_rate = round(sum(1 for record in records if record.isUncertain) / max(len(records), 1), 4)
    raw_event_family_other_rate = round(event_family_distribution.get("other", 0) / max(len(records), 1), 4)
    duration_summary = build_duration_summary(record.clipDurationSeconds for record in records)
    label_spread = build_label_spread(records, flat_label_distribution)
    miss_vs_made_confusion = build_miss_vs_made_confusion(records)
    labeled_eval = build_labeled_eval_summary(records)
    proposal_summary = build_proposal_summary(records)
    accepted_shot_outcome_calibration = proposal_summary.get("acceptedShotOutcomeCalibration")
    trace_summary = build_trace_summary(records)
    candidate_namespace_summary = build_namespace_summary(record.candidateNamespace for record in records)
    collapse_examples = build_collapse_examples(records)
    clip_total = max(len(records), 1)
    highlight_dominance = round(flat_label_distribution.get("Highlight", 0) / clip_total, 4)
    event_family_other_dominance = round(event_family_distribution.get("other", 0) / clip_total, 4)
    dominant_flat_label = label_spread["dominantLabel"]
    dominant_flat_label_share = label_spread["dominantLabelShare"]
    other_bucket_distribution = build_other_bucket_distribution(records)
    other_bucket_audit = build_other_bucket_audit(records)
    return {
        "summary": {
            "jobCount": len(trace_summary["jobIds"]),
            "clipCount": len(records),
            "requestIds": trace_summary["requestIds"],
            "uploadTraceIds": trace_summary["uploadTraceIds"],
            "inferenceAttemptIds": trace_summary["inferenceAttemptIds"],
            "modelVersions": trace_summary["modelVersions"],
            "candidateNamespaces": candidate_namespace_summary,
            "flatLabelDistribution": flat_label_distribution,
            "eventFamilyDistribution": event_family_distribution,
            "shotSubtypeDistribution": shot_subtype_distribution,
            "outcomeDistribution": outcome_distribution,
            "sourceDomainDistribution": source_domain_distribution,
            "uncertaintyRate": uncertainty_rate,
            "rawEventFamilyOtherRate": raw_event_family_other_rate,
            "highlightDominance": highlight_dominance,
            "eventFamilyOtherDominance": event_family_other_dominance,
            "dominantFlatLabel": dominant_flat_label,
            "dominantFlatLabelShare": dominant_flat_label_share,
            "proposalAcceptanceRate": proposal_summary["proposalAcceptanceRate"],
            "proposalAcceptanceClipCount": proposal_summary["proposalAcceptanceClipCount"],
            "proposalAcceptedCount": proposal_summary["proposalAcceptedCount"],
            "familyGateOpenRate": proposal_summary["familyGateOpenRate"],
            "familyGateOpenClipCount": proposal_summary["familyGateOpenClipCount"],
            "familyGateOpenCount": proposal_summary["familyGateOpenCount"],
            "shotHeadInvocationRate": proposal_summary["shotHeadInvocationRate"],
            "shotHeadInvocationClipCount": proposal_summary["shotHeadInvocationClipCount"],
            "shotHeadInvocationCount": proposal_summary["shotHeadInvocationCount"],
            "eventnessCalibration": proposal_summary["eventnessCalibration"],
            "acceptanceCalibration": proposal_summary["acceptanceCalibration"],
            "acceptedShotProposalOutcomeAccuracy": proposal_summary["acceptedShotProposalOutcomeAccuracy"],
            "acceptedShotSubtypeDistribution": proposal_summary["acceptedShotSubtypeDistribution"],
            "acceptedShotAbstentionRate": proposal_summary["acceptedShotAbstentionRate"],
            "acceptedShotOutcomeCalibration": accepted_shot_outcome_calibration,
            "dunkDominance": proposal_summary["dunkDominance"],
            "rejectedProposalAudit": proposal_summary["rejectedProposalAudit"],
            "splitOtherDistribution": other_bucket_distribution,
            "otherBucketAudit": other_bucket_audit,
            "missVsMadeConfusion": miss_vs_made_confusion,
            "eventSpotterPrecision": labeled_eval["eventSpotterPrecision"],
            "eventSpotterRecall": labeled_eval["eventSpotterRecall"],
            "eventDetectionPrecision": labeled_eval["eventDetectionPrecision"],
            "eventDetectionRecall": labeled_eval["eventDetectionRecall"],
            "eventFamilyAccuracy": labeled_eval["eventFamilyAccuracy"],
            "outcomeAccuracy": labeled_eval["outcomeAccuracy"],
            "shotSubtypeAccuracy": labeled_eval["shotSubtypeAccuracy"],
            "labeledClipCount": labeled_eval["labeledClipCount"],
            "durationSummary": duration_summary,
            "mixedBatchLabelSpread": label_spread,
        },
        "clips": [asdict(record) for record in records],
        "collapseExamples": collapse_examples,
        "labelSpreadWarnings": build_spread_warnings(
            label_spread,
            uncertainty_rate,
            proposal_summary=proposal_summary,
        ),
    }


def build_acceptance_calibration_summary(records: list[ShadowClipRecord]) -> dict[str, Any] | None:
    scored = [
        record
        for record in records
        if record.expectedEventFamily is not None and record.proposalAcceptanceProbability is not None
    ]
    if not scored:
        return None

    def correctness(record: ShadowClipRecord) -> float:
        return 1.0 if normalize_bucket(record.expectedEventFamily) != "other" else 0.0

    total = len(scored)
    brier = round(
        sum((float(record.proposalAcceptanceProbability) - correctness(record)) ** 2 for record in scored) / total,
        4,
    )
    bins: list[dict[str, Any]] = []
    bin_edges = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.000001)]
    for lower, upper in bin_edges:
        bucket = [
            record
            for record in scored
            if lower <= float(record.proposalAcceptanceProbability) < upper
            or (upper > 1.0 and float(record.proposalAcceptanceProbability) == 1.0)
        ]
        if not bucket:
            bins.append(
                {
                    "bin": f"[{lower:.1f},{upper:.1f})",
                    "count": 0,
                    "accuracy": None,
                    "meanConfidence": None,
                    "risk": None,
                }
            )
            continue
        mean_confidence = sum(float(record.proposalAcceptanceProbability) for record in bucket) / len(bucket)
        accuracy = sum(correctness(record) for record in bucket) / len(bucket)
        bins.append(
            {
                "bin": f"[{lower:.1f},{upper:.1f})",
                "count": len(bucket),
                "accuracy": round(accuracy, 4),
                "meanConfidence": round(mean_confidence, 4),
                "risk": round(1.0 - accuracy, 4),
            }
        )

    ece_lite = round(
        sum(
            (bin_entry["count"] / total) * abs(bin_entry["accuracy"] - bin_entry["meanConfidence"])
            for bin_entry in bins
            if bin_entry["count"] > 0 and bin_entry["accuracy"] is not None and bin_entry["meanConfidence"] is not None
        ),
        4,
    )
    coverage_curve = []
    ordered = sorted(scored, key=lambda record: float(record.proposalAcceptanceProbability), reverse=True)
    for index, _ in enumerate(ordered, start=1):
        covered = ordered[:index]
        accuracy = sum(correctness(record) for record in covered) / len(covered)
        coverage_curve.append(
            {
                "coverage": round(index / total, 4),
                "risk": round(1.0 - accuracy, 4),
                "count": len(covered),
            }
        )

    return {
        "scoredClips": total,
        "brierScore": brier,
        "eceLite": ece_lite,
        "reliabilityBuckets": bins,
        "coverageRiskCurve": coverage_curve,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = ["# Shadow Eval Report", ""]
    lines.append(f"- Jobs: `{summary['jobCount']}`")
    lines.append(f"- Clips: `{summary['clipCount']}`")
    lines.append(f"- Uncertainty rate: `{summary['uncertaintyRate']:.4f}`")
    lines.append(f"- Raw eventFamily=other rate: `{summary['rawEventFamilyOtherRate']:.4f}`")
    lines.append(f"- Highlight dominance: `{summary['highlightDominance']:.4f}`")
    lines.append(f"- EventFamily=other dominance: `{summary['eventFamilyOtherDominance']:.4f}`")
    lines.append(f"- Dominant flat label: `{summary['dominantFlatLabel']}`")
    lines.append(f"- Dominant flat-label share: `{summary['dominantFlatLabelShare']:.4f}`")
    lines.append(f"- Proposal acceptance rate: `{summary.get('proposalAcceptanceRate')}`")
    lines.append(f"- Family gate open rate: `{summary.get('familyGateOpenRate')}`")
    lines.append(f"- Shot head invocation rate: `{summary.get('shotHeadInvocationRate')}`")
    lines.append(f"- Eventness calibration: `{json.dumps(summary.get('eventnessCalibration'), sort_keys=True)}`")
    lines.append(f"- Acceptance calibration: `{json.dumps(summary.get('acceptanceCalibration'), sort_keys=True)}`")
    lines.append(
        f"- Accepted-shot outcome calibration: `{json.dumps(summary.get('acceptedShotOutcomeCalibration'), sort_keys=True)}`"
    )
    lines.append(f"- Split-other distribution: `{json.dumps(summary['splitOtherDistribution'], sort_keys=True)}`")
    lines.append(f"- Candidate namespace: `{summary['candidateNamespaces']['dominantNamespace']}`")
    lines.append(f"- Mixed-batch unique labels: `{summary['mixedBatchLabelSpread']['uniqueLabelCount']}`")
    lines.append(
        f"- Dominant flat label: `{summary['mixedBatchLabelSpread']['dominantLabel']}` "
        f"({summary['mixedBatchLabelSpread']['dominantLabelShare']:.2%})"
    )
    lines.append(
        f"- Duration median: `{summary['durationSummary']['medianSeconds']:.2f}s`, "
        f"p90: `{summary['durationSummary']['p90Seconds']:.2f}s`"
    )
    lines.append("")
    lines.append("## Distributions")
    lines.append(f"- Flat labels: `{json.dumps(summary['flatLabelDistribution'], sort_keys=True)}`")
    lines.append(f"- Event families: `{json.dumps(summary['eventFamilyDistribution'], sort_keys=True)}`")
    lines.append(f"- Shot subtypes: `{json.dumps(summary['shotSubtypeDistribution'], sort_keys=True)}`")
    lines.append(f"- Outcomes: `{json.dumps(summary['outcomeDistribution'], sort_keys=True)}`")
    lines.append(f"- Source domains: `{json.dumps(summary['sourceDomainDistribution'], sort_keys=True)}`")
    lines.append(f"- Other audit: `{json.dumps(summary['otherBucketAudit'], sort_keys=True)}`")
    lines.append(
        f"- Accepted-shot outcome accuracy: `{summary.get('acceptedShotProposalOutcomeAccuracy')}`"
    )
    lines.append(
        f"- Accepted-shot subtype distribution: `{json.dumps(summary.get('acceptedShotSubtypeDistribution'), sort_keys=True)}`"
    )
    lines.append(f"- Accepted-shot abstention rate: `{summary.get('acceptedShotAbstentionRate')}`")
    lines.append(f"- Dunk dominance: `{summary.get('dunkDominance')}`")
    lines.append(f"- Rejected proposal audit: `{json.dumps(summary.get('rejectedProposalAudit'), sort_keys=True)}`")
    lines.append(f"- Miss-vs-made confusion: `{json.dumps(summary['missVsMadeConfusion'], sort_keys=True)}`")
    if summary.get("labeledClipCount", 0) > 0:
        lines.append(
            f"- Event spotter precision / recall: "
            f"`{summary['eventSpotterPrecision']}` / `{summary['eventSpotterRecall']}`"
        )
        lines.append(
            f"- Event detection precision / recall: "
            f"`{summary['eventDetectionPrecision']}` / `{summary['eventDetectionRecall']}`"
        )
        lines.append(f"- Event family accuracy: `{summary['eventFamilyAccuracy']}`")
        lines.append(f"- Outcome accuracy: `{summary['outcomeAccuracy']}`")
        lines.append(f"- Shot subtype accuracy: `{summary['shotSubtypeAccuracy']}`")
    lines.append("")
    if report.get("baselineSummary") and report.get("comparisonSummary"):
        baseline = report["baselineSummary"]
        comparison = report["comparisonSummary"]
        lines.append("## Comparison vs Baseline")
        lines.append(
            f"- Baseline candidate namespace: `{baseline.get('candidateNamespaces', {}).get('dominantNamespace', 'unknown')}`"
        )
        lines.append(
            f"- Candidate namespace: `{summary['candidateNamespaces']['dominantNamespace']}`"
        )
        lines.append(
            f"- Baseline flat labels: `{json.dumps(baseline['flatLabelDistribution'], sort_keys=True)}`"
        )
        lines.append(
            f"- Candidate flat labels: `{json.dumps(summary['flatLabelDistribution'], sort_keys=True)}`"
        )
        lines.append(
            f"- Flat label spread delta: `{comparison['mixedBatchLabelSpread']['spreadScoreDelta']:+.4f}`"
        )
        lines.append(
            f"- Highlight share delta: `{comparison['flatLabel']['highlightShareDelta']:+.4f}`"
        )
        lines.append(
            f"- Uncertainty delta: `{comparison['uncertaintyRateDelta']:+.4f}`"
        )
        lines.append(
            f"- Miss-vs-made delta: `{json.dumps(comparison['missVsMadeConfusionDelta'], sort_keys=True)}`"
        )
        lines.append("")
    lines.append("## Mixed Batch Spread")
    lines.append(f"- Spread score: `{summary['mixedBatchLabelSpread']['spreadScore']:.4f}`")
    lines.append(f"- Top labels: `{json.dumps(summary['mixedBatchLabelSpread']['topLabels'], sort_keys=True)}`")
    lines.append("")
    lines.append("## Clip Table")
    lines.append(
        "| clipId | jobId | requestId | uploadTraceId | inferenceAttemptId | candidateNamespace | modelVersion | flatLabel | eventFamily | proposalAccepted | familyGateOpen | familyGateRejectionReason | shotHeadInvoked | proposalRejector | proposalEventScore | proposalAcceptanceRawScore | proposalAcceptanceProbability | proposalEnergyScore | otherBucket | manualAudit | shotSubtype | outcome | confidenceBeforeMapping | confidenceAfterMapping | confidence | durationSeconds | merged | sourceEventCount | uncertain | rawVideoMAETop1 | rawXCLIPTop1 |"
    )
    lines.append(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    )
    for clip in report["clips"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md_cell(clip.get("clipId")),
                    escape_md_cell(clip.get("jobId")),
                    escape_md_cell(clip.get("requestId")),
                    escape_md_cell(clip.get("uploadTraceId")),
                    escape_md_cell(clip.get("inferenceAttemptId")),
                    escape_md_cell(clip.get("candidateNamespace")),
                    escape_md_cell(clip.get("modelVersion")),
                    escape_md_cell(clip.get("flatLabel")),
                    escape_md_cell(clip.get("eventFamily")),
                    escape_md_cell(clip.get("proposalAccepted")),
                    escape_md_cell(clip.get("familyGateOpen")),
                    escape_md_cell(clip.get("familyGateRejectionReason")),
                    escape_md_cell(clip.get("shotHeadInvoked")),
                    escape_md_cell(clip.get("proposalRejectorLabel")),
                    escape_md_cell(clip.get("proposalScore")),
                    escape_md_cell(clip.get("proposalAcceptanceRawScore")),
                    escape_md_cell(clip.get("proposalAcceptanceProbability")),
                    escape_md_cell(clip.get("proposalEnergyScore")),
                    escape_md_cell(clip.get("otherBucket")),
                    escape_md_cell(clip.get("manualAuditLabel")),
                    escape_md_cell(clip.get("shotSubtype")),
                    escape_md_cell(clip.get("outcome")),
                    escape_md_cell(clip.get("confidenceBeforeMapping")),
                    escape_md_cell(clip.get("confidenceAfterMapping")),
                    escape_md_cell(clip.get("confidence")),
                    escape_md_cell(clip.get("clipDurationSeconds")),
                    escape_md_cell(clip.get("wasMerged")),
                    escape_md_cell(clip.get("sourceEventCount")),
                    escape_md_cell(clip.get("isUncertain")),
                    escape_md_cell(first_label(clip.get("rawVideoMAETopK", []))),
                    escape_md_cell(first_label(clip.get("rawXCLIPSuggestions", []))),
                ]
            )
            + " |"
        )
    if report["collapseExamples"]:
        lines.append("")
        lines.append("## Collapse Examples")
        for item in report["collapseExamples"][:8]:
            lines.append(
                f"- `{item['clipId']}`: raw diversity `{item['rawDiversity']}` -> final `{item['flatLabel']}`"
            )
    if report["labelSpreadWarnings"]:
        lines.append("")
        lines.append("## Warnings")
        for warning in report["labelSpreadWarnings"]:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def _extract_top_level_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("clips"), list):
            return [payload]
        if isinstance(payload.get("result"), dict) and isinstance(payload["result"].get("clips"), list):
            merged = dict(payload)
            merged["clips"] = payload["result"]["clips"]
            return [merged]
        if isinstance(payload.get("results"), dict) and isinstance(payload["results"].get("clips"), list):
            merged = dict(payload)
            merged["clips"] = payload["results"]["clips"]
            return [merged]
        return [payload]
    raise ValueError("Batch results must be a JSON object or array.")


def _normalize_batch_item(
    item: dict[str, Any],
    *,
    shadow_source: str = "auto",
    manual_audits: dict[str, dict[str, str | None]] | None = None,
) -> list[ShadowClipRecord]:
    top_job_id = _first_non_empty(item.get("jobId"), item.get("id"))
    top_request_id = _first_non_empty(item.get("requestId"), item.get("traceId"))
    top_upload_trace_id = _first_non_empty(item.get("uploadTraceId"), item.get("traceId"))
    top_attempt_id = _first_non_empty(item.get("inferenceAttemptId"), item.get("attemptId"))
    top_model_version = _first_non_empty(item.get("modelVersion"), item.get("version"))
    clips = item.get("clips")
    if not isinstance(clips, list) or not clips:
        clips = [item]
    records: list[ShadowClipRecord] = []
    for clip_index, clip in enumerate(clips):
        if not isinstance(clip, dict):
            continue
        shadow_namespace, shadow_payload = _resolve_shadow_payload(clip, shadow_source=shadow_source)
        clip_identifier = _resolve_clip_identifier(
            clip,
            clip_index=clip_index,
            job_id=_first_non_empty(clip.get("jobId"), top_job_id),
        )
        audit_override = (manual_audits or {}).get(clip_identifier, {})
        records.append(
            ShadowClipRecord(
                jobId=_first_non_empty(clip.get("jobId"), top_job_id),
                clipId=clip_identifier,
                requestId=_first_non_empty(clip.get("requestId"), top_request_id),
                uploadTraceId=_first_non_empty(clip.get("uploadTraceId"), top_upload_trace_id),
                inferenceAttemptId=_first_non_empty(clip.get("inferenceAttemptId"), top_attempt_id),
                modelVersion=_first_non_empty(
                    shadow_payload.get("modelVersion") if shadow_payload else None,
                    shadow_payload.get("runtime_fusion_model_version") if shadow_payload else None,
                    clip.get("modelVersion"),
                    top_model_version,
                ),
                flatLabel=_normalize_flat_label(clip, shadow_payload),
                eventFamily=_normalize_event_family(clip, shadow_payload),
                eventSpotterFamily=_normalize_event_spotter_family(clip, shadow_payload),
                otherBucket=_normalize_other_bucket(clip, shadow_payload),
                otherBucketReason=_normalize_other_bucket_reason(clip, shadow_payload),
                shotSubtype=_normalize_shot_subtype(clip, shadow_payload),
                outcome=_normalize_outcome(clip, shadow_payload),
                confidence=_normalize_confidence(clip, shadow_payload),
                confidenceBeforeMapping=_to_optional_float(
                    _first_defined(
                        shadow_payload.get("confidenceBeforeMapping") if shadow_payload else None,
                        shadow_payload.get("confidence_before_mapping") if shadow_payload else None,
                        clip.get("confidenceBeforeMapping"),
                        clip.get("confidence_before_mapping"),
                    )
                ),
                confidenceAfterMapping=_to_optional_float(
                    _first_defined(
                        shadow_payload.get("confidenceAfterMapping") if shadow_payload else None,
                        shadow_payload.get("confidence_after_mapping") if shadow_payload else None,
                        clip.get("confidenceAfterMapping"),
                        clip.get("confidence_after_mapping"),
                    )
                ),
                resultConfidence=_to_optional_float(clip.get("resultConfidence")),
                candidateNamespace=shadow_namespace or shadow_source,
                proposalAccepted=_normalize_proposal_accepted(clip, shadow_payload),
                proposalScore=_normalize_proposal_event_score(clip, shadow_payload),
                proposalAcceptanceRawScore=_normalize_proposal_acceptance_raw_score(clip, shadow_payload),
                proposalAcceptanceProbability=_normalize_proposal_acceptance_probability(clip, shadow_payload),
                proposalEnergyScore=_normalize_proposal_energy_score(clip, shadow_payload),
                proposalRejectorLabel=_normalize_proposal_rejector_label(clip, shadow_payload),
                proposalRejectorConfidence=_normalize_proposal_rejector_confidence(clip, shadow_payload),
                familyGateOpen=_normalize_family_gate_open(clip, shadow_payload),
                familyGateRejectionReason=_normalize_family_gate_rejection_reason(clip, shadow_payload),
                shotHeadInvoked=_normalize_shot_head_invoked(clip, shadow_payload),
                shotSpecialistUsed=_normalize_shot_specialist_used(clip, shadow_payload),
                shotSpecialistAbstained=_normalize_shot_specialist_abstained(clip, shadow_payload),
                clipDurationSeconds=_to_optional_float(clip.get("clipDurationSeconds")),
                wasMerged=bool(clip.get("wasMerged", False)),
                sourceEventCount=_to_optional_int(clip.get("sourceEventCount")),
                isUncertain=_normalize_uncertain(clip, shadow_payload),
                rawVideoMAETopK=_normalize_top_k(
                    (
                        shadow_payload.get("runtime_fusion_snapshot", {}).get("videoMAE")
                        if isinstance(shadow_payload, dict)
                        else None
                    )
                    or clip.get("rawVideoMAETopK")
                    or clip.get("rawTopLabels")
                    or clip.get("videoMAE", {}).get("topK")
                    or []
                ),
                rawXCLIPSuggestions=_normalize_top_k(
                    (
                        shadow_payload.get("runtime_fusion_snapshot", {}).get("xclip")
                        if isinstance(shadow_payload, dict)
                        else None
                    )
                    or clip.get("rawXCLIPSuggestions")
                    or clip.get("comparisonRawTopLabels")
                    or clip.get("xclip", {}).get("topK")
                    or []
                ),
                expectedLabel=_first_non_empty(clip.get("expectedLabel"), clip.get("goldLabel"), clip.get("targetLabel")),
                expectedEventFamily=_first_non_empty(clip.get("expectedEventFamily"), item.get("expectedEventFamily")),
                expectedOutcome=_first_non_empty(clip.get("expectedOutcome"), item.get("expectedOutcome")),
                expectedShotSubtype=_first_non_empty(clip.get("expectedShotSubtype"), item.get("expectedShotSubtype")),
                sourceDomain=_first_non_empty(clip.get("sourceDomain"), item.get("sourceDomain")),
                manualAuditLabel=_normalize_other_audit_label(clip, shadow_payload, audit_override),
                manualAuditRationale=_normalize_other_audit_rationale(clip, shadow_payload, audit_override),
            )
        )
    return records


def _resolve_clip_identifier(clip: dict[str, Any], *, clip_index: int, job_id: Any) -> str:
    clip_id = _first_non_empty(clip.get("clipId"), clip.get("id"))
    if clip_id is not None:
        return str(clip_id)
    if job_id is not None:
        return f"{job_id}:clip-{clip_index + 1}"
    return f"unknown:clip-{clip_index + 1}"


def load_manual_audits(paths: Iterable[Path]) -> dict[str, dict[str, str | None]]:
    audit_map: dict[str, dict[str, str | None]] = {}
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Missing manual audit file: {path}")
        raw_text = path.read_text(encoding="utf-8").strip()
        if not raw_text:
            continue
        entries: list[dict[str, Any]]
        if path.suffix == ".jsonl":
            entries = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
        else:
            payload = json.loads(raw_text)
            if isinstance(payload, dict):
                candidate_entries = payload.get("records") or payload.get("audits") or payload.get("clips") or []
                entries = candidate_entries if isinstance(candidate_entries, list) else [payload]
            elif isinstance(payload, list):
                entries = payload
            else:
                raise ValueError(f"Unsupported manual audit payload: {path}")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            clip_id = _first_non_empty(entry.get("clipId"), entry.get("clip_id"))
            if clip_id is None:
                continue
            audit_map[clip_id] = {
                "manualAuditLabel": _normalize_other_audit_label(entry, None, {}),
                "manualAuditRationale": _normalize_other_audit_rationale(entry, None, {}),
            }
    return audit_map


def build_trace_summary(records: list[ShadowClipRecord]) -> dict[str, list[str]]:
    return {
        "jobIds": unique_values(record.jobId for record in records),
        "requestIds": unique_values(record.requestId for record in records),
        "uploadTraceIds": unique_values(record.uploadTraceId for record in records),
        "inferenceAttemptIds": unique_values(record.inferenceAttemptId for record in records),
        "modelVersions": unique_values(record.modelVersion for record in records),
        "candidateNamespaces": unique_values(record.candidateNamespace for record in records),
    }


def build_namespace_summary(values: Iterable[str | None]) -> dict[str, Any]:
    counts = Counter(normalize_bucket(value) for value in values)
    if not counts:
        return {
            "dominantNamespace": "unknown",
            "dominantNamespaceShare": 0.0,
            "namespaceCounts": {},
        }
    dominant_namespace, dominant_count = max(counts.items(), key=lambda item: (item[1], item[0]))
    total = max(sum(counts.values()), 1)
    return {
        "dominantNamespace": dominant_namespace,
        "dominantNamespaceShare": round(dominant_count / total, 4),
        "namespaceCounts": dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))),
    }


def build_label_spread(records: list[ShadowClipRecord], label_distribution: dict[str, int]) -> dict[str, Any]:
    total = max(len(records), 1)
    unique_label_count = len(label_distribution)
    dominant_label, dominant_count = ("", 0)
    if label_distribution:
        dominant_label, dominant_count = max(label_distribution.items(), key=lambda item: (item[1], item[0]))
    entropy = 0.0
    for count in label_distribution.values():
        if count <= 0:
            continue
        probability = count / total
        entropy -= probability * __import__("math").log(probability, 2)
    spread_score = round(1.0 - (dominant_count / total), 4) if total else 0.0
    return {
        "uniqueLabelCount": unique_label_count,
        "dominantLabel": dominant_label or "unknown",
        "dominantLabelShare": round(dominant_count / total, 4) if total else 0.0,
        "entropy": round(entropy, 4),
        "spreadScore": spread_score,
        "topLabels": sorted(label_distribution.items(), key=lambda item: (-item[1], item[0]))[:8],
    }


def build_miss_vs_made_confusion(records: list[ShadowClipRecord]) -> dict[str, int]:
    counts = Counter(
        {
            "expectedMissPredictedMadeShot": 0,
            "expectedMadePredictedMiss": 0,
            "expectedMissPredictedHighlight": 0,
            "expectedMadePredictedHighlight": 0,
        }
    )
    for record in records:
        expected = normalize_expected_label(record.expectedLabel)
        predicted = normalize_expected_label(record.flatLabel)
        if expected == "miss" and predicted == "made shot":
            counts["expectedMissPredictedMadeShot"] += 1
        elif expected == "made shot" and predicted == "miss":
            counts["expectedMadePredictedMiss"] += 1
        elif expected == "miss" and predicted == "highlight":
            counts["expectedMissPredictedHighlight"] += 1
        elif expected == "made shot" and predicted == "highlight":
            counts["expectedMadePredictedHighlight"] += 1
    return dict(counts)


def build_labeled_eval_summary(records: list[ShadowClipRecord]) -> dict[str, Any]:
    labeled = [record for record in records if record.expectedEventFamily]
    if not labeled:
        return {
            "labeledClipCount": 0,
            "eventSpotterPrecision": None,
            "eventSpotterRecall": None,
            "eventDetectionPrecision": None,
            "eventDetectionRecall": None,
            "eventFamilyAccuracy": None,
            "outcomeAccuracy": None,
            "shotSubtypeAccuracy": None,
        }

    actual_positive = [record for record in labeled if normalize_bucket(record.expectedEventFamily) != "other"]
    predicted_positive = [record for record in labeled if normalize_bucket(_spotter_family(record)) != "other"]
    true_positive = [
        record
        for record in labeled
        if normalize_bucket(record.expectedEventFamily) != "other" and normalize_bucket(_spotter_family(record)) != "other"
    ]
    precision = round(len(true_positive) / len(predicted_positive), 4) if predicted_positive else None
    recall = round(len(true_positive) / len(actual_positive), 4) if actual_positive else None
    event_family_accuracy = round(
        sum(1 for record in labeled if normalize_bucket(record.expectedEventFamily) == normalize_bucket(record.eventFamily))
        / len(labeled),
        4,
    )

    outcome_labeled = [record for record in labeled if record.expectedOutcome]
    outcome_accuracy = (
        round(
            sum(1 for record in outcome_labeled if normalize_bucket(record.expectedOutcome) == normalize_bucket(record.outcome))
            / len(outcome_labeled),
            4,
        )
        if outcome_labeled
        else None
    )

    subtype_labeled = [record for record in labeled if record.expectedShotSubtype]
    shot_subtype_accuracy = (
        round(
            sum(
                1
                for record in subtype_labeled
                if normalize_bucket(record.expectedShotSubtype) == normalize_bucket(record.shotSubtype)
            )
            / len(subtype_labeled),
            4,
        )
        if subtype_labeled
        else None
    )

    return {
        "labeledClipCount": len(labeled),
        "eventSpotterPrecision": precision,
        "eventSpotterRecall": recall,
        "eventDetectionPrecision": precision,
        "eventDetectionRecall": recall,
        "eventFamilyAccuracy": event_family_accuracy,
        "outcomeAccuracy": outcome_accuracy,
        "shotSubtypeAccuracy": shot_subtype_accuracy,
    }


def build_proposal_summary(records: list[ShadowClipRecord]) -> dict[str, Any]:
    eligible_records = [record for record in records if record.proposalAccepted is not None]
    proposal_acceptance_rate = (
        round(sum(1 for record in eligible_records if record.proposalAccepted) / len(eligible_records), 4)
        if eligible_records
        else None
    )
    proposal_accepted_count = sum(1 for record in eligible_records if record.proposalAccepted)
    family_gate_records = [record for record in records if record.familyGateOpen is not None]
    family_gate_open_count = sum(1 for record in family_gate_records if record.familyGateOpen)
    family_gate_open_rate = (
        round(family_gate_open_count / len(family_gate_records), 4) if family_gate_records else None
    )
    shot_head_records = [record for record in records if record.shotHeadInvoked is not None]
    shot_head_invocation_count = sum(1 for record in shot_head_records if record.shotHeadInvoked)
    shot_head_invocation_rate = (
        round(shot_head_invocation_count / len(shot_head_records), 4) if shot_head_records else None
    )

    labeled_scored = [
        record
        for record in eligible_records
        if record.expectedEventFamily is not None and record.proposalAcceptanceProbability is not None
    ]
    if labeled_scored:
        positive_rows = [record for record in labeled_scored if normalize_bucket(record.expectedEventFamily) != "other"]
        negative_rows = [record for record in labeled_scored if normalize_bucket(record.expectedEventFamily) == "other"]
        eventness_brier = round(
            sum(
                (float(record.proposalAcceptanceProbability) - (1.0 if normalize_bucket(record.expectedEventFamily) != "other" else 0.0)) ** 2
                for record in labeled_scored
            )
            / len(labeled_scored),
            4,
        )
        eventness_calibration = {
            "eligibleClips": len(labeled_scored),
            "brierScore": eventness_brier,
            "positiveMeanScore": round(
                sum(float(record.proposalAcceptanceProbability) for record in positive_rows) / len(positive_rows),
                4,
            )
            if positive_rows
            else None,
            "negativeMeanScore": round(
                sum(float(record.proposalAcceptanceProbability) for record in negative_rows) / len(negative_rows),
                4,
            )
            if negative_rows
            else None,
        }
    else:
        eventness_calibration = None
    acceptance_calibration = build_acceptance_calibration_summary(eligible_records)

    accepted_shot_rows = [
        record
        for record in eligible_records
        if record.proposalAccepted
        and (record.familyGateOpen is True if record.familyGateOpen is not None else True)
        and normalize_bucket(record.expectedEventFamily) == "shot_attempt"
        and record.expectedOutcome is not None
    ]
    accepted_shot_outcome_accuracy = (
        round(
            sum(1 for record in accepted_shot_rows if normalize_bucket(record.expectedOutcome) == normalize_bucket(record.outcome))
            / len(accepted_shot_rows),
            4,
        )
        if accepted_shot_rows
        else None
    )
    accepted_shot_outcome_calibration = build_outcome_calibration_summary(accepted_shot_rows)
    accepted_shot_subtype_distribution = distribution(
        (record.shotSubtype or "null") for record in accepted_shot_rows
    )
    accepted_shot_abstention_rate = (
        round(
            sum(
                1
                for record in accepted_shot_rows
                if record.shotSpecialistAbstained is True
                or normalize_bucket(record.shotSubtype or "null") in {"null", "uncertain"}
            )
            / len(accepted_shot_rows),
            4,
        )
        if accepted_shot_rows
        else None
    )
    dunk_dominance = (
        round(
            sum(1 for record in accepted_shot_rows if normalize_text(record.flatLabel) == "dunk")
            / len(accepted_shot_rows),
            4,
        )
        if accepted_shot_rows
        else None
    )

    rejected_labeled_rows = [
        record
        for record in eligible_records
        if record.proposalAccepted is False and record.expectedEventFamily is not None
    ]
    rejected_true_negative = sum(1 for record in rejected_labeled_rows if normalize_bucket(record.expectedEventFamily) == "other")
    rejected_true_miss = sum(1 for record in rejected_labeled_rows if normalize_bucket(record.expectedEventFamily) != "other")
    rejected_proposal_audit = {
        "eligibleRejectedClips": len(rejected_labeled_rows),
        "trueNegativeCount": rejected_true_negative,
        "trueMissCount": rejected_true_miss,
        "trueNegativeRate": round(rejected_true_negative / len(rejected_labeled_rows), 4) if rejected_labeled_rows else None,
        "trueMissRate": round(rejected_true_miss / len(rejected_labeled_rows), 4) if rejected_labeled_rows else None,
    }

    return {
        "proposalAcceptanceRate": proposal_acceptance_rate,
        "proposalAcceptanceClipCount": len(eligible_records),
        "proposalAcceptedCount": proposal_accepted_count,
        "familyGateOpenRate": family_gate_open_rate,
        "familyGateOpenClipCount": len(family_gate_records),
        "familyGateOpenCount": family_gate_open_count,
        "shotHeadInvocationRate": shot_head_invocation_rate,
        "shotHeadInvocationClipCount": len(shot_head_records),
        "shotHeadInvocationCount": shot_head_invocation_count,
        "eventnessCalibration": eventness_calibration,
        "acceptanceCalibration": acceptance_calibration,
        "acceptedShotProposalOutcomeAccuracy": accepted_shot_outcome_accuracy,
        "acceptedShotOutcomeCalibration": accepted_shot_outcome_calibration,
        "acceptedShotSubtypeDistribution": accepted_shot_subtype_distribution,
        "acceptedShotAbstentionRate": accepted_shot_abstention_rate,
        "dunkDominance": dunk_dominance,
        "rejectedProposalAudit": rejected_proposal_audit,
    }


def build_acceptance_calibration_summary(records: list[ShadowClipRecord]) -> dict[str, Any] | None:
    scored = [
        record
        for record in records
        if record.proposalAccepted is not None and record.proposalAcceptanceProbability is not None
    ]
    if not scored:
        return None

    def correctness(record: ShadowClipRecord) -> float:
        return 1.0 if bool(record.proposalAccepted) else 0.0

    total = len(scored)
    brier = round(
        sum((float(record.proposalAcceptanceProbability) - correctness(record)) ** 2 for record in scored) / total,
        4,
    )
    bins: list[dict[str, Any]] = []
    bin_edges = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.000001)]
    for lower, upper in bin_edges:
        bucket = [
            record
            for record in scored
            if lower <= float(record.proposalAcceptanceProbability) < upper
            or (upper > 1.0 and float(record.proposalAcceptanceProbability) == 1.0)
        ]
        if not bucket:
            bins.append(
                {
                    "bin": f"[{lower:.1f},{upper:.1f})",
                    "count": 0,
                    "accuracy": None,
                    "meanProbability": None,
                    "risk": None,
                }
            )
            continue
        mean_probability = sum(float(record.proposalAcceptanceProbability) for record in bucket) / len(bucket)
        accuracy = sum(correctness(record) for record in bucket) / len(bucket)
        bins.append(
            {
                "bin": f"[{lower:.1f},{upper:.1f})",
                "count": len(bucket),
                "accuracy": round(accuracy, 4),
                "meanProbability": round(mean_probability, 4),
                "risk": round(1.0 - accuracy, 4),
            }
        )

    ece_lite = round(
        sum(
            (bin_entry["count"] / total) * abs(bin_entry["accuracy"] - bin_entry["meanProbability"])
            for bin_entry in bins
            if bin_entry["count"] > 0 and bin_entry["accuracy"] is not None and bin_entry["meanProbability"] is not None
        ),
        4,
    )
    coverage_curve = []
    ordered = sorted(scored, key=lambda record: float(record.proposalAcceptanceProbability), reverse=True)
    for index, _ in enumerate(ordered, start=1):
        covered = ordered[:index]
        accuracy = sum(correctness(record) for record in covered) / len(covered)
        coverage_curve.append(
            {
                "coverage": round(index / total, 4),
                "risk": round(1.0 - accuracy, 4),
                "count": len(covered),
            }
        )

    return {
        "scoredClips": total,
        "brierScore": brier,
        "eceLite": ece_lite,
        "reliabilityBuckets": bins,
        "coverageRiskCurve": coverage_curve,
    }


def build_outcome_calibration_summary(records: list[ShadowClipRecord]) -> dict[str, Any] | None:
    scored = [
        record
        for record in records
        if record.expectedOutcome is not None and record.confidenceAfterMapping is not None
    ]
    if not scored:
        return None

    def correctness(record: ShadowClipRecord) -> float:
        return 1.0 if normalize_bucket(record.expectedOutcome) == normalize_bucket(record.outcome) else 0.0

    total = len(scored)
    brier = round(
        sum((float(record.confidenceAfterMapping) - correctness(record)) ** 2 for record in scored) / total,
        4,
    )
    bins: list[dict[str, Any]] = []
    bin_edges = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.000001)]
    for lower, upper in bin_edges:
        bucket = [
            record
            for record in scored
            if lower <= float(record.confidenceAfterMapping) < upper
            or (upper > 1.0 and float(record.confidenceAfterMapping) == 1.0)
        ]
        if not bucket:
            bins.append(
                {
                    "bin": f"[{lower:.1f},{upper:.1f})",
                    "count": 0,
                    "accuracy": None,
                    "meanConfidence": None,
                    "risk": None,
                }
            )
            continue
        mean_confidence = sum(float(record.confidenceAfterMapping) for record in bucket) / len(bucket)
        accuracy = sum(correctness(record) for record in bucket) / len(bucket)
        bins.append(
            {
                "bin": f"[{lower:.1f},{upper:.1f})",
                "count": len(bucket),
                "accuracy": round(accuracy, 4),
                "meanConfidence": round(mean_confidence, 4),
                "risk": round(1.0 - accuracy, 4),
            }
        )

    ece_lite = round(
        sum(
            (bin_entry["count"] / total) * abs(bin_entry["accuracy"] - bin_entry["meanConfidence"])
            for bin_entry in bins
            if bin_entry["count"] > 0 and bin_entry["accuracy"] is not None and bin_entry["meanConfidence"] is not None
        ),
        4,
    )
    coverage_curve = []
    ordered = sorted(scored, key=lambda record: float(record.confidenceAfterMapping), reverse=True)
    for index, _ in enumerate(ordered, start=1):
        covered = ordered[:index]
        accuracy = sum(correctness(record) for record in covered) / len(covered)
        coverage_curve.append(
            {
                "coverage": round(index / total, 4),
                "risk": round(1.0 - accuracy, 4),
                "count": len(covered),
            }
        )

    return {
        "scoredClips": total,
        "brierScore": brier,
        "eceLite": ece_lite,
        "reliabilityBuckets": bins,
        "coverageRiskCurve": coverage_curve,
    }


def build_other_bucket_distribution(records: list[ShadowClipRecord]) -> dict[str, int]:
    other_records = [record for record in records if normalize_bucket(record.eventFamily) == "other"]
    return distribution(record.otherBucket for record in other_records if record.otherBucket)


def build_other_bucket_audit(records: list[ShadowClipRecord]) -> dict[str, Any]:
    other_records = [record for record in records if normalize_bucket(record.eventFamily) == "other"]
    audited_records = [record for record in other_records if record.manualAuditLabel]
    total_records = max(len(records), 1)
    audit_distribution = distribution(record.manualAuditLabel for record in audited_records)
    true_negative_count = audit_distribution.get("true_negative_non_event", 0)
    true_model_miss_count = audit_distribution.get("real_event_missed_by_model", 0)
    return {
        "eligibleOtherClips": len(other_records),
        "auditedOtherClips": len(audited_records),
        "unauditedOtherClips": max(len(other_records) - len(audited_records), 0),
        "manualAuditDistribution": audit_distribution,
        "trueNegativeRateWithinOther": round(true_negative_count / len(audited_records), 4) if audited_records else None,
        "trueModelMissRateWithinOther": round(true_model_miss_count / len(audited_records), 4) if audited_records else None,
        "trueNegativeShareOfBatch": round(true_negative_count / total_records, 4),
        "trueModelMissShareOfBatch": round(true_model_miss_count / total_records, 4),
    }


def _spotter_family(record: ShadowClipRecord) -> str:
    return record.eventSpotterFamily or record.eventFamily


def build_collapse_examples(records: list[ShadowClipRecord]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for record in records:
        raw_labels = [first_label(record.rawVideoMAETopK), first_label(record.rawXCLIPSuggestions)]
        diversity = len({label for label in raw_labels if label and label != "none"})
        if diversity >= 2 and record.flatLabel == "Highlight":
            examples.append(
                {
                    "clipId": record.clipId,
                    "flatLabel": record.flatLabel,
                    "rawDiversity": diversity,
                    "rawVideoMAETopK": record.rawVideoMAETopK[:3],
                    "rawXCLIPSuggestions": record.rawXCLIPSuggestions[:3],
                }
            )
    return examples


def build_spread_warnings(
    label_spread: dict[str, Any],
    uncertainty_rate: float,
    *,
    proposal_summary: dict[str, Any] | None = None,
) -> list[str]:
    warnings: list[str] = []
    if label_spread["uniqueLabelCount"] < 4:
        warnings.append("Mixed batch produced fewer than four flat labels.")
    if label_spread["dominantLabelShare"] > 0.5:
        warnings.append("One flat label still dominates more than half the batch.")
    if uncertainty_rate > 0.5:
        warnings.append("Uncertainty remains above 50% on this batch.")
    if proposal_summary:
        proposal_acceptance_rate = proposal_summary.get("proposalAcceptanceRate")
        proposal_acceptance_clip_count = int(proposal_summary.get("proposalAcceptanceClipCount") or 0)
        proposal_accepted_count = int(proposal_summary.get("proposalAcceptedCount") or 0)
        family_gate_open_count = int(proposal_summary.get("familyGateOpenCount") or 0)
        shot_head_invocation_count = int(proposal_summary.get("shotHeadInvocationCount") or 0)
        if proposal_acceptance_rate in {0.0, 1.0} and proposal_acceptance_clip_count > 0:
            warnings.append("Proposal acceptance collapsed to 0% or 100%.")
        if proposal_accepted_count > 0 and family_gate_open_count == 0:
            warnings.append("Accepted proposals exist, but family gate never opened.")
        if proposal_accepted_count > 0 and shot_head_invocation_count == 0:
            warnings.append("Accepted proposals exist, but shot head never invoked.")
    return warnings


def build_shadow_comparison_summary(baseline_summary: dict[str, Any], candidate_summary: dict[str, Any]) -> dict[str, Any]:
    baseline_clip_count = max(int(baseline_summary.get("clipCount", 0)), 1)
    candidate_clip_count = max(int(candidate_summary.get("clipCount", 0)), 1)
    baseline_flat = baseline_summary.get("flatLabelDistribution", {})
    candidate_flat = candidate_summary.get("flatLabelDistribution", {})
    baseline_spread = baseline_summary.get("mixedBatchLabelSpread", {})
    candidate_spread = candidate_summary.get("mixedBatchLabelSpread", {})
    return {
        "candidateNamespace": {
            "baseline": baseline_summary.get("candidateNamespaces", {}).get("dominantNamespace", "unknown"),
            "candidate": candidate_summary.get("candidateNamespaces", {}).get("dominantNamespace", "unknown"),
        },
        "flatLabel": {
            "baselineDominantLabel": baseline_spread.get("dominantLabel"),
            "candidateDominantLabel": candidate_spread.get("dominantLabel"),
            "baselineDominantLabelShare": baseline_spread.get("dominantLabelShare", 0.0),
            "candidateDominantLabelShare": candidate_spread.get("dominantLabelShare", 0.0),
            "dominantLabelShareDelta": round(
                float(candidate_spread.get("dominantLabelShare", 0.0))
                - float(baseline_spread.get("dominantLabelShare", 0.0)),
                4,
            ),
            "highlightShareBaseline": round(float(baseline_flat.get("Highlight", 0)) / baseline_clip_count, 4),
            "highlightShareCandidate": round(float(candidate_flat.get("Highlight", 0)) / candidate_clip_count, 4),
            "highlightShareDelta": round(
                float(candidate_flat.get("Highlight", 0)) / candidate_clip_count
                - float(baseline_flat.get("Highlight", 0)) / baseline_clip_count,
                4,
            ),
            "baselineDistribution": baseline_flat,
            "candidateDistribution": candidate_flat,
        },
        "eventFamily": {
            "baselineDistribution": baseline_summary.get("eventFamilyDistribution", {}),
            "candidateDistribution": candidate_summary.get("eventFamilyDistribution", {}),
        },
        "outcome": {
            "baselineDistribution": baseline_summary.get("outcomeDistribution", {}),
            "candidateDistribution": candidate_summary.get("outcomeDistribution", {}),
        },
        "shotSubtype": {
            "baselineDistribution": baseline_summary.get("shotSubtypeDistribution", {}),
            "candidateDistribution": candidate_summary.get("shotSubtypeDistribution", {}),
        },
        "mixedBatchLabelSpread": {
            "baselineUniqueLabelCount": baseline_spread.get("uniqueLabelCount", 0),
            "candidateUniqueLabelCount": candidate_spread.get("uniqueLabelCount", 0),
            "uniqueLabelCountDelta": int(candidate_spread.get("uniqueLabelCount", 0))
            - int(baseline_spread.get("uniqueLabelCount", 0)),
            "baselineSpreadScore": baseline_spread.get("spreadScore", 0.0),
            "candidateSpreadScore": candidate_spread.get("spreadScore", 0.0),
            "spreadScoreDelta": round(
                float(candidate_spread.get("spreadScore", 0.0)) - float(baseline_spread.get("spreadScore", 0.0)),
                4,
            ),
        },
        "uncertaintyRateDelta": round(
            float(candidate_summary.get("uncertaintyRate", 0.0)) - float(baseline_summary.get("uncertaintyRate", 0.0)),
            4,
        ),
        "missVsMadeConfusionDelta": {
            key: int(candidate_summary.get("missVsMadeConfusion", {}).get(key, 0))
            - int(baseline_summary.get("missVsMadeConfusion", {}).get(key, 0))
            for key in sorted(
                set(baseline_summary.get("missVsMadeConfusion", {})).union(
                    candidate_summary.get("missVsMadeConfusion", {})
                )
            )
        },
    }


def distribution(values: Iterable[Any]) -> dict[str, int]:
    counts = Counter(normalize_bucket(value) for value in values)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def normalize_bucket(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip()
    return text if text else "null"


def normalize_expected_label(value: str | None) -> str:
    text = normalize_text(value)
    if text in {"made shot", "made", "make"}:
        return "made shot"
    if text in {"miss", "missed", "highlight", "uncertain"}:
        return "miss" if text == "miss" or text == "missed" else "highlight"
    return text


def _normalize_flat_label(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> str:
    raw = _first_non_empty(
        shadow_payload.get("label") if shadow_payload else None,
        shadow_payload.get("displayLabel") if shadow_payload else None,
        clip.get("finalLabel"),
        clip.get("label"),
        clip.get("displayLabel"),
        clip.get("action"),
        "Highlight",
    )
    text = normalize_text(raw)
    if text in {"dunk", "layup", "three pointer", "three", "fast break", "block", "steal"}:
        return canonical_to_display_label(text if text != "three pointer" else "three")
    if text in {"made shot", "made"}:
        return "Made Shot"
    if text in {"miss", "missed", "highlight", "uncertain"}:
        return "Highlight"
    if text in {"three pointer", "3 pointer", "3 point"}:
        return "Three Pointer"
    if text in {"fastbreak"}:
        return "Fast Break"
    return str(raw)


def _normalize_event_family(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> str:
    value = _first_non_empty(
        shadow_payload.get("eventFamily") if shadow_payload else None,
        clip.get("eventFamily"),
        clip.get("eventType"),
    )
    family = normalize_text(value).replace(" ", "_")
    if family in EVENT_FAMILIES:
        return family
    return "other" if _normalize_flat_label(clip, shadow_payload) == "Highlight" else _taxonomy_from_label(_normalize_flat_label(clip, shadow_payload))[0]


def _normalize_event_spotter_family(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> str | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    value = _first_non_empty(
        shadow_payload.get("eventSpotterFamily") if shadow_payload else None,
        shadow_payload.get("temporal_event_detector_event_family") if shadow_payload else None,
        shadow_payload.get("temporal_student_event_spotter_family") if shadow_payload else None,
        metadata.get("temporal_event_detector_event_family") if isinstance(metadata, dict) else None,
        metadata.get("temporal_student_event_spotter_family") if isinstance(metadata, dict) else None,
        clip.get("eventSpotterFamily"),
    )
    text = normalize_text(value)
    family = text.replace(" ", "_")
    if family in EVENT_FAMILIES:
        return family
    return None


def _normalize_other_bucket(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> str | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    value = _first_non_empty(
        shadow_payload.get("eventFamilyOtherBucket") if shadow_payload else None,
        shadow_payload.get("temporal_student_other_bucket") if shadow_payload else None,
        metadata.get("eventFamilyOtherBucket") if isinstance(metadata, dict) else None,
        metadata.get("temporal_student_other_bucket") if isinstance(metadata, dict) else None,
        clip.get("eventFamilyOtherBucket"),
    )
    text = normalize_text(value).replace(" ", "_")
    return text if text in OTHER_BUCKETS else None


def _normalize_proposal_accepted(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> bool | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    value = _first_defined(
        shadow_payload.get("temporal_event_detector_proposal_accepted") if shadow_payload else None,
        shadow_payload.get("temporal_event_detector_gate_open") if shadow_payload else None,
        metadata.get("temporal_event_detector_proposal_accepted") if isinstance(metadata, dict) else None,
        metadata.get("temporal_event_detector_gate_open") if isinstance(metadata, dict) else None,
        clip.get("proposalAccepted"),
    )
    if value is None:
        return None
    return bool(value)


def _normalize_family_gate_open(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> bool | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    value = _first_defined(
        shadow_payload.get("temporal_event_detector_family_gate_open") if shadow_payload else None,
        shadow_payload.get("temporal_event_detector_classifier_gate_open") if shadow_payload else None,
        shadow_payload.get("temporal_event_detector_gate_open") if shadow_payload else None,
        metadata.get("temporal_event_detector_family_gate_open") if isinstance(metadata, dict) else None,
        metadata.get("temporal_event_detector_classifier_gate_open") if isinstance(metadata, dict) else None,
        metadata.get("temporal_event_detector_gate_open") if isinstance(metadata, dict) else None,
        clip.get("familyGateOpen"),
    )
    if value is None:
        return None
    return bool(value)


def _normalize_family_gate_rejection_reason(
    clip: dict[str, Any],
    shadow_payload: dict[str, Any] | None = None,
) -> str | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    return _first_non_empty(
        shadow_payload.get("temporal_event_detector_family_gate_rejection_reason") if shadow_payload else None,
        metadata.get("temporal_event_detector_family_gate_rejection_reason") if isinstance(metadata, dict) else None,
        clip.get("familyGateRejectionReason"),
    )


def _normalize_shot_head_invoked(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> bool | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    value = _first_defined(
        shadow_payload.get("temporal_event_detector_shot_head_invoked") if shadow_payload else None,
        shadow_payload.get("temporal_event_detector_shot_specialist_used") if shadow_payload else None,
        metadata.get("temporal_event_detector_shot_head_invoked") if isinstance(metadata, dict) else None,
        metadata.get("temporal_event_detector_shot_specialist_used") if isinstance(metadata, dict) else None,
        clip.get("shotHeadInvoked"),
        clip.get("shotSpecialistUsed"),
    )
    if value is None:
        return None
    return bool(value)


def _normalize_proposal_event_score(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> float | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    return _to_optional_float(
        _first_defined(
            shadow_payload.get("temporal_event_detector_proposal_acceptance_score") if shadow_payload else None,
            shadow_payload.get("temporal_event_detector_event_score") if shadow_payload else None,
            metadata.get("temporal_event_detector_proposal_acceptance_score") if isinstance(metadata, dict) else None,
            metadata.get("temporal_event_detector_event_score") if isinstance(metadata, dict) else None,
            clip.get("proposalScore"),
        )
    )


def _normalize_proposal_acceptance_raw_score(
    clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None
) -> float | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    return _to_optional_float(
        _first_defined(
            shadow_payload.get("temporal_event_detector_proposal_acceptance_raw_score") if shadow_payload else None,
            metadata.get("temporal_event_detector_proposal_acceptance_raw_score") if isinstance(metadata, dict) else None,
            clip.get("proposalAcceptanceRawScore"),
            clip.get("proposalScore"),
        )
    )


def _normalize_proposal_acceptance_probability(
    clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None
) -> float | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    return _to_optional_float(
        _first_defined(
            shadow_payload.get("temporal_event_detector_proposal_acceptance_probability") if shadow_payload else None,
            metadata.get("temporal_event_detector_proposal_acceptance_probability") if isinstance(metadata, dict) else None,
            clip.get("proposalAcceptanceProbability"),
            clip.get("proposalAcceptanceProbabilityCalibrated"),
            clip.get("proposalScore"),
        )
    )


def _normalize_proposal_energy_score(
    clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None
) -> float | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    return _to_optional_float(
        _first_defined(
            shadow_payload.get("temporal_event_detector_proposal_acceptance_energy") if shadow_payload else None,
            shadow_payload.get("temporal_event_detector_proposal_energy_score") if shadow_payload else None,
            metadata.get("temporal_event_detector_proposal_acceptance_energy") if isinstance(metadata, dict) else None,
            metadata.get("temporal_event_detector_proposal_energy_score") if isinstance(metadata, dict) else None,
            clip.get("proposalEnergyScore"),
        )
    )


def _normalize_proposal_rejector_label(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> str | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    return _first_non_empty(
        shadow_payload.get("temporal_event_detector_proposal_rejector_label") if shadow_payload else None,
        metadata.get("temporal_event_detector_proposal_rejector_label") if isinstance(metadata, dict) else None,
        clip.get("proposalRejectorLabel"),
    )


def _normalize_proposal_rejector_confidence(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> float | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    return _to_optional_float(
        _first_defined(
            shadow_payload.get("temporal_event_detector_proposal_rejector_confidence") if shadow_payload else None,
            metadata.get("temporal_event_detector_proposal_rejector_confidence") if isinstance(metadata, dict) else None,
            clip.get("proposalRejectorConfidence"),
        )
    )


def _normalize_shot_specialist_used(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> bool | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    value = _first_defined(
        shadow_payload.get("temporal_event_detector_shot_specialist_used") if shadow_payload else None,
        metadata.get("temporal_event_detector_shot_specialist_used") if isinstance(metadata, dict) else None,
        clip.get("shotSpecialistUsed"),
    )
    if value is None:
        return None
    return bool(value)


def _normalize_shot_specialist_abstained(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> bool | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    value = _first_defined(
        shadow_payload.get("temporal_event_detector_shot_specialist_abstained") if shadow_payload else None,
        metadata.get("temporal_event_detector_shot_specialist_abstained") if isinstance(metadata, dict) else None,
        clip.get("shotSpecialistAbstained"),
    )
    if value is None:
        return None
    return bool(value)


def _normalize_other_bucket_reason(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> str | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    return _first_non_empty(
        shadow_payload.get("eventFamilyOtherBucketReason") if shadow_payload else None,
        shadow_payload.get("temporal_student_other_bucket_reason") if shadow_payload else None,
        metadata.get("eventFamilyOtherBucketReason") if isinstance(metadata, dict) else None,
        metadata.get("temporal_student_other_bucket_reason") if isinstance(metadata, dict) else None,
        clip.get("eventFamilyOtherBucketReason"),
    )


def _normalize_shot_subtype(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> str | None:
    if shadow_payload is not None and "shotSubtype" in shadow_payload:
        if shadow_payload.get("shotSubtype") is None:
            return None
    elif "shotSubtype" in clip and clip.get("shotSubtype") is None:
        return None
    value = _first_non_empty(
        shadow_payload.get("shotSubtype") if shadow_payload else None,
        clip.get("shotSubtype"),
        clip.get("shotType"),
    )
    text = normalize_text(value)
    if text in {"dunk", "layup", "jumper", "three", "putback"}:
        return text
    if text in {"null", "uncertain", "unknown", ""}:
        return None
    return _taxonomy_from_label(_normalize_flat_label(clip, shadow_payload))[1]


def _normalize_outcome(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> str:
    value = _first_non_empty(
        shadow_payload.get("outcome") if shadow_payload else None,
        clip.get("outcome"),
        clip.get("makeMiss"),
    )
    text = normalize_text(value)
    if text in OUTCOMES:
        return text
    return _taxonomy_from_label(_normalize_flat_label(clip, shadow_payload))[2]


def _taxonomy_from_label(label: str) -> tuple[str, str | None, str]:
    text = normalize_text(label)
    if text == "dunk":
        return "shot_attempt", "dunk", "made"
    if text == "layup":
        return "shot_attempt", "layup", "made"
    if text == "three pointer" or text == "three":
        return "shot_attempt", "three", "made"
    if text == "made shot":
        return "shot_attempt", "jumper", "made"
    if text == "jumper":
        return "shot_attempt", "jumper", "made"
    if text == "putback":
        return "shot_attempt", "putback", "made"
    if text == "block":
        return "defensive_event", None, "blocked"
    if text == "steal":
        return "turnover", None, "uncertain"
    if text == "fast break":
        return "transition", None, "uncertain"
    if text == "miss":
        return "shot_attempt", None, "missed"
    return "other", None, "uncertain"


def _normalize_confidence(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> float:
    for value in (
        _to_optional_float(shadow_payload.get("confidenceAfterMapping")) if shadow_payload else None,
        _to_optional_float(shadow_payload.get("confidence_after_mapping")) if shadow_payload else None,
        _to_optional_float(shadow_payload.get("confidence")) if shadow_payload else None,
        _to_optional_float(clip.get("confidenceAfterMapping")),
        _to_optional_float(clip.get("confidence")),
        _to_optional_float(clip.get("resultConfidence")),
        _to_optional_float(clip.get("confidenceBeforeMapping")),
    ):
        if value is not None:
            return value
    return 0.0


def _normalize_uncertain(clip: dict[str, Any], shadow_payload: dict[str, Any] | None = None) -> bool:
    if shadow_payload is not None and "isUncertain" in shadow_payload:
        return bool(shadow_payload["isUncertain"])
    if "isUncertain" in clip:
        return bool(clip["isUncertain"])
    if normalize_text(_first_non_empty(
        shadow_payload.get("outcome") if shadow_payload else None,
        clip.get("outcome"),
        clip.get("makeMiss"),
    )) == "uncertain":
        return True
    return normalize_text(
        _first_non_empty(
            shadow_payload.get("label") if shadow_payload else None,
            clip.get("finalLabel"),
            clip.get("label"),
            clip.get("displayLabel"),
            "",
        )
    ) == "highlight"


def _normalize_top_k(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            label = item.get("label") or item.get("rawLabel") or item.get("canonicalLabel") or item.get("displayLabel")
            rows.append(
                {
                    "label": str(label) if label is not None else "unknown",
                    "confidence": _to_optional_float(item.get("confidence")) or 0.0,
                    "rawLabel": item.get("rawLabel") or item.get("raw_label"),
                    "canonicalLabel": item.get("canonicalLabel") or item.get("canonical_label"),
                    "modelVersion": item.get("modelVersion") or item.get("model_version"),
                }
            )
        else:
            rows.append({"label": str(item), "confidence": 0.0})
    return rows


def _normalize_other_audit_label(
    clip: dict[str, Any],
    shadow_payload: dict[str, Any] | None,
    audit_override: dict[str, str | None],
) -> str | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    value = _first_non_empty(
        audit_override.get("manualAuditLabel"),
        shadow_payload.get("manualAuditLabel") if shadow_payload else None,
        metadata.get("manualAuditLabel") if isinstance(metadata, dict) else None,
        clip.get("manualAuditLabel"),
        clip.get("otherAuditLabel"),
    )
    text = normalize_text(value).replace(" ", "_")
    return text if text in OTHER_AUDIT_LABELS else None


def _normalize_other_audit_rationale(
    clip: dict[str, Any],
    shadow_payload: dict[str, Any] | None,
    audit_override: dict[str, str | None],
) -> str | None:
    metadata = shadow_payload.get("metadata") if isinstance(shadow_payload, dict) else None
    return _first_non_empty(
        audit_override.get("manualAuditRationale"),
        shadow_payload.get("manualAuditRationale") if shadow_payload else None,
        metadata.get("manualAuditRationale") if isinstance(metadata, dict) else None,
        clip.get("manualAuditRationale"),
        clip.get("otherAuditRationale"),
    )


def _to_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _first_defined(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _resolve_shadow_payload(clip: dict[str, Any], *, shadow_source: str = "auto") -> tuple[str | None, dict[str, Any] | None]:
    keys = (
        (
            "runtimeFusionLoRAShadow",
            "runtimeFusionTemporalShadow",
            "runtimeFusionDistilledShadow",
            "runtimeFusionShadow",
            "runtimeFusionLive",
            "runtimeFusionPrimary",
        )
        if shadow_source == "auto"
        else (shadow_source,)
    )
    for key in keys:
        value = clip.get(key)
        if isinstance(value, dict):
            return key, value
    return None, None


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(character.lower() if character.isalnum() else " " for character in str(value)).strip()


def unique_values(values: Iterable[str | None]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value is None:
            continue
        if value not in seen:
            seen.append(value)
    return seen


def first_label(items: list[dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    first = items[0]
    if isinstance(first, dict):
        return str(first.get("label") or first.get("rawLabel") or first.get("canonicalLabel") or "unknown")
    return str(first)


def escape_md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def build_duration_summary(values: Iterable[float | None]) -> dict[str, Any]:
    samples = sorted(float(value) for value in values if value is not None)
    if not samples:
        return {"count": 0, "medianSeconds": 0.0, "p90Seconds": 0.0}
    p90_index = max(int(round((len(samples) - 1) * 0.9)), 0)
    return {
        "count": len(samples),
        "medianSeconds": round(median(samples), 4),
        "p90Seconds": round(samples[p90_index], 4),
    }


if __name__ == "__main__":
    raise SystemExit(main())
