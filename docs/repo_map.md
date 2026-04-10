# Repo Map

## Source of Truth

- `charlie2233/rork-hoopshighlights-ai_Final`
  - Role: source of truth and active deployment repo
  - Visibility: private
  - Evidence:
    - Current local `origin` points to this repo.
    - Contains the Cloudflare Worker under `services/control-plane/`.
    - Contains the Python inference service under `services/inference/`.
    - Contains the live shadow-eval harness at `services/inference/scripts/run_shadow_eval.py`.
    - Contains the Phase 4 artifact chain through `docs/phase4g_proposal_conditioned_shot_head_and_hierarchical_promotion_report.md`.
    - Contains the signature fields and payload names used by the current product path: `runtimeFusionTemporalShadow`, `uploadTraceId`, `inferenceAttemptId`, `requestId`, `modelVersion`.
  - Confidence: very high

## Deployment Repo

- `charlie2233/rork-hoopshighlights-ai_Final`
  - The current Worker/runtime contract is not split into a separate deploy repo.
  - Queue dispatch, callback normalization, inference payload shaping, and shadow namespaces all live here.

## Adjacent Repos

- `charlie2233/rork-hoops-clips-cloud`
  - Role: adjacent older cloud/mobile wrapper
  - Evidence: contains Expo and cloud wiring, but not the Phase 4 shadow pipeline signatures.

- `charlie2233/Basketball_action_recoginition_sever`
  - Role: adjacent research/model repo
  - Evidence: standalone basketball action recognition server and training code; not wired into the current control-plane/runtime contract.

- `charlie2233/ai-hoops-board`
  - Role: adjacent product/UI repo
  - Evidence: tactics board/PWA only; no direct Worker or inference coupling found.

- `charlie2233/Hoops_Clips`
- `charlie2233/Hoops_Clips_FInal`
- `charlie2233/new-hoops-clips`
- `charlie2233/new-hoops-clips-160`
- `charlie2233/hoops-clips-new`
  - Role: adjacent or legacy Hoops repos
  - Evidence: GitHub repo inventory shows they are separate Hoops-named repositories, but the active Phase 4 control-plane/runtime signatures and branch lineage are absent from the checked-out source repo and do not appear in the active deployment branch chain.

## Scaffold Or Legacy Repos

- `charlie2233/Hoops_clips_final_version`
- `charlie2233/Hoops_clips_final-version`

These repos are related Hoops codebases, but they do not contain the Phase 4 multistage shadow pipeline signatures used by the current runtime and eval harness.

## Private Clones And Generated Scaffolds

- `charlie2233/hoops-clips_2_with-Rorks`
- `charlie2233/rork-hoops-clips-cloud-clone-clone`
- `charlie2233/rork-hoops-clips-cloud-clone-clone-clone-885`
- `charlie2233/rork-hoops-clips-cloud-clone-clone-clone-816`
- `charlie2233/rork-hoops-clips-cloud-clone-clone-clone-132`
  - Role: generated clones or scaffolds
  - Evidence: GitHub metadata marks them as Rork-created clones. None is the current local `origin`, and none is referenced by the active Phase 4 branch lineage or deployment wiring.

## Evidence Used

- GitHub repo metadata for the private repo showed the expected HoopsClips description and private status.
- GitHub repository inventory for `charlie2233` surfaced the broader Hoops repo family, including adjacent public repos and private clone variants.
- Recursive tree inspection found the `services/inference/` pipeline paths in the private repo.
- Recursive tree inspection on the public candidate repos did not surface the Phase 4 signatures such as `run_shadow_eval.py`, `perception_features.py`, `runtimeFusionTemporalShadow`, `uploadTraceId`, or `inferenceAttemptId`.
- The active phase branch lineage exists only in this repo, including `codex/phase4a-*` through `codex/phase4h-*`.
