#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# 한글: `fin-us/mcp-news`, `fin-us/mcp-trading`(backend·frontend와 같은 레벨)에 `npm ci`를 실행합니다.
#      뉴스 MCP는 Playwright Chromium이 필요합니다.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"

cd "${ROOT}/mcp-news"
npm ci
npx playwright install chromium

cd "${ROOT}/mcp-trading"
npm ci

echo "OK: fin-us/mcp-news and fin-us/mcp-trading Node dependencies installed."
