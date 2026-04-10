# Phase 4h Rollout Checklist

## Staging Validation Result - 2026-04-10

- Result: no-go; hold and recalibrate before any larger shadow rollout.
- Batch: `43` completed Worker-path uploads produced `63` clips through staging.
- Eval artifact: `services/inference/evals/phase4h_staging_eval/shadow_eval_report.json`.
- Audit queue: `services/inference/evals/phase4h_staging_eval/phase4h_audit_queue.json`.
- Proposal acceptance rate: `0.127` (`8` / `63`), below the `0.35` lower bound.
- Family gate open rate: `0.0`; accepted proposals existed but `familyGateOpenCount == 0`.
- Shot head invocation rate: `0.0`; accepted-shot outcome accuracy is not computable.
- Dominant flat label: `Highlight` at `1.0`; raw `eventFamily=other` is `1.0`.
- Miss-to-made drift: `0`, but this is weak because no clip reached a made-shot label.
- Telemetry gap: staged payload lacks calibrated acceptance probability, acceptance energy score, and explicit family-gate rejection reasons.

## Before Shadow Deploy

- Confirm branch is `codex/phase4h-calibrated-acceptance-gate-unblocking`.
- Confirm `services/inference/tests/test_temporal_event_detector.py` passes.
- Confirm `services/inference/tests/test_shadow_eval.py` passes.
- Confirm syntax check passes for all touched Phase 4h files.
- Confirm no app-facing contract fields changed in control-plane or iOS payload parsing.

## After Shadow Deploy

- Run one Worker-path smoke job.
- Confirm `requestId`, `uploadTraceId`, `inferenceAttemptId`, and `modelVersion` are present end to end.
- Confirm `runtimeFusionTemporalShadow` is non-null on the returned clips.
- Confirm `temporal_event_detector_family_gate_rejection_reason` is present whenever `familyGateOpen == false`.
- Confirm `temporal_event_detector_proposal_acceptance_probability` and `temporal_event_detector_proposal_acceptance_energy` are present in shadow metadata.

## Large Batch Eval

- Run a mixed shadow batch with at least `60` clips.
- Record:
  - proposal acceptance rate,
  - family gate open rate,
  - shot head invocation rate,
  - dominant flat-label share,
  - raw `eventFamily=other` rate,
  - uncertainty rate,
  - accepted-shot outcome accuracy,
  - acceptance calibration,
  - accepted-shot outcome calibration,
  - coverage-vs-risk curve.

## Guardrail Checks

- Proposal acceptance rate stays between `0.35` and `0.75`.
- `Highlight` dominance stays below `0.55`.
- raw `eventFamily=other` stays below `0.40`.
- No single flat label exceeds `0.65`.
- Miss-to-made drift remains `0`.
- Accepted proposals do not get suppressed so completely that `familyGateOpenCount == 0`.
- Accepted proposals do not get suppressed so completely that `shotHeadInvocationCount == 0`.

## Stop Conditions

- If `proposalAcceptanceRate` collapses to `0.0` or `1.0`, stop and inspect acceptor calibration before touching the detector.
- If accepted proposals exist but `familyGateOpenCount == 0`, stop and inspect gate rejection reasons before changing label mapping.
- If `familyGateOpenCount > 0` but `shotHeadInvocationCount == 0`, stop and inspect family output collapse before changing the shot head.
