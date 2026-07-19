# HoopClips App Store Submission Package

This folder keeps App Store listing material beside the canonical iOS target.
It does not contain signing credentials, review passwords, or App Store Connect
API keys.

## Current Package

- `app-store-metadata-en-US.json`: structured English listing draft, brand
  asset paths, screenshot manifest, privacy copy, and explicit operator gates.
- `screenshots/en-US/iphone-6.9`: current 1320 x 2868 iPhone frames.
- `screenshots/en-US/ipad-13`: current 2064 x 2752 iPad frames.
- `app-review-sign-in.md`: review-account and reviewer-flow instructions. The
  real password belongs only in App Store Connect.

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

- `https://atrak.dev/apps/hoopsclips/support.html`
- `https://atrak.dev/apps/hoopsclips/privacy.html`
- `https://atrak.dev/apps/hoopsclips/terms.html`

`--require-ready` intentionally fails until App Review contact information, age
rating, content rights, and DSA status are resolved.

Simulator screenshot proof is not physical-device or installed-TestFlight
proof. The submitted Release build remains cloud-only; no local analysis or
render fallback is represented here.
