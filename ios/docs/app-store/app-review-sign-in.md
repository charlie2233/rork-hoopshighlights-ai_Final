# App Review Sign-In Notes

Use these notes for App Store Connect > App Review Information > Sign-In Information.

## Review Account

- Username: use the exact review-only username stored in App Store Connect
- Password: use the exact review-only password stored in App Store Connect

Do not copy either credential into this repo or duplicate the password in the Notes field. HoopClips uses Firebase Authentication for Release email/password sign-in when `HOOPS_FIREBASE_AUTH_API_KEY` is configured. Before submitting, sign in once with the exact App Store Connect account in build 54 so the Firebase user is materialized and the credentials are proven.

## Reviewer Instructions

Paste this into App Review notes. The separate App Store Connect Sign-In Information fields already provide the username and password.

```text
Please use the provided test account to sign in.

Email/password sign-in is backed by Firebase Authentication in the Release build.

The public release build uses HoopClips cloud for video upload, AI analysis, AI edit planning, and final video rendering. The iOS app is the control surface for import, review, status, preview, save, and share.

Suggested review path:
1. Sign in with the provided review account.
2. Complete the sign-in prompt shown by the app.
3. Open Membership to view HoopClips Premium.
4. Use Apple's sandbox purchase flow for Premium Monthly.
5. Restore purchases from the paywall if needed.
6. Import a short basketball video from Photos or Files.
7. Accept the cloud AI prompt, choose the target team or All teams, then run analysis and wait for the generated clips.
8. Review generated clips.
9. Use AI Edit to generate a cloud-rendered highlight reel.
10. Preview, save to Photos, and share the highlight reel.

No external hardware, cloud dashboard, or admin access is required. The app may upload the selected source video to HoopClips cloud only after the reviewer accepts the in-app cloud AI prompt for team scan or analysis.
```

## Backend Account Requirement

`HOOPS_FIREBASE_AUTH_API_KEY` must be configured before public submission. If the Firebase account does not already exist, the app creates it on first email sign-in. For safest App Review behavior, authenticate once with the exact account stored in App Store Connect before submission. Record only the pass/fail result, never the credential values.
