import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_team_highlight_accuracy import AccuracyThresholds, evaluate_accuracy


class TeamHighlightAccuracyEvalTests(unittest.TestCase):
    def test_selected_team_eval_counts_uncertain_review_and_defensive_events(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_three"},
                        "prediction": {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.94}},
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "block"},
                        "prediction": {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.91}},
                    },
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "steal"},
                        "prediction": {
                            "keep": True,
                            "includeForReview": True,
                            "teamAttributionStatus": "uncertain",
                            "teamAttribution": {"teamId": "team_dark", "confidence": 0.7},
                        },
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
        self.assertEqual(report.metrics.selectedTeamRecallWithUncertain, 1.0)
        self.assertEqual(report.metrics.highlightPrecision, 1.0)
        self.assertEqual(report.metrics.highlightRecall, 1.0)
        self.assertEqual(report.metrics.defensiveEventRecall, 1.0)
        self.assertEqual(report.metrics.uncertainReviewCount, 1)

    def test_confident_opponent_attributed_to_selected_team_fails_precision(self) -> None:
        report = evaluate_accuracy(
            {
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_three"},
                        "prediction": {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.92}},
                    },
                    {
                        "expected": {"teamId": "team_light", "isHighlight": True, "eventType": "layup"},
                        "prediction": {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.91}},
                    },
                ],
            },
            thresholds=AccuracyThresholds(defensiveEventRecall=0.0),
        )

        self.assertEqual(report.status, "fail")
        self.assertLess(report.metrics.selectedTeamPrecision, 0.85)
        self.assertTrue(any("selectedTeamPrecision" in failure for failure in report.failures))

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
                    "prediction": {"keep": True, "teamAttribution": {"teamId": "team_dark", "confidence": 0.95}},
                }
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


if __name__ == "__main__":
    unittest.main()
