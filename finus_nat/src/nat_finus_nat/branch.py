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
라우터 에이전트가 선택한 하위 에이전트를 호출하는 도구입니다.
"""

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.api_server import ChatRequestOrMessage
from nat.data_models.api_server import ChatResponse
from nat.data_models.function import FunctionBaseConfig


class FeBranchConfig(FunctionBaseConfig, name="fe_branch"):
    inner_function_name: str = Field(
        ...,
        min_length=1,
        description="Name of the function entry in the same config (the nested react_agent).",
    )
    tool_description: str | None = Field(
        default=None,
        description="Optional LangChain tool description; defaults to a generic delegation message.",
    )


def _response_to_text(result: ChatResponse | str) -> str:
    if isinstance(result, str):
        return result
    if result.choices and result.choices[0].message.content is not None:
        return result.choices[0].message.content
    return ""


@register_function(config_type=FeBranchConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def fe_branch(config: FeBranchConfig, builder: Builder):
    inner_name = config.inner_function_name
    desc = config.tool_description or (
        f"Run the nested ReAct agent `{inner_name}` on the user's question (plain text).")

    async def run_subagent(user_query: str) -> str:
        inner = await builder.get_function(inner_name)
        payload = ChatRequestOrMessage(input_message=user_query)
        result = await inner.ainvoke(payload)
        return _response_to_text(result)

    yield FunctionInfo.from_fn(run_subagent, description=desc)
