# Phase Launch182 - AI Edit Long-Reel Accuracy Pass

## Goal

Improve GPT-led highlight editing quality for longer reels without changing the cloud-first architecture.

## Finding

HoopClips can now request up to 4:30 edits and sends a large GPT candidate pool, but the GPT underfill guard still treated very long edits as acceptable with too few selected clips. For a 4:30 request, the old floor asked for about 10 kept clips and roughly 35% of target duration when the candidate pool had more to offer.

That made GPT more likely to over-prune a long team reel into a short best-of edit instead of using more clear, non-duplicate candidates.

A subagent backend audit also found the GPT candidate cap was already generous at 320 candidates, but team quick scan still gave rich clip-frame evidence to only 220 candidates. With the existing 2560 clip-frame budget, all 320 candidates can receive 8 frames each, so the tail of the candidate pool did not need to fall back to compact evidence.

A subagent iOS audit found that empty `ClipTeamAttribution.source` values could bypass the selected-team evidence requirement, making high-confidence but source-less attribution eligible as a confident team match.

## Change

- Raised the long-reel GPT underfill clip floor:
  - `181s-240s`: 14 desired clips when available.
  - `241s-270s`: 16 desired clips when available.
- Raised the minimum duration floor used to detect over-pruned GPT results:
  - `91s-180s`: 45% of requested duration.
  - `181s-270s`: 55% of requested duration.
- Kept the floor bounded by available quality candidate duration so weak or missing footage does not force impossible renders.
- Kept all full-video handling out of GPT; this only changes how the backend judges GPT decisions over existing candidate clips and sampled keyframes.
- Raised team quick scan rich candidate depth from 220 to 320 in backend defaults, Cloud Build substitutions, and launch preflight requirements.
- Added coverage proving the full 320-candidate internal pool receives 8 clip frames per candidate within the existing 2560-frame clip budget.
- Treated missing or blank iOS team attribution source as `unknown`, so it now requires frame and role evidence before auto-keep or confident selected-team matching.
- Added a visible AI Edit target/focus summary before render, showing selected-team or all-teams guardrails so users can catch the wrong target before starting an edit.

## Product Impact

- A 4:30 team reel now pressures GPT to keep more clear highlights when the candidate pool supports it.
- Long edits should better match the user's requested length instead of collapsing into only a few top clips.
- Selected-team filtering and GPT planning get stronger jersey/action evidence across the full candidate pool before clips are accepted, rejected, or kept reviewable.
- iOS is less likely to over-trust old or incomplete team attribution, and users get a clearer target/focus checkpoint in AI Edit.
- GPT still rejects boring, duplicate, unclear, or unsafe clips, but it now needs a stronger reason to return a tiny long-form edit.

## Architecture Notes

- Cloud editing service owns the rerank floor, GPT plan validation, and render safety.
- iOS still only sends options/prompts and shows status/preview/share.
- No iOS analysis, rendering, composition, export, Remotion, or Canva runtime was added.
- GPT still receives compact candidate metadata and sampled keyframes only, never full videos.

## Validation

- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py` passed.
- Focused backend tests passed:
  - `test_payload_includes_long_reel_selection_floor_for_gpt`
  - `test_long_target_duration_requires_deeper_gpt_backfill_floor`
- Full GPT reranker module passed: `services.editing.tests.test_gpt_reranker`, 71 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/team_quick_scan.py ios/backend/app/config.py ios/backend/tests/test_team_quick_scan.py ios/backend/tests/test_pipeline_quality.py scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py` passed.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan ios.backend.tests.test_pipeline_quality -v` passed: 91 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest scripts.test_launch_backend_config_preflight -v` passed: 7 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python scripts/launch_backend_config_preflight.py --json` passed: 84 pass, 12 warn, 0 fail.
- Focused iOS tests passed for target/focus summary and missing team source evidence.
- Full `HoopsClipsTests/HoopsClipsTests` passed on iPhone 17 Pro simulator (`7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2`): 97 tests passed, 0 failed.
- iOS Debug `build-for-testing` passed with `CODE_SIGNING_ALLOWED=NO`.

## Launch Status

This improves long-form AI Edit quality pressure, but it does not prove internal launch readiness by itself. Remaining launch blockers still include real-device TestFlight smoke, staging cloud edit timeout/version proof, and labeled real-footage accuracy evidence for selected-team highlights, blocks, steals, uncertain review clips, and opponent rejection.
