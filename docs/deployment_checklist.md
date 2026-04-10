# Deployment Checklist

## iOS

- Set signing/team values for release.
- Set RevenueCat production config.
- Set Google sign-in config.
- Set environment-specific cloud base URLs.
- Verify release build behavior on device.

## Cloudflare

- Verify Worker routes are deployed.
- Verify R2 buckets exist.
- Verify Queue bindings are live.
- Verify Durable Object namespace is configured.
- Verify D1 is provisioned and migrated.
- Verify callback auth is enabled.

## Inference

- Verify the Python GPU service image builds.
- Verify FFmpeg is available in the container.
- Verify source download, inference, and callback paths work.
- Verify model version is emitted in results.

## Dashboard

- Verify internal access protection is enabled.
- Verify dashboard reads from the Cloudflare control plane only.
- Verify no inference work runs in Vercel.

## Observability

- Verify Sentry DSNs are set for iOS, Worker, inference, and dashboard.
- Verify trace propagation is working.
- Verify sample-video smoke tests pass before cutover.

