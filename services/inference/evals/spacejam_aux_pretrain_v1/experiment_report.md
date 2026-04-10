# SpaceJam Auxiliary Pretraining Experiment

- Status: `blocked_missing_spacejam_manifest`
- Recommendation: `revise`
- Reason: The configured SpaceJam manifest is not present locally, so the auxiliary-pretraining run was not started.
- Feature flag / config gate: `spacejam_aux_pretrain_v1`

## Scope

- Training-path only. No runtime contract changes.
- Clip modality only in v1. Joint rows remain ignored.
- Conservative label mapping only: `Shoot -> shot_candidate_aux`, `No Action -> coarse_non_event_aux`.
- Ambiguous SpaceJam classes stay unmapped by default.

## Baseline Metrics

- proposalAcceptanceRate: `0.5455`
- familyGateOpenRate: `0.5455`
- shotHeadInvocationRate: `0.4545`
- dominantFlatLabelShare: `0.5455`
- rawEventFamilyOtherRate: `0.4545`
- uncertaintyRate: `0.6364`
- acceptedShotOutcomeAccuracy: `1.0`
- brierScore: `0.0077`
- eceLite: `0.0456`
- highlightDominance: `0.5455`
- missVsMadeConfusion: `0`
- flatLabelDistribution: `{'Fast Break': 1, 'Highlight': 6, 'Layup': 1, 'Made Shot': 3}`

## After Metrics

- No post-pretraining detector metrics were produced in this branch.
- The auxiliary path stays isolated behind separate config until a real SpaceJam clip export is attached and evaluated offline.

## Abort Criteria

- Configured abort conditions: `{'calibrationWorsens': True, 'dominantFlatLabelShareIncreases': True, 'familyGateOpenRateDrops': True, 'uncertaintyOrCollapseRegresses': True}`
- Abort immediately if calibration worsens, dominant flat-label share rises, family-gate open rate drops, or collapse behavior regresses.

## Recommendation

- `revise`
- Keep the adapter and config scaffolding.
- Do not route this branch into PR #2 or the Phase 4h rollout path.
- Re-run only after a local SpaceJam clip manifest and clip files exist.
