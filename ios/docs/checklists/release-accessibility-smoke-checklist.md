# Release Accessibility Smoke Checklist

Run this checklist on a physical iPhone with the internal TestFlight or Release-candidate build before submission. For internal TestFlight readiness, use the cloud-first staging path: import, team choice, cloud upload/analysis, AI Edit render, preview, download, and share/open-in. This checklist does not approve public GA cloud cutover; public cloud ML/rendering still stays gated until production auth, storage, observability, accuracy, deploy, and smoke evidence are proven.

## Test Matrix

| Mode | Required checks |
| --- | --- |
| Normal mode | Cold launch, sign-in, Photos import, Files import, team choice, cloud upload/analysis, Review, AI Edit render, preview, download, History resume, share/open-in, settings, and paywall remain reachable. |
| VoiceOver enabled | Primary controls have useful labels and hints; progress updates are announced; selected, locked, kept, discarded, and unavailable states are spoken. |
| Largest text size | Buttons do not clip; paywall, auth, settings, team choice, review cards, AI Edit controls, status labels, History actions, and share targets remain readable and tappable. |
| Reduce Motion enabled | Decorative background/hero motion becomes static; tab swipe and option selections do not rely on motion to communicate state. |

## Full Cloud Path Pass Criteria

- Import one Photos video and one Files video without the app hanging after long-copy progress.
- Choose All teams or a detected jersey-color team before cloud analysis starts.
- Confirm cloud upload and analysis use clear status text with no fake thinking or ETA-style promises.
- Review generated clips with readable kept/discarded controls, clip details, and source playback.
- Start AI Edit only after the source is cloud-uploaded; iOS must not claim to render or analyze the final MP4 locally.
- Receive a cloud-rendered MP4, preview it in the app, download or save it, and open the system share sheet.
- Share/open the saved reel through at least Files plus one editor or social target available on the device.
- Reopen History, resume the project, watch the source, watch the saved reel, share the saved reel, and confirm delete copy is plain.

## VoiceOver Pass Criteria

- Import button announces ready/in-progress state and cancel import is reachable.
- Source video, clip preview, History preview, AI Edit preview, and export preview have descriptive labels.
- Cloud upload, analysis, and AI Edit progress announce status changes without fake thinking, vague ETA, or secret-like backend text.
- Analysis progress announces status changes and 25/50/75/100 percent progress buckets.
- Review filters announce selected state.
- Clip rows announce label, time range, confidence, and kept/discarded state.
- Slow-motion toggle announces selected state.
- Export theme, music, quality, format, AI Edit style, target length, template, and revision options announce selected/locked state.
- Download, Share, Save to Photos, Files, editor shortcuts, and social shortcuts describe what they open.
- History actions announce Resume Project, Watch Source, Watch Saved Reel, Share, and Delete Project plainly.
- Paywall close, loading, processing, and restore/purchase states are understandable.
- Settings sliders announce label and current value.

## Largest Text Pass Criteria

- Auth and verification buttons grow vertically instead of clipping text.
- Paywall subscribe button and sign-in-required button remain readable.
- Import recovery and History action labels remain readable.
- Team choice, cloud status, AI Edit generate, revision, preview, download, and share controls remain readable.
- Export editor/social shortcut labels can wrap to two lines.
- Settings sliders and values remain discoverable.

## Forbidden User-Visible Copy

Fail the smoke if any internal TestFlight screen shows:

- `thinking`, `almost there`, `hang tight`, or similar fake-work phrasing.
- `ETA`, `estimated time`, or countdown-style promises that are not backed by real job state.
- Presigned URLs, object keys, bucket names, tokens, credentials, signatures, or raw backend error payloads.
- Copy implying iOS performs production analysis, edit planning, or final MP4 rendering locally.

## Reduce Motion Pass Criteria

- Home/import hero and page backdrops remain visually present but static.
- Swipe navigation still changes tabs without animation.
- Option changes and verification success still update state without requiring animation.

## Evidence To Capture

- Date/time, device model, iOS version, app version/build, and Release build provenance.
- Pass/fail for each mode in the test matrix.
- Non-secret backend provenance: Worker/editing version SHA, workflow/run IDs, and cloud job/render IDs when visible.
- Screenshots for import progress, team choice, Review, AI Edit rendered preview, revised preview, History project detail, and share/open-in sheet.
- Notes for any inaccessible control or clipped text.
- Unified-log reference if a crash, hang, purchase issue, import issue, or export issue appears.
