from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from services.inference.app.distilled_clip_encoder import DistilledClipEncoderBundle


TEACHER_DISTILLED_STUDENT_SCHEMA_VERSION = "teacher-distilled-clip-student-v1"
TEACHER_DISTILLED_STUDENT_FEATURE_VERSION = "teacher-distilled-clip-features-v1"
TEACHER_DISTILLED_STUDENT_MODEL_VERSION = "teacher-distilled-clip-student-v1"
TEACHER_DISTILLED_STUDENT_BUNDLE_PATH = Path(__file__).resolve().parents[2] / "models" / "teacher_distilled_clip_student_v1.json"


def load_teacher_distilled_student_bundle(path: Path | None = None) -> DistilledClipEncoderBundle:
    bundle_path = path or TEACHER_DISTILLED_STUDENT_BUNDLE_PATH
    return DistilledClipEncoderBundle.load(bundle_path)


@lru_cache(maxsize=1)
def get_teacher_distilled_student_bundle(path: str | None = None) -> DistilledClipEncoderBundle | None:
    bundle_path = Path(path) if path else TEACHER_DISTILLED_STUDENT_BUNDLE_PATH
    if not bundle_path.exists():
        return None
    return load_teacher_distilled_student_bundle(bundle_path)
