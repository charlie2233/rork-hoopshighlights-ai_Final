# Phase UX11 Import State Recovery

## Goal

Reduce the chance that a real iPhone appears stuck on `Preparing video` after a large Photos import that actually saved successfully.

## Changes

- The import status now offers the recovery path sooner:
  - First slow-import reminder changed from 8 seconds to 4 seconds.
  - Long-running reminder changed from 45 seconds to 30 seconds.
- Import recovery copy is shorter and more direct:
  - Users are told to check History if the project already saved.
  - The status card keeps the message compact for small phones and Dynamic Type.

## Architecture Guardrails

- This is iOS import/preview/status handling only.
- No local AI analysis, rendering, composition, or export behavior was added.
- Cloud remains responsible for analysis, GPT editing, edit planning, rendering, and storage.

## Validation

- Passed: `git diff --check`.
- Passed: focused iOS import-policy tests on `iPhone 16e` simulator:
  - `HoopsClipsTests.testVideoImportPolicyUsesFileBackedVideoTypesOnly`
  - `HoopsClipsTests.testVideoImportPolicyNormalizesPhotosTransferFileExtensions`
  - `HoopsClipsTests.testVideoImportPolicyConsumesOnlyHoopClipsTemporaryPhotosTransfers`
- Passed: iOS Debug simulator build with `CODE_SIGNING_ALLOWED=NO`.
- Note: an earlier generic simulator test command failed before running because XCTest needs a concrete simulator device.

## Launch Notes

- This does not replace a real-device Photos import smoke.
- The old file-backed Photos transfer risk is already covered in `HoopsClipsTests.testVideoImportPolicyUsesFileBackedVideoTypesOnly`.
- Real-device TestFlight smoke should still verify: Photos import, Files import, close/reopen during import, History recovery, and cloud analysis kickoff after import.
