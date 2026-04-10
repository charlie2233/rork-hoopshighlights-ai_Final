# Phase 4h Go / No-Go

## Recommendation

**No-go. Hold and recalibrate. Do not promote Phase 4h to a larger shadow batch yet, and do not proceed to 4i/4j or detector-family work from this result.**

The staged 63-clip Worker-path batch fails four of five promotion gates and lacks the calibrated telemetry needed to trust the remaining calibration metrics.

## Gate Result

| Gate | Target | Observed | Result |
| --- | --- | ---: | --- |
| Proposal acceptance rate | `0.35 to 0.75` | `0.1270` | `FAIL` |
| Highlight dominance | `< 0.55` | `1.0000` | `FAIL` |
| Raw eventFamily=other | `< 0.40` | `1.0000` | `FAIL` |
| Dominant flat-label share | `<= 0.65` | `1.0000` | `FAIL` |
| Miss-to-made drift | `= 0` | `0` | `PASS` |

## What Passed

- Miss-to-made drift remained `0`, but this is weak evidence because no clip reached a made-shot label or the shot head.
- Worker-path upload, processing, trace IDs, and `runtimeFusionTemporalShadow` payload normalization worked across `43` staging jobs and `63` clips.

## What Failed

- Proposal acceptance under-fired: `0.127`, below the `0.35` lower bound.
- Family gate remained closed for every clip: `familyGateOpenCount=0` despite `proposalAcceptedCount=8`.
- Shot head was starved: `shotHeadInvocationCount=0`, so accepted-shot outcome accuracy is not measurable.
- Flat labels collapsed: `Highlight=63/63`, no single-label guard is satisfied.
- Raw event family collapsed: `other=63/63`, well above the `0.40` gate.
- Calibrated acceptance probability, energy score, and explicit family-gate rejection reasons were absent from the staged payload.

## Next Branch

Open a small Phase 4h follow-up branch, for example `codex/phase4h1-staging-telemetry-and-gate-calibration`, focused only on:

- deploying/restoring calibrated acceptance probability, energy score, and explicit gate-rejection telemetry to staging;
- fixing family-gate suppression when a proposal is accepted and likely a real event;
- rerunning the same `>=60` clip staging batch before any 4i/4j planning;
- preserving the app-facing contract and current shadow payload compatibility.

## SpaceJam

Skipped because local SpaceJam inputs were absent. Do not resume `exp/spacejam-aux-pretrain` until a real manifest and clip root are present.
