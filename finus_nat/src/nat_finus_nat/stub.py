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

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig


class FeStubConfig(FunctionBaseConfig, name="fe_stub"):
    pass


@register_function(config_type=FeStubConfig)
async def fe_stub(_config: FeStubConfig, _builder: Builder):
    async def placeholder_note(query: str) -> str:
        return (
            "This branch has no external data tools yet. Answer from general knowledge only, "
            f"or say you cannot fetch live data. Context: {query[:400]!r}"
        )

    yield FunctionInfo.from_fn(
        placeholder_note,
        description="Explain if live data is needed and answer briefly from general knowledge when possible.",
    )
