# Phase Clip56: Defensive Review Reserve

## Goal

Keep real blocks, steals, forced-turnover, and defensive-stop highlights visible for user review and GPT-led editing even when high-scoring made-shot clips fill the Review cap first.

## Change

- Review trimming now reserves a small number of high-quality defensive clips before filling the remaining slots in original ranked order.
- Defensive reserve candidates must still pass the existing analysis auto-keep quality gate, so weak defensive-looking noise does not displace stronger clips.
- The existing selected-team uncertain reserve still runs, which means selected-team workflows can keep both strong defensive highlights and uncertain team-attribution clips for user review.
- The output order remains source/rank order after reserves are selected, so this does not create artificial story ordering in analysis results.

## Architecture

- Cloud backend owns this clip-selection policy.
- iOS behavior is unchanged: it still displays Review clips, `Team?`/`Outcome?`/`Timing?` badges, and lets the user keep/discard before export.
- No local iOS analysis, rendering, composition, or FFmpeg command generation was added.

## Validation

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py` passed.
- Focused backend tests passed: 3 tests covering defensive Review reserve, selected-team uncertain reserve, and best uncertain clip selection.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` passed: 142 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` passed: 90 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 42 tests.

## Launch Recommendation

Keep this reserve enabled for internal beta. Labeled evaluation should include games where blocks/steals are lower ranked than made shots so the 85% target measures defensive recall, not only scoring precision.
