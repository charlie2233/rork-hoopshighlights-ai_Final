# App Review Sign-In Notes

Use these notes for App Store Connect > App Review Information > Sign-In Information.

## Review Account

- Username: `appreview@hoopsclips.app`
- Password: use a strong review-only password entered directly in App Store Connect

Do not commit the real App Review password to the repo. The current HoopsClips email sign-in path creates the local app user on first sign-in and accepts any non-empty email with a password of at least 6 characters.

## Reviewer Instructions

Paste this into App Review notes and replace `<APP_REVIEW_PASSWORD>` only inside App Store Connect:

```text
Please use the provided test account to sign in.

Username: appreview@hoopsclips.app
Password: <APP_REVIEW_PASSWORD>

After email sign-in, the app shows an in-app demo verification code. Enter that displayed 6-digit code to complete verification.

The public release build uses on-device video analysis only. Cloud ML is intentionally disabled for this launch.

Suggested review path:
1. Sign in with the provided review account.
2. Enter the in-app demo verification code.
3. Open Membership to view HoopsClips Premium.
4. Use Apple's sandbox purchase flow for Premium Monthly.
5. Restore purchases from the paywall if needed.
6. Import a short basketball video from Photos or Files.
7. Run on-device analysis.
8. Review generated clips.
9. Export and save the highlight reel.

No external hardware, cloud dashboard, or admin access is required.
```

## Why No Server-Side Account Setup Is Needed

HoopsClips currently uses local app auth for email sign-in. There is no production user database row to pre-create for the App Review account. The reviewer account is materialized on the review device when Apple signs in with the provided email and password.
