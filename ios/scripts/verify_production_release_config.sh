#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_PATH="$ROOT_DIR/ios/HoopsClips.xcodeproj"
EXPECTED_BUILD_NUMBER="${EXPECTED_BUILD_NUMBER:-}"

if [[ ! "$EXPECTED_BUILD_NUMBER" =~ ^[0-9]+$ ]]; then
  echo "EXPECTED_BUILD_NUMBER must be a positive integer." >&2
  exit 1
fi

SETTINGS_FILE="$(mktemp)"
trap 'rm -f "$SETTINGS_FILE"' EXIT

xcodebuild \
  -project "$PROJECT_PATH" \
  -target HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  CURRENT_PROJECT_VERSION="$EXPECTED_BUILD_NUMBER" \
  CODE_SIGNING_ALLOWED=NO \
  -showBuildSettings > "$SETTINGS_FILE"

read_setting() {
  local key="$1"
  awk -F' = ' -v wanted="$key" '$1 ~ "^[[:space:]]*" wanted "$" && $2 != "" { print $2; found=1; exit } END { if (!found) print "" }' "$SETTINGS_FILE"
}

normalized_setting() {
  read_setting "$1" | sed 's#/\$()/#//#g'
}

require_exact() {
  local key="$1"
  local expected="$2"
  local value
  value="$(normalized_setting "$key")"
  if [[ "$value" != "$expected" ]]; then
    printf 'Expected %s=%s, got %s\n' "$key" "$expected" "${value:-<empty>}" >&2
    exit 1
  fi
  printf '%s=expected\n' "$key"
}

require_production_https_url() {
  local key="$1"
  local value
  value="$(normalized_setting "$key")"
  if [[ ! "$value" =~ ^https://[^[:space:]]+$ ]]; then
    printf '%s must be a non-empty HTTPS URL.\n' "$key" >&2
    exit 1
  fi
  if [[ "$value" =~ [Ss][Tt][Aa][Gg][Ii][Nn][Gg] ]] || [[ "$value" =~ localhost ]] || [[ "$value" =~ 127\.0\.0\.1 ]]; then
    printf '%s still points at a staging or local endpoint.\n' "$key" >&2
    exit 1
  fi
  printf '%s=production-shaped\n' "$key"
}

require_exact "HOOPS_APP_ENV" "production"
require_exact "HOOPS_CLOUD_LAUNCH_MODE" "enabled"
require_production_https_url "HOOPS_CLOUD_ANALYSIS_BASE_URL"
require_production_https_url "HOOPS_CLOUD_EDIT_BASE_URL"
require_exact "PRODUCT_BUNDLE_IDENTIFIER" "atrak.charlie.hoopsclips"
require_exact "MARKETING_VERSION" "1.0.0"
require_exact "CURRENT_PROJECT_VERSION" "$EXPECTED_BUILD_NUMBER"
require_exact "INFOPLIST_FILE" "HoopsClips/App-Info.plist"
require_exact "CODE_SIGN_STYLE" "Automatic"

printf 'Production Release config is cloud-only and contains no staging/local endpoint markers.\n'
