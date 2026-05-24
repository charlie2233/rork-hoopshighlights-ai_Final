import unittest
from pathlib import Path


class MainWorkflowCodecheckTriggerTests(unittest.TestCase):
    def test_cloud_deploy_workflow_runs_codechecks_on_every_main_push(self) -> None:
        text = workflow_text("cloud-edit-deploy-preflight.yml")

        assert_contains_all(
            self,
            text,
            [
                "push:",
                "branches:",
                "- main",
                "pull_request:",
                "Editing backend Python tests",
                "PYTHONPATH=ios/backend:services/editing python -m unittest discover ios/backend/tests -v",
                "PYTHONPATH=ios/backend:services/editing python -m unittest discover services/editing/tests -v",
                "python -m unittest discover -s scripts -p 'test_*.py' -v",
            ],
        )
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.operation != 'codecheck'", text)
        self.assertNotIn("paths:", text)

    def test_ios_upload_workflow_runs_unsigned_codecheck_on_every_main_push(self) -> None:
        text = workflow_text("ios-testflight-upload.yml")

        assert_contains_all(
            self,
            text,
            [
                "push:",
                "branches:",
                "- main",
                "pull_request:",
                "github.event_name == 'push'",
                "CODE_SIGNING_ALLOWED=NO",
            ],
        )
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.operation != 'codecheck'", text)
        self.assertNotIn("paths:", text)


def workflow_text(name: str) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / ".github" / "workflows" / name).read_text(encoding="utf-8")


def assert_contains_all(test_case: unittest.TestCase, text: str, needles: list[str]) -> None:
    for needle in needles:
        test_case.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
