# Phase Launch release-owner gate handoff - 2026-06-03

## Purpose

This is the secret-safe external handoff for the remaining HoopClips internal TestFlight launch gates. It gives release owners or a browser agent exact actions to take without returning secrets, tokens, private key contents, base64 values, presigned URLs, or private video contents in chat.

## Current branch

- repo: `charlie2233/rork-hoopshighlights-ai_Final`
- branch: `codex/phase-launch-proof-next`
- current recheck: 2026-06-03T21:10:03Z
- latest checked tip before this handoff refresh: `bd329f7a536fa7456093f7b27ff9c026b3043a96`
- latest safe cloud preflight on that tip: `26912829790`, success
- latest no-secret iOS codecheck on that tip: `26912829701`, success

These green runs are useful current branch proof, but they do not close production URL/secrets, Release Secrets Preflight, signed archive/upload, installed TestFlight smoke, or human label gates.

## Release-owner actions

### 1. Set production cloud URL variables

In GitHub environment `production`, confirm or set these non-secret environment variables:

- `HOOPS_CLOUD_ANALYSIS_BASE_URL`
- `HOOPS_CLOUD_EDIT_BASE_URL`

Return only:

- whether each variable exists
- whether each value points to the intended production endpoint
- the hostname only if needed for review

Do not return full URLs if they contain private query strings, credentials, tokens, or presigned parameters.

### 2. Confirm production secret names and validity

Current visible production secret names include:

- `HOOPS_DEVELOPMENT_TEAM`
- `HOOPS_FIREBASE_AUTH_API_KEY`
- `HOOPS_GOOGLE_CLIENT_ID`
- `HOOPS_GOOGLE_REVERSED_CLIENT_ID`
- `HOOPS_REVENUECAT_API_KEY`
- `HOOPS_SENTRY_DSN`

Release owners must confirm that required values are current and usable. Return only:

- secret name
- present/missing
- rotation date or update date if visible
- whether the owner confirms the value is valid

Do not return secret values.

### 3. Rerun Release Secrets Preflight

Only after production variables/secrets are fixed or explicitly confirmed, rerun:

```bash
gh workflow run release-secrets-preflight.yml --ref codex/phase-launch-proof-next
```

Then report:

- run ID
- branch
- head SHA
- conclusion
- URL

Latest known status before this handoff: `26884199422`, failure, head `86fdc33`.

### 4. Run signed archive/upload path

Only after signing, profile, App Store Connect, and release-secret checks are ready, run the signed TestFlight/archive operation using the repo workflow controls. Report only:

- run ID
- build number
- archive job conclusion
- upload job conclusion
- App Store Connect processing status if visible
- TestFlight build availability status

Do not return signing certificate contents, `.p12` data, private keys, provisioning profile contents, issuer private key contents, API key values, or full JWTs.

### 5. Complete installed TestFlight smoke

On a trusted device, install the TestFlight build and run the full launch smoke:

- import real basketball footage
- choose team/edit intent
- upload to cloud backend
- review generated clips with readable controls
- receive finished MP4
- preview finished MP4
- download/export
- share or open in common editors such as Files, Photos, CapCut, iMovie, or Adobe

Return only:

- build number
- TestFlight version
- device model
- iOS version
- tester initials/name
- timestamp
- pass/fail per step
- non-secret issue notes

Do not upload private source video, finished MP4, or presigned media URLs into chat unless explicitly requested and cleared.

### 6. Complete human accuracy labels

Use the local reviewer bundle already generated on this workstation:

```text
/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle_launch_current_reduced/team_highlight_label_review.html
```

Current reduced review status remains `0/18` complete. Launch evidence requires:

- `status=complete`
- `launchEvidenceEligible=true`
- `completeClipCount=54`
- `incompleteClipCount=0`

Return only:

- completed count
- remaining count
- downloaded label bundle file path
- whether any clips need second review

Do not paste full label JSON unless explicitly requested.

## Completion rule

This release-owner handoff remains open until production cloud URLs/secrets, Release Secrets Preflight, signed archive/upload, installed TestFlight smoke, and human labels are all proven current on the launch branch.
