import json
import tempfile
import unittest
from pathlib import Path

from scripts.apply_team_highlight_manual_labels import apply_manual_labels


class ApplyTeamHighlightManualLabelsTests(unittest.TestCase):
    def test_dry_run_validates_downloaded_labels_without_overwriting_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-label-apply-") as temp_dir:
            root = Path(temp_dir)
            analysis_path = root / "analysis.json"
            labels_path = root / "labels.json"
            downloads_dir = root / "downloads"
            downloads_dir.mkdir()
            write_json(analysis_path, {"results": {"clips": []}})
            write_json(labels_path, label_payload(needs_label=True))
            write_json(downloads_dir / "case_a_manual_labels.json", label_payload(needs_label=False))

            report = apply_manual_labels(
                manifest={"cases": [{"caseId": "case_a", "analysisResult": "analysis.json", "labels": "labels.json"}]},
                manifest_dir=root,
                downloads_dir=downloads_dir,
                explicit_sources={},
                apply=False,
                allow_incomplete=False,
            )

            target_after_dry_run = json.loads(labels_path.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["mode"], "dry_run")
        self.assertEqual(report["completeClipCount"], 1)
        self.assertFalse(report["cases"][0]["applied"])
        self.assertTrue(target_after_dry_run["clips"][0]["needsLabel"])

    def test_apply_overwrites_target_after_validation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-label-apply-") as temp_dir:
            root = Path(temp_dir)
            analysis_path = root / "analysis.json"
            labels_path = root / "labels.json"
            downloads_dir = root / "downloads"
            downloads_dir.mkdir()
            write_json(analysis_path, {"results": {"clips": []}})
            write_json(labels_path, label_payload(needs_label=True))
            write_json(downloads_dir / "case_a_manual_labels.json", label_payload(needs_label=False))

            report = apply_manual_labels(
                manifest={"cases": [{"caseId": "case_a", "analysisResult": "analysis.json", "labels": "labels.json"}]},
                manifest_dir=root,
                downloads_dir=downloads_dir,
                explicit_sources={},
                apply=True,
                allow_incomplete=False,
            )
            target_after_apply = json.loads(labels_path.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["mode"], "apply")
        self.assertTrue(report["cases"][0]["applied"])
        self.assertFalse(target_after_apply["clips"][0]["needsLabel"])

    def test_apply_accepts_single_review_page_bundle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-label-bundle-") as temp_dir:
            root = Path(temp_dir)
            analysis_path = root / "analysis.json"
            labels_path = root / "labels.json"
            bundle_path = root / "team_highlight_manual_labels_bundle.json"
            write_json(analysis_path, {"results": {"clips": []}})
            write_json(labels_path, label_payload(needs_label=True))
            write_json(
                bundle_path,
                {
                    "schemaVersion": "team-highlight-manual-label-bundle-v1",
                    "source": "team_highlight_label_review_page",
                    "cases": [label_payload(needs_label=False)],
                },
            )

            report = apply_manual_labels(
                manifest={"cases": [{"caseId": "case_a", "analysisResult": "analysis.json", "labels": "labels.json"}]},
                manifest_dir=root,
                downloads_dir=root / "downloads",
                explicit_sources={},
                bundle_path=bundle_path,
                apply=True,
                allow_incomplete=False,
            )
            target_after_apply = json.loads(labels_path.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["cases"][0]["applied"])
        self.assertEqual(report["cases"][0]["sourcePath"], str(bundle_path))
        self.assertFalse(target_after_apply["clips"][0]["needsLabel"])

    def test_blocks_incomplete_downloaded_labels_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-label-apply-") as temp_dir:
            root = Path(temp_dir)
            analysis_path = root / "analysis.json"
            labels_path = root / "labels.json"
            downloads_dir = root / "downloads"
            downloads_dir.mkdir()
            write_json(analysis_path, {"results": {"clips": []}})
            write_json(labels_path, label_payload(needs_label=True))
            incomplete = label_payload(needs_label=False)
            incomplete["clips"][0]["expected"]["outcome"] = None
            write_json(downloads_dir / "case_a_manual_labels.json", incomplete)

            report = apply_manual_labels(
                manifest={"cases": [{"caseId": "case_a", "analysisResult": "analysis.json", "labels": "labels.json"}]},
                manifest_dir=root,
                downloads_dir=downloads_dir,
                explicit_sources={},
                apply=True,
                allow_incomplete=False,
            )

        self.assertEqual(report["status"], "blocked")
        self.assertIn("incomplete", report["cases"][0]["errors"][0])

    def test_rejects_mismatched_label_identity_and_forbidden_url_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-label-apply-") as temp_dir:
            root = Path(temp_dir)
            analysis_path = root / "analysis.json"
            labels_path = root / "labels.json"
            downloads_dir = root / "downloads"
            downloads_dir.mkdir()
            write_json(analysis_path, {"results": {"clips": []}})
            write_json(labels_path, label_payload(needs_label=True))
            mismatched = label_payload(needs_label=False)
            mismatched["clips"][0]["predictionClipId"] = "clip_wrong"
            write_json(downloads_dir / "case_a_manual_labels.json", mismatched)

            mismatch_report = apply_manual_labels(
                manifest={"cases": [{"caseId": "case_a", "analysisResult": "analysis.json", "labels": "labels.json"}]},
                manifest_dir=root,
                downloads_dir=downloads_dir,
                explicit_sources={},
                apply=False,
                allow_incomplete=False,
            )

            leaked = label_payload(needs_label=False)
            leaked["sourceUrl"] = "https://r2.example.test/source?X-Amz-Signature=secret"
            write_json(downloads_dir / "case_a_manual_labels.json", leaked)
            leak_report = apply_manual_labels(
                manifest={"cases": [{"caseId": "case_a", "analysisResult": "analysis.json", "labels": "labels.json"}]},
                manifest_dir=root,
                downloads_dir=downloads_dir,
                explicit_sources={},
                apply=False,
                allow_incomplete=False,
            )

        self.assertEqual(mismatch_report["status"], "blocked")
        self.assertIn("predictionClipId mismatch", mismatch_report["cases"][0]["errors"][0])
        self.assertEqual(leak_report["status"], "blocked")
        self.assertIn("forbidden URL/object-key fields", leak_report["cases"][0]["errors"][0])


def label_payload(*, needs_label: bool) -> dict:
    return {
        "caseId": "case_a",
        "clips": [
            {
                "labelId": "label_001",
                "predictionClipId": "clip_001",
                "needsLabel": needs_label,
                "expected": {
                    "teamId": "team_black",
                    "isHighlight": True,
                    "eventType": "made_shot",
                    "outcome": "made",
                },
            }
        ],
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
