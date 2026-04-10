# Phase 4g: Proposal Conditioned Shot Head And Hierarchical Promotion

Branch: `codex/phase4g-proposal-conditioned-shot-head-and-hierarchical-promotion`  
Base verified state: `a600a21`

## Goal

Fix the downstream shot-specialist failure by retraining it on detector/verifier-accepted proposals, calibrating outcome/subtype probabilities on proposal-conditioned gold data, and promoting uncertain `shot_attempt` clips more truthfully than the old `Highlight` fallback.

## What Changed

- Rebuilt the proposal-conditioned shot-specialist training path in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py), [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/train_temporal_event_detector_candidates.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/train_temporal_event_detector_candidates.py), and [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py) so the shot head trains and calibrates on accepted and borderline proposals from the frozen TriDet plus verifier stack instead of generic aligned clips.
- Added outcome-first subtype gating and shadow-only generic `Shot Attempt` promotion in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py), while keeping the shared live app label mapper unchanged.
- Extended shadow eval and control-plane compatibility coverage in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py), [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_event_detector.py), and [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/control-plane/test/control-plane-structured-metadata.test.ts`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/control-plane/test/control-plane-structured-metadata.test.ts).
- Fixed a shadow-only staging crash in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/perception_features.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/perception_features.py) after the first rollout attempt. The temporal shadow path was failing on Cloud Run with `NameError: name '_arc_score' is not defined`; the fix switched the arc helper to a stable exported symbol so the proposal-conditioned detector could execute in staging.

## Local Validation

- `env PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/.venv/bin/python -m unittest services.inference.tests.test_temporal_event_detector services.inference.tests.test_shadow_eval`
- `env PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/.venv/bin/python -m unittest services.inference.tests.test_runtime_model`
- `env PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/.venv/bin/python -m unittest services.inference.tests.test_perception_features services.inference.tests.test_temporal_event_detector services.inference.tests.test_shadow_eval services.inference.tests.test_runtime_model`
- `npx tsx --test services/control-plane/test/control-plane-structured-metadata.test.ts`
- `npm --prefix services/control-plane run typecheck`

All passed locally before the final rerun deployment.

## Offline Refresh Evaluation

- Candidate report: [`/tmp/phase4g-proposal-conditioned-shot-head/comparison_report.md`](/tmp/phase4g-proposal-conditioned-shot-head/comparison_report.md)
- Candidate JSON: [`/tmp/phase4g-proposal-conditioned-shot-head/comparison_report.json`](/tmp/phase4g-proposal-conditioned-shot-head/comparison_report.json)
- Winner: `shot-specialist-refresh`

Offline summary:

- The proposal-conditioned shot-specialist refresh remained the winner.
- Outcome calibration on the held-out accepted-shot gold rows was strong.
- Subtype calibration was still weaker than outcome calibration, but it no longer showed the earlier `Dunk` domination offline.

The offline result looked acceptable enough to stage, so phase4g proceeded to shadow rollout.

## Staging Rollout Attempt 1

- Cloud Build: `1235ff62-2f5e-4fac-8f47-490700ed3447`
- Cloud Run revision: `hoopsclips-inference-staging-00031-xjs`
- Durable URL: [https://hoopsclips-inference-staging-568888872909.us-central1.run.app](https://hoopsclips-inference-staging-568888872909.us-central1.run.app)
- Direct URL: [https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app](https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app)
- `/version` returned `phase4g-proposal-conditioned-shot-head-and-hierarchical-promotion`

Initial smoke and simulator checks completed, but the mixed live shadow batch was invalid.

### First Smoke

- Job id: `49fcca432db3447a834be5004887b88b`
- Upload trace id: `6c4042faf4eb45eda295f9f20bc40177`
- Inference attempt id: `af2a87a8b14b44e386a4488e13955c82`
- Final status: `completed`

### First Batch Failure

- Broken batch artifacts: [`/tmp/phase4g-batch/summary.json`](/tmp/phase4g-batch/summary.json), [`/tmp/phase4g-batch/shadow-report/shadow_eval_report.json`](/tmp/phase4g-batch/shadow-report/shadow_eval_report.json)
- Raw clip payloads showed `runtimeFusionTemporalShadow: null` on every clip.
- Cloud Run logs showed the real failure:
  - `temporal shadow prediction failed ... NameError: name '_arc_score' is not defined`

Because the shadow payload was null, the first batch report was not a valid phase4g shadow evaluation. It was effectively measuring the flattened fallback labels, not the candidate model.

## Shadow Crash Fix

- Fix commit: `1434f0c`
- Fix: [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/perception_features.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/perception_features.py)

After the fix, the branch was redeployed and validated again from scratch.

## Staging Rollout Attempt 2

- Cloud Build: `dfe63f30-ed20-49ca-a327-7f1ba0894983`
- Cloud Run revision: `hoopsclips-inference-staging-00033-5f2`
- Durable URL: [https://hoopsclips-inference-staging-568888872909.us-central1.run.app](https://hoopsclips-inference-staging-568888872909.us-central1.run.app)
- Direct URL: [https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app](https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app)
- `/version` returned `phase4g-proposal-conditioned-shot-head-and-hierarchical-promotion`
- `/readyz` returned `ready`

### Worker-Path Smoke

- Trace id: `phase4g-smoke-002`
- Job id: `54ee8693858a44c0b4e9143b741783a6`
- Upload trace id: `a9ca0a52650846b1bddb8c3e11e2a5e1`
- Inference attempt id: `a348507bbed64eb488245a3bb24068bf`
- Final status: `completed`
- Clip count: `1`

### Simulator Upload Smoke

- Screenshot: ![phase4g iOS smoke](/tmp/phase4g-ios-smoke-final.png)
- The app reached `Review` and the trace card showed:
  - `requestId`
  - `uploadTraceId`
  - `inferenceAttemptId`
  - `modelVersion`

The first simulator screenshot in this phase was contaminated by persisted app state. A clean uninstall/reinstall rerun fixed that and produced the valid screenshot above.

### Mixed Live Shadow Batch

- Batch summary: [`/tmp/phase4g-rerun-batch/summary.json`](/tmp/phase4g-rerun-batch/summary.json)
- Shadow report markdown: [`/tmp/phase4g-rerun-batch/shadow-report/shadow_eval_report.md`](/tmp/phase4g-rerun-batch/shadow-report/shadow_eval_report.md)
- Shadow report JSON: [`/tmp/phase4g-rerun-batch/shadow-report/shadow_eval_report.json`](/tmp/phase4g-rerun-batch/shadow-report/shadow_eval_report.json)

The rerun batch is valid:

- `runtimeFusionTemporalShadow` was non-null on all `12` clips
- Candidate namespace was `runtimeFusionTemporalShadow` with share `1.0`
- No Cloud Run `temporal shadow prediction failed` errors were emitted after the patched rollout

Live shadow summary:

- Jobs: `8`
- Clips: `12`
- Flat label distribution: `{"Highlight": 12}`
- EventFamily distribution: `{"other": 12}`
- Outcome distribution: `{"uncertain": 12}`
- ShotSubtype distribution: `{"null": 12}`
- Highlight dominance: `1.0`
- EventFamily=`other` dominance: `1.0`
- Uncertainty rate: `1.0`
- Accepted-shot outcome accuracy: `0.0`
- Accepted-shot abstention rate: `1.0`
- Dunk dominance: `0.0`
- Miss-vs-made confusion: `{"expectedMadePredictedHighlight": 0, "expectedMadePredictedMiss": 0, "expectedMissPredictedHighlight": 0, "expectedMissPredictedMadeShot": 0}`

Internal detector counters from the raw shadow payloads:

- Proposal accepted: `2 / 12`
- Classifier gate open: `0 / 12`
- Shot specialist used: `0 / 12`
- Generic `Shot Attempt` promoted: `0 / 12`
- Likely shot attempt: `0 / 12`
- Rejector labels: `ambiguous 10`, `real_event 2`
- Acceptor labels: `reject 10`, `accept 2`
- Event-spotter families: `other 4`, `shot_attempt 4`, `transition 4`

Interpretation:

- The `_arc_score` shadow crash is fixed. The temporal shadow runtime now executes and returns payloads correctly.
- The model itself regressed into total open-set rejection on the mixed live batch.
- The proposal verifier accepted only `2` clips, but the downstream family gate still never opened.
- Because the family gate never opened, the phase4g shot-specialist head never ran on any live clip in the valid rerun batch.
- The new hierarchical promotion path also never triggered, so uncertain shot attempts still surfaced as `Highlight`.

## Acceptance Check

Failed.

Acceptance target vs observed:

- Accepted-shot outcome accuracy `> 0.6`: observed `0.0`
- Subtype abstention on weak evidence: technically yes, but only because subtype was never reached; not the intended success mode
- No collapse to one subtype: passed (`null` only), but the branch collapsed to a single flat label instead
- No miss drift into `Made Shot`: passed
- No regression in smoke / simulator / trace metadata: passed on the patched rerun

## Verdict

Phase 4g is not promotable.

What succeeded:

- The live control-plane contract stayed unchanged.
- The simulator Review card and trace metadata still work after a clean app reset.
- The shadow payload is now stable and non-null in live batch artifacts.
- The branch avoided a `Made Shot` / `Dunk` hallucination collapse.

What failed:

- The proposal-conditioned shot-specialist improvements did not transfer into usable live shot classification.
- The valid live shadow rerun collapsed completely into `Highlight / other / uncertain / null`.
- The proposal gate and family gate prevented the shot-specialist head from running at all on the mixed live batch.
- The shadow-only generic `Shot Attempt` promotion never activated in live staging.

Conclusion:

Phase4g fixed the shadow runtime crash but did not fix the underlying model problem. The branch should remain shadow-only. The next change should target the verifier/family-gate path that is suppressing accepted shot proposals before the specialized outcome head can contribute.
