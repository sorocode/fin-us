#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# 한글: Vite 프론트 컨테이너만 기동 (:5173). node_modules는 익명 볼륨으로 유지.

set -euo pipefail
_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${_SCRIPTS_DIR}/_compose_up.sh" frontend
