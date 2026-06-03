# Installed TestFlight Smoke Handoff - 2026-06-03

This handoff is for the person with access to a trusted physical iPhone and the
current internal TestFlight build. It does not mark the smoke gate complete.

Do not paste secrets, tokens, private keys, passwords, session cookies, base64
values, or full presigned URLs into chat, screenshots, notes, or logs.

## Current status

- Branch evidence head before this handoff: `b8f6c85`
- Latest safe checks at that head:
  - `Cloud Edit Deploy Preflight` run `26890738870`: `success`
  - `iOS Internal TestFlight Upload` codecheck run `26890742073`: `success`
- Installed TestFlight smoke: `unproven`
- Apple signing/current signed archive: externally blocked before this handoff
- Production cloud URL variables: still missing until the release owner sets:
  - `HOOPS_CLOUD_ANALYSIS_BASE_URL`
  - `HOOPS_CLOUD_EDIT_BASE_URL`
- Human-reviewed accuracy labels: still `0/54` complete

This smoke should run only after the tester has a processed current internal
TestFlight build installed on a trusted physical iPhone and the intended cloud
environment is confirmed.

## Prerequisites before running smoke

Confirm these non-secret facts first:

- Current internal TestFlight build is processed and installable.
- Tester iPhone is trusted, online, and can launch the installed TestFlight app.
- App build number and branch/SHA are known.
- Cloud analysis/edit base URLs for this build are confirmed by the release
  owner.
- Release Secrets Preflight is green for the environment used by the build, or
  the tester explicitly records that the smoke is internal-staging-only and not
  production-cutover evidence.
- The tester has at least one real basketball source video available in Photos
  or Files.

Do not run this as launch evidence against an old developer-installed build or a
historical TestFlight upload.

## Smoke path to execute

Run the full path on the physical iPhone:

1. Install HoopClips from TestFlight.
2. Cold launch the app.
3. Confirm legal links open.
4. Sign in or continue using the intended internal-test auth path.
5. Import a real basketball video from Photos.
6. Import or open a real basketball video from Files if available.
7. Confirm the app shows readable import/progress/recovery copy.
8. Run team scan or pre-analysis team choice.
9. Choose either a detected team or `All teams`.
10. Start cloud analysis.
11. Confirm analysis status stays cloud-owned and does not mention local
    analysis fallback, fake thinking, or ETA copy.
12. Open Review.
13. Confirm clip cards and controls are readable on the phone.
14. Keep/remove at least one clip if needed.
15. Go to Export or AI Edit.
16. Choose an edit intent/style and target length.
17. Render through the cloud backend.
18. Confirm work receipt/timeline/status is readable.
19. Preview the finished MP4.
20. Download or save the saved reel.
21. Share/open the MP4 through the iOS share sheet.
22. If available, open/share to at least one editor target such as Files,
    Photos, CapCut, iMovie, or Adobe.
23. Request one revision such as `More Hype`, `Shorter`, or a similar allowed
    edit note.
24. Preview and share/open the revised MP4.
25. Close and reopen HoopClips.
26. Use History to resume the project, watch source video, watch saved reel,
    share saved reel, and delete only if cleanup is intended.

## Required observation checks

Watch for and record any issue in these areas:

- Hidden or clipped labels on small phone layout.
- Dynamic Type or long text pushing buttons off-screen.
- Confusing status copy.
- Fake `thinking`, vague ETA, or `hang tight` copy.
- Any suggestion that production analysis or rendering happened locally on iOS.
- Import hanging after long Photos or Files import.
- App backgrounding breaking import, analysis, render, or history recovery.
- Saved reel preview missing or share sheet opening without an MP4.
- Download/save to Photos failure.
- Share/open-in targets missing or receiving the wrong file.
- Revision render replacing or losing the wrong saved reel.
- Any token, URL query string, object key, or credential appearing in visible UI
  or logs.

## Evidence to report back

Report only non-secret evidence:

- TestFlight build number.
- App version/build if visible.
- Commit SHA or branch if known.
- iPhone model and iOS version.
- Cloud environment label used for the build, such as internal staging or
  production.
- Whether each smoke path step passed or failed.
- Any failing step name and short non-secret description.
- Whether the rendered MP4 previewed.
- Whether save/download succeeded.
- Which share/open-in targets were verified.
- Whether History resume/source/saved-reel/share/delete controls worked.
- Screenshot names or local file paths for redacted screenshots, if collected.

Do not report:

- Login credentials.
- Passwords.
- API keys.
- Tokens.
- Private keys.
- Base64 secret values.
- Full presigned URLs.
- Upload, source, render, or object-key URLs.
- Personal contact/payment identifiers.

## Completion criteria

The installed TestFlight smoke blocker can be marked resolved only after:

- A current internal TestFlight build is installed from TestFlight, not from a
  local developer install.
- The full import -> team choice -> cloud analysis -> Review -> cloud render ->
  preview -> download/save -> share/open-in -> revision -> History path passes.
- Failures are either fixed and rerun or explicitly documented as launch
  blockers.
- `ios/docs/reports/release-device-smoke-report.md` is updated with the passing
  build number, device, date, and non-secret evidence.
- The current readiness snapshot is updated with the passing smoke evidence.

Until then, internal TestFlight readiness remains incomplete.

## 2026-06-03 current branch proof before installed-device smoke

Current branch tip before this handoff refresh was
`cc2cac0 chore: clarify label review checkpoint copy`.
Safe branch proof on that commit:

- Cloud Edit Deploy Preflight run `26899359298`: `success`
- `iOS Internal TestFlight Upload` codecheck run `26899359347`: `success`

This proof only covers remote branch preflight/codecheck. Installed TestFlight
smoke is still `unproven` until a trusted device installs the TestFlight build
and records the full import -> cloud analysis -> AI Edit -> MP4 preview ->
download/share/open-in path with non-secret evidence.

Keep preserving unrelated local files. The current checkout still has untracked
root Xcode project folders that must not be staged unless explicitly requested.

## 2026-06-03 current branch proof refresh - 2f2ffae

This refresh updates the branch proof available before a trusted-device installed TestFlight smoke. It does not mark installed smoke complete.

Current branch: `codex/phase-launch-proof-next`
Current pushed tip: `2f2ffae`

Fresh no-secret workflow proof on this tip:

- `Cloud Edit Deploy Preflight` run `26911966539`: `success`
- `iOS Internal TestFlight Upload` with `operation=codecheck` run `26911966470`: `success`

What this proof covers:

- The launch branch still passes the safe cloud-edit preflight lane.
- The launch branch still passes the safe iOS TestFlight workflow codecheck lane.
- The latest handoff docs and iOS backend-status copy guardrails are present on the pushed branch.

What this proof does not cover:

- It is not a signed App Store Connect archive/upload proof.
- It is not proof that the current internal TestFlight build is processed or installable.
- It is not installed-app smoke evidence from a trusted iPhone.
- It is not production cloud readiness proof; production `HOOPS_CLOUD_ANALYSIS_BASE_URL` and `HOOPS_CLOUD_EDIT_BASE_URL` are still not visible in GitHub production variables.
- It is not GPT clipping quality proof; the current label bundle is still `0/54` complete and `launchEvidenceEligible=false`.

Trusted-device tester should use the smoke steps above only after release owner confirms the intended TestFlight build is installed from TestFlight and the intended backend environment is selected. Record non-secret evidence only: build number, backend host name, workflow run IDs, visible app status copy, screenshots/video timestamps, and pass/fail notes. Do not return secrets, tokens, private key contents, presigned URLs, private video contents, or full storage object URLs.
