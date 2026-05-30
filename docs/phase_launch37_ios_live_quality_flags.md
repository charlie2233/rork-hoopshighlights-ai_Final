# Phase Launch37: iOS Live Quality Flags

Date: 2026-05-30
Branch: `codex/phase-launch37-ios-live-quality-flags`
Base: `main` at `7d96a61` (`Merge PR #37: Clarify secret metadata preflight access`)

## Goal

Make the internal TestFlight AI Edit surface detect stale or underconfigured live editing backends before a user starts a cloud render. The cloud backend remains the owner of GPT clip selection, edit planning, revisions, rendering, and storage; iOS only reads status/flags and blocks or displays controls accordingly.

## Changes

- `CloudEditFeatureFlags` now decodes the canonical GPT-led editing flags returned by `/version`:
  - `aiClipGptEditorEnabled`
  - `aiClipGptPlanEditEnabled`
  - `aiClipGptRevisionEnabled`
  - `gptHighlightRerankerEnabled`
- iOS now computes missing launch-readiness flag names for the required live flag contract:
  - `aiEditEnabled`
  - `aiEditLiveRenderEnabled`
  - `aiEditRevisionEnabled`
  - `aiEditTemplatePackEnabled`
  - `aiClipGptEditorEnabled`
  - `aiClipGptPlanEditEnabled`
  - `aiClipGptRevisionEnabled`
  - `gptHighlightRerankerEnabled`
- `AIEditView` fails closed when cloud edit is enabled but `/v1/editing/version` is missing, fails, or returns a stale flag surface.
- `AIEditView` surfaces specific cloud status copy for disabled template packs, GPT clip selection, GPT plan editing, and GPT revision planning.
- Control-plane editing proxy tests now verify GPT flag passthrough from the internal editing service.

## Evidence

- Main after PR #37 push checks:
  - Cloud Edit Deploy Preflight push codechecks: success, run `26668461905`
  - iOS Internal TestFlight Upload no-secret codecheck: success, run `26668461889`
- Current live readiness remains blocked by deployment state, not current source:
  - staging Worker `/v1/editing/version` returns 404
  - direct Cloud Run `/version` reports stale `gitSha` and is missing GPT/live-render flags
  - latest manual secret-gated preflight was for prior main `3ae4d2a`

## Validation

Commands run from `/Users/hanfei/.config/superpowers/worktrees/rork-hoopshighlights-ai_Final/codex-phase-clip5-hybrid-recall-quality`:

```bash
git diff --check
```

Result: passed.

```bash
(cd services/control-plane && npm test -- --runInBand)
```

Result: passed, 28 tests.

```bash
(cd services/control-plane && npm run typecheck)
```

Result: passed.

```bash
xcodebuild build-for-testing \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-clip28-audit-dd \
  CODE_SIGNING_ALLOWED=NO
```

Result: passed.

XcodeBuildMCP:

```text
test_sim -only-testing:HoopsClipsTests
build_sim
```

Results:
- `HoopsClipsTests`: passed, 92 tests.
- Debug simulator build: passed.

```bash
python3 scripts/submission_readiness_preflight.py --json
```

Result after commit: failed as expected with a clean working tree. Remaining failures are the launch blockers below plus required CI/manual preflight reruns after this branch reaches `main`.

## Remaining Launch Blockers

- Cloudflare `CLOUDFLARE_API_TOKEN` still needs replacement/rescope and a manual `operation=preflight` run.
- Staging Worker and Cloud Run editing service need deployment of current source so `/v1/editing/version` proxies the canonical flag surface.
- Launch-grade real-footage team highlight accuracy report is still missing.
- Connected iPhone post-install smoke remains unproven.
- Internal TestFlight upload/archive still requires explicit workflow dispatch after deploy readiness is proven.
