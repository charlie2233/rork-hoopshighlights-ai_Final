# iOS App Store Connect Live Readiness Audit

Date: 2026-07-19

Branch: `codex/ios-store-connect-live-readiness-20260719`

## Scope

This audit reconciles the current iOS source, build 54 TestFlight evidence, the
public HoopClips legal pages, and the live App Store Connect record. It does not
submit the app, expose review credentials, or claim that source/build proof is
an installed-device or App Review result.

## Architecture And Brand

- Release remains `production_cloud_only` with no local render fallback.
- iOS is limited to import/upload, review, status, preview, save, share, and
  external-editor handoff. Cloud services own analysis, edit planning, and final
  rendering.
- The canonical iOS AppIcon is a valid 1024 x 1024 PNG without alpha.
- The macOS AppIcon and BrandMark source files are byte-identical to the iOS
  assets. No connected iPhone or separate macOS logo work is required.
- iOS and macOS share one backend accuracy report. A duplicate macOS labeling
  pass would not provide independent model evidence.

## Live App Store Connect Evidence

The authenticated in-app side browser showed:

- App Apple ID `6763813635`, version `1.0`, state `Prepare for Submission`.
- Build `1.0.0 (54)` is `VALID`, internal TestFlight, not expired, and has no
  non-exempt encryption declaration. It is not yet selected for the version.
- Both screenshot sets are empty. Media Manager explicitly accepts the prepared
  1320 x 2868 iPhone 6.9-inch and 2064 x 2752 iPad 13-inch assets.
- Subtitle, promotional text, description, keywords, and categories are blank.
- Support and marketing URLs are stale and must be replaced with the public
  Atrak HoopClips pages.
- App Review credential/contact fields are populated. Their values were not
  copied into git. The credential pair remains unverified against build 54.
- App Review notes are stale and incorrectly claim local analysis/export. The
  replacement notes accurately describe cloud upload, analysis, edit planning,
  rendering, preview, save, and share.
- Release is currently automatic; the prepared package calls for manual release.
- App Privacy has not been started and its policy URL is blank.
- Content Rights and Age Ratings are not configured.
- Base app price and app availability are not configured.
- Digital Services Act status is already configured as non-trader.
- `monthly_premium` is a one-month subscription, available in all countries or
  regions, with current pricing based at USD 9.99 and localized equivalents.
  It remains `Prepare for Submission` and must accompany the first app version.

No `Add for Review` action was taken.

## Public URLs

- Marketing: `https://atrak.dev/apps/hoopsclips/`
- Support: `https://atrak.dev/apps/hoopsclips/support.html`
- Privacy: `https://atrak.dev/apps/hoopsclips/privacy.html`
- Terms: `https://atrak.dev/apps/hoopsclips/terms.html`

The privacy page describes cloud video processing, providers, diagnostics,
purchase status, temporary render retention, and deletion requests. The terms
require uploaders to have permission from applicable athletes, guardians,
schools, teams, leagues, venues, broadcasters, and music owners.

## Prepared Privacy Declaration

Data is collected for App Functionality. No declared data is used for tracking.

| Data type | Linked to user | Tracking |
| --- | --- | --- |
| Email Address | Yes | No |
| Photos or Videos | Yes | No |
| User ID | Yes | No |
| Device ID | Yes | No |
| Purchase History | No | No |
| Customer Support | Yes | No |
| Product Interaction | No | No |
| Other Diagnostic Data | No | No |

The app privacy manifest covers the first-party collection map. RevenueCat's
bundled privacy manifest separately declares unlinked Purchase History for App
Functionality. Google Sign-In's bundled manifest declares no collected data or
tracking. The public policy also discloses Apple/Google authentication,
RevenueCat/Apple purchase handling, operational diagnostics, and cloud video
providers.

## Prepared Legal And Rating Answers

- Content Rights: `Yes`. HoopClips accesses user-selected footage and requires
  the uploader to hold all necessary rights and permissions.
- Age-rating feature questions: No parental controls, age assurance,
  unrestricted web access, broad in-app UGC distribution, social feed, direct
  messaging/chat, or advertising.
- Content-frequency questions: `None` based on the app's supplied content and
  intended private editing workflow.

These are prepared answers, not saved legal declarations. They require the
release owner's action-time confirmation in App Store Connect.

## Shared Accuracy Evidence

The completed shared iOS/macOS label bundle contains 43 reviewed clips from one
case and is launch-evidence eligible, but its current report fails:

- highlight precision: `0.1163` versus required `0.85`
- shot outcome evidence quality: `0.0` versus required `0.85`
- case coverage: `1` versus required `2`
- required positive, opponent, and defensive-event coverage is missing

This must not be described as an 85% pass. Before submission, either produce a
current passing shared backend report or record an explicit release-owner risk
acceptance for build 54. Do not repeat the labeling work for macOS.

## Remaining Submission Gates

1. Save the prepared listing, categories, URLs, cloud-only review notes, manual
   release mode, screenshots, build 54 selection, Free price, and availability.
2. Save and publish App Privacy after confirming the prepared declaration.
3. Save Content Rights and Age Ratings after release-owner confirmation.
4. Verify the exact App Store Connect review account in build 54 without copying
   credentials into the repository.
5. Run build 54 from TestFlight through real cloud upload, analysis, Review, AI
   Edit, render, preview, save, and share, or record an explicit waiver.
6. Resolve or explicitly accept the current shared backend accuracy failure.
7. Include `monthly_premium` with the first version submission.
8. Obtain explicit confirmation immediately before `Add for Review`.

Until these gates close, the package is prepared but the app is not ready to be
submitted for review.
