import tempfile
import unittest
from pathlib import Path

from scripts.build_team_highlight_eval_payload import build_eval_payload, main
from scripts.evaluate_team_highlight_accuracy import AccuracyThresholds, evaluate_accuracy
from scripts.make_team_highlight_label_template import build_label_template
from scripts.test_team_highlight_accuracy_eval import defensive_outcome_evidence, made_shot_evidence


def analysis_clip(start: float, end: float, label: str, keep: bool, team_id: str, confidence: float) -> dict:
    evidence_frame_refs = [f"{label.lower().replace(' ', '_')}_setup", f"{label.lower().replace(' ', '_')}_result"]
    evidence_role_groups = ["setup", "outcome"]
    return {
        "startTime": start,
        "endTime": end,
        "eventCenter": round((start + end) / 2.0, 3),
        "label": label,
        "confidence": confidence,
        "audioScore": 0.4,
        "visualScore": 0.8,
        "motionScore": 0.7,
        "combinedScore": 0.82,
        "shouldAutoKeep": keep,
        "shouldEnableSlowMotion": False,
        "teamAttribution": {
            "teamId": team_id,
            "confidence": confidence,
            "evidenceFrameRefs": evidence_frame_refs,
            "evidenceRoleGroups": evidence_role_groups,
        },
        "teamEvidence": {
            "status": "evidence_backed" if confidence >= 0.85 else "weak_evidence",
            "evidenceBacked": confidence >= 0.85,
            "frameRefCount": len(evidence_frame_refs),
            "roleGroupCount": len(evidence_role_groups),
            "requiresEvidence": True,
            "reasons": [] if confidence >= 0.85 else ["low_confidence"],
        },
        "teamAttributionStatus": "matched" if confidence >= 0.85 else "uncertain",
        "nativeShotSignals": {
            "timingWindowOk": True,
            "outcome": "made" if "Shot" in label else "not_shot",
        },
    }


class BuildTeamHighlightEvalPayloadTests(unittest.TestCase):
    def test_build_payload_matches_real_analysis_predictions_and_review_uncertain_clip(self) -> None:
        made = {**analysis_clip(10.0, 14.0, "Made Shot", True, "team_dark", 0.94), **made_shot_evidence()}
        steal = {**analysis_clip(30.0, 33.2, "Steal", False, "team_dark", 0.64), **defensive_outcome_evidence("steal")}
        payload = build_eval_payload(
            analysis={
                "jobId": "job_real_001",
                "teamScanJobId": "scan_real_001",
                "results": {
                    "teamSelection": {"mode": "team", "teamId": "team_dark", "colorLabel": "black"},
                    "detectedTeams": [
                        {"teamId": "team_dark", "label": "Black jerseys", "colorLabel": "black", "confidence": 0.93},
                        {"teamId": "team_light", "label": "White jerseys", "colorLabel": "white", "confidence": 0.91},
                    ],
                    "clips": [made, steal],
                },
            },
            labels={
                "caseId": "real_game_001",
                "videoId": "video_real_001",
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "labelId": "made_001",
                        "start": 10.1,
                        "end": 14.1,
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_three", "outcome": "made"},
                    },
                    {
                        "labelId": "steal_001",
                        "start": 30.1,
                        "end": 33.1,
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "steal"},
                    },
                ],
            },
        )

        report = evaluate_accuracy(
            payload,
            thresholds=AccuracyThresholds(
                minCases=1,
                minScoredClips=2,
                minSelectedTeamHighlights=2,
                minShotOutcomeEvidenceClips=1,
                minMissedShotOutcomeEvidenceClips=0,
                minOpponentHighlights=0,
                minNegativeClips=0,
                minBadWindowNegatives=0,
                minSelectedTeamBlocks=0,
                minSelectedTeamSteals=1,
                minSelectedTeamForcedTurnovers=0,
                minSelectedTeamDefensiveStops=0,
                minSelectedTeamDefensiveEvents=1,
                minAllTeamsCases=0,
            ),
        )

        self.assertEqual(payload["cases"][0]["caseId"], "real_game_001")
        self.assertEqual(payload["cases"][0]["videoId"], "video_real_001")
        self.assertEqual(payload["cases"][0]["analysisJobId"], "job_real_001")
        self.assertEqual(payload["cases"][0]["teamScanJobId"], "scan_real_001")
        self.assertEqual(payload["cases"][0]["teamMode"], "team")
        self.assertEqual(payload["cases"][0]["selectedTeamColorLabel"], "black")
        self.assertEqual(payload["cases"][0]["detectedTeams"][0]["teamId"], "team_dark")
        self.assertEqual(payload["cases"][0]["detectedTeams"][0]["colorLabel"], "black")
        self.assertEqual(payload["cases"][0]["clips"][0]["prediction"]["teamEvidence"]["status"], "evidence_backed")
        self.assertEqual(payload["cases"][0]["clips"][1]["prediction"]["keep"], False)
        self.assertEqual(payload["cases"][0]["clips"][1]["prediction"]["includeForReview"], True)
        self.assertEqual(payload["cases"][0]["clips"][1]["prediction"]["teamEvidence"]["status"], "weak_evidence")
        self.assertEqual(report.status, "pass")
        self.assertEqual(report.evidence.inputSchemaVersion, "team-highlight-eval-v1")
        self.assertEqual(report.evidence.inputSource, "real_cloud_analysis_with_manual_labels")
        self.assertEqual(report.evidence.casesMissingAnalysisJobId, 0)
        self.assertEqual(report.evidence.casesMissingTeamMode, 0)
        self.assertEqual(report.evidence.casesMissingTeamScanJobId, 0)
        self.assertEqual(report.evidence.casesMissingDetectedTeamOptions, 0)
        self.assertEqual(report.evidence.casesMissingSelectedTeamColorLabel, 0)
        self.assertEqual(report.evidence.casesMissingSelectedTeamDetectedOption, 0)
        self.assertEqual(report.metrics.selectedTeamRecallWithUncertain, 1.0)
        self.assertEqual(report.metrics.uncertainReviewCount, 1)

    def test_build_payload_fails_when_analysis_prediction_is_unlabeled(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unlabeled prediction clips"):
            build_eval_payload(
                analysis={"clips": [analysis_clip(10.0, 14.0, "Made Shot", True, "team_dark", 0.94)]},
                labels={"selectedTeamId": "team_dark", "clips": []},
            )

    def test_prediction_index_zero_matches_without_clip_id(self) -> None:
        payload = build_eval_payload(
            analysis={
                "clips": [
                    {**analysis_clip(10.0, 14.0, "Made Shot", True, "team_dark", 0.94), "id": "clip_made_001"},
                ]
            },
            labels={
                "selectedTeamId": "team_dark",
                "clips": [
                    {
                        "labelId": "made_001",
                        "predictionIndex": 0,
                        "start": 10.0,
                        "end": 14.0,
                        "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_shot", "outcome": "made"},
                    }
                ],
            },
        )

        self.assertEqual(payload["cases"][0]["clips"][0]["prediction"]["start"], 10.0)

    def test_prediction_index_rejects_stale_clip_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "not labeled predictionClipId"):
            build_eval_payload(
                analysis={
                    "clips": [
                        {**analysis_clip(10.0, 14.0, "Made Shot", True, "team_dark", 0.94), "id": "clip_new_001"},
                    ]
                },
                labels={
                    "selectedTeamId": "team_dark",
                    "clips": [
                        {
                            "labelId": "made_001",
                            "predictionIndex": 0,
                            "predictionClipId": "clip_old_001",
                            "start": 10.0,
                            "end": 14.0,
                            "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_shot", "outcome": "made"},
                        }
                    ],
                },
            )

    def test_prediction_index_rejects_stale_time_window(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not overlap analysis clip"):
            build_eval_payload(
                analysis={
                    "clips": [
                        {**analysis_clip(10.0, 14.0, "Made Shot", True, "team_dark", 0.94), "id": "clip_made_001"},
                    ]
                },
                labels={
                    "selectedTeamId": "team_dark",
                    "clips": [
                        {
                            "labelId": "made_001",
                            "predictionIndex": 0,
                            "predictionClipId": "clip_made_001",
                            "start": 40.0,
                            "end": 44.0,
                            "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_shot", "outcome": "made"},
                        }
                    ],
                },
            )

    def test_label_template_marks_every_prediction_as_needing_human_labels(self) -> None:
        template = build_label_template(
            analysis={
                "jobId": "job_real_001",
                "results": {
                    "teamSelection": {"mode": "team", "teamId": "team_dark", "colorLabel": "black"},
                    "detectedTeams": [
                        {"teamId": "team_dark", "label": "Black jerseys", "colorLabel": "black", "confidence": 0.93},
                        {"teamId": "team_light", "label": "White jerseys", "colorLabel": "white", "confidence": 0.91},
                    ],
                    "clips": [
                        {**analysis_clip(10.0, 14.0, "Made Shot", True, "team_dark", 0.94), "id": "clip_made_001"},
                        {**analysis_clip(30.0, 33.2, "Steal", False, "team_dark", 0.64), "id": "clip_steal_001"},
                    ],
                },
            },
            case_id="real_game_001",
            video_id="video_real_001",
        )

        self.assertEqual(template["schemaVersion"], "team-highlight-manual-label-template-v1")
        self.assertEqual(template["source"], "real_cloud_analysis_label_template")
        self.assertEqual(template["caseId"], "real_game_001")
        self.assertEqual(template["videoId"], "video_real_001")
        self.assertEqual(template["analysisJobId"], "job_real_001")
        self.assertEqual(template["selectedTeamId"], "team_dark")
        self.assertEqual(template["selectedTeamColorLabel"], "black")
        self.assertEqual(len(template["clips"]), 2)
        self.assertTrue(template["clips"][0]["needsLabel"])
        self.assertEqual(template["clips"][0]["predictionClipId"], "clip_made_001")
        self.assertEqual(template["clips"][0]["predicted"]["teamId"], "team_dark")

    def test_build_payload_rejects_unfilled_label_template_rows(self) -> None:
        labels = build_label_template(
            analysis={"jobId": "job_real_001", "results": {"clips": [{**analysis_clip(10.0, 14.0, "Made Shot", True, "team_dark", 0.94), "id": "clip_made_001"}]}},
            case_id="real_game_001",
            video_id="video_real_001",
            selected_team_id="team_dark",
        )

        with self.assertRaisesRegex(ValueError, "still has needsLabel=true"):
            build_eval_payload(
                analysis={"jobId": "job_real_001", "results": {"clips": [{**analysis_clip(10.0, 14.0, "Made Shot", True, "team_dark", 0.94), "id": "clip_made_001"}]}},
                labels=labels,
            )

        labels["clips"][0]["needsLabel"] = False
        with self.assertRaisesRegex(ValueError, "is incomplete"):
            build_eval_payload(
                analysis={"jobId": "job_real_001", "results": {"clips": [{**analysis_clip(10.0, 14.0, "Made Shot", True, "team_dark", 0.94), "id": "clip_made_001"}]}},
                labels=labels,
            )

        labels["clips"][0]["expected"] = {
            "teamId": "team_dark",
            "isHighlight": True,
            "eventType": "made_shot",
            "outcome": "made",
        }
        payload = build_eval_payload(
            analysis={"jobId": "job_real_001", "results": {"clips": [{**analysis_clip(10.0, 14.0, "Made Shot", True, "team_dark", 0.94), "id": "clip_made_001"}]}},
            labels=labels,
        )

        self.assertEqual(payload["cases"][0]["clips"][0]["expected"]["teamId"], "team_dark")
        self.assertTrue(payload["cases"][0]["clips"][0]["expected"]["isHighlight"])

    def test_cli_writes_payload_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-eval-payload-") as temp_dir:
            temp_path = Path(temp_dir)
            analysis_path = temp_path / "analysis.json"
            labels_path = temp_path / "labels.json"
            output_path = temp_path / "eval.json"
            analysis_path.write_text(
                '{"results":{"teamSelection":{"mode":"team","teamId":"team_dark"},"clips":[]}}',
                encoding="utf-8",
            )
            labels_path.write_text(
                '{"caseId":"empty_case","selectedTeamId":"team_dark","clips":[]}',
                encoding="utf-8",
            )

            import sys

            old_argv = sys.argv
            try:
                sys.argv = [
                    "build_team_highlight_eval_payload.py",
                    "--analysis-result",
                    str(analysis_path),
                    "--labels",
                    str(labels_path),
                    "--output",
                    str(output_path),
                ]
                exit_code = main()
            finally:
                sys.argv = old_argv

            self.assertEqual(exit_code, 0)
            self.assertIn('"schemaVersion": "team-highlight-eval-v1"', output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
