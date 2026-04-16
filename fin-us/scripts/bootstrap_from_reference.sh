#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# 한글: `fin-us-reference/`의 backend(에이전트 YAML·core 제외)·frontend-react·mcp-* 를
#      실행용 `fin-us/`로 복사한 뒤, NAT 통합용 `main.py`·`requirements.txt`를 덮어씁니다.
#      `fin-us-reference/` 안의 파일은 수정하지 않습니다.

set -euo pipefail
# 한글: `fin-us/scripts/` 기준으로 저장소 루트(compose·finus_nat와 같은 디렉터리)는 두 단계 위입니다.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
_default_ref="${ROOT}/fin-us-reference"
REF="${FIN_US_REFERENCE_DIR:-${_default_ref}}"
DST="${ROOT}/fin-us"
TPL="${ROOT}/fin-us/scripts/templates"

if [[ ! -d "${REF}" ]]; then
  echo "ERROR: ${REF} not found" >&2
  exit 1
fi

rsync -a --delete \
  --exclude node_modules --exclude dist \
  "${REF}/mcp-news/" "${DST}/mcp-news/"

rsync -a --delete \
  --exclude node_modules --exclude dist \
  "${REF}/mcp-trading/" "${DST}/mcp-trading/"

rsync -a --delete \
  --exclude node_modules --exclude dist \
  "${REF}/frontend-react/" "${DST}/frontend-react/"

rsync -a --delete \
  --exclude __pycache__ --exclude .venv \
  "${REF}/backend/" "${DST}/backend/"

# NAT(`finus_nat`)가 오케스트레이션을 담당하므로 reference의 agents/core는 실행 트리에 두지 않음
rm -rf "${DST}/backend/agents" "${DST}/backend/core"

cp "${TPL}/main_integrated.py" "${DST}/backend/main.py"
cp "${TPL}/requirements_integrated.txt" "${DST}/backend/requirements.txt"
cp "${TPL}/pyproject_integrated.toml" "${DST}/backend/pyproject.toml"

# Vite `/api` proxy runs inside the frontend container; target must be the Compose service.
perl -pi -e "s#target: 'http://[^']+'#target: 'http://backend:8000'#" "${DST}/frontend-react/vite.config.ts" 2>/dev/null || true

# fin-us 실행 트리만: TS 6 경고 무시 + 빌드는 Vite만 (reference의 tsc 단계는 통합 환경에서 생략)
perl -0777 -i -pe 's/"jsx": "react-jsx"\n  \}/"jsx": "react-jsx",\n    "ignoreDeprecations": "6.0"\n  }/s' \
  "${DST}/frontend-react/tsconfig.json" 2>/dev/null || true
perl -pi -e 's/"build": "tsc && vite build"/"build": "vite build"/' "${DST}/frontend-react/package.json" 2>/dev/null || true

rm -rf "${DST}/backend/fin_us_backend" 2>/dev/null || true

echo "OK: fin-us populated from fin-us-reference."
