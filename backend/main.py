from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import asyncio
import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from core.agent import MultiAgentOrchestrator

# 1. 환경변수 및 초기 설정
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# 멀티 에이전트 에이전트 설정 경로
AGENTS_PATH = os.path.join(os.path.dirname(__file__), "agents")

app = FastAPI(
    title="Fin-Us Stock Analysis API",
    description="MCP 기반 뉴스/리서치 분석 및 멀티 에이전트 협업 투자 에이전트 서비스",
    version="1.2.0"
)

# 2. CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Pydantic 모델 정의
class NewsItem(BaseModel):
    title: str
    link: Optional[str] = None

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

# 4. MCP 서버 설정
NEWS_MCP_PARAMS = StdioServerParameters(command="node", args=["../mcp-news/index.js"])
TRADING_MCP_PARAMS = StdioServerParameters(command="node", args=["../mcp-trading/index.js"])

# 5. [Helper] MCP 호출 함수
async def run_mcp_tool(server_params: StdioServerParameters, tool_name: str, arguments: dict):
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result.content[0].text
    except Exception as e:
        print(f"MCP Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"데이터 공급원({tool_name}) 연결 실패")

# --- API 엔드포인트 영역 ---

@app.get("/api/v1/news", response_model=CommonResponse, tags=["Market Data"])
async def get_news(stock: str = Query(..., example="삼성전자")):
    """특정 종목의 최신 뉴스를 가져옵니다."""
    content = await run_mcp_tool(NEWS_MCP_PARAMS, "get_market_news", {"stock_name": stock})
    return {"status": "success", "data": {"stock": stock, "news": content.split("\n")}}

@app.get("/api/v1/analyze", response_model=CommonResponse, tags=["AI Agent"])
async def analyze_stock(
    stock: str = Query(..., example="SK하이닉스"),
    provider: str = Query("openai", description="AI 모델 제공자 (openai 또는 anthropic)")
):
    """뉴스, 수급 현황, 리서치 리포트를 수집하고 멀티 에이전트 협업을 통해 투자 전략을 분석합니다."""
    try:
        orchestrator = MultiAgentOrchestrator(AGENTS_PATH, provider=provider)
        report_data = await orchestrator.analyze_stock(stock)
        
        # AnalysisReport 모델에 맞게 변환
        report = AnalysisReport(**report_data)
        
        return {"status": "success", "data": report.model_dump()}
    except Exception as e:
        print(f"Multi-Agent Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"멀티 에이전트 분석 도중 오류가 발생했습니다: {str(e)}")

@app.get("/api/v1/trading/trend", response_model=CommonResponse, tags=["Market Data"])
async def get_trading_trend(stock: str = Query(..., example="삼성전자")):
    """특정 종목의 외국인 및 기관 매매 동향을 가져옵니다."""
    trend = await run_mcp_tool(NEWS_MCP_PARAMS, "get_investor_trading", {"stock_name": stock})
    return {"status": "success", "data": {"stock": stock, "trend": trend}}

@app.get("/api/v1/trading/balance", response_model=CommonResponse, tags=["Trading"])
async def get_account_balance():
    """현재 연결된 계좌의 잔고 현황을 조회합니다."""
    balance_text = await run_mcp_tool(TRADING_MCP_PARAMS, "get_balance", {})
    return {"status": "success", "data": {"report": balance_text}}

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "alive"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
