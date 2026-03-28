# Phase 3b Label Audit

## Goal

Document where basketball label collapse occurred before the phase 3b taxonomy work, and what the new internal audit surfaces preserve.

## Where Collapse Happened

### Proposal Stage

- No major label collapse happened in candidate proposal.
- [`services/inference/app/heuristics.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/heuristics.py) only proposed temporal candidates from energy peaks and did not assign basketball classes yet.

### Base Classifier

- Raw VideoMAE top-k predictions were available, but only the normalized canonical labels were preserved in the pipeline.
- Before this phase, [`services/inference/app/backends/videomae.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/backends/videomae.py) reduced raw model labels through `normalize_action_label()` and kept only aggregated canonical `topLabels`.
- That meant the raw pre-mapping label distribution was not persisted for later audit.

### Relabel Layer

- X-CLIP suggestions were similarly collapsed into canonical labels before persistence.
- Before this phase, [`services/inference/app/backends/xclip.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/backends/xclip.py) only preserved canonical prompt mappings, not the raw prompt scores as a first-class output.

### Final Mapping Layer

- This was the main collapse point.
- [`services/inference/app/labels.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/labels.py) previously mapped broad shot-like raw labels into `jumper`, and unknown labels also tended to fall through into a generic shot bucket.
- [`services/inference/app/heuristics.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/heuristics.py) then defaulted most shot-like outputs to a made scoring event.
- [`services/inference/app/labels.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/labels.py) finally mapped canonical `jumper` to the app-facing display label `Made Shot`.
- The end result was a blind collapse from raw model variety into one display class.

## What Phase 3b Preserves Now

- Raw VideoMAE top-k labels and scores via `rawTopLabels`
- Raw X-CLIP prompt suggestions and scores via `comparisonRawTopLabels`
- Canonical post-normalization labels via `topLabels`
- Internal taxonomy fields:
  - `eventFamily`
  - `eventSubtype`
  - `shotSubtype`
  - `outcome`
- Confidence before mapping via `confidenceBeforeMapping`
- Confidence after mapping via `confidenceAfterMapping`
- Explicit uncertainty via `isUncertain`

## Backward Compatibility

- The app-facing flat display label still comes from `label` / `action`.
- The control-plane callback/result schema remains additive.
- Existing iOS review rendering continues to work without requiring a contract break.
