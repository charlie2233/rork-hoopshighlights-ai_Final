# HoopClips Remaining Launch Actions Checklist

Date: 2026-06-13
Branch: main
Current tip when created: 210cdc36

## Source

This checklist translates the latest local handoff summary into concrete HoopClips launch actions.

The handoff summary reported:

- `backend-staging-health`: ready
- `latest-approval-batch-handoff`: succeeded
- `latest-production-evidence-bundle-handoff`: succeeded
- `latest-live-routing-route-switch-review-packet-handoff`: succeeded
- `latest-live-routing-route-switch-evidence-bundle-handoff`: launchReviewReady
- `archive-live-routing-canary-telemetry`: exited 0 and persisted 1 sanitized archive entry, but remains blocked by the London/walking telemetry report
- `launchReady`: false
- `stagingHealthStatus`: needsReview
- `Remaining actions`: 8
- `Code changes required`: 0

## Checklist

1. [ ] Clear current-head Cloud Edit Deploy Preflight.

Status: in progress.

Evidence:

- Latest current-head run after the fast team-scan test fix: https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/27487270275
- Previous current-head failure was one stale backend test expecting the old 320-clip team-scan budget.
- Commit `210cdc36` updates the test to the intended fast pre-scan budget.

Owner:

- Codex can inspect and fix code/test failures.

2. [ ] Refresh current-head iOS Internal TestFlight proof.

Status: pending.

Evidence needed:

- Current commit SHA
- Build number
- Upload workflow URL
- Upload conclusion

Owner:

- Codex can trigger upload after the backend deploy preflight is clean and the user approves the GitHub/Apple spend.

3. [ ] Review staging health status.

Status: needs release-owner review.

Evidence already available:

- Local health: http://localhost:8000/health
- Public tunnel used: https://discrimination-disabilities-connectors-paragraphs.trycloudflare.com/
- Handoff summary reported `backend-staging-health: ready`.

Owner:

- Release owner must accept or reject the staging health packet.

4. [ ] Finalize route-switch review packet.

Status: launchReviewReady, not final.

Evidence already available:

- `latest-live-routing-route-switch-review-packet-handoff`: succeeded
- `latest-live-routing-route-switch-evidence-bundle-handoff`: launchReviewReady

Owner:

- Release owner must approve route-switch readiness.

5. [ ] Unblock London/walking telemetry report dependency.

Status: blocked.

Evidence:

- Canary archive command exited 0 and persisted 1 sanitized archive entry.
- The same command still returned blocked because the London/walking telemetry report is unresolved.

Owner:

- Release owner or telemetry owner must either attach the missing telemetry report or explicitly waive/defer it.

6. [ ] Re-run or re-accept canary telemetry archive after the telemetry dependency is cleared.

Status: pending telemetry unblock.

Evidence needed:

- Sanitized canary archive status
- Archive entry count
- Non-secret path or handoff ID

Owner:

- Codex can rerun the local archive command if the exact command is available locally.

7. [ ] Complete real installed TestFlight smoke on the latest uploaded build.

Status: pending.

Required path:

- Install from TestFlight
- Import real basketball footage
- Run cloud analysis
- Review clips
- Export / AI Edit
- Render
- Preview
- Save or share/open-in

Owner:

- User must perform phone-side proof.
- Codex can provide the smoke checklist and record non-secret evidence.

8. [ ] Final release-owner launch readiness signoff.

Status: blocked until items 1-7 are complete or explicitly waived.

Evidence needed:

- `launchReady: true`
- `stagingHealthStatus: ready` or release-owner accepted
- Non-secret bundle/handoff IDs
- Current commit SHA
- Current TestFlight build number

Owner:

- Release owner.

## Notes

- Accuracy proof is treated as user-accepted for this checklist because the user explicitly said the current accuracy is good enough.
- No secrets, tokens, private keys, full presigned URLs, or private media are included here.
- Code changes required by the handoff summary are currently `0`; remaining work is proof, review, or release-owner acceptance unless the preflight reveals another stale test or deploy issue.
