from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .annotations import ANNOTATION_SCHEMA_VERSION


DEFAULT_MINE_VERSION = "hard-negative-v1"
DEFAULT_SOURCE_DOMAIN = "live_runtime"
DEFAULT_QUEUE_BUCKET = "hard_negative"


@dataclass(frozen=True)
class LiveMiningClip:
    clip_id: str
    source_domain: str
    source_batch_id: str | None
    schema_version: str | None
    job_id: str | None
    request_id: str | None
    upload_trace_id: str | None
    inference_attempt_id: str | None
    model_version: str | None
    final_label: str
    event_family: str | None
    outcome: str | None
    shot_subtype: str | None
    confidence: float | None
    confidence_before_mapping: float | None
    confidence_after_mapping: float | None
    result_confidence: float | None
    margin: float | None
    was_merged: bool
    source_event_count: int | None
    clip_duration_seconds: float | None
    is_uncertain: bool
    raw_top_labels: list[dict[str, Any]]
    comparison_raw_top_labels: list[dict[str, Any]]
    raw_runtime_outputs: dict[str, Any]
    raw_teacher_outputs: dict[str, Any]


@dataclass(frozen=True)
class HardNegativeQueueItem:
    clip_id: str
    source_domain: str
    source_batch_id: str | None
    schema_version: str | None
    job_id: str | None
    request_id: str | None
    upload_trace_id: str | None
    inference_attempt_id: str | None
    model_version: str | None
    final_label: str
    event_family: str | None
    outcome: str | None
    shot_subtype: str | None
    confidence: float | None
    confidence_before_mapping: float | None
    confidence_after_mapping: float | None
    result_confidence: float | None
    margin: float | None
    was_merged: bool
    source_event_count: int | None
    clip_duration_seconds: float | None
    review_bucket: str
    priority_score: float
    sample_weight: float
    training_weight: float
    priority_reasons: list[str]
    source_tags: list[str]
    raw_top_labels: list[dict[str, Any]]
    comparison_raw_top_labels: list[dict[str, Any]]
    raw_runtime_outputs: dict[str, Any]
    raw_teacher_outputs: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["priority_score"] = round(self.priority_score, 4)
        data["sample_weight"] = round(self.sample_weight, 4)
        data["training_weight"] = round(self.training_weight, 4)
        return data


@dataclass(frozen=True)
class HardNegativeMiningReport:
    queue_version: str
    summary: dict[str, Any]
    queue: list[HardNegativeQueueItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "queueVersion": self.queue_version,
            "summary": self.summary,
            "queue": [item.as_dict() for item in self.queue],
        }


def load_live_payloads(paths: Sequence[Path]) -> list[LiveMiningClip]:
    clips: list[LiveMiningClip] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        clips.extend(normalize_payload(payload, source_batch_id=path.stem))
    return clips


def normalize_payload(payload: Any, *, source_batch_id: str | None = None) -> list[LiveMiningClip]:
    if isinstance(payload, list):
        return [normalize_clip_row(item, source_batch_id=source_batch_id) for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, Mapping):
        raise TypeError("live payload must be an object, array, or clip list")

    context = {
        "jobId": _optional_text(payload.get("jobId")),
        "requestId": _optional_text(payload.get("requestId")),
        "uploadTraceId": _optional_text(payload.get("uploadTraceId")),
        "inferenceAttemptId": _optional_text(payload.get("inferenceAttemptId")),
        "modelVersion": _optional_text(payload.get("modelVersion")),
        "schemaVersion": _optional_text(payload.get("schemaVersion")) or ANNOTATION_SCHEMA_VERSION,
    }

    clip_rows = _extract_clip_rows(payload)
    normalized: list[LiveMiningClip] = []
    for row in clip_rows:
        if not isinstance(row, Mapping):
            continue
        merged_row = dict(context)
        merged_row.update(row)
        normalized.append(normalize_clip_row(merged_row, source_batch_id=source_batch_id))
    if normalized:
        return normalized

    if "clipId" in payload:
        return [normalize_clip_row(payload, source_batch_id=source_batch_id)]
    return []


def build_hard_negative_queue(
    clips: Iterable[LiveMiningClip],
    *,
    min_margin: float = 0.08,
    min_result_confidence: float = 0.75,
    top_k: int | None = None,
) -> list[HardNegativeQueueItem]:
    queue: list[HardNegativeQueueItem] = []
    for clip in clips:
        item = score_live_clip(
            clip,
            min_margin=min_margin,
            min_result_confidence=min_result_confidence,
        )
        if item is not None:
            queue.append(item)
    queue.sort(key=lambda item: (-item.priority_score, item.source_batch_id or "", item.clip_id))
    if top_k is not None:
        return queue[:top_k]
    return queue


def score_live_clip(
    clip: LiveMiningClip,
    *,
    min_margin: float,
    min_result_confidence: float,
) -> HardNegativeQueueItem | None:
    reasons: list[str] = []
    priority_score = 0.0

    final_label = _normalized_label(clip.final_label)
    event_family = _normalized_label(clip.event_family)
    outcome = _normalized_label(clip.outcome)
    confidence = clip.confidence if clip.confidence is not None else clip.result_confidence
    low_margin = clip.margin is not None and clip.margin < min_margin
    low_result_confidence = confidence is not None and confidence < min_result_confidence
    comparison_disagreement = _comparison_disagreement(clip)
    eligible = final_label == "highlight" or event_family == "other" or low_margin or comparison_disagreement or clip.was_merged or (clip.source_event_count or 0) > 1

    if not eligible:
        return None

    if final_label == "highlight":
        reasons.append("final_label_highlight")
        priority_score += 0.42
    if event_family == "other":
        reasons.append("event_family_other")
        priority_score += 0.42
    if low_margin:
        reasons.append("low_margin")
        priority_score += min(0.35, 0.15 + max(min_margin - float(clip.margin or 0.0), 0.0) * 2.0)
    if comparison_disagreement:
        reasons.append("cross_model_disagreement")
        priority_score += 0.3
    if clip.is_uncertain or outcome == "uncertain":
        reasons.append("uncertain")
        priority_score += 0.14
    if clip.was_merged or (clip.source_event_count or 0) > 1:
        reasons.append("merged_multi_event")
        priority_score += 0.12
    if low_result_confidence:
        reasons.append("low_result_confidence")
        priority_score += 0.1

    if not reasons:
        return None

    bucket = _primary_bucket(reasons, final_label=final_label, event_family=event_family, low_margin=low_margin, disagreement=comparison_disagreement)
    priority_score = min(priority_score, 1.0)
    sample_weight = min(3.0, round(1.0 + priority_score * 1.8, 2))
    training_weight = sample_weight
    source_tags = _source_tags(clip, reasons, final_label=final_label, event_family=event_family, low_margin=low_margin, disagreement=comparison_disagreement)

    return HardNegativeQueueItem(
        clip_id=clip.clip_id,
        source_domain=clip.source_domain,
        source_batch_id=clip.source_batch_id,
        schema_version=clip.schema_version,
        job_id=clip.job_id,
        request_id=clip.request_id,
        upload_trace_id=clip.upload_trace_id,
        inference_attempt_id=clip.inference_attempt_id,
        model_version=clip.model_version,
        final_label=clip.final_label,
        event_family=clip.event_family,
        outcome=clip.outcome,
        shot_subtype=clip.shot_subtype,
        confidence=clip.confidence,
        confidence_before_mapping=clip.confidence_before_mapping,
        confidence_after_mapping=clip.confidence_after_mapping,
        result_confidence=clip.result_confidence,
        margin=clip.margin,
        was_merged=clip.was_merged,
        source_event_count=clip.source_event_count,
        clip_duration_seconds=clip.clip_duration_seconds,
        review_bucket=bucket,
        priority_score=priority_score,
        sample_weight=sample_weight,
        training_weight=training_weight,
        priority_reasons=reasons,
        source_tags=source_tags,
        raw_top_labels=clip.raw_top_labels,
        comparison_raw_top_labels=clip.comparison_raw_top_labels,
        raw_runtime_outputs=clip.raw_runtime_outputs,
        raw_teacher_outputs=clip.raw_teacher_outputs,
    )


def build_hard_negative_report(
    clips: Iterable[LiveMiningClip],
    *,
    min_margin: float = 0.08,
    min_result_confidence: float = 0.75,
    top_k: int | None = None,
) -> HardNegativeMiningReport:
    queue = build_hard_negative_queue(
        clips,
        min_margin=min_margin,
        min_result_confidence=min_result_confidence,
        top_k=top_k,
    )
    summary = build_summary(queue)
    return HardNegativeMiningReport(queue_version=DEFAULT_MINE_VERSION, summary=summary, queue=queue)


def build_summary(queue: Sequence[HardNegativeQueueItem]) -> dict[str, Any]:
    return {
        "queueVersion": DEFAULT_MINE_VERSION,
        "queuedClips": len(queue),
        "byReviewBucket": _count_by(item.review_bucket for item in queue),
        "byReason": _count_by(reason for item in queue for reason in item.priority_reasons),
        "byFinalLabel": _count_by(_normalized_label(item.final_label) for item in queue),
        "byEventFamily": _count_by(_normalized_label(item.event_family) for item in queue if item.event_family),
        "bySourceDomain": _count_by(item.source_domain for item in queue),
        "bySourceBatchId": _count_by(item.source_batch_id for item in queue if item.source_batch_id),
        "priorityScore": _score_stats(item.priority_score for item in queue),
        "sampleWeight": _score_stats(item.sample_weight for item in queue),
        "trainingWeight": _score_stats(item.training_weight for item in queue),
    }


def render_markdown(report: HardNegativeMiningReport) -> str:
    summary = report.summary
    lines = ["# Hard Negative Mining Queue", ""]
    lines.append(f"- Queue version: `{summary['queueVersion']}`")
    lines.append(f"- Queued clips: `{summary['queuedClips']}`")
    lines.append(f"- Training-ready rows: `{summary['queuedClips']}`")
    lines.append(f"- Dominant label: `{_dominant(summary['byFinalLabel'])}`")
    lines.append(f"- Dominant event family: `{_dominant(summary['byEventFamily'])}`")
    lines.append(f"- Mean sample weight: `{summary['sampleWeight']['mean']:.2f}`")
    lines.append(f"- Max sample weight: `{summary['sampleWeight']['max']:.2f}`")
    lines.append("")
    lines.append("## Reasons")
    for reason, count in sorted(summary["byReason"].items()):
        lines.append(f"- {reason}: {count}")
    lines.append("")
    lines.append("## Queue")
    for index, item in enumerate(report.queue, start=1):
        lines.append(
            f"{index}. `{item.clip_id}` [{item.review_bucket}] weight={item.sample_weight:.2f} "
            f"priority={item.priority_score:.2f} reasons={', '.join(item.priority_reasons)}"
        )
    return "\n".join(lines) + "\n"


def write_artifacts(output_dir: Path, report: HardNegativeMiningReport) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    queue_path = output_dir / "hard_negative_queue.jsonl"
    training_path = output_dir / "hard_negative_training.jsonl"
    md_path = output_dir / "hard_negative_queue.md"
    summary_path = output_dir / "hard_negative_queue_summary.json"
    queue_path.write_text("\n".join(json.dumps(item.as_dict(), sort_keys=True) for item in report.queue) + ("\n" if report.queue else ""), encoding="utf-8")
    training_path.write_text("\n".join(json.dumps(item.as_dict(), sort_keys=True) for item in report.queue) + ("\n" if report.queue else ""), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    summary_path.write_text(json.dumps(report.summary, indent=2, sort_keys=True), encoding="utf-8")
    return queue_path, training_path, md_path


def normalize_clip_row(row: Mapping[str, Any], *, source_batch_id: str | None = None) -> LiveMiningClip:
    shadow = _select_shadow_payload(row)
    shadow_snapshot = _shadow_snapshot(shadow)
    raw_top_labels = _normalize_top_labels(
        row.get("rawTopLabels")
        or row.get("topLabels")
        or row.get("rawVideoMAETopK")
        or shadow_snapshot.get("rawTopLabels")
        or shadow_snapshot.get("videoMAE")
    )
    comparison_top_labels = _normalize_top_labels(
        row.get("comparisonRawTopLabels")
        or row.get("comparisonTopLabels")
        or shadow_snapshot.get("comparisonRawTopLabels")
        or shadow_snapshot.get("comparisonVideoMAE")
    )
    confidence_before_mapping = _optional_float(row.get("confidenceBeforeMapping") or shadow_snapshot.get("confidenceBeforeMapping"))
    confidence_after_mapping = _optional_float(row.get("confidenceAfterMapping") or shadow_snapshot.get("confidenceAfterMapping"))
    confidence = _optional_float(row.get("confidence") or shadow_snapshot.get("confidence"))
    result_confidence = _optional_float(row.get("resultConfidence") or shadow_snapshot.get("resultConfidence"))
    margin = _extract_margin(row, raw_top_labels, comparison_top_labels)
    event_family = _optional_text(row.get("eventFamily") or shadow_snapshot.get("eventFamily"))
    final_label = _optional_text(
        row.get("finalLabel")
        or row.get("label")
        or row.get("action")
        or shadow_snapshot.get("label")
        or shadow_snapshot.get("finalLabel")
    ) or "unknown"
    source_domain = _optional_text(row.get("sourceDomain")) or DEFAULT_SOURCE_DOMAIN
    source_batch = _optional_text(row.get("sourceBatchId") or row.get("jobId") or source_batch_id)
    raw_runtime_outputs = _raw_runtime_snapshot(row)
    if shadow_snapshot:
        raw_runtime_outputs["selectedShadow"] = shadow_snapshot
    raw_teacher_outputs = _raw_teacher_snapshot(row)
    source_event_count = _optional_int(row.get("sourceEventCount"))

    return LiveMiningClip(
        clip_id=_required_text(row, "clipId"),
        source_domain=source_domain,
        source_batch_id=source_batch,
        schema_version=_optional_text(row.get("schemaVersion")) or ANNOTATION_SCHEMA_VERSION,
        job_id=_optional_text(row.get("jobId")),
        request_id=_optional_text(row.get("requestId")),
        upload_trace_id=_optional_text(row.get("uploadTraceId")),
        inference_attempt_id=_optional_text(row.get("inferenceAttemptId")),
        model_version=_optional_text(row.get("modelVersion") or shadow_snapshot.get("runtime_fusion_model_version") or shadow_snapshot.get("modelVersion")),
        final_label=final_label,
        event_family=event_family,
        outcome=_optional_text(row.get("outcome")),
        shot_subtype=_optional_text(row.get("shotSubtype")),
        confidence=confidence,
        confidence_before_mapping=confidence_before_mapping,
        confidence_after_mapping=confidence_after_mapping,
        result_confidence=result_confidence,
        margin=margin,
        was_merged=bool(row.get("wasMerged", False)),
        source_event_count=source_event_count,
        clip_duration_seconds=_optional_float(row.get("clipDurationSeconds")),
        is_uncertain=bool(row.get("isUncertain", False)),
        raw_top_labels=raw_top_labels,
        comparison_raw_top_labels=comparison_top_labels,
        raw_runtime_outputs=raw_runtime_outputs,
        raw_teacher_outputs=raw_teacher_outputs,
    )


def _extract_margin(
    row: Mapping[str, Any],
    raw_top_labels: list[dict[str, Any]],
    comparison_top_labels: list[dict[str, Any]],
) -> float | None:
    margin = _optional_float(row.get("margin"))
    if margin is not None:
        return margin
    source = raw_top_labels or comparison_top_labels
    if len(source) < 2:
        return None
    top = float(source[0].get("confidence", 0.0) or 0.0)
    second = float(source[1].get("confidence", 0.0) or 0.0)
    return round(max(top - second, 0.0), 4)


def _extract_clip_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in ("clips",):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    for outer_key in ("results", "result"):
        outer = payload.get(outer_key)
        if isinstance(outer, Mapping):
            clips = outer.get("clips")
            if isinstance(clips, list):
                return [item for item in clips if isinstance(item, Mapping)]
    return []


def _raw_runtime_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "label": row.get("label") or row.get("finalLabel"),
        "eventFamily": row.get("eventFamily"),
        "outcome": row.get("outcome"),
        "shotSubtype": row.get("shotSubtype"),
        "confidence": row.get("confidence"),
        "confidenceBeforeMapping": row.get("confidenceBeforeMapping"),
        "confidenceAfterMapping": row.get("confidenceAfterMapping"),
        "resultConfidence": row.get("resultConfidence"),
        "rawTopLabels": row.get("rawTopLabels") or row.get("topLabels") or [],
        "comparisonRawTopLabels": row.get("comparisonRawTopLabels") or row.get("comparisonTopLabels") or [],
        "clipDurationSeconds": row.get("clipDurationSeconds"),
        "wasMerged": row.get("wasMerged"),
        "sourceEventCount": row.get("sourceEventCount"),
        "margin": row.get("margin"),
    }
    if row.get("runtimeFusionTemporalShadow"):
        snapshot["runtimeFusionTemporalShadow"] = row["runtimeFusionTemporalShadow"]
    if row.get("runtimeFusionDistilledShadow"):
        snapshot["runtimeFusionDistilledShadow"] = row["runtimeFusionDistilledShadow"]
    return {key: value for key, value in snapshot.items() if value is not None}


def _select_shadow_payload(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in (
        "runtimeFusionTemporalShadow",
        "runtimeFusionDistilledShadow",
        "runtimeFusionLoRAShadow",
        "runtimeFusionShadow",
        "runtimeFusionPrimary",
        "runtimeFusionLive",
    ):
        value = row.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _shadow_snapshot(shadow: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(shadow, Mapping):
        return {}
    snapshot = dict(shadow.get("runtime_fusion_snapshot") or shadow.get("snapshot") or {})
    snapshot.update(
        {
            "label": shadow.get("label"),
            "finalLabel": shadow.get("finalLabel"),
            "eventFamily": shadow.get("eventFamily") or shadow.get("event_family"),
            "outcome": shadow.get("outcome"),
            "shotSubtype": shadow.get("shotSubtype") or shadow.get("shot_subtype"),
            "confidence": shadow.get("confidence"),
            "confidenceBeforeMapping": shadow.get("confidenceBeforeMapping"),
            "confidenceAfterMapping": shadow.get("confidenceAfterMapping"),
            "resultConfidence": shadow.get("resultConfidence"),
            "runtime_fusion_model_version": shadow.get("runtime_fusion_model_version") or shadow.get("modelVersion"),
        }
    )
    return {key: value for key, value in snapshot.items() if value is not None}


def _raw_teacher_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    value = row.get("rawTeacherOutputs") or row.get("teacherOutputs") or row.get("teacher")
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _normalize_top_labels(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        value = value.get("topK") or value.get("topLabels") or value.get("labels") or []
    if not isinstance(value, list):
        return []
    labels: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        labels.append(
            {
                "label": _optional_text(item.get("label") or item.get("canonicalLabel") or item.get("rawLabel")) or "unknown",
                "confidence": _optional_float(item.get("confidence")) or 0.0,
                "modelVersion": _optional_text(item.get("modelVersion")),
            }
        )
    labels.sort(key=lambda item: float(item.get("confidence", 0.0) or 0.0), reverse=True)
    return labels


def _comparison_disagreement(clip: LiveMiningClip) -> bool:
    if not clip.raw_top_labels or not clip.comparison_raw_top_labels:
        return False
    return _normalized_label(clip.raw_top_labels[0].get("label")) != _normalized_label(clip.comparison_raw_top_labels[0].get("label"))


def _source_tags(
    clip: LiveMiningClip,
    reasons: Sequence[str],
    *,
    final_label: str,
    event_family: str,
    low_margin: bool,
    disagreement: bool,
) -> list[str]:
    tags = [clip.source_domain, DEFAULT_QUEUE_BUCKET]
    if final_label == "highlight":
        tags.append("highlight_predicted")
    if event_family == "other":
        tags.append("event_family_other")
    if low_margin:
        tags.append("low_margin")
    if disagreement:
        tags.append("disagreement")
    if clip.is_uncertain:
        tags.append("uncertain")
    if clip.was_merged or (clip.source_event_count or 0) > 1:
        tags.append("multi_event")
    tags.extend(reason for reason in reasons if reason not in tags)
    return _ordered_unique(tags)


def _primary_bucket(
    reasons: Sequence[str],
    *,
    final_label: str,
    event_family: str,
    low_margin: bool,
    disagreement: bool,
) -> str:
    if disagreement:
        return "cross_model_disagreement"
    if low_margin:
        return "low_margin"
    if final_label == "highlight" and event_family == "other":
        return "highlight_other"
    if final_label == "highlight":
        return "highlight_only"
    if event_family == "other":
        return "other_only"
    return reasons[0] if reasons else DEFAULT_QUEUE_BUCKET


def _score_stats(values: Iterable[float]) -> dict[str, float]:
    items = [float(value) for value in values]
    if not items:
        return {"min": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "min": round(min(items), 4),
        "max": round(max(items), 4),
        "mean": round(sum(items) / len(items), 4),
    }


def _count_by(items: Iterable[str | None]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if item is None:
            continue
        counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items()))


def _dominant(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _normalized_label(value: Any) -> str:
    if value is None:
        return "null"
    return str(value).strip().lower().replace(" ", "_")


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = _optional_text(row.get(key))
    if value is None:
        raise ValueError(f"Missing required field: {key}")
    return value


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ordered_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
