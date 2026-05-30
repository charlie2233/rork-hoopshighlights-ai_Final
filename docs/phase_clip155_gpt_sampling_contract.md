# Phase Clip155 GPT Sampling Contract

Branch: `codex/phase-clip155-gpt-editor-contract-gap`

## Goal

Tighten the GPT-led highlight editor sampling contract so staging matches the launch plan:

- Free: top 8 candidate clips, 3 keyframes per clip.
- Pro/internal: 20 to 30 candidate clips, 5 to 8 keyframes per clip.
- Free daily AI edit chances remain 3.

This keeps GPT as the final semantic editor while staying cloud-only. The iOS app still only uploads, displays state, reviews, previews, downloads, shares, and sends user commands.

## Changes

- Clamped Free GPT candidate sampling to `1...8` and defaulted it to 8.
- Fixed Free GPT keyframes per clip at 3, including legacy override names.
- Clamped Pro/internal candidates to `20...30` and defaulted staging to 30.
- Clamped Pro/internal keyframes to `5...8` and defaulted staging to 8.
- Updated Cloud Build staging substitutions and GitHub deploy workflow env vars from the earlier 60-candidate/10-frame quality-beta values to the launch-shaped caps.
- Updated editing service docs and GPT-led phase docs so operator-facing instructions no longer claim Free uses 10 keyframes or 60 GPT-reviewed candidates.
- Kept OpenAI payload rules unchanged: existing candidate clips only, sampled JPEG keyframes only, `store=false`, strict JSON schema, no source URLs, no storage keys, no FFmpeg commands.

## Spark Review Note Check

The external review note flagged a bad Photos import filename interpolation in the dirty root branch. I verified the current `origin/main` worktree already has the corrected form:

```swift
URL.temporaryDirectory.appending(path: "imported_video_\(UUID().uuidString).\(fileExtension)")
```

This branch does not touch the dirty root logo/import branch or the untracked root Xcode project folders.

## Validation

Commands run:

```bash
python3 -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py scripts/launch_backend_config_preflight.py
```

Result: passed.

```bash
uv run --with-requirements ios/backend/requirements.txt --python 3.11 env PYTHONPATH=ios/backend:services/editing python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_uses_launch_contract_candidate_cap services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_env_overrides_are_launch_bounded services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_requires_shot_quality_signals_and_context_judgment -v
```

Result: passed, 4 tests.

```bash
uv run --with-requirements ios/backend/requirements.txt --python 3.11 env PYTHONPATH=ios/backend:services/editing python -m unittest services.editing.tests.test_gpt_reranker -v
```

Result: passed, 61 tests.

```bash
uv run --with-requirements ios/backend/requirements.txt --python 3.11 env PYTHONPATH=ios/backend:services/editing python -m unittest ios.backend.tests.test_edit_plan_agent -v
```

Result: passed, 97 tests.

```bash
python3 scripts/launch_backend_config_preflight.py --json
```

Result: passed static launch preflight with 81 pass, 12 warn, 0 fail.

```bash
ruby -e 'require "yaml"; YAML.load_file("services/editing/cloudbuild.yaml"); YAML.load_file(".github/workflows/cloud-edit-deploy-preflight.yml"); puts "yaml parses"'
```

Result: passed.

```bash
git diff --check
```

Result: passed.

## Remaining Launch Notes

- This branch does not deploy staging and does not spend GitHub Actions minutes.
- Real iPhone/TestFlight post-install smoke is still required after the staging stack is refreshed.
- Staging Worker/editing deployment still needs live proof before App Store submission.
