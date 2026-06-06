# Phase Launch label bundle handoff - updated 2026-06-06

## Current status

The launch team/highlight reviewer bundle exists locally in a reduced current
form. It is still not launch evidence because human labels remain incomplete.

Current reduced label status:

- `status`: `incomplete`
- `launchEvidenceEligible`: `false`
- complete clips: `0/18`
- incomplete clips: `18/18`
- affected cases: `launch_label_troy_white_slice_10m_15m_current_reduced_001` and `launch_label_second_game_326_all_001`
- every incomplete clip is still missing `needsLabel=false`, `reviewedByHuman=true`, `expected.teamId`, `expected.isHighlight`, `expected.eventType`, and `expected.outcome`

## Source video inputs

The required local source videos are available at:

```text
/Users/hanfei/Downloads/HoopClips_Troy_vs_ElDorado_2026-01-28_troy_white_slice_10m-15m.mp4
/Users/hanfei/Downloads/326_1770329282.mp4
```

Do not commit source videos. They are only local review media inputs for the
label-review page.

## Current bundle generation summary

The combined reduced reviewer bundle was generated locally with two cases:

- Reduced Troy current case: `10` clips, `team_white`, color `white`.
- Second 326 case: `8` clips, all-teams mode.

Current local bundle outputs:

- `artifacts/team_highlight_labeling_bundle_launch_current_reduced/team_highlight_label_review.html`
- `artifacts/team_highlight_labeling_bundle_launch_current_reduced/manifest.json`
- `artifacts/team_highlight_labeling_bundle_launch_current_reduced/label_status.json`
- `artifacts/team_highlight_labeling_bundle_launch_current_reduced/review_queue.md`

These bundle files are ignored by `.gitignore` through the `artifacts/` rule.
They are present locally for review on this workstation, but they are not
committed to the branch.

## Launch evidence rule

The bundle is only a reviewer tool. Launch accuracy evidence remains blocked
until all 18 clips have human-reviewed labels with `needsLabel=false`,
`reviewedByHuman=true`, and the required expected fields filled in. GPT draft
labels and generated bundle files do not count as human-reviewed launch
evidence.
