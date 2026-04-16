#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# 한글: Fin-Us Node MCP는 `fin-us/mcp-*`(backend와 같은 레벨)에 있습니다. 이 스크립트는 호환용으로
#      상위 `fin-us/scripts/install_fin_us_mcp.sh`에 위임합니다.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${HERE}/../../fin-us/scripts/install_fin_us_mcp.sh"
