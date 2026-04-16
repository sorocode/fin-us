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

"""Smoke test: example package registers without import errors.

한글: 패키지가 설치·경로만 맞다면 `register` import 한 번으로
`fe_branch` / `finus_*` / 스텁이 NAT에 모두 등록되는지 확인합니다.
(실제 MCP·Ollama 연결은 이 테스트 범위 밖입니다.)
"""


def test_register_module_imports():
    """Importing register should load all NAT component registrations.

    한글: `nat_finus_nat.register`를 import하면 side effect로
    `[project.entry-points.'nat.components']`에 묶인 모든 `@register_function`이 로드됩니다.
    """
    import nat_finus_nat.register  # noqa: F401 — 등록 부수효과만 검증
