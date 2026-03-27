# AGENTS.md

Work in small, phase-scoped changes.

- Sync from `origin/main` before starting a new slice.
- Keep PRs small and phase-based; do not mix control plane, inference, iOS, and dashboard work unless the change is only compatibility wiring.
- Commit and push after each completed change set.
- Do not revert or rewrite work you did not author.
- Use subagents for parallel investigation when the task spans iOS, backend, infra, ML, web, or observability.
- Preserve the current on-device Vision/CoreML path as the fast local preview and offline fallback.
- Keep production config out of hard-coded constants. Prefer environment-specific config files and runtime-injected secrets.
- Treat the current `ios/` layout as the repo root for app/backend work.

Phase priorities:

1. Release readiness: branch sync, signing/team values, RevenueCat prod config, Google sign-in config, production cloud base URL.
2. Cloud control plane: Worker, R2, Queues, Durable Objects, D1.
3. GPU inference service: containerized Python service for FFmpeg and model inference.
4. iOS cloud integration: upload, poll, hydrate, fallback.
5. Dashboard, observability, eval, and cutover.

