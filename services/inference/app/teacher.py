from __future__ import annotations

from dataclasses import dataclass
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .features import sample_video_frames
from .interfaces import TeacherLabeler
from .models import CandidateWindow
from ..datasets.annotations import load_annotation_rows, write_annotation_rows


TEACHER_PROMPT_VERSION = "qwen-basketball-teacher-v3"
TEACHER_SOURCE_DOMAIN = "offline_teacher"
TEACHER_ANNOTATION_SCHEMA_VERSION = "2026-03-31"
TEACHER_PSEUDO_LABEL_MIN_CONFIDENCE = 0.82
TEACHER_PSEUDO_LABEL_MIN_NEGATIVE_CONFIDENCE = 0.78
VALID_EVENT_FAMILIES = {"shot_attempt", "turnover", "defensive_event", "transition", "other"}
VALID_OUTCOMES = {"made", "missed", "blocked", "uncertain"}
VALID_SHOT_SUBTYPES = {"dunk", "layup", "jumper", "three", "putback"}
VALID_HARD_NEGATIVE_TYPES = {
    "dead_ball",
    "inbound",
    "dribble_only",
    "replay",
    "celebration",
    "camera_pan",
    "half_court_setup",
    "other",
}


@dataclass(frozen=True)
class TeacherAnnotationRecord:
    clipId: str
    sourceDomain: str
    schemaVersion: str
    sourceRef: str | None
    eventFamily: str
    outcome: str
    shotSubtype: str | None
    ballVisible: bool
    hoopVisible: bool
    ballNearRim: float
    ballThroughHoopLikelihood: float
    possessionChangeLikelihood: float
    transitionLikelihood: float
    teacherConfidence: float
    humanVerified: bool
    reviewerNotes: str
    rawRuntimeOutputs: dict[str, Any]
    rawTeacherOutputs: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "clipId": self.clipId,
            "sourceDomain": self.sourceDomain,
            "schemaVersion": self.schemaVersion,
            "sourceRef": self.sourceRef,
            "eventFamily": self.eventFamily,
            "outcome": self.outcome,
            "shotSubtype": self.shotSubtype,
            "ballVisible": self.ballVisible,
            "hoopVisible": self.hoopVisible,
            "ballNearRim": round(self.ballNearRim, 4),
            "ballThroughHoopLikelihood": round(self.ballThroughHoopLikelihood, 4),
            "possessionChangeLikelihood": round(self.possessionChangeLikelihood, 4),
            "transitionLikelihood": round(self.transitionLikelihood, 4),
            "teacherConfidence": round(self.teacherConfidence, 4),
            "humanVerified": self.humanVerified,
            "reviewerNotes": self.reviewerNotes,
            "rawRuntimeOutputs": self.rawRuntimeOutputs,
            "rawTeacherOutputs": self.rawTeacherOutputs,
        }


@dataclass
class QwenTeacherLabeler(TeacherLabeler):
    model_name: str
    device: str = "auto"
    frame_count: int = 4

    def suggest(self, source_path: Path, candidate: CandidateWindow, context: dict[str, Any]) -> dict[str, Any]:
        frames = sample_video_frames(
            source_path,
            frame_count=self.frame_count,
            start_seconds=candidate.startTime,
            end_seconds=candidate.endTime,
        )
        if not frames:
            return self._failure(candidate, "no_frames_sampled")

        try:
            processor, model, runtime_device = _load_backend(self.model_name, self.device)
            prompt = _build_teacher_prompt(candidate, context)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        *({"type": "image", "image": frame} for frame in frames),
                    ],
                }
            ]

            chat_prompt = processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = processor(text=[chat_prompt], images=frames, return_tensors="pt", padding=True)
            inputs = _move_inputs(inputs, runtime_device)
            model = model.to(runtime_device)
            generated = model.generate(**inputs, max_new_tokens=200)
            prompt_token_count = inputs["input_ids"].shape[1]
            decoded = processor.batch_decode(
                generated[:, prompt_token_count:],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            )[0]
            parsed = _parse_teacher_response(decoded)
            evidence = _build_teacher_evidence(candidate, context, len(frames))
            result = normalize_teacher_output(
                {
                    **parsed,
                    "candidateId": candidate.candidateId,
                    "responseText": decoded.strip(),
                    "evidence": evidence,
                    "promptVersion": TEACHER_PROMPT_VERSION,
                    "annotationSchemaVersion": TEACHER_ANNOTATION_SCHEMA_VERSION,
                    "modelVersion": f"teacher:{self.model_name}",
                }
            )
            return {
                "status": "ok",
                "modelVersion": f"teacher:{self.model_name}",
                "promptVersion": TEACHER_PROMPT_VERSION,
                "annotationSchemaVersion": TEACHER_ANNOTATION_SCHEMA_VERSION,
                "sourceDomain": TEACHER_SOURCE_DOMAIN,
                "clipId": candidate.candidateId,
                "candidateId": candidate.candidateId,
                **result,
            }
        except Exception as exc:
            return self._failure(candidate, f"inference_failed:{exc.__class__.__name__}", extra={"error": str(exc)})

    def _failure(self, candidate: CandidateWindow, reason: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "modelVersion": f"teacher:{self.model_name}",
            "promptVersion": TEACHER_PROMPT_VERSION,
            "candidateId": candidate.candidateId,
            "failureReason": reason,
            **(extra or {}),
        }


def _build_teacher_prompt(candidate: CandidateWindow, context: dict[str, Any]) -> str:
    structured_signals = context.get("structuredSignals") or {}
    action_summary = context.get("actionSummary") or {}
    perception_summary = context.get("perceptionSummary") or {}
    payload = {
        "candidateId": candidate.candidateId,
        "startTime": round(candidate.startTime, 3),
        "endTime": round(candidate.endTime, 3),
        "structuredSignals": structured_signals,
        "actionSummary": action_summary,
        "perceptionSummary": perception_summary,
    }
    return (
        "You are auditing a basketball highlight clip. "
        "Return strict JSON with keys eventFamily, outcome, shotSubtype, displayLabelSuggestion, teacherConfidence, "
        "hardNegativeType, pseudoLabelRecommended, evidence, and notes. "
        "Use eventFamily from {shot_attempt, turnover, defensive_event, transition, other}. "
        "Use outcome from {made, missed, blocked, uncertain}. "
        "Only set shotSubtype for shot attempts using {dunk, layup, jumper, three, putback}. "
        "For non-highlights, set hardNegativeType from {dead_ball, inbound, dribble_only, replay, celebration, camera_pan, half_court_setup, other}. "
        "Set pseudoLabelRecommended=true only when the label is strong enough to add to a silver training set. "
        f"Context: {json.dumps(payload, sort_keys=True)}"
    )


def _parse_teacher_response(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if not candidate:
        return {}
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.IGNORECASE | re.DOTALL)
        if fenced is not None:
            try:
                return json.loads(fenced.group(1))
            except json.JSONDecodeError:
                pass
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"notes": candidate}


def build_teacher_annotation_record(
    *,
    clip_id: str,
    source_domain: str,
    teacher_output: dict[str, Any],
    runtime_outputs: dict[str, Any] | None = None,
    source_ref: str | None = None,
    human_verified: bool = False,
    reviewer_notes: str | None = None,
) -> TeacherAnnotationRecord:
    normalized_teacher_output = normalize_teacher_output(teacher_output)
    evidence = normalized_teacher_output.get("evidence") or {}
    structured_signals = evidence.get("structuredSignals") or {}
    perception_summary = evidence.get("perceptionSummary") or {}
    teacher_confidence = _coerce_confidence(normalized_teacher_output.get("teacherConfidence"))
    if teacher_confidence is None:
        teacher_confidence = _coerce_confidence(normalized_teacher_output.get("confidence")) or 0.0
    return TeacherAnnotationRecord(
        clipId=clip_id,
        sourceDomain=source_domain,
        schemaVersion=TEACHER_ANNOTATION_SCHEMA_VERSION,
        sourceRef=source_ref,
        eventFamily=str(normalized_teacher_output.get("eventFamily") or "other"),
        outcome=str(normalized_teacher_output.get("outcome") or "uncertain"),
        shotSubtype=normalized_teacher_output.get("shotSubtype"),
        ballVisible=bool(perception_summary.get("ballVisible", False)),
        hoopVisible=bool(perception_summary.get("hoopVisible", False)),
        ballNearRim=_coerce_float(structured_signals.get("ballNearRim"), 0.0),
        ballThroughHoopLikelihood=_coerce_float(structured_signals.get("ballThroughHoopLikelihood"), 0.0),
        possessionChangeLikelihood=_coerce_float(structured_signals.get("possessionChangeLikelihood"), 0.0),
        transitionLikelihood=_coerce_float(
            structured_signals.get("transitionLikelihood", structured_signals.get("transitionSpeedScore")),
            0.0,
        ),
        teacherConfidence=teacher_confidence,
        humanVerified=human_verified,
        reviewerNotes=reviewer_notes or str(normalized_teacher_output.get("notes") or ""),
        rawRuntimeOutputs=runtime_outputs or {},
        rawTeacherOutputs=normalized_teacher_output,
    )


def build_silver_annotation_record(
    *,
    clip_id: str,
    source_domain: str,
    teacher_output: dict[str, Any],
    runtime_outputs: dict[str, Any] | None = None,
    source_ref: str | None = None,
) -> TeacherAnnotationRecord | None:
    normalized = normalize_teacher_output(teacher_output)
    pseudo_label = normalized.get("pseudoLabel") or {}
    if not pseudo_label.get("eligible", False):
        return None
    return build_teacher_annotation_record(
        clip_id=clip_id,
        source_domain=source_domain,
        teacher_output=normalized,
        runtime_outputs=runtime_outputs,
        source_ref=source_ref,
        human_verified=False,
    )


def upsert_silver_annotation(silver_dataset_path: Path, record: TeacherAnnotationRecord) -> None:
    existing = load_annotation_rows(silver_dataset_path) if silver_dataset_path.exists() else []
    by_clip_id = {item.clipId: item for item in existing}
    by_clip_id[record.clipId] = record
    ordered = sorted(by_clip_id.values(), key=lambda item: item.clipId)
    write_annotation_rows(silver_dataset_path, ordered)


def normalize_teacher_output(
    teacher_output: dict[str, Any],
    *,
    min_training_confidence: float = TEACHER_PSEUDO_LABEL_MIN_CONFIDENCE,
    min_negative_confidence: float = TEACHER_PSEUDO_LABEL_MIN_NEGATIVE_CONFIDENCE,
) -> dict[str, Any]:
    normalized = dict(teacher_output)
    event_family = _normalize_event_family(normalized.get("eventFamily"))
    outcome = _normalize_outcome(normalized.get("outcome"), event_family)
    shot_subtype = _normalize_shot_subtype(normalized.get("shotSubtype"), event_family)
    confidence = _coerce_confidence(normalized.get("teacherConfidence"))
    if confidence is None:
        confidence = _coerce_confidence(normalized.get("confidence"))
    evidence = dict(normalized.get("evidence") or {})
    hard_negative_type = _normalize_hard_negative_type(normalized.get("hardNegativeType"), event_family)
    pseudo_label = _build_pseudo_label_gate(
        event_family=event_family,
        outcome=outcome,
        shot_subtype=shot_subtype,
        confidence=confidence,
        evidence=evidence,
        requested=bool(normalized.get("pseudoLabelRecommended", False)),
        min_training_confidence=min_training_confidence,
        min_negative_confidence=min_negative_confidence,
    )
    normalized.update(
        {
            "eventFamily": event_family,
            "outcome": outcome,
            "shotSubtype": shot_subtype,
            "teacherConfidence": confidence,
            "confidence": confidence,
            "hardNegativeType": hard_negative_type,
            "pseudoLabel": pseudo_label,
            "promptVersion": normalized.get("promptVersion") or TEACHER_PROMPT_VERSION,
            "annotationSchemaVersion": normalized.get("annotationSchemaVersion") or TEACHER_ANNOTATION_SCHEMA_VERSION,
            "evidence": evidence,
        }
    )
    return normalized


def _coerce_confidence(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    return min(max(confidence, 0.0), 1.0)


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_event_family(value: Any) -> str:
    text = str(value or "other").strip().lower()
    return text if text in VALID_EVENT_FAMILIES else "other"


def _normalize_outcome(value: Any, event_family: str) -> str:
    text = str(value or "uncertain").strip().lower()
    if text not in VALID_OUTCOMES:
        return "uncertain"
    if event_family not in {"shot_attempt", "defensive_event"}:
        return "uncertain"
    if event_family == "defensive_event" and text not in {"blocked", "uncertain"}:
        return "uncertain"
    return text


def _normalize_shot_subtype(value: Any, event_family: str) -> str | None:
    if event_family != "shot_attempt":
        return None
    text = str(value).strip().lower() if value not in {None, ""} else None
    return text if text in VALID_SHOT_SUBTYPES else None


def _normalize_hard_negative_type(value: Any, event_family: str) -> str | None:
    if event_family != "other":
        return None
    text = str(value or "other").strip().lower()
    return text if text in VALID_HARD_NEGATIVE_TYPES else "other"


def _build_pseudo_label_gate(
    *,
    event_family: str,
    outcome: str,
    shot_subtype: str | None,
    confidence: float | None,
    evidence: dict[str, Any],
    requested: bool,
    min_training_confidence: float,
    min_negative_confidence: float,
) -> dict[str, Any]:
    if confidence is None:
        return {"eligible": False, "reason": "missing_confidence", "threshold": min_training_confidence}

    threshold = min_negative_confidence if event_family == "other" else min_training_confidence
    if confidence < threshold:
        return {
            "eligible": False,
            "reason": "confidence_below_threshold",
            "threshold": threshold,
            "requested": requested,
        }

    structured_signals = dict(evidence.get("structuredSignals") or {})
    perception_summary = dict(evidence.get("perceptionSummary") or {})
    ball_visible = bool(perception_summary.get("ballVisible", False))
    hoop_visible = bool(perception_summary.get("hoopVisible", False))
    strong_shot_evidence = (
        ball_visible
        or hoop_visible
        or _coerce_float(structured_signals.get("ballNearRim"), 0.0) >= 0.45
        or _coerce_float(structured_signals.get("ballThroughHoopLikelihood"), 0.0) >= 0.35
    )

    if event_family == "shot_attempt":
        if shot_subtype is None and outcome in {"made", "missed"}:
            return {"eligible": False, "reason": "shot_missing_subtype", "threshold": threshold, "requested": requested}
        if not strong_shot_evidence:
            return {"eligible": False, "reason": "weak_shot_evidence", "threshold": threshold, "requested": requested}
    if event_family == "transition" and _coerce_float(structured_signals.get("transitionLikelihood"), 0.0) < 0.45:
        return {"eligible": False, "reason": "weak_transition_evidence", "threshold": threshold, "requested": requested}
    if event_family == "defensive_event" and outcome != "blocked":
        return {"eligible": False, "reason": "defensive_outcome_uncertain", "threshold": threshold, "requested": requested}

    return {
        "eligible": True,
        "reason": "confidence_gated_teacher_label",
        "threshold": threshold,
        "requested": requested,
    }


def _build_teacher_evidence(candidate: CandidateWindow, context: dict[str, Any], frame_count: int) -> dict[str, Any]:
    structured_signals = context.get("structuredSignals") or {}
    action_summary = context.get("actionSummary") or {}
    perception_summary = context.get("perceptionSummary") or {}
    return {
        "frameCount": frame_count,
        "candidateId": candidate.candidateId,
        "candidateWindow": {
            "startSeconds": round(candidate.startTime, 3),
            "endSeconds": round(candidate.endTime, 3),
            "durationSeconds": round(candidate.endTime - candidate.startTime, 3),
        },
        "structuredSignals": structured_signals,
        "actionSummary": action_summary,
        "perceptionSummary": perception_summary,
    }


@lru_cache(maxsize=2)
def _load_backend(model_name: str, device: str) -> tuple[Any, Any, Any]:
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor  # type: ignore

    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModelForImageTextToText.from_pretrained(model_name)
    runtime_device = _resolve_device(device)
    return processor, model, runtime_device


def _resolve_device(device: str):
    import torch

    if device == "cpu":
        return torch.device("cpu")
    if device == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    if device == "mps" and torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _move_inputs(inputs: dict[str, Any], device: Any) -> dict[str, Any]:
    return {
        key: value.to(device) if hasattr(value, "to") else value
        for key, value in inputs.items()
    }
