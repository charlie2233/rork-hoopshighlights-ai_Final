# Phase Launch Current Readiness Audit - 2026-06-04

Branch: `codex/phase-launch-proof-next`

Audit commit: `d5c5c87 Document Troy backend accuracy check`

Purpose: act on the latest launch-readiness prompt and capture the current repo, deploy, staging, TestFlight, and accuracy blockers without staging unrelated root Xcode folders or leaking secrets.

## Repo Hygiene

Commands run:

```bash
git status --short --branch
git log -1 --oneline --decorate
git worktree list
git branch --show-current
git log --oneline -10
git diff --stat
git diff --check
git pull --ff-only
```

Results:

- Current branch: `codex/phase-launch-proof-next`.
- Latest commit before this doc: `d5c5c87 Document Troy backend accuracy check`.
- Branch is up to date with `origin/codex/phase-launch-proof-next`.
- `git diff --stat` produced no tracked diff output.
- `git diff --check` produced no whitespace/error output.
- Tracked working tree was clean before writing this document.
- Unrelated untracked root folders remain and were not staged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`

Recent launch-proof commits:

```text
d5c5c87 Document Troy backend accuracy check
a225a76 Pad team highlight review clip windows
582c548 Dedupe overlapping team highlight review clips
bec058f Improve team label clip playback review
b547fec Make cloud accuracy upload timeouts configurable
5a91d88 Surface human label review queue in bundle
993fc71 Add human label review queue export
3a563a4 docs: record staging deploy live sha proof
ecada4c docs: record live backend status probe
39304d9 docs: record current signing preflight failure
```

## Live Staging Version Probe

Command run:

```bash
python3 scripts/staging_version_probe.py \
  --worker-base-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --editing-version-url https://hoopclips-editing-staging-npya43jiia-uc.a.run.app/version \
  --json
```

Result summary:

- Overall status: `fail`.
- Diagnosis: `staging_version_git_sha_not_expected`.
- Expected git SHA from current checkout: `d5c5c878a7e8319b50ca6e9862713bffe4ff1b81`.
- Worker `/v1/editing/version`: HTTP `200`, not the older 404 state.
- Direct editing `/version`: HTTP `200`.
- Both endpoints reported git SHA: `3a563a478dc648098d5e35fc15c1dd1911a62056`.

Feature flags returned by both endpoints included:

```text
aiClipGptEditorEnabled
aiClipGptPlanEditEnabled
aiClipGptRevisionEnabled
aiEditEnabled
aiEditFreeWatermarkRequired
aiEditLiveRenderEnabled
aiEditMaxDailyRenders
aiEditProExportsEnabled
aiEditRevisionEnabled
aiEditTemplatePackEnabled
gptHighlightRerankerEnabled
```

Interpretation:

- The Worker route is no longer missing; `/v1/editing/version` now responds with feature flag state.
- Staging is still stale relative to the current launch branch.
- A new staging deploy is still needed before current source changes can be considered live.

## Cloud Edit Deploy Workflow Evidence

Command run:

```bash
gh run list --workflow cloud-edit-deploy-preflight.yml --limit 8 \
  --json databaseId,status,conclusion,createdAt,updatedAt,headBranch,headSha,event,displayTitle,url
```

Latest observed runs:

| Run | Created | Branch | Head SHA | Conclusion |
| --- | --- | --- | --- | --- |
| `26929403700` | `2026-06-04T03:51:57Z` | `codex/phase-launch-proof-next` | `5a91d88` | `success` |
| `26928890799` | `2026-06-04T03:37:33Z` | `codex/phase-launch-proof-next` | `993fc71` | `success` |
| `26928097475` | `2026-06-04T03:15:47Z` | `codex/phase-launch-proof-next` | `3a563a4` | `success` |
| `26927820278` | `2026-06-04T03:07:41Z` | `codex/phase-launch-proof-next` | `ecada4c` | `success` |

Interpretation:

- Cloud deploy preflight has recent success evidence, but the latest run is for `5a91d88`, not current `d5c5c87`.
- Live Worker/editing endpoints currently report `3a563a4`, proving staging is older than even the latest successful cloud preflight.
- No new deploy was triggered in this audit because deploying Worker/Cloud Run is a mutating, potentially billing-consuming action and should be a deliberate operator action.

## Release Secrets Preflight Evidence

Command run:

```bash
gh run list --workflow release-secrets-preflight.yml --limit 5 \
  --json databaseId,status,conclusion,createdAt,updatedAt,headBranch,headSha,event,displayTitle,url

gh run view 26929404669 --log
```

Latest observed release preflight:

- Run: `26929404669`.
- Created: `2026-06-04T03:51:58Z`.
- Branch: `codex/phase-launch-proof-next`.
- Head SHA: `5a91d88`.
- Conclusion: `failure`.

The failure log showed these production release values present/masked:

```text
HOOPS_DEVELOPMENT_TEAM=present
HOOPS_REVENUECAT_API_KEY=present
HOOPS_GOOGLE_CLIENT_ID=present
HOOPS_GOOGLE_REVERSED_CLIENT_ID=present
HOOPS_FIREBASE_AUTH_API_KEY=present
HOOPS_PRIVACY_POLICY_URL=present
HOOPS_TERMS_OF_SERVICE_URL=present
HOOPS_SENTRY_DSN=present
```

The failure log showed these required production release values empty:

```text
HOOPS_CLOUD_ANALYSIS_BASE_URL
HOOPS_CLOUD_EDIT_BASE_URL
```

Interpretation:

- The current release-secrets blocker is specific and actionable.
- Production release cannot pass until cloud analysis/edit base URLs are configured in the release environment.
- No secret values were printed or committed.

## TestFlight / Submission Workflow Lookup

Commands attempted:

```bash
gh run list --workflow ios-internal-testflight-upload.yml --limit 6 --json ...
gh run list --workflow submission-readiness-preflight.yml --limit 6 --json ...
```

Results:

```text
HTTP 404: workflow ios-internal-testflight-upload.yml not found on the default branch
HTTP 404: workflow submission-readiness-preflight.yml not found on the default branch
```

Interpretation:

- The workflow display names may exist under different filenames, or these workflow files are not currently on the default branch under those names.
- Do not treat this as TestFlight smoke proof.
- Installed TestFlight smoke remains unproven until a real device run is documented with build/device/time/job IDs and screenshots or video.

## Human Accuracy / Troy Evidence

Current Troy accuracy report is documented in:

```text
docs/troy_human_accuracy_backend_clip_report.md
```

Current Troy result after the latest dedupe and padding work:

- Raw cloud candidates: `81`.
- Deduped retained review/export clips: `43`.
- Omitted temporal duplicates: `38`.
- Completed retained labels: `43/43`.
- Average padded clip window: `8.905s`.
- Accuracy report status: `fail`.
- Highlight precision: `0.1163`, below required `0.85`.
- Case count: `1`, below required `2`.
- Team mode: `all`, not selected Troy/white team.

The labels are complete, but they prove the backend candidate quality problem rather than closing launch accuracy.

## Current Blockers

### P0 Blockers

1. Staging deploy is stale.

Evidence:

- Current checkout SHA: `d5c5c878a7e8319b50ca6e9862713bffe4ff1b81`.
- Worker/editing live SHA: `3a563a478dc648098d5e35fc15c1dd1911a62056`.

Required next action:

- Trigger a deliberate staging deploy for current branch/source, then rerun `scripts/staging_version_probe.py`.

2. Production release secrets are incomplete.

Missing:

```text
HOOPS_CLOUD_ANALYSIS_BASE_URL
HOOPS_CLOUD_EDIT_BASE_URL
```

Required next action:

- Set these in the production/release GitHub environment or the workflow's expected secret/variable source.
- Rerun `release-secrets-preflight.yml` after setting them.

3. Installed TestFlight smoke is not proven.

Required proof:

```text
Install TestFlight build
upload/import video
cloud analysis
Review
Export
AI Edit
render
preview
More Hype revision
revised preview
share/open-in
```

Evidence to capture:

```text
screenshots or video
jobId
renderJobId
revisionId
Worker git SHA/version
Cloud Run revision/version
R2 final object key names only if safe/non-secret
```

4. Launch-grade accuracy still fails.

Current cause:

- All-teams fallback, not selected Troy/white proof.
- Too many false positives.
- Only one case.
- Shot outcome evidence quality failed.
- Defensive coverage gates failed.

Required next backend work:

```text
fix selected-team scan reliability
rerun selected-team analysis for Troy/white
add stricter candidate-quality filter
add possession-level suppression
improve shot outcome evidence
collect at least one more case
rebuild launch accuracy report
```

## Recommended Immediate Next Action

The next action should be a deliberate staging deploy, but it should not be triggered casually because it mutates live staging and may consume GitHub/GCP/Cloudflare resources.

Recommended command after operator confirms deploy is allowed:

```bash
gh workflow run cloud-edit-deploy-preflight.yml \
  --repo charlie2233/rork-hoopshighlights-ai_Final \
  --ref codex/phase-launch-proof-next \
  -f operation=deploy
```

After it completes, run:

```bash
python3 scripts/staging_version_probe.py \
  --worker-base-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --editing-version-url https://hoopclips-editing-staging-npya43jiia-uc.a.run.app/version \
  --json
```

Success condition:

- Worker and editing endpoint SHA match the deploy commit or an explicitly accepted deploy SHA.
- Worker `/v1/editing/version` remains HTTP `200`.
- Direct editing `/version` remains HTTP `200`.
- Required AI Edit/GPT/live-render flags are present.

## Bottom Line

The product foundation is still in place, and the Worker version route is now live. The current blockers are proof and accuracy:

1. Staging is stale relative to current source.
2. Production release cloud base URLs are missing.
3. Installed TestFlight smoke is not proven.
4. Human accuracy labels are complete for Troy, but the result demonstrates poor candidate precision and selected-team evidence is still unresolved.

Do not polish random features next. The next launch-critical move is staging deploy refresh, followed by real-device TestFlight smoke and selected-team accuracy repair.
