# Installed iPhone device tunnel recheck

Date: 2026-06-06
Branch: `codex/phase-clip1-gpt-led-highlight-editor`

## Purpose

This recheck narrows the installed TestFlight smoke blocker. It does not prove
installed smoke; it documents why the smoke cannot run yet on the physical
phone.

## Device state

Command:

```bash
xcrun devicectl list devices
```

Result:

```text
charlie's iPhone / iPhone 15 Pro / state=unavailable
identifier=E5786BB6-0095-5509-8B85-110C0B5CE6D3
hostname=charliedeiPhone.coredevice.local
```

Device details from:

```bash
xcrun devicectl device info details --device E5786BB6-0095-5509-8B85-110C0B5CE6D3
```

Relevant non-secret fields:

```text
pairingState=paired
tunnelState=unavailable
developerModeStatus=enabled
ddiServicesAvailable=false
lastConnectionDate=2026-06-04 04:06:31 +0000
```

`xcrun xcdevice list` also reports the physical iPhone as unavailable and says
Xcode is browsing on the local network for the device. The recovery suggestion
is to ensure the device is unlocked and attached by cable or on the same local
network.

## Local reachability checks

USB scan:

```bash
system_profiler SPUSBDataType | rg "iPhone|Apple Mobile|DT7R261XL7|00008130"
```

Result: no iPhone USB attachment was detected.

CoreDevice hostname check:

```bash
ping -c 2 -t 5 charliedeiPhone.coredevice.local
```

Result:

```text
ping: cannot resolve charliedeiPhone.coredevice.local: Unknown host
```

## Current conclusion

Installed TestFlight smoke remains blocked because the trusted iPhone is paired
but not reachable by USB or CoreDevice network tunnel.

This is not an app-code blocker. The next owner action is:

1. Unlock the iPhone.
2. Connect it to this Mac with USB, or ensure the phone and Mac are on the same
   local network with wireless debugging available.
3. Open Xcode Devices and Simulators if needed to refresh CoreDevice.
4. Rerun:

```bash
xcrun devicectl list devices
python3 scripts/submission_readiness_preflight.py \
  --labeling-bundle-dir artifacts/team_highlight_labeling_bundle_launch_current_reduced \
  --json
```

The device blocker is not closed until the preflight reports an available
physical iPhone and the installed TestFlight smoke flow is executed end to end.
