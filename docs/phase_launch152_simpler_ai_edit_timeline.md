# Phase Launch152 Simpler AI Edit Timeline

## Goal

Make Export easier to use on internal TestFlight by reducing always-visible AI Edit clutter while preserving real cloud job status.

## Changes

- Replaced the always-expanded `AI Edit Timeline` block with a compact `Cloud Job` card.
- The card now shows the current real cloud step first.
- Full job steps stay available behind `Show cloud details`.
- Timeline step titles/details now wrap and scale better for accessibility Dynamic Type and smaller iPhones.

## Architecture

- No rendering, analysis, or composition moved into iOS.
- iOS still only displays cloud job status and controls.
- Timeline content still comes from real render/job state or the existing local fallback timeline model.
- No fake ETA, fake thinking copy, or artificial waiting was added.

## Validation

```sh
git diff --check
```

- Passed.

```sh
XcodeBuildMCP build_sim
```

- Passed with no warnings.

```sh
XcodeBuildMCP test_sim -only-testing:HoopsClipsTests
```

- Passed: 121 tests, 0 failures.
- UI smoke was not run in this pass to avoid hitting staging/live cloud unnecessarily.

## Launch Notes

- This keeps the AI Edit page simpler without removing evidence. Users see one status row by default and can expand details only when they care.
- Real-device/TestFlight smoke is still required for final launch readiness.
