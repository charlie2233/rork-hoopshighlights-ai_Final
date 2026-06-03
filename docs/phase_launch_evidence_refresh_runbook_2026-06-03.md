# Phase Launch evidence refresh runbook - 2026-06-03

Purpose: refresh launch evidence without turning stale docs into launch claims.

Use this before any internal TestFlight readiness claim, release-owner handoff, signed archive/upload attempt, or installed-device smoke report.

## Secret-safe rules

Report only non-secret status and identifiers:

- branch name
- commit SHA
- workflow run IDs
- workflow conclusion/status
- visible environment variable names and non-secret public base URLs
- TestFlight build number/status
- device smoke pass/fail notes
- label-review counts

Do not report secrets, tokens, private key contents, `.p12` data, provisioning profile contents, issuer private key contents, base64 values, JWTs, presigned URLs, storage object URLs with private paths, private video contents, or finished MP4 contents.

## 1. Refresh branch sync and local cleanliness

Run from repo root:

```bash
git fetch --prune
git status --short --branch
git rev-parse HEAD
git rev-parse --abbrev-ref --symbolic-full-name @{u}
git rev-list --left-right --count HEAD...@{u}
git diff --name-status
git diff --cached --name-status
git ls-files -o --exclude-standard
```

Launch evidence requires the checked branch to be synced with its upstream before claiming a current result. Preserve unrelated untracked files such as local root Xcode workspace `Package.resolved` files unless explicitly told otherwise.

## 2. Refresh safe no-secret branch workflows

Current branch proof should come from the latest matching head SHA, not from older docs.

```bash
gh run list \
  --branch codex/phase-launch-proof-next \
  --limit 8 \
  --json databaseId,status,conclusion,headSha,workflowName,createdAt,event \
  --jq '.[] | [.databaseId,.status,(.conclusion // ""),.headSha[0:7],.workflowName,.event,.createdAt] | @tsv'
```

Required supporting proof before a launch handoff can say the branch codecheck surface is current:

- latest `Cloud Edit Deploy Preflight` run for the checked head is `success`
- latest `iOS Internal TestFlight Upload` run with `operation=codecheck` for the checked head is `success`

This proof is supporting evidence only. It is not production cloud readiness, signed archive/upload, installed TestFlight smoke, or human-reviewed GPT accuracy proof.

## 3. Refresh production cloud URL and release-secret gate

```bash
gh variable list --env production
gh run list \
  --workflow release-secrets-preflight.yml \
  --limit 3 \
  --json databaseId,status,conclusion,headSha,headBranch,createdAt,event \
  --jq '.[] | [.databaseId,.status,(.conclusion // ""),.headSha[0:7],(.headBranch // ""),.event,.createdAt] | @tsv'
```

Production cloud cutover remains blocked unless all of these are current and true:

- `HOOPS_CLOUD_ANALYSIS_BASE_URL` is visible or otherwise confirmed through a secret-safe release-owner path
- `HOOPS_CLOUD_EDIT_BASE_URL` is visible or otherwise confirmed through a secret-safe release-owner path
- `release-secrets-preflight.yml` passes on the launch branch after variables/secrets are fixed or confirmed

Do not use green no-secret branch workflows as a substitute for Release Secrets Preflight.

## 4. Refresh human-reviewed accuracy evidence

```bash
jq -r '["status=" + .status, "clipCount=" + (.clipCount|tostring), "completeClipCount=" + (.completeClipCount|tostring), "incompleteClipCount=" + (.incompleteClipCount|tostring), "launchEvidenceEligible=" + (.launchEvidenceEligible|tostring), "missing=" + (.missingFieldCounts|to_entries|map(.key + ":" + (.value|tostring))|join(", "))] | .[]' \
  artifacts/team_highlight_labeling_bundle/label_status.json
```

Launch accuracy remains blocked unless the label status reports:

- `status=complete`
- `completeClipCount=54`
- `incompleteClipCount=0`
- `launchEvidenceEligible=true`

GPT draft labels do not count as launch evidence. Every clip must be human-reviewed and the launch team accuracy report must be rebuilt.

## 5. Refresh signed archive/upload evidence

Only after production URLs/secrets and signing inputs are ready, run the signed archive/upload workflow path. Report only:

- workflow name
- run ID
- head SHA
- job names and conclusions
- TestFlight build number or processing status

Codecheck is not signed archive/upload proof.

## 6. Refresh installed TestFlight smoke evidence

Installed smoke requires a trusted physical iPhone running a build installed from TestFlight, not a local developer install.

The smoke must cover:

- install HoopClips from TestFlight
- import real basketball footage
- choose team/edit intent
- upload to the cloud backend
- review cloud-generated GPT-led clips
- receive a finished MP4
- preview the MP4
- download/save it
- share/open it in common editors
- confirm there is no confusing copy, hidden text, broken layout, fake status, or local-only editing behavior

Report only non-secret evidence: build number, backend host name, visible app status copy, screenshots/video timestamps, pass/fail notes, and issue summaries.

## Current blocker posture from the 2026-06-03T21:22Z refresh

At the time this runbook was created:

- branch `codex/phase-launch-proof-next` was synced at `40a2da5f03729967549fa3cea2db6f770d244195`
- latest no-secret cloud/iOS branch workflows were green on `40a2da5`
- production variables still showed only privacy and terms URLs
- `HOOPS_CLOUD_ANALYSIS_BASE_URL` and `HOOPS_CLOUD_EDIT_BASE_URL` were still missing from visible production variables
- latest Release Secrets Preflight remained `26884199422`, failure, head `86fdc33`
- label status remained `0/54` complete and `launchEvidenceEligible=false`
- signed archive/upload and installed trusted-device TestFlight smoke were still unproven

This runbook is not launch evidence by itself. It is the repeatable way to gather the evidence that can support or reject a launch-ready claim.
