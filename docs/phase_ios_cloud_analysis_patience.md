# Phase iOS Cloud Analysis Patience

## Goal

Reduce tester confusion when cloud analysis takes longer because HoopClips is using larger candidate pools, GPT team prescan, and backend-owned highlight logic.

## Changes

- iOS now waits up to 8 minutes for cloud analysis job state instead of stopping at 3 minutes.
- Polling still uses the real backend job state and stage text. No fake ETA, no fake thinking, and no local analysis fallback was added.
- The client timeout copy now tells testers to reopen the project from History and retry, instead of implying the whole cloud job definitely failed.

## Why This Helps

Longer game videos and team-targeted GPT workflows can legitimately take longer than the old client-side patience window. Letting the real job keep reporting queued/processing state gives internal testers a clearer path and avoids unnecessary retry loops.

## Validation

Run after this change:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=A46E2157-77ED-42CE-959D-65C068681A47' build
```

Recommended real-device smoke:

1. Import a large basketball video.
2. Let the team scan and cloud analysis run beyond 3 minutes if needed.
3. Confirm status remains based on real backend stages.
4. Confirm timeout copy is readable if the 8-minute client window is reached.
