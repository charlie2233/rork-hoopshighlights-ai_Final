# Repo Map

## Source of truth

- `charlie2233/rork-hoopshighlights-ai_Final`
  - Private repo
  - Contains the Phase 4 shadow/inference pipeline under `services/inference/`
  - Holds the live eval harness (`services/inference/scripts/run_shadow_eval.py`) and nearest tests
  - Confidence: high

## Adjacent repos

- `charlie2233/Hoops_clips_final_version`
- `charlie2233/Hoops_clips_final-version`
- `charlie2233/Basketball_action_recoginition_sever`
- `charlie2233/ai-hoops-board`

These repos are related Hoops codebases, but they do not contain the Phase 4 multi-stage shadow pipeline signatures used by the current runtime and eval harness.

## Evidence used

- GitHub repo metadata for the private repo showed the expected HoopsClips description and private status.
- Recursive tree inspection found the `services/inference/` pipeline paths in the private repo.
- Recursive tree inspection on the public candidate repos did not surface the Phase 4 signatures such as `run_shadow_eval.py`, `perception_features.py`, `runtimeFusionTemporalShadow`, `uploadTraceId`, or `inferenceAttemptId`.
