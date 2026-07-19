# HoopClips App Store Submission Package

This folder keeps App Store listing material beside the canonical iOS target.
It does not contain signing credentials, review passwords, or App Store Connect
API keys.

## Current Package

- `app-store-metadata-en-US.json`: structured English listing draft, brand
  asset paths, screenshot manifest, privacy declaration map, live-account audit,
  and explicit operator gates.
- `screenshots/en-US/iphone-6.9`: current 1320 x 2868 iPhone frames.
- `screenshots/en-US/ipad-13`: current 2064 x 2752 iPad frames.
- `app-review-sign-in.md`: review-account and reviewer-flow instructions. The
  real password belongs only in App Store Connect.
- `shared-backend-accuracy-2026-07-19.json`: current aggregate launch-gate
  evidence shared by iOS and macOS. It reuses the completed iOS human labels,
  remaps stale cloud prediction identifiers one-to-one by reviewed time overlap,
  does not create a duplicate Mac labeling set, and truthfully remains failed.

The screenshots use the current Debug-only seeded workflow so they can show the
real Review-to-AI-Edit product UI without uploading user footage or exposing
cloud credentials. Only polished AI Edit frames are included; synthetic black
video-preview frames remain test evidence and are not part of this listing set.

The active App Store icon is the canonical iOS asset at
`ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`. The
matching in-app brand mark is in `BrandMark.imageset/brand_mark.png`.

The final screenshot order was visually reviewed on July 19, 2026. The package
uses `Photo & Video` as the primary category because editing is the core app
function, with `Sports` as the secondary basketball category. This follows
Apple's category guidance:
`https://developer.apple.com/app-store/categories/`.

## Validate

Run the structural package check:

```bash
python3 scripts/validate_app_store_submission_package.py
```

This exits successfully when the local package and image specifications are
valid, while still printing unresolved external/operator gates. Before an
actual App Store submission, require every gate to be closed:

```bash
python3 scripts/validate_app_store_submission_package.py --require-ready
```

The public product-specific pages are live and recorded in the metadata:

- `https://atrak.dev/apps/hoopsclips/`
- `https://atrak.dev/apps/hoopsclips/support.html`
- `https://atrak.dev/apps/hoopsclips/privacy.html`
- `https://atrak.dev/apps/hoopsclips/terms.html`

## Production Store Candidate Lane

The public Store candidate uses
`.github/workflows/ios-app-store-production-upload.yml`, the `production`
GitHub environment, `Release.xcconfig`, and reserved build number 56. It never
uses `InternalStaging.xcconfig` and its export options do not set
`testFlightInternalTestingOnly`.

The workflow offers three deliberate operations:

- `config-check`: validates production-shaped cloud URLs and Release settings;
  no archive or upload.
- `archive`: creates and verifies a signed production-cloud archive; no upload.
- `upload`: archives, verifies, and uploads the candidate; it never performs
  `Add for Review`.

Before any dispatch, the production environment must have approved non-staging
cloud URL variables and the App Store Connect secret names
`APP_STORE_CONNECT_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID`, and
`APP_STORE_CONNECT_API_KEY_BASE64`. Do not copy values into git. The July 19
audit found staging markers in both production URL variables and found those
three upload secret names missing, so the lane is intentionally blocked.

## Live App Store Connect State

The in-app side browser audit and read-only App Store Connect status run
`29706397510` on July 19, 2026 established the following without copying
credentials or private contact values into the repository:

- App version `1.0` remains `Prepare for Submission`.
- TestFlight build `1.0.0 (55)` is valid internal-staging evidence. Its archive
  uses `InternalStaging.xcconfig`, `internal_staging`, and the staging Worker, so
  it is not eligible for public App Store review and must not be selected.
- Production-cloud build `1.0.0 (56)` is reserved as the next Store candidate.
  Its fail-closed workflow is prepared, but archive/upload remains blocked while
  production cloud URL variables still carry staging markers and App Store
  Connect upload secrets are absent from the production GitHub environment.
- The iPhone 6.9-inch and iPad 13-inch Media Manager slots accept the prepared
  screenshot dimensions, but both sets remain unuploaded.
- Listing copy, categories, privacy policy, base app price, app availability,
  age rating, and content rights remain unsaved.
- Existing App Review credential and contact fields are populated but must be
  verified against the eventual valid production-cloud Store candidate. Their
  values remain App Store Connect-only.
- Existing App Review notes incorrectly describe local processing and must be
  replaced with the cloud-only notes in `app-review-sign-in.md`.
- Digital Services Act status is configured as non-trader.
- `monthly_premium` is configured for one month, priced from USD 9.99 with
  localized equivalents, available in all countries or regions, and remains
  `Prepare for Submission` for inclusion with the first app version.

`--require-ready` intentionally fails until production endpoint cutover, the
production Store archive/upload, listing, screenshots, build selection,
free-app pricing and availability, privacy declaration, age rating, content
rights, review-account login, first-subscription inclusion, installed exact-
candidate cloud-flow smoke, and shared backend accuracy gate are resolved. The
final `Add for Review` action is a separate release-owner confirmation.

Simulator screenshot proof is not physical-device or installed-TestFlight
proof. The submitted Release build remains cloud-only; no local analysis or
render fallback is represented here. A connected iPhone is not needed for the
macOS app or for App Store metadata entry; it is needed only for the independent
installed iOS/TestFlight smoke. iOS and macOS use the same cloud-backend accuracy
evidence, so do not create a duplicate macOS labeling set.
