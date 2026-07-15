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
        self.assertIn("if: github.event_name != 'workflow_dispatch' || inputs.operation != 'credential-check'", text)
        self.assertIn(
            "if: github.event_name == 'workflow_dispatch' && inputs.operation != 'codecheck' && inputs.operation != 'credential-check'",
            text,
        )
        self.assertNotIn("paths:", text)

    def test_cloud_deploy_workflow_has_credential_only_dispatch(self) -> None:
        text = workflow_text("cloud-edit-deploy-preflight.yml")

        assert_contains_all(
            self,
            text,
            [
                "- credential-check",
                "deploy-credential-check:",
                "Verify cloud deploy credentials only",
                "if: github.event_name == 'workflow_dispatch' && inputs.operation == 'credential-check'",
                "npm --prefix services/control-plane ci",
                "services/editing/scripts/deploy_preflight.py",
                "credential-only deploy preflight succeeded",
                "GitHub Actions staging credential check:",
                "-f operation=credential-check",
            ],
        )

    def test_cloud_deploy_workflow_deploys_and_verifies_editing_cloud_run(self) -> None:
        text = workflow_text("cloud-edit-deploy-preflight.yml")

        assert_contains_all(
            self,
            text,
            [
                "cloud_run_revision:",
                "Deploy staging editing service",
                "gcloud auth configure-docker",
                "docker build",
                "docker push",
                "gcloud run deploy \"$EDITING_SERVICE_NAME\"",
                "HOOPS_GIT_SHA=${GITHUB_SHA}",
                "--set-secrets=\"HOOPS_EDITING_SERVICE_SECRET=HOOPS_EDITING_SERVICE_SECRET:latest",
                "HOOPS_INTERNAL_PROCESS_SECRET=HOOPS_EDITING_SERVICE_SECRET:latest",
                "Verify direct editing version after deploy",
                "Verify Worker editing version after deploy",
                ".featureFlags.aiEditLiveRenderEnabled == true",
                ".featureFlags.aiClipGptEditorEnabled == true",
                ".gptHighlightReranker.configured == true",
                "Roll back staging editing service",
                "cloud_run_revision is required when operation=rollback",
                'deploy_ref="${GITHUB_REF_NAME:-main}"',
                "--ref ${deploy_ref}",
                "-f cloud_run_revision=<previous-cloud-run-revision>",
            ],
        )
        self.assertNotIn("--ref main", text)

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
        self.assertIn(
            "if: github.event_name == 'workflow_dispatch' && (inputs.operation == 'preflight' || inputs.operation == 'archive' || inputs.operation == 'upload')",
            text,
        )
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.operation == 'status'", text)
        status_job = text.split("  app-store-connect-status:\n", 1)[1]
        self.assertNotIn("xcodebuild archive", status_job)
        self.assertNotIn("-allowProvisioningUpdates", status_job)
        self.assertNotIn("paths:", text)


def workflow_text(name: str) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / ".github" / "workflows" / name).read_text(encoding="utf-8")


def assert_contains_all(test_case: unittest.TestCase, text: str, needles: list[str]) -> None:
    for needle in needles:
        test_case.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
