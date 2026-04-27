# Release Accessibility Smoke Checklist

Run this checklist on a physical iPhone with the Release build before App Store submission. Keep cloud analysis disabled for public GA; this checklist only covers the app/on-device path.

## Test Matrix

| Mode | Required checks |
| --- | --- |
| Normal mode | Cold launch, sign-in, import, on-device analysis, review, export, save/share, settings, and paywall remain reachable. |
| VoiceOver enabled | Primary controls have useful labels and hints; progress updates are announced; selected, locked, kept, discarded, and unavailable states are spoken. |
| Largest text size | Buttons do not clip; paywall, auth, settings, review cards, export options, and share targets remain readable and tappable. |
| Reduce Motion enabled | Decorative background/hero motion becomes static; tab swipe and option selections do not rely on motion to communicate state. |

## VoiceOver Pass Criteria

- Import button announces ready/in-progress state and cancel import is reachable.
- Source video, clip preview, history preview, and export preview have descriptive labels.
- Analysis progress announces status changes and 25/50/75/100 percent progress buckets.
- Review filters announce selected state.
- Clip rows announce label, time range, confidence, and kept/discarded state.
- Slow-motion toggle announces selected state.
- Export theme, music, quality, and format options announce selected/locked state.
- Share, Save to Photos, editor shortcuts, and social shortcuts describe what they open.
- Paywall close, loading, processing, and restore/purchase states are understandable.
- Settings sliders announce label and current value.

## Largest Text Pass Criteria

- Auth and verification buttons grow vertically instead of clipping text.
- Paywall subscribe button and sign-in-required button remain readable.
- Export editor/social shortcut labels can wrap to two lines.
- Settings sliders and values remain discoverable.

## Reduce Motion Pass Criteria

- Home/import hero and page backdrops remain visually present but static.
- Swipe navigation still changes tabs without animation.
- Option changes and verification success still update state without requiring animation.

## Evidence To Capture

- Date/time, device model, iOS version, app version/build, and Release build provenance.
- Pass/fail for each mode in the test matrix.
- Notes for any inaccessible control or clipped text.
- Unified-log reference if a crash, hang, purchase issue, import issue, or export issue appears.
