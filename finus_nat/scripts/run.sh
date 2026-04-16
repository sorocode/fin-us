#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# 한글: Fin-Us 저장소 루트에서 `nat run`을 이 프로젝트(`finus_nat`) 컨텍스트로 실행합니다.
#      - `--project`로 `nat-finus-nat`를 지정해야 `fe_branch`/`finus_*` 타입이 등록됩니다.
#      - `--config_file`은 `configs/router.yml`(→ `agents/diary_agent.yml` → … → `common.yml` 병합)을 가리킵니다.
#
# Usage (this git repository root — same directory as docker-compose.yml):
#   1) Start Ollama (`ollama serve`) and pull the model: `ollama pull qwen3.5:9b`
#   2) For news/recommend/strategy: install Node deps under fin-us/mcp-* (see fin-us/scripts/install_fin_us_mcp.sh); for containers use `docker compose build` from repo root
#   3) Optional: OLLAMA_MODEL, OLLAMA_OPENAI_BASE_URL, OLLAMA_API_KEY; then:
#      ./finus_nat/scripts/run.sh "your message"
#
# NAT does not download models; it POSTs to Ollama and spawns Fin-Us MCP (Node) when those tools run.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

# 한글: 아래 이유로 반드시 `--project "${FE_PKG}"`를 붙입니다.
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

# 한글: uv 캐시 디렉터리가 root 소유면 쓰기 실패하므로 사용자별 대체 경로를 씁니다.
# If ~/.cache/uv is root-owned (e.g. after `sudo uv`), uv cannot write there; use a user cache unless set.
_default_uv_cache="${HOME}/.cache/uv"
if [[ -z "${UV_CACHE_DIR:-}" ]] && [[ -e "${_default_uv_cache}" ]] && [[ ! -w "${_default_uv_cache}" ]]; then
  export UV_CACHE_DIR="${HOME}/.cache/uv-${USER}"
fi

export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3.5:9b}"
uv run --project "${FE_PKG}" nat run --config_file "${FE_PKG}/configs/router.yml" --input "${1:-Hello}"
