#!/usr/bin/env bash

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"

command -v docker >/dev/null || { echo "ERROR: docker required" >&2; exit 1; }

if command -v npm >/dev/null 2>&1; then
  echo "== MCP Node deps (mcp-news, mcp-trading) =="
  bash "${FIN_US_INTEGRATE_ROOT}/scripts/install_fin_us_mcp.sh"
else
  echo "WARN: npm not found. Install Node.js and run: bash scripts/install_fin_us_mcp.sh" >&2
  echo "      (backend needs mcp-*/node_modules on the host bind mount.)" >&2
fi

echo "== docker compose build (finus-nat + FastAPI backend; Unity 클라이언트는 Docker 밖에서 실행) =="
cd "${FIN_US_INTEGRATE_ROOT}"
docker compose build

echo
echo "OK. Start API stack:"
echo "  bash ${FIN_US_INTEGRATE_ROOT}/scripts/run_stack.sh"
echo "Or one service: bash ${FIN_US_INTEGRATE_ROOT}/scripts/run_stack.sh backend"
echo
echo "Unity 대시보드: ${FIN_FRONTEND} 프로젝트를 열고, Dashboard UI의 API Base URL을"
echo "  백엔드와 맞추세요 (로컬 uvicorn·Docker compose 모두 호스트 http://localhost:8787 — 컨테이너 내부는 8000)."
