import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_team_highlight_accuracy import AccuracyThresholds, evaluate_accuracy


def timed_prediction(prediction: dict, start: float = 10.0, end: float = 14.0, event_center: float = 12.0) -> dict:
    return {
        **prediction,
        "start": start,
        "end": end,
        "eventCenter": event_center,
    }


def team_attribution(
    confidence: float,
    team_id: str = "team_dark",
    refs: list[str] | None = None,
    role_groups: list[str] | None = None,
) -> dict:
    return {
        "teamId": team_id,
        "confidence": confidence,
        "evidenceFrameRefs": refs or ["clip_0_release", "clip_0_result"],
        "evidenceRoleGroups": role_groups or ["action", "outcome"],
    }


def made_shot_evidence() -> dict:
    return {
        "outcome": "made",
        "qualitySignals": {"ballPathVisible": True, "rimResultVisible": True},
        "shotResultEvidence": {
            "releaseToRimContinuity": "continuous",
            "rimResultEvidence": "made_visible",
            "outcomeConfidence": 0.9,
            "rimEntrySequence": "visible_entry",
            "ballApproachFrameRole": "rimApproach",
            "rimEntryFrameRole": "rimEntry",
            "ballBelowRimOrNetFrameRole": "belowRim",
            "rimEntrySequenceConfidence": 0.9,
        },
        "shotTrackingEvidence": {
            "ballVisibleFrameRoles": ["release", "rimApproach", "rimEntry", "belowRim"],
            "rimVisibleFrameRoles": ["rimApproach", "rimEntry", "belowRim"],
            "resultFrameRole": "rimEntry",
            "ballEntersRimFrameRole": "rimEntry",
            "trajectoryContinuity": "continuous",
        },
    }


def blocked_shot_evidence() -> dict:
    return {
        "outcome": "blocked",
        "qualitySignals": {"ballPathVisible": True, "rimResultVisible": True},
        "shotResultEvidence": {
            "releaseToRimContinuity": "partial",
            "rimResultEvidence": "blocked",
            "outcomeConfidence": 0.88,
            "rimEntrySequence": "blocked",
            "ballApproachFrameRole": None,
            "rimEntryFrameRole": None,
            "ballBelowRimOrNetFrameRole": None,
            "rimEntrySequenceConfidence": 0.88,
        },
        "shotTrackingEvidence": {
            "ballVisibleFrameRoles": ["challenge", "defenseOutcome"],
            "rimVisibleFrameRoles": [],
            "resultFrameRole": "defenseOutcome",
            "ballEntersRimFrameRole": None,
        },
    }


def weak_made_shot_evidence() -> dict:
    return {
        "outcome": "made",
        "qualitySignals": {"ballPathVisible": False, "rimResultVisible": False},
        "shotResultEvidence": {
            "rimResultEvidence": "unclear",
            "outcomeConfidence": 0.4,
            "rimEntrySequence": "unclear",
        },
        "shotTrackingEvidence": {
            "ballVisibleFrameRoles": [],
            "rimVisibleFrameRoles": [],
        },
    }


class TeamHighlightAccuracyEvalTests(unittest.TestCase):
    def test_selected_team_eval_counts_uncertain_review_and_defensive_events(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_three"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": team_attribution(0.94),
                                **made_shot_evidence(),
                            }
                        ),
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "block"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": team_attribution(0.91),
                                **blocked_shot_evidence(),
                            },
                            start=20.0,
                            end=23.0,
                            event_center=21.2,
                        ),
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "steal"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "includeForReview": True,
                                "teamAttributionStatus": "uncertain",
                                "teamAttribution": {"teamId": "team_dark", "confidence": 0.7},
                            },
                            start=30.0,
                            end=33.0,
                            event_center=31.3,
                        ),
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "forced turnover"},
                        "prediction": timed_prediction(
                            {"keep": True, "teamAttribution": team_attribution(0.9)},
                            start=40.0,
                            end=43.2,
                            event_center=41.4,
                        ),
                    },
                    {
                        "expected": {"teamId": "team_light", "isHighlight": True, "eventType": "layup"},
                        "prediction": {"keep": False, "teamAttribution": {"teamId": "team_light", "confidence": 0.95}},
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": False, "eventType": "dead_ball"},
                        "prediction": {"keep": False, "teamAttribution": {"teamId": "team_dark", "confidence": 0.9}},
                    },
                ],
            }
        )

        self.assertEqual(report.status, "pass")
        self.assertEqual(report.metrics.selectedTeamPrecision, 1.0)
        self.assertEqual(report.metrics.selectedTeamEvidenceQuality, 1.0)
        self.assertEqual(report.metrics.selectedTeamRecallWithUncertain, 1.0)
        self.assertEqual(report.metrics.highlightPrecision, 1.0)
        self.assertEqual(report.metrics.highlightRecall, 1.0)
        self.assertEqual(report.metrics.defensiveEventRecall, 1.0)
        self.assertEqual(report.metrics.clipTimingQuality, 1.0)
        self.assertEqual(report.metrics.shotOutcomeEvidenceQuality, 1.0)
        self.assertEqual(report.metrics.defensiveEventCount, 3)
        self.assertEqual(report.metrics.shotOutcomeEvidenceClipCount, 2)
        self.assertEqual(report.metrics.selectedTeamBlockCount, 1)
        self.assertEqual(report.metrics.selectedTeamStealCount, 1)
        self.assertEqual(report.metrics.selectedTeamEvidenceClipCount, 3)
        self.assertEqual(report.metrics.badSelectedTeamEvidenceCount, 0)
        self.assertEqual(report.metrics.uncertainReviewCount, 1)

    def test_eval_without_selected_team_defensive_coverage_cannot_pass_readiness(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_three"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": {"teamId": "team_dark", "confidence": 0.94},
                                **made_shot_evidence(),
                            }
                        ),
                    }
                ],
            }
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.metrics.defensiveEventCount, 0)
        self.assertTrue(any("selectedTeamDefensiveEventCoverage" in failure for failure in report.failures))

    def test_uncertain_review_without_auto_keep_counts_for_selected_team_recall(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "steal"},
                        "prediction": timed_prediction(
                            {
                                "keep": False,
                                "includeForReview": True,
                                "teamAttributionStatus": "uncertain",
                                "teamAttribution": {"teamId": "team_dark", "confidence": 0.64},
                            },
                            start=30.0,
                            end=33.2,
                            event_center=31.4,
                        ),
                    }
                ],
            },
            thresholds=AccuracyThresholds(
                selectedTeamPrecision=0.0,
                selectedTeamRecallWithUncertain=1.0,
                highlightPrecision=0.0,
                highlightRecall=0.0,
                defensiveEventRecall=1.0,
                clipTimingQuality=1.0,
                shotOutcomeEvidenceQuality=0.0,
                minSelectedTeamDefensiveEvents=1,
                minSelectedTeamBlocks=0,
                minSelectedTeamSteals=1,
            ),
        )

        self.assertEqual(report.status, "pass")
        self.assertEqual(report.metrics.selectedTeamRecallWithUncertain, 1.0)
        self.assertEqual(report.metrics.selectedTeamEvidenceQuality, 1.0)
        self.assertEqual(report.metrics.defensiveEventRecall, 1.0)
        self.assertEqual(report.metrics.uncertainReviewCount, 1)

    def test_eval_with_block_but_no_steal_cannot_pass_readiness(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "block"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": {"teamId": "team_dark", "confidence": 0.91},
                                **blocked_shot_evidence(),
                            },
                            start=20.0,
                            end=23.0,
                            event_center=21.2,
                        ),
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "forced turnover"},
                        "prediction": timed_prediction(
                            {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.9}},
                            start=40.0,
                            end=43.2,
                            event_center=41.4,
                        ),
                    },
                ],
            }
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.metrics.defensiveEventCount, 2)
        self.assertEqual(report.metrics.selectedTeamBlockCount, 1)
        self.assertEqual(report.metrics.selectedTeamStealCount, 0)
        self.assertTrue(any("selectedTeamStealCoverage" in failure for failure in report.failures))

    def test_made_shot_without_visible_rim_entry_evidence_fails_outcome_quality(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_three"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": {"teamId": "team_dark", "confidence": 0.94},
                                **weak_made_shot_evidence(),
                            }
                        ),
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "block"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": {"teamId": "team_dark", "confidence": 0.91},
                                **blocked_shot_evidence(),
                            },
                            start=20.0,
                            end=23.0,
                            event_center=21.2,
                        ),
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "steal"},
                        "prediction": timed_prediction(
                            {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.91}},
                            start=30.0,
                            end=33.0,
                            event_center=31.3,
                        ),
                    },
                ],
            }
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.metrics.shotOutcomeEvidenceClipCount, 2)
        self.assertEqual(report.metrics.badShotOutcomeEvidenceCount, 1)
        self.assertTrue(any("shotOutcomeEvidenceQuality" in failure for failure in report.failures))

    def test_label_only_made_shot_evidence_fails_outcome_quality(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_three"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": {"teamId": "team_dark", "confidence": 0.94},
                                "outcomeEvidenceSource": "label_only",
                                **made_shot_evidence(),
                            }
                        ),
                    }
                ],
            },
            thresholds=AccuracyThresholds(
                selectedTeamPrecision=0.0,
                selectedTeamRecallWithUncertain=0.0,
                highlightPrecision=0.0,
                highlightRecall=0.0,
                defensiveEventRecall=0.0,
                clipTimingQuality=0.0,
                shotOutcomeEvidenceQuality=0.85,
                minSelectedTeamDefensiveEvents=0,
                minSelectedTeamBlocks=0,
                minSelectedTeamSteals=0,
            ),
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.metrics.shotOutcomeEvidenceClipCount, 1)
        self.assertEqual(report.metrics.badShotOutcomeEvidenceCount, 1)
        self.assertTrue(any("shotOutcomeEvidenceQuality" in failure for failure in report.failures))

    def test_made_shot_low_rim_entry_sequence_confidence_fails_outcome_quality(self) -> None:
        weak_entry = made_shot_evidence()
        weak_entry["shotResultEvidence"] = {
            **weak_entry["shotResultEvidence"],
            "rimEntrySequenceConfidence": 0.4,
        }

        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_three"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": {"teamId": "team_dark", "confidence": 0.94},
                                **weak_entry,
                            }
                        ),
                    }
                ],
            },
            thresholds=AccuracyThresholds(
                selectedTeamPrecision=0.0,
                selectedTeamRecallWithUncertain=0.0,
                highlightPrecision=0.0,
                highlightRecall=0.0,
                defensiveEventRecall=0.0,
                clipTimingQuality=0.0,
                shotOutcomeEvidenceQuality=0.85,
                minSelectedTeamDefensiveEvents=0,
                minSelectedTeamBlocks=0,
                minSelectedTeamSteals=0,
            ),
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.metrics.shotOutcomeEvidenceClipCount, 1)
        self.assertEqual(report.metrics.badShotOutcomeEvidenceCount, 1)
        self.assertTrue(any("shotOutcomeEvidenceQuality" in failure for failure in report.failures))

    def test_defensive_event_recall_normalizes_forced_turnover_labels(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "forced-turnover"},
                        "prediction": timed_prediction(
                            {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.94}},
                            start=10.0,
                            end=13.0,
                            event_center=11.2,
                        ),
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "turnover_forced"},
                        "prediction": {"keep": False, "teamAttribution": {"teamId": "team_dark", "confidence": 0.93}},
                    },
                ],
            },
            thresholds=AccuracyThresholds(
                highlightRecall=0.0,
                selectedTeamRecallWithUncertain=0.0,
                defensiveEventRecall=0.85,
            ),
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.metrics.defensiveEventCount, 2)
        self.assertEqual(report.metrics.defensiveEventRecall, 0.5)
        self.assertTrue(any("defensiveEventRecall" in failure for failure in report.failures))

    def test_confident_opponent_attributed_to_selected_team_fails_precision(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_three"},
                        "prediction": timed_prediction({"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.92}}),
                    },
                    {
                        "expected": {"teamId": "team_light", "isHighlight": True, "eventType": "layup"},
                        "prediction": timed_prediction(
                            {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.91}},
                            start=20.0,
                            end=24.0,
                            event_center=22.0,
                        ),
                    },
                ],
            },
            thresholds=AccuracyThresholds(defensiveEventRecall=0.0),
        )

        self.assertEqual(report.status, "fail")
        self.assertLess(report.metrics.selectedTeamPrecision, 0.85)
        self.assertTrue(any("selectedTeamPrecision" in failure for failure in report.failures))

    def test_confident_selected_team_without_frame_refs_fails_evidence_quality(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "steal"},
                        "prediction": timed_prediction(
                            {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.94}},
                            start=18.0,
                            end=21.4,
                            event_center=19.3,
                        ),
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "block"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": team_attribution(0.95),
                                **blocked_shot_evidence(),
                            },
                            start=28.0,
                            end=31.2,
                            event_center=29.2,
                        ),
                    },
                ],
            },
            thresholds=AccuracyThresholds(
                selectedTeamPrecision=0.0,
                selectedTeamEvidenceQuality=0.85,
                selectedTeamRecallWithUncertain=0.0,
                highlightPrecision=0.0,
                highlightRecall=0.0,
                defensiveEventRecall=0.0,
                clipTimingQuality=0.0,
                shotOutcomeEvidenceQuality=0.0,
                minSelectedTeamDefensiveEvents=0,
                minSelectedTeamBlocks=0,
                minSelectedTeamSteals=0,
            ),
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.metrics.selectedTeamEvidenceClipCount, 2)
        self.assertEqual(report.metrics.badSelectedTeamEvidenceCount, 1)
        self.assertEqual(report.metrics.selectedTeamEvidenceQuality, 0.5)
        self.assertTrue(any("selectedTeamEvidenceQuality" in failure for failure in report.failures))

    def test_confident_selected_team_without_role_diversity_fails_evidence_quality(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "steal"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": team_attribution(
                                    0.94,
                                    refs=["clip_0_release", "clip_0_arc"],
                                    role_groups=["action"],
                                ),
                            },
                            start=18.0,
                            end=21.4,
                            event_center=19.3,
                        ),
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "block"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": team_attribution(0.95),
                                **blocked_shot_evidence(),
                            },
                            start=28.0,
                            end=31.2,
                            event_center=29.2,
                        ),
                    },
                ],
            },
            thresholds=AccuracyThresholds(
                selectedTeamPrecision=0.0,
                selectedTeamEvidenceQuality=0.85,
                selectedTeamRecallWithUncertain=0.0,
                highlightPrecision=0.0,
                highlightRecall=0.0,
                defensiveEventRecall=0.0,
                clipTimingQuality=0.0,
                shotOutcomeEvidenceQuality=0.0,
                minSelectedTeamDefensiveEvents=0,
                minSelectedTeamBlocks=0,
                minSelectedTeamSteals=0,
            ),
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.metrics.selectedTeamEvidenceClipCount, 2)
        self.assertEqual(report.metrics.badSelectedTeamEvidenceCount, 1)
        self.assertEqual(report.metrics.selectedTeamEvidenceQuality, 0.5)
        self.assertTrue(any("selectedTeamEvidenceQuality" in failure for failure in report.failures))

    def test_empty_input_fails_instead_of_claiming_accuracy(self) -> None:
        report = evaluate_accuracy({"cases": []})

        self.assertEqual(report.status, "fail")
        self.assertIn("No eval cases found.", report.failures)

    def test_cli_json_output_is_machine_readable(self) -> None:
        payload = {
            "selectedTeamId": "team_dark",
            "clips": [
                {
                    "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "block"},
                    "prediction": timed_prediction(
                        {
                            "keep": True,
                            "teamAttribution": team_attribution(0.95),
                            **blocked_shot_evidence(),
                        },
                        start=8.0,
                        end=11.0,
                        event_center=9.2,
                    ),
                },
                {
                    "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "steal"},
                    "prediction": timed_prediction(
                        {"keep": True, "teamAttribution": team_attribution(0.95)},
                        start=18.0,
                        end=21.4,
                        event_center=19.3,
                    ),
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "labels.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "scripts.evaluate_team_highlight_accuracy", str(path), "--json"],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["status"], "pass")
        self.assertEqual(parsed["metrics"]["defensiveEventRecall"], 1.0)
        self.assertEqual(parsed["metrics"]["clipTimingQuality"], 1.0)
        self.assertEqual(parsed["metrics"]["shotOutcomeEvidenceQuality"], 1.0)
        self.assertEqual(parsed["metrics"]["selectedTeamEvidenceQuality"], 1.0)

    def test_tiny_or_pre_basket_kept_clip_fails_timing_quality(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_three"},
                        "prediction": timed_prediction(
                            {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.95}},
                            start=10.0,
                            end=10.1,
                            event_center=10.05,
                        ),
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "layup"},
                        "prediction": timed_prediction(
                            {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.95}},
                            start=20.0,
                            end=23.0,
                            event_center=20.2,
                        ),
                    },
                ],
            },
            thresholds=AccuracyThresholds(
                selectedTeamPrecision=0.0,
                selectedTeamRecallWithUncertain=0.0,
                highlightPrecision=0.0,
                highlightRecall=0.0,
                defensiveEventRecall=0.0,
                clipTimingQuality=0.85,
            ),
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.metrics.clipTimingQuality, 0.0)
        self.assertEqual(report.metrics.badTimingClipCount, 2)
        self.assertTrue(any("clipTimingQuality" in failure for failure in report.failures))

    def test_kept_shot_missing_native_timing_window_fails_timing_quality(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "jumper"},
                        "prediction": timed_prediction(
                            {
                                "keep": True,
                                "teamAttribution": {"teamId": "team_dark", "confidence": 0.95},
                                "nativeShotSignals": {"timingWindowOk": False},
                            },
                            start=10.0,
                            end=14.0,
                            event_center=12.0,
                        ),
                    }
                ],
            },
            thresholds=AccuracyThresholds(
                selectedTeamPrecision=0.0,
                selectedTeamRecallWithUncertain=0.0,
                highlightPrecision=0.0,
                highlightRecall=0.0,
                defensiveEventRecall=0.0,
                clipTimingQuality=0.85,
            ),
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.metrics.clipTimingQuality, 0.0)
        self.assertEqual(report.metrics.badTimingClipCount, 1)


if __name__ == "__main__":
    unittest.main()
