from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

from .labels import canonical_to_display_label
from .models import ActionPrediction, LabelScore


SHOT_LABELS = {"dunk", "layup", "jumper", "three", "putback", "miss"}


@dataclass(frozen=True)
class StructuredBasketballSignals:
    ballNearRim: float
    ballAboveRim: float
    ballArcApex: float
    ballThroughHoopLikelihood: float
    possessionChangeLikelihood: float
    playerToRimDistance: float | None
    ballCarrierSpeed: float
    transitionSpeedScore: float
    defenderProximityAtShot: float
    shotReleaseCandidate: float
    samePlayContinuityScore: float

    def as_metadata(self) -> dict[str, Any]:
        return {key: (round(value, 4) if isinstance(value, float) else value) for key, value in asdict(self).items()}


@dataclass(frozen=True)
class StructuredDecision:
    canonicalLabel: str
    displayLabel: str
    eventFamily: str
    eventSubtype: str | None
    shotSubtype: str | None
    outcome: str
    eventType: str
    shotType: str
    makeMiss: str
    confidenceBeforeMapping: float
    confidenceAfterMapping: float
    eventFamilyConfidenceBeforeMapping: float
    eventFamilyConfidenceAfterMapping: float
    shotSubtypeConfidenceBeforeMapping: float | None
    shotSubtypeConfidenceAfterMapping: float | None
    outcomeConfidenceBeforeMapping: float
    outcomeConfidenceAfterMapping: float
    isUncertain: bool
    familyScores: dict[str, float]
    outcomeScores: dict[str, float]
    subtypeScores: dict[str, float]

    def as_metadata(self) -> dict[str, Any]:
        return {
            "canonicalLabel": self.canonicalLabel,
            "displayLabel": self.displayLabel,
            "eventFamily": self.eventFamily,
            "eventSubtype": self.eventSubtype,
            "shotSubtype": self.shotSubtype,
            "outcome": self.outcome,
            "eventType": self.eventType,
            "shotType": self.shotType,
            "makeMiss": self.makeMiss,
            "confidenceBeforeMapping": round(self.confidenceBeforeMapping, 4),
            "confidenceAfterMapping": round(self.confidenceAfterMapping, 4),
            "eventFamilyConfidenceBeforeMapping": round(self.eventFamilyConfidenceBeforeMapping, 4),
            "eventFamilyConfidenceAfterMapping": round(self.eventFamilyConfidenceAfterMapping, 4),
            "shotSubtypeConfidenceBeforeMapping": round(self.shotSubtypeConfidenceBeforeMapping, 4)
            if self.shotSubtypeConfidenceBeforeMapping is not None
            else None,
            "shotSubtypeConfidenceAfterMapping": round(self.shotSubtypeConfidenceAfterMapping, 4)
            if self.shotSubtypeConfidenceAfterMapping is not None
            else None,
            "outcomeConfidenceBeforeMapping": round(self.outcomeConfidenceBeforeMapping, 4),
            "outcomeConfidenceAfterMapping": round(self.outcomeConfidenceAfterMapping, 4),
            "isUncertain": self.isUncertain,
            "familyScores": _round_mapping(self.familyScores),
            "outcomeScores": _round_mapping(self.outcomeScores),
            "subtypeScores": _round_mapping(self.subtypeScores),
        }


def derive_structured_signals(
    *,
    candidate_metadata: dict[str, Any],
    action: ActionPrediction,
) -> StructuredBasketballSignals:
    perception = candidate_metadata.get("perception") or {}
    frame_width = max(int(perception.get("frameWidth") or 0), 1)
    frame_height = max(int(perception.get("frameHeight") or 0), 1)
    frame_diagonal = math.sqrt((frame_width * frame_width) + (frame_height * frame_height))
    tracks = perception.get("tracks") or []

    ball_track = _primary_track(tracks, "basketball")
    rim_track = _primary_track(tracks, "rim")
    player_tracks = [track for track in tracks if track.get("label") == "player"]
    ball_points = _track_points(ball_track, frame_width, frame_height)
    rim_points = _track_points(rim_track, frame_width, frame_height)

    rim_anchor = rim_points[0] if rim_points else None
    near_rim_distances: list[float] = []
    above_rim_frames = 0
    through_hoop_hits = 0
    shot_release_score = 0.0

    if ball_points and rim_anchor:
        rim_center = rim_anchor["center"]
        rim_width = max(rim_anchor["box"]["width"], 1.0)
        rim_height = max(rim_anchor["box"]["height"], 1.0)
        for point in ball_points:
            distance = _euclidean_distance(point["center"], rim_center)
            near_rim_distances.append(distance / max(frame_diagonal, 1.0))
            if point["center"][0] >= rim_anchor["box"]["x1"] - (rim_width * 0.75) and point["center"][0] <= rim_anchor["box"]["x2"] + (rim_width * 0.75):
                if point["center"][1] < rim_center[1]:
                    above_rim_frames += 1
        for previous, current in zip(ball_points, ball_points[1:]):
            previous_above = previous["center"][1] < rim_center[1]
            current_below = current["center"][1] > rim_center[1]
            inside_rim_lane = rim_anchor["box"]["x1"] - (rim_width * 0.5) <= current["center"][0] <= rim_anchor["box"]["x2"] + (rim_width * 0.5)
            if previous_above and current_below and inside_rim_lane:
                through_hoop_hits += 1

    arc_score = _arc_score(ball_points, frame_height)
    if ball_points and player_tracks:
        shot_release_score = _shot_release_score(ball_points, player_tracks, frame_diagonal, frame_width, frame_height)

    player_to_rim_distance = _player_to_rim_distance(player_tracks, rim_anchor, frame_diagonal, frame_width, frame_height)
    ball_carrier_speed, possession_change_likelihood = _ball_carrier_motion(ball_points, player_tracks, frame_diagonal, frame_width, frame_height)
    transition_speed_score = _transition_speed_score(player_tracks, ball_carrier_speed, frame_diagonal, frame_width, frame_height)
    defender_proximity = _defender_proximity(player_tracks, ball_points, frame_diagonal, frame_width, frame_height)
    continuity_score = _continuity_score(ball_track, player_tracks)

    ball_near_rim = 0.0
    if near_rim_distances:
        best_distance = min(near_rim_distances)
        ball_near_rim = max(0.0, 1.0 - min(best_distance / 0.24, 1.0))

    ball_above_rim = (above_rim_frames / len(ball_points)) if ball_points else 0.0
    ball_through_hoop = min(max((through_hoop_hits / max(len(ball_points) - 1, 1)) * 1.8, 0.0), 1.0)

    if action.canonicalLabel in {"fast break", "steal"}:
        transition_speed_score = min(max(transition_speed_score + 0.1, 0.0), 1.0)
        possession_change_likelihood = min(max(possession_change_likelihood + 0.08, 0.0), 1.0)
    if action.canonicalLabel == "block":
        defender_proximity = min(max(defender_proximity + 0.1, 0.0), 1.0)
    if action.canonicalLabel in SHOT_LABELS:
        shot_release_score = min(max(shot_release_score + 0.08, 0.0), 1.0)

    return StructuredBasketballSignals(
        ballNearRim=min(max(ball_near_rim, 0.0), 1.0),
        ballAboveRim=min(max(ball_above_rim, 0.0), 1.0),
        ballArcApex=min(max(arc_score, 0.0), 1.0),
        ballThroughHoopLikelihood=min(max(ball_through_hoop, 0.0), 1.0),
        possessionChangeLikelihood=min(max(possession_change_likelihood, 0.0), 1.0),
        playerToRimDistance=round(player_to_rim_distance, 4) if player_to_rim_distance is not None else None,
        ballCarrierSpeed=min(max(ball_carrier_speed, 0.0), 1.0),
        transitionSpeedScore=min(max(transition_speed_score, 0.0), 1.0),
        defenderProximityAtShot=min(max(defender_proximity, 0.0), 1.0),
        shotReleaseCandidate=min(max(shot_release_score, 0.0), 1.0),
        samePlayContinuityScore=min(max(continuity_score, 0.0), 1.0),
    )


def derive_structured_decision(
    *,
    signals: StructuredBasketballSignals,
    action: ActionPrediction,
) -> StructuredDecision:
    auxiliary_scores = _auxiliary_label_scores(action.topLabels)
    shot_aux = _max_score(auxiliary_scores, {"dunk", "layup", "jumper", "three", "putback", "miss"})
    turnover_aux = _max_score(auxiliary_scores, {"steal"})
    defensive_aux = _max_score(auxiliary_scores, {"block"})
    transition_aux = _max_score(auxiliary_scores, {"fast break"})

    family_scores = {
        "shot_attempt": min(
            max(
                (signals.shotReleaseCandidate * 0.38)
                + (signals.ballArcApex * 0.24)
                + (signals.ballNearRim * 0.18)
                + (signals.ballAboveRim * 0.08)
                + (shot_aux * 0.28),
                0.0,
            ),
            1.0,
        ),
        "turnover": min(
            max(
                (signals.possessionChangeLikelihood * 0.62)
                + (signals.samePlayContinuityScore * 0.1)
                + (turnover_aux * 0.44),
                0.0,
            ),
            1.0,
        ),
        "defensive_event": min(
            max(
                (signals.defenderProximityAtShot * 0.45)
                + (signals.shotReleaseCandidate * 0.18)
                + (defensive_aux * 0.5),
                0.0,
            ),
            1.0,
        ),
        "transition": min(
            max(
                (signals.transitionSpeedScore * 0.6)
                + (signals.ballCarrierSpeed * 0.12)
                + (transition_aux * 0.44),
                0.0,
            ),
            1.0,
        ),
        "other": 0.28,
    }
    dominant_family, dominant_family_score, family_margin = _pick_label(family_scores)
    if dominant_family_score < 0.42 or family_margin < 0.06:
        dominant_family = "other"

    outcome_scores = {
        "made": 0.0,
        "missed": 0.0,
        "blocked": 0.0,
        "uncertain": 0.25,
    }
    subtype_scores = {
        "dunk": 0.0,
        "layup": 0.0,
        "jumper": 0.0,
        "three": 0.0,
        "putback": 0.0,
    }

    player_to_rim = signals.playerToRimDistance if signals.playerToRimDistance is not None else 0.45

    if dominant_family == "shot_attempt":
        made_aux = _max_score(auxiliary_scores, {"dunk", "layup", "jumper", "three", "putback"}) * 0.42
        miss_aux = _max_score(auxiliary_scores, {"miss"}) * 0.92
        block_aux = _max_score(auxiliary_scores, {"block"}) * 0.92
        outcome_scores["made"] = max(
            signals.ballThroughHoopLikelihood,
            made_aux,
            (
                (signals.ballNearRim * 0.26)
                + (signals.ballArcApex * 0.18)
                + (signals.shotReleaseCandidate * 0.18)
                + (signals.ballAboveRim * 0.1)
            ),
        )
        outcome_scores["missed"] = max(
            (
                (signals.shotReleaseCandidate * 0.28)
                + (signals.ballArcApex * 0.18)
                + ((1.0 - signals.ballThroughHoopLikelihood) * 0.16)
            ),
            miss_aux,
        )
        outcome_scores["blocked"] = max(
            block_aux,
            signals.defenderProximityAtShot * 0.72 * max(signals.shotReleaseCandidate, 0.35),
        )
        outcome_scores["uncertain"] = max(
            0.22,
            1.0 - max(outcome_scores["made"], outcome_scores["missed"], outcome_scores["blocked"]),
        )

        subtype_scores["dunk"] = max(
            _max_score(auxiliary_scores, {"dunk"}),
            min(max(signals.ballAboveRim, 0.0), 1.0) * max(0.0, 1.0 - (player_to_rim / 0.22)),
        )
        subtype_scores["layup"] = max(
            _max_score(auxiliary_scores, {"layup"}),
            max(0.0, 1.0 - (player_to_rim / 0.28)) * max(signals.shotReleaseCandidate, 0.35),
        )
        subtype_scores["three"] = max(
            _max_score(auxiliary_scores, {"three"}),
            min(max((player_to_rim - 0.28) / 0.22, 0.0), 1.0) * max(signals.shotReleaseCandidate, 0.35),
        )
        subtype_scores["putback"] = max(
            _max_score(auxiliary_scores, {"putback"}),
            max(signals.samePlayContinuityScore, 0.0) * max(0.0, 1.0 - (player_to_rim / 0.24)),
        )
        subtype_scores["jumper"] = max(
            _max_score(auxiliary_scores, {"jumper"}),
            max(0.0, 1.0 - abs(player_to_rim - 0.35) / 0.28) * max(signals.shotReleaseCandidate, 0.32),
        )

    if dominant_family == "turnover":
        outcome = "uncertain"
        canonical_label = "steal"
        display_label = "Steal"
        event_subtype = "steal"
        shot_subtype = None
        outcome_scores["uncertain"] = max(outcome_scores["uncertain"], 0.7)
    elif dominant_family == "transition":
        outcome = "uncertain"
        canonical_label = "fast break"
        display_label = "Fast Break"
        event_subtype = "transition"
        shot_subtype = None
        outcome_scores["uncertain"] = max(outcome_scores["uncertain"], 0.68)
    elif dominant_family == "defensive_event":
        blocked_score = max(outcome_scores["blocked"], _max_score(auxiliary_scores, {"block"}) * 0.96)
        outcome = "blocked" if blocked_score >= 0.44 else "uncertain"
        canonical_label = "block" if outcome == "blocked" else "uncertain"
        display_label = "Block" if outcome == "blocked" else "Highlight"
        event_subtype = "block" if outcome == "blocked" else None
        shot_subtype = None
        outcome_scores["blocked"] = blocked_score
    elif dominant_family == "shot_attempt":
        outcome_label, outcome_score, outcome_margin = _pick_label(outcome_scores)
        if outcome_score < 0.4 or outcome_margin < 0.05:
            outcome_label = "uncertain"

        if (
            outcome_label == "made"
            and signals.ballThroughHoopLikelihood < 0.62
            and (
                action.canonicalLabel == "miss"
                or miss_aux >= max(made_aux, 0.38)
            )
        ):
            outcome_label = "missed"

        subtype_label, subtype_score, subtype_margin = _pick_label(subtype_scores)
        if subtype_score < 0.34 or subtype_margin < 0.04:
            subtype_label = None

        outcome = outcome_label
        shot_subtype = subtype_label
        event_subtype = shot_subtype
        if outcome == "blocked":
            canonical_label = "block"
            display_label = "Block"
        elif outcome == "missed":
            canonical_label = "miss"
            display_label = "Highlight"
        elif shot_subtype in {"dunk", "layup", "three"} and outcome != "uncertain":
            canonical_label = shot_subtype
            display_label = canonical_to_display_label(shot_subtype)
        elif shot_subtype == "putback" and outcome == "made":
            canonical_label = "putback"
            display_label = "Made Shot"
        elif outcome == "made":
            canonical_label = shot_subtype or "jumper"
            display_label = "Made Shot" if canonical_label != "three" else "Three Pointer"
        else:
            canonical_label = shot_subtype or "uncertain"
            display_label = "Highlight"
    else:
        outcome = "uncertain"
        canonical_label = "uncertain"
        display_label = "Highlight"
        event_subtype = None
        shot_subtype = None
        outcome_scores["uncertain"] = max(outcome_scores["uncertain"], 0.6)

    confidence_before_mapping = dominant_family_score
    family_confidence_before_mapping = dominant_family_score
    family_confidence_after_mapping = dominant_family_score if dominant_family != "other" else max(dominant_family_score, 0.46)
    shot_confidence_before_mapping = subtype_scores.get(shot_subtype, 0.0) if shot_subtype else None
    shot_confidence_after_mapping = shot_confidence_before_mapping
    outcome_confidence_before_mapping = outcome_scores.get(outcome, 0.0)
    outcome_confidence_after_mapping = outcome_confidence_before_mapping
    if dominant_family == "shot_attempt":
        confidence_after_mapping = max(dominant_family_score, outcome_scores.get(outcome, 0.0), max(subtype_scores.values(), default=0.0))
    elif dominant_family in {"turnover", "transition", "defensive_event"}:
        confidence_after_mapping = max(dominant_family_score, _max_score(auxiliary_scores, {canonical_label}))
    else:
        confidence_after_mapping = max(0.46, dominant_family_score)

    return StructuredDecision(
        canonicalLabel=canonical_label,
        displayLabel=display_label,
        eventFamily=dominant_family,
        eventSubtype=event_subtype,
        shotSubtype=shot_subtype,
        outcome=outcome,
        eventType=dominant_family,
        shotType=shot_subtype or "unknown",
        makeMiss="make" if outcome == "made" else "miss" if outcome in {"missed", "blocked"} else "unknown",
        confidenceBeforeMapping=min(max(confidence_before_mapping, 0.0), 1.0),
        confidenceAfterMapping=min(max(confidence_after_mapping, 0.0), 1.0),
        eventFamilyConfidenceBeforeMapping=min(max(family_confidence_before_mapping, 0.0), 1.0),
        eventFamilyConfidenceAfterMapping=min(max(family_confidence_after_mapping, 0.0), 1.0),
        shotSubtypeConfidenceBeforeMapping=min(max(shot_confidence_before_mapping, 0.0), 1.0)
        if shot_confidence_before_mapping is not None
        else None,
        shotSubtypeConfidenceAfterMapping=min(max(shot_confidence_after_mapping, 0.0), 1.0)
        if shot_confidence_after_mapping is not None
        else None,
        outcomeConfidenceBeforeMapping=min(max(outcome_confidence_before_mapping, 0.0), 1.0),
        outcomeConfidenceAfterMapping=min(max(outcome_confidence_after_mapping, 0.0), 1.0),
        isUncertain=outcome == "uncertain" or canonical_label == "uncertain",
        familyScores=family_scores,
        outcomeScores=outcome_scores,
        subtypeScores=subtype_scores,
    )


def _primary_track(tracks: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
    matching = [track for track in tracks if track.get("label") == label]
    if not matching:
        return None
    return max(matching, key=lambda item: (int(item.get("observationCount") or 0), float(item.get("averageConfidence") or 0.0)))


def _track_points(track: dict[str, Any] | None, frame_width: int, frame_height: int) -> list[dict[str, Any]]:
    if not track:
        return []
    points: list[dict[str, Any]] = []
    for observation in track.get("observations") or []:
        box = observation.get("box") or {}
        x1 = float(box.get("x1") or 0.0) * frame_width
        y1 = float(box.get("y1") or 0.0) * frame_height
        x2 = float(box.get("x2") or 0.0) * frame_width
        y2 = float(box.get("y2") or 0.0) * frame_height
        points.append(
            {
                "timestamp": float(observation.get("timestampSeconds") or 0.0),
                "confidence": float(observation.get("confidence") or 0.0),
                "box": {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "width": max(x2 - x1, 0.0),
                    "height": max(y2 - y1, 0.0),
                },
                "center": ((x1 + x2) / 2.0, (y1 + y2) / 2.0),
            }
        )
    return points


def _arc_score(ball_points: list[dict[str, Any]], frame_height: int) -> float:
    if len(ball_points) < 3 or frame_height <= 0:
        return 0.0
    ys = [point["center"][1] for point in ball_points]
    start_y = ys[0]
    apex_y = min(ys)
    end_y = ys[-1]
    apex_index = ys.index(apex_y)
    if apex_index == 0 or apex_index == len(ys) - 1:
        return 0.0
    rise = max(start_y - apex_y, 0.0) / frame_height
    drop = max(end_y - apex_y, 0.0) / frame_height
    return min(max((rise + drop) * 2.4, 0.0), 1.0)


def _shot_release_score(
    ball_points: list[dict[str, Any]],
    player_tracks: list[dict[str, Any]],
    frame_diagonal: float,
    frame_width: int,
    frame_height: int,
) -> float:
    if len(ball_points) < 2 or not player_tracks or frame_diagonal <= 0:
        return 0.0
    player_points = [_track_points(track, frame_width, frame_height) for track in player_tracks]
    flattened = [point for points in player_points for point in points]
    if not flattened:
        return 0.0
    early_point = ball_points[0]
    later_point = ball_points[min(2, len(ball_points) - 1)]
    early_player_distance = min(_euclidean_distance(early_point["center"], point["center"]) for point in flattened)
    later_player_distance = min(_euclidean_distance(later_point["center"], point["center"]) for point in flattened)
    upward_motion = max(early_point["center"][1] - later_point["center"][1], 0.0) / max(frame_diagonal, 1.0)
    separation_gain = max(later_player_distance - early_player_distance, 0.0) / max(frame_diagonal, 1.0)
    return min(max((upward_motion * 8.0) + (separation_gain * 10.0), 0.0), 1.0)


def _player_to_rim_distance(
    player_tracks: list[dict[str, Any]],
    rim_anchor: dict[str, Any] | None,
    frame_diagonal: float,
    frame_width: int,
    frame_height: int,
) -> float | None:
    if not rim_anchor or not player_tracks or frame_diagonal <= 0:
        return None
    rim_center = rim_anchor["center"]
    distances: list[float] = []
    for track in player_tracks:
        for point in _track_points(track, frame_width, frame_height):
            distances.append(_euclidean_distance(point["center"], rim_center) / frame_diagonal)
    if not distances:
        return None
    return min(distances)


def _ball_carrier_motion(
    ball_points: list[dict[str, Any]],
    player_tracks: list[dict[str, Any]],
    frame_diagonal: float,
    frame_width: int,
    frame_height: int,
) -> tuple[float, float]:
    if frame_diagonal <= 0:
        return 0.0, 0.0
    if not player_tracks:
        return 0.0, 0.0

    track_sequences: dict[str, list[dict[str, Any]]] = {
        str(track.get("trackId")): _track_points(track, frame_width, frame_height) for track in player_tracks
    }
    carrier_assignments: list[str] = []
    carrier_speeds: list[float] = []

    for point in ball_points:
        best_track_id = None
        best_distance = None
        for track_id, track_points in track_sequences.items():
            nearest = _nearest_point(track_points, point["timestamp"])
            if nearest is None:
                continue
            distance = _euclidean_distance(nearest["center"], point["center"])
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_track_id = track_id
        if best_track_id is not None:
            carrier_assignments.append(best_track_id)

    for track_points in track_sequences.values():
        if len(track_points) < 2:
            continue
        for previous, current in zip(track_points, track_points[1:]):
            elapsed = max(current["timestamp"] - previous["timestamp"], 0.001)
            distance = _euclidean_distance(previous["center"], current["center"])
            carrier_speeds.append(min(distance / (frame_diagonal * elapsed), 1.0))

    possession_change_count = 0
    for previous, current in zip(carrier_assignments, carrier_assignments[1:]):
        if previous != current:
            possession_change_count += 1

    average_speed = sum(carrier_speeds) / len(carrier_speeds) if carrier_speeds else 0.0
    possession_change = possession_change_count / max(len(carrier_assignments) - 1, 1) if carrier_assignments else 0.0
    return average_speed, possession_change


def _transition_speed_score(
    player_tracks: list[dict[str, Any]],
    ball_carrier_speed: float,
    frame_diagonal: float,
    frame_width: int,
    frame_height: int,
) -> float:
    if not player_tracks or frame_diagonal <= 0:
        return ball_carrier_speed
    displacements: list[float] = []
    for track in player_tracks:
        points = _track_points(track, frame_width, frame_height)
        if len(points) < 2:
            continue
        start = points[0]
        end = points[-1]
        displacements.append(_euclidean_distance(start["center"], end["center"]) / frame_diagonal)
    player_progress = (sum(displacements) / len(displacements)) if displacements else 0.0
    return min(max((ball_carrier_speed * 0.65) + (player_progress * 0.85), 0.0), 1.0)


def _defender_proximity(
    player_tracks: list[dict[str, Any]],
    ball_points: list[dict[str, Any]],
    frame_diagonal: float,
    frame_width: int,
    frame_height: int,
) -> float:
    if not player_tracks or not ball_points or frame_diagonal <= 0:
        return 0.0
    release_point = ball_points[min(1, len(ball_points) - 1)]
    distances: list[float] = []
    for track in player_tracks:
        nearest = _nearest_point(_track_points(track, frame_width, frame_height), release_point["timestamp"])
        if nearest is None:
            continue
        distances.append(_euclidean_distance(nearest["center"], release_point["center"]) / frame_diagonal)
    if len(distances) < 2:
        return 0.0
    distances.sort()
    defender_distance = distances[1]
    return min(max(1.0 - min(defender_distance / 0.22, 1.0), 0.0), 1.0)


def _continuity_score(ball_track: dict[str, Any] | None, player_tracks: list[dict[str, Any]]) -> float:
    ball_observations = int(ball_track.get("observationCount") or 0) if ball_track else 0
    player_observations = max((int(track.get("observationCount") or 0) for track in player_tracks), default=0)
    ball_component = min(max(ball_observations / 12.0, 0.0), 1.0) * 0.45
    player_component = min(max(player_observations / 12.0, 0.0), 1.0) * 0.25
    return min(max(ball_component + player_component, 0.0), 1.0)


def _nearest_point(points: list[dict[str, Any]], timestamp: float) -> dict[str, Any] | None:
    if not points:
        return None
    return min(points, key=lambda point: abs(point["timestamp"] - timestamp))


def _pick_label(scores: dict[str, float]) -> tuple[str, float, float]:
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ordered:
        return "uncertain", 0.0, 0.0
    best_label, best_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0
    return best_label, best_score, best_score - second_score


def _auxiliary_label_scores(top_labels: list[LabelScore]) -> dict[str, float]:
    result: dict[str, float] = {}
    for label_score in top_labels:
        result[label_score.label] = max(result.get(label_score.label, 0.0), label_score.confidence)
    return result


def _max_score(scores: dict[str, float], labels: set[str]) -> float:
    return max((scores.get(label, 0.0) for label in labels), default=0.0)


def _euclidean_distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    dx = first[0] - second[0]
    dy = first[1] - second[1]
    return math.sqrt((dx * dx) + (dy * dy))


def _round_mapping(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 4) for key, value in values.items()}
