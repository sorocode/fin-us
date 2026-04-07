import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import axios from "axios";
import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";

// 1. 환경변수 로드
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.join(__dirname, ".env") });

const { KIS_API_KEY, KIS_API_SECRET, KIS_ACCOUNT_NO, KIS_URL } = process.env;

// 2. 서버 인스턴스 생성
const server = new Server(
  { name: "trading-tool", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// 3. 도구 목록 정의
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "get_balance",
      description: "한국투자증권 계좌의 현재 잔고 및 자산 현황을 조회합니다.",
      inputSchema: {
        type: "object",
        properties: {},
      },
    },
  ],
}));

/**
 * [Helper] KIS API Access Token 발급
 */
async function getAccessToken() {
  try {
    const response = await axios.post(`${KIS_URL}/oauth2/tokenP`, {
      grant_type: "client_credentials",
      appkey: KIS_API_KEY,
      appsecret: KIS_API_SECRET,
    });
    return response.data.access_token;
  } catch (error) {
    throw new Error(`Access Token 발급 실패: ${error.response?.data?.msg1 || error.message}`);
  }
}

// 4. 도구 실행 로직
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "get_balance") {
    
    // API 키 설정 확인
    if (!KIS_API_KEY || KIS_API_KEY === "your_kis_api_key_here") {
      return {
        content: [{ 
          type: "text", 
          text: "에러: KIS API 키가 설정되지 않았습니다. mcp-trading/.env 파일을 확인해주세요." 
        }],
        isError: true,
      };
    }

    try {
      const token = await getAccessToken();

      // 주식 잔고 조회 API 호출 (실무 예시: v1/trading/inquire-balance)
      // 실제 API 상세 파라미터(CANO, ACNT_PRDT_CD 등)는 계좌에 맞게 조정 필요
      const response = await axios.get(`${KIS_URL}/uapi/domestic-stock/v1/trading/inquire-balance`, {
        headers: {
          "Content-Type": "application/json",
          "authorization": `Bearer ${token}`,
          "appkey": KIS_API_KEY,
          "appsecret": KIS_API_SECRET,
          "tr_id": "TTTC8434R", // 실전용 TR ID (모의투자는 다를 수 있음)
          "custtype": "P",      // 개인
        },
        params: {
          "CANO": KIS_ACCOUNT_NO.substring(0, 8),
          "ACNT_PRDT_CD": KIS_ACCOUNT_NO.substring(8, 10),
          "AFHR_FLPR_YN": "N",
          "OFL_YN": "",
          "INQR_DVSN": "02",
          "UNPR_DVSN": "01",
          "FUND_STTL_ICLD_YN": "N",
          "FRLG_AMT_UNIT_CD": "00",
          "CTX_AREA_FK100": "",
          "CTX_AREA_NK100": ""
        }
      });

      const data = response.data;
      if (data.rt_cd !== '0') {
        throw new Error(`API 오류: ${data.msg1}`);
      }

      // 결과 포맷팅 (주요 자산 정보 추출)
      const summary = data.output2[0];
      const balanceInfo = `
[계좌 잔고 현황]
- 총 평가금액: ${summary.tot_evlu_amt}원
- 순자산금액: ${summary.pchs_amt_smtl_amt}원
- 총 손익: ${summary.evlu_pfls_smtl_amt}원 (수익률: ${summary.evlu_pfls_rt}%)
- 예수금: ${summary.dnca_tot_amt}원
      `.trim();

      return {
        content: [{ type: "text", text: balanceInfo }],
      };
    } catch (error) {
      return {
        content: [{ type: "text", text: `잔고 조회 중 에러 발생: ${error.message}` }],
        isError: true,
      };
    }
  }
  throw new Error("존재하지 않는 도구입니다.");
});

// 5. 전송 계층 연결
const transport = new StdioServerTransport();
await server.connect(transport);

console.error("Trading MCP Server is running...");
