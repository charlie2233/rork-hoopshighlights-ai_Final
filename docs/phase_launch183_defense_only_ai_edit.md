# Phase Launch183 Defense Only AI Edit

Date: 2026-06-01
Branch: `codex/phase-launch183-defense-only-ai-edit`

## Goal

Improve HoopClips AI Edit accuracy for players, parents, and coaches who want a reel focused on defense. The app now exposes a clearer `Defense only` quick prompt, and the cloud backend maps that note to a structured `defense_only` editing intent.

## Architecture

- iOS remains a control surface only. It sends a user edit note and shows status, preview, download, and share.
- Cloud backend owns prompt parsing, GPT candidate selection, edit planning, render validation, and rendering.
- GPT still receives only existing candidate clip IDs, metadata, and sampled keyframes.
- GPT cannot generate FFmpeg commands, source video URLs, storage keys, or raw render instructions.

## Behavior

The backend now recognizes phrases such as:

- `defense only`
- `blocks and steals only`
- `just defense`
- `no offense`
- `defensive highlights only`

Those phrases produce:

- `styleIntents: ["defense_focus", "defense_only"]`
- `focusAreas: ["defense"]`
- `structuredSummary: ["defense_focus", "defense_only"]`

For GPT sampling and reranking:

- Defense-only jobs reserve the candidate budget for defensive events when enough defensive candidates exist.
- Defensive events include blocks, steals, forced turnovers, stops, deflections, charges, pressure, and loose-ball recoveries.
- Offensive makes can still fill the reel only when defensive candidates are not enough for a reviewable result.
- Selection rules sent to GPT now include `defenseOnlyRequested`, `defensiveQualityCandidateCount`, and a defense-only policy.

## iOS UX

The previous `Focus defense` quick prompt is now `Defense only`.

Prompt text:

`Defense only: prioritize blocks, steals, forced turnovers, stops, deflections, charges, and loose balls. Use offense only if there are not enough clear defensive clips.`

## Validation Log

Commands run so far:

```bash
git pull --ff-only origin main
python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_gpt_reranker.py
uv run --no-project --with-requirements services/editing/requirements.txt python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_includes_structured_user_edit_intent_without_raw_prompt services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_marks_defense_only_intent_and_quality_rules services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_reserves_buried_defensive_candidates_for_gpt_review services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_defense_only_sampling_prefers_defensive_pool_before_scoring_fill
env PYTHONPATH=ios/backend uv run --no-project --with-requirements ios/backend/requirements.txt python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_user_prompt_is_sanitized_and_mapped_to_structured_edit_intent ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_user_prompt_turnover_language_maps_to_defense_focus ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_user_prompt_defense_only_maps_to_strict_defensive_intent
uv run --no-project --with-requirements services/editing/requirements.txt python -m unittest services.editing.tests.test_gpt_reranker
env PYTHONPATH=ios/backend uv run --no-project --with-requirements ios/backend/requirements.txt python -m unittest ios.backend.tests.test_edit_plan_agent
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2 -derivedDataPath .codex-build/DerivedData build-for-testing
```

Results:

- Python compile: pass.
- Focused GPT reranker tests: 4 passed.
- Focused backend prompt-intent tests: 3 passed.
- Full GPT reranker module: 73 passed.
- Full backend edit-plan agent module: 105 passed.
- `git diff --check`: pass.
- iOS Debug build-for-testing on iPhone 17 Pro simulator `7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2`: pass.

## Remaining Launch Risk

- Needs real-device/TestFlight smoke on a long video after the connected iPhone is available.
- Needs staging cloud edit timeout/version proof.
- Needs labeled footage accuracy report for selected-team defense/offense separation, uncertain clips, blocks, steals, and opponent rejection.
