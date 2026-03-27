# Implementation Plan

## Phase 0

- Sync to `origin/main`.
- Capture the repo audit and release blockers.
- Add operating docs and architecture diagrams.
- Lock the current cloud API contract with tests.

## Phase 1

- Replace the GCP control plane with Cloudflare Worker, R2, Queues, Durable Objects, and D1.
- Add signed direct uploads, job state, queue dispatch, callback handling, and delete/expiry cleanup.
- Keep a local emulation path for development.

## Phase 2

- Add the standalone Python GPU inference service.
- Define the candidate proposal, recognition, event inference, reranking, and artifact writing interfaces.
- Baseline on VideoMAE, compare against X-CLIP, and store normalized result manifests in R2.

## Phase 3

- Move production config into environment-specific iOS configuration.
- Wire cloud uploads, polling, hydration, and fallback into the app.
- Keep the on-device Vision/CoreML path intact.

## Phase 4

- Add a Vercel dashboard for review, artifact inspection, and clip moderation.
- Keep optional title/summary generation off the inference path.

## Phase 5

- Add Sentry, eval harnesses, deployment checklists, and cutover checks.
- Review residual risk before production launch.

