# Phase Clip1 GPT Reranker Story Order

Date: 2026-05-23
Branch: `codex/phase-clip1-gpt-reranker-story-order`

## Scope

This branch tightens the cloud-owned GPT highlight reranker so the model's `storyOrder` output is no longer ignored. iOS remains a control surface only; no local video analysis, rendering, composition, or export was added.

## What Changed

- `services/editing/editing_app/gpt_reranker.py` now parses `storyOrder` from the strict Responses API JSON payload and passes it into the deterministic rerank application.
- `ios/backend/app/editing.py` now stores a bounded `gptStoryOrderIndex` on existing candidate clips, uses that ordering ahead of score for reranked best-first plans, ignores invented clip IDs, and records applied story order in `GPTHighlightRerankSummary`.
- `services/editing/editing_app/models.py` now includes `gptRerankStoryOrderClipIds` in the AI Work Receipt and adds a non-secret summary row when story order is applied.
- `ios/HoopsClips/HoopsClips/Models/CloudEditTypes.swift` decodes the optional receipt field so iOS can display backend status without owning the reranker.

## Validation

Python syntax:

```bash
python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/editing_app/models.py services/editing/tests/test_gpt_reranker.py services/editing/tests/test_editing_service.py ios/backend/tests/test_edit_plan_agent.py
```

Result: passed.

Full editing-service tests:

```bash
/tmp/hoopclips-editing-test-venv313/bin/python -m pytest services/editing/tests -q
```

Result:

```text
45 passed in 19.72s
```

GPT reranker unit tests:

```bash
/tmp/hoopclips-editing-test-venv313/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
```

Result:

```text
Ran 8 tests
OK
```

Edit-plan agent tests:

```bash
cd ios/backend && .venv/bin/python -m unittest tests.test_edit_plan_agent -v
```

Result:

```text
Ran 19 tests
OK
```

Focused editing-service receipt test:

```bash
/tmp/hoopclips-editing-test-venv313/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_gpt_highlight_rerank_summary_feeds_render_receipt -v
```

Result:

```text
Ran 1 test
OK
```

iOS Debug simulator build:

```bash
Build iOS Apps build_sim CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment
```

Result: passed. Build log:
`/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-23T17-58-39-647Z_pid51963_da37951c.log`

iOS build-for-testing:

```bash
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip1-story-order-bft-dd CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment
```

Result: passed with existing Swift concurrency/deprecation warnings in legacy local analysis/export/test code paths.

Diff check:

```bash
git diff --check
```

Result: passed.

Pre-submission readiness gate:

```bash
python3 scripts/submission_readiness_preflight.py --archive-path /tmp/HoopsClips-Launch8-InternalStaging.xcarchive
```

Result before committing this branch:

```text
pass=18 warn=2 fail=8
```

The branch-dirty failure is expected before commit. The remaining external launch blockers are listed below.

## Remaining Blockers

- The reranker still needs a live staging smoke after OpenAI and cloud deploy credentials are configured.
- Internal TestFlight/App Store submission remains blocked by the staging Worker `/v1/editing/version` 404, missing GitHub `staging` deploy/upload inputs, and missing installed TestFlight smoke proof.
