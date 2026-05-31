# Phase Launch93 Photos Import Temporary File Cleanup

## Goal

Reduce large-video import friction during the post-install TestFlight smoke path without moving analysis or rendering onto iOS.

## Change

- Photos imports still use file-backed `Transferable` representations only.
- After `HighlightsViewModel.loadVideo(url:)` creates the persistent HoopClips project copy, the Photos temporary import file is removed on a detached utility task.
- The cleanup only removes files under the process temporary directory.

## Architecture

This stays within the allowed iOS control-surface work:

- iOS imports/copies the selected source into the app project library.
- Cloud still owns analysis, GPT clip selection, edit planning, rendering, storage, and revisions.
- No local video analysis, composition, final render, or export was added.

## Validation

- `XcodeBuildMCP test_sim -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyUsesFileBackedVideoTypesOnly`: passed.
- `XcodeBuildMCP build_sim`: passed.
- `git diff --check`: passed.
- Real-device import smoke remains blocked until the wired iPhone is available to `devicectl`.
