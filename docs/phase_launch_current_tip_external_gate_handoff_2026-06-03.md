# Phase Launch Current-Tip External Gate Handoff (2026-06-03)

## Purpose

Record the current external proof gap for `codex/phase-launch-proof-next` without exposing secrets or treating stale workflow success as launch evidence.

This is a handoff artifact only. It does not mark HoopClips ready for internal TestFlight, does not approve public cloud cutover, and does not replace the required human-reviewed accuracy report or installed-device smoke.

## Current Branch State

- Branch: `codex/phase-launch-proof-next`
- Pre-handoff branch tip observed before this note: `08389ce`
- Remote sync state at inspection: `0` ahead / `0` behind `origin/codex/phase-launch-proof-next`
- Branch-to-main state at inspection: `0` behind / `43` ahead of `origin/main`
- Preserved unrelated untracked root folders remain unstaged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`

## Stale Branch Workflow Evidence

Latest successful branch-dispatched runs are not current-tip proof because they ran on `bc37b0e`, not the observed branch tip `08389ce`:

- `Cloud Edit Deploy Preflight` run `26860674510`: success, head SHA `bc37b0ec5613ecee87d90e057245abeb92865800`
- `iOS Internal TestFlight Upload` run `26860672121`: success, head SHA `bc37b0ec5613ecee87d90e057245abeb92865800`
- `iOS Internal TestFlight Upload` run `26860897604`: success, head SHA `bc37b0ec5613ecee87d90e057245abeb92865800`
- `iOS Internal TestFlight Upload` run `26861050768`: success, head SHA `bc37b0ec5613ecee87d90e057245abeb92865800`

These runs are useful historical evidence that the branch direction has worked before, but they must not be counted as current launch proof after the later commits on this branch.

## Current External Gates Still Open

- Rerun required branch workflows at the intended launch tip and confirm each run head SHA matches that tip.
- Complete secret-gated cloud deploy proof without printing or returning secret values.
- Deploy current editing source so live `/version` reports the current git SHA.
- Land or deliberately update `main`, then rerun the failed main cloud deploy and TestFlight upload workflows.
- Finish all human-reviewed label rows, apply without `--allow-incomplete`, rebuild `artifacts/team_highlight_accuracy_report.json`, and rerun submission readiness with `--team-accuracy-report`.
- Install the internal TestFlight build on a trusted iPhone and complete the full import -> team choice -> cloud analysis -> Review -> AI Edit render -> preview -> revision -> download -> share/open-in smoke.

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

This current-tip proof does not close production cloud URLs/secrets,
human-reviewed accuracy labels, signed archive/TestFlight upload, or installed
TestFlight smoke.
