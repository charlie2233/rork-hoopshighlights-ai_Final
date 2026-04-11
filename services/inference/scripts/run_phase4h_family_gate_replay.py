from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


EVENT_FAMILIES = ("shot_attempt", "turnover", "defensive_event", "transition", "other")
SPOTTER_RESCUE_MAX_DELTA = 0.08
SPOTTER_RESCUE_MIN_PROBABILITY = 0.35
SPOTTER_RESCUE_MIN_ACCEPTANCE = 0.7


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    raw_by_clip = load_raw_batch(args.raw_batch_dir) if args.raw_batch_dir else {}
    clips = report.get("clips", [])
    debug_rows = build_accepted_debug_rows(clips, raw_by_clip)
    sweep_rows = run_sweeps(clips, raw_by_clip)
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    args.docs_dir.mkdir(parents=True, exist_ok=True)

    debug_payload = {
        "sourceReport": str(args.report),
        "rawBatchDir": str(args.raw_batch_dir) if args.raw_batch_dir else None,
        "acceptedProposalCount": len(debug_rows),
        "rows": debug_rows,
    }
    sweep_payload = {
        "sourceReport": str(args.report),
        "rawBatchDir": str(args.raw_batch_dir) if args.raw_batch_dir else None,
        "rows": sweep_rows,
        "recommendedConfig": recommend_config(sweep_rows),
    }
    (args.artifact_dir / "family_gate_accepted_debug.json").write_text(
        json.dumps(debug_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.artifact_dir / "family_gate_sweep.json").write_text(
        json.dumps(sweep_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.docs_dir / "phase4h_family_gate_debug_report.md").write_text(
        render_debug_markdown(debug_payload),
        encoding="utf-8",
    )
    (args.docs_dir / "phase4h_family_gate_sweep_report.md").write_text(
        render_sweep_markdown(sweep_payload),
        encoding="utf-8",
    )
    print(args.docs_dir / "phase4h_family_gate_debug_report.md")
    print(args.docs_dir / "phase4h_family_gate_sweep_report.md")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Phase 4h family gate telemetry and threshold sweeps.")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("services/inference/evals/phase4h_staging_eval/shadow_eval_report.json"),
    )
    parser.add_argument("--raw-batch-dir", type=Path)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("services/inference/evals/phase4h_staging_eval"),
    )
    parser.add_argument("--docs-dir", type=Path, default=Path("docs"))
    return parser.parse_args(argv)


def load_raw_batch(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    raw_by_clip: dict[str, dict[str, Any]] = {}
    for item in sorted(path.glob("*.json")):
        payload = json.loads(item.read_text(encoding="utf-8"))
        clips = payload.get("clips") or payload.get("results", {}).get("clips") or []
        job_id = payload.get("jobId") or payload.get("id")
        for index, clip in enumerate(clips, start=1):
            clip_id = clip.get("clipId") or (f"{job_id}:clip-{index}" if job_id else None)
            if isinstance(clip_id, str):
                raw_by_clip[clip_id] = clip
    return raw_by_clip


def build_accepted_debug_rows(clips: list[dict[str, Any]], raw_by_clip: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for clip in clips:
        if not clip.get("proposalAccepted"):
            continue
        raw_clip = raw_by_clip.get(str(clip.get("clipId")), {})
        shadow = raw_clip.get("runtimeFusionTemporalShadow") or {}
        family_distribution = _family_distribution(clip, shadow)
        ranking = rank_distribution(family_distribution)
        top1 = ranking[0] if ranking else (clip.get("eventFamily"), None)
        top2 = ranking[1] if len(ranking) > 1 else (None, None)
        spotter_family = shadow.get("temporal_student_event_spotter_family") or clip.get("eventSpotterFamily")
        spotter_probability = family_distribution.get(spotter_family) if isinstance(spotter_family, str) else None
        raw_logits = shadow.get("temporal_event_detector_family_raw_logits")
        raw_logits_source = "runtime_payload" if raw_logits is not None else "unavailable_in_current_staging_payload"
        proxy_logits = logits_from_probabilities(family_distribution) if raw_logits is None else None
        closure_reason = (
            shadow.get("temporal_event_detector_family_gate_rejection_reason")
            or clip.get("familyGateRejectionReason")
            or derive_gate_closure_reason(
                proposal_accepted=bool(clip.get("proposalAccepted")),
                family_gate_open=bool(clip.get("familyGateOpen")),
                family_distribution=family_distribution,
                spotter_family=spotter_family,
            )
        )
        forced = forced_family_eval(clip, family_distribution)
        relaxed = relaxed_family_eval(clip, family_distribution, spotter_family)
        rows.append(
            {
                "clipId": clip.get("clipId"),
                "jobId": clip.get("jobId"),
                "requestId": clip.get("requestId"),
                "uploadTraceId": clip.get("uploadTraceId"),
                "inferenceAttemptId": clip.get("inferenceAttemptId"),
                "sourceDomain": clip.get("sourceDomain"),
                "expectedEventFamily": clip.get("expectedEventFamily"),
                "expectedOutcome": clip.get("expectedOutcome"),
                "expectedShotSubtype": clip.get("expectedShotSubtype"),
                "predictedEventFamily": clip.get("eventFamily"),
                "predictedOutcome": clip.get("outcome"),
                "predictedShotSubtype": clip.get("shotSubtype"),
                "proposalAccepted": clip.get("proposalAccepted"),
                "acceptanceScore": clip.get("proposalScore"),
                "calibratedAcceptanceProbability": (
                    shadow.get("temporal_event_detector_proposal_acceptance_probability")
                    or clip.get("proposalAcceptanceProbability")
                ),
                "acceptanceEnergyScore": (
                    shadow.get("temporal_event_detector_proposal_acceptance_energy")
                    or shadow.get("temporal_event_detector_proposal_energy_score")
                    or clip.get("proposalEnergyScore")
                ),
                "rawFamilyLogits": raw_logits,
                "rawFamilyLogitsSource": raw_logits_source,
                "proxyFamilyLogitsFromProbabilities": proxy_logits,
                "temperatureScaledFamilyProbabilities": temperature_scale(family_distribution, temperature=1.0),
                "top1Family": top1[0],
                "top1FamilyProbability": top1[1],
                "top2Family": top2[0],
                "top2FamilyProbability": top2[1],
                "top2Margin": round(float(top1[1] or 0.0) - float(top2[1] or 0.0), 4),
                "eventSpotterFamily": spotter_family,
                "eventSpotterFamilyProbabilityInFamilyHead": spotter_probability,
                "familyEnergyScore": family_energy(raw_logits, family_distribution),
                "gateOpen": clip.get("familyGateOpen"),
                "explicitGateClosureReason": closure_reason,
                "shotHeadPreconditions": shadow.get("temporal_event_detector_shot_head_preconditions")
                or {
                    "proposalAccepted": bool(clip.get("proposalAccepted")),
                    "classifierGateOpen": bool(clip.get("familyGateOpen")),
                    "eventFamilyIsShotAttempt": clip.get("eventFamily") == "shot_attempt",
                    "shotHeadInvoked": bool(clip.get("shotHeadInvoked")),
                },
                "mapperFallbackReason": shadow.get("temporal_event_detector_mapper_fallback_reason")
                or ("event_family_other_highlight_fallback" if clip.get("eventFamily") == "other" else None),
                "featureValidityFlags": shadow.get("temporal_event_detector_feature_validity_flags")
                or {
                    "available": False,
                    "reason": "feature_validity_flags_absent_from_current_staging_payload",
                },
                "shadowForcedFamilyEval": shadow.get("temporal_event_detector_shadow_forced_family_eval") or forced,
                "shadowRelaxedFamilyEval": shadow.get("temporal_event_detector_shadow_relaxed_family_eval") or relaxed,
            }
        )
    return rows


def run_sweeps(clips: list[dict[str, Any]], raw_by_clip: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    temperatures = (0.75, 1.0, 1.25, 1.5, 2.0)
    thresholds = (0.35, 0.42, 0.5, 0.55, 0.62)
    margins = (0.0, 0.02, 0.05, 0.08, 0.1)
    for temperature in temperatures:
        for threshold in thresholds:
            for margin in margins:
                for accepted_implies_family_eval in (False, True):
                    for spotter_rescue in (False, True):
                        rows.append(
                            evaluate_sweep(
                                clips,
                                raw_by_clip,
                                temperature=temperature,
                                threshold=threshold,
                                margin=margin,
                                accepted_implies_family_eval=accepted_implies_family_eval,
                                spotter_rescue=spotter_rescue,
                            )
                        )
    return rows


def evaluate_sweep(
    clips: list[dict[str, Any]],
    raw_by_clip: dict[str, dict[str, Any]],
    *,
    temperature: float,
    threshold: float,
    margin: float,
    accepted_implies_family_eval: bool,
    spotter_rescue: bool,
) -> dict[str, Any]:
    labels = []
    families = []
    family_gate_open_count = 0
    shot_head_invocation_count = 0
    false_event_opens = 0
    for clip in clips:
        accepted = bool(clip.get("proposalAccepted"))
        raw_clip = raw_by_clip.get(str(clip.get("clipId")), {})
        shadow = raw_clip.get("runtimeFusionTemporalShadow") or {}
        distribution = temperature_scale(_family_distribution(clip, shadow), temperature=temperature)
        spotter_family = shadow.get("temporal_student_event_spotter_family") or clip.get("eventSpotterFamily")
        selected_family, reason = select_family_for_sweep(
            distribution,
            spotter_family=spotter_family,
            accepted=accepted,
            accepted_implies_family_eval=accepted_implies_family_eval,
            threshold=threshold,
            margin=margin,
            spotter_rescue=spotter_rescue,
            acceptance_score=float(clip.get("proposalScore") or 0.0),
        )
        gate_open = accepted and selected_family != "other"
        shot_invoked = gate_open and selected_family == "shot_attempt"
        family_gate_open_count += int(gate_open)
        shot_head_invocation_count += int(shot_invoked)
        families.append(selected_family if gate_open else "other")
        labels.append(flat_label_for_family(selected_family if gate_open else "other"))
        if gate_open and clip.get("expectedEventFamily") == "other":
            false_event_opens += 1
    label_counts = Counter(labels)
    family_counts = Counter(families)
    clip_count = max(len(clips), 1)
    dominant_label, dominant_count = label_counts.most_common(1)[0] if label_counts else ("none", 0)
    return {
        "temperature": temperature,
        "familyTop1Threshold": threshold,
        "familyTop2MarginThreshold": margin,
        "acceptedImpliesFamilyEval": accepted_implies_family_eval,
        "spotterRescue": spotter_rescue,
        "familyGateOpenCount": family_gate_open_count,
        "shotHeadInvocationCount": shot_head_invocation_count,
        "rawEventFamilyOtherRate": round(family_counts.get("other", 0) / clip_count, 4),
        "dominantFlatLabel": dominant_label,
        "dominantFlatLabelShare": round(dominant_count / clip_count, 4),
        "flatLabelDistribution": dict(sorted(label_counts.items())),
        "eventFamilyDistribution": dict(sorted(family_counts.items())),
        "falseEventOpenCount": false_event_opens,
        "dunkMadeHallucinationSignal": 0,
    }


def select_family_for_sweep(
    distribution: dict[str, float],
    *,
    spotter_family: Any,
    accepted: bool,
    accepted_implies_family_eval: bool,
    threshold: float,
    margin: float,
    spotter_rescue: bool,
    acceptance_score: float,
) -> tuple[str, str]:
    if not accepted or not accepted_implies_family_eval:
        return "other", "proposal_not_accepted_or_eval_disabled"
    ranking = rank_distribution(distribution)
    if not ranking:
        return "other", "family_distribution_missing"
    top1_label, top1_probability = ranking[0]
    top2_probability = ranking[1][1] if len(ranking) > 1 else 0.0
    top2_margin = max(float(top1_probability) - float(top2_probability), 0.0)
    if (
        spotter_rescue
        and isinstance(spotter_family, str)
        and spotter_family in EVENT_FAMILIES
        and spotter_family != "other"
        and float(distribution.get(spotter_family, 0.0)) >= SPOTTER_RESCUE_MIN_PROBABILITY
        and float(top1_probability) - float(distribution.get(spotter_family, 0.0)) <= SPOTTER_RESCUE_MAX_DELTA
        and acceptance_score >= SPOTTER_RESCUE_MIN_ACCEPTANCE
    ):
        return spotter_family, "spotter_family_close_margin_rescue"
    if (
        top1_label in EVENT_FAMILIES
        and top1_label != "other"
        and float(top1_probability) >= threshold
        and top2_margin >= margin
    ):
        return top1_label, "family_top1_passed"
    return "other", "family_threshold_or_margin_failed"


def recommend_config(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    viable = [
        row
        for row in rows
        if row["familyGateOpenCount"] > 0
        and row["shotHeadInvocationCount"] > 0
        and row["falseEventOpenCount"] == 0
        and row["dominantFlatLabelShare"] < 1.0
    ]
    if not viable:
        return None
    viable.sort(
        key=lambda row: (
            row["falseEventOpenCount"],
            -row["shotHeadInvocationCount"],
            row["dominantFlatLabelShare"],
            abs(row["temperature"] - 1.0),
            abs(row["familyTop1Threshold"] - 0.42),
            abs(row["familyTop2MarginThreshold"] - 0.02),
        )
    )
    return viable[0]


def _family_distribution(clip: dict[str, Any], shadow: dict[str, Any]) -> dict[str, float]:
    distribution = (
        shadow.get("temporal_event_detector_family_distribution")
        or shadow.get("temporal_student_family_distribution")
        or clip.get("familyDistribution")
        or {}
    )
    if not isinstance(distribution, dict):
        return {}
    return {str(key): float(value) for key, value in distribution.items() if key in EVENT_FAMILIES}


def forced_family_eval(clip: dict[str, Any], distribution: dict[str, float]) -> dict[str, Any]:
    ranking = rank_distribution(distribution)
    top1 = ranking[0][0] if ranking else "other"
    accepted = bool(clip.get("proposalAccepted"))
    family = top1 if accepted and top1 != "other" else "other"
    gate_open = accepted and family != "other"
    return {
        "enabled": True,
        "mode": "accepted_implies_family_eval_top1",
        "family": family,
        "familyGateWouldOpen": gate_open,
        "shotHeadWouldInvoke": gate_open and family == "shot_attempt",
    }


def relaxed_family_eval(clip: dict[str, Any], distribution: dict[str, float], spotter_family: Any) -> dict[str, Any]:
    family, reason = select_family_for_sweep(
        distribution,
        spotter_family=spotter_family,
        accepted=bool(clip.get("proposalAccepted")),
        accepted_implies_family_eval=True,
        threshold=0.42,
        margin=0.02,
        spotter_rescue=True,
        acceptance_score=float(clip.get("proposalScore") or 0.0),
    )
    gate_open = bool(clip.get("proposalAccepted")) and family != "other"
    return {
        "enabled": True,
        "mode": "accepted_with_relaxed_family_margin_and_spotter_rescue",
        "family": family,
        "familyGateWouldOpen": gate_open,
        "shotHeadWouldInvoke": gate_open and family == "shot_attempt",
        "reason": reason,
    }


def derive_gate_closure_reason(
    *,
    proposal_accepted: bool,
    family_gate_open: bool,
    family_distribution: dict[str, float],
    spotter_family: Any,
) -> str | None:
    if family_gate_open:
        return None
    if not proposal_accepted:
        return "proposal_rejected"
    ranking = rank_distribution(family_distribution)
    if not ranking:
        return "accepted_but_family_distribution_missing"
    top1_label, top1_probability = ranking[0]
    top2_probability = ranking[1][1] if len(ranking) > 1 else 0.0
    if top1_label == "other":
        return "accepted_but_family_top1_other"
    if float(top1_probability) - float(top2_probability) < 0.08:
        if isinstance(spotter_family, str) and spotter_family != top1_label:
            return "accepted_but_family_margin_low_and_spotter_disagrees"
        return "accepted_but_family_margin_low"
    return "accepted_but_family_gate_closed_without_exported_reason"


def rank_distribution(distribution: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(
        ((str(label), round(float(probability), 4)) for label, probability in distribution.items()),
        key=lambda item: item[1],
        reverse=True,
    )


def logits_from_probabilities(distribution: dict[str, float]) -> dict[str, float] | None:
    if not distribution:
        return None
    return {label: round(math.log(max(float(probability), 1e-9)), 4) for label, probability in distribution.items()}


def temperature_scale(distribution: dict[str, float], *, temperature: float) -> dict[str, float]:
    if not distribution:
        return {}
    logits = {label: math.log(max(float(probability), 1e-9)) for label, probability in distribution.items()}
    scaled = {label: logit / max(float(temperature), 1e-6) for label, logit in logits.items()}
    max_logit = max(scaled.values())
    exp_values = {label: math.exp(value - max_logit) for label, value in scaled.items()}
    denom = sum(exp_values.values()) or 1.0
    return {label: round(value / denom, 4) for label, value in exp_values.items()}


def family_energy(raw_logits: Any, distribution: dict[str, float]) -> float | None:
    if raw_logits is None:
        return None
    values = [float(value) for value in raw_logits]
    if not values:
        return None
    max_logit = max(values)
    return round(-(max_logit + math.log(sum(math.exp(value - max_logit) for value in values))), 4)


def flat_label_for_family(family: str) -> str:
    if family == "shot_attempt":
        return "Shot Attempt"
    if family == "transition":
        return "Fast Break"
    if family == "turnover":
        return "Steal"
    if family == "defensive_event":
        return "Block"
    return "Highlight"


def render_debug_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    reason_counts = Counter(row.get("explicitGateClosureReason") or "none" for row in rows)
    forced_count = sum(1 for row in rows if row.get("shadowForcedFamilyEval", {}).get("familyGateWouldOpen"))
    relaxed_count = sum(1 for row in rows if row.get("shadowRelaxedFamilyEval", {}).get("familyGateWouldOpen"))
    relaxed_shots = sum(1 for row in rows if row.get("shadowRelaxedFamilyEval", {}).get("shotHeadWouldInvoke"))
    lines = [
        "# Phase 4h Family Gate Debug Report",
        "",
        "## Summary",
        "",
        f"- Accepted proposals replayed: `{len(rows)}`",
        f"- Forced-family comparator gate opens: `{forced_count}`",
        f"- Relaxed-family comparator gate opens: `{relaxed_count}`",
        f"- Relaxed-family comparator shot-head invocations: `{relaxed_shots}`",
        f"- Closure reason distribution: `{json.dumps(dict(sorted(reason_counts.items())), sort_keys=True)}`",
        "- Current staging payload did not include raw family logits or feature-validity flags; this branch adds those fields for the next staging smoke.",
        "",
        "## Accepted Proposal Table",
        "",
        "| clipId | expected | top1 | top2 | margin | spotter | accepted score | gate open | closure reason | forced family | relaxed family | relaxed shot head |",
        "| --- | --- | --- | --- | ---: | --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        expected = "/".join(
            str(value)
            for value in (row.get("expectedEventFamily"), row.get("expectedOutcome"), row.get("expectedShotSubtype"))
            if value is not None
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("clipId")),
                    expected,
                    f"{row.get('top1Family')} ({row.get('top1FamilyProbability')})",
                    f"{row.get('top2Family')} ({row.get('top2FamilyProbability')})",
                    str(row.get("top2Margin")),
                    str(row.get("eventSpotterFamily")),
                    str(row.get("acceptanceScore")),
                    str(row.get("gateOpen")),
                    str(row.get("explicitGateClosureReason")),
                    str(row.get("shadowForcedFamilyEval", {}).get("family")),
                    str(row.get("shadowRelaxedFamilyEval", {}).get("family")),
                    str(row.get("shadowRelaxedFamilyEval", {}).get("shotHeadWouldInvoke")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def render_sweep_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    recommended = payload.get("recommendedConfig")
    best = sorted(
        rows,
        key=lambda row: (
            row["falseEventOpenCount"],
            -row["shotHeadInvocationCount"],
            row["dominantFlatLabelShare"],
        ),
    )[:10]
    lines = [
        "# Phase 4h Family Gate Sweep Report",
        "",
        "## Recommendation",
        "",
    ]
    if recommended:
        lines.extend(
            [
                "- Recommended smoke setting: accepted-implies-family-eval with spotter rescue.",
                f"- Family temperature: `{recommended['temperature']}`",
                f"- Family top-1 threshold: `{recommended['familyTop1Threshold']}`",
                f"- Family top-2 margin threshold: `{recommended['familyTop2MarginThreshold']}`",
                f"- Replay family gate opens: `{recommended['familyGateOpenCount']}`",
                f"- Replay shot-head invocations: `{recommended['shotHeadInvocationCount']}`",
                f"- Replay raw eventFamily=other rate: `{recommended['rawEventFamilyOtherRate']}`",
                f"- Replay dominant flat-label share: `{recommended['dominantFlatLabelShare']}`",
                "- Go/no-go for next step: run a small `15-20` clip staging smoke only. Do not promote larger rollout until calibrated acceptance probability, energy, and explicit gate reasons are visible in staging.",
            ]
        )
    else:
        lines.append("- No viable relaxed family-gate config found on replay.")
    lines.extend(
        [
            "",
            "## Top Sweep Rows",
            "",
            "| temp | threshold | margin | accepted eval | spotter rescue | gate opens | shot head | raw other | dominant share | false event opens |",
            "| ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in best:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["temperature"]),
                    str(row["familyTop1Threshold"]),
                    str(row["familyTop2MarginThreshold"]),
                    str(row["acceptedImpliesFamilyEval"]),
                    str(row["spotterRescue"]),
                    str(row["familyGateOpenCount"]),
                    str(row["shotHeadInvocationCount"]),
                    str(row["rawEventFamilyOtherRate"]),
                    str(row["dominantFlatLabelShare"]),
                    str(row["falseEventOpenCount"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Over-Fire Check",
            "",
            "- The replay opens only accepted proposals, so rejected known misses and unlabeled demo clips remain closed.",
            "- The replay does not emit concrete outcome/subtype predictions; `dunkMadeHallucinationSignal` remains `0` because the sweep stops at family/shot-head invocation.",
            "- A live smoke must verify the actual shot head does not reintroduce made/dunk hallucination.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
