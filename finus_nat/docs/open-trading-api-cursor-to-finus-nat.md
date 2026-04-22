# `/Users/rokpolar/open-trading-api/.cursor` 구조 분석

> 저장소 문서 규칙에 따라, 본문에서 제품명은 **NVIDIA NeMo Agent Toolkit** / **NeMo Agent Toolkit**으로 표기합니다(원문의 “NAT” 약칭과 동일 의미).

먼저 이 폴더는 **Cursor IDE가 자체 에이전트를 움직일 때 참고하는 사양**입니다. `finus_nat`(NeMo Agent Toolkit 워크플로)와는 **실행 주체와 런타임이 다른** 레이어라는 점부터 구분해야 “적용”을 올바르게 계획할 수 있습니다.

## 1. 폴더 구성 요약

```text
.cursor/
├── rules/            # alwaysApply 안전 규칙 (32줄)
│   └── kis-safety.mdc
├── skills/           # 에이전트 역할 정의 (Claude Skill 포맷, frontmatter + 본문)
│   ├── kis-strategy-builder/SKILL.md     (Step 1: 전략 설계)
│   ├── kis-backtester/SKILL.md           (Step 2: 백테스트) + references/*.md
│   ├── kis-order-executor/SKILL.md       (Step 3: 신호/주문)
│   ├── kis-team/SKILL.md                 (오케스트레이터 1→2→3)
│   └── kis-cs/SKILL.md                   (상담/거절/정책 응답)
├── commands/         # 슬래시 커맨드 (/auth, /my-status, /kis-setup, /kis-help)
├── scripts/          # 커맨드가 호출하는 Python (auth, do_auth, api_client, setup_check)
├── hooks/            # Cursor 라이프사이클 훅
│   ├── hooks.json        # afterAgentResponse, stop
│   ├── cursor/secret-scan.sh
│   └── cursor/session-log.sh
└── logs/             # 훅이 남기는 세션/보안 로그
```

각 파일의 역할은 크게 네 가지입니다.

| 요소 | 역할 | Cursor에서의 의미 |
|---|---|---|
| `rules/*.mdc` | 항상 적용되는 금지/허용 규칙 | 시스템 프롬프트에 상시 주입 |
| `skills/*/SKILL.md` | 특정 트리거 문구에서 활성화되는 역할(페르소나+워크플로) | frontmatter `description`의 키워드로 auto-invoke |
| `commands/*.md` | `/auth`, `/my-status` 같은 슬래시 커맨드 정의 | 사용자가 명시 호출할 때만 실행 |
| `hooks/*` + `scripts/*` | 에이전트 외부에서 돌아가는 코드 (보안 스캔, 로깅, KIS API 호출) | 에이전트가 직접 답변에 섞지 못하는 일 |

## 2. 설계 의도(한 줄 요약)

- **3단계 파이프라인**: `strategy-builder → backtester → order-executor`, 상위에 `kis-team`이 순서/승인을 책임지는 오케스트레이터.
- **고객응대 분리**: 사용자가 “직접 종목 추천해줘”처럼 규정 위반 요청을 하면 `kis-cs` 스킬로 빠지게 해서 본 파이프라인을 더럽히지 않음.
- **안전장치 이중화**: (1) `kis-safety.mdc`로 프롬프트 레벨에서 막고, (2) `hooks/secret-scan.sh`로 출력 후 사후 감시.
- **툴 호출 ≠ 자연어 지시**: 실제 KIS 호출은 `scripts/*.py`(REST)와 `backtester` MCP 서버(`http://127.0.0.1:3846/mcp`)가 담당. 스킬 문서는 “어떤 툴을 어떤 인자로 호출해야 하는지”를 알려주는 런북에 가깝습니다.

## 3. `finus_nat`와 매핑 — 핵심은 “그대로 옮길 수 없다”

현재 `finus_nat`는 NeMo Agent Toolkit이고 구조는 이렇습니다.

```text
fin-us/finus_nat/
├── configs/
│   ├── common.yml
│   ├── router.yml                  # 상위 라우터/팀 역할
│   └── agents/
│       ├── diary_agent.yml
│       ├── monitoring_agent.yml
│       ├── news_agent.yml
│       ├── recommend_agent.yml
│       ├── strategy_agent.yml
│       └── trading_agent.yml
└── src/nat_finus_nat/              # 툴/함수 구현
```

두 세계의 개념은 다음처럼 대응됩니다.

| `.cursor` 쪽 개념 | 실행 주체 | `finus_nat`(NeMo Agent Toolkit) 쪽 대응 | 형태 |
|---|---|---|---|
| `rules/kis-safety.mdc` (alwaysApply) | Cursor 에이전트 | `configs/common.yml` 공통 시스템 프롬프트 + 각 agent `additional_instructions` 상단 | YAML |
| `skills/kis-strategy-builder/SKILL.md` | Cursor 에이전트 | `configs/agents/strategy_agent.yml` (ReAct agent) | YAML + (긴 본문은 별도 `.md`로 외부화) |
| `skills/kis-backtester/SKILL.md` (+ references) | Cursor 에이전트 | 새 `backtest_agent.yml` + KIS MCP 툴 바인딩 | YAML + tool |
| `skills/kis-order-executor/SKILL.md` | Cursor 에이전트 | `trading_agent.yml` 강화 + 주문 실행 툴 | YAML + tool |
| `skills/kis-team/SKILL.md` | Cursor 에이전트 | `router.yml`(또는 상위 react agent)의 `tool_names`에 각 `*_branch_agent` 연결 | YAML |
| `skills/kis-cs/SKILL.md` | Cursor 에이전트 | `cs_agent.yml` 또는 라우터의 fallback 분기 | YAML |
| `commands/auth.md`, `my-status.md` | 사용자 호출 | NeMo Agent Toolkit에는 슬래시 커맨드가 없음 → **툴(function)** 로 만들고 에이전트가 호출 | `@register_function` |
| `commands/kis-setup.md` | 사용자 호출 | 개발 환경 세팅 → **NeMo Agent Toolkit 범위 밖**, `scripts/`에 그대로 두기 | 그대로 |
| `commands/kis-help.md` | 사용자 호출 | 정적 문서 → NeMo Agent Toolkit에 넣을 필요 없음, README/도움 함수로 | README |
| `scripts/auth.py`, `api_client.py`, `do_auth.py` | 순수 Python | `src/nat_finus_nat/tools/` 아래 NeMo Agent Toolkit 함수로 래핑 | Python + `@register_function` |
| `hooks/hooks.json` + `secret-scan.sh` | Cursor IDE | NeMo Agent Toolkit은 IDE 훅이 없음 → **미들웨어/후처리 함수** 또는 로깅 옵저버로 | Python |
| `hooks/session-log.sh` | Cursor IDE | NeMo Agent Toolkit 자체 tracing/`general.telemetry` 설정 | YAML |

핵심 포인트 두 가지:

1. **스킬 = 에이전트 1개**로 본다. `kis-strategy-builder` SKILL.md 전체를 `strategy_agent.yml`의 `additional_instructions`에 통째로 넣지 마십시오. 앞서 얘기한 150줄 문제가 여기서 다시 터집니다. 이 중에서 **페르소나/규칙**만 프롬프트에 남기고, **“이 파라미터를 이 툴로 호출하라”는 부분은 그 툴의 description과 schema로 이전**합니다.
2. **커맨드는 NeMo Agent Toolkit에서 “툴(function)”로 바뀐다.** `/auth`, `/my-status` 같은 Cursor 전용 호출은 NeMo Agent Toolkit에선 없으므로, `scripts/auth.py`를 그대로 import해서 `kis_auth_status`, `kis_account_snapshot` 같은 함수로 등록하고 에이전트 `tool_names`에 추가해야 합니다.

## 4. 구체 이식 계획 (추천 순서)

### Phase 0 — 공통 규칙/공용 설정 (가장 먼저)

- `rules/kis-safety.mdc` 내용을 정리해 `configs/common.yml`(있다면 `base:`로 상속되는 곳)에 **요약형** 시스템 지시로 넣는다. 길이는 20~30줄 이내.
- 한 문단으로 모든 에이전트가 공유할 것: “secret 하드코딩 금지 / 실전 주문 전 확인 / 계좌번호 마스킹 / 신호 강도 0.5 미만 주문 금지”.

### Phase 1 — 스크립트를 NeMo Agent Toolkit 툴로 이관

`src/nat_finus_nat/tools/kis/` 디렉터리 신설:

- `auth.py` → `kis_auth_status`, `kis_auth_login(mode: Literal["vps","prod"])`
- `api_client.py` → `kis_account_balance`, `kis_holdings`, `kis_market_index`
- (백테스터 MCP는 이미 서버라면 MCP 클라이언트 툴로 바인딩)

각 함수는 NeMo Agent Toolkit의 `@register_function` + `pydantic` 스키마로 노출. 기존 스크립트 파일은 건드리지 말고 **얇은 래퍼만** 작성하세요.

### Phase 2 — 스킬 → 에이전트 YAML 변환

각 SKILL.md에 대해 아래 3개 칸만 추출:

| SKILL.md 영역 | NeMo Agent Toolkit 대응 |
|---|---|
| frontmatter `description` | `function_description` 또는 `tool_description` (라우터용) |
| 본문의 `Purpose` + `Workflow` 핵심 규칙(10~30줄) | `additional_instructions` |
| 본문의 “이 툴을 이 인자로 호출하라” 표 | `tool_names` + 각 툴 description에 흡수 |

예: `strategy_agent.yml`은 이미 20줄대 골격이 있으니 `kis-strategy-builder` SKILL.md의 본문 중 “진입·청산 연산자 규칙 / `$param_name` 금지 / 다중 출력 지표는 단일 alias + compare_to” 정도만 옮기면 충분합니다. 10개 프리셋 목록·전체 YAML 예시는 **프롬프트 대신 `references/*.md` 파일로 디스크에 두고 필요할 때 `read_file` 툴로 읽게** 하십시오.

### Phase 3 — 라우터/오케스트레이션

- `kis-team` = `configs/router.yml`의 상위 ReAct agent. `tool_names: [strategy_branch_agent, backtest_branch_agent, trading_branch_agent, cs_branch_agent]`.
- `additional_instructions`엔 “단계 간 사용자 확인”, “실전 모드 경고”만. 세부 규칙은 각 하위 에이전트가 이미 알고 있어야 합니다.

### Phase 4 — hooks 대체

- `secret-scan.sh` → NeMo Agent Toolkit 응답 후처리용 함수/미들웨어(프로젝트에 옵저버 훅이 있다면 거기, 없으면 `trading_agent`의 최종 포맷 함수 말미에 정규식 검사).
- `session-log.sh` → NeMo Agent Toolkit 빌트인 tracing/로깅 설정으로 대체. 동일 포맷의 로그가 필요하면 커스텀 옵저버로 한 번만 구현.

## 5. 흔히 빠지는 함정

- **SKILL.md 통째 복붙 금지.** 300줄짜리 `kis-backtester` SKILL을 `additional_instructions`에 넣으면 토큰 비용과 ReAct 포맷 붕괴가 동시에 옵니다.
- **커맨드는 NeMo Agent Toolkit에선 존재하지 않는다.** `/auth` 같은 UX는 상위 라우터의 한 툴 호출로 “인증 상태를 먼저 확인합니다” 같은 문구로 재현하세요.
- **훅은 IDE 전용.** 보안/로깅은 NeMo Agent Toolkit 런타임 안에서 구현해야 실제로 동작합니다. `.sh` 훅을 그대로 옮겨선 아무것도 걸러지지 않습니다.
- **MCP 주소 하드코딩 금지.** `http://127.0.0.1:3846/mcp`는 config 값으로 빼고(`common.yml` 또는 env), 툴 쪽에서 주입받게.
- **`rules/kis-safety.mdc`의 `alwaysApply: true` 의미를 착각하지 말 것.** NeMo Agent Toolkit에는 동일 메커니즘이 없으니, “공통 prompt를 base로 상속”하는 방식으로만 재현됩니다.

## 6. 다음으로 할 수 있는 작업 (선택)

원하면 바로 이어서 이 중 하나를 구체 파일로 만들 수 있습니다. 어느 쪽부터 할지, 그리고 백테스터 MCP(`:3846`)를 NeMo Agent Toolkit에서 실제로 붙여야 하는지(또는 일단 보류)만 정하면 해당 영역을 실제 파일로 작성할 수 있습니다.

1. `configs/common.yml`에 들어갈 **KIS 공통 안전 시스템 프롬프트(요약판, 25줄 이하)** 초안
2. `kis-strategy-builder` SKILL.md → `strategy_agent.yml`의 `additional_instructions` **압축본(30~40줄)** + 외부화할 `references/` 파일 목록
3. `scripts/auth.py` / `api_client.py`를 NeMo Agent Toolkit 툴로 래핑하는 `src/nat_finus_nat/tools/kis/` 골격
4. `router.yml`을 `kis-team` 오케스트레이터로 확장하는 diff

---

**출처**: 이 문서는 대화에서 정리한 `open-trading-api`의 `.cursor` 폴더와 `finus_nat` 이식 매핑 내용을 문서화한 것입니다. 원본 경로는 macOS 기준 `/Users/rokpolar/open-trading-api/.cursor`입니다 (`/home/rokpolar/...`는 해당 환경에 없을 수 있음).
