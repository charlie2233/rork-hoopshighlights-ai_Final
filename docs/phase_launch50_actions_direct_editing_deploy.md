# Phase Launch50: Actions Direct Editing Deploy

## Goal

Unblock the staging editing-service deploy path after Cloudflare token verification passed but `gcloud builds submit` repeatedly failed before creating a build because the GitHub deploy identity could not access the legacy Cloud Build source bucket.

## Evidence Before Change

- `Cloud Edit Deploy Preflight` workflow dispatches reached these successful checks:
  - Worker typecheck and staging dry run.
  - Editing backend Python tests.
  - GCP authentication.
  - Wrangler token authentication.
  - Staging Worker secret-name check.
  - Staging deployment read scope.
  - Staging Worker dry-run with CI token.
- Deploy runs still failed at `Deploy staging editing service` with:
  - `ERROR: (gcloud.builds.submit) The user is forbidden from accessing the bucket [hoopsclips-9d38f_cloudbuild].`
- Runs inspected:
  - `26673705167`
  - `26673828031`
  - `26673950024`

## GCP/IAM Reconciliation

- Confirmed the deploy service account is `hoopclips-github-deploy@hoopsclips-9d38f.iam.gserviceaccount.com`.
- Reset GitHub staging GCP secrets to the known provider/service-account values without printing secret payloads.
- Added narrow project/bucket IAM for the GitHub workload identity and deploy service account:
  - `roles/serviceusage.serviceUsageConsumer`
  - `roles/storage.legacyBucketReader` on `gs://hoopsclips-9d38f_cloudbuild`
  - `roles/storage.legacyBucketWriter` on `gs://hoopsclips-9d38f_cloudbuild`
  - `roles/storage.objectAdmin` on `gs://hoopsclips-9d38f_cloudbuild`
- The legacy Cloud Build bucket failure persisted, so the workflow now avoids that source bucket path.

## Implementation

- Replaced the workflow's editing-service deploy step with a direct GitHub Actions deploy:
  - `gcloud auth configure-docker`
  - `docker build -f services/editing/Dockerfile`
  - `docker push` to Artifact Registry
  - `gcloud run deploy` using the same staging AI/GPT flags and Secret Manager mounts
- Cloud rendering and analysis remain backend-owned. This only changes CI deployment transport; it does not move analysis, rendering, composition, or FFmpeg work into iOS.

## Validation

- `git diff --check`
- `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/cloud-edit-deploy-preflight.yml")'`
- `python3 -m unittest scripts.test_main_workflow_codecheck_triggers scripts.test_submission_readiness_preflight scripts.test_launch_backend_config_preflight -v`
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
- Local Docker build was attempted but this machine does not have `docker` installed, so the container build must be verified in GitHub Actions.

## Next Deploy Proof

- Push branch and use one deploy workflow run to verify:
  - direct Docker build succeeds
  - direct Docker push succeeds
  - Cloud Run deploy succeeds
  - direct editing `/version` matches the commit SHA and required AI/GPT flags
  - Worker deploy and Worker `/v1/editing/version` succeed

## Remaining Launch Work

- Run a fresh signed TestFlight upload after deploy proof.
- Do real-device internal smoke on iPhone:
  - install TestFlight build
  - upload/import a short basketball video
  - confirm cloud team scan and team selection
  - run analysis, Review, Export, AI Edit render
  - preview, request More Hype revision, preview revised render
  - share/open-in
