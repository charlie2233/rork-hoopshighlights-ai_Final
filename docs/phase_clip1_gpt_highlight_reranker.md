# Phase Clip1 GPT Highlight Reranker

## Branch

- Branch: `codex/phase-clip1-gpt-highlight-reranker`
- Base commit: `3872bd3` (`codex/phase-ux3-pro-template-pack`)
- Scope: add a disabled-by-default, cloud-owned GPT highlight reranker that improves candidate clip ordering and edit suggestions before the existing deterministic `EditPlan` builder.

## Architecture

The reranker is backend-only. iOS does not analyze, edit, compose, or render video for this feature.

Flow:

```text
existing candidate clips
-> editing service materializes source object
-> FFmpeg samples JPEG keyframes from candidate windows only
-> OpenAI Responses API with Structured Outputs JSON schema
-> validated decisions for existing clip IDs only
-> deterministic EditPlan builder
-> existing FFmpeg renderer
-> AI Work Receipt / render log metadata
```

GPT is not allowed to create clips, rewrite exact timestamps, run CV/tracking, invoke FFmpeg commands directly, or render video. It can only score existing candidates, reject weak/boring/duplicate clips, suggest captions, and suggest safe slow-motion/crop hints inside source bounds.

OpenAI implementation notes follow the official Responses API shape where image inputs are accepted and Structured Outputs are configured with `text.format.type = "json_schema"` and `strict = true`.

Sources:

- [OpenAI Responses API reference](https://platform.openai.com/docs/api-reference/responses/compact?api-mode=responses)
- [OpenAI Structured Outputs guide](https://platform.openai.com/docs/guides/structured-outputs?api-mode=responses&lang=python)

## Config

Safe default: off.

Environment controls:

- `HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED`: enables the reranker when true.
- `HOOPS_OPENAI_API_KEY` or `OPENAI_API_KEY`: required to call OpenAI.
- `HOOPS_GPT_HIGHLIGHT_RERANK_MODEL`: default `gpt-4.1-mini`.
- `HOOPS_GPT_HIGHLIGHT_RERANK_TIMEOUT_SECONDS`: default `18`.
- `HOOPS_GPT_HIGHLIGHT_RERANK_FREE_MAX_CLIPS`: default/cap `8`.
- `HOOPS_GPT_HIGHLIGHT_RERANK_FREE_FRAMES_PER_CLIP`: fixed at `3`.
- `HOOPS_GPT_HIGHLIGHT_RERANK_PAID_MAX_CLIPS`: default `24`, clamped to `20-30`.
- `HOOPS_GPT_HIGHLIGHT_RERANK_PAID_FRAMES_PER_CLIP`: default `5`, clamped to `5-8`.
- `HOOPS_GPT_HIGHLIGHT_RERANK_MAX_OUTPUT_TOKENS`, `HOOPS_GPT_HIGHLIGHT_RERANK_FRAME_WIDTH`, `HOOPS_GPT_HIGHLIGHT_RERANK_JPEG_QUALITY`, and `HOOPS_GPT_HIGHLIGHT_RERANK_MAX_IMAGE_BYTES` bound cost and payload size.

The `/version` response exposes only safe status: enabled/configured, model, and sampling caps. It does not expose API keys, images, source URLs, R2 credentials, or presigned URLs.

## Implementation

- `ios/backend/app/editing.py`: adds GPT decision/summary models, candidate metadata, ranking blend, caption hints, slow-motion hints, and `apply_gpt_highlight_rerank`.
- `services/editing/editing_app/gpt_reranker.py`: extracts candidate keyframes and calls OpenAI Responses API with strict JSON schema output.
- `services/editing/editing_app/main.py`: applies reranking before edit-job creation when enabled/configured and feeds summaries into render requests.
- `services/editing/editing_app/models.py`: adds receipt/timeline fields for rerank applied/fallback evidence.
- `ios/HoopsClips/HoopsClips/Models/CloudEditTypes.swift` and `AIEditView.swift`: decode optional rerank receipt fields without requiring UI changes.

## Fallback

The feature falls back to deterministic ranking when:

- the flag is disabled
- no API key is configured
- source materialization fails
- keyframe extraction fails
- OpenAI returns an HTTP/network/parse/schema error
- GPT returns no valid decisions
- GPT rejects every clip

Fallback is recorded as safe metadata (`fallbackReason`) only. No artificial waiting or fake backend work is added.

## Validation

Commands run:

```sh
python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/models.py services/editing/editing_app/main.py services/editing/editing_app/gpt_reranker.py
```

Passed.

```sh
cd ios/backend && .venv/bin/python -m unittest tests.test_edit_plan_agent
```

Passed: 17 tests.

```sh
ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_gpt_highlight_rerank_summary_feeds_render_receipt
```

Passed. This exercised a fake GPT decision path through edit creation, cloud render, and AI Work Receipt metadata without calling OpenAI.

```sh
ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service
```

Passed: 29 tests.

```sh
git diff --check
```

Passed before iOS validation and again after evidence-doc updates.

```sh
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-clip1-debug-dd CODE_SIGNING_ALLOWED=NO build
```

Passed.

```sh
xcodebuild -quiet -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-clip1-bft-dd CODE_SIGNING_ALLOWED=NO build-for-testing
```

Passed with existing Swift concurrency/deprecation warnings in legacy local analysis/export/test code paths, including `VideoAnalysisService.swift`, `VideoExportService.swift`, and `HoopsClipsTests.swift`.

System `python3 -m unittest ...` failed before test import because global Python does not have `fastapi`; rerun with `ios/backend/.venv/bin/python` passed for the focused paths above.

## Remaining Blockers

- The real TestFlight post-install smoke remains blocked until a trusted online iPhone is available.
- Live staging reranker smoke was not run because the branch has not been deployed and no OpenAI/Cloudflare/GCP production credentials should be inferred or logged from this environment.
- `services/inference` is not tracked source in this checkout; the reranker is integrated into the currently tracked editing service path.
- Production launch remains gated by the existing auth, storage, observability, render reliability, and Phase 4h confirmed-label gate.
