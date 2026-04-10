# SpaceJam Auxiliary Pretraining Experiment Report

## Status

- Status: `blocked_missing_spacejam_manifest`
- Recommendation: `revise`
- Reason: the public SpaceJam repository points to a Google Drive zip, but this repo does not include a local clip-manifest export or clip directory that can be used for truthful auxiliary pretraining in this branch.

## Before Metrics

These are the current offline baseline metrics from the checked-in Phase 4h temporal detector bundle on the in-repo evaluation slice:

- proposalAcceptanceRate: `0.5455`
- familyGateOpenRate: `0.5455`
- shotHeadInvocationRate: `0.4545`
- dominantFlatLabelShare: `0.5455`
- rawEventFamilyOtherRate: `0.4545`
- uncertaintyRate: `0.6364`
- acceptedShotOutcomeAccuracy: `1.0`
- brierScore: `0.0077`
- eceLite: `0.0456`
- flatLabelDistribution: `{'Fast Break': 1, 'Highlight': 6, 'Layup': 1, 'Made Shot': 3}`
- highlightDominance: `0.5455`
- missVsMadeConfusion: `0`

## After Metrics

- No after-metrics were produced.
- The branch intentionally does not inject SpaceJam-derived weights into the mainline detector, verifier, or rollout path.
- A truthful after-run comparison requires a local SpaceJam clip manifest plus locally reachable clip files.

## What Landed

- Training-only SpaceJam adapter in [spacejam_aux_pretrain.py](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/spacejam_aux_pretrain.py)
- Separate experiment config in [spacejam_aux_pretrain_v1.json](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/configs/spacejam_aux_pretrain_v1.json)
- Guarded experiment harness in [run_spacejam_aux_pretrain_experiment.py](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_spacejam_aux_pretrain_experiment.py)

## Recommendation

- `revise`
- Keep the adapter and the separate config.
- Do not merge any SpaceJam-derived behavior into the current Phase 4h rollout branch.
- Re-run this experiment only after attaching a local SpaceJam clip manifest and clip root, then compare against the same baseline metrics before considering any future recall-oriented follow-on work.
