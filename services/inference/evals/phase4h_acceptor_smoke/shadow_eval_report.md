# Shadow Eval Report

- Jobs: `11`
- Clips: `15`
- Uncertainty rate: `1.0000`
- Raw eventFamily=other rate: `0.8000`
- Highlight dominance: `0.8000`
- EventFamily=other dominance: `0.8000`
- Dominant flat label: `Highlight`
- Dominant flat-label share: `0.8000`
- Proposal acceptance rate: `0.2`
- Family gate open rate: `0.2`
- Shot head invocation rate: `0.2`
- Eventness calibration: `{"brierScore": 0.0083, "eligibleClips": 9, "negativeMeanScore": null, "positiveMeanScore": 0.9137}`
- Acceptance calibration: `{"brierScore": 0.7264, "coverageRiskCurve": [{"count": 1, "coverage": 0.0667, "risk": 1.0}, {"count": 2, "coverage": 0.1333, "risk": 1.0}, {"count": 3, "coverage": 0.2, "risk": 1.0}, {"count": 4, "coverage": 0.2667, "risk": 1.0}, {"count": 5, "coverage": 0.3333, "risk": 1.0}, {"count": 6, "coverage": 0.4, "risk": 1.0}, {"count": 7, "coverage": 0.4667, "risk": 1.0}, {"count": 8, "coverage": 0.5333, "risk": 1.0}, {"count": 9, "coverage": 0.6, "risk": 1.0}, {"count": 10, "coverage": 0.6667, "risk": 1.0}, {"count": 11, "coverage": 0.7333, "risk": 1.0}, {"count": 12, "coverage": 0.8, "risk": 1.0}, {"count": 13, "coverage": 0.8667, "risk": 0.9231}, {"count": 14, "coverage": 0.9333, "risk": 0.8571}, {"count": 15, "coverage": 1.0, "risk": 0.8}], "eceLite": 0.7348, "reliabilityBuckets": [{"accuracy": null, "bin": "[0.0,0.2)", "count": 0, "meanProbability": null, "risk": null}, {"accuracy": null, "bin": "[0.2,0.4)", "count": 0, "meanProbability": null, "risk": null}, {"accuracy": null, "bin": "[0.4,0.6)", "count": 0, "meanProbability": null, "risk": null}, {"accuracy": null, "bin": "[0.6,0.8)", "count": 0, "meanProbability": null, "risk": null}, {"accuracy": 0.2, "bin": "[0.8,1.0)", "count": 15, "meanProbability": 0.9348, "risk": 0.8}], "scoredClips": 15}`
- Accepted-shot outcome calibration: `{"brierScore": 0.1764, "coverageRiskCurve": [{"count": 1, "coverage": 0.3333, "risk": 0.0}, {"count": 2, "coverage": 0.6667, "risk": 0.0}, {"count": 3, "coverage": 1.0, "risk": 0.0}], "eceLite": 0.42, "reliabilityBuckets": [{"accuracy": null, "bin": "[0.0,0.2)", "count": 0, "meanConfidence": null, "risk": null}, {"accuracy": null, "bin": "[0.2,0.4)", "count": 0, "meanConfidence": null, "risk": null}, {"accuracy": 1.0, "bin": "[0.4,0.6)", "count": 3, "meanConfidence": 0.58, "risk": 0.0}, {"accuracy": null, "bin": "[0.6,0.8)", "count": 0, "meanConfidence": null, "risk": null}, {"accuracy": null, "bin": "[0.8,1.0)", "count": 0, "meanConfidence": null, "risk": null}], "scoredClips": 3}`
- Split-other distribution: `{"ambiguous_event": 12}`
- Candidate namespace: `runtimeFusionTemporalShadow`
- Mixed-batch unique labels: `2`
- Dominant flat label: `Highlight` (80.00%)
- Duration median: `4.75s`, p90: `7.90s`

## Distributions
- Flat labels: `{"Highlight": 12, "Made Shot": 3}`
- Event families: `{"other": 12, "shot_attempt": 3}`
- Shot subtypes: `{"null": 15}`
- Outcomes: `{"made": 3, "uncertain": 12}`
- Source domains: `{"staging_hoopcut_demo_mixed_unlabeled": 6, "staging_hoopcut_known_made": 3, "staging_hoopcut_known_miss": 6}`
- Other audit: `{"auditedOtherClips": 0, "eligibleOtherClips": 12, "manualAuditDistribution": {}, "trueModelMissRateWithinOther": null, "trueModelMissShareOfBatch": 0.0, "trueNegativeRateWithinOther": null, "trueNegativeShareOfBatch": 0.0, "unauditedOtherClips": 12}`
- Accepted-shot outcome accuracy: `1.0`
- Accepted-shot subtype distribution: `{"null": 3}`
- Accepted-shot abstention rate: `1.0`
- Dunk dominance: `0.0`
- Rejected proposal audit: `{"eligibleRejectedClips": 6, "trueMissCount": 6, "trueMissRate": 1.0, "trueNegativeCount": 0, "trueNegativeRate": 0.0}`
- Miss-vs-made confusion: `{"expectedMadePredictedHighlight": 0, "expectedMadePredictedMiss": 0, "expectedMissPredictedHighlight": 0, "expectedMissPredictedMadeShot": 0}`
- Event spotter precision / recall: `1.0` / `1.0`
- Event detection precision / recall: `1.0` / `1.0`
- Event family accuracy: `0.3333`
- Outcome accuracy: `0.3333`
- Shot subtype accuracy: `0.0`

## Mixed Batch Spread
- Spread score: `0.2000`
- Top labels: `[["Highlight", 12], ["Made Shot", 3]]`

## Clip Table
| clipId | jobId | requestId | uploadTraceId | inferenceAttemptId | candidateNamespace | modelVersion | flatLabel | eventFamily | proposalAccepted | familyGateOpen | familyGateRejectionReason | shotHeadInvoked | proposalRejector | proposalEventScore | proposalAcceptanceRawScore | proposalAcceptanceProbability | proposalEnergyScore | otherBucket | manualAudit | shotSubtype | outcome | confidenceBeforeMapping | confidenceAfterMapping | confidence | durationSeconds | merged | sourceEventCount | uncertain | rawVideoMAETop1 | rawXCLIPTop1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| be091e189c554c12a7e871a7d8738c26:clip-1 | be091e189c554c12a7e871a7d8738c26 | 88f91e05-dd61-4b33-8c55-bf23a5cb691e | fd830daddd9d475387c15d7bff139bbf | 4f9aa726a9024af7b69d1ff503515443 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Made Shot | shot_attempt | True | True |  | True | real_event | 0.8726 | 0.8726 | 0.8726 | -0.7086 |  |  |  | made | 0.8726 | 0.58 | 0.58 | 4.5 | False | 1 | True | fast break | fast break |
| 2b49f9b5803041b5b821a48ff2c1fa42:clip-1 | 2b49f9b5803041b5b821a48ff2c1fa42 | 9800355f-a2cf-401b-8986-085e02c2c84d | 067f96857dba41b5aa80509bb62f9473 | 409bafdca297457689cd733332fecf28 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0655 | 0.0655 | 0.9345 | -1.1892 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 5.25 | False | 1 | True | fast break | fast break |
| dfca3ccbf44443f481fb9f8bb91b3087:clip-1 | dfca3ccbf44443f481fb9f8bb91b3087 | 685e2132-e496-465c-8139-c22dadbd9a30 | b624810f53494747bed0a69a5af9ae3e | 633d19eeda224dabb3f57e78ae723642 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0661 | 0.0661 | 0.9339 | -1.1815 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 4.2 | False | 1 | True | fast break | fast break |
| 6c0850d1f7ce471883085e31f949bdb8:clip-1 | 6c0850d1f7ce471883085e31f949bdb8 | b185363b-350a-4e5e-ad72-feafe1816805 | 6c4674691d00497aa937a6818bf2d125 | d92bd9bad69d49bf8dcbbf6e00e8dc7a | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0764 | 0.0764 | 0.9236 | -1.1246 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 4.75 | False | 1 | True | layup | three |
| 6c0850d1f7ce471883085e31f949bdb8:clip-2 | 6c0850d1f7ce471883085e31f949bdb8 | b185363b-350a-4e5e-ad72-feafe1816805 | 6c4674691d00497aa937a6818bf2d125 | d92bd9bad69d49bf8dcbbf6e00e8dc7a | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0115 | 0.0115 | 0.9885 | -2.1608 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 7.9 | True | 4 | True | uncertain | uncertain |
| 6c0850d1f7ce471883085e31f949bdb8:clip-3 | 6c0850d1f7ce471883085e31f949bdb8 | b185363b-350a-4e5e-ad72-feafe1816805 | 6c4674691d00497aa937a6818bf2d125 | d92bd9bad69d49bf8dcbbf6e00e8dc7a | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0125 | 0.0125 | 0.9875 | -2.1324 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 7.515 | True | 3 | True | uncertain | uncertain |
| 3cab58f678ad4056bf480f8fb4cc0bfe:clip-1 | 3cab58f678ad4056bf480f8fb4cc0bfe | 65ac7bbf-f509-447a-808f-bc2ae633233f | 6df229bab8814ae6953e43afb6dca1e4 | 102730cb5b374ca791646584543d674c | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Made Shot | shot_attempt | True | True |  | True | real_event | 0.8726 | 0.8726 | 0.8726 | -0.7086 |  |  |  | made | 0.8726 | 0.58 | 0.58 | 4.5 | False | 1 | True | fast break | fast break |
| f0052274d90446209839ed7c97a415c0:clip-1 | f0052274d90446209839ed7c97a415c0 | 88105e80-33e2-4a07-8d6a-f9539898c746 | 2e8fa6550dfe4102adde968d5b7f5ed8 | e03cdb5cb6b0441586eeeefb0435adce | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0655 | 0.0655 | 0.9345 | -1.1892 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 5.25 | False | 1 | True | fast break | fast break |
| 7cdf4a39699f4c0ca5e6acacdcab30b1:clip-1 | 7cdf4a39699f4c0ca5e6acacdcab30b1 | fbdcbc85-3964-4c94-ba77-30c5beea3eac | 8d521aff21614e7d8e24065acd629774 | d6c4a1a6198d455f8849609f930c555a | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0661 | 0.0661 | 0.9339 | -1.1815 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 4.2 | False | 1 | True | fast break | fast break |
| 95e9a27a15c34e9f8cd367e464cf6905:clip-1 | 95e9a27a15c34e9f8cd367e464cf6905 | cd96c319-1fcb-422b-b287-df57ce819855 | 75ac1ca115364ef99ac4c3ae2da4bafa | c12957c4533f41fab29361d49f5fed8d | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0764 | 0.0764 | 0.9236 | -1.1246 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 4.75 | False | 1 | True | layup | three |
| 95e9a27a15c34e9f8cd367e464cf6905:clip-2 | 95e9a27a15c34e9f8cd367e464cf6905 | cd96c319-1fcb-422b-b287-df57ce819855 | 75ac1ca115364ef99ac4c3ae2da4bafa | c12957c4533f41fab29361d49f5fed8d | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0115 | 0.0115 | 0.9885 | -2.1608 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 7.9 | True | 4 | True | uncertain | uncertain |
| 95e9a27a15c34e9f8cd367e464cf6905:clip-3 | 95e9a27a15c34e9f8cd367e464cf6905 | cd96c319-1fcb-422b-b287-df57ce819855 | 75ac1ca115364ef99ac4c3ae2da4bafa | c12957c4533f41fab29361d49f5fed8d | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0125 | 0.0125 | 0.9875 | -2.1324 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 7.515 | True | 3 | True | uncertain | uncertain |
| f09a1de39a604ae38f947cc83c301586:clip-1 | f09a1de39a604ae38f947cc83c301586 | 40d3bc3c-fa0f-46a4-921c-0511d3167e23 | 03319e45e9264c09b14025d1e4dec830 | ca182a5f41f34652b60b8d80e07ac3c5 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Made Shot | shot_attempt | True | True |  | True | real_event | 0.8726 | 0.8726 | 0.8726 | -0.7086 |  |  |  | made | 0.8726 | 0.58 | 0.58 | 4.5 | False | 1 | True | fast break | fast break |
| 3b626f1e2d5b4291b4a8a3a7f2cebbd6:clip-1 | 3b626f1e2d5b4291b4a8a3a7f2cebbd6 | 8e1e9c4a-5bab-4655-aed2-913283230ba4 | 807b9e91da4549a3a3b31494a56e76e2 | a60b7964c7214e74ab3db36733a8eade | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0655 | 0.0655 | 0.9345 | -1.1892 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 5.25 | False | 1 | True | fast break | fast break |
| 1ce65fa7f590407ebf96324cc30277d8:clip-1 | 1ce65fa7f590407ebf96324cc30277d8 | 39bc94d2-aafe-481f-ac2c-815c071fe263 | 79f0eb41f6484bf0ab8ef8c758b37d3c | 2ca24d2b5a7a4d87bf3c5cbe38bf491b | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0661 | 0.0661 | 0.9339 | -1.1815 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 4.2 | False | 1 | True | fast break | fast break |

## Collapse Examples
- `6c0850d1f7ce471883085e31f949bdb8:clip-1`: raw diversity `2` -> final `Highlight`
- `95e9a27a15c34e9f8cd367e464cf6905:clip-1`: raw diversity `2` -> final `Highlight`

## Warnings
- Mixed batch produced fewer than four flat labels.
- One flat label still dominates more than half the batch.
- Uncertainty remains above 50% on this batch.
