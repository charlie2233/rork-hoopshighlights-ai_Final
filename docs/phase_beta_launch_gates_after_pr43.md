# Beta Launch Gate Status After PR #43

Date: 2026-07-05

## Summary

PR #43 is merged into `main` at `449cd0907f62dd728741fb43a81e4f9e3815a4ff`. The enhancement integration workstream is complete on `main`; do not redo that integration.

Current `main` is `4540381752db2eb5ac22442c8f49971e0d49f6cb` after the launch UI cleanup and build `44` bump. The remaining beta launch blocker is Apple certificate/provisioning state during TestFlight upload. The cloud integration, staging deploy, live version proof, deterministic Worker render path, and build `44` archive are proven.

## Confirmed Main State

- PR #43: merged at `2026-06-28T09:00:46Z`.
- Integration merge commit: `449cd0907f62dd728741fb43a81e4f9e3815a4ff`.
- Current main commit: `4540381752db2eb5ac22442c8f49971e0d49f6cb`.
- PR #46 and PR #47: merged; launch proof/testing UI hidden, Settings Formspree support retained, and Settings support banners auto-dismiss.
- PR #48: merged; next TestFlight build bumped to `1.0.0 (44)`.
- Branch posture: `main` contains the integration; follow-up work should stay scoped to launch gates, docs, signing, and smoke proof.

## GitHub Actions State

- `Cloud Edit Deploy Preflight` push run `28317247578`: success on `449cd0907f62dd728741fb43a81e4f9e3815a4ff`.
- `iOS Internal TestFlight Upload` push/codecheck run `28317247560`: success on `449cd0907f62dd728741fb43a81e4f9e3815a4ff`.
- `Cloud Edit Deploy Preflight` credential-check run `28317383878`: success on `449cd0907f62dd728741fb43a81e4f9e3815a4ff`.
- `Cloud Edit Deploy Preflight` deploy run `28317412159`: success on `449cd0907f62dd728741fb43a81e4f9e3815a4ff`.
- `iOS Internal TestFlight Upload` upload run `28470081179`: success for build `43`.
- `iOS Internal TestFlight Upload` archive run `28756536677`: success for build `44` on `4540381752db2eb5ac22442c8f49971e0d49f6cb`.
- `iOS Internal TestFlight Upload` upload run `28756673502`: failed during signed archive because Apple certificate limit/provisioning is not ready on the fresh upload runner.

## Staging Deploy And Version Proof

The staging deploy passed after PR #43 was merged. The live Worker `/v1/editing/version` and direct editing `/version` checks reported the merged SHA and the expected AI Edit/GPT feature flags.

Operator rerun command:

```bash
python3 scripts/staging_version_probe.py --expected-git-sha 449cd0907f62dd728741fb43a81e4f9e3815a4ff --json
```

## Deterministic Render Smoke

The deterministic Worker render smoke passed through the active Worker render path after the merge. It produced a valid MP4 with H.264 video and AAC audio.

This proves the Worker/direct editing render contract for a deterministic edit plan. It does not replace an installed TestFlight run on real basketball footage.

## Synthetic GPT Smoke Classification

The synthetic GPT iOS client smoke uploaded generated test video and received `empty_clip_list` from `POST /v1/edit-jobs`.

Classification: expected synthetic-video no-clips case, not current evidence of a Worker/direct editing contract bug.

Reasoning:

- The smoke source is synthetic test video, not real basketball footage.
- Backend tests intentionally require `empty_clip_list` when GPT rejects every candidate and no render-worthy clips remain.
- The deterministic Worker render smoke passed with a valid edit plan against the same deployed path.
- Real launch proof must use real basketball footage and the installed TestFlight app.

## iOS Signing/TestFlight Blocker

Build `44` archive run `28756536677` passed and verified bundle ID `atrak.charlie.hoopsclips`, version `1.0.0`, build `44`, environment `internal_staging`, and cloud launch mode `internal_only`.

Build `44` upload run `28756673502` then failed while re-archiving on a fresh runner after CI materialized the required non-secret and secret inputs. The failure is Apple account signing state:

- Apple account has reached the maximum number of certificates and requires choosing a certificate to revoke.
- No matching iOS App Development provisioning profile was available for bundle ID `atrak.charlie.hoopsclips`.

Use `TESTFLIGHT_BLOCKER.md` as the account-holder handoff.

## Real-Basketball TestFlight Smoke Checklist

Run this only after the archive/upload workflow succeeds and App Store Connect finishes processing the internal TestFlight build.

1. Install the latest internal TestFlight build on a trusted iPhone.
2. Confirm the build is for merge SHA `449cd0907f62dd728741fb43a81e4f9e3815a4ff` or a documented later launch-gate SHA.
3. Confirm the app is in internal staging mode and points to `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`.
4. Upload a real basketball video from Photos or Files.
5. Wait for upload completion and `proxy_ready`.
6. Run team scan and select/confirm the target team if prompted.
7. Start cloud analysis and wait for completion.
8. Open Review and confirm real basketball clips are visible.
9. Keep/discard clips as needed without forcing weak clips into the edit.
10. Open AI Edit.
11. Choose a style and target length.
12. Create the AI edit plan.
13. Request cloud render and wait for the render to finish.
14. Download the final MP4.
15. Preview the downloaded MP4 in-app.
16. Save the MP4 to Photos.
17. Use the share sheet to open/export the MP4 to Files and at least one editor target such as CapCut, iMovie, or Adobe if installed.
18. Request one revision, such as higher energy or shorter length.
19. Render, download, preview, and share/open the revised export.
20. Record build number, SHA, workflow run IDs, source video duration, pass/fail notes, and screenshots/log snippets with no secrets.

## After Apple Repair

Build `44` already has a passing archive-only run. After the Apple certificate/provisioning issue is repaired, rerun upload:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=upload
```

Then complete the real-basketball TestFlight smoke checklist above and update `ios/docs/reports/release-device-smoke-report.md` with the result.
