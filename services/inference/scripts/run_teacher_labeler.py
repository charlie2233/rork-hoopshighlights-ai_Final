from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.inference.app.config import InferenceSettings
from services.inference.app.models import CandidateWindow
from services.inference.app.teacher import QwenTeacherLabeler, build_teacher_annotation_record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the offline basketball teacher labeler on a clip window.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--candidate-id", type=str, default="teacher-audit-1")
    parser.add_argument("--source-domain", type=str, default="teacher_audit")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--runtime-json", type=Path, default=None)
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

    annotation = build_teacher_annotation_record(
        clip_id=candidate.candidateId,
        source_domain=args.source_domain,
        teacher_output=suggestion,
        runtime_outputs=runtime_outputs,
        human_verified=False,
    ).as_dict()

    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / f"{candidate.candidateId}.teacher.json").write_text(
            json.dumps(suggestion, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (args.output_dir / f"{candidate.candidateId}.annotation.json").write_text(
            json.dumps(annotation, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    print(json.dumps(annotation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
