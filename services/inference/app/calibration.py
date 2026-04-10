from __future__ import annotations

from dataclasses import dataclass
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RUNTIME_CALIBRATION_SCHEMA_VERSION = "runtime-calibration-v1"
RUNTIME_CALIBRATION_PATH = Path(__file__).resolve().parents[1] / "evals" / "runtime_calibration.json"

_DIMENSION_LABEL_ALIASES: dict[str, dict[str, str]] = {
    "eventFamily": {
        "shot": "shot_attempt",
        "shot_attempt": "shot_attempt",
        "defense": "defensive_event",
        "defensive": "defensive_event",
    },
    "outcome": {
        "make": "made",
        "made": "made",
        "miss": "missed",
        "missed": "missed",
        "block": "blocked",
        "blocked": "blocked",
        "uncertain": "uncertain",
    },
    "shotSubtype": {
        "fast_break": "fast_break",
        "fast break": "fast_break",
        "three pointer": "three",
        "three-point": "three",
        "3 point": "three",
        "3-pointer": "three",
    },
}


@dataclass(frozen=True)
class CalibrationBin:
    min_score: float
    max_score: float
    count: int
    positives: int
    calibrated_score: float

    def contains(self, score: float) -> bool:
        if self.min_score <= score <= self.max_score:
            return True
        if score >= 1.0 and self.max_score >= 1.0:
            return True
        return False


@dataclass(frozen=True)
class LabelCalibration:
    label: str
    bins: tuple[CalibrationBin, ...]
    fallback_score: float
    support: int

    def calibrate(self, score: float) -> float:
        if not self.bins:
            return round(min(max(score, 0.0), 1.0), 4)

        clamped = min(max(score, 0.0), 1.0)
        for bucket in self.bins:
            if bucket.contains(clamped):
                return round(min(max(bucket.calibrated_score, 0.0), 1.0), 4)

        if clamped <= self.bins[0].min_score:
            return round(min(max(self.bins[0].calibrated_score, 0.0), 1.0), 4)
        return round(min(max(self.bins[-1].calibrated_score, 0.0), 1.0), 4)


@dataclass(frozen=True)
class RuntimeCalibration:
    schema_version: str
    source_dataset: str
    split_strategy: str
    dimensions: dict[str, dict[str, LabelCalibration]]
    holdout_metrics: dict[str, Any]
    notes: tuple[str, ...] = ()

    def calibrate_distribution(self, dimension: str, distribution: dict[str, float]) -> dict[str, float]:
        dimension_calibration = self.dimensions.get(dimension)
        if not dimension_calibration:
            return dict(distribution)

        calibrated: dict[str, float] = {}
        for label, score in distribution.items():
            label_calibration = dimension_calibration.get(_alias_label(dimension, label))
            calibrated[label] = label_calibration.calibrate(score) if label_calibration else round(min(max(score, 0.0), 1.0), 4)
        return calibrated

    def calibration_version_for(self, dimension: str) -> str | None:
        if dimension in self.dimensions:
            return self.schema_version
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "sourceDataset": self.source_dataset,
            "splitStrategy": self.split_strategy,
            "dimensions": {
                dimension: {
                    label: {
                        "label": calibration.label,
                        "bins": [
                            {
                                "minScore": bucket.min_score,
                                "maxScore": bucket.max_score,
                                "count": bucket.count,
                                "positives": bucket.positives,
                                "calibratedScore": bucket.calibrated_score,
                            }
                            for bucket in calibration.bins
                        ],
                        "fallbackScore": calibration.fallback_score,
                        "support": calibration.support,
                    }
                    for label, calibration in label_calibrations.items()
                }
                for dimension, label_calibrations in self.dimensions.items()
            },
            "holdoutMetrics": self.holdout_metrics,
            "notes": list(self.notes),
        }


def load_runtime_calibration(path: Path | None = None) -> RuntimeCalibration:
    calibration_path = path or RUNTIME_CALIBRATION_PATH
    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    return _parse_runtime_calibration(payload)


@lru_cache(maxsize=1)
def get_runtime_calibration(path: str | None = None) -> RuntimeCalibration | None:
    calibration_path = Path(path) if path else RUNTIME_CALIBRATION_PATH
    if not calibration_path.exists():
        return None
    return load_runtime_calibration(calibration_path)


def _parse_runtime_calibration(payload: dict[str, Any]) -> RuntimeCalibration:
    dimensions: dict[str, dict[str, LabelCalibration]] = {}
    for dimension, label_calibrations in (payload.get("dimensions") or {}).items():
        parsed_labels: dict[str, LabelCalibration] = {}
        for label, calibration_payload in (label_calibrations or {}).items():
            bins = tuple(
                CalibrationBin(
                    min_score=float(item.get("minScore", 0.0)),
                    max_score=float(item.get("maxScore", 1.0)),
                    count=int(item.get("count", 0)),
                    positives=int(item.get("positives", 0)),
                    calibrated_score=float(item.get("calibratedScore", item.get("fallbackScore", 0.0))),
                )
                for item in calibration_payload.get("bins", [])
            )
            parsed_labels[str(label)] = LabelCalibration(
                label=str(calibration_payload.get("label", label)),
                bins=bins,
                fallback_score=float(calibration_payload.get("fallbackScore", 0.0)),
                support=int(calibration_payload.get("support", 0)),
            )
        dimensions[str(dimension)] = parsed_labels

    return RuntimeCalibration(
        schema_version=str(payload.get("schemaVersion", RUNTIME_CALIBRATION_SCHEMA_VERSION)),
        source_dataset=str(payload.get("sourceDataset", "")),
        split_strategy=str(payload.get("splitStrategy", "")),
        dimensions=dimensions,
        holdout_metrics=dict(payload.get("holdoutMetrics") or {}),
        notes=tuple(str(item) for item in payload.get("notes", []) if item is not None),
    )


def _alias_label(dimension: str, label: str) -> str:
    alias_map = _DIMENSION_LABEL_ALIASES.get(dimension, {})
    return alias_map.get(label, label)
