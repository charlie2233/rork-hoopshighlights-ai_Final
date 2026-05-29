# Phase Clip136 - Team Scan Defensive Action Evidence

Date: 2026-05-29
Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Improve pre-analysis team selection accuracy for defensive highlights. A GPT quick-scan clip attribution can no longer claim high confidence for steals, forced turnovers, defensive stops, or blocks using only setup/result frames. Confident defensive ownership now requires a sampled action frame that shows the defender making the play.

This supports the selected-team workflow:

- user imports video
- cloud quick-scan labels teams by jersey color
- user chooses a team or all teams before analysis
- selected-team analysis keeps that team's scoring and defensive highlights
- uncertain clips stay reviewable instead of being silently discarded

## Change

`ios/backend/app/team_quick_scan.py`

- Blocks require `challenge` or `ballDeflection` evidence for high-confidence ownership.
- Steals, strips, and forced turnovers require `ballDeflection`, `possessionChange`, or `ballControlChange` evidence.
- Defensive stops require an action-oriented defensive role such as `challenge`, `possessionPressure`, `possessionChange`, or `ballControlChange`.
- Setup and outcome frames still count toward evidence diversity, but they are not enough by themselves for confident defensive ownership.

`ios/backend/tests/test_team_quick_scan.py`

- Added coverage that caps a steal attribution below the confident threshold when GPT cites only `defenseSetup` and `defenseOutcome`.
- Added coverage that keeps high confidence when GPT cites a real `possessionChange` frame plus an outcome frame.

## Red/Green Evidence

Red test before implementation:

```bash
PYTHONPATH=/tmp/hoopclips-backend-test-deps:ios/backend:services/editing \
/Users/hanfei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
-m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_high_confidence_steal_attribution_requires_possession_change_evidence -v
```

Result:

```text
FAIL: expected confidence < 0.85, got 0.92
```

Green focused tests:

```bash
PYTHONPATH=/tmp/hoopclips-backend-test-deps:ios/backend:services/editing \
/Users/hanfei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
-m unittest \
  ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_high_confidence_steal_attribution_requires_possession_change_evidence \
  ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_high_confidence_steal_attribution_accepts_possession_change_evidence -v
```

Result:

```text
Ran 2 tests in 0.002s
OK
```

Full quick-scan suite:

```bash
PYTHONPATH=/tmp/hoopclips-backend-test-deps:ios/backend:services/editing \
/Users/hanfei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
-m unittest ios.backend.tests.test_team_quick_scan -v
```

Result:

```text
Ran 33 tests in 0.130s
OK
```

Broader backend validation:

```bash
PYTHONPATH=/tmp/hoopclips-backend-test-deps:ios/backend:services/editing \
/Users/hanfei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
-m unittest discover -s ios/backend/tests -v
```

Result:

```text
Ran 197 tests in 4.762s
OK
```

Editing service and GPT reranker validation:

```bash
PYTHONPATH=/tmp/hoopclips-backend-test-deps:ios/backend:services/editing \
/Users/hanfei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
-m unittest discover -s services/editing/tests -v
```

Result:

```text
Ran 107 tests in 23.431s
OK
```

## Launch Notes

- No iOS rendering, local video analysis, or FFmpeg behavior changed.
- No full video is sent to GPT; this remains sampled-frame quick-scan logic.
- No secrets, R2 credentials, or full presigned URLs were printed or stored.
- This is an accuracy hardening change, not final evidence that HoopClips is ready for App Store/TestFlight submission. Real-device TestFlight smoke and staging render proof are still launch gates.

## Post-Commit Readiness Refresh

Clean local preflight with live probes skipped:

```bash
python3 scripts/submission_readiness_preflight.py --skip-live
```

Result:

```text
pass=22 warn=2 fail=8
```

Remaining failures:

- missing launch-grade labeled-footage team-highlight accuracy report
- wired iPhone detected but unavailable to CoreDevice
- main-branch workflow evidence is stale relative to `2c57e20`
- installed TestFlight smoke remains unproven
- staging Worker version proof and live iOS kill-switch proof remain documented blockers
- Cloudflare deploy credential proof remains documented as blocked

Full live preflight:

```bash
python3 scripts/submission_readiness_preflight.py
```

Result:

```text
pass=22 warn=0 fail=11
```

Additional live failures:

- Worker `GET /v1/editing/version` returned HTTP `404`
- direct editing `/version` is stale and missing required GPT/live-render flags

Current wired device state:

```bash
xcrun devicectl list devices
```

Result:

```text
charlie's iPhone: unavailable, iPhone 15 Pro
```

Staging deploy attempt:

```bash
gh workflow run "Cloud Edit Deploy Preflight" \
  --repo charlie2233/rork-hoopshighlights-ai_Final \
  --ref codex/phase-clip28-cloud-team-quick-scan \
  -f operation=deploy
```

Run:

```text
https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/26635719986
```

Result:

```text
failure before workflow steps started
```

Annotation:

```text
The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings
```

Impact:

- no Worker deploy occurred
- no Cloud Run editing deploy occurred
- no rollback version or Cloud Run revision was produced
- this is a GitHub account billing/spending-limit blocker, not a source-code test failure
