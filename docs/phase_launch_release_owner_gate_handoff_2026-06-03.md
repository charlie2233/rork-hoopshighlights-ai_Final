# Phase Launch release-owner gate handoff - 2026-06-03

## Purpose

This is the secret-safe external handoff for the remaining HoopClips internal TestFlight launch gates. It gives release owners or a browser agent exact actions to take without returning secrets, tokens, private key contents, base64 values, presigned URLs, or private video contents in chat.

## Current branch

- repo: `charlie2233/rork-hoopshighlights-ai_Final`
- branch: `codex/phase-clip1-gpt-led-highlight-editor`
- current recheck: 2026-06-07T06:01:11Z
- latest checked tip before this handoff refresh: `73c8dca8888e9f90d18faea4237cc7964789a96d`
- latest internal TestFlight upload proof: `27082807084`, success
- latest Release Secrets Preflight proof: `27084311582`, success

These green runs close the release-owner production cloud URL variable, release-secret preflight, and signed archive/upload proof for the current branch. They do not close installed TestFlight smoke or human label gates.

## Current resolved release-owner gates

- Production environment variables `HOOPS_CLOUD_ANALYSIS_BASE_URL` and `HOOPS_CLOUD_EDIT_BASE_URL` are present in GitHub `production`.
- Release Secrets Preflight `27084311582` completed successfully on `73c8dca8888e9f90d18faea4237cc7964789a96d`.
- Internal TestFlight upload `27082807084` completed successfully; no iOS upload-relevant files changed afterward.

## Release-owner actions

### 1. Production cloud URL variables

Status: resolved on 2026-06-07.

In GitHub environment `production`, these non-secret environment variables are now present:

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

### 3. Release Secrets Preflight

Status: resolved on 2026-06-07.

Latest green run:

```bash
gh run view 27084311582 --repo charlie2233/rork-hoopshighlights-ai_Final
```

- branch: `codex/phase-clip1-gpt-led-highlight-editor`
- head SHA: `73c8dca8888e9f90d18faea4237cc7964789a96d`
- conclusion: success
- URL: `https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/27084311582`

### 4. Signed archive/upload path

Status: resolved for current upload-relevant code on 2026-06-07.

Latest green run:

- run ID: `27082807084`
- head SHA: `8b4f349d841dd3110babfb1522d805e299dbc6a4`
- archive job conclusion: success
- upload job conclusion: success
- URL: `https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/27082807084`

Do not return signing certificate contents, `.p12` data, private keys, provisioning profile contents, issuer private key contents, API key values, or full JWTs if this path is rerun.

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

This release-owner handoff is closed for production cloud URL variables, Release Secrets Preflight, and signed archive/upload proof on the current branch. Installed TestFlight smoke and human labels remain tracked by their dedicated handoff docs.
