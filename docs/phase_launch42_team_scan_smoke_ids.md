# Phase Launch42: Team Scan Smoke IDs

Date: 2026-05-29
Branch: `codex/phase-launch42-team-scan-smoke-ids`

## Goal

Make the internal TestFlight post-install smoke easier to drive on a wired iPhone by giving the preanalysis team targeting controls stable automation identifiers. The product flow already requires the user to choose a scanned jersey-color team or All teams before analysis when cloud team scan detects teams; this phase makes that requirement directly addressable by UI automation and manual evidence capture.

## Changes

- Added deterministic `HighlightTeamSelection.accessibilityIdentifier` values:
  - `analysis.teamTarget.choice.all`
  - `analysis.teamTarget.choice.<team-id-or-label>`
- Added IDs to the iOS import/analysis screen:
  - `analysis.teamTarget.section`
  - `analysis.teamTarget.status`
  - `analysis.startButton`
- Added a DEBUG-only, no-network UI smoke fixture:
  - launch argument: `--hoops-team-choice-ui-smoke`
  - smoke mode: `HOOPS_UI_SMOKE_MODE=team_choice`
  - seeds an imported-video state with Blue jerseys and White jerseys detected
  - keeps analysis locked until the user confirms All teams or one jersey-color team
- Added `testPreanalysisTeamChoiceSmoke` to capture screenshots before and after team confirmation when UI smoke tests are enabled.
- Kept iOS as a control surface only. This phase does not add local analysis, rendering, composition, or export behavior.
- Added unit expectations that scanned team choices produce stable automation IDs while preserving the 0.85 confidence threshold and uncertain-review inclusion.

## Smoke Usage

For the post-install TestFlight loop:

1. Import a video.
2. Wait for `analysis.teamTarget.section`.
3. If scan is running, wait for `analysis.teamTarget.status` to stop showing progress.
4. Tap either `analysis.teamTarget.choice.all` or a scanned team button such as `analysis.teamTarget.choice.team-dark`.
5. Verify `analysis.startButton` becomes enabled.
6. Start analysis and continue to Review, Export, AI Edit, render, revision, preview, download, and share/open-in.

The selected-team path should keep uncertain clips available for Review, including blocks, steals, forced turnovers, and defensive stops when ownership is not fully certain.

For simulator UI evidence without cloud calls:

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch42-ui-dd -only-testing:HoopsClipsUITests/HoopsClipsUITests/testPreanalysisTeamChoiceSmoke OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE' CODE_SIGNING_ALLOWED=NO
```

## Validation

Commands run for this phase:

```bash
git diff --check
# passed

xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch42-test-dd2 -only-testing:HoopsClipsTests/HoopsClipsTests/testHighlightTeamSelectionCodablePreservesPrimaryColorHex -only-testing:HoopsClipsTests/HoopsClipsTests/testTeamTargetChoicesRequireDetectedTeams CODE_SIGNING_ALLOWED=NO
# passed

xcodebuild -quiet test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch42-ui-dd -only-testing:HoopsClipsUITests/HoopsClipsUITests/testPreanalysisTeamChoiceSmoke 'OTHER_SWIFT_FLAGS=$(inherited) -D HOOPS_ENABLE_UI_SMOKE' CODE_SIGNING_ALLOWED=NO
# passed; attached "Team Choice Before Confirmation" and "Team Choice Blue Confirmed" screenshots in the xcresult

xcodebuild -quiet -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch42-dd2 CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment build
# passed with existing Swift warnings

python3 scripts/submission_readiness_preflight.py --json
# failed with launch blockers listed below

gh pr checks 42 --json name,state,bucket,workflow,startedAt,completedAt,link
# PR checks were triggered, but hosted runner jobs did not start because GitHub reports failed account payments or a spending-limit increase requirement
```

## Remaining Launch Blockers

This phase does not clear the live external blockers:

- Google Cloud Secret Manager is missing `HOOPS_OPENAI_API_KEY`; no enabled version is verified.
- Secret Manager Secret Accessor is not verified for the staging deploy service account.
- Cloudflare `CLOUDFLARE_API_TOKEN`/Wrangler deploy proof is still required in the GitHub `staging` environment.
- GitHub Actions hosted runner jobs for PR #42 are blocked before execution by account billing/spending-limit status.
- No successful staging deploy/preflight run has completed after the missing-secret failure.
- Live staging Worker `/v1/editing/version` is stale/404 until the Worker is deployed.
- Direct editing Cloud Run version is stale until the current source is deployed.
- Launch-grade team/highlight accuracy report from real labeled footage is still missing.
- Installed TestFlight smoke still needs an available physical iPhone.
