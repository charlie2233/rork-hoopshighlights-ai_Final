# Cloudflare Tunnel Staging Endpoint

Use this workflow when you need a durable staging endpoint for the inference service before a cloud deploy is available.

Do not use `cloudflared tunnel --url`. That quick tunnel is ephemeral and only appropriate for ad hoc debugging.

## Preferred staging target

If the inference service is already deployed to Cloud Run, use the Cloud Run URL as `INFERENCE_BASE_URL`.
That is the preferred durable endpoint for staging rollout and shadow validation.

## Named tunnel fallback

If you need to expose a local inference server through Cloudflare, create a named tunnel and route it to a durable hostname in your zone.

Example commands:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference

# Authenticate once per machine.
cloudflared tunnel login

# Create the named tunnel once.
cloudflared tunnel create hoopsclips-inference-staging

# Route a durable hostname in your Cloudflare zone to the tunnel.
cloudflared tunnel route dns hoopsclips-inference-staging inference-staging.<your-zone>
```

Copy the example config and adjust the hostname and credentials-file path:

```bash
cp /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudflared/staging-tunnel.example.yml \
  /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudflared/staging-tunnel.yml
```

Then run the helper script:

```bash
bash /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_named_tunnel.sh
```

After the tunnel is reachable, set the staging control-plane secret:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/control-plane
printf '%s' 'https://inference-staging.<your-zone>' | npx wrangler secret put INFERENCE_BASE_URL --env staging
```

Verify the service health before starting a live job:

```bash
curl https://inference-staging.<your-zone>/readyz
```

The response should report `callback`, `ingress`, and `r2` as `configured`.
