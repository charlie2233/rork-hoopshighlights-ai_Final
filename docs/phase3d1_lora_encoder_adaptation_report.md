# Phase 3D1 LoRA Encoder Adaptation

Branch: `codex/phase3d1-lora-encoder-adaptation`

Base verified state: `10c6f8b`

## What changed

- Added a candidate-window-aware VideoMAE LoRA runtime path so the adapted encoder sees the same candidate clip window as the baseline runtime classifier.
- Added runtime bundle export and loading coverage for the rsLoRA VideoMAE path.
- Consolidated the annotation contract around the canonical schema file and fixed schema drift for `sourceRef` and nullable basketball-signal fields.
- Removed the hidden `scikit-learn` import dependency from dataset-export time by replacing the training-data vectorization step with a lightweight in-repo vectorizer.
- Documented the staging/runtime env needed for LoRA shadow rollout and corrected the durable-tunnel runbook path typo.

## Local validation

### Tests

- `python3 -m unittest services.inference.tests.test_pipeline services.inference.tests.test_runtime_training_data services.inference.tests.test_shadow_eval services.inference.tests.test_videomae_backend services.inference.tests.test_videomae_lora`
  - passed on system Python with LoRA-only tests skipped when `torch` is unavailable
- `services/inference/.venv/bin/python -m unittest services.inference.tests.test_annotations services.inference.tests.test_runtime_training_data services.inference.tests.test_videomae_backend services.inference.tests.test_videomae_lora services.inference.tests.test_pipeline services.inference.tests.test_shadow_eval services.inference.tests.test_runtime_model services.inference.tests.test_calibration`
  - passed
- `npm --prefix services/control-plane run typecheck`
  - passed
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Staging -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO`
  - passed

### LoRA training/export

- Installed missing repo-venv packages required for this phase:
  - `peft`
  - `scikit-learn`
- Tiny smoke export succeeded:
  - `services/inference/.venv/bin/python services/inference/scripts/train_videomae_lora.py --tiny-smoke --epochs 1 --frame-count 4 --image-size 112 --batch-size 1 --output-dir /tmp/hoopsclips-videomae-lora-smoke`
- Real pretrained VideoMAE export succeeded after fixing geometry resolution:
  - `services/inference/.venv/bin/python services/inference/scripts/train_videomae_lora.py --model-name MCG-NJU/videomae-base-finetuned-kinetics --epochs 1 --frame-count 4 --image-size 112 --batch-size 1 --output-dir /tmp/hoopsclips-videomae-lora-full2`
- The exported bundle now records the effective pretrained geometry instead of the invalid CLI override:
  - `frameCount=16`
  - `imageSize=224`

## Key fixes

### Candidate-window correctness

The first LoRA runtime draft was classifying the whole prepared source video during live inference. That would have made the adapted encoder incomparable to the baseline path and would have hidden real label quality changes inside unrelated context. The runtime path now passes `candidate.startTime` and `candidate.endTime` through the LoRA prediction call.

### Pretrained geometry correctness

The first pretrained training run failed because the script accepted `image_size=112` against a pretrained VideoMAE checkpoint that expects `224x224`. The training/export path now resolves geometry from the pretrained backbone config unless `--tiny-smoke` is used.

### Schema correctness

The canonical JSON schema previously did not match the Python annotation loader. `sourceRef` and nullable signal fields are now represented correctly in `services/inference/datasets/annotation_schema.json`.

## Remaining blocker

This branch is not live-staging verified yet.

The code is ready for a LoRA shadow rollout, but this machine does not currently have a durable inference deploy path available:

- `gcloud` is not installed, so the documented Cloud Run staging deploy path cannot be executed from here.
- `cloudflared` is installed, but no origin cert is present locally, so a named Cloudflare Tunnel cannot be created or listed from this machine without additional login/bootstrap.

Because of that, the branch does **not** yet include:

- a live staging redeploy of the inference service with `HOOPS_INFERENCE_VIDEOMAE_LORA_MODE=shadow`
- a fresh mixed-batch live shadow report comparing phase3d vs phase3d1
- a decision on whether LoRA should stay `shadow` or be promoted

## Recommended next step

Use one durable staging path, then rerun the mixed batch:

1. Preferred: deploy the current inference service to Cloud Run staging and set:
   - `HOOPS_INFERENCE_RUNTIME_MODEL_MODE=shadow`
   - `HOOPS_INFERENCE_VIDEOMAE_LORA_MODE=shadow`
   - `HOOPS_INFERENCE_VIDEOMAE_LORA_BUNDLE_PATH=/app/services/inference/models/videomae_lora_v1/runtime_bundle.json`
2. Fallback: bootstrap the named Cloudflare Tunnel from `docs/cloudflare_tunnel_staging.md`.
3. Run the mixed live batch and compare against the phase3d shadow baseline with `services/inference/scripts/run_shadow_eval.py --shadow-source runtimeFusionLoRAShadow --baseline-results ...`.
