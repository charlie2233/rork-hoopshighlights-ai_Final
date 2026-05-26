# Phase Clip6: Outcome-Aware Shot Signals

## Goal

Improve cloud highlight candidate quality so HoopClips does not send or keep tiny clips, pre-basket-only clips, or clips without visible setup and outcome context.

## Architecture

- Cloud backend owns analysis, candidate filtering, GPT selection, edit planning, rendering, and storage.
- iOS remains a control surface only.
- No local iOS analysis, composition, export, or rendering was added.
- GPT still receives only candidate clip context/keyframes downstream, never full videos.
- GPT still cannot emit FFmpeg commands or bypass validators.
- No secrets, R2 credentials, or presigned URLs were added or printed.

## Changes

### Outcome-Aware Visual Events

Native visual event scoring now groups nearby visual-motion frames and prefers the later rim/result portion of a shot-like sequence over the first release-like motion. This makes `eventCenter` more useful for downstream GPT keyframe sampling:

- `preEvent` and `release` frames are more likely to fall before the event center.
- `rim` and `outcome` frames are more likely to land at/after the event center.
- Dead aftermath motion is not allowed to displace the actual outcome frame.

### Setup and Follow-Through Required

Native shot context scoring now requires both:

- at least `2.0s` of setup before the shot event
- at least `1.25s` of outcome/follow-through after the shot event

Windows that start right before the basket, or end before the result is visible, no longer cross the shot-label classifier threshold.

### Analysis Clip Normalization Before Rerank

All analysis clips now pass through a backend normalization gate before optional external reranking:

- Tiny non-shot clips are dropped.
- Tiny shot-like clips with a usable `eventCenter` are expanded around setup plus outcome context.
- Shot-like clips without enough setup/outcome context are dropped before rerank/GPT can see them.
- `shouldAutoKeep` and slow-motion flags are cleared unless the normalized clip meets score, confidence, duration, and context requirements.

This protects the pipeline even if an external provider or mocked provider returns a high-confidence 0.1s clip.

## Tests

Commands run:

```sh
python3 -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py
```

Result: pass.

```sh
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v
```

Result: 16 tests passed.

```sh
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality ios.backend.tests.test_external_providers -v
```

Result: 24 tests passed.

```sh
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
```

Result: 83 tests passed.

```sh
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
```

Result: 65 tests passed.

```sh
git diff --check
```

Result: pass.

## New Coverage

- Provider 0.1s clips are removed before rerank.
- Hybrid merged pools drop non-overlapping tiny provider clips while keeping valid native candidates.
- Tiny shot-like clips with event center expand to setup and outcome context when possible.
- Native shot context requires both setup and follow-through.
- Visual event detection chooses rim/outcome over release in a shot sequence.
- Visual event detection does not shift to dead aftermath.

## Launch Notes

This phase is safe for internal TestFlight readiness because it only changes the cloud/native analysis candidate quality gate and tests. Live staging proof still depends on the existing provider-side gates:

- `CLOUDFLARE_API_TOKEN` saved in GitHub `staging`
- staging deploy/rollback proof
- signed TestFlight archive proof
- wired-device TestFlight smoke

## Follow-Up Recommendation

A future phase can add optional compact `nativeShotSignals` metadata into `EditCandidateClip` and GPT payloads, such as setup score, outcome score, event-center quality, and native outcome confidence. This phase avoided a cross-client schema expansion and instead improved the authoritative cloud candidate gates first.
