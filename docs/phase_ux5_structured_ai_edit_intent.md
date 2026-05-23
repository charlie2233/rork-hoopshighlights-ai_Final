# Phase UX5 Structured AI Edit Intent

## Goal

Make the Export AI Edit text box safe for GPT-led editing by mapping user wording into deterministic structured intent before it reaches the GPT reranker.

## Architecture

- iOS still collects a short optional `userPrompt` and sends it with `CreateEditJobRequest`.
- The backend sanitizes the prompt, rejects renderer commands, URLs, presigned URL markers, and storage-key markers.
- The backend derives `EditUserPromptIntent` with bounded fields such as style intents, focus areas, tone, pacing, requested aspect ratio, requested duration, template hint, effect intensity, and audio preference.
- GPT receives `userEditIntent` only. Raw user prompt text is not included in the OpenAI payload.
- Template and plan-tier validators still decide what can actually render. A Free request can express an NBA recap or recruiting style intent, but it cannot unlock Pro template rendering.

## Structured Intent Examples

- `more hype` -> `styleIntents: ["more_hype"]`, `tone: "hype"`, `effectIntensity: "high"`.
- `focus on defense` -> `styleIntents: ["defense_focus"]`, `focusAreas: ["defense"]`.
- `30s vertical mixtape` -> `requestedDurationSeconds: 30`, `requestedAspectRatio: "9:16"`, `styleIntents: ["vertical_mixtape"]`.
- `make it NBA recap` -> `styleIntents: ["nba_recap"]`; Pro/internal can also receive `templateHint: "nba_recap_pro_v1"`.

## Safety

- GPT cannot see raw renderer commands from user text.
- GPT cannot output FFmpeg, shell, URLs, storage paths, or exact timestamps.
- Backend validators still enforce candidate IDs, clip bounds, template rules, watermark/outro policy, render cost, and safe `EditPlanPatch` paths.
- Existing deterministic fallback still works when GPT is disabled, unconfigured, or unavailable.

## Evidence

- `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py` - passed.
- `PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-ios-backend-venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent services.editing.tests.test_gpt_reranker` - 40 tests passed.
- `PYTHONPATH=ios/backend /tmp/hoopclips-ios-backend-venv/bin/python -m unittest discover ios/backend/tests` - 42 tests passed.
- `PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-ios-backend-venv/bin/python -m unittest discover services/editing/tests` - 48 tests passed, including local render/revision/history coverage.
- `npm --prefix services/control-plane test` - 20/20 tests passed.
- `npm --prefix services/control-plane run typecheck` - passed.
- `npm --prefix services/control-plane run deploy:staging:dry-run` - passed; no deploy attempted.
- `python3 scripts/submission_readiness_preflight.py` - still NO-GO with `pass=18 warn=0 fail=9`; remaining failures are external signing/upload/deploy/live-smoke blockers.
- `git diff --check` - passed.

## Launch Notes

This branch improves clipping/edit intent quality but does not unblock external submission. Internal TestFlight remains blocked until GitHub staging secrets/variables, App Store Connect inputs, staging Worker deploy, and installed device smoke are proven.
