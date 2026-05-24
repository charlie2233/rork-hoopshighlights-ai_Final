#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


REPO = "charlie2233/rork-hoopshighlights-ai_Final"
ENVIRONMENT = "staging"
PROJECT_ID_SOURCE = "docs/gcp_cost_control_2026_05_10.md"
REGION_SOURCE = "services/editing/cloudbuild.yaml"
LEGAL_URL_SOURCE = "ios/docs/runbooks/rork-release-operator-handoff.md"


@dataclass(frozen=True)
class PublicVariable:
    name: str
    source: str
    value_available: bool


@dataclass(frozen=True)
class ApplyResult:
    name: str
    source: str
    status: str


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    values = resolve_public_variable_values(repo_root)
    variables = [
        PublicVariable(name=name, source=source, value_available=bool(value))
        for name, (value, source) in values.items()
    ]

    if args.json:
        exit_code = 0 if all(variable.value_available for variable in variables) else 1
        payload = {
            "mode": "apply" if args.apply else "dry-run",
            "repo": args.repo,
            "environment": args.environment,
            "variables": [asdict(variable) for variable in variables],
        }
        if args.apply:
            results = apply_variables(values, repo=args.repo, environment=args.environment)
            payload["results"] = [asdict(result) for result in results]
            exit_code = 0 if all(result.status == "set" for result in results) else 1
        print(json.dumps(payload, indent=2, sort_keys=True))
        return exit_code

    print("HoopClips GitHub staging public variable setup")
    print(f"mode={'apply' if args.apply else 'dry-run'}")
    print("Values are read from repo-tracked launch config/docs and are not printed.")
    if args.apply:
        results = apply_variables(values, repo=args.repo, environment=args.environment)
        for result in results:
            print(f"[{result.status.upper()}] {result.name} ({result.source})")
        return 0 if all(result.status == "set" for result in results) else 1

    for variable in variables:
        status = "ready" if variable.value_available else "missing-source"
        print(f"[DRY-RUN] {variable.name} {status} ({variable.source})")
    print("Run again with --apply to set only these non-secret GitHub environment variables.")
    return 0 if all(variable.value_available for variable in variables) else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Set HoopClips GitHub staging environment variables that are explicitly "
            "public/non-secret in repo-tracked launch docs. Secret values are never read or printed."
        )
    )
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--environment", default=ENVIRONMENT)
    parser.add_argument("--apply", action="store_true", help="Actually set GitHub environment variables.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output without variable values.")
    return parser.parse_args()


def resolve_public_variable_values(repo_root: Path) -> dict[str, tuple[str | None, str]]:
    return {
        "GCP_PROJECT_ID": (extract_project_id(repo_root), PROJECT_ID_SOURCE),
        "GCP_REGION": (extract_cloudbuild_substitution(repo_root, "_REGION"), REGION_SOURCE),
        "HOOPS_PRIVACY_POLICY_URL": (
            extract_shell_export_or_bullet_value(repo_root, "HOOPS_PRIVACY_POLICY_URL"),
            LEGAL_URL_SOURCE,
        ),
        "HOOPS_TERMS_OF_SERVICE_URL": (
            extract_shell_export_or_bullet_value(repo_root, "HOOPS_TERMS_OF_SERVICE_URL"),
            LEGAL_URL_SOURCE,
        ),
    }


def extract_project_id(repo_root: Path) -> str | None:
    text = read_text(repo_root / PROJECT_ID_SOURCE)
    if text is None:
        return None
    match = re.search(r"Project:\s*`([^`]+)`", text)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def extract_cloudbuild_substitution(repo_root: Path, name: str) -> str | None:
    text = read_text(repo_root / REGION_SOURCE)
    if text is None:
        return None
    pattern = re.compile(rf"^\s*{re.escape(name)}:\s*([^\n#]+?)\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    value = match.group(1).strip().strip("\"'")
    return value or None


def extract_shell_export_or_bullet_value(repo_root: Path, name: str) -> str | None:
    text = read_text(repo_root / LEGAL_URL_SOURCE)
    if text is None:
        return None
    patterns = (
        re.compile(rf"^\s*-\s*`{re.escape(name)}=([^`]+)`", re.MULTILINE),
        re.compile(rf"^\s*export\s+{re.escape(name)}=\"([^\"]+)\"", re.MULTILINE),
    )
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(1).strip()
            return value or None
    return None


def apply_variables(values: dict[str, tuple[str | None, str]], *, repo: str, environment: str) -> list[ApplyResult]:
    results: list[ApplyResult] = []
    for name, (value, source) in values.items():
        if not value:
            results.append(ApplyResult(name=name, source=source, status="missing-source"))
            continue
        try:
            result = subprocess.run(
                [
                    "gh",
                    "variable",
                    "set",
                    name,
                    "--repo",
                    repo,
                    "--env",
                    environment,
                    "--body",
                    value,
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            results.append(ApplyResult(name=name, source=source, status="failed"))
            continue
        results.append(ApplyResult(name=name, source=source, status="set" if result.returncode == 0 else "failed"))
    return results


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
