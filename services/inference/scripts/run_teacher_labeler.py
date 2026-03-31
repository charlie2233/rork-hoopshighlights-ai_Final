from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.inference.app.config import InferenceSettings
from services.inference.app.models import CandidateWindow
from services.inference.app.teacher import (
    QwenTeacherLabeler,
    TEACHER_PSEUDO_LABEL_MIN_CONFIDENCE,
    TEACHER_PSEUDO_LABEL_MIN_NEGATIVE_CONFIDENCE,
    build_silver_annotation_record,
    build_teacher_annotation_record,
    normalize_teacher_output,
    upsert_silver_annotation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the offline basketball teacher labeler on a clip window.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--candidate-id", type=str, default="teacher-audit-1")
    parser.add_argument("--source-domain", type=str, default="teacher_audit")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--runtime-json", type=Path, default=None)
    parser.add_argument("--silver-dataset", type=Path, default=None)
    parser.add_argument("--source-ref", type=str, default=None)
    parser.add_argument("--min-pseudo-confidence", type=float, default=TEACHER_PSEUDO_LABEL_MIN_CONFIDENCE)
    parser.add_argument("--min-negative-confidence", type=float, default=TEACHER_PSEUDO_LABEL_MIN_NEGATIVE_CONFIDENCE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = InferenceSettings()
    teacher = QwenTeacherLabeler(
        model_name=settings.teacher_model_name,
        frame_count=settings.teacher_frame_count,
    )
    candidate = CandidateWindow(
        candidateId=args.candidate_id,
        startTime=max(args.start, 0.0),
        endTime=max(args.end, args.start + 0.001),
        score=0.5,
        source="teacher_audit",
    )
    runtime_outputs = {}
    if args.runtime_json is not None:
        runtime_outputs = json.loads(args.runtime_json.read_text(encoding="utf-8"))

    suggestion = teacher.suggest(
        args.source,
        candidate,
        {
            "structuredSignals": runtime_outputs.get("structuredSignals") or {},
            "actionSummary": runtime_outputs.get("actionSummary") or {},
            "perceptionSummary": runtime_outputs.get("perceptionSummary") or {},
        },
    )
    normalized_suggestion = normalize_teacher_output(
        suggestion,
        min_training_confidence=args.min_pseudo_confidence,
        min_negative_confidence=args.min_negative_confidence,
    )

    annotation = build_teacher_annotation_record(
        clip_id=candidate.candidateId,
        source_domain=args.source_domain,
        teacher_output=normalized_suggestion,
        runtime_outputs=runtime_outputs,
        source_ref=args.source_ref or str(args.source),
        human_verified=False,
    ).as_dict()

    silver_record = build_silver_annotation_record(
        clip_id=candidate.candidateId,
        source_domain=args.source_domain,
        teacher_output=normalized_suggestion,
        runtime_outputs=runtime_outputs,
        source_ref=args.source_ref or str(args.source),
    )
    if args.silver_dataset is not None and silver_record is not None:
        upsert_silver_annotation(args.silver_dataset, silver_record)

    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / f"{candidate.candidateId}.teacher.json").write_text(
            json.dumps(normalized_suggestion, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (args.output_dir / f"{candidate.candidateId}.annotation.json").write_text(
            json.dumps(annotation, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (args.output_dir / f"{candidate.candidateId}.pseudo_label_gate.json").write_text(
            json.dumps((normalized_suggestion.get("pseudoLabel") or {}), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    print(json.dumps(annotation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
