from __future__ import annotations

from dataclasses import dataclass
from math import exp, sqrt
from statistics import mean
from typing import Iterable, Sequence


BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class PerceptionObservation:
    label: str
    bbox: BBox
    confidence: float = 1.0
    timestamp_seconds: float = 0.0
    track_id: str | None = None
    team: str | None = None


@dataclass(frozen=True)
class PerceptionFeatureVector:
    playerToRimDistance: float
    ballNearRim: float
    ballToRimDistance: float
    ballToRimLikelihood: float
    ballAboveRim: float
    ballArcApex: float
    ballVerticalVelocityY: float
    ballVerticalSpeedNearRim: float
    ballThroughHoopLikelihood: float
    possessionChangeLikelihood: float
    transitionSpeedScore: float
    ballCarrierSpeed: float
    defenderProximityAtShot: float
    shotReleaseCandidate: float
    samePlayContinuityScore: float


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clamp_signed(value: float, limit: float = 1.0) -> float:
    return max(-limit, min(limit, value))


def _center(box: BBox) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _width(box: BBox) -> float:
    return max(0.0, box[2] - box[0])


def _height(box: BBox) -> float:
    return max(0.0, box[3] - box[1])


def _distance(box_a: BBox, box_b: BBox) -> float:
    ax, ay = _center(box_a)
    bx, by = _center(box_b)
    return sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def _logistic(value: float, midpoint: float, scale: float) -> float:
    scale = max(scale, 1e-6)
    z = (value - midpoint) / scale
    # Use a numerically stable sigmoid so extreme live tracking velocities do not
    # overflow and silently disable the temporal shadow path.
    if z >= 0.0:
        return 1.0 / (1.0 + exp(-min(z, 700.0)))
    exp_z = exp(max(z, -700.0))
    return exp_z / (1.0 + exp_z)


def _distance_score(distance: float, scale: float) -> float:
    scale = max(scale, 1e-6)
    return _clamp01(distance / scale)


def _proximity_score(distance: float, scale: float) -> float:
    return _clamp01(1.0 - _distance_score(distance, scale))


def _nearest(observations: Sequence[PerceptionObservation], reference: PerceptionObservation) -> PerceptionObservation | None:
    if not observations:
        return None
    return min(observations, key=lambda obs: _distance(obs.bbox, reference.bbox))


def _group_by_time(frames: Sequence[Sequence[PerceptionObservation]]) -> list[tuple[float, list[PerceptionObservation]]]:
    grouped: list[tuple[float, list[PerceptionObservation]]] = []
    for frame in frames:
        if not frame:
            continue
        grouped.append((frame[0].timestamp_seconds, list(frame)))
    grouped.sort(key=lambda item: item[0])
    return grouped


def _dominant_track_series(
    frames: Sequence[Sequence[PerceptionObservation]],
    target_labels: Iterable[str],
) -> tuple[str | None, list[PerceptionObservation]]:
    by_track: dict[str, list[PerceptionObservation]] = {}
    wanted = {label.lower() for label in target_labels}
    for frame in frames:
        for obs in frame:
            if obs.track_id is None or obs.label.lower() not in wanted:
                continue
            by_track.setdefault(obs.track_id, []).append(obs)
    if not by_track:
        return None, []
    track_id = max(by_track.items(), key=lambda item: len(item[1]))[0]
    series = sorted(by_track[track_id], key=lambda obs: obs.timestamp_seconds)
    return track_id, series


def _track_speed(series: Sequence[PerceptionObservation]) -> float:
    if len(series) < 2:
        return 0.0
    first = series[0]
    last = series[-1]
    dt = max(last.timestamp_seconds - first.timestamp_seconds, 1e-6)
    return _distance(first.bbox, last.bbox) / dt


def _ball_velocity(series: Sequence[PerceptionObservation]) -> tuple[float, float]:
    if len(series) < 2:
        return 0.0, 0.0
    first = series[0]
    last = series[-1]
    dt = max(last.timestamp_seconds - first.timestamp_seconds, 1e-6)
    first_cx, first_cy = _center(first.bbox)
    last_cx, last_cy = _center(last.bbox)
    return ((last_cx - first_cx) / dt, (last_cy - first_cy) / dt)


def compute_arc_score(series: Sequence[PerceptionObservation]) -> float:
    if len(series) < 3:
        return 0.0
    centers_y = [_center(obs.bbox)[1] for obs in series]
    apex_index = min(range(len(centers_y)), key=centers_y.__getitem__)
    if apex_index == 0 or apex_index == len(centers_y) - 1:
        return 0.0
    apex_y = centers_y[apex_index]
    left_drop = centers_y[0] - apex_y
    right_drop = centers_y[-1] - apex_y
    if left_drop <= 0.0 or right_drop <= 0.0:
        return 0.0
    return _clamp01(min(left_drop, right_drop) / 0.18)


def _collect(series: Sequence[PerceptionObservation], frame_time: float, tolerance: float = 0.15) -> list[PerceptionObservation]:
    return [obs for obs in series if abs(obs.timestamp_seconds - frame_time) <= tolerance]


def _zero_feature_vector() -> PerceptionFeatureVector:
    return PerceptionFeatureVector(*(0.0 for _ in range(len(PerceptionFeatureVector.__dataclass_fields__))))


def derive_perception_features(
    frames: Sequence[Sequence[PerceptionObservation]],
    *,
    rim_labels: Sequence[str] = ("rim", "hoop"),
    ball_labels: Sequence[str] = ("ball",),
    player_labels: Sequence[str] = ("player",),
    defender_labels: Sequence[str] = ("defender", "opponent"),
) -> PerceptionFeatureVector:
    grouped = _group_by_time(frames)
    if not grouped:
        return _zero_feature_vector()

    all_frames = [frame for _, frame in grouped]
    ball_series = [obs for frame in all_frames for obs in frame if obs.label.lower() in {label.lower() for label in ball_labels}]
    rim_series = [obs for frame in all_frames for obs in frame if obs.label.lower() in {label.lower() for label in rim_labels}]
    player_series = [obs for frame in all_frames for obs in frame if obs.label.lower() in {label.lower() for label in player_labels}]
    defender_series = [
        obs
        for frame in all_frames
        for obs in frame
        if obs.label.lower() in {label.lower() for label in defender_labels} or (obs.team or "").lower() == "defense"
    ]

    if not ball_series:
        return _zero_feature_vector()

    ball_series = sorted(ball_series, key=lambda obs: obs.timestamp_seconds)
    rim_series = sorted(rim_series, key=lambda obs: obs.timestamp_seconds)
    player_series = sorted(player_series, key=lambda obs: obs.timestamp_seconds)
    defender_series = sorted(defender_series, key=lambda obs: obs.timestamp_seconds)

    shot_candidate_scores: list[float] = []
    ball_near_rim_scores: list[float] = []
    ball_above_rim_scores: list[float] = []
    near_rim_distances: list[float] = []
    continuity_pairs: list[float] = []
    carrier_track_ids: list[str] = []
    ball_velocity_x, ball_velocity_y = _ball_velocity(ball_series) if len(ball_series) >= 2 else (0.0, 0.0)

    for ball in ball_series:
        nearest_rim = _nearest(rim_series, ball)
        nearest_player = _nearest(player_series, ball)
        nearest_defender = _nearest(defender_series, ball)

        if nearest_rim is None:
            ball_near_rim_scores.append(0.0)
            ball_above_rim_scores.append(0.0)
            shot_candidate_scores.append(0.0)
            continue

        rim_center = _center(nearest_rim.bbox)
        ball_center = _center(ball.bbox)
        rim_height = max(_height(nearest_rim.bbox), 1e-6)
        normalized_distance = _distance(ball.bbox, nearest_rim.bbox)
        near_rim = _proximity_score(normalized_distance, 0.35)
        above_rim = _clamp01((rim_center[1] - ball_center[1]) / max(rim_height * 2.5, 1e-6))

        vertical_motion = _clamp01(_logistic(-ball_velocity_y, -0.01, 0.08))

        player_proximity = 0.0
        defender_proximity = 0.0
        if nearest_player is not None:
            player_proximity = _proximity_score(_distance(ball.bbox, nearest_player.bbox), 0.4)
            if nearest_player.track_id:
                carrier_track_ids.append(nearest_player.track_id)
        if nearest_defender is not None:
            defender_proximity = _proximity_score(_distance(ball.bbox, nearest_defender.bbox), 0.4)

        ball_near_rim_scores.append(near_rim)
        ball_above_rim_scores.append(above_rim)
        near_rim_distances.append(normalized_distance)
        shot_candidate_scores.append(_clamp01(0.5 * near_rim + 0.3 * above_rim + 0.2 * vertical_motion))
        continuity_pairs.append(_clamp01(0.5 * player_proximity + 0.5 * (1.0 - defender_proximity)))

    shot_index = max(range(len(ball_series)), key=lambda idx: shot_candidate_scores[idx])
    shot_ball = ball_series[shot_index]
    shot_time = shot_ball.timestamp_seconds
    shot_rim = _nearest(rim_series, shot_ball)
    shot_player = _nearest(player_series, shot_ball)
    shot_defender = _nearest(defender_series, shot_ball)

    ball_near_rim = max(ball_near_rim_scores)
    ball_above_rim = max(ball_above_rim_scores)
    best_ball_to_rim_distance = min(near_rim_distances) if near_rim_distances else 1.0
    ball_to_rim_likelihood = _clamp01(1.0 - min(best_ball_to_rim_distance / 0.28, 1.0))
    ball_vertical_speed_near_rim = _clamp01(_logistic(abs(ball_velocity_y), 0.12, 0.08))
    # Keep this helper as a normal module symbol because the Cloud Run shadow
    # path has shown brittle late-binding around underscored helpers.
    ball_arc_apex = compute_arc_score(ball_series)

    if shot_rim is None:
        player_to_rim_distance = 0.0
        ball_through_hoop_likelihood = 0.0
    else:
        player_to_rim_distance = 0.0
        if shot_player is not None:
            player_to_rim_distance = _distance_score(_distance(shot_player.bbox, shot_rim.bbox), 0.75)
        rim_center_y = _center(shot_rim.bbox)[1]
        shot_center_y = _center(shot_ball.bbox)[1]
        rim_height = max(_height(shot_rim.bbox), 1e-6)
        above = shot_center_y <= rim_center_y - 0.08 * rim_height
        below = shot_center_y >= rim_center_y + 0.06 * rim_height
        pre_above = any(_center(ball.bbox)[1] <= rim_center_y - 0.04 * rim_height for ball in ball_series[: shot_index + 1])
        post_below = any(_center(ball.bbox)[1] >= rim_center_y + 0.04 * rim_height for ball in ball_series[shot_index:])
        ball_through_hoop_likelihood = _clamp01(
            0.45 * ball_near_rim
            + 0.25 * (1.0 if pre_above and post_below else 0.0)
            + 0.15 * (1.0 if above or below else 0.0)
            + 0.15 * shot_candidate_scores[shot_index]
        )

    carrier_track_id, carrier_series = _dominant_track_series(all_frames, player_labels)
    if carrier_series:
        ball_carrier_speed = _track_speed(carrier_series)
    else:
        ball_carrier_speed = 0.0
    ball_speed = _track_speed(ball_series)

    if carrier_track_id is not None:
        carrier_frame_ratio = len(_collect(player_series, shot_time)) / max(len(player_series), 1)
    else:
        carrier_frame_ratio = 0.0
    temporal_continuity = mean(continuity_pairs) if continuity_pairs else 0.0
    same_play_continuity = _clamp01(0.6 * carrier_frame_ratio + 0.4 * temporal_continuity)

    if shot_defender is not None:
        defender_proximity_at_shot = _proximity_score(_distance(shot_ball.bbox, shot_defender.bbox), 0.5)
    else:
        defender_proximity_at_shot = 0.0

    transition_speed_score = _clamp01(_logistic(max(ball_carrier_speed, ball_speed), 0.18, 0.08))
    carrier_continuity = 0.0
    if carrier_track_id is not None and carrier_series:
        carrier_continuity = len(carrier_series) / max(len(ball_series), 1)
    possession_change_likelihood = _clamp01(
        0.45 * (1.0 - same_play_continuity)
        + 0.3 * transition_speed_score
        + 0.25 * (1.0 if ball_through_hoop_likelihood < 0.35 and len({track for track in carrier_track_ids if track}) > 1 else 0.0)
    )
    shot_release_candidate = _clamp01(max(shot_candidate_scores))

    return PerceptionFeatureVector(
        playerToRimDistance=_clamp01(player_to_rim_distance),
        ballNearRim=_clamp01(ball_near_rim),
        ballToRimDistance=_clamp01(best_ball_to_rim_distance),
        ballToRimLikelihood=_clamp01(ball_to_rim_likelihood),
        ballAboveRim=_clamp01(ball_above_rim),
        ballArcApex=_clamp01(ball_arc_apex),
        ballVerticalVelocityY=_clamp_signed(ball_velocity_y),
        ballVerticalSpeedNearRim=_clamp01(ball_vertical_speed_near_rim),
        ballThroughHoopLikelihood=_clamp01(ball_through_hoop_likelihood),
        possessionChangeLikelihood=_clamp01(possession_change_likelihood),
        transitionSpeedScore=_clamp01(transition_speed_score),
        ballCarrierSpeed=_clamp01(ball_carrier_speed),
        defenderProximityAtShot=_clamp01(defender_proximity_at_shot),
        shotReleaseCandidate=_clamp01(shot_release_candidate),
        samePlayContinuityScore=_clamp01(0.6 * carrier_continuity + 0.4 * same_play_continuity),
    )
