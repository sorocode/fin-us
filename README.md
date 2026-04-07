# 📈 Fin-Us: AI Stock Analysis & Trading Agent

Fin-Us는 **MCP (Model Context Protocol)** 아키텍처를 활용하여 실시간 뉴스 분석과 증권사 API 연동을 결합한 차세대 AI 투자 에이전트 시스템입니다. LLM(GPT-4)이 시장 상황을 분석하고, 한국투자증권(KIS) API를 통해 실질적인 자산 관리 및 매매 전략을 제안합니다.

## 🚀 주요 특징

- **MCP 기반 모듈화**: 뉴스 크롤링, 트레이딩 엔진 등 각 기능을 독립적인 MCP 서버로 분리하여 확장성과 유지보수성을 극대화했습니다.
- **실시간 데이터 분석**: Playwright 기반의 뉴스 크롤러를 통해 특정 종목의 최신 시장 반응을 즉각적으로 수집합니다.
- **AI 의사결정**: 수집된 뉴스를 바탕으로 GPT-4 모델이 투자 등급(BUY/SELL/HOLD)과 신뢰도 점수, 근거가 포함된 리포트를 생성합니다.
- **증권사 연동**: 한국투자증권(KIS) API와 연동하여 계좌 잔고 조회 및 자산 현황을 실시간으로 파악합니다.

## 🏗️ 시스템 아키텍처

시스템은 '관심사 분리' 원칙에 따라 다음과 같이 구성됩니다.

1.  **Core Orchestrator (`backend/`)**: Python (FastAPI)
    - 사용자의 요청을 수신하고 전체 워크플로우를 관리합니다.
    - MCP Client로서 하위 도구들을 호출하고 LLM과 통신하여 최종 분석 결과를 도출합니다.
2.  **News Provider (`mcp-news/`)**: Node.js (Playwright)
    - 네이버 등 주요 포털에서 특정 종목의 최신 뉴스를 스크래핑하는 MCP 서버입니다.
3.  **Trading Provider (`mcp-trading/`)**: Node.js (KIS API)
    - 한국투자증권 API를 호출하여 계좌 잔고를 조회하고 매매 기능을 수행하는 MCP 서버입니다.

## 🛠️ 설치 및 시작하기

### 사전 준비 사항

- Python 3.12+
- Node.js & npm
- API Keys: OpenAI API, 한국투자증권(KIS) API Key/Secret

### 1. 환경 변수 설정

각 프로젝트 폴더의 `.env.example`을 참고하여 `.env` 파일을 생성합니다.

```bash
# backend/.env
OPENAI_API_KEY=your_openai_key

# mcp-trading/.env
KIS_API_KEY=your_kis_key
KIS_API_SECRET=your_kis_secret
KIS_ACCOUNT_NO=your_account_number
KIS_URL=https://openapi.koreainvestment.com:9443
```

### 2. 백엔드 실행

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 3. MCP 서버 설치

```bash
# 뉴스 MCP
cd mcp-news
npm install

# 트레이딩 MCP
cd mcp-trading
npm install
```

## 📝 주요 API 및 기능

| 도구 이름         | 위치          | 설명                                                                                                         |
| :---------------- | :------------ | :----------------------------------------------------------------------------------------------------------- |
| `get_market_news` | `mcp-news`    | 특정 종목의 최신 뉴스 3개를 수집합니다.                                                                      |
| `get_balance`     | `mcp-trading` | 한국투자증권 계좌의 현재 잔고 및 자산 현황을 조회합니다.                                                     |
| `/analyze` (API)  | `backend`     | 뉴스 수집 + AI 분석을 통해 투자 전략 리포트를 생성합니다. (`provider` 파라미터로 openai/anthropic 선택 가능) |

## 📅 로드맵

- [x] 프로젝트 아키텍처 설계
- [x] Playwright 기반 뉴스 MCP 서버 구현
- [x] OpenAI 연동 및 투자 분석 로직 구현
- [x] 한국투자증권 API 기반 잔고 조회 기능
- [ ] 실제 매매 주문 기능 추가 (Buy/Sell)
- [ ] NVIDIA NeMo Guardrails 기반 안전 장치 도입
- [x] 다중 언어 백엔드(Express) 정식 지원 (Express TypeScript 마이그레이션 완료)

---

_이 프로젝트는 투자 권유가 아니며, AI 분석 결과에 따른 투자 책임은 사용자 본인에게 있습니다._
사용자 본인에게 있습니다.\*
