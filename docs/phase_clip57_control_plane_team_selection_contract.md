# Phase Clip57: Control Plane Team Selection Contract

## Goal

Make selected-team highlight intent survive the production Cloudflare control-plane path. iOS and the Python backend already understand `teamSelection`, but queued inference must receive the same team/all-teams choice so selected-team analysis, uncertain review inclusion, blocks, and steals can be enforced in staging.

## Change

- Added shared control-plane `TeamSelection`, `TeamOption`, and `ClipTeamAttribution` types.
- Presign/create requests can store `teamSelection` on the job record.
- Start requests can set or update `teamSelection` before queue dispatch.
- Queue messages and external inference dispatch requests now carry `teamSelection`.
- Retry dispatch uses the stored job-level `teamSelection`.
- Job status responses attach stored `teamSelection` to completed results when the inference result did not echo it.
- Legacy inference manifest normalization now preserves:
  - `eventCenter`
  - `nativeShotSignals`
  - `teamAttribution`
  - `teamAttributionStatus`
  - `detectedTeams`
  - `teamSelection`

## Architecture

- Cloud backend/control-plane owns selected-team policy and dispatch.
- iOS still only uploads, asks for team scan/selection, starts analysis, and displays Review/export state.
- No full videos are sent to GPT by this change.
- No secrets, R2 credentials, or presigned URLs are logged.

## Validation

- `npm run typecheck` in `services/control-plane` passed.
- `npm test -- --test-name-pattern 'selected team|legacy inference manifest|happy path'` in `services/control-plane` passed: 22 tests.
- `npm test` in `services/control-plane` passed: 22 tests.
- `git diff --check` passed.

## Launch Recommendation

Treat this as a staging blocker for selected-team internal smoke. Without this contract, iOS could appear to select a team while production inference analyzes all teams or drops uncertain-team context.
