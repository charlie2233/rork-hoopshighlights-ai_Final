# Phase 4h Labeling Guide

## Purpose

Use this guide to label the Phase 4h acceptor retrain inputs. The goal is to separate true hard negatives from missed basketball events and to add lightweight labels for proposals already accepted by the detector/verifier stack.

Do not change model outputs in the CSV. Fill only the reviewer columns:

- `reviewer_split_other_bucket`
- `reviewer_manual_audit_label`
- `reviewer_shot_attempt`
- `reviewer_outcome`
- `review_status`
- `reviewed_by`
- `qa_status`
- `notes`

## Review Status

- `needs_review`: default state; no human decision yet.
- `reviewed`: one reviewer completed the row.
- `needs_second_pass`: the clip is unclear, occluded, cut off, or disagrees with artifact hints.
- `blocked_missing_media`: the row cannot be reviewed because the clip/video is unavailable.

## QA Status

- `not_started`: default state.
- `qa_pass`: reviewer label is internally consistent and usable for training.
- `qa_fail`: reviewer label conflicts with the guide or required fields are missing.
- `qa_needs_tiebreak`: reviewers disagree or the clip is too ambiguous for a single-pass decision.

## Hard-Negative Buckets

Use `reviewer_split_other_bucket` only when the clip is not a real basketball event for the runtime task.

- `dead_ball`: play is stopped or clearly inactive. Examples: whistle aftermath, ball held while players reset, free-throw setup before action, stoppage after made basket. Edge case: if live action resumes and a shot/turnover occurs inside the clip, do not mark dead-ball.
- `replay_or_reaction`: broadcast replay, celebration, bench/fan reaction, player reaction shot, or post-play highlight replay. Edge case: a replay showing the actual shot is still replay_or_reaction if it is not live game action.
- `setup`: half-court setup, inbound setup, players getting into formation, casual dribbling before an attack, or camera framing before the event begins. Edge case: if the clip includes the attack start, shot release, turnover, or clear transition, mark it as a real event or ambiguous rather than setup.
- `true_negative_non_event`: camera pan, scoreboard, crowd, empty court, unrelated footage, or basketball-adjacent footage without actionable play. Edge case: if the ball/player action is visible but unclear, use ambiguous rather than true negative.

## Manual Audit Labels

Use `reviewer_manual_audit_label` for the high-level training decision.

- `true_negative_non_event`: the clip is not a runtime basketball event. Pair this with one of the hard-negative buckets above.
- `real_event_missed_by_model`: a basketball event is visible but the runtime marked it as `other` or `Highlight`.
- `ambiguous_clip`: the clip lacks enough visual evidence to call event vs non-event confidently.
- `data_sampling_issue`: the crop/window is wrong, media is corrupted, duplicate-only, or the clip does not match its artifact metadata.

## Accepted Proposal Labels

For rows with `candidate_bucket=accepted_proposal_light_label`, review the accepted proposal only.

- `reviewer_shot_attempt=yes`: visible shot attempt, layup attempt, dunk attempt, putback, or blocked shot attempt.
- `reviewer_shot_attempt=no`: accepted proposal is not a shot attempt, even if basketball action is visible.
- `reviewer_shot_attempt=uncertain`: proposal may be a shot, but timing/crop/occlusion prevents confirmation.
- `reviewer_outcome=made`: ball visibly goes through the hoop or the immediate aftermath clearly proves make.
- `reviewer_outcome=missed`: shot attempt misses and does not score.
- `reviewer_outcome=blocked`: defender blocks or clearly redirects the attempt before normal rim flight.
- `reviewer_outcome=uncertain`: outcome is not visible or cannot be trusted.

If `reviewer_shot_attempt` is `no`, leave `reviewer_outcome` blank unless a shot outcome is still visibly relevant for a nearby accepted proposal.

## Ambiguity Rules

- Prefer `ambiguous_clip` over guessing when the ball, rim, or event moment is off-screen.
- Prefer `real_event_missed_by_model` when the event is visible even if subtype is unclear.
- Prefer `setup` only when no decisive basketball event occurs inside the window.
- Do not infer made/missed from scoreboard, announcer context, or prior clip order unless the visual evidence in this clip supports it.

## QA Checklist

- Reviewer fields are filled only by a human reviewer, not by artifact metadata.
- Hard-negative rows with `reviewer_manual_audit_label=true_negative_non_event` also have `reviewer_split_other_bucket` set to one of the four hard-negative buckets.
- Real event misses do not get a hard-negative bucket.
- Accepted proposal rows have `reviewer_shot_attempt` filled.
- Accepted proposal rows with `reviewer_shot_attempt=yes` have `reviewer_outcome` filled.
- `notes` explains every `ambiguous_clip`, `data_sampling_issue`, and QA failure.
