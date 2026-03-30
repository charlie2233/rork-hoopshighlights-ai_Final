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


TEACHER_PROMPT_VERSION = "qwen-basketball-teacher-v2"
TEACHER_SOURCE_DOMAIN = "offline_teacher"
TEACHER_ANNOTATION_SCHEMA_VERSION = "2026-03-29"


@dataclass(frozen=True)
class TeacherAnnotationRecord:
    clipId: str
    sourceDomain: str
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
            teacher_confidence = _coerce_confidence(parsed.get("teacherConfidence"))
            if teacher_confidence is None:
                teacher_confidence = _coerce_confidence(parsed.get("confidence"))
            return {
                "status": "ok",
                "modelVersion": f"teacher:{self.model_name}",
                "promptVersion": TEACHER_PROMPT_VERSION,
                "annotationSchemaVersion": TEACHER_ANNOTATION_SCHEMA_VERSION,
                "sourceDomain": TEACHER_SOURCE_DOMAIN,
                "clipId": candidate.candidateId,
                "candidateId": candidate.candidateId,
                "responseText": decoded.strip(),
                "eventFamily": parsed.get("eventFamily"),
                "outcome": parsed.get("outcome"),
                "shotSubtype": parsed.get("shotSubtype"),
                "displayLabelSuggestion": parsed.get("displayLabelSuggestion"),
                "teacherConfidence": teacher_confidence,
                "confidence": teacher_confidence,
                "notes": parsed.get("notes"),
                "evidence": evidence,
                "rawTeacherOutputs": {
                    "responseText": decoded.strip(),
                    "parsed": parsed,
                    "promptVersion": TEACHER_PROMPT_VERSION,
                    "annotationSchemaVersion": TEACHER_ANNOTATION_SCHEMA_VERSION,
                    "modelVersion": f"teacher:{self.model_name}",
                },
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
        "Return strict JSON with keys eventFamily, outcome, shotSubtype, displayLabelSuggestion, teacherConfidence, evidence, and notes. "
        "Use eventFamily from {shot_attempt, turnover, defensive_event, transition, other}. "
        "Use outcome from {made, missed, blocked, uncertain}. "
        "Only set shotSubtype for shot attempts using {dunk, layup, jumper, three, putback}. "
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
    human_verified: bool = False,
    reviewer_notes: str | None = None,
) -> TeacherAnnotationRecord:
    evidence = teacher_output.get("evidence") or {}
    structured_signals = evidence.get("structuredSignals") or {}
    perception_summary = evidence.get("perceptionSummary") or {}
    teacher_confidence = _coerce_confidence(teacher_output.get("teacherConfidence"))
    if teacher_confidence is None:
        teacher_confidence = _coerce_confidence(teacher_output.get("confidence")) or 0.0
    return TeacherAnnotationRecord(
        clipId=clip_id,
        sourceDomain=source_domain,
        eventFamily=str(teacher_output.get("eventFamily") or "other"),
        outcome=str(teacher_output.get("outcome") or "uncertain"),
        shotSubtype=teacher_output.get("shotSubtype"),
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
        reviewerNotes=reviewer_notes or str(teacher_output.get("notes") or ""),
        rawRuntimeOutputs=runtime_outputs or {},
        rawTeacherOutputs=teacher_output,
    )


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
