# HoopsClips Dashboard

Standalone Next.js App Router scaffold for the internal review/admin surface. This app is intentionally read/review/control only:

- it talks to the Cloudflare control plane
- it does not run FFmpeg or inference
- it does not own source uploads
- it only forwards review and metadata requests

## What is in this scaffold
- `app/layout.tsx` for the global shell
- `app/page.tsx` for the overview landing page
- `app/jobs/page.tsx` for the jobs list and filters
- `app/jobs/[jobId]/page.tsx` for job detail, artifacts, clip review, and metadata actions
- `app/api/admin/**` route handlers for review and metadata requests
- `lib/control-plane.ts` for the typed API client
- `lib/env.ts` for runtime config parsing
- `lib/internal-allowlist.ts` for internal-only access gating

## Environment
Set these variables in Vercel or local `.env.local`:

- `CLOUDFLARE_CONTROL_PLANE_BASE_URL`
- `CLOUDFLARE_SERVICE_TOKEN`
- `ADMIN_ALLOWED_EMAILS`
- `ADMIN_ALLOWED_DOMAIN`
- `NEXT_PUBLIC_DASHBOARD_NAME`
- `NEXT_PUBLIC_DASHBOARD_ENV`
- `OPENAI_API_KEY` for optional metadata generation later

## Run locally
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/dashboard
npm install
npm run dev
```

## Notes
- Internal-only access is enforced by `lib/internal-allowlist.ts`.
- The control-plane client is fail-fast when base URL or service token is missing.
- Review and metadata mutations are routed through `app/api/admin/**`.
- The scaffold uses server-rendered pages and plain CSS so it can be wired up incrementally without a design-system dependency.
