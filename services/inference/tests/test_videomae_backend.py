from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.inference.app.backends.videomae import VideoMAEActionRecognizer
from services.inference.app.interfaces import VideoFeatures
from services.inference.app.models import CandidateWindow


class VideoMAEBackendTests(unittest.TestCase):
    @patch("services.inference.app.backends.videomae._predict_lora_window")
    @patch("services.inference.app.backends.videomae._load_lora_runtime_backend")
    def test_lora_runtime_uses_candidate_window_bounds(
        self,
        mock_load_runtime_backend,
        mock_predict_lora_window,
    ) -> None:
        runtime_bundle = SimpleNamespace(
            runtime_metadata={"frameCount": 8, "modelVersion": "videomae-rslora:test"},
            temperature={"eventFamily": 1.0},
        )
        mock_load_runtime_backend.return_value = (runtime_bundle, "cpu")
        mock_predict_lora_window.return_value = {
            "displayLabel": "Dunk",
            "canonicalLabel": "dunk",
            "confidenceAfterMapping": 0.84,
            "confidenceBeforeMapping": 0.77,
            "eventFamily": "shot_attempt",
            "shotSubtype": "dunk",
            "outcome": "made",
            "isUncertain": False,
            "rawEventFamily": {"confidence": 0.88, "topLabels": [{"label": "shot_attempt", "confidence": 0.88}]},
            "rawOutcome": {"confidence": 0.81, "topLabels": [{"label": "made", "confidence": 0.81}]},
            "rawShotSubtype": {"confidence": 0.79, "topLabels": [{"label": "dunk", "confidence": 0.79}]},
            "rawTopLabels": {
                "eventFamily": [{"label": "shot_attempt", "confidence": 0.88}],
                "outcome": [{"label": "made", "confidence": 0.81}],
                "shotSubtype": [{"label": "dunk", "confidence": 0.79}],
            },
        }
        recognizer = VideoMAEActionRecognizer(
            model_name="videomae-test",
            lora_bundle_path="/tmp/runtime_bundle.json",
        )
        candidate = CandidateWindow(
            candidateId="candidate-1",
            startTime=12.5,
            endTime=17.75,
            score=0.93,
            source="heuristic",
        )
        features = VideoFeatures(
            source_path=Path("/tmp/source.mp4"),
            duration_seconds=30.0,
            fps=30.0,
            frame_count=900,
        )

        result = recognizer.recognize(candidate, features)

        mock_predict_lora_window.assert_called_once()
        self.assertEqual(mock_predict_lora_window.call_args.kwargs["start_seconds"], 12.5)
        self.assertEqual(mock_predict_lora_window.call_args.kwargs["end_seconds"], 17.75)
        self.assertEqual(result.label, "Dunk")
        self.assertEqual(result.shotSubtype, "dunk")
        self.assertEqual(result.modelVersion, "videomae-rslora:test")


if __name__ == "__main__":
    unittest.main()
