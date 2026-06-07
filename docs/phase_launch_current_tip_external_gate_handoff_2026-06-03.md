# Phase Launch Current-Tip External Gate Handoff (2026-06-03)

## Purpose

Record the current external proof state for `main` without exposing secrets or treating stale workflow success as launch evidence.

This is a handoff artifact only. It does not mark HoopClips ready for internal TestFlight, does not approve public cloud cutover, and does not replace the required human-reviewed accuracy report or installed-device smoke.

## Current Branch State

- Branch: `main`
- Current checked tip: `39322802b6da18c49699f91cdf78b2e59ea1cb7b`
- Remote sync state at inspection: `0` ahead / `0` behind `origin/main`
- Branch-to-main state at inspection: launch branch has been fast-forwarded into `main`
- Preserved unrelated untracked root folders remain unstaged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`

## Historical Branch Workflow Evidence

Latest successful branch-dispatched runs are not current-tip proof because they ran on `bc37b0e`, not the observed branch tip `08389ce`:

- `Cloud Edit Deploy Preflight` run `26860674510`: success, head SHA `bc37b0ec5613ecee87d90e057245abeb92865800`
- `iOS Internal TestFlight Upload` run `26860672121`: success, head SHA `bc37b0ec5613ecee87d90e057245abeb92865800`
- `iOS Internal TestFlight Upload` run `26860897604`: success, head SHA `bc37b0ec5613ecee87d90e057245abeb92865800`
- `iOS Internal TestFlight Upload` run `26861050768`: success, head SHA `bc37b0ec5613ecee87d90e057245abeb92865800`

These runs are useful historical evidence that the branch direction has worked before, but they must not be counted as current launch proof after the later commits on this branch.

## Current External Gates Still Open

- Finish all human-reviewed label rows, apply without `--allow-incomplete`, rebuild `artifacts/team_highlight_accuracy_report.json`, and rerun submission readiness with `--team-accuracy-report`.
- Install the internal TestFlight build on a trusted iPhone and complete the full import -> team choice -> cloud analysis -> Review -> AI Edit render -> preview -> revision -> download -> share/open-in smoke.

The current `main` tip has fresh successful proof for the main Cloud Edit Deploy Preflight and internal TestFlight upload workflows. Production cloud URL inputs, release-secret preflight, deploy credential preflight, signed archive, archive metadata, and build `16` internal TestFlight upload are no longer open in this handoff.

## Secret-Safe Return Rules For Provider Or Browser Work

If a browser-side/provider-side agent repairs credentials or triggers workflow reruns, it should return only non-secret proof:

- Workflow name and run URL
- Run status and conclusion
- Run head SHA and whether it matches the expected current tip
- Non-secret names of any missing provider inputs
- Whether each required secret exists and has an enabled latest version, yes/no only
- Whether deploy service accounts have required metadata/payload access, yes/no only
- Final blocker name if something remains blocked

It must not return private keys, base64 key material, API tokens, R2 credentials, OpenAI keys, Secret Manager payloads, presigned URLs, screenshots containing secrets, or full credential-bearing command output.

## Next Operator Checklist

1. Re-run `git fetch origin --prune` and confirm this branch is still synced with origin.
2. Record the new expected launch-tip SHA after any additional commits.
3. Use `scripts/launch_provider_input_handoff.py --ref codex/phase-launch-proof-next` for secret-safe provider repair instructions.
4. Trigger only the cheap deploy `credential-check` first when repairing provider credentials.
5. Count workflow proof only when the run head SHA matches the expected launch-tip SHA.
6. Keep public cloud cutover blocked until production auth, storage, observability, rollback, render reliability, label evidence, and installed TestFlight proof are all complete.

## 2026-06-03 current-tip refresh

Current branch tip before this handoff refresh was
`56bb842 chore: clarify label review launch-ready gate`.

Safe branch proof on that tip:

- Cloud Edit Deploy Preflight run `26900042638`: `success`
- `iOS Internal TestFlight Upload` codecheck run `26900042665`: `success`

Current production environment variable check still visibly exposes only:

- `HOOPS_PRIVACY_POLICY_URL=https://rork.com/privacy`
- `HOOPS_TERMS_OF_SERVICE_URL=https://rork.com/terms`

`HOOPS_CLOUD_ANALYSIS_BASE_URL` and `HOOPS_CLOUD_EDIT_BASE_URL` remain missing
from the visible production environment. The latest `Release Secrets Preflight`
run remains `26884199422`, completed `failure` on `86fdc33` at
`2026-06-03T12:17:59Z`.

This older 2026-06-03 proof is superseded by the 2026-06-07 `main` proof below. Human-reviewed accuracy labels and installed TestFlight smoke remain open in their dedicated evidence paths.

## 2026-06-03 `64ddebc` proof refresh

Current branch tip `64ddebc` (`chore: track current tip external gate handoff`) keeps the consolidated external-gate handoff visible to `scripts/submission_readiness_preflight.py` blocker-doc coverage.

Remote branch proof for `64ddebc`:

- Cloud Edit Deploy Preflight `26900804785`: success
- iOS Internal TestFlight Upload codecheck `26900804722`: success
- Cloud Edit Deploy Preflight duplicate dispatch `26900909850`: success
- iOS Internal TestFlight Upload codecheck duplicate dispatch `26900909936`: success

This older proof only confirmed that the branch kept the external blockers represented in readiness preflight coverage and that safe cloud/iOS codecheck workflows passed for that tip. It is superseded by the 2026-06-07 `main` proof below.

## 2026-06-07 `main` proof refresh

Current `main` tip:

- `39322802b6da18c49699f91cdf78b2e59ea1cb7b`
- Commit: `Align TestFlight metadata check with build 16`

Current non-secret workflow proof:

- Cloud Edit Deploy Preflight run `27086530548`: `success`
- iOS Internal TestFlight Upload run `27086530557`: `success`
- TestFlight upload build: `16`

This closes the stale current-tip external gate handoff for production cloud URL inputs, release-secret/deploy credential preflight, main Cloud Edit Deploy Preflight proof, signed archive proof, archive metadata proof, and internal TestFlight upload proof. The remaining launch gates are tracked separately: human-reviewed team-highlight accuracy evidence and installed trusted-device TestFlight smoke.
