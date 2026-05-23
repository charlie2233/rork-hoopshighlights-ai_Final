# Phase Clip1: Cookbook Revision Context

## Goal

Make GPT Edit Cool revision planning use the same Agent Template Cookbook strategy context as the initial GPT-led highlight editor. This keeps revision commands such as More Hype, NBA Style, and Shorter aligned with the selected director preset while preserving deterministic backend validation and rendering.

## Repo And Branch Evidence

- Branch: `codex/phase-clip1-cookbook-revision-context`
- Base commit: `fb48f73` (`main`, `origin/main`) - Agent Template Cookbook landed on main.
- Current checkout has no `services/inference` directory; inference remains external or branch-specific in this repo state.
- Original user checkout at `/Users/hanfei/rork-hoopshighlights-ai_Final` remains dirty on another branch with unrelated local files; this branch was made in the clean worktree.

## Implementation

- Added `agentTemplateCookbook` to GPT revision patch payloads in `services/editing/editing_app/gpt_reranker.py`.
- The revision payload resolves the active `TemplatePack`, builds compact cookbook context from existing candidate clips, and keeps `EditPlanPatch` as strict Structured Outputs JSON only.
- No new GPT calls were added.
- No iOS analysis, rendering, composition, or export behavior changed.
- No full video, source object key, presigned URL, R2 credential, or FFmpeg command is sent to GPT.

## Test Coverage

Added `test_revision_patch_payload_uses_agent_template_cookbook` to `services/editing/tests/test_gpt_reranker.py`.

The test proves:

- Revision payloads use `store=false`.
- Revision output remains JSON-schema structured output.
- A Pro/internal Cinematic Mixtape revision receives `cinematic_mixtape_pro_v1` cookbook rules.
- Candidate context stays compact.
- `sourceObjectKey`, source upload object paths, `downloadUrl`, and `https://` are absent from the revision payload.

## Commands Run

```bash
git status --short --branch
git fetch --all --prune
gh run list --repo charlie2233/rork-hoopshighlights-ai_Final --limit 20 --json databaseId,workflowName,headBranch,headSha,status,conclusion,createdAt,updatedAt,event,displayTitle,url
curl -sS -o /tmp/hoopclips-worker-version-<timestamp>.json -w '%{http_code}\n' https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version
gh run view 26342828803 --repo charlie2233/rork-hoopshighlights-ai_Final --json databaseId,headSha,status,conclusion,createdAt,updatedAt,url,jobs
gh secret list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name,updatedAt
gh variable list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name,updatedAt
python3 -m py_compile services/editing/editing_app/gpt_reranker.py
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_revision_patch_payload_uses_agent_template_cookbook -v
```

## Current Launch Blockers

- Live staging Worker still returns `404` for `GET /v1/editing/version`, so live kill-switch and editing-service version proof through the Worker remains unverified.
- Latest manual `Cloud Edit Deploy Preflight` run `26342828803` on 2026-05-23 failed in job `Verify cloud edit deploy secrets` at `Assert cloud deploy inputs are present`. The Worker typecheck/dry-run job passed.
- Local environment does not have `CLOUDFLARE_API_TOKEN` set.
- GitHub `staging` environment secret and variable name lists returned empty arrays, so deploy inputs are still missing or not visible to this token.
- Full installed TestFlight smoke remains unproven: upload/import -> cloud analysis -> Review -> Export -> AI Edit -> render -> preview -> More Hype revision -> revised preview -> share/open-in.

## Launch Recommendation

After staging deploy credentials are configured and the Worker is refreshed, run the live GPT-led edit smoke with at least one base template and one internal/Pro template. Confirm the More Hype/NBA Style/Shorter revision request receives cookbook context, returns validated `EditPlanPatch` JSON, renders a revised preview, and never logs source object keys or full presigned URLs.
