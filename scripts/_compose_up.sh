#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# 한글: `docker compose up --build` 공통 진입점. 서비스 인자 없으면 전체 스택.

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"

command -v docker >/dev/null || { echo "ERROR: docker not found" >&2; exit 1; }

cd "${FIN_US_INTEGRATE_ROOT}"
exec docker compose up --build "$@"
