from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from services.inference.scripts.run_eval_report import to_optional_float
from services.inference.training.hard_negative_mining import hard_example_signal


DEFAULT_TOP_K = 50


@dataclass(frozen=True)
class UnifiedClipAnnotation:
    clip_id: str
    source_domain: str
    schema_version: str | None
    event_family: str
    outcome: str
    shot_subtype: str | None
    ball_visible: bool
    hoop_visible: bool
    ball_near_rim: float | None
    ball_through_hoop_likelihood: float | None
    possession_change_likelihood: float | None
    transition_likelihood: float | None
    teacher_confidence: float | None
    human_verified: bool
    reviewer_notes: str
    raw_runtime_outputs: dict[str, Any]
    raw_teacher_outputs: dict[str, Any]


@dataclass(frozen=True)
class DisagreementQueueItem:
    clip_id: str
    source_domain: str
    schema_version: str | None
    review_bucket: str
    priority_score: float
    hard_example_score: float
    hard_example_weight: float
    hard_example: bool
    hard_example_tier: str
    priority_reasons: list[str]
    runtime_label: str
    runtime_event_family: str
    runtime_outcome: str
    runtime_shot_subtype: str | None
    runtime_confidence: float | None
    teacher_label: str | None
    teacher_event_family: str | None
    teacher_outcome: str | None
    teacher_shot_subtype: str | None
    teacher_confidence: float | None
    ball_visible: bool
    hoop_visible: bool
    ball_near_rim: float | None
    ball_through_hoop_likelihood: float | None
    possession_change_likelihood: float | None
    transition_likelihood: float | None
    human_verified: bool
    reviewer_notes: str
    raw_runtime_outputs: dict[str, Any]
    raw_teacher_outputs: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["priority_score"] = round(self.priority_score, 4)
        data["hard_example_score"] = round(self.hard_example_score, 4)
        data["hard_example_weight"] = round(self.hard_example_weight, 4)
        return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an offline disagreement review queue.")
    parser.add_argument("--annotations", type=Path, required=True, help="Unified annotation JSON list or {records: []}.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for queue artifacts.")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Maximum number of queued clips to emit.")
    parser.add_argument("--min-teacher-confidence", type=float, default=0.75)
    parser.add_argument("--max-runtime-confidence", type=float, default=0.55)
    parser.add_argument("--min-ball-evidence", type=float, default=0.7)
    return parser.parse_args()


def load_annotations(path: Path) -> list[UnifiedClipAnnotation]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        records = payload.get("records") or payload.get("annotations") or []
    else:
        records = payload
    if not isinstance(records, list):
        raise ValueError("annotations payload must be a list or contain records[]")
    return [parse_annotation(item) for item in records]


def parse_annotation(item: dict[str, Any]) -> UnifiedClipAnnotation:
    if not isinstance(item, dict):
        raise TypeError("annotation item must be an object")
    raw_runtime_outputs = dict(item.get("rawRuntimeOutputs") or {})
    raw_teacher_outputs = dict(item.get("rawTeacherOutputs") or {})
    return UnifiedClipAnnotation(
        clip_id=str(item["clipId"]),
        source_domain=str(item["sourceDomain"]),
        schema_version=_normalize_optional_text(item.get("schemaVersion")),
        event_family=str(item["eventFamily"]),
        outcome=str(item["outcome"]),
        shot_subtype=_normalize_optional_text(item.get("shotSubtype")),
        ball_visible=bool(item.get("ballVisible", False)),
        hoop_visible=bool(item.get("hoopVisible", False)),
        ball_near_rim=to_optional_float(item.get("ballNearRim")),
        ball_through_hoop_likelihood=to_optional_float(item.get("ballThroughHoopLikelihood")),
        possession_change_likelihood=to_optional_float(item.get("possessionChangeLikelihood")),
        transition_likelihood=to_optional_float(item.get("transitionLikelihood")),
        teacher_confidence=to_optional_float(item.get("teacherConfidence")),
        human_verified=bool(item.get("humanVerified", False)),
        reviewer_notes=str(item.get("reviewerNotes", "")),
        raw_runtime_outputs=raw_runtime_outputs,
        raw_teacher_outputs=raw_teacher_outputs,
    )


def build_disagreement_queue(
    annotations: Iterable[UnifiedClipAnnotation],
    *,
    min_teacher_confidence: float = 0.75,
    max_runtime_confidence: float = 0.55,
    min_ball_evidence: float = 0.7,
) -> list[DisagreementQueueItem]:
    items: list[DisagreementQueueItem] = []
    for annotation in annotations:
        item = score_annotation(
            annotation,
            min_teacher_confidence=min_teacher_confidence,
            max_runtime_confidence=max_runtime_confidence,
            min_ball_evidence=min_ball_evidence,
        )
        if item is not None:
            items.append(item)
    items.sort(key=lambda item: (-item.priority_score, item.clip_id))
    return items


def score_annotation(
    annotation: UnifiedClipAnnotation,
    *,
    min_teacher_confidence: float,
    max_runtime_confidence: float,
    min_ball_evidence: float,
) -> DisagreementQueueItem | None:
    runtime_outputs = annotation.raw_runtime_outputs
    teacher_outputs = annotation.raw_teacher_outputs

    runtime_label = _runtime_label(runtime_outputs)
    teacher_label = _teacher_label(teacher_outputs)
    runtime_event_family = _runtime_event_family(runtime_outputs, runtime_label)
    runtime_outcome = _runtime_outcome(runtime_outputs)
    runtime_shot_subtype = _runtime_shot_subtype(runtime_outputs)
    runtime_confidence = _runtime_confidence(runtime_outputs)
    teacher_event_family = _teacher_event_family(teacher_outputs)
    teacher_outcome = _teacher_outcome(teacher_outputs)
    teacher_shot_subtype = _teacher_shot_subtype(teacher_outputs)
    teacher_confidence = annotation.teacher_confidence if annotation.teacher_confidence is not None else _runtime_confidence(teacher_outputs)
    if teacher_confidence is None:
        teacher_confidence = _teacher_confidence(teacher_outputs)

    priority_reasons: list[str] = []
    priority_score = 0.0

    if _label_is_highlight_only(runtime_label):
        priority_reasons.append("app_facing_label_only_highlight")
        priority_score += 0.25

    if _runtime_and_teacher_disagree(runtime_label, teacher_label, runtime_event_family, teacher_event_family, runtime_outcome, teacher_outcome):
        priority_reasons.append("runtime_teacher_disagree")
        priority_score += 0.4

    if _miss_made_conflict(runtime_outcome, teacher_outcome, runtime_label, teacher_label):
        priority_reasons.append("miss_vs_made_conflict")
        priority_score += 0.3

    if _strong_ball_hoop_evidence(annotation, min_ball_evidence) and runtime_shot_subtype in {None, "unknown"}:
        priority_reasons.append("strong_ball_hoop_evidence_null_subtype")
        priority_score += 0.2

    if teacher_confidence is not None and runtime_confidence is not None and teacher_confidence >= min_teacher_confidence and runtime_confidence <= max_runtime_confidence:
        priority_reasons.append("high_teacher_low_runtime")
        priority_score += 0.2

    if not priority_reasons:
        return None

    hard_example_score = hard_example_signal(
        annotation.__dict__,
        source_kind="disagreement",
        source_domain=annotation.source_domain,
        priority_score=priority_score,
        teacher_confidence=teacher_confidence,
        reasons=priority_reasons,
    )
    hard_example_weight = 1.0 + 1.8 * hard_example_score
    hard_example_tier = _hard_example_tier(hard_example_score, priority_reasons)

    if annotation.human_verified:
        priority_score *= 0.9
        priority_reasons.append("human_verified_review")

    review_bucket = _primary_bucket(priority_reasons)
    return DisagreementQueueItem(
        clip_id=annotation.clip_id,
        source_domain=annotation.source_domain,
        schema_version=annotation.schema_version,
        review_bucket=review_bucket,
        priority_score=min(priority_score, 1.0),
        hard_example_score=round(hard_example_score, 4),
        hard_example_weight=round(hard_example_weight, 4),
        hard_example=hard_example_score >= 0.45,
        hard_example_tier=hard_example_tier,
        priority_reasons=priority_reasons,
        runtime_label=runtime_label,
        runtime_event_family=runtime_event_family,
        runtime_outcome=runtime_outcome,
        runtime_shot_subtype=runtime_shot_subtype,
        runtime_confidence=runtime_confidence,
        teacher_label=teacher_label,
        teacher_event_family=teacher_event_family,
        teacher_outcome=teacher_outcome,
        teacher_shot_subtype=teacher_shot_subtype,
        teacher_confidence=teacher_confidence,
        ball_visible=annotation.ball_visible,
        hoop_visible=annotation.hoop_visible,
        ball_near_rim=annotation.ball_near_rim,
        ball_through_hoop_likelihood=annotation.ball_through_hoop_likelihood,
        possession_change_likelihood=annotation.possession_change_likelihood,
        transition_likelihood=annotation.transition_likelihood,
        human_verified=annotation.human_verified,
        reviewer_notes=annotation.reviewer_notes,
        raw_runtime_outputs=runtime_outputs,
        raw_teacher_outputs=teacher_outputs,
    )


def build_summary(queue: list[DisagreementQueueItem], annotations: Iterable[UnifiedClipAnnotation]) -> dict[str, Any]:
    by_bucket = Counter(item.review_bucket for item in queue)
    by_source = Counter(item.source_domain for item in queue)
    hard_by_tier = Counter(item.hard_example_tier for item in queue if item.hard_example)
    source_total = Counter(annotation.source_domain for annotation in annotations)
    return {
        "totalAnnotations": sum(source_total.values()),
        "queuedClips": len(queue),
        "byBucket": dict(sorted(by_bucket.items())),
        "bySourceDomain": dict(sorted(by_source.items())),
        "hardExampleQueued": sum(1 for item in queue if item.hard_example),
        "hardExampleByTier": dict(sorted(hard_by_tier.items())),
    }


def render_markdown(summary: dict[str, Any], queue: list[DisagreementQueueItem]) -> str:
    lines = ["# Disagreement Review Queue", ""]
    lines.append(f"- Total annotations: {summary['totalAnnotations']}")
    lines.append(f"- Queued clips: {summary['queuedClips']}")
    lines.append("")
    lines.append("## Buckets")
    for bucket, count in summary["byBucket"].items():
        lines.append(f"- {bucket}: {count}")
    lines.append("")
    lines.append("## Queue")
    for index, item in enumerate(queue, start=1):
        lines.append(
            f"{index}. `{item.clip_id}` [{item.review_bucket}] score={item.priority_score:.2f} "
            f"hard={item.hard_example_tier}:{item.hard_example_weight:.2f} "
            f"runtime={item.runtime_label} teacher={item.teacher_label or 'n/a'} reasons={', '.join(item.priority_reasons)}"
        )
    return "\n".join(lines) + "\n"


def write_artifacts(output_dir: Path, summary: dict[str, Any], queue: list[DisagreementQueueItem]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "disagreement_queue.json"
    md_path = output_dir / "disagreement_queue.md"
    json_payload = {
        "summary": summary,
        "queue": [item.as_dict() for item in queue],
    }
    json_path.write_text(json.dumps(json_payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(summary, queue), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    args = parse_args()
    annotations = load_annotations(args.annotations)
    queue = build_disagreement_queue(
        annotations,
        min_teacher_confidence=args.min_teacher_confidence,
        max_runtime_confidence=args.max_runtime_confidence,
        min_ball_evidence=args.min_ball_evidence,
    )[: args.top_k]
    summary = build_summary(queue, annotations)
    json_path, md_path = write_artifacts(args.output_dir, summary, queue)
    print(md_path)
    print(json_path)
    return 0


def _primary_bucket(priority_reasons: list[str]) -> str:
    for reason in (
        "runtime_teacher_disagree",
        "miss_vs_made_conflict",
        "app_facing_label_only_highlight",
        "strong_ball_hoop_evidence_null_subtype",
        "high_teacher_low_runtime",
        "human_verified_review",
    ):
        if reason in priority_reasons:
            return reason
    return priority_reasons[0]


def _hard_example_tier(hard_example_score: float, priority_reasons: list[str]) -> str:
    if "miss_vs_made_conflict" in priority_reasons or "runtime_teacher_disagree" in priority_reasons:
        return "critical"
    if hard_example_score >= 0.8:
        return "high"
    if hard_example_score >= 0.55:
        return "medium"
    return "low"


def _runtime_label(outputs: dict[str, Any]) -> str:
    return str(outputs.get("label") or outputs.get("displayLabel") or outputs.get("finalLabel") or "unknown").strip()


def _teacher_label(outputs: dict[str, Any]) -> str | None:
    value = outputs.get("displayLabelSuggestion") or outputs.get("label") or outputs.get("finalLabel")
    if value is None:
        family = outputs.get("eventFamily")
        outcome = outputs.get("outcome")
        subtype = outputs.get("shotSubtype")
        if family == "shot_attempt" and subtype:
            return str(subtype)
        if family == "turnover":
            return "Steal"
        if family == "transition":
            return "Fast Break"
        if family == "defensive_event":
            return "Block" if outcome == "blocked" else "Highlight"
        return None
    return str(value).strip()


def _runtime_event_family(outputs: dict[str, Any], runtime_label: str) -> str:
    value = outputs.get("eventFamily") or outputs.get("eventType")
    if value is not None:
        return str(value).strip()
    if runtime_label.lower() in {"steal", "block", "fast break"}:
        return {"steal": "turnover", "block": "defensive_event", "fast break": "transition"}[runtime_label.lower()]
    if runtime_label.lower() == "highlight":
        return "other"
    return "shot_attempt"


def _runtime_outcome(outputs: dict[str, Any]) -> str:
    value = outputs.get("outcome") or outputs.get("makeMiss")
    if value is None:
        return "uncertain"
    value = str(value).strip().lower()
    if value in {"make", "made"}:
        return "made"
    if value in {"miss", "missed"}:
        return "missed"
    if value in {"blocked", "block"}:
        return "blocked"
    return "uncertain"


def _runtime_shot_subtype(outputs: dict[str, Any]) -> str | None:
    value = outputs.get("shotSubtype") or outputs.get("shotType")
    if value in {None, "", "unknown"}:
        return None
    return str(value).strip()


def _teacher_event_family(outputs: dict[str, Any]) -> str | None:
    value = outputs.get("eventFamily") or outputs.get("eventType")
    return str(value).strip() if value else None


def _teacher_outcome(outputs: dict[str, Any]) -> str | None:
    value = outputs.get("outcome") or outputs.get("makeMiss")
    if value is None:
        return None
    return _runtime_outcome({"outcome": value})


def _teacher_shot_subtype(outputs: dict[str, Any]) -> str | None:
    value = outputs.get("shotSubtype") or outputs.get("shotType")
    if value in {None, "", "unknown"}:
        return None
    return str(value).strip()


def _runtime_confidence(outputs: dict[str, Any]) -> float | None:
    for key in ("confidenceAfterMapping", "confidence", "confidenceBeforeMapping", "resultConfidence"):
        value = to_optional_float(outputs.get(key))
        if value is not None:
            return value
    return None


def _teacher_confidence(outputs: dict[str, Any]) -> float | None:
    for key in ("confidence", "confidenceAfterMapping", "confidenceBeforeMapping"):
        value = to_optional_float(outputs.get(key))
        if value is not None:
            return value
    return None


def _label_is_highlight_only(runtime_label: str) -> bool:
    normalized = runtime_label.strip().lower()
    return normalized in {"highlight", "uncertain", "unknown", "generic", "other"}


def _runtime_and_teacher_disagree(
    runtime_label: str,
    teacher_label: str | None,
    runtime_event_family: str,
    teacher_event_family: str | None,
    runtime_outcome: str,
    teacher_outcome: str | None,
) -> bool:
    runtime_label_norm = runtime_label.strip().lower() if runtime_label else "unknown"
    teacher_label_norm = teacher_label.strip().lower() if teacher_label else None
    if teacher_label_norm is not None and runtime_label_norm != teacher_label_norm:
        return True
    if teacher_event_family is not None and runtime_event_family != teacher_event_family:
        return True
    if teacher_outcome is not None and runtime_outcome != teacher_outcome:
        return True
    return False


def _miss_made_conflict(runtime_outcome: str, teacher_outcome: str | None, runtime_label: str, teacher_label: str | None) -> bool:
    made_miss = {"made", "missed"}
    if runtime_outcome in made_miss and teacher_outcome in made_miss and runtime_outcome != teacher_outcome:
        return True
    return False


def _strong_ball_hoop_evidence(annotation: UnifiedClipAnnotation, min_ball_evidence: float) -> bool:
    if not (annotation.ball_visible and annotation.hoop_visible):
        return False
    signals = [
        annotation.ball_near_rim or 0.0,
        annotation.ball_through_hoop_likelihood or 0.0,
        annotation.possession_change_likelihood or 0.0,
        annotation.transition_likelihood or 0.0,
    ]
    return max(signals) >= min_ball_evidence


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


if __name__ == "__main__":
    raise SystemExit(main())
