# Phase Clip160: Control-Plane Audio Cue Passthrough

## Goal

Keep crowd/audio cue metadata intact as clips move through the control plane so GPT-led editing can use the backend signal that was already computed.

## Change

- Added `audioCueType`, `audioCueConfidence`, and `audioCueTime` to control-plane `CloudClip`.
- Added the same optional fields to control-plane `EditCandidateClip` for edit-job payload compatibility.
- Normalized audio cue fields from inference callback manifests.
- Added a regression assertion that a callback clip with audio cue metadata returns those fields in the public job result.

## Architecture

- Cloud backend still owns audio analysis, GPT clip selection, edit planning, and rendering.
- iOS behavior is unchanged.
- No full videos are sent to GPT.
- Audio cues remain recall metadata, not a deterministic final highlight decision.

## Validation

Local commands run:

```bash
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test
```

Results:

- Control-plane typecheck: passed.
- Control-plane tests: 33 passed.

## Launch Recommendation

Keep surfacing audio cues in AI Work Receipts and GPT context as supporting evidence. GPT should still reject audio-only, boring, duplicate, or visually unclear moments.
