# Phase Launch Active Readiness Snapshot (2026-06-03)

Branch: `codex/phase-launch-proof-next`
Live preflight evidence commit: `3bf34f7`
Latest branch tip checked after this cleanup: `832fd12`
Branch-to-main state at this check: `0` behind `origin/main`, `35` ahead.

## Preflight Verification Run

- Command: `python3 scripts/launch_backend_config_preflight.py --json`
  - Result: `status=pass`, `pass=85`, `warn=12`, `fail=0`
- Command: `python3 scripts/submission_readiness_preflight.py --team-accuracy-report artifacts/team_highlight_labeling_bundle/temp_mapped_draft/team_highlight_accuracy_report.json --json`
  - Result: `status=fail`, `pass=26`, `warn=1`, `fail=7`
  - Live staging Worker and direct editing `/version` probes both returned non-secret AI Edit/GPT feature-flag state.
  - GitHub staging deploy/upload input names were visible enough for the input-name checks to pass without printing secret values.

## Submission Fails

1. **Team-highlight accuracy evidence (hard blocker)**
   - The available `temp_mapped_draft` report is explicitly rejected as draft evidence.
   - Current status: 0/54 complete; 54 remaining.
   - Current draft report still fails launch thresholds: only 1 distinct video, highlight precision 0.0926, shot outcome evidence quality 0.0, selected-team highlight coverage 2, and missing made/missed/opponent/defensive coverage.
   - Bundle files in progress:
     - `artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html`
     - `artifacts/team_highlight_labeling_bundle/label_status.json`
     - `artifacts/team_highlight_labeling_bundle/next_steps.md`

2. **Connected iPhone / installed TestFlight smoke**
   - `xcrun devicectl` can see an iPhone, but it is unavailable for install/smoke testing.
   - Device detail from the preflight: `pairingState=paired`, `tunnelState=unavailable`, `developerModeStatus=enabled`, `ddiServicesAvailable=false`, `lastConnectionDate=2026-05-31 05:23:35 +0000`.
   - `docs/phase_edit7g_post_testflight_internal_smoke.md` still records unproven post-install smoke.

3. **Editing service deploy drift**
   - Direct editing service returned feature flags, but `gitSha` does not match the current checkout.
   - Current source must be deployed before submission-readiness can be claimed.

4. **Main GitHub workflow status**
   - Latest main-branch `Cloud Edit Deploy Preflight` run `26766947519` failed at `2026-06-01T16:11:23Z`.
   - Root cause observed from logs: main expected `team_quick_scan_max_candidate_clips=160`, while current launch config uses `320`.
   - This branch already updates the backend test/config expectation to `320`, but main must receive the branch and rerun before this blocker can be marked closed.
   - Latest main-branch `iOS Internal TestFlight Upload` run `26766947563` failed at `2026-06-01T16:11:23Z`.
   - Root cause observed from logs: main expected `CURRENT_PROJECT_VERSION=11`, while current internal staging build is `14`.
   - This branch already aligns the workflow metadata check, preflight constant, verify script, and Xcode project build number to `14`, but main must receive the branch and rerun before this blocker can be marked closed.

5. **Current-tip branch workflow freshness**
   - Live GitHub evidence found successful branch-dispatched runs on `bc37b0e`, not on the current tip `832fd12`.
   - `Cloud Edit Deploy Preflight` run `26860674510`: success on `bc37b0e`.
   - `iOS Internal TestFlight Upload` runs `26860672121`, `26860897604`, and `26861050768`: success on `bc37b0e`.
   - These runs are useful branch evidence, but current-tip launch proof still requires rerunning the workflows after landing the latest label/evidence-safety commits.

6. **Secret-gated deploy preflight**
   - The secret-gated deploy job is still not launch-proven: `status=completed`, `conclusion=skipped`.
   - The preflight recommends `operation=credential-check` while repairing provider credentials, then `operation=preflight` or `operation=deploy`.

## Current Warnings

- Unrelated untracked root Xcode folders remain present and must not be staged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`

## Passes and Non-Blockers

- Backend config preflight: production-readiness claim remains intentionally blocked by design (no env.production).
- iOS settings and TestFlight internal overlay configuration checks pass.
- Internal staging upload artifact candidate exists in repo.
- Live Worker `/v1/editing/version` returned non-secret AI Edit/GPT feature flags.
- Direct editing `/version` returned non-secret AI Edit/GPT feature flags, although its git SHA is stale.
- Required cloud deploy input names are present locally or in the GitHub staging environment without printing values.
- Required iOS upload input names are present locally or in the GitHub staging environment without printing values.
- Accuracy tooling now blocks launch report output when manual labels are incomplete, and submission preflight rejects draft accuracy reports.

## Next Required Actions

- Finish manual human review to produce a launch-grade label report (`artifacts/team_highlight_accuracy_report.json`) then rerun submission readiness.
- Deploy current editing source so direct editing `/version` reports the current git SHA.
- Land this branch on main, then rerun failed main workflows, including secret-gated `Cloud Edit Deploy Preflight` and `iOS Internal TestFlight Upload`.
- Rerun branch or post-merge workflows at the current launch tip before treating CI evidence as fresh.
- Install TestFlight internal build on trusted device and complete the full import -> analysis -> export -> render -> revision -> share smoke with screenshot evidence.
- Keep production/public cloud cutover blocked until production auth, storage, observability, rollback, label evidence, and installed TestFlight proof are complete.
