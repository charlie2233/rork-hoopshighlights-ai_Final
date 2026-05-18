# Phase UX5 RevenueCat Pro Subscription

## Branch

- Branch: `codex/phase-ux5-revenuecat-pro-subscription`
- Base commit: `f2eff49`
- Scope: wire real HoopClips Pro purchase/restore entitlement flow through RevenueCat/App Store in-app purchase.

## Payment Routing Decision

HoopClips Pro unlocks digital app functionality: priority AI Edit rendering, cleaner exports, revision limits, storage limits, and template access. For the iOS app, the compliant primary path is App Store in-app purchase with RevenueCat entitlement handling.

Stripe was reviewed as a fallback, but no Stripe product, price, Checkout Session, or Payment Link was created in this branch. Stripe remains appropriate for a future web/admin subscription surface, but the iOS in-app Pro unlock should use App Store purchase unless a separately approved external-purchase entitlement/cutover is made.

Reference points:

- Apple App Review Guidelines: digital goods and app functionality generally use in-app purchase, with limited external purchase exceptions by storefront/entitlement: https://developer.apple.com/app-store/review/guidelines/
- RevenueCat identifying customers: app-owned user IDs can be passed with `logIn()` after SDK configuration: https://www.revenuecat.com/docs/customers/identifying-customers
- RevenueCat customer info: apps should refresh customer info when users access premium content, and should provide restore purchases: https://www.revenuecat.com/docs/customers/customer-info

## Implemented

- `SubscriptionManager` now syncs authenticated HoopClips users into RevenueCat with a stable hashed App User ID.
- Anonymous/signed-out users are forced back to non-Pro locally so a prior account does not leak Pro UI state.
- Purchase and restore update the configured `pro` entitlement from `CustomerInfo`.
- `ContentView` now syncs RevenueCat identity when the authenticated user changes.
- Export AI Edit Pro upsells now open the real `PaywallView` path instead of staying informational only.
- Locked Pro AI Edit templates still do not render; they present Pro info and can route to the App Store paywall.
- Paywall copy now matches AI Edit Pro value: priority cloud edit, clean 1080p exports, more revisions/storage, and Pro template packs.
- Subscription policy copy now uses HoopClips Pro language and AI Edit benefits.

## RevenueCat Contract

Expected RevenueCat/App Store setup:

- RevenueCat API key: `HOOPSRevenueCatAPIKey`
- Entitlement ID: `pro`
- Offering: current offering with at least one monthly package
- App Store product display name: `Pro Monthly`
- Restore purchases: visible in paywall

RevenueCat App User ID format:

```text
hoops_<auth_method>_<sha256_of_hoopclips_user_id>
```

This avoids raw email/phone/user identifiers in RevenueCat while keeping identity stable for restore/support.

## Stripe Fallback Status

Not implemented in-app.

If a future web subscription fallback is approved, use Stripe Billing APIs with Checkout Sessions and Customer Portal. Do not add a Stripe Payment Link inside the iOS app to unlock Pro digital features without a separate App Store policy review and storefront-specific external-purchase decision.

## Validation

```sh
git diff --check
```

Passed.

```sh
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-ux5-dd \
  build CODE_SIGNING_ALLOWED=NO
```

Passed: `/tmp/hoopclips-ux5-build.log` ended with `** BUILD SUCCEEDED **`.

```sh
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-ux5-dd \
  build-for-testing CODE_SIGNING_ALLOWED=NO
```

Passed: `/tmp/hoopclips-ux5-bft.log` ended with `** TEST BUILD SUCCEEDED **`.

## Remaining Blockers

- RevenueCat current offering/product must exist in the target project for live purchase UI to load.
- App Store sandbox purchase/restore smoke was not run in this branch because it requires App Store Connect sandbox credentials and a configured product.
- Server-side Pro policy trust should eventually verify entitlement state with RevenueCat/webhook/backend state before broad external beta.
- Stripe web subscription fallback is intentionally not created here.
- Production config placeholders remain separate release-ops gates.

## No Local Rendering

This branch only changes subscription entitlement handling and purchase UX. It does not add local video analysis, local edit planning, or local AVFoundation production rendering.
