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

"""Fin-Us NAT components.

Loads ``finus_nat/.env`` so ``MEM0_API_KEY`` (Mem0 Platform) is available when the NAT CLI
cwd is not ``finus_nat/``. Matches NeMo examples: credentials only via env, not YAML.
"""

from pathlib import Path

from dotenv import load_dotenv

# register.py -> nat_finus_nat/ -> src/ -> finus_nat/
_FINUS_NAT_ENV = Path(__file__).resolve().parents[2] / ".env"
if _FINUS_NAT_ENV.is_file():
    load_dotenv(_FINUS_NAT_ENV, override=False)

from nat_finus_nat import branch  # noqa: E402, F401
from nat_finus_nat import finus_api  # noqa: E402, F401
from nat_finus_nat import stub  # noqa: E402, F401
