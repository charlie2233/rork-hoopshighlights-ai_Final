# Phase Clip1 GPT Reranker Readiness

Date: 2026-05-23
Branch: `codex/phase-clip1-gpt-reranker-readiness`
Base: `dda39c1` (`codex/phase-ux2b-freemium-pro-ui-hardening`)

## Scope

This branch re-audits and hardens the cloud-owned GPT highlight reranker already present in the launch stack. It does not add iOS video analysis, local rendering, local composition, local export, Remotion, or Canva inside iOS. iOS remains the upload, review, status, preview, download, share, and editor handoff surface.

Two read-only subagents audited the backend reranker contract and the EditPlan/AI Work Receipt integration. Their findings drove the targeted hardening below.

## Changes

- Preserve the required `start`, `event_center`, and `finish` keyframe roles even for very short candidate clips where timestamps collapse to the same frame.
- Filter OpenAI payload frames to sampled candidate clip IDs only, so a stray frame object cannot add images for a non-candidate or invented clip.
- Extend GPT payload unit coverage for compact fields, strict schema shape, no video/source URL leakage, candidate-only images, and short-clip semantic sampling.
- Attach a disabled GPT rerank summary when the service-level `gptHighlightRerankerEnabled` launch switch is off, so stored edit-job renders can expose disabled/fallback evidence in the AI Work Receipt.
- Extend the edit service render test to assert disabled rerank evidence on the stored edit-job render path.
- Add GPT reranker cost knobs to the editing service README and clarify that `/version` exposes only non-secret status and sampling caps.
- Extend launch preflight literal-secret scanning to cover GPT docs, the editing README, and the GPT reranker implementation.

## Contract Check

- Existing candidate clips only: `rerank_edit_request_with_gpt` samples from `rank_clips(request.clips)[:max_clips]`.
- No full videos to GPT: FFmpeg extracts JPEG keyframes from candidate windows; the OpenAI payload includes compact JSON plus `data:image/jpeg;base64,...` images.
- Sampling caps: Free remains top 8 clips and Pro/internal remains 20 to 30 clips; quality-beta configs can sample up to 10 frames each.
- Structured output: the Responses payload uses `text.format.type = "json_schema"` with `strict = true`.
- Output schema: `clipId`, `keep`, `highlightScore`, `watchabilityScore`, `basketballEvent`, `outcome`, `caption`, `reason`, and `suggestedEdit` with `slowMotion`, `slowMotionCenter`, `captionMoment`, `cropFocus`, `extendBeforeSeconds`, and `extendAfterSeconds`.
- Deterministic ownership: GPT can bias ranking, captions, slow-motion hints, crop focus, and source-window hints, but cannot create clips, replace FFmpeg extraction, replace CV tracking, replace rendering, or override exact timestamps.
- AI Work Receipt: applied and disabled/fallback rerank summaries flow through stored edit jobs into render timeline/receipt metadata.

Official OpenAI docs checked on 2026-05-23:

- Responses API create: https://platform.openai.com/docs/api-reference/responses/create?api-mode=responses
- Structured Outputs guide: https://platform.openai.com/docs/guides/structured-outputs
- GPT-4.1 model page: https://platform.openai.com/docs/models/gpt-4.1
- Images and vision guide: https://platform.openai.com/docs/guides/images-vision?api-mode=responses

## Commands And Evidence

Repository sync and branch state:

```bash
git fetch --prune origin
git status --short --branch
git log --oneline --decorate -6
```

Result: branch `codex/phase-clip1-gpt-reranker-readiness` on `dda39c1`; unrelated untracked root Xcode folders remain untracked and unstaged.

Python syntax check:

```bash
python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/models.py services/editing/editing_app/main.py services/editing/editing_app/gpt_reranker.py scripts/launch_backend_config_preflight.py services/editing/tests/test_gpt_reranker.py services/editing/tests/test_editing_service.py ios/backend/tests/test_edit_plan_agent.py
```

Result: passed with exit code 0.

Focused GPT reranker tests:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
```

Result:

```text
Ran 7 tests in 0.004s
OK
```

Editing service backend tests:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
```

Result:

```text
Ran 37 tests in 20.854s
OK
```

EditPlan backend tests:

```bash
cd ios/backend && .venv/bin/python -m unittest tests.test_edit_plan_agent -v
```

Result:

```text
Ran 18 tests in 0.053s
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

Warnings remain for intended production cutover blockers, Statsig runtime source, backend Sentry/RevenueCat deploy config, staging ingress posture, and internal beta defaults.

iOS Debug simulator build:

```text
XcodeBuildMCP session_show_defaults
XcodeBuildMCP build_sim CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation
```

Result: `SUCCEEDED` for `HoopsClips` on simulator `7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2`. Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-23T07-23-59-522Z_pid17685_b21e40ab.log`.

iOS build-for-testing:

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip1-gpt-readiness-bft-dd build-for-testing CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation
```

Result: `** TEST BUILD SUCCEEDED **`. Log: `/tmp/hoopclips-clip1-gpt-readiness-bft.log`.

Git whitespace hygiene:

```bash
git diff --check
```

Result: passed with exit code 0.

ASCII scan over changed files:

```bash
rg -n --pcre2 '[^\x00-\x7F]' docs/phase_clip1_gpt_reranker_readiness.md services/editing/editing_app/gpt_reranker.py services/editing/editing_app/main.py services/editing/tests/test_gpt_reranker.py services/editing/tests/test_editing_service.py services/editing/README.md scripts/launch_backend_config_preflight.py
```

Result: no matches.

Keyword leak scan over changed files and staging Cloud Build config:

```bash
rg -n -i 'presigned|secret|token|r2|api[_-]?key|access[_-]?key|private[_-]?key|dsn|https?://[^[:space:]\"]+|downloadUrl|uploadUrl|OPENAI' docs/phase_clip1_gpt_reranker_readiness.md services/editing/editing_app/gpt_reranker.py services/editing/editing_app/main.py services/editing/tests/test_gpt_reranker.py services/editing/tests/test_editing_service.py services/editing/README.md scripts/launch_backend_config_preflight.py services/editing/cloudbuild.yaml
```

Result: expected config names, placeholder docs, source-controlled endpoints, and unit-test sentinel values only; no R2 credential values, OpenAI key values, full presigned URLs, or bearer tokens were added.

## Not Run

- No real OpenAI call.
- No staging deploy.
- No live R2 render or Worker-path render smoke.
- No physical-device TestFlight post-install smoke.
- No control-plane typecheck; this branch did not edit `services/control-plane`.

## Blockers

- GPT reranker remains disabled by default in staging Cloud Build until an operator enables the switch with an OpenAI key secret and runs live staging smoke.
- Production cutover remains blocked by the existing launch gates: production Worker config, provider secrets, observability/Statsig/RevenueCat verification, and TestFlight device smoke.
- CI deploy automation still depends on valid `CLOUDFLARE_API_TOKEN` proof and deploy/rollback verification.
