from __future__ import annotations

import unittest

from services.inference.app.teacher import _parse_teacher_response


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


if __name__ == "__main__":
    unittest.main()
