# Phase Launch6 Backend Config Preflight

Date: 2026-05-22
Branch: `codex/phase-launch6-backend-config-preflight`

## Scope

This branch adds a static, no-secret launch preflight for the backend and app configuration required before an internal iOS TestFlight smoke. It does not deploy, render, analyze video, read operator-held secrets, print R2 credentials, or print presigned URLs.

The preflight is intentionally conservative: it proves staging/internal-beta wiring where it can inspect source-controlled config, and it records production cutover gaps as warnings instead of claiming production readiness.

## What It Checks

- Control Plane Wrangler staging worker, R2 buckets, D1 binding, queue/DLQ wiring, required Worker secret names, and observability.
- Editing Cloud Run staging service name, staging R2 buckets, AI Edit kill-switch substitutions, environment mappings, required secret names, and ingress posture.
- Cloud deploy workflow coverage for secret presence checks, Wrangler read/deploy/rollback commands, dry-run, and GCP Workload Identity inputs.
- Release workflow cloud-off gates for App Store/TestFlight Release builds.
- iOS Release and InternalStaging xcconfig posture.
- Editing service feature flag exposure through `/version`.
- Event logging and presign logging guards that avoid URL/secret/object-key leakage.
- Launch docs/config files for literal secret-like values and unsafe production-readiness claims.

## Commands And Evidence

Static preflight:

```bash
python3 scripts/launch_backend_config_preflight.py
```

Result:

```text
HoopClips backend/config launch preflight
pass=54 warn=12 fail=0
```

Machine-readable mode:

```bash
python3 scripts/launch_backend_config_preflight.py --json
```

Result:

```text
status=pass
summary pass=54 warn=12 fail=0
```

Focused unit tests:

```bash
python3 -m unittest scripts.test_launch_backend_config_preflight -v
```

Result:

```text
Ran 2 tests in 0.006s
OK
```

Python syntax check:

```bash
python3 -m py_compile scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py
```

Result: passed with exit code 0.

Control-plane typecheck:

```bash
npm --prefix services/control-plane run typecheck
```

Result: `tsc -p tsconfig.json --noEmit` passed with exit code 0.

iOS Debug simulator build:

```bash
XcodeBuildMCP build_sim -skipPackagePluginValidation
```

Result: succeeded for scheme `HoopsClips` on simulator `7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2`.

iOS build-for-testing:

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-derived-data -skipPackagePluginValidation build-for-testing
```

Result: `TEST BUILD SUCCEEDED`.

Git whitespace hygiene:

```bash
git diff --check
```

Result: passed with exit code 0.

ASCII scan over changed files:

```bash
rg -n --pcre2 '[^\x00-\x7F]' scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py docs/phase_launch6_backend_config_preflight.md services/control-plane/README.md
```

Result: no matches.

Keyword leak scan over changed files:

```bash
rg -n -i 'presigned|secret|token|r2|api[_-]?key|access[_-]?key|private[_-]?key|dsn|https?://[^[:space:]\"]+|downloadUrl|uploadUrl' scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py docs/phase_launch6_backend_config_preflight.md services/control-plane/README.md
```

Result: expected config-name, placeholder, and documentation references only; no R2 credential values, no presigned URLs, and no secret literals were added.

## Current Warnings

- Production Worker cutover remains blocked because `env.production` is absent from the Wrangler config.
- Top-level Worker D1/R2 placeholders remain present; internal beta must use `env.staging`.
- AI Edit and live render default enabled in staging Cloud Build substitutions; verify this is intentional before a real deploy.
- Editing Cloud Build does not configure backend Sentry DSN, Statsig as a remote flag source, or a RevenueCat REST verifier secret.
- Staging Cloud Run allows unauthenticated ingress and relies on shared-secret enforcement plus Worker mediation.
- Launch docs still record production cutover blockers and missing CI deploy credential proof.

## Screenshots And Job IDs

No screenshots, deploy job IDs, render job IDs, or smoke job IDs were produced by this branch. This phase is a source-controlled configuration preflight only.

## Internal Launch Status

This branch improves launch readiness evidence, but it does not make HoopClips ready for internal launch by itself.

Remaining blockers:

- Real TestFlight post-install smoke on an installed app: upload/import, cloud analysis, Review, Export, AI Edit render, preview, More Hype revision, revised preview, share/open-in.
- Real Cloudflare/GCP staging deploy and rollback proof with `CLOUDFLARE_API_TOKEN` and GCP Workload Identity inputs configured in GitHub.
- Backend Sentry DSN, Statsig production flag source, and RevenueCat verifier secret decisions before production cutover.
- Production backend cutover remains explicitly blocked until internal beta proof is complete.
