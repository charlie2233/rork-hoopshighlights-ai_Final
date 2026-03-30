from __future__ import annotations

import unittest

from services.inference.app.teacher import _parse_teacher_response, build_teacher_annotation_record


class TeacherLabelerTests(unittest.TestCase):
    def test_parse_teacher_response_extracts_embedded_json(self) -> None:
        payload = _parse_teacher_response(
            "Here is the audit:\n"
            '{"eventFamily":"shot_attempt","outcome":"missed","shotSubtype":"jumper","displayLabelSuggestion":"Highlight","confidence":0.62,"notes":"Clear release, no make."}'
        )

        self.assertEqual(payload["eventFamily"], "shot_attempt")
        self.assertEqual(payload["outcome"], "missed")
        self.assertEqual(payload["shotSubtype"], "jumper")

    def test_parse_teacher_response_falls_back_to_notes(self) -> None:
        payload = _parse_teacher_response("unclear clip, likely transition but not enough context")

        self.assertEqual(payload["notes"], "unclear clip, likely transition but not enough context")

    def test_parse_teacher_response_handles_fenced_json(self) -> None:
        payload = _parse_teacher_response(
            "```json\n"
            '{"eventFamily":"turnover","outcome":"uncertain","shotSubtype":null,"displayLabelSuggestion":"Steal","teacherConfidence":0.74,"notes":"Live-ball turnover."}'
            "\n```"
        )

        self.assertEqual(payload["eventFamily"], "turnover")
        self.assertEqual(payload["displayLabelSuggestion"], "Steal")
        self.assertEqual(payload["teacherConfidence"], 0.74)

    def test_build_teacher_annotation_record_separates_teacher_outputs(self) -> None:
        teacher_output = {
            "eventFamily": "shot_attempt",
            "outcome": "missed",
            "shotSubtype": "jumper",
            "displayLabelSuggestion": "Highlight",
            "teacherConfidence": 0.73,
            "notes": "Open jumper rimmed out.",
            "evidence": {
                "structuredSignals": {
                    "ballNearRim": 0.82,
                    "ballThroughHoopLikelihood": 0.11,
                    "possessionChangeLikelihood": 0.04,
                    "transitionSpeedScore": 0.02,
                },
                "perceptionSummary": {
                    "ballVisible": True,
                    "hoopVisible": True,
                },
            },
        }

        record = build_teacher_annotation_record(
            clip_id="clip-123",
            source_domain="teacher_audit",
            teacher_output=teacher_output,
            runtime_outputs={"label": "miss", "confidence": 0.61},
            human_verified=False,
        ).as_dict()

        self.assertEqual(record["clipId"], "clip-123")
        self.assertEqual(record["sourceDomain"], "teacher_audit")
        self.assertEqual(record["teacherConfidence"], 0.73)
        self.assertTrue(record["ballVisible"])
        self.assertTrue(record["hoopVisible"])
        self.assertEqual(record["eventFamily"], "shot_attempt")
        self.assertEqual(record["outcome"], "missed")
        self.assertEqual(record["shotSubtype"], "jumper")
        self.assertEqual(record["rawRuntimeOutputs"]["label"], "miss")
        self.assertEqual(record["rawTeacherOutputs"]["displayLabelSuggestion"], "Highlight")


if __name__ == "__main__":
    unittest.main()
