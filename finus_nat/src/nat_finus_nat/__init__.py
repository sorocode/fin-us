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

"""Fin-Us NAT example: router_agent + sub-agents (OpenAI API by default; optional Ollama; Fin-Us MCP tools; KIS MCP optional).

  이 패키지는 예제 워크플로(`configs/router.yml` 등)에서 쓰는 커스텀 NAT 컴포넌트의 네임스페이스입니다.
  실제 등록은 `register` 모듈이 `nat.components` 엔트리포인트로 로드될 때 수행됩니다.
"""
