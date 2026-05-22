# Phase Clip1 GPT Reranker Hardening

Date: 2026-05-22
Branch: `codex/phase-clip1-gpt-reranker-hardening`
Base: `1736602` (`codex/phase-launch6-backend-config-preflight`)

## Scope

This branch hardens the existing cloud-owned GPT highlight reranker. It does not add iOS video analysis, local rendering, local composition, or local export. iOS remains the upload/review/status/preview/download/share control surface.

## Changes

- Set OpenAI Responses API payloads to `store=false` so generated reranker responses are not stored for later API retrieval.
- Keep Structured Outputs strict JSON schema and candidate-window image inputs.
- Clamp GPT image detail to supported levels: `low`, `high`, `original`, or `auto`.
- Keep the staging Cloud Run GPT reranker launch switch explicit and disabled by default in `services/editing/cloudbuild.yaml`.
- Extend backend config preflight coverage for the GPT reranker flag and OpenAI key gate.
- Feed GPT `extendBeforeSeconds` and `extendAfterSeconds` hints into deterministic EditPlan source-window placement without letting GPT create clips or override exact timestamps.
- Clamp GPT slow-motion and caption moments to the existing candidate clip bounds before they can influence the edit plan.
- Add focused unit coverage for no-store payloads, strict schema, image detail clamping, and free/pro sampling caps without real OpenAI credentials.

## OpenAI Docs Checked

- Responses API `store` parameter: `store` controls whether the generated response can be retrieved later.
- Structured Outputs with `text.format.type = "json_schema"` and `strict = true`.
- Vision image inputs using `input_image` with base64 data URLs.
- Image detail levels: `low`, `high`, `original`, and `auto`.

## Commands And Evidence

Focused GPT reranker tests:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
```

Result:

```text
Ran 4 tests in 0.005s
OK
```

Focused EditPlan GPT regression tests:

```bash
cd ios/backend && .venv/bin/python -m unittest tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_uses_existing_clip_ids_only tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_clamps_hints_and_biases_source_window -v
```

Result:

```text
Ran 2 tests in 0.003s
OK
```

Backend/config launch preflight:

```bash
python3 scripts/launch_backend_config_preflight.py
```

Result:

```text
HoopClips backend/config launch preflight
pass=57 warn=12 fail=0
```

Python syntax check:

```bash
python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py scripts/launch_backend_config_preflight.py services/editing/tests/test_gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py
```

Result: passed with exit code 0.

Full touched editing service tests:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker services.editing.tests.test_editing_service -v
```

Result:

```text
Ran 39 tests in 26.380s
OK
```

Full edit-plan backend tests:

```bash
cd ios/backend && .venv/bin/python -m unittest tests.test_edit_plan_agent -v
```

Result:

```text
Ran 18 tests in 0.057s
OK
```

Control-plane typecheck:

```bash
npm --prefix services/control-plane run typecheck
```

Result: `tsc -p tsconfig.json --noEmit` passed.

iOS Debug simulator build:

```bash
XcodeBuildMCP build_sim -skipPackagePluginValidation
```

Result: succeeded for `HoopsClips` on simulator `7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2`. Existing warnings remain in legacy local analysis/export/test code paths; no errors.

iOS build-for-testing:

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-derived-data -skipPackagePluginValidation build-for-testing
```

Result: `TEST BUILD SUCCEEDED`. Existing Swift 6 actor/deprecation warnings remain in test/local analysis/export code paths; no errors.

Git whitespace hygiene:

```bash
git diff --check
```

Result: passed with exit code 0.

ASCII scan over changed files:

```bash
rg -n --pcre2 '[^\x00-\x7F]' ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py services/editing/cloudbuild.yaml scripts/launch_backend_config_preflight.py docs/phase_clip1_gpt_reranker_hardening.md docs/phase_clip1_gpt_highlight_reranker.md services/editing/README.md
```

Result: no matches.

Keyword leak scan over changed files:

```bash
rg -n -i 'presigned|secret|token|r2|api[_-]?key|access[_-]?key|private[_-]?key|dsn|https?://[^[:space:]\"]+|downloadUrl|uploadUrl|OPENAI' ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py services/editing/cloudbuild.yaml scripts/launch_backend_config_preflight.py docs/phase_clip1_gpt_reranker_hardening.md docs/phase_clip1_gpt_highlight_reranker.md services/editing/README.md
```

Result: expected config names, placeholder docs, source-controlled endpoints, and unit-test sentinel values only; no R2 credential values, OpenAI key values, or presigned URLs were added.

## Not Run

- No real OpenAI call.
- No staging deploy.
- No TestFlight post-install smoke.
- No live cloud render job or revision job.
