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

"""Fin-Us NAT plugins: stdio ``mcp-news``, remote [Kis Trading MCP](https://github.com/koreainvestment/open-trading-api/tree/main/MCP/Kis%20Trading%20MCP), direct KIS HTTP."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol, TypeAlias
from zoneinfo import ZoneInfo

import httpx
from mcp import ClientSession
from mcp import StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig
from nat_finus_nat.finus_paths import fin_us_vendor_root

logger = logging.getLogger(__name__)


def _langchain_escape_braces(text: str) -> str:
    """ReAct 프롬프트가 ChatPromptTemplate라서 ``{``/``}``가 변수로 해석됨 — JSON 예시는 ``{{``/``}}`` 로 이스케이프."""
    return text.replace("{", "{{").replace("}", "}}")


# --- Remote MCP / doc limits (tune without hunting literals) ---
_MCP_DOC_MAX_CHARS = 14_000
_MCP_LIST_TOOLS_GRACE_SEC = 10.0
_SSE_CONNECT_CAP = 60.0
_SSE_CONNECT_FLOOR = 5.0

McpCallArguments: TypeAlias = dict[str, Any]


class _FinusVendorTimeout(Protocol):
    vendor_root: str | None
    timeout_sec: float


def _resolve_vendor_root(override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return fin_us_vendor_root()


def _node_deps_ready(server_dir: Path) -> bool:
    sdk = server_dir / "node_modules" / "@modelcontextprotocol" / "sdk"
    return sdk.is_dir()


def _mcp_call_tool_first_text(result: Any) -> str:
    """First text block from MCP ``call_tool`` result (stdio or remote)."""
    blocks = getattr(result, "content", None) or []
    if not blocks:
        return ""
    block0 = blocks[0]
    return getattr(block0, "text", str(block0))


def _sse_connect_timeout(operation_timeout: float) -> float:
    return min(_SSE_CONNECT_CAP, max(_SSE_CONNECT_FLOOR, operation_timeout * 0.25))


@asynccontextmanager
async def _remote_mcp_session(
    *,
    transport: Literal["sse", "streamable-http"],
    url: str,
    operation_timeout: float,
):
    """Connected, initialized ``ClientSession`` for one Kis-style remote MCP."""
    conn = _sse_connect_timeout(operation_timeout)
    if transport == "sse":
        async with sse_client(
            url=url,
            timeout=conn,
            sse_read_timeout=operation_timeout,
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
        return
    async with httpx.AsyncClient() as http_client:
        async with streamable_http_client(url=url, http_client=http_client) as (read, write, _get_sid):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


async def _mcp_call_tool(
    *,
    vendor_root: Path,
    subdir: str,
    tool_name: str,
    arguments: McpCallArguments,
    timeout_sec: float,
) -> str:
    server_dir = (vendor_root / subdir).resolve()
    script = (server_dir / "index.js").resolve()
    if not script.is_file():
        return json.dumps(
            {
                "error": "mcp_server_script_missing",
                "path": str(script),
                "hint": (
                    f"Expected MCP under {vendor_root}; run the install script "
                    f"(scripts/install_fin_us_mcp.sh from this repository root) "
                    "or set FINUS_VENDOR_ROOT."
                ),
            },
            ensure_ascii=False)

    if not _node_deps_ready(server_dir):
        news = vendor_root / "mcp-news"
        return json.dumps(
            {
                "error": "mcp_node_dependencies_missing",
                "path": str(server_dir),
                "detail": "ERR_MODULE_NOT_FOUND @modelcontextprotocol/sdk — node_modules not installed.",
                "hint": (f"cd {news} && npm ci && npx playwright install chromium"),
            },
            ensure_ascii=False)

    params = StdioServerParameters(command="node", args=[str(script)], cwd=str(server_dir))

    async def _inner() -> str:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return _mcp_call_tool_first_text(await session.call_tool(tool_name, arguments))

    try:
        return await asyncio.wait_for(_inner(), timeout=timeout_sec)
    except TimeoutError:
        return json.dumps({"error": "mcp_timeout", "tool": tool_name}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc), "tool": tool_name}, ensure_ascii=False)


async def _mcp_call_tool_remote(
    *,
    transport: Literal["sse", "streamable-http"],
    url: str,
    tool_name: str,
    arguments: McpCallArguments,
    timeout_sec: float,
) -> str:
    """Call a single MCP tool over SSE or streamable-http (e.g. Kis Trading MCP in Docker)."""

    if not url.strip():
        return json.dumps(
            {"error": "mcp_url_empty", "tool": tool_name, "hint": "Set mcp_url on finus_account_balance config."},
            ensure_ascii=False,
        )

    async def _inner() -> str:
        async with _remote_mcp_session(
            transport=transport,
            url=url,
            operation_timeout=timeout_sec,
        ) as session:
            return _mcp_call_tool_first_text(await session.call_tool(tool_name, arguments))

    try:
        return await asyncio.wait_for(_inner(), timeout=timeout_sec)
    except TimeoutError:
        return json.dumps({"error": "mcp_timeout", "tool": tool_name, "transport": transport}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {"error": str(exc), "tool": tool_name, "transport": transport, "url": url},
            ensure_ascii=False,
        )


def _vendor_and_timeout(config: _FinusVendorTimeout) -> tuple[Path, float]:
    return _resolve_vendor_root(config.vendor_root), config.timeout_sec


async def _mcp_news_stock(config: _FinusVendorTimeout, tool_name: str, stock_name: str) -> str:
    vr, timeout = _vendor_and_timeout(config)
    return await _mcp_call_tool(
        vendor_root=vr,
        subdir="mcp-news",
        tool_name=tool_name,
        arguments={"stock_name": stock_name},
        timeout_sec=timeout,
    )


class FinusMarketNewsConfig(FunctionBaseConfig, name="finus_market_news"):
    vendor_root: str | None = Field(default=None, description="Override parent dir containing mcp-news (stdio MCP).")
    timeout_sec: float = Field(default=120.0, ge=5.0, le=600.0)


class FinusInvestorTradingConfig(FunctionBaseConfig, name="finus_investor_trading"):
    vendor_root: str | None = Field(default=None)
    timeout_sec: float = Field(default=120.0, ge=5.0, le=600.0)


class FinusResearchReportsConfig(FunctionBaseConfig, name="finus_research_reports"):
    """Unified research pipeline: search by category (종목/시황/산업/…) → PDF 다운로드 → 텍스트 추출 → 에이전트로 전달.

    Wraps the single MCP tool ``get_research_reports`` exposed by fin-us/mcp-news (stdio).
    """

    vendor_root: str | None = Field(default=None)
    timeout_sec: float = Field(default=240.0, ge=10.0, le=900.0)
    default_limit: int = Field(default=3, ge=1, le=20)
    default_chars_per_report: int = Field(default=3000, ge=500, le=20000)
    default_max_text_reports: int = Field(default=3, ge=1, le=20)


class FinusKisDailyTradesConfig(FunctionBaseConfig, name="finus_kis_daily_trades"):
    """Same-calendar-day domestic stock order/fill history via KIS HTTP Open API (no MCP)."""

    timeout_sec: float = Field(default=120.0, ge=5.0, le=600.0)


_KIS_TRADING_REMOTE_API_ALIASES: dict[str, str] = {
    "잔고조회": "inquire_balance",
    "잔고": "inquire_balance",
    "계좌조회": "inquire_balance",
    "계좌": "inquire_balance",
    "포트폴리오": "inquire_balance",
    "보유종목": "inquire_balance",
    "보유": "inquire_balance",
    "내잔고": "inquire_balance",
    "내계좌": "inquire_balance",
    "balance": "inquire_balance",
    "portfolio": "inquire_balance",
    "holdings": "inquire_balance",
}


def _compact_api_label(label: str) -> str:
    return label.lower().replace(" ", "").replace("_", "").replace("-", "")


def _kis_trading_alias_lookup() -> dict[str, str]:
    """Map raw / lower / compact forms → canonical ``api_type`` for remote MCP."""
    lut: dict[str, str] = {}
    for key, canon in _KIS_TRADING_REMOTE_API_ALIASES.items():
        for v in {key, key.lower(), _compact_api_label(key)}:
            lut.setdefault(v, canon)
    return lut


_KIS_TRADING_ALIAS_LUT: dict[str, str] = _kis_trading_alias_lookup()


def _parse_leading_json_object(text: str) -> dict[str, Any] | None:
    """Parse first JSON object from a string (ReAct often appends ``Question:`` / ``Thought:`` after Action Input)."""
    t = (text or "").strip()
    if not t:
        return None
    i = t.find("{")
    if i < 0:
        return None
    try:
        obj, _end = json.JSONDecoder().raw_decode(t[i:])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _normalize_remote_trading_api_type(api_type: str) -> str:
    raw = (api_type or "").strip()
    if not raw:
        return raw
    return (
        _KIS_TRADING_ALIAS_LUT.get(raw)
        or _KIS_TRADING_ALIAS_LUT.get(raw.lower())
        or _KIS_TRADING_ALIAS_LUT.get(_compact_api_label(raw))
        or raw
    )


def _normalize_trading_call_blob(blob: McpCallArguments) -> McpCallArguments:
    """Return a shallow copy with ``api_type`` normalized when present."""
    at = blob.get("api_type")
    if at is None:
        return blob
    s = str(at).strip()
    if not s:
        return blob
    return {**blob, "api_type": _normalize_remote_trading_api_type(s)}


def _kis_env_dv() -> str:
    """실전/모의: ``FINUS_KIS_ENV_DV`` 우선, 없으면 ``FINUS_KIS_PAPER``/``KIS_PAPER``."""
    x = (os.getenv("FINUS_KIS_ENV_DV") or "").strip().lower()
    if x in ("real", "demo"):
        return x
    paper = (os.getenv("FINUS_KIS_PAPER") or os.getenv("KIS_PAPER") or "").strip().lower()
    if paper in ("1", "true", "yes", "y"):
        return "demo"
    return "real"


# Kis Open API ``inquire_balance`` — 서버가 빈 params를 거부할 때 쓰는 고정 기본값(open-trading-api MCP와 동일 계열).
_INQUIRE_BALANCE_DEFAULTS: dict[str, Any] = {
    "afhr_flpr_yn": "N",
    "inqr_dvsn": "02",
    "unpr_dvsn": "01",
    "fund_sttl_icld_yn": "N",
    "fncg_amt_auto_rdpt_yn": "N",
    "prcs_dvsn": "00",
    "tr_cont": "",
    "depth": 0,
    "max_depth": 10,
}


def _default_inquire_balance_params() -> dict[str, Any]:
    return {"env_dv": _kis_env_dv(), **_INQUIRE_BALANCE_DEFAULTS}


def _enrich_domestic_stock_call(blob: McpCallArguments) -> McpCallArguments:
    """``inquire_balance`` + 빈 ``params``면 서버 필수 필드를 기본값으로 채움(공식 MCP도 params 스키마 필요)."""
    blob = _normalize_trading_call_blob(blob)
    at = str(blob.get("api_type") or "").strip().lower()
    if at != "inquire_balance":
        return blob
    raw = blob.get("params")
    user = raw if isinstance(raw, dict) else {}
    merged = {**_default_inquire_balance_params(), **user}
    return {**blob, "params": merged}


def _domestic_stock_symbol_from_text(text: str, *, default: str = "005930") -> str:
    for tok in text.replace("/", " ").replace(",", " ").split():
        if tok.isdigit() and len(tok) == 6:
            return tok
    return default


class FinusAccountBalanceConfig(FunctionBaseConfig, name="finus_account_balance"):
    """Remote [Kis Trading MCP](https://github.com/koreainvestment/open-trading-api/tree/main/MCP/Kis%20Trading%20MCP) — NAT는 SSE ``call_tool``만 수행."""

    timeout_sec: float = Field(default=180.0, ge=5.0, le=600.0)
    mcp_transport: Literal["sse", "streamable-http"] = Field(
        default="sse",
        description="Official MCP Docker exposes SSE on container port 3000.",
    )
    mcp_url: str = Field(
        default="http://kis-trading-mcp:3000/sse",
        description="Same network as MCP container: :3000/sse. Host publishes e.g. 3300:3000 → set FINUS_KIS_TRADING_MCP_URL.",
    )
    trading_tool_name: str = Field(
        default="domestic_stock",
        description="Official MCP tool name is typically ``domestic_stock`` (``api_type`` + ``params`` in arguments).",
    )


async def _mcp_trading_balance(config: FinusAccountBalanceConfig) -> str:
    """``tool_input`` 비었을 때: ``domestic_stock`` → ``inquire_balance``."""
    tool_name = (config.trading_tool_name or "").strip()
    if tool_name == "domestic_stock":
        return await _mcp_call_tool_remote(
            transport=config.mcp_transport,
            url=config.mcp_url,
            tool_name=tool_name,
            arguments=_enrich_domestic_stock_call({"api_type": "inquire_balance", "params": {}}),
            timeout_sec=config.timeout_sec,
        )

    return await _mcp_call_tool_remote(
        transport=config.mcp_transport,
        url=config.mcp_url,
        tool_name=config.trading_tool_name,
        arguments={},
        timeout_sec=config.timeout_sec,
    )


@register_function(config_type=FinusMarketNewsConfig)
async def finus_market_news(config: FinusMarketNewsConfig, _builder: Builder):
    async def get_market_news(stock_name: str) -> str:
        """Fin-Us ``mcp-news`` stdio MCP: 최신 시장 뉴스(헤드라인·요약)를 종목명 기준으로 조회합니다.

        ``stock_name``은 한글 종목명 또는 6자리 종목코드(예: 삼성전자, 005930)를 넣으세요.
        MCP 도구 ``get_market_news``를 호출한 JSON/텍스트 결과를 그대로 반환합니다.
        """
        return await _mcp_news_stock(config, "get_market_news", stock_name)

    yield FunctionInfo.from_fn(get_market_news, description=get_market_news.__doc__)


@register_function(config_type=FinusInvestorTradingConfig)
async def finus_investor_trading(config: FinusInvestorTradingConfig, _builder: Builder):
    async def get_investor_trading(stock_name: str) -> str:
        """Fin-Us ``mcp-news`` stdio MCP: 외국인·기관 등 투자자별 순매수/수급 흐름(약 5거래일)을 종목 기준으로 조회합니다.

        ``stock_name``은 한글 종목명 또는 6자리 종목코드입니다. MCP 도구 ``get_investor_trading`` 결과를 반환합니다.
        """
        return await _mcp_news_stock(config, "get_investor_trading", stock_name)

    yield FunctionInfo.from_fn(get_investor_trading, description=get_investor_trading.__doc__)


_ALLOWED_CATEGORIES = ("company", "industry", "market_info", "invest", "economy", "debenture")


def _normalize_category(category: str) -> str:
    c = (category or "").strip().lower()
    if c in _ALLOWED_CATEGORIES:
        return c
    alias = {
        "종목": "company",
        "종목분석": "company",
        "기업": "company",
        "산업": "industry",
        "산업분석": "industry",
        "시황": "market_info",
        "시황정보": "market_info",
        "market": "market_info",
        "투자": "invest",
        "투자정보": "invest",
        "경제": "economy",
        "경제분석": "economy",
        "채권": "debenture",
        "채권분석": "debenture",
    }
    return alias.get(c, "company")


@register_function(config_type=FinusResearchReportsConfig)
async def finus_research_reports(config: FinusResearchReportsConfig, _builder: Builder):
    async def get_research_reports(
        category: str = "company",
        query: str = "",
        limit: int = 0,
        chars_per_report: int = 0,
        max_text_reports: int = 0,
    ) -> str:
        """카테고리·검색어로 네이버 리서치 리포트를 찾아 PDF를 저장하고 본문 텍스트까지 한 번에 돌려주는 단일 파이프라인.

        종목 질의는 ``category='company'``, 시황은 ``'market_info'``, 산업은 ``'industry'``를 사용하세요.
        한국어 alias(종목/시황/산업/투자/경제/채권)도 허용합니다. ``query``는 종목명/6자리 종목코드/키워드 중 하나이며
        빈 문자열이면 해당 카테고리의 최신 리포트를 가져옵니다.

        Args:
            category: company | industry | market_info | invest | economy | debenture
            query: 종목명/종목코드/키워드 (비우면 최신순).
            limit: 대상 리포트 수 (0이면 config 기본값).
            chars_per_report: 각 리포트의 본문 텍스트 노출 상한 (0이면 기본값).
            max_text_reports: 본문을 인라인으로 붙여 반환할 리포트 개수 (0이면 기본값).

        Returns:
            JSON 문자열. ``reports[i].text``에 절삭된 본문이 포함됩니다.
        """
        effective_limit = limit if limit and limit > 0 else config.default_limit
        effective_chars = chars_per_report if chars_per_report and chars_per_report > 0 else config.default_chars_per_report
        effective_max_texts = max_text_reports if max_text_reports and max_text_reports > 0 else config.default_max_text_reports

        vr, timeout = _vendor_and_timeout(config)
        return await _mcp_call_tool(
            vendor_root=vr,
            subdir="mcp-news",
            tool_name="get_research_reports",
            arguments={
                "category": _normalize_category(category),
                "query": query or "",
                "limit": int(effective_limit),
                "chars_per_report": int(effective_chars),
                "max_text_reports": int(effective_max_texts),
            },
            timeout_sec=timeout,
        )

    yield FunctionInfo.from_fn(get_research_reports, description=get_research_reports.__doc__)


async def _kis_issue_access_token(*, base_url: str, app_key: str, app_secret: str, timeout: float) -> str:
    token_url = f"{base_url.rstrip('/')}/oauth2/tokenP"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            token_url,
            json={
                "grant_type": "client_credentials",
                "appkey": app_key,
                "appsecret": app_secret,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        token = body.get("access_token")
        if not token:
            raise RuntimeError(str(body.get("msg1") or body))
        return str(token)


def _kis_tr_id_daily_ccld() -> str:
    override = (os.getenv("FINUS_KIS_TR_ID_DAILY_CCLD") or "").strip()
    if override:
        return override
    paper = (os.getenv("FINUS_KIS_PAPER") or "").lower() in ("1", "true", "yes", "y")
    return "VTTC8001R" if paper else "TTTC8001R"


@register_function(config_type=FinusKisDailyTradesConfig)
async def finus_kis_daily_trades(config: FinusKisDailyTradesConfig, _builder: Builder):
    async def get_today_domestic_trade_history(placeholder: str = "") -> str:
        """한국투자 Open API(HTTP)로 당일(KST 기준) 국내주식 일별주문체결 내역을 조회합니다.

        ``placeholder``는 NAT 도구 스키마 호환용이며 조회에 사용하지 않습니다.
        MCP가 아니라 ``KIS_URL``·``KIS_API_KEY``·``KIS_API_SECRET``·``KIS_ACCOUNT_NO`` 환경 변수를 사용합니다.
        모의투자는 ``FINUS_KIS_PAPER=true`` 또는 ``FINUS_KIS_TR_ID_DAILY_CCLD`` 로 TR_ID를 직접 지정하세요.

        Returns:
            JSON 문자열. 성공 시 ``output1``(체결·주문 내역 배열), ``output2``(집계) 및 조회일 ``as_of_kst_date``.
        """
        kis_url = (os.getenv("KIS_URL") or "").strip().rstrip("/")
        api_key = (os.getenv("KIS_API_KEY") or "").strip()
        api_secret = (os.getenv("KIS_API_SECRET") or "").strip()
        account_no = (os.getenv("KIS_ACCOUNT_NO") or "").strip()

        if not all([kis_url, api_key, api_secret, account_no]):
            return json.dumps(
                {
                    "error": "kis_env_missing",
                    "hint": "Set KIS_URL, KIS_API_KEY, KIS_API_SECRET, KIS_ACCOUNT_NO (10 digits: 8+2).",
                },
                ensure_ascii=False,
            )

        if len(account_no) != 10 or not account_no.isdigit():
            return json.dumps(
                {"error": "kis_invalid_account", "detail": "KIS_ACCOUNT_NO must be 10 digits."},
                ensure_ascii=False,
            )

        today_kst = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
        tr_id = _kis_tr_id_daily_ccld()
        token_timeout = min(60.0, float(config.timeout_sec))

        try:
            token = await _kis_issue_access_token(
                base_url=kis_url,
                app_key=api_key,
                app_secret=api_secret,
                timeout=token_timeout,
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": "kis_token_failed", "detail": str(exc)}, ensure_ascii=False)

        path = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
        params: dict[str, str] = {
            "CANO": account_no[0:8],
            "ACNT_PRDT_CD": account_no[8:10],
            "INQR_STRT_DT": today_kst,
            "INQR_END_DT": today_kst,
            "SLL_BUY_DVSN_CD": "00",
            "INQR_DVSN": "01",
            "PDNO": "",
            "CCLD_DVSN": "00",
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN_3": "00",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": api_key,
            "appsecret": api_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

        try:
            async with httpx.AsyncClient(timeout=config.timeout_sec) as client:
                resp = await client.get(f"{kis_url}{path}", headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": "kis_http_failed", "detail": str(exc)}, ensure_ascii=False)

        if data.get("rt_cd") != "0":
            return json.dumps(
                {
                    "error": "kis_api_error",
                    "rt_cd": data.get("rt_cd"),
                    "msg_cd": data.get("msg_cd"),
                    "msg1": data.get("msg1"),
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "as_of_kst_date": today_kst,
                "tr_id": tr_id,
                "output1": data.get("output1"),
                "output2": data.get("output2"),
            },
            ensure_ascii=False,
        )

    yield FunctionInfo.from_fn(get_today_domestic_trade_history, description=get_today_domestic_trade_history.__doc__)


def _mcp_tool_input_schema_json(tool: Any) -> str | None:
    schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
    if schema is None:
        return None
    if hasattr(schema, "schema_json"):
        return str(schema.schema_json(indent=2))
    if hasattr(schema, "model_json_schema"):
        return json.dumps(schema.model_json_schema(), indent=2, ensure_ascii=False)
    if isinstance(schema, dict):
        return json.dumps(schema, indent=2, ensure_ascii=False)
    return json.dumps({"raw": str(schema)}, indent=2, ensure_ascii=False)


def _format_one_mcp_tool(tool: Any) -> str:
    name = getattr(tool, "name", "?")
    desc = (getattr(tool, "description", None) or "").strip()
    schema = _mcp_tool_input_schema_json(tool)
    lines = [f"### MCP tool `{name}`"]
    if desc:
        lines.append(desc)
    if schema:
        lines.append("inputSchema:")
        lines.append(schema)
    return "\n".join(lines)


def _build_list_tools_doc(lr: Any, want: str) -> str:
    tools = list(getattr(lr, "tools", None) or [])
    header = (
        "### Kis Trading MCP (list_tools)\n"
        "공식 흐름: ``find_api_detail``로 파라미터 확인 후 ``domestic_stock`` 호출. "
        "NAT는 ``tool_input``에 api_type·params 키를 가진 JSON 한 줄만 넣으면 됨. "
        "``inquire_balance``에 빈 params면 NAT가 필수 필드를 채움. 한글 api_type 별칭은 자동 치환.\n"
    )
    if not tools:
        return header + "(서버가 빈 도구 목록을 반환했습니다.)"
    for t in tools:
        if getattr(t, "name", None) == want:
            return header + _format_one_mcp_tool(t)
    names = [getattr(t, "name", "?") for t in tools]
    parts = [header, f"(YAML의 trading_tool_name={want!r} 이 목록에 없음. 사용 가능 이름: {names})\n"]
    for t in tools[:12]:
        parts.append(_format_one_mcp_tool(t))
        parts.append("")
    return "\n".join(parts).strip()


async def _fetch_mcp_tool_documentation(config: FinusAccountBalanceConfig) -> str | None:
    """Connect once at workflow build and pull ``tools/list`` so the LLM sees real inputSchema."""
    if (os.environ.get("FINUS_SKIP_MCP_LIST_TOOLS") or "").strip().lower() in ("1", "true", "yes"):
        return None
    url = (config.mcp_url or "").strip()
    if not url:
        return None
    want = (config.trading_tool_name or "").strip()
    timeout_sec = min(25.0, max(5.0, float(config.timeout_sec)))

    async def _list() -> str:
        async with _remote_mcp_session(
            transport=config.mcp_transport,
            url=url,
            operation_timeout=timeout_sec,
        ) as session:
            return _build_list_tools_doc(await session.list_tools(), want)

    try:
        text = await asyncio.wait_for(_list(), timeout=timeout_sec + _MCP_LIST_TOOLS_GRACE_SEC)
        if len(text) > _MCP_DOC_MAX_CHARS:
            return text[: _MCP_DOC_MAX_CHARS - 100] + "\n…(truncated)"
        return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("finus_account_balance: list_tools failed for %s: %s", url, exc)
        return None


@register_function(config_type=FinusAccountBalanceConfig)
async def finus_account_balance(config: FinusAccountBalanceConfig, _builder: Builder):
    async def get_account_balance(tool_input: str = "") -> str:
        """원격 MCP에 넘길 JSON을 **문자열 하나**로 받습니다. 첫 ``{...}`` 만 파싱.

        - ``inquire_balance`` + 빈 ``params``: NAT가 ``env_dv`` 등 필수 키 보정(``FINUS_KIS_ENV_DV`` 또는 ``FINUS_KIS_PAPER``).
        - 비어 있으면 잔고 조회 폴백.
        """
        tool_name = (config.trading_tool_name or "").strip()
        ti = (tool_input or "").strip()

        blob = _parse_leading_json_object(ti)
        if blob:
            return await _mcp_call_tool_remote(
                transport=config.mcp_transport,
                url=config.mcp_url,
                tool_name=tool_name,
                arguments=_enrich_domestic_stock_call(blob),
                timeout_sec=config.timeout_sec,
            )

        if tool_name == "domestic_stock" and ti:
            symbol = _domestic_stock_symbol_from_text(ti)
            return await _mcp_call_tool_remote(
                transport=config.mcp_transport,
                url=config.mcp_url,
                tool_name=tool_name,
                arguments={
                    "api_type": "inquire_price",
                    "params": {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": symbol},
                },
                timeout_sec=config.timeout_sec,
            )

        return await _mcp_trading_balance(config)

    base_desc = (get_account_balance.__doc__ or "").strip()
    remote = await _fetch_mcp_tool_documentation(config)
    merged = f"{base_desc}\n\n{remote}" if remote else base_desc
    yield FunctionInfo.from_fn(get_account_balance, description=_langchain_escape_braces(merged))
