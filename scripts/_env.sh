# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# 한글: `run_*.sh` / `setup_deps.sh` / `check_env.sh`에서만 `source` 하세요.
#      통합 루트는 이 파일이 있는 `scripts/`에서 위로 올라가며 찾습니다(부모 한 단계만 쓰지 않음).
#      레이아웃: `docker-compose.yml` + (`fin-us/backend` 또는 루트 `backend`). 필요 시
#      `FIN_US_INTEGRATE_ROOT`를 미리 export 하면 탐색을 건너뜁니다.

_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

_fin_us_resolve_integrate_root() {
  local d="${_SCRIPTS_DIR}"
  while true; do
    if [[ -f "${d}/docker-compose.yml" ]]; then
      if [[ -d "${d}/fin-us/backend" ]] || [[ -d "${d}/backend" ]]; then
        printf '%s\n' "$(cd "${d}" && pwd)"
        return 0
      fi
    fi
    [[ "${d}" == "/" ]] && return 1
    d="$(cd "${d}/.." && pwd)"
  done
}

if [[ -n "${FIN_US_INTEGRATE_ROOT:-}" ]] && [[ -d "${FIN_US_INTEGRATE_ROOT}" ]]; then
  FIN_US_INTEGRATE_ROOT="$(cd "${FIN_US_INTEGRATE_ROOT}" && pwd)"
else
  FIN_US_INTEGRATE_ROOT="$(_fin_us_resolve_integrate_root)" || {
    echo "ERROR: Fin-Us integrate root not found (need docker-compose.yml and fin-us/backend or backend)." >&2
    echo "       Set FIN_US_INTEGRATE_ROOT to the directory that contains docker-compose.yml." >&2
    return 1 2>/dev/null || exit 1
  }
fi
export FIN_US_INTEGRATE_ROOT

if [[ -d "${FIN_US_INTEGRATE_ROOT}/fin-us" ]]; then
  export FIN_US_DIR="${FIN_US_INTEGRATE_ROOT}/fin-us"
else
  export FIN_US_DIR="${FIN_US_INTEGRATE_ROOT}"
fi
export FINUS_NAT_DIR="${FIN_US_INTEGRATE_ROOT}/finus_nat"
export FIN_BACKEND="${FIN_US_DIR}/backend"
export FIN_FRONTEND="${FIN_US_DIR}/frontend-react"
