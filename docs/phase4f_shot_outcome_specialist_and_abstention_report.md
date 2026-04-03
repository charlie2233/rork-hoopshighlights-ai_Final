# Phase 4f: Shot Outcome Specialist And Abstention

Branch: `codex/phase4f-shot-outcome-specialist-and-abstention`  
Base verified state: `36a31bf`

## Goal

Keep the current TriDet proposal generator and open-set verifier/ranking layer frozen, but replace the downstream shot classifier with a shot-specialist head that only predicts outcome and subtype when the evidence around release and rim events is strong enough.

## What Changed

- Added shot-specialist-only bundle refresh support in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py) and [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/train_temporal_event_detector_candidates.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/train_temporal_event_detector_candidates.py) so the phase4e proposal stack stays frozen while only the shot outcome/subtype heads are retrained and recalibrated.
- Added shot-centric runtime features in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/perception_features.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/perception_features.py), [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/structured_signals.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/structured_signals.py), and [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/pipeline.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/pipeline.py), including ball-to-rim distance, rim likelihood, arc apex, vertical velocity, and near-rim velocity features.
- Tightened downstream shot handling in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py) and [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_student.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_student.py) so the specialist only runs on accepted `shot_attempt` proposals, removes the old `transition/other -> shot_attempt` upcast, and raises uncertainty when the shot head abstains.
- Extended shadow reporting in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py) and updated test coverage in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_event_detector.py), [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_shadow_eval.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_shadow_eval.py), [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_pipeline.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_pipeline.py), [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_student.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_student.py), and [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/control-plane/test/control-plane-structured-metadata.test.ts`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/control-plane/test/control-plane-structured-metadata.test.ts).
- Refreshed the deployed staging bundle in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/models/temporal_event_detector_v1.json`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/models/temporal_event_detector_v1.json) and updated [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudbuild.yaml`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudbuild.yaml) to stamp the rollout as `phase4f-shot-outcome-specialist-and-abstention`.

## Local Validation

- `python -m unittest services.inference.tests.test_temporal_event_detector services.inference.tests.test_shadow_eval services.inference.tests.test_pipeline services.inference.tests.test_runtime_model services.inference.tests.test_structured_signals services.inference.tests.test_temporal_student`
- `npx tsx --test services/control-plane/test/control-plane-structured-metadata.test.ts`
- `npm --prefix services/control-plane run typecheck`

All passed before rollout.

## Offline Refresh Evaluation

- Candidate report: [`/tmp/phase4f-candidates/comparison_report.md`](/tmp/phase4f-candidates/comparison_report.md)
- Candidate JSON: [`/tmp/phase4f-candidates/comparison_report.json`](/tmp/phase4f-candidates/comparison_report.json)
- Winner bundle: [`/tmp/phase4f-candidates/temporal_event_detector_shot_specialist_refresh_v1.json`](/tmp/phase4f-candidates/temporal_event_detector_shot_specialist_refresh_v1.json)

Key offline comparison:

- Baseline proposal acceptance stayed at `0.5455` with accepted-shot outcome accuracy `0.8`, dunk dominance `0.4`, and uncertainty `0.4545`.
- The shot-specialist refresh improved accepted-shot outcome accuracy to `1.0`, reduced dunk dominance to `0.0`, raised abstention to `0.6`, and shifted accepted-shot subtype distribution to `{"jumper": 1, "null": 4}`.
- Offline winner: `shot-specialist-refresh`

The offline refresh looked directionally correct: fewer invented dunks, higher abstention, and better made-vs-missed separation without retraining the proposal stack.

## Staging Rollout

- Cloud Run build: `d4f88155-17db-4b8b-9693-8f22cd2365d6`
- Cloud Run revision: `hoopsclips-inference-staging-00029-jxq`
- Cloud Run URL: [https://hoopsclips-inference-staging-568888872909.us-central1.run.app](https://hoopsclips-inference-staging-568888872909.us-central1.run.app)
- Cloud Run direct URL: [https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app](https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app)
- Worker URL: [https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev](https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev)
- `/version` returned `phase4f-shot-outcome-specialist-and-abstention`

## Worker-Path Smoke

The bundled Node happy-path smoke hit a transient polling transport failure twice with `ECONNRESET`, the same class of network failure seen earlier in this staging path. I did not change the control-plane contract or the smoke script for that.

A retrying manual Worker-path smoke completed successfully:

- Trace id: `phase4f-smoke-003`
- Job id: `d681c1f63c9f47399f1dd8328b7c9e79`
- Upload trace id: `71b819332db54e5697c4dee2675def5b`
- Inference attempt id: `04ec150e04274a5192b9950591b562b3`
- Request id: `b345e100-bae0-4440-9907-afff987185d1`
- Final status: `completed`
- Clip count: `1`

## Simulator Upload Smoke

The staging iOS app built and launched successfully on the booted simulator, then reached `Review` with live trace metadata visible.

- Screenshot: ![phase4f iOS smoke](/tmp/phase4f-ios-smoke.png)
- Visible fields on screen:
  - `requestId`
  - `uploadTraceId`
  - `inferenceAttemptId`
  - `modelVersion`

This confirms the app-side Review card and trace metadata contract stayed intact.

## Mixed Live Shadow Batch

- Manifest size: `8` uploads
- Batch summary: [`/tmp/phase4f-batch/summary.json`](/tmp/phase4f-batch/summary.json)
- Shadow report markdown: [`/tmp/phase4f-batch/shadow-report/shadow_eval_report.md`](/tmp/phase4f-batch/shadow-report/shadow_eval_report.md)
- Shadow report json: [`/tmp/phase4f-batch/shadow-report/shadow_eval_report.json`](/tmp/phase4f-batch/shadow-report/shadow_eval_report.json)

Live summary from [`/tmp/phase4f-batch/shadow-report/shadow_eval_report.json`](/tmp/phase4f-batch/shadow-report/shadow_eval_report.json):

- Jobs: `8`
- Clips: `12`
- Flat label distribution: `{"Fast Break": 4, "Highlight": 8}`
- EventFamily distribution: `{"other": 2, "shot_attempt": 6, "transition": 4}`
- Outcome distribution: `{"missed": 2, "uncertain": 10}`
- ShotSubtype distribution: `{"layup": 6, "null": 6}`
- Highlight dominance: `0.6667`
- EventFamily=`other` dominance: `0.1667`
- Uncertainty rate: `0.8333`
- Outcome accuracy: `0.3333`
- Shot subtype accuracy: `0.0`
- Event spotter precision / recall: `0.6` / `1.0`
- Event detection precision / recall: `0.6` / `1.0`
- Miss-vs-made confusion: `{"expectedMadePredictedHighlight": 0, "expectedMadePredictedMiss": 0, "expectedMissPredictedHighlight": 0, "expectedMissPredictedMadeShot": 0}`

Notable live behavior:

- The phase4d/4e `Dunk` / `made` collapse did stop. The live batch no longer collapsed into one confident positive subtype.
- The branch regressed into a different failure mode: `Highlight` / `Fast Break` dominated the batch, with `Highlight` at `66.67%`.
- The live batch did not show concrete subtype collapse to `Dunk`, but it also did not demonstrate the intended shot-specialist abstention cleanly. Weak-evidence `shot_attempt` clips still carried concrete `layup` subtypes while the outcome stayed `uncertain`.
- No miss clip drifted into `Made Shot`, which is an improvement relative to the earlier TriDet-only detector path.
- The live shadow artifacts did not expose proposal-acceptance fields or shot-specialist usage flags in the returned clip payloads, so accepted-shot outcome accuracy was not measurable directly from the staging batch report. The visible downstream behavior was still negative: the broadcast shot clips mostly abstained on outcome while the batch collapsed back toward `Highlight` / `Fast Break`.

Representative live failure shape:

- The two broadcast make clips became `Highlight` / `shot_attempt` / `uncertain` / `layup`.
- The four broadcast miss clips became `Fast Break` / `transition` / `uncertain`.
- Each `DEMO_VID` upload still produced one `other` clip plus two extra `shot_attempt` clips, one of which resolved to `missed`.

## Verdict

Phase 4f is not promotable.

What improved:

- No collapse to a single confident positive label.
- No miss drift into `Made Shot`.
- `eventFamily=other` dropped to `16.67%`.
- Smoke, simulator upload, and trace metadata all stayed healthy.

What failed:

- Accepted-shot outcome improvement from offline did not carry into live staging behavior.
- Live batch flat labels collapsed back to just `2` labels.
- `Highlight` dominance worsened to `66.67%`.
- Subtype abstention on weak evidence did not hold: `shot_attempt` clips still emitted concrete `layup` subtypes under `uncertain` outcomes.
- Live outcome quality remained poor at `0.3333`.

Conclusion:

The phase4f shot-specialist refresh fixed the phase4c/4d-style `Dunk` hallucination offline and prevented a live `Made Shot` collapse, but the staging runtime still did not produce reliable shot-finish decisions on real mixed clips. The branch should remain shadow-only.
