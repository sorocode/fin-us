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

# 1. 환경변수 및 초기 설정
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

app = FastAPI(
    title="Fin-Us Stock Analysis API",
    description="MCP 기반 뉴스 수집 및 GPT/Claude 분석 투자 에이전트 서비스",
    version="1.1.0"
)

# 2. CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 ["http://localhost:3000"] 등으로 제한 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Pydantic 모델 정의 (프론트엔드와 주고받을 데이터 규격)
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

# 6. [Logic] AI 분석 엔진 (OpenAI/Anthropic 지원)
async def get_trading_signal(news_text: str, stock_name: str, trading_trend: str = "", provider: str = "openai") -> TradingSignal:
    prompt = f"전문 투자 분석가로서 '{stock_name}'의 최신 뉴스와 수급 현황을 분석하여 BUY/SELL/HOLD 신호를 JSON 형식으로 생성하세요. 필드는 decision, confidence_score, reason, target_stock을 포함해야 합니다.\n\n[최신 뉴스]\n{news_text}\n\n[수급 현황(외인/기관)]\n{trading_trend}"
    
    try:
        if provider == "openai":
            if not OPENAI_API_KEY:
                raise HTTPException(status_code=400, detail="OpenAI API 키가 설정되지 않았습니다.")
            
            response = openai_client.chat.completions.create(
                model="gpt-5.4-mini",
                messages=[
                    {"role": "system", "content": "금융 분석 전문가입니다. 반드시 JSON으로만 응답하세요."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            return TradingSignal(**data)
            
        elif provider == "anthropic":
            if not ANTHROPIC_API_KEY:
                raise HTTPException(status_code=400, detail="Anthropic API 키가 설정되지 않았습니다.")
            
            response = anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system="금융 분석 전문가입니다. 반드시 JSON으로만 응답하세요. 다른 설명은 생략하세요.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            # Claude의 응답 텍스트 추출
            text_content = response.content[0].text
            data = json.loads(text_content)
            return TradingSignal(**data)
        
        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 모델 제공자입니다.")
            
    except Exception as e:
        print(f"AI Error ({provider}): {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI 분석 도중 오류가 발생했습니다: {str(e)}")

# --- API 엔드포인트 영역 (v1 계층화) ---

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
    """뉴스 및 수급 현황을 수집하고 선택한 AI가 투자 신호를 분석합니다."""
    # 뉴스 및 수급 데이터 동시 수집
    news_task = run_mcp_tool(NEWS_MCP_PARAMS, "get_market_news", {"stock_name": stock})
    trend_task = run_mcp_tool(NEWS_MCP_PARAMS, "get_investor_trading", {"stock_name": stock})
    
    news_content, trend_content = await asyncio.gather(news_task, trend_task)
    
    signal = await get_trading_signal(news_content, stock, trend_content, provider)
    
    report = AnalysisReport(
        summary=f"[{provider.upper()}] '{stock}' 분석 결과 현재 {signal.decision} 전략을 추천합니다.",
        details=signal,
        source_news=news_content.split("\n"),
        trading_trend=trend_content
    )
    return {"status": "success", "data": report.model_dump()}

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
