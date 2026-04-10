# Phase 4h Draft PR

## Title

`phase4h: calibrate proposal acceptance and unblock gate telemetry`

## Summary

This PR is the minimal Phase 4h follow-on to Phase 4g. It does not change the detector family or the app-facing contract. It makes the proposal acceptance path observable and calibratable so the next `>=60` clip shadow batch can tell us whether the blocker is:

- proposal over-rejection,
- family-gate suppression after proposal acceptance,
- shot-head coverage gaps after gate opening,
- or downstream label collapse after the gate opens.

## Why

The live system has been oscillating between:

- under-fire collapse to `Highlight / other / uncertain`, and
- over-fire collapse to `shot_attempt / made / Dunk`.

Phase 4g showed that accepted shot proposals were being suppressed before the specialized shot head could contribute. The highest-leverage next step is to add calibration and gate telemetry, not another detector swap.

## Repo Of Record

- Source of truth: `charlie2233/rork-hoopshighlights-ai_Final`
- Evidence: this repo owns the Cloudflare Worker, Python inference runtime, iOS client, `runtimeFusionTemporalShadow`, and the full Phase 4 report chain.

## Changed Files

- `services/inference/app/runtime_models/temporal_event_detector.py`
  - decouples proposal acceptance from family-gate openness
  - adds explicit family-gate rejection reasons
  - emits raw acceptance score, calibrated acceptance probability, and energy score
- `services/inference/app/temporal_encoder.py`
  - exposes raw logits needed for acceptance calibration and energy reporting
- `services/inference/training/temporal_event_detector.py`
  - adds configurable focal/class-balanced binary loss support for accept/reject training
- `services/inference/scripts/train_temporal_event_detector_candidates.py`
  - wires the new accept/reject loss configuration into detector candidate training
- `services/inference/scripts/run_shadow_eval.py`
  - reports proposal acceptance rate, family gate open rate, shot head invocation rate
  - reports Brier score, ECE-lite buckets, and coverage-vs-risk outputs
  - adds guardrails for 0%/100% acceptance and gate-suppression failure modes
- `services/inference/tests/test_temporal_event_detector.py`
  - covers new telemetry and configurable training hooks
- `services/inference/tests/test_shadow_eval.py`
  - covers the new summary metrics and guardrail failures
- `services/control-plane/test/control-plane-structured-metadata.test.ts`
  - verifies shadow metadata stays additive and contract-compatible
- `docs/repo_map.md`
- `docs/phase4h_calibrated_acceptance_and_gate_unblocking.md`
- `docs/phase4h_rollout_checklist.md`

## Key Runtime Behavior Changes

- `proposalAccepted` can now be true while `familyGateOpen` is false, and that state is explicit instead of disappearing into fallback labels.
- When the family gate stays closed, the shadow payload includes `temporal_event_detector_family_gate_rejection_reason`.
- Shadow telemetry now includes:
  - `temporal_event_detector_proposal_acceptance_raw_score`
  - `temporal_event_detector_proposal_acceptance_probability`
  - `temporal_event_detector_proposal_acceptance_energy`
- The app-facing label contract is unchanged.

## Testing

Run:

```bash
uv run --with-requirements services/inference/requirements.txt \
  python3 -m unittest \
  services.inference.tests.test_temporal_event_detector \
  services.inference.tests.test_shadow_eval
```

Optional syntax check:

```bash
python3 -m py_compile \
  services/inference/app/runtime_models/temporal_event_detector.py \
  services/inference/app/temporal_encoder.py \
  services/inference/scripts/run_shadow_eval.py \
  services/inference/tests/test_temporal_event_detector.py \
  services/inference/tests/test_shadow_eval.py \
  services/inference/training/temporal_event_detector.py
```

## Rollout Risk

- Low contract risk: app-facing payload fields are unchanged and shadow telemetry is additive.
- Medium model-behavior risk: calibration hooks may expose that the current verifier thresholds are too strict or too loose.
- Medium rollout risk: the next large shadow batch may still fail acceptance, but this PR ensures we can tell why without guessing.

## Rollout Checklist

See `docs/phase4h_rollout_checklist.md`.

## Phase 4h Acceptance Guardrails

The next `>=60` clip shadow batch should confirm:

- proposal acceptance rate between `0.35` and `0.75`
- `Highlight` dominance `< 0.55`
- raw `eventFamily=other` `< 0.40`
- no single flat label share `> 0.65`
- miss-to-made drift remains `0`

## Follow-Up

Do not jump to a new detector family until the first Phase 4h large-batch report answers:

- how many proposals are accepted,
- how many accepted proposals open the family gate,
- how many gate-open shot proposals reach the shot head,
- and whether calibration, not architecture, is the main blocker.
