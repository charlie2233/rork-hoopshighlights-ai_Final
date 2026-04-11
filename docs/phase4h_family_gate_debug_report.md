# Phase 4h Family Gate Debug Report

## Summary

- Accepted proposals replayed: `8`
- Forced-family comparator gate opens: `8`
- Relaxed-family comparator gate opens: `8`
- Relaxed-family comparator shot-head invocations: `8`
- Closure reason distribution: `{"accepted_but_family_margin_low_and_spotter_disagrees": 8}`
- Current staging payload did not include raw family logits or feature-validity flags; this branch adds those fields for the next staging smoke.

## Accepted Proposal Table

| clipId | expected | top1 | top2 | margin | spotter | accepted score | gate open | closure reason | forced family | relaxed family | relaxed shot head |
| --- | --- | --- | --- | ---: | --- | ---: | --- | --- | --- | --- | --- |
| d71d2879c44a46698a0f777532df29d2:clip-1 | shot_attempt/made/dunk | transition (0.5264) | shot_attempt (0.4706) | 0.0558 | shot_attempt | 0.8726 | False | accepted_but_family_margin_low_and_spotter_disagrees | transition | shot_attempt | True |
| 2aa63636630c4a5384c69d585439c9cf:clip-1 | shot_attempt/made/dunk | transition (0.5264) | shot_attempt (0.4706) | 0.0558 | shot_attempt | 0.8726 | False | accepted_but_family_margin_low_and_spotter_disagrees | transition | shot_attempt | True |
| 505fcb9380154c0db345373b1f67f942:clip-1 | shot_attempt/made/dunk | transition (0.5264) | shot_attempt (0.4706) | 0.0558 | shot_attempt | 0.8726 | False | accepted_but_family_margin_low_and_spotter_disagrees | transition | shot_attempt | True |
| 7958f1dac8b3436dabab5264ae341919:clip-1 | shot_attempt/made/dunk | transition (0.5264) | shot_attempt (0.4706) | 0.0558 | shot_attempt | 0.8726 | False | accepted_but_family_margin_low_and_spotter_disagrees | transition | shot_attempt | True |
| 081080779d544737acc513fcf01e9bee:clip-1 | shot_attempt/made/dunk | transition (0.5264) | shot_attempt (0.4706) | 0.0558 | shot_attempt | 0.8726 | False | accepted_but_family_margin_low_and_spotter_disagrees | transition | shot_attempt | True |
| d3a90653a10d4d65b8a306801bd30a86:clip-1 | shot_attempt/made/dunk | transition (0.5264) | shot_attempt (0.4706) | 0.0558 | shot_attempt | 0.8726 | False | accepted_but_family_margin_low_and_spotter_disagrees | transition | shot_attempt | True |
| f859a308118c42d0b22cf582f42e8e0a:clip-1 | shot_attempt/made/dunk | transition (0.5264) | shot_attempt (0.4706) | 0.0558 | shot_attempt | 0.8726 | False | accepted_but_family_margin_low_and_spotter_disagrees | transition | shot_attempt | True |
| 50d003aedd814d4d8bbcd4b3741cc21c:clip-1 | shot_attempt/made/dunk | transition (0.5264) | shot_attempt (0.4706) | 0.0558 | shot_attempt | 0.8726 | False | accepted_but_family_margin_low_and_spotter_disagrees | transition | shot_attempt | True |
