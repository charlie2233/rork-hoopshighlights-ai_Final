import unittest
from pathlib import Path

from scripts.launch_backend_config_preflight import (
    REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS,
    REQUIRED_ANALYSIS_TEAM_SCAN_ENV_MAPPINGS,
    REQUIRED_FREE_DAILY_EDIT_CHANCES,
    REQUIRED_GPT_RERANK_ENV_MAPPINGS,
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
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_AI_CLIP_GPT_MAX_CANDIDATES_FREE"], "60")
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_AI_CLIP_GPT_MAX_CANDIDATES_PRO"], "60")
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_AI_CLIP_GPT_TIMEOUT_SECONDS"], "60")
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_AI_CLIP_GPT_MAX_OUTPUT_TOKENS"], "12000")
        self.assertEqual(REQUIRED_GPT_RERANK_SUBSTITUTIONS["_GPT_HIGHLIGHT_RERANKER_ENABLED"], "true")
        self.assertIn("HOOPS_OPENAI_API_KEY", REQUIRED_GCP_SECRETS)

    def test_gpt_reranker_required_flags_cannot_be_weakened(self) -> None:
        self.assertEqual(
            set(REQUIRED_GPT_RERANK_SUBSTITUTIONS),
            {
                "_AI_CLIP_GPT_EDITOR_ENABLED",
                "_AI_CLIP_GPT_PLAN_EDIT_ENABLED",
                "_AI_CLIP_GPT_REVISION_ENABLED",
                "_AI_CLIP_GPT_KEYFRAMES_PER_CLIP",
                "_AI_CLIP_GPT_MAX_CANDIDATES_FREE",
                "_AI_CLIP_GPT_MAX_CANDIDATES_PRO",
                "_AI_CLIP_GPT_TIMEOUT_SECONDS",
                "_AI_CLIP_GPT_MAX_OUTPUT_TOKENS",
                "_GPT_HIGHLIGHT_RERANKER_ENABLED",
            },
        )
        for substitution_key in REQUIRED_GPT_RERANK_SUBSTITUTIONS:
            env_key = "HOOPS" + substitution_key
            self.assertTrue(
                any(mapping == f"{env_key}=${{{substitution_key}}}" for mapping in REQUIRED_GPT_RERANK_ENV_MAPPINGS),
                f"{substitution_key} is not required in Cloud Run env mappings",
            )

    def test_analysis_cloudbuild_requires_team_scan_quality_defaults(self) -> None:
        self.assertEqual(REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS["_MAX_RETURNED_CLIPS"], "60")
        self.assertEqual(REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS["_TEAM_QUICK_SCAN_ENABLED"], "true")
        self.assertEqual(REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS["_TEAM_QUICK_SCAN_CLIP_FRAMES_PER_CLIP"], "8")
        self.assertEqual(REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS["_TEAM_QUICK_SCAN_RICH_CANDIDATE_CLIPS"], "120")
        self.assertEqual(REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS["_TEAM_QUICK_SCAN_MAX_TOTAL_CLIP_FRAMES"], "1200")
        self.assertEqual(REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS["_TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS"], "160")
        self.assertEqual(REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS["_TEAM_QUICK_SCAN_MAX_OUTPUT_TOKENS"], "12000")

    def test_team_scan_required_flags_cannot_be_weakened(self) -> None:
        self.assertEqual(
            set(REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS),
            {
                "_MAX_RETURNED_CLIPS",
                "_TEAM_QUICK_SCAN_ENABLED",
                "_TEAM_QUICK_SCAN_CLIP_FRAMES_PER_CLIP",
                "_TEAM_QUICK_SCAN_RICH_CANDIDATE_CLIPS",
                "_TEAM_QUICK_SCAN_MAX_TOTAL_CLIP_FRAMES",
                "_TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS",
                "_TEAM_QUICK_SCAN_MAX_OUTPUT_TOKENS",
            },
        )
        for substitution_key in REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS:
            env_key = "HOOPS" + substitution_key
            self.assertTrue(
                any(mapping == f"{env_key}=${{{substitution_key}}}" for mapping in REQUIRED_ANALYSIS_TEAM_SCAN_ENV_MAPPINGS),
                f"{substitution_key} is not required in Cloud Run env mappings",
            )

    def test_free_daily_edit_quota_policy_is_three(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        findings = run_checks(repo_root)
        quota_findings = [item for item in findings if "free" in item.check and ("quota" in item.check or "policy" in item.check)]

        self.assertEqual(REQUIRED_FREE_DAILY_EDIT_CHANCES, 3)
        self.assertGreaterEqual(len(quota_findings), 5)
        self.assertFalse(
            any(item.status == "fail" for item in quota_findings),
            "\n".join(f"{item.path}: {item.detail}" for item in quota_findings if item.status == "fail"),
        )


if __name__ == "__main__":
    unittest.main()
