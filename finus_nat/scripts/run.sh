#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

# fe_stub / fe_branch are registered by nat-finus-nat (nat.components). Running plain
# `uv run nat run` from the repo root uses only nvidia-nat, so those types are missing unless
# this example project is the active uv project.
FE_PKG="finus_nat"

FE_PKG_ABS="${ROOT}/${FE_PKG}"
_nat_sh="${FE_PKG_ABS}/.venv/bin/nat"
if [[ -f "${_nat_sh}" ]]; then
  _py_line="$(head -1 "${_nat_sh}" || true)"
  _py="${_py_line/#\#!/}"
  if [[ -n "${_py}" && ! -x "${_py}" ]]; then
    echo "Removing stale ${FE_PKG}/.venv (nat launcher pointed at missing Python)." >&2
    rm -rf "${FE_PKG_ABS}/.venv"
  fi
fi

# If ~/.cache/uv is root-owned (e.g. after `sudo uv`), uv cannot write there; use a user cache unless set.
_default_uv_cache="${HOME}/.cache/uv"
if [[ -z "${UV_CACHE_DIR:-}" ]] && [[ -e "${_default_uv_cache}" ]] && [[ ! -w "${_default_uv_cache}" ]]; then
  export UV_CACHE_DIR="${HOME}/.cache/uv-${USER}"
fi

uv run --project "${FE_PKG}" nat run --config_file "${FE_PKG}/configs/router.yml" --input "${1:-Hello}"
