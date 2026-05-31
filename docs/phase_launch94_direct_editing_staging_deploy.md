# Phase Launch94 Direct Editing Staging Deploy

## Goal

Deploy the current GPT-led editing backend to staging without spending GitHub Actions minutes, then verify live non-secret version state for launch readiness.

## Deploy

- Branch: `codex/phase-launch70-editing-analysis-progress`
- Source commit: `f6ff93a8251f20eb6cfc40ff73f8a54f0bb57393`
- Command: `gcloud builds submit --project hoopsclips-9d38f --config services/editing/cloudbuild.yaml --substitutions _IMAGE_TAG=f6ff93a8251f20eb6cfc40ff73f8a54f0bb57393 .`
- Cloud Build ID: `940bbc75-ecbc-4dda-882d-66c1af043144`
- Build status: `SUCCESS`
- Image: `us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging:f6ff93a8251f20eb6cfc40ff73f8a54f0bb57393`
- Revision: `hoopclips-editing-staging-00040-qx8`
- Traffic: `100 percent`

Cloud Run deploy completed with an IAM policy warning:

`Setting IAM policy failed, try "gcloud beta run services add-iam-policy-binding --region=us-central1 --member=allUsers --role=roles/run.invoker hoopclips-editing-staging"`

The service was already reachable through the existing staging path, so this did not block version verification.

## Live Version Evidence

Command:

`curl --fail --silent --show-error https://hoopclips-editing-staging-npya43jiia-uc.a.run.app/version | python3 -m json.tool`

Result:

- `service`: `hoopclips-editing`
- `backendModelVersion`: `editing-cloud-v1`
- `gitSha`: `f6ff93a8251f20eb6cfc40ff73f8a54f0bb57393`
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

`python3 scripts/staging_version_probe.py --expected-git-sha f6ff93a8251f20eb6cfc40ff73f8a54f0bb57393 --json`

Result: `pass`

- Worker `/v1/editing/version` gitSha matched `f6ff93a8251f20eb6cfc40ff73f8a54f0bb57393`.
- Direct editing `/version` gitSha matched `f6ff93a8251f20eb6cfc40ff73f8a54f0bb57393`.
- Both returned the expected non-secret AI Edit feature flag keys.

## Submission Preflight After Deploy

Command:

`python3 scripts/submission_readiness_preflight.py --archive-path ios/archives/HoopsClips-Launch72.xcarchive --json`

Result: `28 pass / 6 fail / 0 warn`

Cleared:

- Direct editing service gitSha now matches current checkout.

Remaining blockers:

- Launch-grade team-highlight accuracy report is missing; 85% selected-team/highlight quality remains unproven until the labeled review set is completed.
- Connected iPhone is detected but unavailable for install/smoke testing.
- Latest main-branch Cloud Edit Deploy Preflight run is stale versus the current checkout.
- Latest main-branch iOS Internal TestFlight Upload run is stale versus the current checkout.
- Latest manually dispatched Cloud Edit Deploy Preflight run is stale versus the current checkout.
- Installed TestFlight post-install smoke remains unproven.

## Notes

- No secrets, R2 credentials, API keys, private key material, or presigned URLs were printed or stored in this document.
- This deploy used local Cloud Build rather than GitHub Actions to conserve the Actions budget.
- The next launch proof still needs real-device availability and human clip-label review, not another backend code change.
