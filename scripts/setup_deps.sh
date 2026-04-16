#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"

BOOTSTRAP=0
for _arg in "$@"; do
  if [[ "${_arg}" == "--bootstrap" ]]; then
    BOOTSTRAP=1
  fi
done

command -v docker >/dev/null || { echo "ERROR: docker required" >&2; exit 1; }

if [[ "${BOOTSTRAP}" -eq 1 ]]; then
  echo "== bootstrap fin-us from fin-us-reference =="
  bash "${FIN_US_DIR}/scripts/bootstrap_from_reference.sh"
fi

echo "== docker compose build (finus-nat, backend, frontend) =="
cd "${FIN_US_INTEGRATE_ROOT}"
docker compose build

echo
echo "OK. Start the stack:"
echo "  bash ${FIN_US_INTEGRATE_ROOT}/scripts/run_stack.sh"
echo "Or per service: run_backend.sh, run_frontend.sh, run_nat.sh"
