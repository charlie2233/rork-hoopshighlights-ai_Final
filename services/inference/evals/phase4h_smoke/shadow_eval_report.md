# Shadow Eval Report

- Jobs: `12`
- Clips: `18`
- Uncertainty rate: `1.0000`
- Raw eventFamily=other rate: `0.8333`
- Highlight dominance: `0.8333`
- EventFamily=other dominance: `0.8333`
- Dominant flat label: `Highlight`
- Dominant flat-label share: `0.8333`
- Proposal acceptance rate: `0.1667`
- Family gate open rate: `0.1667`
- Shot head invocation rate: `0.1667`
- Eventness calibration: `{"brierScore": 0.0308, "eligibleClips": 9, "negativeMeanScore": null, "positiveMeanScore": 0.8705}`
- Acceptance calibration: `{"brierScore": 0.7099, "coverageRiskCurve": [{"count": 1, "coverage": 0.0556, "risk": 1.0}, {"count": 2, "coverage": 0.1111, "risk": 1.0}, {"count": 3, "coverage": 0.1667, "risk": 1.0}, {"count": 4, "coverage": 0.2222, "risk": 1.0}, {"count": 5, "coverage": 0.2778, "risk": 1.0}, {"count": 6, "coverage": 0.3333, "risk": 1.0}, {"count": 7, "coverage": 0.3889, "risk": 1.0}, {"count": 8, "coverage": 0.4444, "risk": 1.0}, {"count": 9, "coverage": 0.5, "risk": 1.0}, {"count": 10, "coverage": 0.5556, "risk": 1.0}, {"count": 11, "coverage": 0.6111, "risk": 1.0}, {"count": 12, "coverage": 0.6667, "risk": 1.0}, {"count": 13, "coverage": 0.7222, "risk": 1.0}, {"count": 14, "coverage": 0.7778, "risk": 0.9286}, {"count": 15, "coverage": 0.8333, "risk": 0.8667}, {"count": 16, "coverage": 0.8889, "risk": 0.8125}, {"count": 17, "coverage": 0.9444, "risk": 0.8235}, {"count": 18, "coverage": 1.0, "risk": 0.8333}], "eceLite": 0.74, "reliabilityBuckets": [{"accuracy": null, "bin": "[0.0,0.2)", "count": 0, "meanProbability": null, "risk": null}, {"accuracy": null, "bin": "[0.2,0.4)", "count": 0, "meanProbability": null, "risk": null}, {"accuracy": 0.0, "bin": "[0.4,0.6)", "count": 1, "meanProbability": 0.5451, "risk": 1.0}, {"accuracy": 0.0, "bin": "[0.6,0.8)", "count": 1, "meanProbability": 0.7108, "risk": 1.0}, {"accuracy": 0.1875, "bin": "[0.8,1.0)", "count": 16, "meanProbability": 0.9415, "risk": 0.8125}], "scoredClips": 18}`
- Accepted-shot outcome calibration: `{"brierScore": 0.1764, "coverageRiskCurve": [{"count": 1, "coverage": 0.3333, "risk": 0.0}, {"count": 2, "coverage": 0.6667, "risk": 0.0}, {"count": 3, "coverage": 1.0, "risk": 0.0}], "eceLite": 0.42, "reliabilityBuckets": [{"accuracy": null, "bin": "[0.0,0.2)", "count": 0, "meanConfidence": null, "risk": null}, {"accuracy": null, "bin": "[0.2,0.4)", "count": 0, "meanConfidence": null, "risk": null}, {"accuracy": 1.0, "bin": "[0.4,0.6)", "count": 3, "meanConfidence": 0.58, "risk": 0.0}, {"accuracy": null, "bin": "[0.6,0.8)", "count": 0, "meanConfidence": null, "risk": null}, {"accuracy": null, "bin": "[0.8,1.0)", "count": 0, "meanConfidence": null, "risk": null}], "scoredClips": 3}`
- Split-other distribution: `{"ambiguous_event": 15}`
- Candidate namespace: `runtimeFusionTemporalShadow`
- Mixed-batch unique labels: `2`
- Dominant flat label: `Highlight` (83.33%)
- Duration median: `5.00s`, p90: `7.90s`

## Distributions
- Flat labels: `{"Highlight": 15, "Made Shot": 3}`
- Event families: `{"other": 15, "shot_attempt": 3}`
- Shot subtypes: `{"null": 18}`
- Outcomes: `{"made": 3, "uncertain": 15}`
- Source domains: `{"staging_hoopcut_demo_mixed_unlabeled": 9, "staging_hoopcut_known_made": 3, "staging_hoopcut_known_miss": 6}`
- Other audit: `{"auditedOtherClips": 0, "eligibleOtherClips": 15, "manualAuditDistribution": {}, "trueModelMissRateWithinOther": null, "trueModelMissShareOfBatch": 0.0, "trueNegativeRateWithinOther": null, "trueNegativeShareOfBatch": 0.0, "unauditedOtherClips": 15}`
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
- Spread score: `0.1667`
- Top labels: `[["Highlight", 15], ["Made Shot", 3]]`

## Clip Table
| clipId | jobId | requestId | uploadTraceId | inferenceAttemptId | candidateNamespace | modelVersion | flatLabel | eventFamily | proposalAccepted | familyGateOpen | familyGateRejectionReason | shotHeadInvoked | proposalRejector | proposalEventScore | proposalAcceptanceRawScore | proposalAcceptanceProbability | proposalEnergyScore | otherBucket | manualAudit | shotSubtype | outcome | confidenceBeforeMapping | confidenceAfterMapping | confidence | durationSeconds | merged | sourceEventCount | uncertain | rawVideoMAETop1 | rawXCLIPTop1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d48f6b5996d54dcb87e9890f075fe8ab:clip-1 | d48f6b5996d54dcb87e9890f075fe8ab | 9e2ec502-7e6b-44d4-88b9-5b4c249bc181 | 2197f5d458314ebeb4dedd90e1561661 | 6cff7b8ec1f147da8ac0cc512aed2479 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Made Shot | shot_attempt | True | True |  | True | real_event | 0.8726 | 0.8726 | 0.8726 | -0.7086 |  |  |  | made | 0.8726 | 0.58 | 0.58 | 4.5 | False | 1 | True | fast break | fast break |
| 1811784ecfd9436da61a2b5f922baf54:clip-1 | 1811784ecfd9436da61a2b5f922baf54 | 2cf6c516-3877-41d1-bde8-7077f4ba5a04 | fa58aa0cadf14353bef1552607a8f83a | 43101b3d6aa54a198aa754a8dd15fda8 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0655 | 0.0655 | 0.9345 | -1.1892 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 5.25 | False | 1 | True | fast break | fast break |
| 861d8a93836c4c5486e75520feb4503b:clip-1 | 861d8a93836c4c5486e75520feb4503b | 37fecfcc-853e-4387-973e-981976b11645 | 322ceda2a70b4aa2aa59b54ceaba6399 | 051846f060f04b53b51bc46f1025db2a | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0661 | 0.0661 | 0.9339 | -1.1815 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 4.2 | False | 1 | True | fast break | fast break |
| 2755a51b9b244708b7397207968e1c01:clip-1 | 2755a51b9b244708b7397207968e1c01 | 47f31761-fcdc-4d0a-b988-0a88328c43c4 | c33e2546ba9249348bc72480a894e095 | 2b1abd2609d34c0eb795cb2921e5c2a8 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0764 | 0.0764 | 0.9236 | -1.1246 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 4.75 | False | 1 | True | layup | three |
| 2755a51b9b244708b7397207968e1c01:clip-2 | 2755a51b9b244708b7397207968e1c01 | 47f31761-fcdc-4d0a-b988-0a88328c43c4 | c33e2546ba9249348bc72480a894e095 | 2b1abd2609d34c0eb795cb2921e5c2a8 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0115 | 0.0115 | 0.9885 | -2.1608 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 7.9 | True | 4 | True | uncertain | uncertain |
| 2755a51b9b244708b7397207968e1c01:clip-3 | 2755a51b9b244708b7397207968e1c01 | 47f31761-fcdc-4d0a-b988-0a88328c43c4 | c33e2546ba9249348bc72480a894e095 | 2b1abd2609d34c0eb795cb2921e5c2a8 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0125 | 0.0125 | 0.9875 | -2.1324 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 7.515 | True | 3 | True | uncertain | uncertain |
| de9463da378d4ad697c2337d28ffec2a:clip-1 | de9463da378d4ad697c2337d28ffec2a | 7fdaafba-520e-469b-a8b9-bb7ea5fdb365 | a942043895214c56a9581c2532a04e95 | 5a8bcfd29efd414db5a82ecaa0aacb48 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Made Shot | shot_attempt | True | True |  | True | real_event | 0.8726 | 0.8726 | 0.8726 | -0.7086 |  |  |  | made | 0.8726 | 0.58 | 0.58 | 4.5 | False | 1 | True | fast break | fast break |
| c266e2bb827045679bcb45158500c023:clip-1 | c266e2bb827045679bcb45158500c023 | e30e58f9-8eea-4d89-99d9-c07f11a1e8ef | 35d6426a1168412caab56d03224b5f29 | 493bf98355da4fed9305d57573889dc5 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0655 | 0.0655 | 0.9345 | -1.1892 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 5.25 | False | 1 | True | fast break | fast break |
| cd5ec7b3b4be4f11b6e7c38597cc9e08:clip-1 | cd5ec7b3b4be4f11b6e7c38597cc9e08 | 3a9cb7f0-101b-42b5-89b2-d78aed67fb12 | 7443f1bbcb0043c4bf5f2fbb38ea1afb | 21f39c1a0840419b9563c6e357affae9 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0661 | 0.0661 | 0.9339 | -1.1815 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 4.2 | False | 1 | True | fast break | fast break |
| 5fcbbe8f6a8d4fe9a01e8f034e6bae17:clip-1 | 5fcbbe8f6a8d4fe9a01e8f034e6bae17 | 7a6a6fc4-0275-4dad-b0d9-644ec44b8318 | e87bfaa6186443118a34e9547d94a37d | 3b043f4bfdc24f0195e572228fdeab94 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0764 | 0.0764 | 0.9236 | -1.1246 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 4.75 | False | 1 | True | layup | three |
| 5fcbbe8f6a8d4fe9a01e8f034e6bae17:clip-2 | 5fcbbe8f6a8d4fe9a01e8f034e6bae17 | 7a6a6fc4-0275-4dad-b0d9-644ec44b8318 | e87bfaa6186443118a34e9547d94a37d | 3b043f4bfdc24f0195e572228fdeab94 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0115 | 0.0115 | 0.9885 | -2.1608 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 7.9 | True | 4 | True | uncertain | uncertain |
| 5fcbbe8f6a8d4fe9a01e8f034e6bae17:clip-3 | 5fcbbe8f6a8d4fe9a01e8f034e6bae17 | 7a6a6fc4-0275-4dad-b0d9-644ec44b8318 | e87bfaa6186443118a34e9547d94a37d | 3b043f4bfdc24f0195e572228fdeab94 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0125 | 0.0125 | 0.9875 | -2.1324 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 7.515 | True | 3 | True | uncertain | uncertain |
| e1e935b4b54048759f32c304c79b8897:clip-1 | e1e935b4b54048759f32c304c79b8897 | 04c2b69d-95eb-457b-89b0-8c778f09792c | 6cd2f925675841279360400974b84d2f | f676bdc2ad944b13bc737de8e706ea0a | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Made Shot | shot_attempt | True | True |  | True | real_event | 0.8726 | 0.8726 | 0.8726 | -0.7086 |  |  |  | made | 0.8726 | 0.58 | 0.58 | 4.5 | False | 1 | True | fast break | fast break |
| 5b455ca8d19044a680e02cd8afdd000a:clip-1 | 5b455ca8d19044a680e02cd8afdd000a | 07ecfe72-7db7-4cf2-8e53-a6a892367808 | 062c7a5c42264b77bc6e02c1a55d1f13 | 661bda5f24e5477dabb5441136bb524f | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0655 | 0.0655 | 0.9345 | -1.1892 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 5.25 | False | 1 | True | fast break | fast break |
| 7a2d729389fd4230942af7e18267f166:clip-1 | 7a2d729389fd4230942af7e18267f166 | c3674fdd-fef2-4bc6-ac94-cf4f69e188f6 | d7bfef91c8624a7483883a2c3fff6b3e | 594ff7fb022a4b9188abcb713c70008b | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.4549 | 0.4549 | 0.5451 | -0.5038 | ambiguous_event |  |  | uncertain | 0.4549 | 0.4149 | 0.4149 | 4.2 | False | 1 | True | shooting basketball | fast break |
| b84f24e2c6af4f1b9b58393aaacaa009:clip-1 | b84f24e2c6af4f1b9b58393aaacaa009 | cc614c99-5a28-472f-9af3-8a59c7632eaa | 51ff5248c8384079a055d0f1bb9500b2 | 9a7a0af3fd764ae3af50440087b048a0 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.7108 | 0.7108 | 0.7108 | -0.5683 | ambiguous_event |  |  | uncertain | 0.7108 | 0.45 | 0.45 | 4.75 | False | 1 | True | shooting basketball | three |
| b84f24e2c6af4f1b9b58393aaacaa009:clip-2 | b84f24e2c6af4f1b9b58393aaacaa009 | cc614c99-5a28-472f-9af3-8a59c7632eaa | 51ff5248c8384079a055d0f1bb9500b2 | 9a7a0af3fd764ae3af50440087b048a0 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0115 | 0.0115 | 0.9885 | -2.162 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 7.9 | True | 4 | True | dribbling basketball | uncertain |
| b84f24e2c6af4f1b9b58393aaacaa009:clip-3 | b84f24e2c6af4f1b9b58393aaacaa009 | cc614c99-5a28-472f-9af3-8a59c7632eaa | 51ff5248c8384079a055d0f1bb9500b2 | 9a7a0af3fd764ae3af50440087b048a0 | runtimeFusionTemporalShadow | temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2 | Highlight | other | False | False | proposal_rejected | False | ambiguous | 0.0122 | 0.0122 | 0.9878 | -2.1403 | ambiguous_event |  |  | uncertain | 0.18 | 0.18 | 0.18 | 7.515 | True | 3 | True | dribbling basketball | uncertain |

## Collapse Examples
- `2755a51b9b244708b7397207968e1c01:clip-1`: raw diversity `2` -> final `Highlight`
- `5fcbbe8f6a8d4fe9a01e8f034e6bae17:clip-1`: raw diversity `2` -> final `Highlight`
- `7a2d729389fd4230942af7e18267f166:clip-1`: raw diversity `2` -> final `Highlight`
- `b84f24e2c6af4f1b9b58393aaacaa009:clip-1`: raw diversity `2` -> final `Highlight`
- `b84f24e2c6af4f1b9b58393aaacaa009:clip-2`: raw diversity `2` -> final `Highlight`
- `b84f24e2c6af4f1b9b58393aaacaa009:clip-3`: raw diversity `2` -> final `Highlight`

## Warnings
- Mixed batch produced fewer than four flat labels.
- One flat label still dominates more than half the batch.
- Uncertainty remains above 50% on this batch.
