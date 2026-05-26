import unittest
from pathlib import Path

from scripts.launch_backend_config_preflight import (
    REQUIRED_GPT_RERANK_SUBSTITUTIONS,
    has_failures,
    run_checks,
    strip_jsonc_comments,
    summarize,
)
from services.editing.scripts.deploy_preflight import REQUIRED_GCP_SECRETS


class LaunchBackendConfigPreflightTests(unittest.TestCase):
    def test_current_repo_has_no_static_failures(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        findings = run_checks(repo_root)

        self.assertFalse(has_failures(findings), "\n".join(f"{item.check}: {item.detail}" for item in findings if item.status == "fail"))
        summary = summarize(findings)
        self.assertGreater(summary["pass"], 0)
        self.assertGreater(summary["warn"], 0)
        warning_details = "\n".join(item.detail for item in findings if item.status == "warn")
        self.assertIn("production", warning_details.lower())
        self.assertIn("Statsig", warning_details)

    def test_jsonc_comment_stripper_preserves_url_strings(self) -> None:
        source = '''
        {
          // comment before URL
          "endpoint": "https://example.com/path//still-string",
          "value": 1 /* block comment */
        }
        '''

        cleaned = strip_jsonc_comments(source)

        self.assertIn('"https://example.com/path//still-string"', cleaned)
        self.assertNotIn("comment before URL", cleaned)
        self.assertNotIn("block comment", cleaned)

    def test_quality_beta_uses_full_shot_tracker_keyframe_default(self) -> None:
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_AI_CLIP_GPT_EDITOR_ENABLED"], "true")
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_AI_CLIP_GPT_PLAN_EDIT_ENABLED"], "true")
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_AI_CLIP_GPT_REVISION_ENABLED"], "true")
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_AI_CLIP_GPT_KEYFRAMES_PER_CLIP"], "10")
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_AI_CLIP_GPT_MAX_CANDIDATES_FREE"], "30")
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_AI_CLIP_GPT_TIMEOUT_SECONDS"], "45")
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_AI_CLIP_GPT_MAX_OUTPUT_TOKENS"], "6000")
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_GPT_HIGHLIGHT_RERANKER_ENABLED"], "true")
        self.assertIn("HOOPS_OPENAI_API_KEY", REQUIRED_GCP_SECRETS)


if __name__ == "__main__":
    unittest.main()
