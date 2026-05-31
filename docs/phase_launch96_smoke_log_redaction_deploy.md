# Phase Launch96 Smoke Log Redaction Deploy

Date: 2026-05-31
Branch: `codex/phase-launch70-editing-analysis-progress`
Head: `1bea8709ecff63e9af837ccd40c298ed046e0eb4`

## Goal

Finish the launch-readiness sweep by deploying the current smoke-output redaction hardening to staging without spending GitHub Actions minutes, then verify live version state and submission readiness.

This document is evidence only. It does not mark HoopClips ready for Apple/TestFlight submission.

## What Changed

- Smoke success summaries now pass through `sanitize_for_log(...)`.
- Nested error payloads and unknown object payloads are sanitized before logging.
- Storage-sensitive fields and URL fragments are redacted, including presigned URL fields and storage object prefixes.

Files:

- `ios/backend/scripts/live_render_smoke.py`
- `services/editing/scripts/worker_render_smoke.py`
- `services/editing/tests/test_smoke_sanitization.py`

## Local Validation

Commands:

```bash
PYTHONPATH=ios/backend:services/editing \
  /tmp/hoopclips-editing-test-venv/bin/python -m unittest \
  services.editing.tests.test_smoke_sanitization -v
```

Result: `2` tests passed.

```bash
PYTHONPATH=ios/backend:services/editing \
  /tmp/hoopclips-editing-test-venv/bin/python -m py_compile \
  ios/backend/scripts/live_render_smoke.py \
  services/editing/scripts/worker_render_smoke.py
```

Result: passed.

```bash
PYTHONPATH=ios/backend:services/editing \
  /tmp/hoopclips-editing-test-venv/bin/python -m unittest discover \
  -s services/editing/tests -p 'test_*.py'
```

Result: `119` tests passed.

```bash
git diff --check
```

Result: passed.

## Direct Staging Deploy

Command:

```bash
GIT_SHA=$(git rev-parse HEAD) && \
gcloud builds submit \
  --project hoopsclips-9d38f \
  --config services/editing/cloudbuild.yaml \
  --substitutions _IMAGE_TAG=$GIT_SHA .
```

Result:

- Cloud Build ID: `738cddc1-3b3f-454d-a348-837fbd1f2e3e`
- Build status: `SUCCESS`
- Image: `us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging:1bea8709ecff63e9af837ccd40c298ed046e0eb4`
- Revision: `hoopclips-editing-staging-00041-2hv`
- Traffic: `100 percent`

Cloud Run reported the same IAM policy warning as earlier direct deploys:

`Setting IAM policy failed, try "gcloud beta run services add-iam-policy-binding --region=us-central1 --member=allUsers --role=roles/run.invoker hoopclips-editing-staging"`

The existing staging route stayed reachable, so this did not block verification.

## Live Version Evidence

Command:

```bash
curl --fail --silent --show-error \
  https://hoopclips-editing-staging-568888872909.us-central1.run.app/version \
  | python3 -m json.tool
```

Result:

- `service`: `hoopclips-editing`
- `backendModelVersion`: `editing-cloud-v1`
- `gitSha`: `1bea8709ecff63e9af837ccd40c298ed046e0eb4`
- FFmpeg, FFprobe, and drawtext: available
- `aiEditEnabled`: `true`
- `aiEditLiveRenderEnabled`: `true`
- `aiEditRevisionEnabled`: `true`
- `aiEditTemplatePackEnabled`: `true`
- `aiEditFreeWatermarkRequired`: `true`
- `aiEditProExportsEnabled`: `false`
- `aiClipGptEditorEnabled`: `true`
- `aiClipGptPlanEditEnabled`: `true`
- `aiClipGptRevisionEnabled`: `true`
- `gptHighlightRerankerEnabled`: `true`
- GPT reranker configured: `true`
- GPT model: `gpt-4.1`
- Free candidate cap: `60`
- Paid candidate cap: `60`
- Free frames per clip: `3`
- Paid frames per clip: `8`

## Staging Version Probe

Command:

```bash
python3 scripts/staging_version_probe.py \
  --expected-git-sha 1bea8709ecff63e9af837ccd40c298ed046e0eb4 \
  --json
```

Result: `pass`

- Worker `/v1/editing/version` gitSha matched `1bea8709ecff63e9af837ccd40c298ed046e0eb4`.
- Direct editing `/version` gitSha matched `1bea8709ecff63e9af837ccd40c298ed046e0eb4`.
- Both returned non-secret AI Edit feature-flag state.

## Submission Preflight After Deploy

Command:

```bash
python3 scripts/submission_readiness_preflight.py \
  --archive-path ios/archives/HoopsClips-Launch72.xcarchive \
  --json
```

Result: `28 pass / 6 fail / 0 warn`

Cleared:

- Direct editing service gitSha now matches the current checkout.

Still failing:

- Launch-grade team highlight accuracy report is missing; 85% selected-team/highlight quality remains unproven.
- A real iPhone is detected but unavailable for install/smoke testing.
- Latest main-branch Cloud Edit Deploy Preflight run is stale versus the current checkout.
- Latest main-branch iOS Internal TestFlight Upload run is stale versus the current checkout.
- Latest manually dispatched Cloud Edit Deploy Preflight run is stale versus the current checkout.
- Installed TestFlight post-install smoke remains unproven.

## Recommendation

Do not submit yet. The backend staging revision is current and the smoke-output redaction guard is deployed, but launch still requires human-reviewed team accuracy evidence, a real-device TestFlight smoke, and current CI evidence.
