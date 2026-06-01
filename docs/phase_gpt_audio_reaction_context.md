# Phase GPT Audio Reaction Context

## Goal

Improve highlight recall from loud crowd or bench reactions without letting sound alone become a false scoring claim.

The backend candidate pipeline can now surface audio-pop windows near sharp crowd spikes. This phase passes that signal into the GPT-led editor as a recall hint:

- use the sampled keyframes to inspect the play around the pop
- keep the clip only when real basketball action and outcome are visible
- reject crowd-only, aftermath-only, or duplicate reaction clips
- never let GPT replace CV timestamps, FFmpeg extraction, or deterministic rendering

## Architecture

- Cloud/backend owns audio analysis, candidate recall, GPT selection, EditPlan validation, rendering, and storage.
- iOS remains the control surface for upload, review, status, preview, download, and share.
- GPT receives compact clip metadata plus sampled keyframes only. It never receives full videos, source object keys, presigned URLs, or FFmpeg commands.

## GPT Context Additions

Audio reaction candidates are identified by labels such as:

- `Crowd Reaction`
- `Crowd Pop`
- `Audio Reaction`
- `Audio Pop`

When detected, GPT payloads include:

```json
{
  "qualityHints": {
    "audioReactionCandidate": true,
    "audioReactionGuidance": "Crowd/audio pop is a recall hint only; keep or claim an outcome only when sampled frames show real basketball action and visible outcome."
  }
}
```

Agent template context also marks `candidateQuality.audioReactionCandidate` so later plan-edit logic can understand why the candidate exists.

Machine-readable GPT rules now include:

```json
{
  "audioPopIsRecallHintOnly": true,
  "audioPopOutcomeClaimsRequireSampledVisualEvidence": true
}
```

Revision planning payloads include the same quality hints so commands like `More Hype` cannot turn a crowd-pop recall window into a fake bucket, block, or steal.

## Validator Behavior

For audio reaction candidates, GPT scoring or defensive-outcome claims require stronger source support:

- good watchability or motion
- sufficient confidence
- sufficient planning score
- enough pre/post event context
- sampled visual keyframe roles for that candidate

This keeps loud-crowd windows in the reviewable pool but blocks audio-only claims like “made shot” when the sampled frames do not support the event.

## Tests

Run on this branch:

```bash
ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_marks_crowd_reaction_candidates_as_audio_recall_hints -v
PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_crowd_reaction_scoring_claim_without_visual_support -v
```

Recommended broader validation:

```bash
ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v
git diff --check
```

## Launch Note

This improves recall for plays where crowd sound happens slightly after a highlight, but it intentionally keeps review safety high. Crowd audio should help HoopClips look in the right window; GPT and validators still need visual evidence before the clip becomes part of the final render.
