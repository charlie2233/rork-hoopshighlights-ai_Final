# Phase 4h Family Gate Sweep Report

## Recommendation

- Recommended smoke setting: accepted-implies-family-eval with spotter rescue.
- Family temperature: `1.0`
- Family top-1 threshold: `0.42`
- Family top-2 margin threshold: `0.02`
- Replay family gate opens: `8`
- Replay shot-head invocations: `8`
- Replay raw eventFamily=other rate: `0.873`
- Replay dominant flat-label share: `0.873`
- Go/no-go for next step: run a small `15-20` clip staging smoke only. Do not promote larger rollout until calibrated acceptance probability, energy, and explicit gate reasons are visible in staging.

## Top Sweep Rows

| temp | threshold | margin | accepted eval | spotter rescue | gate opens | shot head | raw other | dominant share | false event opens |
| ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0.75 | 0.35 | 0.0 | True | True | 8 | 8 | 0.873 | 0.873 | 0 |
| 0.75 | 0.35 | 0.02 | True | True | 8 | 8 | 0.873 | 0.873 | 0 |
| 0.75 | 0.35 | 0.05 | True | True | 8 | 8 | 0.873 | 0.873 | 0 |
| 0.75 | 0.35 | 0.08 | True | True | 8 | 8 | 0.873 | 0.873 | 0 |
| 0.75 | 0.35 | 0.1 | True | True | 8 | 8 | 0.873 | 0.873 | 0 |
| 0.75 | 0.42 | 0.0 | True | True | 8 | 8 | 0.873 | 0.873 | 0 |
| 0.75 | 0.42 | 0.02 | True | True | 8 | 8 | 0.873 | 0.873 | 0 |
| 0.75 | 0.42 | 0.05 | True | True | 8 | 8 | 0.873 | 0.873 | 0 |
| 0.75 | 0.42 | 0.08 | True | True | 8 | 8 | 0.873 | 0.873 | 0 |
| 0.75 | 0.42 | 0.1 | True | True | 8 | 8 | 0.873 | 0.873 | 0 |

## Over-Fire Check

- The replay opens only accepted proposals, so rejected known misses and unlabeled demo clips remain closed.
- The replay does not emit concrete outcome/subtype predictions; `dunkMadeHallucinationSignal` remains `0` because the sweep stops at family/shot-head invocation.
- A live smoke must verify the actual shot head does not reintroduce made/dunk hallucination.
