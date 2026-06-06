# Build 15 archive signing recheck

Date: 2026-06-06
Branch: `codex/phase-clip1-gpt-led-highlight-editor`
Commit before workflow signing patch: `440f966d4b60042b7dc7bb572ee1e046d341b49f`

## What was attempted

Triggered the iOS internal TestFlight workflow on the launch branch with:

```bash
gh workflow run ios-testflight-upload.yml \
  --repo charlie2233/rork-hoopshighlights-ai_Final \
  --ref codex/phase-clip1-gpt-led-highlight-editor \
  -f operation=archive
```

Run:

- `27054133236`
- URL: `https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/27054133236`
- Head SHA: `440f966d4b60042b7dc7bb572ee1e046d341b49f`

## Result

The archive run failed in `Build signed internal staging archive`.

The following steps passed first:

- Required TestFlight inputs present
- Release secret mirror materialized
- Internal staging build settings verified
- App Store Connect API key materialized

Non-secret failure summary from logs:

```text
** ARCHIVE FAILED **
ios/HoopsClips.xcodeproj: error: Choose a certificate to revoke. Your account has reached the maximum number of certificates. To create a new one, you must choose a certificate to revoke.
ios/HoopsClips.xcodeproj: error: No profiles for 'atrak.charlie.hoopsclips' were found: Xcode couldn't find any iOS App Development provisioning profiles matching 'atrak.charlie.hoopsclips'.
```

## Repo-side diagnosis

A local build-settings probe showed the Release archive configuration resolves to development signing by default:

```text
CODE_SIGN_IDENTITY = Apple Development
CODE_SIGN_STYLE = Automatic
CURRENT_PROJECT_VERSION = 15
PRODUCT_BUNDLE_IDENTIFIER = atrak.charlie.hoopsclips
```

For internal TestFlight archive/upload, the workflow should use distribution signing. The workflow archive command was updated to pass:

```text
CODE_SIGN_IDENTITY="Apple Distribution"
```

## Remaining external signing blocker risk

Even after forcing distribution signing, Apple may still block automatic certificate/profile creation if the App Store Connect team has reached its certificate limit or lacks a usable distribution signing identity/profile for `atrak.charlie.hoopsclips`.

If the next archive attempt still fails with certificate-capacity or missing-profile errors, the required release-owner action is:

1. Revoke an unused Apple signing certificate or free capacity in the Apple Developer account.
2. Ensure a valid Apple Distribution certificate/profile exists for bundle id `atrak.charlie.hoopsclips`.
3. Rerun `ios-testflight-upload.yml` with `operation=archive`.
4. After archive metadata passes, rerun with `operation=upload` for internal TestFlight.

