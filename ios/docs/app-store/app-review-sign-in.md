# App Review Sign-In Notes

Use these notes for App Store Connect > App Review Information > Sign-In Information.

## Review Account

- Username: `appreview@hoopsclips.app`
- Password: use a strong review-only password entered directly in App Store Connect

Do not commit the real App Review password to the repo. hoopclips uses Firebase Authentication for Release email/password sign-in when `HOOPS_FIREBASE_AUTH_API_KEY` is configured. Before submitting, sign in once with this account in the Release app so the Firebase user is materialized and visible in Firebase Authentication.

## Reviewer Instructions

Paste this into App Review notes and replace `<APP_REVIEW_PASSWORD>` only inside App Store Connect:

```text
Please use the provided test account to sign in.

Username: appreview@hoopsclips.app
Password: <APP_REVIEW_PASSWORD>

Email/password sign-in is backed by Firebase Authentication in the Release build.

The public release build uses on-device video analysis only. Cloud ML is intentionally disabled for this launch.

Suggested review path:
1. Sign in with the provided review account.
2. Enter the in-app demo verification code.
3. Open Membership to view hoopclips Premium.
4. Use Apple's sandbox purchase flow for Premium Monthly.
5. Restore purchases from the paywall if needed.
6. Import a short basketball video from Photos or Files.
7. Run on-device analysis.
8. Review generated clips.
9. Export and save the highlight reel.

No external hardware, cloud dashboard, or admin access is required.
```

## Backend Account Requirement

`HOOPS_FIREBASE_AUTH_API_KEY` must be configured before public submission. If the Firebase account does not already exist, the app creates it on first email sign-in. For safest App Review behavior, create it once yourself before submitting.
