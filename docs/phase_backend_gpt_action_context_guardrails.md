# Phase: Backend GPT Action Context Guardrails

Branch: `codex/phase-backend-gpt-action-context-guardrails`

## Goal

Improve GPT-led highlight selection quality by making the backend GPT editor explicitly prefer complete basketball moments and reject late fragments, dead-ball clips, scoreboard/huddle-only clips, post-play-only aftermath, reaction-only clips, and basket/celebration-only clips without the causal play.

## Architecture

- Cloud/backend still owns analysis, candidate selection, GPT reranking, EditPlan validation, rendering, storage, and policy.
- iOS remains the control surface for upload, team choice, status, review, preview, download, and share.
- GPT still receives only existing candidate clips and sampled keyframes, never full videos.
- GPT still does not generate FFmpeg commands or bypass deterministic validators.

## Changes

- Added per-candidate `actionContextGuidance` to the compact GPT payload.
- Added shot-tracker rules requiring setup/event/result context for kept clips.
- Added prompt instructions that kept clips need sampled setup or lead-in, basketball event, visible outcome, and follow-through when those roles exist.
- Added explicit rejection guidance for late fragments, dead balls, scoreboard/huddle-only clips, post-play-only aftermath, reaction-only clips, and basket/celebration-only clips.
- Added `actionContextPolicy` to the selection-quality rules consumed by GPT.
- Updated backend tests to assert the payload and instructions carry the new action-context guardrails.
- Updated the editing service README so launch docs match the backend behavior.

## Background Job Reminder Check

The app already tells users they can switch apps after cloud handoff:

- `CloudAnalysisProgressCopy.backgroundReminder(...)` returns switch-app copy for active cloud analysis after upload.
- `AIEditBackgroundJobCopy.reminder(...)` returns switch-app/cloud-job copy for planning, plan-ready, queued, and rendering states when a cloud source exists.
- `AIEditView` renders the AI Edit background reminder in the status card.
- `VideoPlayerView` renders the cloud analysis background reminder during analysis progress.

This branch did not add local background rendering or local analysis. It only verified that the reminder is already wired to real cloud job states.

## Validation

Commands run locally:

```bash
git diff --check
ios/backend/.venv/bin/python -m pytest services/editing/tests/test_gpt_reranker.py
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16e' -derivedDataPath /tmp/hoopclips-bg-reminder-dd CODE_SIGNING_ALLOWED=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testAIEditBackgroundReminderOnlyAppearsForCloudJobs -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudAnalysisBackgroundReminderIsHonestAndVisible test
python3 scripts/submission_readiness_preflight.py --skip-live --archive-path ios/build/HoopsClips-InternalStaging-Build14.xcarchive --json
```

Results:

- `git diff --check`: passed.
- GPT reranker tests: `104 passed in 0.93s`.
- Focused iOS background-reminder tests: `TEST SUCCEEDED`.
- Local submission-readiness preflight: `status=fail`, `pass=24`, `warn=3`, `fail=6`.

Preflight blockers:

- Launch-grade selected-team/highlight accuracy is still unproven; current labeling bundle progress is `0/54` human-reviewed clips.
- The connected iPhone was detected but unavailable for install/smoke testing.
- Latest main-branch `Cloud Edit Deploy Preflight` run is still failed/stale.
- Latest main-branch `iOS Internal TestFlight Upload` run is still failed/stale.
- Latest manually dispatched deploy preflight is not for the current checkout.
- Installed TestFlight post-install smoke remains unproven.

Existing iOS tests cover the switch-app reminder copy in `ios/HoopsClipsTests/HoopsClipsTests.swift`:

- `AIEditBackgroundJobCopy.reminder(...)` includes `switch apps` and `cloud job` for active cloud render states.
- `CloudAnalysisProgressCopy.backgroundReminder(...)` includes `switch apps` for active cloud analysis after upload.

## Launch Notes

- This improves semantic editing guardrails but does not by itself prove internal TestFlight readiness.
- Still required before submission: installed iPhone smoke through import, cloud analysis, Review, AI Edit render, preview, revision, revised preview, and share/open-in.
- Still required for the 85% target: labeled real-footage accuracy evidence for selected-team highlights, blocks, steals, loud-crowd recall, and GPT final keeps.
