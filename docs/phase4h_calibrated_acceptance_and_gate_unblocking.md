# Phase 4h: Calibrated Acceptance And Gate Unblocking

## Objective

Phase 4h is the smallest viable follow-on to Phase 4g. The goal is not a detector swap. The goal is to make acceptance, family-gate, and shot-head behavior observable and calibratable so the next live shadow batch can distinguish between:

- accepted proposals that are later suppressed,
- proposals that should have been rejected earlier,
- accepted shot attempts that never reach the shot head,
- confident positive collapse caused by downstream gating rather than proposal recall.

## Source Of Truth

- Repo of record: `charlie2233/rork-hoopshighlights-ai_Final`
- Why: this repo owns the Worker, inference service, iOS client, shadow namespaces, and the full Phase 4 artifact chain.

## Scope

### Runtime telemetry

- Decouple `proposalAccepted` from `familyGateOpen`.
- Emit an explicit `temporal_event_detector_family_gate_rejection_reason` when the gate stays closed.
- Emit:
  - raw acceptance score,
  - calibrated acceptance probability,
  - acceptance energy,
  - family gate open,
  - shot head invoked.

### Training hooks

- Add configurable focal/class-balanced loss settings for the proposal rejector and proposal acceptor.
- Keep the detector family unchanged.
- Keep the app-facing payload unchanged.

### Eval guardrails

- Extend shadow eval reporting with:
  - proposal acceptance rate,
  - family gate open rate,
  - shot head invocation rate,
  - dominant flat-label share,
  - raw `eventFamily=other` rate,
  - uncertainty rate,
  - accepted-shot outcome accuracy,
  - acceptance calibration,
  - accepted-shot outcome calibration,
  - reliability buckets,
  - coverage-vs-risk curve.
- Add failing test coverage for:
  - acceptance collapse to `0%` or `100%`,
  - accepted proposals with no family gate opening,
  - accepted proposals with no shot-head invocation.

## Code Changes

- `services/inference/app/runtime_models/temporal_event_detector.py`
  - adds calibrated acceptance telemetry and explicit family-gate rejection reasons.
- `services/inference/app/temporal_encoder.py`
  - exposes raw logits in temporal target predictions for calibration and energy reporting.
- `services/inference/training/temporal_event_detector.py`
  - adds configurable binary loss settings for proposal accept/reject training and propagates them through training helpers.
- `services/inference/scripts/run_shadow_eval.py`
  - reports gate-open and shot-head metrics, acceptance calibration, and reliability summaries.
- `services/inference/tests/test_temporal_event_detector.py`
  - covers the new telemetry fields and configurable loss hooks.
- `services/inference/tests/test_shadow_eval.py`
  - covers the new eval outputs and guardrail failure cases.

## Updated Commands

### Verify unit tests

```bash
uv run --with-requirements services/inference/requirements.txt \
  python3 -m unittest \
  services.inference.tests.test_temporal_event_detector \
  services.inference.tests.test_shadow_eval
```

### Verify syntax quickly

```bash
python3 -m py_compile \
  services/inference/app/runtime_models/temporal_event_detector.py \
  services/inference/app/temporal_encoder.py \
  services/inference/scripts/run_shadow_eval.py \
  services/inference/tests/test_temporal_event_detector.py \
  services/inference/tests/test_shadow_eval.py \
  services/inference/training/temporal_event_detector.py
```

### Retrain detector candidates with configurable accept/reject loss

```bash
uv run --with-requirements services/inference/requirements.txt \
  python3 services/inference/scripts/train_temporal_event_detector_candidates.py \
  --output-dir services/inference/evals/phase4h_temporal_detector \
  --proposal-rejector-loss-mode focal_class_balanced \
  --proposal-rejector-focal-gamma 1.75 \
  --proposal-rejector-class-balance-alpha 0.5 \
  --proposal-acceptor-loss-mode focal_class_balanced \
  --proposal-acceptor-focal-gamma 1.75 \
  --proposal-acceptor-class-balance-alpha 0.5
```

### Run shadow eval on live batch artifacts

```bash
uv run --with-requirements services/inference/requirements.txt \
  python3 services/inference/scripts/run_shadow_eval.py \
  --batch-results /tmp/hoopsclips-shadow/batch.json \
  --shadow-source runtimeFusionTemporalShadow
```

## Rollout Target

This phase is successful only if the next `>=60` clip shadow batch gives enough telemetry to evaluate these guardrails directly:

- proposal acceptance rate between `0.35` and `0.75`
- `Highlight` dominance `< 0.55`
- raw `eventFamily=other` rate `< 0.40`
- no single flat label share `> 0.65`
- miss-to-made drift stays `0`

## Remaining Blockers

- No large-batch live shadow rerun has been completed in this slice.
- The next batch still needs to prove that acceptance and family-gate coverage improve without reintroducing confident positive collapse.
