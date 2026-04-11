from __future__ import annotations

import unittest

from services.inference.scripts.run_phase4h_family_gate_replay import (
    build_accepted_debug_rows,
    recommend_config,
    run_sweeps,
)


class Phase4hFamilyGateReplayTests(unittest.TestCase):
    def test_debug_rows_add_explicit_reason_and_relaxed_comparator(self) -> None:
        clips = [
            {
                "clipId": "clip-accepted-gate-closed",
                "jobId": "job-1",
                "requestId": "request-1",
                "uploadTraceId": "upload-1",
                "inferenceAttemptId": "attempt-1",
                "eventFamily": "other",
                "outcome": "uncertain",
                "shotSubtype": None,
                "expectedEventFamily": "shot_attempt",
                "expectedOutcome": "made",
                "expectedShotSubtype": "dunk",
                "proposalAccepted": True,
                "proposalScore": 0.8726,
                "familyGateOpen": False,
                "shotHeadInvoked": False,
            }
        ]
        raw_by_clip = {
            "clip-accepted-gate-closed": {
                "runtimeFusionTemporalShadow": {
                    "temporal_student_event_spotter_family": "shot_attempt",
                    "temporal_event_detector_family_distribution": {
                        "shot_attempt": 0.4706,
                        "turnover": 0.0019,
                        "defensive_event": 0.0002,
                        "transition": 0.5264,
                        "other": 0.001,
                    },
                }
            }
        }

        rows = build_accepted_debug_rows(clips, raw_by_clip)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["explicitGateClosureReason"], "accepted_but_family_margin_low_and_spotter_disagrees")
        self.assertEqual(rows[0]["shadowForcedFamilyEval"]["family"], "transition")
        self.assertFalse(rows[0]["shadowForcedFamilyEval"]["shotHeadWouldInvoke"])
        self.assertEqual(rows[0]["shadowRelaxedFamilyEval"]["family"], "shot_attempt")
        self.assertTrue(rows[0]["shadowRelaxedFamilyEval"]["shotHeadWouldInvoke"])

    def test_sweep_finds_spotter_rescue_config_without_false_event_open(self) -> None:
        clips = [
            {
                "clipId": "clip-accepted-shot",
                "eventFamily": "other",
                "expectedEventFamily": "shot_attempt",
                "expectedOutcome": "made",
                "proposalAccepted": True,
                "proposalScore": 0.8726,
                "familyGateOpen": False,
                "shotHeadInvoked": False,
            },
            {
                "clipId": "clip-rejected-other",
                "eventFamily": "other",
                "expectedEventFamily": "other",
                "expectedOutcome": "uncertain",
                "proposalAccepted": False,
                "proposalScore": 0.08,
                "familyGateOpen": False,
                "shotHeadInvoked": False,
            },
        ]
        raw_by_clip = {
            "clip-accepted-shot": {
                "runtimeFusionTemporalShadow": {
                    "temporal_student_event_spotter_family": "shot_attempt",
                    "temporal_event_detector_family_distribution": {
                        "shot_attempt": 0.4706,
                        "turnover": 0.0019,
                        "defensive_event": 0.0002,
                        "transition": 0.5264,
                        "other": 0.001,
                    },
                }
            },
            "clip-rejected-other": {
                "runtimeFusionTemporalShadow": {
                    "temporal_student_event_spotter_family": "other",
                    "temporal_event_detector_family_distribution": {
                        "shot_attempt": 0.02,
                        "turnover": 0.01,
                        "defensive_event": 0.01,
                        "transition": 0.02,
                        "other": 0.94,
                    },
                }
            },
        }

        rows = run_sweeps(clips, raw_by_clip)
        recommended = recommend_config(rows)

        self.assertIsNotNone(recommended)
        assert recommended is not None
        self.assertTrue(recommended["acceptedImpliesFamilyEval"])
        self.assertTrue(recommended["spotterRescue"])
        self.assertEqual(recommended["familyGateOpenCount"], 1)
        self.assertEqual(recommended["shotHeadInvocationCount"], 1)
        self.assertEqual(recommended["falseEventOpenCount"], 0)


if __name__ == "__main__":
    unittest.main()
