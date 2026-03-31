from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .annotations import ANNOTATION_SCHEMA_VERSION, ClipAnnotation, annotation_template, write_annotation_rows


DEFAULT_BARD_SOURCE_DOMAIN = "bard:events"
DEFAULT_EBARD_SOURCE_DOMAIN = "ebard:detections"
DEFAULT_SPORTSMOT_SOURCE_DOMAIN = "sportsmot:tracking"
DEFAULT_TRACKID3X3_SOURCE_DOMAIN = "trackid3x3:tracking"
DEFAULT_BARD_SOURCE_DATASET = "BARD"
DEFAULT_EBARD_SOURCE_DATASET = "E-BARD"
DEFAULT_SPORTSMOT_SOURCE_DATASET = "SportsMOT"
DEFAULT_TRACKID3X3_SOURCE_DATASET = "TrackID3x3"


@dataclass(frozen=True)
class ImportResult:
    source_kind: str
    source_domain: str
    source_dataset: str
    rows: list[ClipAnnotation]

    def to_summary(self) -> dict[str, Any]:
        return {
            "schemaVersion": ANNOTATION_SCHEMA_VERSION,
            "sourceKind": self.source_kind,
            "sourceDomain": self.source_domain,
            "sourceDataset": self.source_dataset,
            "rowCount": len(self.rows),
            "humanVerifiedCount": sum(1 for row in self.rows if row.humanVerified),
        }


def import_bard_event_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    source_domain: str = DEFAULT_BARD_SOURCE_DOMAIN,
    source_dataset: str = DEFAULT_BARD_SOURCE_DATASET,
) -> list[ClipAnnotation]:
    imported: list[ClipAnnotation] = []
    for row in rows:
        imported.append(_import_bard_event_row(row, source_domain=source_domain, source_dataset=source_dataset))
    return imported


def import_ebard_detection_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    source_domain: str = DEFAULT_EBARD_SOURCE_DOMAIN,
    source_dataset: str = DEFAULT_EBARD_SOURCE_DATASET,
) -> list[ClipAnnotation]:
    imported: list[ClipAnnotation] = []
    for row in rows:
        imported.append(_import_ebard_detection_row(row, source_domain=source_domain, source_dataset=source_dataset))
    return imported


def import_sportsmot_tracking_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    source_domain: str = DEFAULT_SPORTSMOT_SOURCE_DOMAIN,
    source_dataset: str = DEFAULT_SPORTSMOT_SOURCE_DATASET,
) -> list[ClipAnnotation]:
    imported: list[ClipAnnotation] = []
    for row in rows:
        imported.append(
            _import_tracking_row(
                row,
                source_kind="sportsmot-tracking",
                source_domain=source_domain,
                source_dataset=source_dataset,
            )
        )
    return imported


def import_trackid3x3_tracking_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    source_domain: str = DEFAULT_TRACKID3X3_SOURCE_DOMAIN,
    source_dataset: str = DEFAULT_TRACKID3X3_SOURCE_DATASET,
) -> list[ClipAnnotation]:
    imported: list[ClipAnnotation] = []
    for row in rows:
        imported.append(
            _import_tracking_row(
                row,
                source_kind="trackid3x3-tracking",
                source_domain=source_domain,
                source_dataset=source_dataset,
            )
        )
    return imported


def import_external_basketball_dataset(
    rows: Iterable[Mapping[str, Any]],
    *,
    source_kind: str,
    source_domain: str | None = None,
    source_dataset: str | None = None,
) -> ImportResult:
    normalized_kind = _normalize_source_kind(source_kind)
    if normalized_kind == "bard-event":
        imported_rows = import_bard_event_rows(
            rows,
            source_domain=source_domain or DEFAULT_BARD_SOURCE_DOMAIN,
            source_dataset=source_dataset or DEFAULT_BARD_SOURCE_DATASET,
        )
    elif normalized_kind == "ebard-detection":
        imported_rows = import_ebard_detection_rows(
            rows,
            source_domain=source_domain or DEFAULT_EBARD_SOURCE_DOMAIN,
            source_dataset=source_dataset or DEFAULT_EBARD_SOURCE_DATASET,
        )
    elif normalized_kind == "sportsmot-tracking":
        imported_rows = import_sportsmot_tracking_rows(
            rows,
            source_domain=source_domain or DEFAULT_SPORTSMOT_SOURCE_DOMAIN,
            source_dataset=source_dataset or DEFAULT_SPORTSMOT_SOURCE_DATASET,
        )
    elif normalized_kind == "trackid3x3-tracking":
        imported_rows = import_trackid3x3_tracking_rows(
            rows,
            source_domain=source_domain or DEFAULT_TRACKID3X3_SOURCE_DOMAIN,
            source_dataset=source_dataset or DEFAULT_TRACKID3X3_SOURCE_DATASET,
        )
    else:
        raise ValueError(f"Unsupported source kind: {source_kind}")
    return ImportResult(
        source_kind=normalized_kind,
        source_domain=source_domain
        or (
            DEFAULT_BARD_SOURCE_DOMAIN
            if normalized_kind == "bard-event"
            else DEFAULT_EBARD_SOURCE_DOMAIN
            if normalized_kind == "ebard-detection"
            else DEFAULT_SPORTSMOT_SOURCE_DOMAIN
            if normalized_kind == "sportsmot-tracking"
            else DEFAULT_TRACKID3X3_SOURCE_DOMAIN
        ),
        source_dataset=source_dataset
        or (
            DEFAULT_BARD_SOURCE_DATASET
            if normalized_kind == "bard-event"
            else DEFAULT_EBARD_SOURCE_DATASET
            if normalized_kind == "ebard-detection"
            else DEFAULT_SPORTSMOT_SOURCE_DATASET
            if normalized_kind == "sportsmot-tracking"
            else DEFAULT_TRACKID3X3_SOURCE_DATASET
        ),
        rows=imported_rows,
    )


def load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON array or JSONL file at {path}")
    return payload


def write_imported_rows(path: Path, rows: Sequence[ClipAnnotation]) -> None:
    write_annotation_rows(path, rows)


def _import_bard_event_row(
    row: Mapping[str, Any],
    *,
    source_domain: str,
    source_dataset: str,
) -> ClipAnnotation:
    clip_id = _first_text(row, "clipId", "clip_id", "id", "videoId", "video_id")
    raw_label = _first_text(row, "label", "eventLabel", "event_label", "action", "category", "class")
    event_family = _first_text(row, "eventFamily", "event_family") or _bard_event_family(raw_label)
    outcome = _first_text(row, "outcome", "result") or _bard_outcome(raw_label)
    shot_subtype = _first_text(row, "shotSubtype", "shot_subtype") or _bard_shot_subtype(raw_label, event_family=event_family)
    if event_family != "shot_attempt" and shot_subtype in {"dunk", "layup", "jumper", "three", "putback"}:
        shot_subtype = shot_subtype
    ball_visible = _first_bool(row, "ballVisible", "ball_visible", default=event_family == "shot_attempt")
    hoop_visible = _first_bool(row, "hoopVisible", "hoop_visible", default=event_family == "shot_attempt")
    ball_near_rim = _first_probability(row, "ballNearRim", "ball_near_rim")
    ball_through_hoop = _first_probability(row, "ballThroughHoopLikelihood", "ball_through_hoop_likelihood")
    possession_change = _first_probability(row, "possessionChangeLikelihood", "possession_change_likelihood")
    transition_likelihood = _first_probability(row, "transitionLikelihood", "transition_likelihood")
    teacher_confidence = _first_probability(row, "teacherConfidence", "teacher_confidence", default=_first_probability(row, "confidence", default=0.78))
    source_ref = _first_text(row, "sourceRef", "source_ref", "path", "videoPath", "video_path")
    evidence = _normalize_evidence(row)
    annotation = annotation_template(clip_id=clip_id, source_domain=source_domain, source_kind="bard-event")
    annotation.sourceRef = source_ref
    annotation.eventFamily = event_family
    annotation.outcome = outcome
    annotation.shotSubtype = shot_subtype
    annotation.ballVisible = ball_visible
    annotation.hoopVisible = hoop_visible
    annotation.ballNearRim = ball_near_rim
    annotation.ballThroughHoopLikelihood = ball_through_hoop
    annotation.possessionChangeLikelihood = possession_change
    annotation.transitionLikelihood = transition_likelihood
    annotation.teacherConfidence = teacher_confidence
    annotation.humanVerified = bool(_first_bool(row, "humanVerified", "human_verified", default=False))
    annotation.reviewerNotes = _first_text(row, "reviewerNotes", "reviewer_notes", "notes") or ""
    annotation.rawRuntimeOutputs = _canonical_runtime_payload(
        row,
        source_kind="bard-event",
        source_dataset=source_dataset,
        source_domain=source_domain,
        source_label=raw_label,
    )
    annotation.rawTeacherOutputs = {
        "sourceDataset": source_dataset,
        "sourceDomain": source_domain,
        "sourceDomainTag": source_domain,
        "sourceKind": "bard-event",
        "sourceLabel": raw_label,
        "evidence": evidence,
        "evidenceFields": sorted(evidence),
        "canonicalHierarchy": _canonical_hierarchy_payload(
            event_family=event_family,
            outcome=outcome,
            shot_subtype=shot_subtype,
        ),
        "importVersion": ANNOTATION_SCHEMA_VERSION,
        "notes": _first_text(row, "teacherNotes", "teacher_notes", "notes") or "BARD event supervision imported into canonical hierarchy.",
        "confidence": teacher_confidence,
    }
    return annotation


def _import_ebard_detection_row(
    row: Mapping[str, Any],
    *,
    source_domain: str,
    source_dataset: str,
) -> ClipAnnotation:
    clip_id = _first_text(row, "clipId", "clip_id", "id", "videoId", "video_id")
    detections = _normalize_detections(row)
    source_ref = _first_text(row, "sourceRef", "source_ref", "path", "videoPath", "video_path")
    evidence = _normalize_evidence(row)
    ball_visible = _first_bool(row, "ballVisible", "ball_visible", default=_detection_present(detections, {"ball", "basketball"}))
    hoop_visible = _first_bool(row, "hoopVisible", "hoop_visible", default=_detection_present(detections, {"rim", "hoop", "backboard"}))
    ball_near_rim = _compute_ball_near_rim(row, detections)
    ball_through_hoop = _first_probability(row, "ballThroughHoopLikelihood", "ball_through_hoop_likelihood", default=0.0 if ball_near_rim is None else min(1.0, ball_near_rim * 0.85))
    possession_change = _first_probability(row, "possessionChangeLikelihood", "possession_change_likelihood", default=0.1 if _detection_present(detections, {"steal", "turnover"}) else 0.0)
    transition_likelihood = _first_probability(row, "transitionLikelihood", "transition_likelihood", default=0.6 if _detection_present(detections, {"player", "ball"}) and not hoop_visible else 0.1)
    teacher_confidence = _first_probability(row, "teacherConfidence", "teacher_confidence", default=_first_probability(row, "confidence", default=0.72))
    event_family = _first_text(row, "eventFamily", "event_family") or _ebard_event_family(detections, ball_visible=ball_visible, hoop_visible=hoop_visible, ball_near_rim=ball_near_rim)
    outcome = _first_text(row, "outcome", "result") or _ebard_outcome(ball_visible=ball_visible, hoop_visible=hoop_visible, ball_near_rim=ball_near_rim)
    shot_subtype = _first_text(row, "shotSubtype", "shot_subtype")
    annotation = annotation_template(clip_id=clip_id, source_domain=source_domain, source_kind="ebard-detection")
    annotation.sourceRef = source_ref
    annotation.eventFamily = event_family
    annotation.outcome = outcome
    annotation.shotSubtype = shot_subtype if shot_subtype is not None else None
    annotation.ballVisible = ball_visible
    annotation.hoopVisible = hoop_visible
    annotation.ballNearRim = ball_near_rim
    annotation.ballThroughHoopLikelihood = ball_through_hoop
    annotation.possessionChangeLikelihood = possession_change
    annotation.transitionLikelihood = transition_likelihood
    annotation.teacherConfidence = teacher_confidence
    annotation.humanVerified = bool(_first_bool(row, "humanVerified", "human_verified", default=False))
    annotation.reviewerNotes = _first_text(row, "reviewerNotes", "reviewer_notes", "notes") or ""
    annotation.rawRuntimeOutputs = _canonical_runtime_payload(
        row,
        source_kind="ebard-detection",
        source_dataset=source_dataset,
        source_domain=source_domain,
        source_label=_first_text(row, "label", "eventLabel", "event_label", "action", "category", "class"),
    )
    annotation.rawTeacherOutputs = {
        "sourceDataset": source_dataset,
        "sourceDomain": source_domain,
        "sourceDomainTag": source_domain,
        "sourceKind": "ebard-detection",
        "detections": detections,
        "evidence": evidence,
        "evidenceFields": sorted(evidence),
        "canonicalHierarchy": _canonical_hierarchy_payload(
            event_family=event_family,
            outcome=outcome,
            shot_subtype=shot_subtype,
        ),
        "importVersion": ANNOTATION_SCHEMA_VERSION,
        "notes": _first_text(row, "teacherNotes", "teacher_notes", "notes") or "E-BARD detection supervision imported into canonical hierarchy.",
        "confidence": teacher_confidence,
    }
    return annotation


def _import_tracking_row(
    row: Mapping[str, Any],
    *,
    source_kind: str,
    source_domain: str,
    source_dataset: str,
) -> ClipAnnotation:
    clip_id = _first_text(row, "clipId", "clip_id", "id", "videoId", "video_id")
    source_ref = _first_text(row, "sourceRef", "source_ref", "path", "videoPath", "video_path")
    tracks = _normalize_tracks(row)
    evidence = _normalize_evidence(row)
    source_label = _first_text(row, "label", "eventLabel", "event_label", "action", "category", "class", "sequenceLabel", "sequence_label", "playType", "play_type")

    ball_visible = _first_bool(row, "ballVisible", "ball_visible", default=_detection_present(tracks, {"ball", "basketball"}))
    hoop_visible = _first_bool(row, "hoopVisible", "hoop_visible", default=_detection_present(tracks, {"hoop", "rim", "backboard"}))
    ball_near_rim = _compute_ball_near_rim(row, tracks)
    ball_through_hoop = _first_probability(
        row,
        "ballThroughHoopLikelihood",
        "ball_through_hoop_likelihood",
        default=0.0 if ball_near_rim is None else min(1.0, ball_near_rim * 0.9),
    )
    possession_change = _first_probability(
        row,
        "possessionChangeLikelihood",
        "possession_change_likelihood",
        default=_tracking_possession_change(tracks, source_label),
    )
    transition_likelihood = _first_probability(
        row,
        "transitionLikelihood",
        "transition_likelihood",
        default=_tracking_transition_likelihood(tracks, source_label),
    )
    teacher_confidence = _first_probability(row, "teacherConfidence", "teacher_confidence", default=_first_probability(row, "confidence", default=0.7))
    event_family = _first_text(row, "eventFamily", "event_family") or _tracking_event_family(source_label, tracks, ball_visible=ball_visible, hoop_visible=hoop_visible, ball_near_rim=ball_near_rim)
    outcome = _first_text(row, "outcome", "result") or _tracking_outcome(source_label, tracks, ball_visible=ball_visible, hoop_visible=hoop_visible, ball_near_rim=ball_near_rim)
    shot_subtype = _first_text(row, "shotSubtype", "shot_subtype") or _tracking_shot_subtype(source_label, event_family=event_family, tracks=tracks)
    if event_family != "shot_attempt":
        shot_subtype = None
    annotation = annotation_template(clip_id=clip_id, source_domain=source_domain, source_kind=source_kind)
    annotation.sourceRef = source_ref
    annotation.eventFamily = event_family
    annotation.outcome = outcome
    annotation.shotSubtype = shot_subtype
    annotation.ballVisible = ball_visible
    annotation.hoopVisible = hoop_visible
    annotation.ballNearRim = ball_near_rim
    annotation.ballThroughHoopLikelihood = ball_through_hoop
    annotation.possessionChangeLikelihood = possession_change
    annotation.transitionLikelihood = transition_likelihood
    annotation.teacherConfidence = teacher_confidence
    annotation.humanVerified = bool(_first_bool(row, "humanVerified", "human_verified", default=False))
    annotation.reviewerNotes = _first_text(row, "reviewerNotes", "reviewer_notes", "notes") or ""
    annotation.rawRuntimeOutputs = _canonical_runtime_payload(
        row,
        source_kind=source_kind,
        source_dataset=source_dataset,
        source_domain=source_domain,
        source_label=source_label,
    )
    annotation.rawTeacherOutputs = {
        "sourceDataset": source_dataset,
        "sourceDomain": source_domain,
        "sourceDomainTag": source_domain,
        "sourceKind": source_kind,
        "tracks": tracks,
        "trackSummary": _tracking_summary(tracks),
        "evidence": evidence,
        "evidenceFields": sorted(evidence),
        "canonicalHierarchy": {
            "eventFamily": event_family,
            "outcome": outcome,
            "shotSubtype": shot_subtype,
        },
        "importVersion": ANNOTATION_SCHEMA_VERSION,
        "notes": _first_text(row, "teacherNotes", "teacher_notes", "notes") or "Tracking supervision imported into canonical hierarchy.",
        "confidence": teacher_confidence,
    }
    return annotation


def _canonical_runtime_payload(
    row: Mapping[str, Any],
    *,
    source_kind: str,
    source_dataset: str,
    source_domain: str,
    source_label: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "sourceDataset": source_dataset,
        "sourceKind": source_kind,
        "sourceLabel": source_label,
        "sourceDomainTag": source_domain,
        "importVersion": ANNOTATION_SCHEMA_VERSION,
    }
    for key in ("sourceEventTimeSeconds", "startSeconds", "endSeconds", "clipDurationSeconds", "sourceDurationSeconds"):
        if key in row and row[key] is not None:
            payload[key] = row[key]
    if "evidence" in row and row["evidence"] is not None:
        payload["evidence"] = row["evidence"]
    if "evidenceText" in row and row["evidenceText"]:
        payload["evidenceText"] = row["evidenceText"]
    return payload


def _normalize_source_kind(source_kind: str) -> str:
    normalized = source_kind.strip().lower().replace("_", "-")
    aliases = {
        "bard": "bard-event",
        "bard-event": "bard-event",
        "bard-events": "bard-event",
        "bard-action": "bard-event",
        "ebard": "ebard-detection",
        "e-bard": "ebard-detection",
        "e-bard-detection": "ebard-detection",
        "ebard-detection": "ebard-detection",
        "ebard-detections": "ebard-detection",
        "detection": "ebard-detection",
        "sportsmot": "sportsmot-tracking",
        "sportsmot-tracking": "sportsmot-tracking",
        "sportsmot-tracks": "sportsmot-tracking",
        "trackid3x3": "trackid3x3-tracking",
        "trackid3x3-fixed": "trackid3x3-tracking",
        "trackid3x3-fixed-camera": "trackid3x3-tracking",
        "trackid3x3-fixed-camera-tracking": "trackid3x3-tracking",
        "trackid3x3-amateur": "trackid3x3-tracking",
        "trackid3x3-amateur-like": "trackid3x3-tracking",
        "trackid3x3-amateur-tracking": "trackid3x3-tracking",
        "trackid3x3-tracking": "trackid3x3-tracking",
        "trackid3x3-tracks": "trackid3x3-tracking",
    }
    if normalized not in aliases:
        raise ValueError(f"Unsupported source kind: {source_kind}")
    return aliases[normalized]


def _canonical_hierarchy_payload(
    *,
    event_family: str,
    outcome: str,
    shot_subtype: str | None,
) -> dict[str, Any]:
    return {
        "eventFamily": event_family,
        "outcome": outcome,
        "shotSubtype": shot_subtype,
    }


def _first_text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key in row and row[key] is not None:
            value = str(row[key]).strip()
            if value:
                return value
    return None


def _first_bool(row: Mapping[str, Any], *keys: str, default: bool | None = None) -> bool:
    for key in keys:
        if key in row and row[key] is not None:
            value = row[key]
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "1", "yes", "y"}:
                    return True
                if lowered in {"false", "0", "no", "n"}:
                    return False
            return bool(value)
    if default is None:
        return False
    return bool(default)


def _first_probability(row: Mapping[str, Any], *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        if key in row and row[key] is not None:
            try:
                value = float(row[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be numeric.") from exc
            return max(0.0, min(1.0, value))
    if default is None:
        return None
    return max(0.0, min(1.0, float(default)))


def _normalize_evidence(row: Mapping[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for key in ("evidence", "evidenceText", "evidence_text", "notes", "reviewerNotes", "reviewer_notes"):
        if key in row and row[key] not in (None, "", []):
            evidence[key] = row[key]
    for key in ("sourceLabel", "label", "eventLabel", "event_label", "action", "category", "class"):
        if key in row and row[key] not in (None, ""):
            evidence.setdefault("sourceLabel", row[key])
            break
    for key in ("startSeconds", "endSeconds", "clipDurationSeconds", "sourceDurationSeconds", "sourceEventTimeSeconds"):
        if key in row and row[key] is not None:
            evidence[key] = row[key]
    return evidence


def _normalize_tracks(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_tracks = row.get("tracks")
    if raw_tracks is None:
        raw_tracks = row.get("tracklets")
    if raw_tracks is None:
        raw_tracks = row.get("detections")
    if raw_tracks is None:
        return []
    if not isinstance(raw_tracks, list):
        raise ValueError("tracks/tracklets/detections must be a list when present.")
    normalized: list[dict[str, Any]] = []
    for track in raw_tracks:
        if not isinstance(track, Mapping):
            raise ValueError("Each track entry must be a JSON object.")
        label = _first_text(track, "label", "category", "class", "name")
        bbox = track.get("bbox") or track.get("box") or track.get("bounds")
        normalized_track: dict[str, Any] = {
            "label": label,
            "score": _first_probability(track, "score", "confidence", default=0.0),
        }
        if bbox is not None:
            normalized_track["bbox"] = _normalize_bbox(bbox)
        track_id = track.get("trackId", track.get("track_id", track.get("id")))
        if track_id is not None:
            normalized_track["trackId"] = str(track_id)
        frame_idx = track.get("frameIndex", track.get("frame_index"))
        timestamp = track.get("timestamp", track.get("timeSeconds", track.get("time_seconds")))
        if frame_idx is not None:
            normalized_track["frameIndex"] = int(frame_idx)
        if timestamp is not None:
            normalized_track["timestamp"] = float(timestamp)
        normalized.append(normalized_track)
    return normalized


def _normalize_detections(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_detections = row.get("detections")
    if raw_detections is None:
        raw_detections = row.get("objects")
    if raw_detections is None:
        raw_detections = row.get("annotations")
    if raw_detections is None:
        return []
    if not isinstance(raw_detections, list):
        raise ValueError("detections/objects/annotations must be a list when present.")
    normalized: list[dict[str, Any]] = []
    for detection in raw_detections:
        if not isinstance(detection, Mapping):
            raise ValueError("Each detection must be a JSON object.")
        label = _first_text(detection, "label", "category", "class", "name")
        box = detection.get("bbox") or detection.get("box") or detection.get("bounds")
        normalized_detection: dict[str, Any] = {
            "label": label,
            "score": _first_probability(detection, "score", "confidence", default=0.0),
        }
        if box is not None:
            normalized_detection["bbox"] = _normalize_bbox(box)
        frame_idx = detection.get("frameIndex", detection.get("frame_index"))
        timestamp = detection.get("timestamp", detection.get("timeSeconds", detection.get("time_seconds")))
        if frame_idx is not None:
            normalized_detection["frameIndex"] = int(frame_idx)
        if timestamp is not None:
            normalized_detection["timestamp"] = float(timestamp)
        normalized.append(normalized_detection)
    return normalized


def _normalize_bbox(box: Any) -> list[float]:
    if isinstance(box, Mapping):
        candidates = [box.get(key) for key in ("x1", "y1", "x2", "y2")]
        if all(value is not None for value in candidates):
            return [float(value) for value in candidates]
        candidates = [box.get(key) for key in ("x", "y", "w", "h")]
        if all(value is not None for value in candidates):
            return [float(value) for value in candidates]
    if isinstance(box, Sequence) and not isinstance(box, (str, bytes)):
        if len(box) == 4:
            return [float(value) for value in box]
    raise ValueError("bbox must be a four-value sequence or object.")


def _detection_present(detections: Sequence[Mapping[str, Any]], labels: set[str]) -> bool:
    for detection in detections:
        label = str(detection.get("label") or "").strip().lower()
        if any(token in label for token in labels):
            return True
    return False


def _compute_ball_near_rim(row: Mapping[str, Any], detections: Sequence[Mapping[str, Any]]) -> float | None:
    explicit = _first_probability(row, "ballNearRim", "ball_near_rim")
    if explicit is not None:
        return explicit
    ball_boxes = [detection for detection in detections if _label_matches(detection.get("label"), {"ball", "basketball"}) and "bbox" in detection]
    hoop_boxes = [detection for detection in detections if _label_matches(detection.get("label"), {"hoop", "rim", "backboard"}) and "bbox" in detection]
    if not ball_boxes or not hoop_boxes:
        return None
    ball_box = ball_boxes[0]["bbox"]
    hoop_box = hoop_boxes[0]["bbox"]
    ball_center = _bbox_center(ball_box)
    hoop_center = _bbox_center(hoop_box)
    distance = ((ball_center[0] - hoop_center[0]) ** 2 + (ball_center[1] - hoop_center[1]) ** 2) ** 0.5
    return max(0.0, min(1.0, 1.0 - min(distance, 1.0)))


def _tracking_summary(tracks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    labels = sorted({str(track.get("label") or "").strip().lower() for track in tracks if track.get("label")})
    frame_indices = [int(track["frameIndex"]) for track in tracks if "frameIndex" in track]
    timestamps = [float(track["timestamp"]) for track in tracks if "timestamp" in track]
    return {
        "trackCount": len(tracks),
        "labels": labels,
        "playerTrackCount": sum(1 for track in tracks if _label_matches(track.get("label"), {"player"})),
        "ballTrackCount": sum(1 for track in tracks if _label_matches(track.get("label"), {"ball", "basketball"})),
        "hoopTrackCount": sum(1 for track in tracks if _label_matches(track.get("label"), {"hoop", "rim", "backboard"})),
        "firstFrameIndex": min(frame_indices) if frame_indices else None,
        "lastFrameIndex": max(frame_indices) if frame_indices else None,
        "firstTimestamp": min(timestamps) if timestamps else None,
        "lastTimestamp": max(timestamps) if timestamps else None,
    }


def _bbox_center(box: Sequence[float]) -> tuple[float, float]:
    if len(box) != 4:
        raise ValueError("bbox must contain four values.")
    x1, y1, x2, y2 = [float(value) for value in box]
    if x2 <= x1 or y2 <= y1:
        return (x1, y1)
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _label_matches(label: Any, needles: set[str]) -> bool:
    normalized = str(label or "").strip().lower()
    return any(token in normalized for token in needles)


def _tracking_event_family(
    label: str | None,
    tracks: Sequence[Mapping[str, Any]],
    *,
    ball_visible: bool,
    hoop_visible: bool,
    ball_near_rim: float | None,
) -> str:
    normalized = _normalize_label(label)
    if any(token in normalized for token in {"replay", "celebration", "camera pan", "dead ball", "dead-ball", "inbound", "timeout", "setup", "warmup", "dribble only", "half court setup", "huddle"}):
        return "other"
    if any(token in normalized for token in {"transition", "fast break", "runout", "breakaway"}):
        return "transition"
    if any(token in normalized for token in {"steal", "turnover", "live-ball turnover"}):
        return "turnover"
    if any(token in normalized for token in {"block", "deflection", "contest"}):
        return "defensive_event"
    if any(token in normalized for token in {"dunk", "layup", "jumper", "three", "3pt", "3 point", "putback", "shot", "make", "miss", "finish", "attempt"}):
        return "shot_attempt"
    if _detection_present(tracks, {"shot", "attempt", "score", "finish"}) and ball_visible and hoop_visible:
        return "shot_attempt"
    if ball_visible and hoop_visible and (ball_near_rim is None or ball_near_rim >= 0.35):
        return "shot_attempt"
    return "other"


def _tracking_outcome(
    label: str | None,
    tracks: Sequence[Mapping[str, Any]],
    *,
    ball_visible: bool,
    hoop_visible: bool,
    ball_near_rim: float | None,
) -> str:
    normalized = _normalize_label(label)
    if any(token in normalized for token in {"blocked", "rejected"}):
        return "blocked"
    if any(token in normalized for token in {"miss", "airball", "rim out", "no good", "brick"}):
        return "missed"
    if any(token in normalized for token in {"made", "score", "bucket", "swish", "and one"}):
        return "made"
    if any(token in normalized for token in {"uncertain", "unknown", "setup", "replay", "celebration", "camera pan", "dead ball", "dead-ball", "inbound"}):
        return "uncertain"
    if ball_visible and hoop_visible and ball_near_rim is not None:
        if ball_near_rim >= 0.78:
            return "uncertain"
        if ball_near_rim <= 0.12:
            return "uncertain"
    return "uncertain"


def _tracking_shot_subtype(
    label: str | None,
    *,
    event_family: str,
    tracks: Sequence[Mapping[str, Any]],
) -> str | None:
    if event_family != "shot_attempt":
        return None
    normalized = _normalize_label(label)
    if any(token in normalized for token in {"dunk", "alley oop", "alley-oop", "rim attack", "finish at rim"}):
        return "dunk"
    if any(token in normalized for token in {"layup", "runner", "floater", "up and under", "hook"}):
        return "layup"
    if any(token in normalized for token in {"three", "3pt", "3 point", "deep"}):
        return "three"
    if any(token in normalized for token in {"putback", "tip in", "tip-in", "tip"}):
        return "putback"
    if any(token in normalized for token in {"jumper", "midrange", "pull up", "pull-up"}):
        return "jumper"
    if _detection_present(tracks, {"3pt", "three", "jumper", "dunk", "layup", "putback"}):
        if _detection_present(tracks, {"3pt", "three"}):
            return "three"
        if _detection_present(tracks, {"dunk"}):
            return "dunk"
        if _detection_present(tracks, {"putback"}):
            return "putback"
        if _detection_present(tracks, {"layup", "runner", "floater"}):
            return "layup"
        if _detection_present(tracks, {"jumper"}):
            return "jumper"
    return None


def _tracking_possession_change(tracks: Sequence[Mapping[str, Any]], label: str | None) -> float:
    normalized = _normalize_label(label)
    if any(token in normalized for token in {"steal", "turnover", "deflection"}):
        return 0.9
    if _detection_present(tracks, {"steal", "turnover", "deflection"}):
        return 0.78
    ball_tracks = [track for track in tracks if _label_matches(track.get("label"), {"ball", "basketball"})]
    player_tracks = [track for track in tracks if _label_matches(track.get("label"), {"player"})]
    if len(ball_tracks) >= 2 and player_tracks:
        return 0.45
    return 0.18


def _tracking_transition_likelihood(tracks: Sequence[Mapping[str, Any]], label: str | None) -> float:
    normalized = _normalize_label(label)
    if any(token in normalized for token in {"transition", "fast break", "runout", "breakaway"}):
        return 0.92
    if _detection_present(tracks, {"transition", "fast break", "breakaway"}):
        return 0.84
    player_tracks = sum(1 for track in tracks if _label_matches(track.get("label"), {"player"}))
    if player_tracks >= 5:
        return 0.64
    return 0.22


def _bard_event_family(label: str | None) -> str:
    normalized = _normalize_label(label)
    if not normalized:
        return "other"
    if any(token in normalized for token in {"dunk", "layup", "jumper", "three", "putback", "shot", "make", "miss", "floater", "runner", "hook"}):
        return "shot_attempt"
    if any(token in normalized for token in {"block", "steal", "defense"}):
        return "defensive_event" if "block" in normalized else "turnover"
    if any(token in normalized for token in {"fast break", "transition", "runout", "breakaway"}):
        return "transition"
    if any(token in normalized for token in {"replay", "celebration", "camera pan", "dead ball", "dead-ball", "inbound", "setup", "dribble", "crowd", "timeout", "half court setup", "half-court setup", "warmup"}):
        return "other"
    return "other"


def _bard_outcome(label: str | None) -> str:
    normalized = _normalize_label(label)
    if not normalized:
        return "uncertain"
    if any(token in normalized for token in {"blocked"}):
        return "blocked"
    if any(token in normalized for token in {"miss", "rim out", "airball", "no good", "brick", "rejected"}):
        return "missed"
    if any(token in normalized for token in {"made", "score", "and one", "swish", "dunk", "layup", "jumper", "three", "putback", "floater", "runner"}):
        return "made"
    return "uncertain"


def _bard_shot_subtype(label: str | None, *, event_family: str) -> str | None:
    normalized = _normalize_label(label)
    if event_family != "shot_attempt":
        return None
    if "dunk" in normalized or "alley oop" in normalized or "alley-oop" in normalized:
        return "dunk"
    if "layup" in normalized or "floater" in normalized or "runner" in normalized or "hook" in normalized:
        return "layup"
    if "three" in normalized or "3pt" in normalized or "3 point" in normalized:
        return "three"
    if "putback" in normalized or "tip" in normalized:
        return "putback"
    if "jumper" in normalized or "midrange" in normalized or "pull up" in normalized or "pull-up" in normalized:
        return "jumper"
    if any(token in normalized for token in {"shot", "make", "miss"}):
        return "unknown"
    return None


def _ebard_event_family(
    detections: Sequence[Mapping[str, Any]],
    *,
    ball_visible: bool,
    hoop_visible: bool,
    ball_near_rim: float | None,
) -> str:
    if _detection_present(detections, {"block"}):
        return "defensive_event"
    if _detection_present(detections, {"steal", "turnover"}):
        return "turnover"
    if _detection_present(detections, {"transition", "fast break"}):
        return "transition"
    if _detection_present(detections, {"replay", "celebration", "camera pan", "dead ball", "dead-ball", "inbound", "timeout", "setup"}):
        return "other"
    if ball_visible and hoop_visible and (ball_near_rim is None or ball_near_rim >= 0.35):
        return "shot_attempt"
    return "other"


def _ebard_outcome(*, ball_visible: bool, hoop_visible: bool, ball_near_rim: float | None) -> str:
    if not ball_visible:
        return "uncertain"
    if hoop_visible and ball_near_rim is not None and ball_near_rim >= 0.75:
        return "uncertain"
    return "uncertain"


def _normalize_label(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())
