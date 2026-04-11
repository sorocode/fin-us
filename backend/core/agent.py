import yaml
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json

class Agent:
    def __init__(self, config_path: str, provider: str = "openai"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.name = self.config['name']
        self.role = self.config['role']
        self.persona = self.config['persona']
        self.goal = self.config['goal']
        self.skills = self.config.get('skills', [])
        self.instructions = self.config.get('instructions', [])
        self.provider = provider

        # API 클라이언트 초기화 (실제 운영 시에는 외부에서 주입)
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    async def run_task(self, prompt: str, context_data: Dict[str, Any] = None) -> str:
        system_message = f"당신은 {self.name}이며, {self.role}입니다.\n\n[페르소나]\n{self.persona}\n\n[목표]\n{self.goal}\n\n[지침]\n"
        for inst in self.instructions:
            system_message += f"- {inst}\n"

        user_content = prompt
        if context_data:
            user_content += f"\n\n[참고 데이터]\n{json.dumps(context_data, ensure_ascii=False, indent=2)}"

        if self.provider == "openai":
            response = self.openai_client.chat.completions.create(
                model="gpt-5.4-mini", # 실제 사용 가능한 모델명으로 변경 필요
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_content}
                ]
            )
            return response.choices[0].message.content
        elif self.provider == "anthropic":
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-6", # 실제 사용 가능한 모델명으로 변경 필요
                max_tokens=2048,
                system=system_message,
                messages=[{"role": "user", "content": user_content}]
            )
            return response.content[0].text
        else:
            return "지원하지 않는 모델 제공자입니다."

class MultiAgentOrchestrator:
    def __init__(self, agents_dir: str, provider: str = "openai"):
        self.agents_dir = agents_dir
        self.provider = provider
        self.news_analyst = Agent(os.path.join(agents_dir, "news_analyst.yaml"), provider)
        self.trading_executor = Agent(os.path.join(agents_dir, "trading_executor.yaml"), provider)
        self.orchestrator = Agent(os.path.join(agents_dir, "orchestrator.yaml"), provider)

        # MCP 설정
        self.news_mcp = StdioServerParameters(command="node", args=[os.path.abspath("../mcp-news/index.js")])
        self.trading_mcp = StdioServerParameters(command="node", args=[os.path.abspath("../mcp-trading/index.js")])

    async def _call_mcp(self, mcp_params, tool_name, args):
        async with stdio_client(mcp_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                return result.content[0].text

    async def analyze_stock(self, stock_name: str) -> Dict[str, Any]:
        # 1. News Analyst 작업: 데이터 수집 및 분석
        news = await self._call_mcp(self.news_mcp, "get_market_news", {"stock_name": stock_name})
        trend = await self._call_mcp(self.news_mcp, "get_investor_trading", {"stock_name": stock_name})
        reports = await self._call_mcp(self.news_mcp, "get_research_reports", {"stock_name": stock_name})

        news_analysis = await self.news_analyst.run_task(
            f"'{stock_name}'에 대한 시장 심리와 리서치 리포트 내용을 분석해주세요.",
            context_data={"news": news, "trading_trend": trend, "research_reports": reports}
        )

        # 2. Trading Executor 작업: 계좌 확인 및 매매 전략 수립
        balance = await self._call_mcp(self.trading_mcp, "get_balance", {})
        
        trading_strategy = await self.trading_executor.run_task(
            f"News Analyst의 분석 결과와 계좌 상황을 바탕으로 '{stock_name}'에 대한 매매 결정을 내려주세요.",
            context_data={"analysis_report": news_analysis, "account_balance": balance}
        )

        # 3. Orchestrator 작업: 최종 리포트 생성
        final_report_json = await self.orchestrator.run_task(
            f"'{stock_name}'에 대한 최종 투자 리포트를 작성해주세요. 반드시 JSON 형식으로 작성해야 하며, 'summary', 'details' (decision, confidence_score, reason, target_stock), 'source_news', 'trading_trend' 필드를 포함해야 합니다.",
            context_data={"news_analysis": news_analysis, "trading_strategy": trading_strategy, "source_news": news.split('\n'), "trading_trend": trend}
        )

        try:
            start_idx = final_report_json.find('{')
            end_idx = final_report_json.rfind('}') + 1
            return json.loads(final_report_json[start_idx:end_idx])
        except:
            return {
                "summary": "리포트 생성 중 오류가 발생했습니다.",
                "details": {"decision": "HOLD", "confidence_score": 0, "reason": "JSON 파싱 에러", "target_stock": stock_name},
                "source_news": [],
                "trading_trend": ""
            }
