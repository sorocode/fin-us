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

import logging

from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from pydantic import BaseModel
from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.api_server import ChatRequest
from nat.data_models.api_server import ChatRequestOrMessage
from nat.data_models.api_server import ChatResponse
from nat.data_models.api_server import Message
from nat.data_models.api_server import Usage
from nat.data_models.api_server import UserMessageContentRoleType
from nat.data_models.component_ref import FunctionRef
from nat.data_models.component_ref import LLMRef
from nat.data_models.function import FunctionBaseConfig
from nat.utils.type_converter import GlobalTypeConverter

logger = logging.getLogger(__name__)


class SupervisorBranch(BaseModel):
    name: str = Field(..., min_length=1, description="Stable branch name returned by the supervisor LLM.")
    function_name: FunctionRef = Field(..., description="Function name for the specialized agent.")
    description: str = Field(..., min_length=1, description="Routing description for this branch.")


class FinusSupervisorAgentConfig(FunctionBaseConfig, name="finus_supervisor_agent"):
    llm_name: LLMRef = Field(..., description="LLM used only for branch selection.")
    branches: list[SupervisorBranch] = Field(..., min_length=1, description="Specialized agent branches.")
    max_history_messages: int = Field(default=12, ge=1, description="Recent messages included in routing prompt.")
    description: str = Field(default="Fin-Us chat-native supervisor agent")


def _message_content_to_text(message: Message) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return "\n".join(str(part) for part in content)


def _role_to_label(role: UserMessageContentRoleType) -> str:
    if role == UserMessageContentRoleType.USER:
        return "user"
    if role == UserMessageContentRoleType.ASSISTANT:
        return "assistant"
    if role == UserMessageContentRoleType.SYSTEM:
        return "system"
    return str(role)


def _latest_user_text(messages: list[Message]) -> str:
    for message in reversed(messages):
        if message.role == UserMessageContentRoleType.USER:
            return _message_content_to_text(message)
    return _message_content_to_text(messages[-1])


def _format_history(messages: list[Message], max_history_messages: int) -> str:
    recent_messages = messages[-max_history_messages:]
    lines = []
    for message in recent_messages:
        lines.append(f"{_role_to_label(message.role)}: {_message_content_to_text(message)}")
    return "\n".join(lines)


def _response_to_text(result: ChatResponse | str) -> str:
    if isinstance(result, str):
        return result
    if result.choices and result.choices[0].message.content is not None:
        return result.choices[0].message.content
    return ""


def _normalize_branch_name(raw: str, branches: list[SupervisorBranch]) -> str | None:
    text = raw.strip().strip("`'\" \n\t")
    branch_names = {branch.name: branch.name for branch in branches}
    function_names = {str(branch.function_name): branch.name for branch in branches}

    if text in branch_names:
        return branch_names[text]
    if text in function_names:
        return function_names[text]

    lowered = text.lower()
    for branch in branches:
        if branch.name.lower() in lowered or str(branch.function_name).lower() in lowered:
            return branch.name
    return None


@register_function(config_type=FinusSupervisorAgentConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def finus_supervisor_agent(config: FinusSupervisorAgentConfig, builder: Builder):
    llm = await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
    branch_functions = {
        branch.name: await builder.get_function(branch.function_name)
        for branch in config.branches
    }

    branch_list = "\n".join(
        f"- {branch.name}: {branch.description} (function: {branch.function_name})"
        for branch in config.branches
    )
    branch_names = ", ".join(branch.name for branch in config.branches)

    system_prompt = (
        "You are the Fin-Us supervisor. Choose exactly one branch for the current user request.\n"
        "Use the conversation history only to resolve references such as 'that stock' or 'the previous risk'.\n"
        "Return only the branch name, with no explanation.\n\n"
        f"Available branches:\n{branch_list}\n\n"
        f"Allowed branch names: {branch_names}"
    )

    async def _choose_branch(chat_request: ChatRequest) -> str:
        routing_prompt = (
            "[Conversation]\n"
            f"{_format_history(chat_request.messages, config.max_history_messages)}\n\n"
            "[Current user request]\n"
            f"{_latest_user_text(chat_request.messages)}\n\n"
            "Choose one branch."
        )
        response = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=routing_prompt)])
        selected = _normalize_branch_name(str(response.content), config.branches)
        if selected is None:
            raise ValueError(f"Supervisor failed to choose a valid branch from LLM response: {response.content!r}")
        logger.debug("Fin-Us supervisor selected branch: %s", selected)
        return selected

    async def _response_fn(chat_request_or_message: ChatRequestOrMessage) -> ChatResponse | str:
        chat_request = GlobalTypeConverter.get().convert(chat_request_or_message, to_type=ChatRequest)
        selected_branch = await _choose_branch(chat_request)
        inner = branch_functions[selected_branch]

        payload = ChatRequestOrMessage(**chat_request.model_dump(exclude_none=True))
        result = await inner.ainvoke(payload)

        if chat_request_or_message.is_string:
            return _response_to_text(result)
        if isinstance(result, ChatResponse):
            return result
        return ChatResponse.from_string(str(result), usage=Usage())

    yield FunctionInfo.from_fn(_response_fn, description=config.description)
