#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTERNAL_ROOT="${ROOT}/.external"
VENV_ROOT="${ROOT}/.venvs"
CREATE_VENVS="false"
INSTALL_HOOPCUT="false"
INSTALL_AUTOHIGHLIGHT="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-venvs)
      CREATE_VENVS="true"
      shift
      ;;
    --install-hoopcut)
      CREATE_VENVS="true"
      INSTALL_HOOPCUT="true"
      shift
      ;;
    --install-autohighlight)
      CREATE_VENVS="true"
      INSTALL_AUTOHIGHLIGHT="true"
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

clone_or_update() {
  local url="$1"
  local dest="$2"
  if [[ -d "$dest/.git" ]]; then
    git -C "$dest" pull --ff-only || {
      echo "Warning: failed to update $dest" >&2
      return 1
    }
  elif [[ -d "$dest" ]]; then
    echo "Skipping $dest because it exists but is not a git checkout" >&2
    return 1
  else
    git -c http.version=HTTP/1.1 clone --depth 1 "$url" "$dest" || {
      echo "Warning: failed to clone $url" >&2
      return 1
    }
  fi
  return 0
}

create_venv() {
  local name="$1"
  local venv_path="${VENV_ROOT}/${name}"
  if [[ -x "${venv_path}/bin/python" || -x "${venv_path}/Scripts/python.exe" ]]; then
    return 0
  fi
  python3 -m venv "$venv_path" || {
    echo "Warning: failed to create virtualenv at ${venv_path}" >&2
    return 1
  }
}

pip_path() {
  local name="$1"
  local base="${VENV_ROOT}/${name}"
  if [[ -x "${base}/bin/pip" ]]; then
    printf '%s' "${base}/bin/pip"
  else
    printf '%s' "${base}/Scripts/pip.exe"
  fi
}

mkdir -p "$EXTERNAL_ROOT"

clone_or_update "https://github.com/ericbh22/HoopCut_FH.git" "${EXTERNAL_ROOT}/HoopCut_FH" || true
clone_or_update "https://github.com/dshin13/autohighlight.git" "${EXTERNAL_ROOT}/autohighlight" || true

if [[ "$CREATE_VENVS" == "true" ]]; then
  mkdir -p "$VENV_ROOT"
  create_venv "hoopcut" || true
  create_venv "autohighlight" || true
fi

if [[ "$INSTALL_HOOPCUT" == "true" ]]; then
  "$(pip_path hoopcut)" install -r "${EXTERNAL_ROOT}/HoopCut_FH/requirements.txt"
fi

if [[ "$INSTALL_AUTOHIGHLIGHT" == "true" ]]; then
  echo "Installing autohighlight dependencies may fail on modern Python because it targets TensorFlow 1.x." >&2
  "$(pip_path autohighlight)" install -r "${EXTERNAL_ROOT}/autohighlight/requirements.txt"
fi

cat <<SUMMARY
External repos are available under:
  ${EXTERNAL_ROOT}/HoopCut_FH
  ${EXTERNAL_ROOT}/autohighlight

Backend environment variables:
  export HOOPS_DETECTION_PROVIDER=hybrid
  export HOOPS_HOOPCUT_REPO_PATH="${EXTERNAL_ROOT}/HoopCut_FH"
  export HOOPS_HOOPCUT_PYTHON="${VENV_ROOT}/hoopcut/bin/python"
  export HOOPS_POST_RANKING_PROVIDER=autohighlight
  export HOOPS_AUTOHIGHLIGHT_REPO_PATH="${EXTERNAL_ROOT}/autohighlight"
  export HOOPS_AUTOHIGHLIGHT_PYTHON="${VENV_ROOT}/autohighlight/bin/python"

Recommended next steps:
  1. Run this script with --with-venvs to create isolated virtualenvs.
  2. Run with --install-hoopcut to install the HoopCut dependencies into the dedicated venv.
  3. Only enable --install-autohighlight if you are prepared to run its legacy TensorFlow stack in a separate environment.
SUMMARY
