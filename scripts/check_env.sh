#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# 한글: Docker 기반 실행 전 점검 (docker / compose / 경로 / 백엔드 .env / Ollama 등).
# Usage: bash /path/to/integrate-repo/scripts/check_env.sh

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"

ok=0
warn=0

die_msg() { echo "  ✗ $*" >&2; ok=1; }

echo "== Fin-Us integrated stack (Docker) =="
echo "FIN_US_INTEGRATE_ROOT=${FIN_US_INTEGRATE_ROOT}"
echo

if command -v docker >/dev/null 2>&1; then
  echo "  ✓ docker ($(command -v docker))"
else
  die_msg "docker not found"
fi

if docker compose version >/dev/null 2>&1; then
  echo "  ✓ docker compose $(docker compose version --short 2>/dev/null || echo ok)"
else
  die_msg "docker compose not available"
fi

if [[ ! -d "${FINUS_NAT_DIR}" ]]; then
  die_msg "missing ${FINUS_NAT_DIR}"
else
  echo "  ✓ finus_nat present"
fi

if [[ ! -d "${FIN_BACKEND}" ]]; then
  die_msg "missing ${FIN_BACKEND}"
else
  echo "  ✓ fin-us/backend present"
fi

_env_backend="${FIN_BACKEND}/.env"
if [[ -f "${_env_backend}" ]]; then
  echo "  ✓ backend .env present (${_env_backend})"
else
  echo "  ! backend .env missing — copy fin-us/backend/.env.example to fin-us/backend/.env" >&2
  warn=1
fi

if [[ ! -f "${FIN_US_INTEGRATE_ROOT}/docker-compose.yml" ]]; then
  die_msg "missing docker-compose.yml under ${FIN_US_INTEGRATE_ROOT}"
else
  echo "  ✓ docker-compose.yml present"
fi

if command -v ollama >/dev/null 2>&1; then
  echo "  ✓ ollama CLI present"
else
  echo "  ! ollama CLI not in PATH (optional if NAT uses another LLM endpoint)"
  warn=1
fi

if command -v curl >/dev/null 2>&1; then
  _base="${OLLAMA_OPENAI_BASE_URL:-http://127.0.0.1:11434/v1}"
  _base="${_base%/}"
  if curl -sf --max-time 2 "${_base}/models" >/dev/null 2>&1; then
    echo "  ✓ Ollama HTTP reachable at ${_base}/models"
  else
    echo "  ! cannot reach ${_base}/models — start Ollama or set OLLAMA_OPENAI_BASE_URL"
    warn=1
  fi
else
  echo "  ! curl not found — skipped Ollama HTTP check"
  warn=1
fi

echo
if [[ "${ok}" -ne 0 ]]; then
  echo "Fix errors above."
  exit 1
fi
if [[ "${warn}" -ne 0 ]]; then
  echo "Warnings only — fix .env / LLM before relying on analyze routes."
fi
echo "OK."
