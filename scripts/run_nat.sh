#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# 한글: finus_nat(NAT FastAPI) 컨테이너만 기동. 호스트 uv 불필요.

set -euo pipefail
_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${_SCRIPTS_DIR}/_compose_up.sh" finus-nat
