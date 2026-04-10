from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from pathlib import Path
from typing import Any

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cv2 = None  # type: ignore

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    np = None  # type: ignore

from .interfaces import Detector, Perceptor, Tracker
from .models import CandidateWindow


@dataclass(frozen=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(self.x2 - self.x1, 0.0)

    @property
    def height(self) -> float:
        return max(self.y2 - self.y1, 0.0)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: BoundingBox
    frameIndex: int
    timestampSeconds: float
    source: str
    trackId: str | None = None


@dataclass(frozen=True)
class TrackObservation:
    frameIndex: int
    timestampSeconds: float
    confidence: float
    box: BoundingBox


@dataclass
class Track:
    trackId: str
    label: str
    observations: list[TrackObservation] = field(default_factory=list)

    @property
    def average_confidence(self) -> float:
        if not self.observations:
            return 0.0
        return sum(item.confidence for item in self.observations) / len(self.observations)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "trackId": self.trackId,
            "label": self.label,
            "averageConfidence": round(self.average_confidence, 4),
            "observationCount": len(self.observations),
            "observations": [
                {
                    "frameIndex": observation.frameIndex,
                    "timestampSeconds": round(observation.timestampSeconds, 3),
                    "confidence": round(observation.confidence, 4),
                    "box": asdict(observation.box),
                }
                for observation in self.observations
            ],
        }


@dataclass(frozen=True)
class FramePerception:
    frameIndex: int
    timestampSeconds: float
    detections: list[Detection]

    def to_metadata(self) -> dict[str, Any]:
        return {
            "frameIndex": self.frameIndex,
            "timestampSeconds": round(self.timestampSeconds, 3),
            "detections": [
                {
                    "label": detection.label,
                    "confidence": round(detection.confidence, 4),
                    "source": detection.source,
                    "trackId": detection.trackId,
                    "box": asdict(detection.box),
                }
                for detection in self.detections
            ],
        }


@dataclass
class CandidatePerception:
    candidateId: str
    frameWidth: int
    frameHeight: int
    sampledFrameCount: int
    frames: list[FramePerception]
    tracks: list[Track]
    overlayPaths: list[str] = field(default_factory=list)

    def detection_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for frame in self.frames:
            for detection in frame.detections:
                counts[detection.label] = counts.get(detection.label, 0) + 1
        return counts

    def track_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for track in self.tracks:
            counts[track.label] = counts.get(track.label, 0) + 1
        return counts

    def primary_track(self, label: str) -> Track | None:
        candidates = [track for track in self.tracks if track.label == label]
        if not candidates:
            return None
        return max(candidates, key=lambda item: (len(item.observations), item.average_confidence))

    def to_metadata(self) -> dict[str, Any]:
        return {
            "frameWidth": self.frameWidth,
            "frameHeight": self.frameHeight,
            "sampledFrameCount": self.sampledFrameCount,
            "detectionCounts": self.detection_counts(),
            "trackCounts": self.track_counts(),
            "primaryBallTrackId": self.primary_track("basketball").trackId if self.primary_track("basketball") else None,
            "primaryRimTrackId": self.primary_track("rim").trackId if self.primary_track("rim") else None,
            "frames": [frame.to_metadata() for frame in self.frames],
            "tracks": [track.to_metadata() for track in self.tracks],
            "overlayPaths": list(self.overlayPaths),
        }


@dataclass(frozen=True)
class PerceptionFrame:
    frame: np.ndarray
    timestampSeconds: float
    frameIndex: int
    previousGray: np.ndarray | None = None


@dataclass
class BasketballColorDetector(Detector):
    def detect(self, source_path: Path, candidate: CandidateWindow) -> dict[str, Any]:
        raise NotImplementedError("Frame-level detector should be called through detect_frame().")

    def detect_frame(self, frame: np.ndarray, *, timestamp_seconds: float, frame_index: int) -> list[Detection]:
        return _detect_basketball(frame, timestamp_seconds, frame_index)


@dataclass
class RimColorDetector(Detector):
    def detect(self, source_path: Path, candidate: CandidateWindow) -> dict[str, Any]:
        raise NotImplementedError("Frame-level detector should be called through detect_frame().")

    def detect_frame(self, frame: np.ndarray, *, timestamp_seconds: float, frame_index: int) -> list[Detection]:
        return _detect_rim(frame, timestamp_seconds, frame_index)


@dataclass
class PlayerMotionDetector(Detector):
    def detect(self, source_path: Path, candidate: CandidateWindow) -> dict[str, Any]:
        raise NotImplementedError("Frame-level detector should be called through detect_frame().")

    def detect_frame(
        self,
        frame: np.ndarray,
        *,
        timestamp_seconds: float,
        frame_index: int,
        previous_gray: np.ndarray | None,
    ) -> tuple[list[Detection], np.ndarray]:
        return _detect_players(
            frame,
            timestamp_seconds=timestamp_seconds,
            frame_index=frame_index,
            previous_gray=previous_gray,
        )


@dataclass
class CentroidTracker(Tracker):
    track_radius_by_label: dict[str, float]
    tracks: dict[str, list[Track]] = field(default_factory=dict)
    _next_track_index: int = 1

    def track(self, detections: dict[str, Any]) -> dict[str, Any]:
        frame_detections = detections.get("detections") or []
        assigned = self.assign(list(frame_detections))
        return {
            **detections,
            "detections": assigned,
            "tracks": [track.to_metadata() for track in self.finalize()],
        }

    def assign(self, detections: list[Detection]) -> list[Detection]:
        assigned: list[Detection] = []
        for detection in detections:
            track = self._resolve_track(detection)
            observation = TrackObservation(
                frameIndex=detection.frameIndex,
                timestampSeconds=detection.timestampSeconds,
                confidence=detection.confidence,
                box=detection.box,
            )
            track.observations.append(observation)
            assigned.append(
                Detection(
                    label=detection.label,
                    confidence=detection.confidence,
                    box=detection.box,
                    frameIndex=detection.frameIndex,
                    timestampSeconds=detection.timestampSeconds,
                    source=detection.source,
                    trackId=track.trackId,
                )
            )
        return assigned

    def finalize(self) -> list[Track]:
        ordered: list[Track] = []
        for label_tracks in self.tracks.values():
            ordered.extend(label_tracks)
        ordered.sort(key=lambda item: item.trackId)
        return ordered

    def _resolve_track(self, detection: Detection) -> Track:
        existing_tracks = self.tracks.setdefault(detection.label, [])
        best_track = None
        best_distance = None
        radius = self.track_radius_by_label.get(detection.label, 120.0)
        for track in existing_tracks:
            if not track.observations:
                continue
            last_box = track.observations[-1].box
            distance = _euclidean_distance(last_box.center, detection.box.center)
            if distance > radius:
                continue
            if best_distance is None or distance < best_distance:
                best_track = track
                best_distance = distance
        if best_track is not None:
            return best_track
        new_track = Track(trackId=f"{detection.label}-{self._next_track_index}", label=detection.label)
        self._next_track_index += 1
        existing_tracks.append(new_track)
        return new_track


@dataclass
class HeuristicBasketballPerceptor(Perceptor):
    sample_frames: int = 12
    overlay_frame_limit: int = 3
    ball_track_radius_px: float = 84.0
    player_track_radius_px: float = 164.0
    rim_track_radius_px: float = 92.0
    basketball_detector: BasketballColorDetector = field(default_factory=BasketballColorDetector)
    rim_detector: RimColorDetector = field(default_factory=RimColorDetector)
    player_detector: PlayerMotionDetector = field(default_factory=PlayerMotionDetector)

    def analyze(self, source_path: Path, candidate: CandidateWindow) -> dict[str, Any]:
        if cv2 is None or np is None:
            return {
                "frameWidth": 0,
                "frameHeight": 0,
                "sampledFrameCount": 0,
                "detectionCounts": {},
                "trackCounts": {},
                "frames": [],
                "tracks": [],
                "overlayPaths": [],
                "failureReason": "opencv_unavailable",
            }
        sampled_frames = _sample_candidate_frames(source_path, candidate.startTime, candidate.endTime, self.sample_frames)
        if not sampled_frames:
            return CandidatePerception(
                candidateId=candidate.candidateId,
                frameWidth=0,
                frameHeight=0,
                sampledFrameCount=0,
                frames=[],
                tracks=[],
                overlayPaths=[],
            ).to_metadata()

        frame_perceptions: list[FramePerception] = []
        previous_gray = None
        tracker = CentroidTracker(
            track_radius_by_label={
                "basketball": self.ball_track_radius_px,
                "player": self.player_track_radius_px,
                "rim": self.rim_track_radius_px,
            }
        )
        overlay_paths: list[str] = []
        first_frame = sampled_frames[0]
        frame_height, frame_width = first_frame["frame"].shape[:2]

        for frame_index, sample in enumerate(sampled_frames):
            frame = sample["frame"]
            timestamp_seconds = sample["timestampSeconds"]
            ball_detections = self.basketball_detector.detect_frame(
                frame,
                timestamp_seconds=timestamp_seconds,
                frame_index=frame_index,
            )
            rim_detections = self.rim_detector.detect_frame(
                frame,
                timestamp_seconds=timestamp_seconds,
                frame_index=frame_index,
            )
            player_detections, previous_gray = self.player_detector.detect_frame(
                frame,
                timestamp_seconds=timestamp_seconds,
                frame_index=frame_index,
                previous_gray=previous_gray,
            )
            tracked = tracker.track({"detections": ball_detections + rim_detections + player_detections})
            detections = tracked["detections"]
            frame_perceptions.append(
                FramePerception(
                    frameIndex=frame_index,
                    timestampSeconds=timestamp_seconds,
                    detections=detections,
                )
            )
            if frame_index < self.overlay_frame_limit:
                overlay_path = _write_overlay(
                    frame=frame,
                    detections=detections,
                    candidate_id=candidate.candidateId,
                    frame_index=frame_index,
                )
                if overlay_path is not None:
                    overlay_paths.append(str(overlay_path))

        perception = CandidatePerception(
            candidateId=candidate.candidateId,
            frameWidth=frame_width,
            frameHeight=frame_height,
            sampledFrameCount=len(sampled_frames),
            frames=frame_perceptions,
            tracks=tracker.finalize(),
            overlayPaths=overlay_paths,
        )
        return perception.to_metadata()


def _sample_candidate_frames(source_path: Path, start_seconds: float, end_seconds: float, sample_frames: int) -> list[dict[str, Any]]:
    if cv2 is None or np is None:
        return []
    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        return []

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    start_frame = max(int(start_seconds * fps), 0) if fps > 0 else 0
    end_frame = min(int(end_seconds * fps), total_frames - 1) if fps > 0 and total_frames > 0 else total_frames - 1
    if end_frame < start_frame:
        end_frame = start_frame

    frame_indices = _linspace_indices(start_frame, max(end_frame, start_frame), sample_frames)
    sampled: list[dict[str, Any]] = []
    try:
        for frame_index in frame_indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                continue
            sampled.append(
                {
                    "frameIndex": frame_index,
                    "timestampSeconds": float(frame_index / fps) if fps > 0 else 0.0,
                    "frame": frame,
                }
            )
    finally:
        capture.release()
    return sampled


def _linspace_indices(start_frame: int, end_frame: int, sample_frames: int) -> list[int]:
    if np is None:
        return [start_frame]
    if sample_frames <= 1 or end_frame <= start_frame:
        return [start_frame]
    return [int(round(value)) for value in np.linspace(start_frame, end_frame, num=sample_frames)]


def _detect_basketball(frame: np.ndarray, timestamp_seconds: float, frame_index: int) -> list[Detection]:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array([5, 90, 90])
    upper = np.array([25, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    frame_area = frame.shape[0] * frame.shape[1]
    detections: list[Detection] = []
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < frame_area * 0.00002 or area > frame_area * 0.012:
            continue
        perimeter = max(cv2.arcLength(contour, True), 1.0)
        circularity = float((4.0 * math.pi * area) / (perimeter * perimeter))
        if circularity < 0.35:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        aspect = width / max(height, 1)
        if aspect < 0.55 or aspect > 1.6:
            continue
        confidence = min(max((circularity * 0.7) + (min(width, height) / max(frame.shape[:2]) * 0.6), 0.0), 1.0)
        detections.append(
            Detection(
                label="basketball",
                confidence=confidence,
                box=_normalize_box(x, y, width, height, frame.shape[1], frame.shape[0]),
                frameIndex=frame_index,
                timestampSeconds=timestamp_seconds,
                source="heuristic_color_circle",
            )
        )
    detections.sort(key=lambda item: item.confidence, reverse=True)
    return detections[:3]


def _detect_rim(frame: np.ndarray, timestamp_seconds: float, frame_index: int) -> list[Detection]:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    red_masks = [
        cv2.inRange(hsv, np.array([0, 80, 60]), np.array([12, 255, 255])),
        cv2.inRange(hsv, np.array([165, 80, 60]), np.array([179, 255, 255])),
    ]
    orange_mask = cv2.inRange(hsv, np.array([8, 90, 90]), np.array([24, 255, 255]))
    mask = red_masks[0] | red_masks[1] | orange_mask
    upper_cutoff = int(frame.shape[0] * 0.72)
    mask[upper_cutoff:, :] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    detections: list[Detection] = []
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = frame.shape[0] * frame.shape[1]
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < frame_area * 0.00003 or area > frame_area * 0.01:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        if width < max(height * 1.25, 8):
            continue
        if y > frame.shape[0] * 0.72:
            continue
        horizontalness = min(width / max(height, 1), 6.0) / 6.0
        confidence = min(max((horizontalness * 0.8) + (1.0 - (y / max(frame.shape[0], 1))) * 0.2, 0.0), 1.0)
        detections.append(
            Detection(
                label="rim",
                confidence=confidence,
                box=_normalize_box(x, y, width, height, frame.shape[1], frame.shape[0]),
                frameIndex=frame_index,
                timestampSeconds=timestamp_seconds,
                source="heuristic_color_rim",
            )
        )
    detections.sort(key=lambda item: item.confidence, reverse=True)
    return detections[:2]


def _detect_players(
    frame: np.ndarray,
    *,
    timestamp_seconds: float,
    frame_index: int,
    previous_gray: np.ndarray | None,
) -> tuple[list[Detection], np.ndarray]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if previous_gray is None:
        return [], gray

    delta = cv2.absdiff(gray, previous_gray)
    blurred = cv2.GaussianBlur(delta, (5, 5), 0)
    _, thresholded = cv2.threshold(blurred, 22, 255, cv2.THRESH_BINARY)
    thresholded = cv2.dilate(thresholded, np.ones((5, 5), np.uint8), iterations=2)
    contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = frame.shape[0] * frame.shape[1]
    detections: list[Detection] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < frame_area * 0.0007 or area > frame_area * 0.08:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        if height <= width:
            continue
        aspect = height / max(width, 1)
        if aspect < 1.1 or aspect > 5.5:
            continue
        motion_strength = min(max(float(area / max(frame_area * 0.015, 1.0)), 0.0), 1.0)
        confidence = min(max((motion_strength * 0.7) + (min(aspect / 4.0, 1.0) * 0.3), 0.0), 1.0)
        detections.append(
            Detection(
                label="player",
                confidence=confidence,
                box=_normalize_box(x, y, width, height, frame.shape[1], frame.shape[0]),
                frameIndex=frame_index,
                timestampSeconds=timestamp_seconds,
                source="heuristic_motion_blob",
            )
        )
    detections.sort(key=lambda item: item.confidence, reverse=True)
    return detections[:10], gray


def _normalize_box(x: int, y: int, width: int, height: int, frame_width: int, frame_height: int) -> BoundingBox:
    x1 = min(max(x / max(frame_width, 1), 0.0), 1.0)
    y1 = min(max(y / max(frame_height, 1), 0.0), 1.0)
    x2 = min(max((x + width) / max(frame_width, 1), 0.0), 1.0)
    y2 = min(max((y + height) / max(frame_height, 1), 0.0), 1.0)
    return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)


def _write_overlay(*, frame: np.ndarray, detections: list[Detection], candidate_id: str, frame_index: int) -> Path | None:
    if not detections:
        return None
    overlay = frame.copy()
    height, width = overlay.shape[:2]
    colors = {
        "basketball": (0, 140, 255),
        "rim": (0, 0, 255),
        "player": (0, 255, 0),
    }
    for detection in detections:
        color = colors.get(detection.label, (255, 255, 255))
        box = detection.box
        x1 = int(box.x1 * width)
        y1 = int(box.y1 * height)
        x2 = int(box.x2 * width)
        y2 = int(box.y2 * height)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
        label = f"{detection.label}:{detection.confidence:.2f}"
        if detection.trackId:
            label = f"{label}:{detection.trackId}"
        cv2.putText(overlay, label, (x1, max(y1 - 6, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
    overlay_path = Path("/tmp") / f"hoops-perception-{candidate_id}-{frame_index}.jpg"
    cv2.imwrite(str(overlay_path), overlay)
    return overlay_path


def _euclidean_distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    dx = first[0] - second[0]
    dy = first[1] - second[1]
    return math.sqrt((dx * dx) + (dy * dy))
