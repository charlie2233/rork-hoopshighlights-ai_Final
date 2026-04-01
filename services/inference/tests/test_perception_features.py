from __future__ import annotations

import unittest

from services.inference.app.perception_features import (
    PerceptionObservation,
    derive_perception_features,
)


def _obs(
    label: str,
    bbox: tuple[float, float, float, float],
    *,
    t: float,
    track_id: str | None = None,
    team: str | None = None,
    confidence: float = 0.9,
) -> PerceptionObservation:
    return PerceptionObservation(
        label=label,
        bbox=bbox,
        confidence=confidence,
        timestamp_seconds=t,
        track_id=track_id,
        team=team,
    )


class PerceptionFeatureExtractionTests(unittest.TestCase):
    def test_shot_finishing_signals_are_high_near_the_rim(self) -> None:
        frames = [
            [
                _obs("ball", (0.46, 0.18, 0.50, 0.22), t=0.0, track_id="ball"),
                _obs("rim", (0.44, 0.34, 0.56, 0.40), t=0.0),
                _obs("player", (0.40, 0.58, 0.50, 0.78), t=0.0, track_id="offense-1"),
                _obs("defender", (0.74, 0.62, 0.84, 0.82), t=0.0, track_id="def-1", team="defense"),
            ],
            [
                _obs("ball", (0.47, 0.28, 0.51, 0.32), t=0.1, track_id="ball"),
                _obs("rim", (0.44, 0.34, 0.56, 0.40), t=0.1),
                _obs("player", (0.42, 0.54, 0.52, 0.74), t=0.1, track_id="offense-1"),
                _obs("defender", (0.76, 0.62, 0.86, 0.82), t=0.1, track_id="def-1", team="defense"),
            ],
            [
                _obs("ball", (0.48, 0.37, 0.52, 0.41), t=0.2, track_id="ball"),
                _obs("rim", (0.44, 0.34, 0.56, 0.40), t=0.2),
                _obs("player", (0.44, 0.50, 0.54, 0.70), t=0.2, track_id="offense-1"),
                _obs("defender", (0.78, 0.62, 0.88, 0.82), t=0.2, track_id="def-1", team="defense"),
            ],
            [
                _obs("ball", (0.48, 0.43, 0.52, 0.47), t=0.3, track_id="ball"),
                _obs("rim", (0.44, 0.34, 0.56, 0.40), t=0.3),
                _obs("player", (0.45, 0.48, 0.55, 0.68), t=0.3, track_id="offense-1"),
                _obs("defender", (0.80, 0.62, 0.90, 0.82), t=0.3, track_id="def-1", team="defense"),
            ],
        ]

        features = derive_perception_features(frames)

        self.assertGreater(features.ballNearRim, 0.6)
        self.assertGreater(features.ballAboveRim, 0.15)
        self.assertGreater(features.ballThroughHoopLikelihood, 0.55)
        self.assertGreater(features.shotReleaseCandidate, 0.5)
        self.assertLess(features.defenderProximityAtShot, 0.3)
        self.assertLess(features.playerToRimDistance, 0.7)
        self.assertGreater(features.samePlayContinuityScore, 0.5)

    def test_transition_and_possession_change_rise_when_ball_switches_carriers(self) -> None:
        frames = [
            [
                _obs("ball", (0.16, 0.44, 0.20, 0.48), t=0.0, track_id="ball"),
                _obs("player", (0.10, 0.40, 0.20, 0.60), t=0.0, track_id="carrier-a"),
                _obs("player", (0.58, 0.40, 0.68, 0.60), t=0.0, track_id="carrier-b"),
                _obs("defender", (0.46, 0.42, 0.56, 0.62), t=0.0, track_id="def-1", team="defense"),
            ],
            [
                _obs("ball", (0.34, 0.44, 0.38, 0.48), t=0.2, track_id="ball"),
                _obs("player", (0.26, 0.40, 0.36, 0.60), t=0.2, track_id="carrier-a"),
                _obs("player", (0.54, 0.40, 0.64, 0.60), t=0.2, track_id="carrier-b"),
                _obs("defender", (0.42, 0.42, 0.52, 0.62), t=0.2, track_id="def-1", team="defense"),
            ],
            [
                _obs("ball", (0.58, 0.44, 0.62, 0.48), t=0.4, track_id="ball"),
                _obs("player", (0.50, 0.40, 0.60, 0.60), t=0.4, track_id="carrier-b"),
                _obs("player", (0.42, 0.40, 0.52, 0.60), t=0.4, track_id="carrier-a"),
                _obs("defender", (0.58, 0.42, 0.68, 0.62), t=0.4, track_id="def-1", team="defense"),
            ],
            [
                _obs("ball", (0.74, 0.42, 0.78, 0.46), t=0.6, track_id="ball"),
                _obs("player", (0.66, 0.38, 0.76, 0.58), t=0.6, track_id="carrier-b"),
                _obs("player", (0.60, 0.40, 0.70, 0.60), t=0.6, track_id="carrier-a"),
                _obs("defender", (0.70, 0.40, 0.80, 0.60), t=0.6, track_id="def-1", team="defense"),
            ],
        ]

        features = derive_perception_features(frames)

        self.assertGreater(features.transitionSpeedScore, 0.35)
        self.assertGreater(features.ballCarrierSpeed, 0.2)
        self.assertGreater(features.possessionChangeLikelihood, 0.35)
        self.assertLess(features.samePlayContinuityScore, 0.9)

    def test_defender_pressure_is_high_when_defender_is_close_to_shot_frame(self) -> None:
        frames = [
            [
                _obs("ball", (0.47, 0.28, 0.51, 0.32), t=0.0, track_id="ball"),
                _obs("rim", (0.44, 0.34, 0.56, 0.40), t=0.0),
                _obs("player", (0.40, 0.50, 0.50, 0.70), t=0.0, track_id="offense-1"),
                _obs("defender", (0.49, 0.46, 0.59, 0.66), t=0.0, track_id="def-1", team="defense"),
            ],
            [
                _obs("ball", (0.48, 0.33, 0.52, 0.37), t=0.1, track_id="ball"),
                _obs("rim", (0.44, 0.34, 0.56, 0.40), t=0.1),
                _obs("player", (0.42, 0.48, 0.52, 0.68), t=0.1, track_id="offense-1"),
                _obs("defender", (0.47, 0.41, 0.57, 0.61), t=0.1, track_id="def-1", team="defense"),
            ],
        ]

        features = derive_perception_features(frames)

        self.assertGreater(features.defenderProximityAtShot, 0.5)
        self.assertGreater(features.shotReleaseCandidate, 0.4)

    def test_missing_ball_returns_zero_vector(self) -> None:
        features = derive_perception_features(
            [
                [
                    _obs("rim", (0.44, 0.34, 0.56, 0.40), t=0.0),
                    _obs("player", (0.40, 0.58, 0.50, 0.78), t=0.0, track_id="offense-1"),
                ]
            ]
        )

        self.assertEqual(features.playerToRimDistance, 0.0)
        self.assertEqual(features.ballNearRim, 0.0)
        self.assertEqual(features.ballAboveRim, 0.0)
        self.assertEqual(features.ballThroughHoopLikelihood, 0.0)
        self.assertEqual(features.possessionChangeLikelihood, 0.0)
        self.assertEqual(features.transitionSpeedScore, 0.0)
        self.assertEqual(features.ballCarrierSpeed, 0.0)
        self.assertEqual(features.defenderProximityAtShot, 0.0)
        self.assertEqual(features.shotReleaseCandidate, 0.0)
        self.assertEqual(features.samePlayContinuityScore, 0.0)

    def test_extreme_ball_velocity_does_not_overflow_sigmoid(self) -> None:
        frames = [
            [
                _obs("ball", (0.48, 5000.00, 0.52, 5000.04), t=0.0, track_id="ball"),
                _obs("rim", (0.44, 0.34, 0.56, 0.40), t=0.0),
                _obs("player", (0.40, 0.58, 0.50, 0.78), t=0.0, track_id="offense-1"),
            ],
            [
                _obs("ball", (0.48, -5000.00, 0.52, -4999.96), t=0.1, track_id="ball"),
                _obs("rim", (0.44, 0.34, 0.56, 0.40), t=0.1),
                _obs("player", (0.42, 0.54, 0.52, 0.74), t=0.1, track_id="offense-1"),
            ],
        ]

        features = derive_perception_features(frames)

        self.assertGreaterEqual(features.shotReleaseCandidate, 0.0)
        self.assertLessEqual(features.shotReleaseCandidate, 1.0)


if __name__ == "__main__":
    unittest.main()
