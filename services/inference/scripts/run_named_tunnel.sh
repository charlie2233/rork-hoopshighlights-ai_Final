#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"
config_file="${CLOUDFLARE_TUNNEL_CONFIG:-$repo_root/services/inference/cloudflared/staging-tunnel.yml}"
tunnel_name="${CLOUDFLARE_TUNNEL_NAME:-hoopsclips-inference-staging}"
origin_url="${CLOUDFLARED_ORIGIN_URL:-http://127.0.0.1:8080}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is required but not installed." >&2
  exit 1
fi

if [[ ! -f "$config_file" ]]; then
  cat >&2 <<EOF
Missing tunnel config: $config_file

Create it from:
  $repo_root/services/inference/cloudflared/staging-tunnel.example.yml

Expected hostname: inference-staging.<your-zone>
Expected origin:    $origin_url
EOF
  exit 1
fi

if ! grep -q "service: $origin_url" "$config_file"; then
  echo "Warning: $config_file does not point at $origin_url." >&2
fi

exec cloudflared tunnel --config "$config_file" run "$tunnel_name"
