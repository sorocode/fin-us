# 📈 Fin-Us: Multi-Agent AI Investment Orchestrator

Fin-Us는 **MCP (Model Context Protocol)** 아키텍처와 **멀티 에이전트 워크플로우**를 결합한 차세대 지능형 투자 시스템입니다. 독립적인 인격을 가진 에이전트들이 각자의 도구(MCP)를 활용해 협업하며, 뉴스 분석부터 실제 매매 집행까지의 복잡한 의사결정을 자율적으로 수행합니다.

## 🤖 Multi-Agent Ecosystem

Fin-Us는 단일 모델이 모든 일을 처리하지 않고, 역할이 분리된 전문 에이전트들이 협력합니다. 각 에이전트의 페르소나와 지침은 YAML 설정을 통해 관리됩니다.

| 에이전트 (Agent) | 페르소나 (Persona) | 보유 스킬 (MCP Skills) | 목표 (Goal) |
| :--- | :--- | :--- | :--- |
| **News Analyst** | 냉철한 시장 분석가 | `get_market_news`, `get_investor_trading`, `get_research_reports` | 시장 심리 수치화, 호재/악재 판별 및 리서치 리포트 분석 |
| **Trading Executor** | 리스크 관리 트레이더 | `get_balance`, `place_order` | 자산 현황 파악 및 최적의 매매 집행 |
| **Orchestrator** | 전략 총괄 매니저 | 에이전트 간 협업 조율 | 사용자 요청 분석 및 최종 의사결정 |

## 🚀 주요 특징

- **YAML 기반 에이전트 설정**: 에이전트의 성격, 배경지식, 작업 지침을 코드가 아닌 YAML 파일로 관리하여 유연한 튜닝이 가능합니다.
- **관심사 분리 (SoC)**: MCP를 통해 도구(Tool)를 분리하고, 에이전트별로 역할을 분산하여 LLM의 할루시네이션(환각)을 최소화했습니다.
- **실시간 지식 확장**: Playwright 기반 MCP 서버를 통해 정적인 학습 데이터를 넘어 실시간 시장 데이터 및 **증권사 리포트**에 접근합니다.
- **안정적인 금융 연동**: 한국투자증권(KIS) API를 통해 시뮬레이션이 아닌 실제 자산 데이터를 기반으로 전략을 수립합니다.

## 🏗️ 시스템 아키텍처

시스템은 '관심사 분리' 원칙에 따라 다음과 같이 구성됩니다.

1.  **Orchestration Layer (`backend/`)**: Python (FastAPI)
    - YAML 설정을 로드하여 전문 에이전트 객체를 생성합니다.
    - 에이전트 간의 데이터 전달 및 실행 순서(Workflow)를 제어합니다.
2.  **Tooling Layer (MCP Servers)**:
    - **News Provider (`mcp-news/`)**: 실시간 뉴스 및 **네이버 증권 리서치 리포트** 공급.
    - **Trading Provider (`mcp-trading/`)**: 증권사 API를 통한 정형 금융 데이터 공급 및 명령 집행.
3.  **Presentation Layer (`frontend-react/`)**: React (TypeScript)
    - 실시간 투자 신호 및 분석 리포트를 시각화하여 사용자에게 제공합니다.

## 🛠️ 설치 및 시작하기

### 사전 준비 사항

- Python 3.12+
- Node.js & npm
- API Keys: OpenAI/Anthropic API, 한국투자증권(KIS) API Key/Secret

### 1. 에이전트 페르소나 설정
`backend/agents/` 폴더 내의 YAML 파일을 수정하여 에이전트의 성격을 정의할 수 있습니다.

```yaml
# 예시: news_analyst.yaml
name: "NewsAnalyst"
role: "시장 심리 및 리서치 분석가"
goal: "뉴스의 행간을 읽고 증권사 리포트를 분석하여 투자 신뢰도를 산출함"
```

### 2. 환경 변수 설정

각 프로젝트 폴더의 `.env.example`을 참고하여 `.env` 파일을 생성합니다.

```bash
# backend/.env
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# mcp-trading/.env
KIS_API_KEY=your_kis_key
...
```

### 3. 시스템 가동

```bash
# 1. MCP Servers (News & Trading) 빌드
cd mcp-news && npm install
cd mcp-trading && npm install

# 2. Backend Orchestrator 실행
cd backend
pip install -r requirements.txt
python main.py

# 3. Frontend 실행
cd frontend-react
npm install
npm run dev
```

## 📝 에이전트별 보유 스킬 (MCP Tools)

| 에이전트 | 스킬 이름 | 설명 |
| :--- | :--- | :--- |
| **News Analyst** | `get_market_news` | 네이버 뉴스 기반 최신 동향 수집 |
| | `get_investor_trading` | 기관/외국인 수급 데이터 분석 |
| | `get_research_reports` | **네이버 증권 리서치 종목 분석 리포트 수집** |
| **Trading Executor** | `get_balance` | 실시간 계좌 잔고 및 수익률 확인 |
| | `execute_trade` | 매수/매도 주문 실행 (KIS API) |

## 📅 로드맵

- [x] 멀티 에이전트 협업 구조 설계 (YAML-based)
- [x] MCP 기반 뉴스 수집 및 트레이딩 도구 통합
- [x] **네이버 증권 리서치 리포트 분석 에이전트 구현**
- [x] LLM(Gemini/Claude) 기반 전략 수립 파이프라인 완성
- [ ] NVIDIA NeMo Guardrails를 이용한 투자 가이드라인 준수 레이어 추가
- [ ] 기술적 분석(차트) 에이전트 추가 도입
- [ ] AWS App Runner & Docker 기반 클라우드 배포

---

## 🔀 Docker + NeMo NAT (통합 브랜치)

`docker-compose.yml` 하나로 프론트, 통합 FastAPI 백엔드(`backend/Dockerfile`), **finus-nat**(NeMo NAT)까지 기동합니다. 로컬 개발용으로 백엔드에 저장소 루트 볼륨 마운트(`.:/app`)가 들어 있습니다.

```bash
cp backend/.env.example backend/.env
# 키 입력 후:
docker compose up --build
```

또는:

```bash
bash scripts/run_stack.sh
```

- 로컬에서 `uvicorn --reload`만 쓰고 싶다면 볼륨 마운트된 소스로 호스트에서 실행하면 됩니다.
- `fin-us-reference/` 로컬 복사본은 merge 후 삭제해도 되며, `.gitignore`에 포함되어 있습니다.
