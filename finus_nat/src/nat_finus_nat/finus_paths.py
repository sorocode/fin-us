# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
절대 경로를 계산합니다. fin-us/mcp-news, fin-us/mcp-trading 디렉터리를 참조합니다.
FINUS_VENDOR_ROOT 환경 변수가 설정되면 그 경로를 참조합니다.
"""

from __future__ import annotations

import os
from pathlib import Path


def finus_nat_example_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def fin_us_vendor_root() -> Path:
    env = os.environ.get("FINUS_VENDOR_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    fin_us_home = finus_nat_example_root().parent / "fin-us"
    if (fin_us_home / "mcp-news" / "index.js").is_file() and (fin_us_home / "mcp-trading" / "index.js").is_file():
        return fin_us_home
    return finus_nat_example_root() / "vendor" / "fin_us"


def fin_us_agents_dir() -> Path:
    return finus_nat_example_root() / "configs" / "agents"
