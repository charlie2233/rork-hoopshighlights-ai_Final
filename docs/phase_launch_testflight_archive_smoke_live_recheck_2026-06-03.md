# Phase Launch TestFlight archive and installed smoke live recheck - updated 2026-06-06

## Scope

This is a metadata-only recheck of the current launch branch workflow proof. It
does not run local tests, upload to App Store Connect, install TestFlight, or
claim device smoke.

## Current branch proof

Current branch:

- branch: `codex/phase-clip1-gpt-led-highlight-editor`
- latest documented deploy head: `dd860a62a4a012867b30099fc886c7530aaa16ff`

Latest useful cloud deploy proof:

- Cloud Edit Deploy Preflight run `27055102528`
- conclusion: `success`
- Worker and editing `/version` probes match the deployed SHA

Latest useful iOS archive proof:

- iOS Internal TestFlight Upload run `27054245288`
- operation: `archive`
- conclusion: `failure`
- failure class: Apple signing/provisioning capacity
- non-secret markers: max certificates; no profile for `atrak.charlie.hoopsclips`

This is useful blocker proof, not upload proof.

## Installed smoke status

Installed-device smoke is not complete. The current physical iPhone is paired
but unavailable to CoreDevice:

- `pairingState=paired`
- `tunnelState=unavailable`
- `developerModeStatus=enabled`
- `ddiServicesAvailable=false`

See:

```text
docs/phase_launch_device_tunnel_recheck_2026-06-06.md
```

## Launch gate conclusion

Internal TestFlight readiness remains blocked until there is current evidence
for all of the following:

- signed internal staging archive job completes successfully
- upload to TestFlight succeeds, or the App Store Connect upload blocker is explicitly resolved with a fresh green upload run
- installed TestFlight build is opened on a trusted physical iPhone
- real user path smoke is recorded: import video, choose team/edit intent, upload to cloud, review generated clips, receive finished MP4, preview/download/share/open export
- smoke notes include build number, device, iOS version, tester, timestamp, and no hidden text/fake status/local-only rendering regressions

Green codecheck or deploy status alone is not installed TestFlight proof.
