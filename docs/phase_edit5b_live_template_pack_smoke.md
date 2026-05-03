# Phase Edit5b Live Template Pack Smoke

## Goal

Phase Edit5b proved the three HoopClips AI Edit template packs through the live cloud render path:

```text
Worker -> Cloud Run editing service -> FFmpeg -> R2 final.mp4 + render_log.json -> download URL
```

The iOS app remains a client for Export configuration, preview, download, share, and Open In. No local video rendering, local edit planning, or AVFoundation composition was introduced.

## Branch

- Branch: `codex/phase-edit5b-live-template-pack-smoke`
- Base branch: `codex/phase-edit5-template-pack`
- Commits before final documentation closeout:
  - `3a459b4` - Add live template pack smoke harness
  - `f1be6a3` - Fix editing Cloud Build image tag

## Deployment

The first live template smoke against staging failed before deploy because the active editing service rejected `templateId` as an extra input. That confirmed staging was still on the pre-Phase-5 editing service.

Deploying `services/editing` initially failed because local Cloud Build did not provide `SHORT_SHA`, producing an invalid empty image tag. `services/editing/cloudbuild.yaml` now uses `_IMAGE_TAG`, and the successful deployment used:

```text
gcloud builds submit . \
  --project=hoopsclips-9d38f \
  --config=services/editing/cloudbuild.yaml \
  --substitutions=_IMAGE_TAG=f1be6a3
```

Deployment evidence:

- Cloud Build ID: `056130e3-9b6c-4cb6-aa7b-bfcb03951a22`
- Image: `us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging:f1be6a3`
- Cloud Run revision: `hoopclips-editing-staging-00006-6bv`
- Cloud Run service URL: `https://hoopclips-editing-staging-npya43jiia-uc.a.run.app`
- Worker URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- `/version` returned `gitSha=f1be6a3`, `ffmpegAvailable=true`, `ffprobeAvailable=true`, and `drawtextAvailable=true`.

Cloud Run reported an IAM policy update warning during deploy. The smoke was not blocked because the existing service URL remained reachable and the deployed revision served `/version` successfully.

## Smoke Script

The live smoke used:

```text
HOOPS_SMOKE_OUTPUT_DIR=/tmp/hoopclips-phase5b-template-smoke-rerun \
ios/backend/.venv/bin/python services/editing/scripts/template_pack_smoke.py
```

Summary artifact:

```text
/private/tmp/hoopclips-phase5b-template-smoke-rerun/template_pack_smoke_summary.json
```

The script was tightened after the revision render path rejected extra fields. Revision render now sends only the install identity expected by the Worker endpoint, and polling tolerates a transient `render_job_not_found` response while the Worker/editing state catches up.

## Template Results

### `personal_highlight_v1`

- editJobId: `edit_642f256db7e4445f9284b400bc7da2d8`
- renderJobId: `render_a0b52f5f084f463593389a1defd6c3bd`
- final object: `edits/edit_642f256db7e4445f9284b400bc7da2d8/render_jobs/render_a0b52f5f084f463593389a1defd6c3bd/final.mp4`
- render log: `edits/edit_642f256db7e4445f9284b400bc7da2d8/render_jobs/render_a0b52f5f084f463593389a1defd6c3bd/render_log.json`
- ffprobe summary: H.264/AAC MP4, `720x1280`, duration `16.222005s`, size `380586` bytes.
- Template defaults observed: `aspectRatio=9:16`, `captionStyle=bold_hype`, `musicTrackId=hype_01`, `musicVolume=0.82`, `gameAudioVolume=0.25`, `targetDurationSeconds=15`.

### `full_game_highlight_v1`

- editJobId: `edit_2eb4d77a566a42ca8cf28eeee84a078e`
- renderJobId: `render_be3f221dba504ff29a36796cfc76017d`
- final object: `edits/edit_2eb4d77a566a42ca8cf28eeee84a078e/render_jobs/render_be3f221dba504ff29a36796cfc76017d/final.mp4`
- render log: `edits/edit_2eb4d77a566a42ca8cf28eeee84a078e/render_jobs/render_be3f221dba504ff29a36796cfc76017d/render_log.json`
- ffprobe summary: H.264/AAC MP4, `1280x720`, duration `19.055338s`, size `523901` bytes.
- Template defaults observed: `aspectRatio=16:9`, `captionStyle=clean_scorebug`, `musicTrackId=cinematic_01`, `musicVolume=0.45`, `gameAudioVolume=0.62`, `targetDurationSeconds=60`.

### `coach_review_v1`

- editJobId: `edit_c199ee670eac4af485b112147af95301`
- renderJobId: `render_bf61f8743d4f403dacc7c2a0394764d5`
- final object: `edits/edit_c199ee670eac4af485b112147af95301/render_jobs/render_bf61f8743d4f403dacc7c2a0394764d5/final.mp4`
- render log: `edits/edit_c199ee670eac4af485b112147af95301/render_jobs/render_bf61f8743d4f403dacc7c2a0394764d5/render_log.json`
- ffprobe summary: H.264/AAC MP4, `1280x720`, duration `21.531995s`, size `545811` bytes.
- Template defaults observed: `aspectRatio=source`, `captionStyle=plain`, `musicTrackId=none`, `musicVolume=0`, `gameAudioVolume=1`, `targetDurationSeconds=60`.

## Revision Compatibility

The smoke rendered a `make_more_hype` revision from the Personal Highlight edit:

- base editJobId: `edit_642f256db7e4445f9284b400bc7da2d8`
- revisionId: `rev_078dd17c5f4d4f5e8529f2b874d1236b`
- revised renderJobId: `render_37b0005e9f114985b4e3ad17c2a6b0bd`
- revised final object: `edits/edit_642f256db7e4445f9284b400bc7da2d8/render_jobs/render_37b0005e9f114985b4e3ad17c2a6b0bd/final.mp4`
- revised render log: `edits/edit_642f256db7e4445f9284b400bc7da2d8/render_jobs/render_37b0005e9f114985b4e3ad17c2a6b0bd/render_log.json`
- ffprobe summary: H.264/AAC MP4, `720x1280`, duration `16.222005s`, size `376616` bytes.
- validationResult: `valid=true`, `errors=[]`
- revisedTemplateId: `personal_highlight_v1`

## R2 Render Log Signatures

Render logs were fetched from `hoopsclips-results-staging` with Wrangler R2 object reads. No R2 credentials or presigned download URLs were logged.

Observed `templateSignature` values:

- Personal Highlight: `templateId=personal_highlight_v1`, `templateVersion=v1`, `aspectRatio=9:16`, `captionStyle=bold_hype`, `audioProfile=hype`, `effectProfile=hype_effects`, `outroProfile=free_social_outro`, `watermarkProfile=hoopclips_app_icon_v1`, `outroAssetId=personal_highlight_outro_free_v1`.
- Full Game Highlight: `templateId=full_game_highlight_v1`, `templateVersion=v1`, `aspectRatio=16:9`, `captionStyle=clean_scorebug`, `audioProfile=game_recap`, `effectProfile=subtle_recap`, `outroProfile=standard_recap_outro`, `outroAssetId=full_game_outro_v1`.
- Coach Review: `templateId=coach_review_v1`, `templateVersion=v1`, `aspectRatio=source`, `captionStyle=plain`, `audioProfile=original_audio`, `effectProfile=minimal_review`, `outroProfile=minimal_review_outro`, `outroAssetId=coach_review_outro_v1`.
- More Hype revision: preserved `templateId=personal_highlight_v1`, `aspectRatio=9:16`, `captionStyle=bold_hype`, `audioProfile=hype`, `effectProfile=hype_effects`, and `outroProfile=free_social_outro`.

## Export UI Verification

The UI smoke test now asserts all three Export-page template cards are present before generating a render:

- `export.aiEdit.style.personalHighlight`
- `export.aiEdit.style.fullGameHighlight`
- `export.aiEdit.style.coachReview`

The live Export-page UI flow was not rerun in this branch because Phase Edit5b allowed the Worker smoke path, and the full live UI smoke was already proven in Phase Edit4c. The iOS build and test bundles were rebuilt successfully to verify the updated UI smoke assertions compile.

## Validation

Passed:

- `git diff --check`
- `ios/backend/.venv/bin/python -m py_compile services/editing/scripts/template_pack_smoke.py`
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service`
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent services.editing.tests.test_editing_service`
- `npm run typecheck` in `services/control-plane`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-phase5b-dd build CODE_SIGNING_ALLOWED=NO`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-phase5b-dd build-for-testing CODE_SIGNING_ALLOWED=NO`

## Remaining Notes

- CI/deploy automation still needs a configured `CLOUDFLARE_API_TOKEN`; local Wrangler OAuth was sufficient for this smoke.
- The full live template smoke is too slow for routine PR CI. Keep it manual or nightly, and use faster fixture-based checks for normal CI.
- Future template polish should replace JSON placeholder assets with generated Remotion/Canva-backed design assets, while keeping FFmpeg as the core renderer and EditPlan as the source of truth.
