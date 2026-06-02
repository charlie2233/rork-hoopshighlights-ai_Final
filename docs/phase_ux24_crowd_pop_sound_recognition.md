# Phase UX24: Crowd Pop Sound Recognition

## Goal

Improve highlight recall by treating very loud repeated crowd/bench reactions as a strong hint that a highlight may have happened nearby.

## Change

- Added a `super_loud_cluster` audio cue for repeated, very loud crowd-pop patterns.
- Gave `super_loud_cluster` higher review/candidate reserve priority than ordinary audio spikes.
- Passed the cue through backend analysis, control-plane normalization, GPT reranker context, and iOS Review evidence copy.
- Kept audio cues as recall hints only; GPT and users still need sampled visual evidence before claiming a made shot, block, steal, or other outcome.

## Architecture

- Cloud backend extracts the audio amplitude profile from uploaded video and creates/boosts candidate windows near loud reactions.
- iOS only displays the Review evidence row and sends the selected clips/status through existing cloud flows.
- GPT receives compact candidate metadata and keyframes. It does not receive full videos and cannot generate FFmpeg commands.
- FFmpeg/render planning remains deterministic and validator-owned.

## Validation

Passed locally:

```bash
cd ios/backend && ./.venv/bin/python -m pytest tests/test_pipeline_quality.py -q
# 83 passed, 6 subtests passed in 2.87s
```

```bash
cd services/editing && ../../ios/backend/.venv/bin/python -m pytest tests/test_gpt_reranker.py -q
# 99 passed in 1.78s
```

```bash
cd services/control-plane && ./node_modules/.bin/tsx --test test/control-plane-status-transitions.test.ts
# 11 passed in 2.14s
```

```bash
cd services/control-plane && npm run typecheck
# passed
```

```bash
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16e' -derivedDataPath /tmp/hoopclips-ux23-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation
# TEST BUILD SUCCEEDED
```

```bash
git diff --check
# passed
```

## Launch Notes

- This improves recall, not final truth. Super-loud crowd pops often mean something important happened, but the app should still show them for Review when visual certainty is low.
- The cue is especially useful for blocks, steals, buzzer moments, and off-camera reactions where ordinary motion scoring can miss the play.
