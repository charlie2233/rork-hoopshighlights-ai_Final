#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_PATH="$ROOT_DIR/ios/HoopsClips.xcodeproj"
XCCONFIG_PATH="$ROOT_DIR/ios/HoopsClips/HoopsClips/Config/InternalStaging.xcconfig"

SETTINGS_FILE="$(mktemp)"
trap 'rm -f "$SETTINGS_FILE"' EXIT

xcodebuild \
  -project "$PROJECT_PATH" \
  -target HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -xcconfig "$XCCONFIG_PATH" \
  CODE_SIGNING_ALLOWED=NO \
  -showBuildSettings > "$SETTINGS_FILE"

read_setting() {
  local key="$1"
  awk -F' = ' -v wanted="$key" '$1 ~ "^[[:space:]]*" wanted "$" && $2 != "" { print $2; found=1; exit } END { if (!found) print "" }' "$SETTINGS_FILE"
}

require_exact() {
  local key="$1"
  local expected="$2"
  local value
  value="$(read_setting "$key")"
  value="$(printf '%s' "$value" | sed 's#/\$()/#//#g')"
  if [[ "$value" != "$expected" ]]; then
    printf 'Expected %s=%s, got %s\n' "$key" "$expected" "${value:-<empty>}" >&2
    exit 1
  fi
  printf '%s=expected\n' "$key"
}

require_not_exact() {
  local key="$1"
  local rejected="$2"
  local message="$3"
  local value
  value="$(read_setting "$key")"
  value="$(printf '%s' "$value" | sed 's#/\$()/#//#g')"
  if [[ "$value" == "$rejected" ]]; then
    printf 'Rejected %s=%s. %s\n' "$key" "$rejected" "$message" >&2
    exit 1
  fi
  printf '%s=not-%s\n' "$key" "$rejected"
}

require_exact "HOOPS_APP_ENV" "internal_staging"
require_exact "HOOPS_CLOUD_LAUNCH_MODE" "internal_only"
require_exact "HOOPS_CLOUD_ANALYSIS_BASE_URL" "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"
require_exact "HOOPS_CLOUD_EDIT_BASE_URL" "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"
require_exact "PRODUCT_BUNDLE_IDENTIFIER" "atrak.charlie.hoopsclips"
require_exact "MARKETING_VERSION" "1.0.0"
require_exact "CURRENT_PROJECT_VERSION" "54"
require_exact "INFOPLIST_FILE" "HoopsClips/App-Info.plist"
require_exact "CODE_SIGN_STYLE" "Automatic"
require_not_exact "CODE_SIGN_IDENTITY" "Apple Distribution" "Automatic signing archives fail when a manual distribution identity is forced without a matching manual profile."

printf 'Internal staging Release config is explicit and cloud-enabled for staging only.\n'
