# Phase GPT Audio Reaction Keyframes

## Goal

Improve highlight recall from loud crowd pops without letting audio alone decide the edit.

HoopClips already creates cloud-side `Crowd Reaction` candidates when the audio profile has a sharp local spike. This phase makes GPT review those candidates with reaction-specific keyframes around the sound peak so it can decide whether the pop is tied to a real made shot, block, steal, forced turnover, defensive stop, or other clear basketball highlight.

## Architecture

- Cloud backend owns audio analysis, candidate expansion, keyframe extraction, GPT clip selection, EditPlan validation, rendering, and storage.
- iOS does not perform production audio analysis, video analysis, composition, or rendering.
- GPT receives existing candidate clips plus sampled frames only. Full videos, raw source object keys, presigned URLs, FFmpeg commands, and storage credentials are not sent.
- Audio is a recall signal. GPT and validators still require visible event and outcome evidence before a clip can render as a highlight.

## Keyframe Roles

Audio-reaction candidates still include the required roles:

- `start`
- `eventCenter`
- `finish`

When the tier/keyframe budget allows more than three frames, the backend now samples:

- `reactionLeadIn`: before the crowd pop, where the play likely starts or develops.
- `reactionBuild`: shortly before the audio peak, where the shot/block/steal often becomes visible.
- `reactionAftermath`: shortly after the peak, where the outcome or possession change should be visible.
- `reactionFollowThrough`: later follow-through context for celebrations, possession, or dead-ball rejection.

Shot-specific candidates keep their normal release/rim-entry roles. Defensive candidates keep their challenge/possession-change roles. Reaction candidates use the new roles only as context for GPT review.

## GPT Contract

The payload now exposes `audioReactionVerificationRoles` in `qualityHints` and `shotTrackerRules`. The system instruction tells GPT to inspect these frames and reject candidates that only show crowd noise, dead ball, scoreboard, huddles, or post-play aftermath.

Valid outcomes still require the existing structured evidence:

- Made or missed shots need visible setup, release, ball path, rim/result, and follow-through.
- Blocks need visible challenge, ball path/control, player control, and blocked-shot outcome.
- Steals, forced turnovers, and defensive stops need visible possession/control change or stop.
- Unclear clips remain reviewable or rejected instead of being confidently rendered.

## Validation

Run:

```bash
git diff --check
cd services/editing && python -m pytest tests/test_gpt_reranker.py -q
```

## Launch Notes

- This should improve gyms where the loudest crowd reaction lands slightly after the actual play.
- It favors higher recall while preserving the validator gate, so uncertain audio-pop moments should not become fake made shots.
- Cost can rise only when these candidates are sampled for GPT-led editing; the candidate generation path remains deterministic backend analysis.
