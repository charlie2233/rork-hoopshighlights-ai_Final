from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.inference.app.config import InferenceSettings
from services.inference.app.models import CandidateWindow
from services.inference.app.teacher import QwenTeacherLabeler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the offline basketball teacher labeler on a clip window.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--candidate-id", type=str, default="teacher-audit-1")
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
    suggestion = teacher.suggest(
        args.source,
        candidate,
        {
            "structuredSignals": {},
            "actionSummary": {},
            "perceptionSummary": {},
        },
    )
    print(json.dumps(suggestion, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
