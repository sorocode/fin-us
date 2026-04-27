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

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

import httpx
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_FIN_US_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_ENV = _FIN_US_ROOT / "backend" / ".env"

load_dotenv(_BACKEND_ENV)
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
ANTHROPIC_CHAT_MODEL = os.getenv("ANTHROPIC_CHAT_MODEL", "claude-sonnet-4-20250514")

NAT_BASE_URL = os.environ.get("NAT_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
NAT_CHAT_MODEL = os.environ.get(
    "NAT_CHAT_MODEL",
    os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
)

OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "ollama")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")


def _ollama_openai_base_url() -> str:
    """OpenAI-compatible Ollama /v1. In Docker, 127.0.0.1 is the container — default to host gateway."""
    raw = (os.environ.get("OLLAMA_OPENAI_BASE_URL") or "").strip()
    if not raw:
        raw = (
            "http://host.docker.internal:11434/v1"
            if Path("/.dockerenv").exists()
            else "http://127.0.0.1:11434/v1"
        )
    base = raw.rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


_NEWS_MCP_DIR = (_FIN_US_ROOT / "mcp-news").resolve()
_TRADING_MCP_DIR = (_FIN_US_ROOT / "mcp-trading").resolve()


def _stdio_server_params(mcp_dir: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command="node",
        args=[str(mcp_dir / "index.js")],
        cwd=str(mcp_dir),
    )


NEWS_MCP_PARAMS = _stdio_server_params(_NEWS_MCP_DIR)
TRADING_MCP_PARAMS = _stdio_server_params(_TRADING_MCP_DIR)

app = FastAPI(
    title="Fin-Us + NAT (integrate)",
    description="MCP market data from fin-us; multi-agent analysis via NeMo NAT FastAPI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TradingSignal(BaseModel):
    decision: str = Field(..., description="BUY, SELL, 또는 HOLD")
    confidence_score: float = Field(..., ge=0, le=1)
    reason: str
    target_stock: str


class AnalysisReport(BaseModel):
    summary: str
    details: TradingSignal
    source_news: list[str]
    trading_trend: str | None = None


class CommonResponse(BaseModel):
    status: str = "success"
    data: dict[str, Any] | None = None
    message: str | None = None


async def _llm_openai_chat(user_msg: str) -> str:
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY가 설정되지 않았습니다. backend/.env에 키를 설정하세요.",
        )
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    resp = await client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[{"role": "user", "content": user_msg}],
        temperature=0.2,
    )
    choice = resp.choices[0].message.content
    return (choice or "").strip()


async def _llm_anthropic_chat(user_msg: str) -> str:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY가 설정되지 않았습니다. backend/.env에 키를 설정하세요.",
        )
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    msg = await client.messages.create(
        model=ANTHROPIC_CHAT_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": user_msg}],
    )
    parts: list[str] = []
    for block in msg.content:
        if block.type == "text":
            parts.append(block.text)
    return "".join(parts).strip()


async def _llm_ollama_chat(user_msg: str) -> str:
    base = _ollama_openai_base_url()
    client = AsyncOpenAI(
        api_key=OLLAMA_API_KEY or "ollama",
        base_url=base,
    )
    try:
        resp = await client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": user_msg}],
            temperature=0.2,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Ollama 호출 실패 ({base}, model={OLLAMA_MODEL}): {exc}. "
                "호스트에서 `ollama serve` 실행 여부를 확인하세요. "
                "Docker 백엔드는 기본으로 host.docker.internal을 씁니다; "
                "직접 지정하려면 backend/.env에 OLLAMA_OPENAI_BASE_URL을 넣으세요."
            ),
        ) from exc
    choice = resp.choices[0].message.content
    return (choice or "").strip()


def _nat_message_from_payload(payload: dict[str, Any]) -> str:
    if "error" in payload:
        err = payload["error"]
        msg = err if isinstance(err, str) else err.get("message", repr(err))
        raise HTTPException(status_code=502, detail=f"NAT 오류 응답: {msg}")

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise KeyError("empty or invalid choices")

    first = choices[0]
    if not isinstance(first, dict):
        raise TypeError("choice entry must be a dict")

    message = first.get("message")
    if not isinstance(message, dict):
        raise KeyError("message")

    content = message.get("content")
    return (content if content is not None else "").strip()


async def _llm_nat_chat(user_msg: str) -> str:
    url = f"{NAT_BASE_URL}/v1/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            resp = await client.post(
                url,
                json={
                    "model": NAT_CHAT_MODEL,
                    "messages": [{"role": "user", "content": user_msg}],
                    "temperature": 0.2,
                    "stream": False,
                },
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"NAT에 연결할 수 없습니다 ({url}): {exc}",
        ) from exc

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    try:
        payload = resp.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"NAT JSON 파싱 실패: {exc}; body[:800]={resp.text[:800]!r}",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="NAT 응답이 JSON 객체가 아닙니다.")

    try:
        return _nat_message_from_payload(payload)
    except (KeyError, IndexError, TypeError) as exc:
        body_snip = resp.text[:1200] if resp.text else ""
        raise HTTPException(
            status_code=502,
            detail=(
                f"NAT 응답 형식 오류 ({exc}). NAT_CHAT_MODEL이 NAT 서비스에서 쓰는 모델과 일치하는지 확인하세요. "
                f"body[:1200]={body_snip!r}"
            ),
        ) from exc


async def run_mcp_tool(
    server_params: StdioServerParameters,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                if not result.content:
                    return ""
                block = result.content[0]
                return getattr(block, "text", str(block))
    except Exception as exc:
        logger.exception("MCP call_tool failed for %s", tool_name)
        raise HTTPException(
            status_code=500,
            detail=f"데이터 공급원({tool_name}) 연결 실패: {exc}",
        ) from exc


def _analysis_from_nat_text(raw: str, stock: str) -> dict[str, Any]:
    """Map NAT assistant output to AnalysisReport JSON for the reference React UI."""
    text = (raw or "").strip()
    start = text.rfind("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        chunk = text[start : end + 1]
        try:
            data = json.loads(chunk)
            report = AnalysisReport(**data)
            return report.model_dump()
        except (json.JSONDecodeError, ValueError):
            pass
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    news_snip = lines[:8] if lines else []
    return AnalysisReport(
        summary=text[:8000] if text else "빈 응답",
        details=TradingSignal(
            decision="HOLD",
            confidence_score=0.5,
            reason="NAT 응답을 JSON으로 파싱하지 못해 요약만 표시합니다.",
            target_stock=stock,
        ),
        source_news=news_snip,
        trading_trend=None,
    ).model_dump()


def _normalize_llm_provider(
    provider: str,
) -> Literal["openai", "anthropic", "nat", "ollama"]:
    p = (provider or "openai").strip().lower()
    if p in ("openai", "gpt", "open_ai"):
        return "openai"
    if p in ("anthropic", "claude"):
        return "anthropic"
    if p in ("nat", "nemo", "nvidia"):
        return "nat"
    if p == "ollama":
        return "ollama"
    raise HTTPException(
        status_code=400,
        detail=(
            f"지원하지 않는 provider={provider!r}. "
            "openai | anthropic | ollama | nat(API 전용) 중 하나를 사용하세요."
        ),
    )


async def _llm_chat(
    provider_key: Literal["openai", "anthropic", "nat", "ollama"],
    user_msg: str,
) -> str:
    if provider_key == "openai":
        return await _llm_openai_chat(user_msg)
    if provider_key == "anthropic":
        return await _llm_anthropic_chat(user_msg)
    if provider_key == "ollama":
        return await _llm_ollama_chat(user_msg)
    return await _llm_nat_chat(user_msg)


@app.get("/api/v1/news", response_model=CommonResponse, tags=["Market Data"])
async def get_news(stock: str = Query(..., examples=["삼성전자"])):
    content = await run_mcp_tool(NEWS_MCP_PARAMS, "get_market_news", {"stock_name": stock})
    return {"status": "success", "data": {"stock": stock, "news": content.split("\n")}}


@app.get("/api/v1/analyze", response_model=CommonResponse, tags=["AI Agent"])
async def analyze_stock(
    stock: str = Query(..., examples=["SK하이닉스"]),
    provider: str = Query(
        "openai",
        description=(
            "openai=OpenAI; anthropic=Anthropic; ollama=local OpenAI-compatible /v1; "
            "nat=NAT multi-agent (still available via API query)"
        ),
    ),
):
    user_msg = (
        f"종목: {stock}. 라우터·서브에이전트를 활용해 투자 관점 분석을 하라. "
        "답변 마지막에 **다음 JSON 한 개만** 출력하라 (다른 텍스트 없이도 됨):\n"
        '{"summary":"한 줄 요약",'
        '"details":{"decision":"BUY"|"SELL"|"HOLD","confidence_score":0.0-1.0,'
        f'"reason":"근거","target_stock":"{stock}"}},'
        '"source_news":["헤드라인1","헤드라인2"],'
        '"trading_trend":"수급 한줄 요약 또는 null"}'
    )
    key = _normalize_llm_provider(provider)
    raw = await _llm_chat(key, user_msg)
    data = _analysis_from_nat_text(str(raw), stock)
    return {"status": "success", "data": data}


@app.get("/api/v1/trading/trend", response_model=CommonResponse, tags=["Market Data"])
async def get_trading_trend(stock: str = Query(..., examples=["삼성전자"])):
    trend = await run_mcp_tool(
        NEWS_MCP_PARAMS,
        "get_investor_trading",
        {"stock_name": stock},
    )
    return {"status": "success", "data": {"stock": stock, "trend": trend}}


@app.get("/api/v1/trading/balance", response_model=CommonResponse, tags=["Trading"])
async def get_account_balance():
    balance_text = await run_mcp_tool(TRADING_MCP_PARAMS, "get_balance", {})
    return {"status": "success", "data": {"report": balance_text}}


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "alive", "nat_base_url": NAT_BASE_URL}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("FIN_US_BACKEND_PORT", "8787")))
