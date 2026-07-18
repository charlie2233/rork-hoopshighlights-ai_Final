import subprocess
import sys
import unittest
from pathlib import Path


class AccuracyCliEntrypointTests(unittest.TestCase):
    def test_documented_accuracy_scripts_run_directly(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        scripts = [
            "scripts/collect_team_highlight_accuracy_case.py",
            "scripts/make_team_highlight_label_template.py",
            "scripts/build_launch_team_accuracy_report.py",
            "scripts/summarize_team_highlight_accuracy_gate.py",
        ]

        for script in scripts:
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, script, "--help"],
                    cwd=repo_root,
                    check=True,
                    capture_output=True,
                    text=True,
                )

                self.assertIn("usage:", result.stdout)


if __name__ == "__main__":
    unittest.main()
