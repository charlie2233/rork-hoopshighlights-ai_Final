# Phase Launch80: Staging GPT Quality Deploy

## Scope

This pass verified an external read-only review note, avoided unneeded code churn, and refreshed the staging editing service to the current launch branch without spending GitHub Actions minutes.

No iOS local analysis, rendering, composition, export, FFmpeg ownership, or Remotion/Canva runtime was added. Cloud remains responsible for analysis, GPT-led clip selection, edit planning, rendering, storage, and revisions.

## Review Note Triage

Input: `/Users/hanfei/Desktop/HoopClips-Review-Notes-2026-05-30_full.txt`.

Findings verified against this branch:

- The reported bad Photos import filename string did not reproduce. Current code uses `imported_video_\(UUID().uuidString).\(fileExtension)`.
- The Photos import path is already file-backed only and supports `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- The reported `Data.self` fallback is absent from `VideoPlayerView.swift`.
- The reported CloudEditService locker rerender regression did not reproduce. Focused iOS tests passed through the Build iOS Apps plugin.

## Validation

```bash
Build iOS Apps plugin:
test_sim HoopsClips Debug iPhone 17 Pro -only-testing:HoopsClipsTests/CloudEditServiceTests

python3 -m py_compile ios/backend/scripts/live_render_smoke.py services/editing/scripts/worker_render_smoke.py
python3 -m unittest discover -s scripts -p 'test_*.py' -v
uv run --with-requirements ios/backend/requirements.txt --python 3.11 env PYTHONPATH=ios/backend:services/editing python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
uv run --with-requirements ios/backend/requirements.txt --python 3.11 env PYTHONPATH=ios/backend:services/editing python -m unittest discover -s services/editing/tests -p 'test_*.py' -v
python3 services/editing/scripts/deploy_preflight.py --json
```

Results:

- `CloudEditServiceTests`: 11 passed.
- Smoke script compile: passed.
- `scripts` test discovery: 130 passed.
- `ios/backend/tests`: 207 passed.
- `services/editing/tests`: 117 passed.
- Deploy preflight: blocked only on local Cloudflare/Wrangler auth; GCP CLI, active project, Artifact Registry, required Secret Manager metadata/latest versions, Cloud Run service, and R2 endpoint checks passed.

The attempted combined uv environment using both `ios/backend/requirements.txt` and `services/editing/requirements.txt` was intentionally abandoned because those files pin different `boto3` versions. The successful editing-service test run used the backend requirements environment, matching prior repo validation docs.

## Staging Deploy

To conserve GitHub Actions budget, the direct editing service was redeployed through Google Cloud Build:

```bash
IMAGE_TAG=$(git rev-parse --short HEAD)
gcloud builds submit . \
  --project=hoopsclips-9d38f \
  --config=services/editing/cloudbuild.yaml \
  --substitutions=_IMAGE_TAG="$IMAGE_TAG"
```

Evidence:

- Cloud Build ID: `0c6f9406-dae9-487e-aeff-41dcdf800f85`.
- Image tag: `2ca029d`.
- Image digest: `sha256:5b619d9baf7924c7889d631b8c50a6a368b2aaf3e51abd7b0f08ff37acda6a4d`.
- Cloud Run revision: `hoopclips-editing-staging-00039-tz5`.
- Cloud Run traffic: 100% to `hoopclips-editing-staging-00039-tz5`.

Cloud Run printed an IAM policy warning while reapplying public invoker access, but both the canonical service URL and alternate Cloud Run URL were reachable after deploy.

## Live Version Proof

```bash
python3 scripts/staging_version_probe.py --expected-git-sha 2ca029d --json
```

Result:

- Status: `pass`.
- Diagnosis: `staging_version_ready`.
- Worker `/v1/editing/version`: `gitSha=2ca029d`, `backendModelVersion=editing-cloud-v1`.
- Direct editing `/version`: `gitSha=2ca029d`, `backendModelVersion=editing-cloud-v1`.
- Required non-secret AI Edit kill switches were present on both endpoints.

The direct editing version snapshot also reported:

- `aiClipGptEditorEnabled=true`.
- `aiClipGptPlanEditEnabled=true`.
- `aiClipGptRevisionEnabled=true`.
- `gptHighlightRerankerEnabled=true`.
- GPT reranker configured: `true`.
- Model: `gpt-4.1`.
- Free candidate cap: `60`.
- Pro/internal candidate cap: `60`.
- Free keyframes per clip: `3`.
- Pro/internal keyframes per clip: `8`.

No R2 credentials, service secrets, OpenAI keys, sampled frames, object keys, or full presigned URLs were printed or committed.

## Submission Readiness

After deploy:

```bash
python3 scripts/submission_readiness_preflight.py --archive-path ios/archives/HoopsClips-Launch72.xcarchive --json
```

Result:

- Summary: 28 pass, 6 fail, 0 warn.
- Improved from the previous 27 pass, 7 fail, 0 warn because direct editing `gitSha` now matches the checkout.

Remaining blockers:

- Missing launch-grade `--team-accuracy-report`; 85% selected-team/highlight quality remains unproven until human review completes the 66 Launch71 labels.
- Connected iPhone is detected but unavailable for install/smoke testing.
- Latest main-branch Cloud Edit Deploy Preflight workflow run is stale for the current checkout.
- Latest main-branch iOS Internal TestFlight Upload workflow run is stale for the current checkout.
- Latest secret-gated deploy preflight workflow dispatch is stale for the current checkout.
- Installed TestFlight post-install smoke remains unproven.

## Next Recommended Action

Finish human review of `artifacts/team_highlight_accuracy_launch71_review.html`, apply the completed label bundle without `--allow-incomplete`, generate the launch-grade team accuracy report, then rerun submission preflight with `--team-accuracy-report`. After the wired iPhone is available again, run the installed TestFlight smoke before spending GitHub Actions on final current-main deploy/upload runs.
