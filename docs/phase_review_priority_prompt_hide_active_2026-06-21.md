# Review Priority Prompt Hide Active

## Goal

Reduce repeated guidance in Review so the screen stays focused on watching the current clip and choosing Keep or Nah.

## Change

- The `Review these first` priority card now hides when the Priority filter is already active.
- The card also hides when the `Priority` filter chip is already visible, avoiding duplicate `Priority N` plus `Review these first` guidance.
- The Priority filter itself remains available in the filter bar.
- Keep/Nah, swipe, feedback tags, and detail evidence are unchanged.

## User impact

A normal user sees the priority shortcut only when it is useful. If Priority is already visible or selected, Review stops repeating the same instruction.

## Product note

This removes redundant guidance instead of adding another explanation or control.

## Validation

Not run in this pass per instruction to avoid extra simulator/build/test work unless explicitly requested.
