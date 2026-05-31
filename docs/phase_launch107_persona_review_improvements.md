# Phase Launch107 Persona Review Improvements

Date: 2026-05-31
Branch: `codex/phase-launch70-editing-analysis-progress`

## Goal

Use a 20-persona subagent review panel to find practical launch improvements for HoopClips before internal iOS TestFlight. The panel reviewed the app as players, coaches, parents, privacy reviewers, social/video operators, and Free/Pro buyers. Changes in this pass keep the cloud-first architecture intact: iOS remains the control surface, while cloud owns analysis, AI edit planning, rendering, storage, and quota policy.

## Persona Panel

| # | Persona | Main signal |
|---|---|---|
| 1 | High-school player | Wants faster path: team, side note, review, make reel. |
| 2 | College recruit/player | Recruiting context and coach-ready sharing need to feel first class. |
| 3 | DIII college coach | Avoid social-only captions; preserve context and recruit identity. |
| 4 | AAU coach | Team targeting, uncertain clips, blocks, and steals need visible review tools. |
| 5 | Low-tech parent | Main path has too many scary words and too much setup language. |
| 6 | Tech-savvy parent | Wants upload resilience, clear share/save, and useful history. |
| 7 | High-school head coach | Coach Review should preserve source framing and team evidence. |
| 8 | Assistant coach/video coordinator | Needs current-commit proof, label review, and stronger launch evidence. |
| 9 | Older-iPhone parent | Needs large-text-safe wording, import reliability, and obvious Save to Photos. |
| 10 | Defensive-minded player | Defense, blocks, and steals must be first-class filters. |
| 11 | Tournament/club director | Needs event/team metadata and scalable history/locker. |
| 12 | Skills trainer | Coach Review and slow-motion controls need a serious training path. |
| 13 | Recruiting coordinator | Recruiting Lite/Pro distinction and coach-safe copy matter. |
| 14 | Team social manager | Wants platform-ready outputs, real share copy, and locker organization. |
| 15 | Privacy-conscious parent | Cloud upload, retention, and deletion copy must be truthful. |
| 16 | Non-technical grandparent | The app should read as Choose, Check, Make, Save. |
| 17 | Bilingual/ESL parent | Main flow still has too many hard-coded technical English strings. |
| 18 | App Store/privacy reviewer | Submission story must align with cloud-enabled product reality. |
| 19 | Sports videographer | Large camera-file import and evidence-grade review remain launch risks. |
| 20 | Budget-conscious Free user | Free should feel generous and fair: 3 video edits, clear limits, no hidden policy wording. |

## Repeated Themes

1. The happy path should read like a product: choose video, pick team, check plays, make highlight, save/share.
2. "Discard", "backend", "MP4", "GPT", and config language should stay out of the main customer path.
3. Selected-team review needs trust tools: team badges, uncertain-team clips, defense, blocks, steals.
4. Free must feel usable: 3 video edits/day, 720p, watermark/outro, short cloud retention, clear Save to Photos.
5. Pro value should be concrete: 1080p, no required branding, 25 video edits/day, 10 revisions, 60-day locker, Pro templates.
6. App Store submission cannot claim on-device-only analysis when Release requires cloud upload, analysis, edit planning, and rendering.
7. Large Photos/Files imports and real iPhone smoke remain launch blockers.

## Changes Made

- Review now uses "Skip" instead of "Discard" in visible labels and accessibility values.
- Review adds selected-team, check-team, defense, block, and steal filters with counts and badges.
- Review adds a context strip showing selected team, defensive clips, and clips that need team checking.
- Review entry card now says "Make My Highlight" and opens AI Edit with less technical copy.
- Coach Review defaults to source aspect ratio so film-review clips preserve original framing.
- AI Edit plan card restores detailed Free/Pro rows and says "3 video edits/day" for Free.
- Free plan card now states failed HoopClips jobs do not use a free edit.
- Pro value rows are concrete: 1080p clean exports, no required branding, 25 video edits/day, 10 revisions/edit, 60-day cloud locker, Pro template packs.
- AI Edit side note shows a locked-style warning for Free users asking for NBA/cinematic/recruiting/team package styles.
- AI Edit primary delivery flow adds Save to Photos before Share.
- My AI Edits shows up to 8 rows, adds Save on ready locker rows, and explains cloud expiry versus local Photos/History copies.
- AI Edit and App Review copy reduce customer-facing implementation terms and replace RevenueCat/GPT/backend wording where it appears in the main path.
- App Review sign-in notes now describe the real cloud-enabled product path.
- Backend render quota now counts active/rendered jobs, not failed/failed-timeout jobs, so failed cloud jobs do not burn Free chances.
- First cloud team scan/analysis now asks for explicit cloud AI consent before uploading the source video.
- Team Setup now lets users rename a detected jersey-color team before analysis while preserving the scan-backed team ID.
- Review now shows evidence rows for why a clip is kept/skipped, key moment timestamps, team evidence, outcome evidence, and timing context.
- History now shows each project's selected team or All teams choice, with detail copy explaining uncertain-team review behavior.

## Deferred

- Import preflight for large camera files: size, codec, resolution, local storage, cloud eligibility, and exact over-limit reason.
- Team Setup: save opponent name per project.
- Recruit profile/share packet for coach workflows.
- Platform post packs and deterministic filenames for social managers/videographers.
- Real purchase/restore proof for RevenueCat/App Store sandbox.

## Validation Log

- Passed: `git diff --check`
- Passed: focused editing-service quota tests with `uv run --with-requirements services/editing/requirements.txt --python 3.13 env PYTHONPATH=ios/backend:services/editing python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_daily_render_limit_uses_feature_flag_default_override services.editing.tests.test_editing_service.EditingServiceTests.test_failed_render_does_not_consume_daily_free_quota -v`
- Passed: full editing-service test module with `uv run --with-requirements services/editing/requirements.txt --python 3.13 env PYTHONPATH=ios/backend:services/editing python -m unittest services.editing.tests.test_editing_service -v` (57 tests)
- Passed: iOS Debug simulator build via XcodeBuildMCP `build_sim` with `CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation` (HoopsClips, iPhone 17 Pro, warnings 0)
- Passed: `python3 -m unittest scripts.test_submission_readiness_preflight -v` (36 tests)
- Interrupted: local `xcodebuild test` and `xcodebuild test -only-testing:HoopsClipsTests` both built test bundles, then hung in the simulator runner/finalization path and were terminated. The earlier full run showed multiple unit tests passing and UI smoke tests skipped before the hang, but no clean test summary was produced.
- Expected no-go before commit: `python3 scripts/submission_readiness_preflight.py --skip-live` reported pass=21 warn=3 fail=9 while this branch was still uncommitted.
- Expected no-go after commit: `python3 scripts/submission_readiness_preflight.py --skip-live` reported pass=23 warn=2 fail=8. Repo cleanliness passed; remaining blockers are backend config preflight, team accuracy evidence, archive metadata, unavailable wired iPhone tunnel, stale main CI/deploy runs, secret-gated deploy preflight for the current SHA, and installed TestFlight smoke.
- Follow-up pass: implemented review-deferred cloud consent and detected-team renaming. Validation is tracked in the final handoff for commit after `dd8be93`.
- Follow-up passed: `git diff --check`.
- Follow-up passed: XcodeBuildMCP focused simulator test/build for `HoopsClipsTests/HoopsClipsTests/testTeamTargetCanUseCustomDisplayName` with `CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation`.
- Follow-up passed: `python3 -m unittest scripts.test_submission_readiness_preflight -v` (36 tests).
- Follow-up pass 2: implemented evidence-grade Review rows for clip decision, key moments, team evidence, outcome evidence, and timing context.
- Follow-up pass 2 passed: `git diff --check`, `python3 -m unittest scripts.test_submission_readiness_preflight -v` (36 tests), and XcodeBuildMCP focused simulator tests for `testClipReviewBadgesMarkUncertainTeamOutcomeAndTiming`, `testClipReviewBadgesMarkMissingTeamAttributionStatusUncertain`, and `testClipReviewEvidenceRowsShowConfidentTeamAndKeyMoments`.
- Follow-up pass 2 also made History show selected-team versus All teams context for reopened projects.

## Current Launch Blockers

- Real installed TestFlight smoke is still required on a wired iPhone.
- Real cloud accuracy proof is still required for selected team, highlight windows, blocks, steals, and uncertain-review clips.
- Large Photos/Files import needs real-device matrix proof, especially 4K iPhone and mirrorless `.MOV`.
- App Store privacy copy still needs a full submission pass before submission.
- Production purchase/restore and subscription metadata still need live sandbox proof.
