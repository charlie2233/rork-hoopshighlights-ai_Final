# Phase Launch91 Honest Analysis Status Copy

## Goal

Keep the iOS analysis progress UI useful during long cloud jobs without faking AI thinking, ETA, waits, or backend work.

## Change

- Added `CloudAnalysisService.safeProgressStage(_:fallback:)`.
- Cloud analysis polling now sanitizes backend `job.stage` before showing it in the app.
- Safe real phases such as `Scanning jersey colors` and `Finding candidate clips` still pass through.
- Unsafe or misleading stages fall back to the real queue/processing fallback copy.

## Blocked Stage Text

The sanitizer replaces stage text that contains:

- fake thinking language
- ETA language
- HTTP/full URL markers
- presigned URL markers
- storage object paths such as uploads/renders/render logs
- bucket, token, credential, secret, and access-key markers

This keeps the UI aligned with the product rule: cloud owns the real analysis job, and iOS shows status from actual job state only.

## Validation

- Added `testCloudAnalysisProgressStageSanitizesFakeThinkingEtaAndSensitiveText`.
- Existing `testCloudEditStatusCopyUsesRealCloudJobLanguageWithoutFakeThinking` remains the render-status guardrail.
- `XcodeBuildMCP test_sim -only-testing:HoopsClipsTests`: passed, 95 tests.
- `XcodeBuildMCP build_sim`: passed.
- `git diff --check`: passed.
- GitHub Actions were not triggered for this local copy/test hardening change.

## Launch Notes

- This does not add artificial waits or random fake status copy.
- If the backend returns richer real stages later, iOS can display them as long as they do not contain misleading, sensitive, or storage-specific text.
