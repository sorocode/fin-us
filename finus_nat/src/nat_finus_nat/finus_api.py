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

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Literal, Protocol

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


async def _mcp_call_tool(
    *,
    vendor_root: Path,
    subdir: str,
    tool_name: str,
    arguments: dict[str, Any],
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
                result = await session.call_tool(tool_name, arguments)
                if not result.content:
                    return ""
                block = result.content[0]
                return getattr(block, "text", str(block))

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
    arguments: dict[str, Any],
    timeout_sec: float,
) -> str:
    """Call a single MCP tool over SSE or streamable-http (e.g. Kis Trading MCP in Docker)."""

    if not url.strip():
        return json.dumps(
            {"error": "mcp_url_empty", "tool": tool_name, "hint": "Set mcp_url on finus_account_balance config."},
            ensure_ascii=False,
        )

    async def _inner() -> str:
        if transport == "sse":
            connect_timeout = min(60.0, max(5.0, timeout_sec * 0.25))
            async with sse_client(
                url=url,
                timeout=connect_timeout,
                sse_read_timeout=timeout_sec,
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    if not result.content:
                        return ""
                    block = result.content[0]
                    return getattr(block, "text", str(block))

        # streamable-http
        async with httpx.AsyncClient() as http_client:
            async with streamable_http_client(url=url, http_client=http_client) as (read, write, _get_sid):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    if not result.content:
                        return ""
                    block = result.content[0]
                    return getattr(block, "text", str(block))

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


class FinusAccountBalanceConfig(FunctionBaseConfig, name="finus_account_balance"):
    """Account snapshot via Kis Trading MCP only (HTTP); no local fin-us/mcp-trading."""

    timeout_sec: float = Field(default=180.0, ge=5.0, le=600.0)
    mcp_transport: Literal["sse", "streamable-http"] = Field(
        default="sse",
        description="Transport to Kis Trading MCP (Docker default: SSE on port 3000).",
    )
    mcp_url: str = Field(
        default="http://kis-trading-mcp:3000/sse",
        description="Kis Trading MCP URL (SSE path /sse or streamable-http /mcp). Override in YAML with env.",
    )
    trading_tool_name: str = Field(
        default="get_balance",
        description="Tool name on the Kis Trading MCP server for balance inquiry.",
    )


async def _mcp_trading_balance(config: FinusAccountBalanceConfig) -> str:
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
        return await _mcp_news_stock(config, "get_market_news", stock_name)

    yield FunctionInfo.from_fn(get_market_news, description=get_market_news.__doc__)


@register_function(config_type=FinusInvestorTradingConfig)
async def finus_investor_trading(config: FinusInvestorTradingConfig, _builder: Builder):
    async def get_investor_trading(stock_name: str) -> str:
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


@register_function(config_type=FinusAccountBalanceConfig)
async def finus_account_balance(config: FinusAccountBalanceConfig, _builder: Builder):
    async def get_account_balance(placeholder: str) -> str:
        _ = placeholder
        return await _mcp_trading_balance(config)

    yield FunctionInfo.from_fn(get_account_balance, description=get_account_balance.__doc__)
