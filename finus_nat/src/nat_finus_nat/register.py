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

"""Register Fin-Us workflow helpers and vendored MCP tools for workflow YAML.

  `pyproject.toml`의 `[project.entry-points.'nat.components']`가 이 모듈을 가리킵니다.
  NAT가 워크플로를 빌드할 때 이 파일을 import하면 아래 서브모듈의 `@register_function` 데코레이터가
  실행되어 YAML의 `_type` 문자열과 Python 구현이 연결됩니다.

  - `branch`   → `_type: fe_branch`     (`*_branch_agent` → 내부 `*_agent` react_agent, `configs/agents/*_agent.yml`)
  - `finus_api`→ `_type: finus_*`      (Fin-Us MCP stdio; 저장소 루트의 `mcp-*` 또는 레거시 `fin-us/mcp-*`)
  - `stub`     → `_type: fe_stub`       (`common.yml`에 정의; ReAct용 최소 도구)
"""

from nat_finus_nat import branch  # noqa: F401 — fe_branch 등록
from nat_finus_nat import finus_api  # noqa: F401 — finus_* MCP 도구 등록
from nat_finus_nat import stub  # noqa: F401 — fe_stub 등록
