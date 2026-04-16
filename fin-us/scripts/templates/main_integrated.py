# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Fin-Us reference UI + MCP routes, with agent analysis delegated to NAT (`finus_nat`).

Copied from `fin-us-reference/backend/main.py` patterns for market MCP endpoints; orchestration
YAML under `backend/agents/` is intentionally not used — routing lives in NAT workflows.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field

# --- paths: fin-us/backend -> fin-us/{mcp-news,mcp-trading}
FIN_US_ROOT = Path(__file__).resolve().parent.parent
NEWS_MCP_DIR = (FIN_US_ROOT / "mcp-news").resolve()
TRADING_MCP_DIR = (FIN_US_ROOT / "mcp-trading").resolve()

load_dotenv(FIN_US_ROOT / "backend" / ".env")
load_dotenv()

NAT_BASE_URL = os.environ.get("NAT_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
NAT_CHAT_MODEL = os.environ.get(
    "NAT_CHAT_MODEL",
    os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
)

NEWS_MCP_PARAMS = StdioServerParameters(
    command="node",
    args=[str(NEWS_MCP_DIR / "index.js")],
    cwd=str(NEWS_MCP_DIR),
)
TRADING_MCP_PARAMS = StdioServerParameters(
    command="node",
    args=[str(TRADING_MCP_DIR / "index.js")],
    cwd=str(TRADING_MCP_DIR),
)

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
    source_news: List[str]
    trading_trend: Optional[str] = None


class CommonResponse(BaseModel):
    status: str = "success"
    data: Optional[dict] = None
    message: Optional[str] = None


async def run_mcp_tool(
    server_params: StdioServerParameters,
    tool_name: str,
    arguments: dict,
) -> str:
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result.content[0].text
    except Exception as e:  # noqa: BLE001
        print(f"MCP Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"데이터 공급원({tool_name}) 연결 실패: {e}",
        ) from e


def _analysis_from_nat_text(raw: str, stock: str) -> dict:
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


@app.get("/api/v1/news", response_model=CommonResponse, tags=["Market Data"])
async def get_news(stock: str = Query(..., examples=["삼성전자"])):
    content = await run_mcp_tool(
        NEWS_MCP_PARAMS,
        "get_market_news",
        {"stock_name": stock},
    )
    return {"status": "success", "data": {"stock": stock, "news": content.split("\n")}}


@app.get("/api/v1/analyze", response_model=CommonResponse, tags=["AI Agent"])
async def analyze_stock(
    stock: str = Query(..., examples=["SK하이닉스"]),
    provider: str = Query(
        "openai",
        description="ignored — orchestration is NAT + finus_nat",
    ),
):
    _ = provider
    user_msg = (
        f"종목: {stock}. 라우터·서브에이전트를 활용해 투자 관점 분석을 하라. "
        "답변 마지막에 **다음 JSON 한 개만** 출력하라 (다른 텍스트 없이도 됨):\n"
        '{"summary":"한 줄 요약",'
        '"details":{"decision":"BUY"|"SELL"|"HOLD","confidence_score":0.0-1.0,'
        f'"reason":"근거","target_stock":"{stock}"}},'
        '"source_news":["헤드라인1","헤드라인2"],'
        '"trading_trend":"수급 한줄 요약 또는 null"}'
    )
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
        raw = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"NAT 응답 형식 오류: {exc}",
        ) from exc

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
