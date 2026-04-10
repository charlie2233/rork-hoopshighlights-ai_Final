from __future__ import annotations

import unittest

from services.inference.app.models import ActionPrediction, LabelScore, RawLabelScore
from services.inference.app.structured_signals import derive_structured_decision, derive_structured_signals


def _make_action(
    *,
    canonical_label: str,
    confidence: float,
    top_labels: list[tuple[str, float]] | None = None,
) -> ActionPrediction:
    ranked = [
        LabelScore(label=label, confidence=score, rawLabel=label, modelVersion="test:model")
        for label, score in (top_labels or [(canonical_label, confidence)])
    ]
    raw_ranked = [
        RawLabelScore(rawLabel=label, canonicalLabel=label, confidence=score, modelVersion="test:model")
        for label, score in (top_labels or [(canonical_label, confidence)])
    ]
    return ActionPrediction(
        label=canonical_label.title(),
        canonicalLabel=canonical_label,
        confidence=confidence,
        modelVersion="test:model",
        topLabels=ranked,
        rawTopLabels=raw_ranked,
    )


def _perception_with_ball_rim_player() -> dict[str, object]:
    return {
        "frameWidth": 1280,
        "frameHeight": 720,
        "sampledFrameCount": 5,
        "detectionCounts": {"basketball": 5, "rim": 5, "player": 6},
        "trackCounts": {"basketball": 1, "rim": 1, "player": 2},
        "tracks": [
            {
                "trackId": "basketball-1",
                "label": "basketball",
                "averageConfidence": 0.88,
                "observationCount": 5,
                "observations": [
                    {"timestampSeconds": 0.0, "confidence": 0.9, "box": {"x1": 0.44, "y1": 0.46, "x2": 0.46, "y2": 0.48}},
                    {"timestampSeconds": 0.3, "confidence": 0.9, "box": {"x1": 0.47, "y1": 0.36, "x2": 0.49, "y2": 0.38}},
                    {"timestampSeconds": 0.6, "confidence": 0.9, "box": {"x1": 0.50, "y1": 0.28, "x2": 0.52, "y2": 0.30}},
                    {"timestampSeconds": 0.9, "confidence": 0.87, "box": {"x1": 0.53, "y1": 0.35, "x2": 0.55, "y2": 0.37}},
                    {"timestampSeconds": 1.2, "confidence": 0.86, "box": {"x1": 0.57, "y1": 0.44, "x2": 0.59, "y2": 0.46}},
                ],
            },
            {
                "trackId": "rim-1",
                "label": "rim",
                "averageConfidence": 0.91,
                "observationCount": 5,
                "observations": [
                    {"timestampSeconds": 0.0, "confidence": 0.91, "box": {"x1": 0.50, "y1": 0.33, "x2": 0.58, "y2": 0.36}},
                    {"timestampSeconds": 0.3, "confidence": 0.91, "box": {"x1": 0.50, "y1": 0.33, "x2": 0.58, "y2": 0.36}},
                    {"timestampSeconds": 0.6, "confidence": 0.91, "box": {"x1": 0.50, "y1": 0.33, "x2": 0.58, "y2": 0.36}},
                    {"timestampSeconds": 0.9, "confidence": 0.91, "box": {"x1": 0.50, "y1": 0.33, "x2": 0.58, "y2": 0.36}},
                    {"timestampSeconds": 1.2, "confidence": 0.91, "box": {"x1": 0.50, "y1": 0.33, "x2": 0.58, "y2": 0.36}},
                ],
            },
            {
                "trackId": "player-1",
                "label": "player",
                "averageConfidence": 0.82,
                "observationCount": 3,
                "observations": [
                    {"timestampSeconds": 0.0, "confidence": 0.82, "box": {"x1": 0.41, "y1": 0.44, "x2": 0.48, "y2": 0.80}},
                    {"timestampSeconds": 0.3, "confidence": 0.82, "box": {"x1": 0.43, "y1": 0.42, "x2": 0.50, "y2": 0.80}},
                    {"timestampSeconds": 0.6, "confidence": 0.81, "box": {"x1": 0.45, "y1": 0.41, "x2": 0.52, "y2": 0.80}},
                ],
            },
            {
                "trackId": "player-2",
                "label": "player",
                "averageConfidence": 0.71,
                "observationCount": 3,
                "observations": [
                    {"timestampSeconds": 0.3, "confidence": 0.71, "box": {"x1": 0.55, "y1": 0.42, "x2": 0.62, "y2": 0.80}},
                    {"timestampSeconds": 0.6, "confidence": 0.72, "box": {"x1": 0.57, "y1": 0.42, "x2": 0.64, "y2": 0.80}},
                    {"timestampSeconds": 0.9, "confidence": 0.71, "box": {"x1": 0.59, "y1": 0.43, "x2": 0.66, "y2": 0.80}},
                ],
            },
        ],
        "overlayPaths": [],
    }


class StructuredSignalDecisionTests(unittest.TestCase):
    def test_miss_candidate_stays_missed_when_ball_never_goes_through_hoop(self) -> None:
        action = _make_action(
            canonical_label="miss",
            confidence=0.58,
            top_labels=[("miss", 0.58), ("jumper", 0.52), ("three", 0.22)],
        )
        signals = derive_structured_signals(candidate_metadata={"perception": _perception_with_ball_rim_player()}, action=action)
        decision = derive_structured_decision(signals=signals, action=action)

        self.assertEqual(decision.eventFamily, "shot_attempt")
        self.assertEqual(decision.outcome, "missed")
        self.assertEqual(decision.displayLabel, "Highlight")
        self.assertNotEqual(decision.canonicalLabel, "jumper")

    def test_turnover_candidate_uses_possession_change_signal(self) -> None:
        perception = _perception_with_ball_rim_player()
        turnover_track = {
            **perception,
            "tracks": [
                {
                    "trackId": "basketball-1",
                    "label": "basketball",
                    "averageConfidence": 0.84,
                    "observationCount": 4,
                    "observations": [
                        {"timestampSeconds": 0.0, "confidence": 0.82, "box": {"x1": 0.20, "y1": 0.54, "x2": 0.22, "y2": 0.56}},
                        {"timestampSeconds": 0.3, "confidence": 0.83, "box": {"x1": 0.38, "y1": 0.52, "x2": 0.40, "y2": 0.54}},
                        {"timestampSeconds": 0.6, "confidence": 0.86, "box": {"x1": 0.66, "y1": 0.50, "x2": 0.68, "y2": 0.52}},
                        {"timestampSeconds": 0.9, "confidence": 0.84, "box": {"x1": 0.78, "y1": 0.48, "x2": 0.80, "y2": 0.50}},
                    ],
                },
                {
                    "trackId": "player-1",
                    "label": "player",
                    "averageConfidence": 0.8,
                    "observationCount": 2,
                    "observations": [
                        {"timestampSeconds": 0.0, "confidence": 0.8, "box": {"x1": 0.16, "y1": 0.42, "x2": 0.26, "y2": 0.86}},
                        {"timestampSeconds": 0.3, "confidence": 0.79, "box": {"x1": 0.18, "y1": 0.42, "x2": 0.28, "y2": 0.86}},
                    ],
                },
                {
                    "trackId": "player-2",
                    "label": "player",
                    "averageConfidence": 0.78,
                    "observationCount": 2,
                    "observations": [
                        {"timestampSeconds": 0.6, "confidence": 0.78, "box": {"x1": 0.62, "y1": 0.42, "x2": 0.72, "y2": 0.86}},
                        {"timestampSeconds": 0.9, "confidence": 0.79, "box": {"x1": 0.74, "y1": 0.42, "x2": 0.84, "y2": 0.86}},
                    ],
                },
            ],
        }
        action = _make_action(
            canonical_label="steal",
            confidence=0.56,
            top_labels=[("steal", 0.56), ("fast break", 0.41), ("miss", 0.18)],
        )
        signals = derive_structured_signals(candidate_metadata={"perception": turnover_track}, action=action)
        decision = derive_structured_decision(signals=signals, action=action)

        self.assertEqual(decision.eventFamily, "turnover")
        self.assertEqual(decision.canonicalLabel, "steal")
        self.assertEqual(decision.displayLabel, "Steal")
        self.assertTrue(decision.isUncertain)


if __name__ == "__main__":
    unittest.main()
