# Runtime Fusion Model Report

- Feature count: `65`
- Train rows: `18`
- Validation rows: `11`
- Test rows: `11`
- Support-promoted gold clips: `2`
- Promoted clip IDs: `gold-shot-blocked-layup-001, gold-shot-made-three-001`

## eventFamily
- Temperature: `0.6`
- Uncertainty threshold: `0.4418`
- Margin threshold: `0.0583`
- Train support: `{'turnover': 2, 'transition': 1, 'other': 7, 'shot_attempt': 7, 'defensive_event': 1}`
- Validation accuracy/macroF1: `0.5455` / `0.3542`
- Test accuracy/macroF1: `0.4545` / `0.35`
- Test top-2 accuracy: `0.9091`

## outcome
- Temperature: `1.05`
- Uncertainty threshold: `0.6644`
- Margin threshold: `0.2`
- Train support: `{'uncertain': 10, 'missed': 4, 'made': 3, 'blocked': 1}`
- Validation accuracy/macroF1: `0.4545` / `0.4361`
- Test accuracy/macroF1: `0.2727` / `0.2667`
- Test top-2 accuracy: `0.7273`

## shotSubtype
- Temperature: `1.5`
- Uncertainty threshold: `0.5382`
- Margin threshold: `0.2`
- Train support: `{'null': 10, 'layup': 3, 'dunk': 1, 'jumper': 1, 'putback': 2, 'three': 1}`
- Validation accuracy/macroF1: `0.2727` / `0.1889`
- Test accuracy/macroF1: `0.1818` / `0.1`
- Test top-2 accuracy: `0.8182`
