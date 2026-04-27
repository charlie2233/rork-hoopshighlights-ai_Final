# Firebase Auth Setup for HoopsClips

HoopsClips uses Firebase Authentication REST APIs for real email/password accounts in Release builds. This keeps App Review credentials real without adding a Firebase SDK dependency to the iOS target.

## Why Firebase Auth

- Email/password accounts are stored in a real backend and can sign in on any device.
- The app can create the account on first email sign-in if it does not already exist.
- The only app secret required is the Firebase Web API key, injected as `HOOPS_FIREBASE_AUTH_API_KEY`.

## Firebase Console Steps

1. Open Firebase Console and create or select the HoopsClips project.
2. Add an iOS app with bundle ID `atrak.charlie.hoopsclips`.
3. Open **Authentication**.
4. Open **Sign-in method**.
5. Enable **Email/Password**.
6. Open **Project settings**.
7. Copy the project **Web API Key**.

## GitHub Production Secret

Add this secret to the GitHub Actions `production` environment:

```bash
gh secret set HOOPS_FIREBASE_AUTH_API_KEY -e production -b "$HOOPS_FIREBASE_AUTH_API_KEY"
```

`Release Secrets Preflight` now fails if this value is missing.

## Local Smoke Mirror

Add the same value to the local smoke environment before regenerating `LocalSecrets.xcconfig`:

```bash
export HOOPS_FIREBASE_AUTH_API_KEY="..."
./ios/scripts/materialize_local_secrets.sh
```

Do not commit `LocalSecrets.xcconfig`.

## App Review Account

Use a real email/password pair in App Store Connect. Before submitting, sign in once with that pair in the Release build so the Firebase account is materialized and visible in Firebase Authentication.

Recommended username:

```text
appreview@hoopsclips.app
```

Use a strong review-only password and store it only in App Store Connect.

## Validation

- `Release Secrets Preflight` passes.
- Settings > Launch Status in DEBUG shows `Email Auth = Ready`.
- Email sign-in with the App Review credentials succeeds on at least one physical device.
- The same credentials sign in again after reinstall or on a second device.
