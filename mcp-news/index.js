import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { chromium } from "playwright";

// 1. 서버 인스턴스 생성
const server = new Server(
  { name: "news-tool", version: "1.0.0" },
  { capabilities: { tools: {} } },
);

// 2. 도구 목록 정의
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "get_market_news",
      description: "특정 주식 종목의 최신 뉴스 3개를 네이버에서 가져옵니다.",
      inputSchema: {
        type: "object",
        properties: {
          stock_name: {
            type: "string",
            description: "주식 종목명 (예: 삼성전자, SK하이닉스)",
          },
        },
        required: ["stock_name"],
      },
    },
  ],
}));

// 3. 도구 실행 로직 (통합 및 보강 버전)
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "get_market_news") {
    const { stock_name } = request.params.arguments;

    if (!stock_name) {
      return {
        content: [
          { type: "text", text: "에러: stock_name 파라미터가 누락되었습니다." },
        ],
        isError: true,
      };
    }

    // 브라우저 실행 (봇 차단 방지를 위해 상세 설정 추가)
    const browser = await chromium.launch({ headless: true });
    try {
      const context = await browser.newContext({
        userAgent:
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport: { width: 1280, height: 800 },
        extraHTTPHeaders: {
          "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        },
      });
      const page = await context.newPage();

      // 네이버 뉴스 검색 결과로 이동
      const searchUrl = `https://search.naver.com/search.naver?where=news&query=${encodeURIComponent(stock_name)}&sm=tab_opt&sort=0`;

      await page.goto(searchUrl, { waitUntil: "load" });

      // 뉴스 제목 요소 또는 뉴스 목록이 나타날 때까지 대기 (최대 8초)
      await Promise.race([
        page.waitForSelector(".news_tit", { timeout: 8000 }),
        page.waitForSelector(".list_news", { timeout: 8000 }),
      ]).catch(() => null);

      // 페이지 로드 후 잠시 추가 대기 (동적 렌더링 대응)
      await page.waitForTimeout(1000);

      // 뉴스 제목 추출 (하이브리드 방식: 기존 .news_tit + 새로운 Fender 구조 대응)
      const results = await page.evaluate(() => {
        // 1. 기존 .news_tit 셀렉터 시도
        const traditional = Array.from(document.querySelectorAll(".news_tit"))
          .map((t) => t.textContent.trim())
          .filter((t) => t.length > 0);

        if (traditional.length > 0) return traditional.slice(0, 3);

        // 2. 새로운 구조 (Fender Renderer) 대응
        const listNews = document.querySelector(".list_news");
        if (!listNews) return [];

        const titles = [];
        const links = Array.from(listNews.querySelectorAll('a[target="_blank"]'));

        for (const link of links) {
          const text = link.textContent.trim();
          // 제목 필터링 로직:
          // - 너무 짧거나(언론사명 등) 너무 긴 것(기사 요약 등) 제외
          // - "저장", "바로가기" 등 유틸리티 텍스트 제외
          // - 말줄임표(...)로 끝나는 요약문 제외
          if (
            text.length > 10 &&
            text.length < 100 &&
            !text.includes("저장") &&
            !text.includes("바로가기") &&
            !text.endsWith("...") &&
            !link.className.includes("press")
          ) {
            if (!titles.includes(text)) {
              titles.push(text);
            }
          }
          if (titles.length >= 3) break;
        }
        return titles;
      });

      if (results.length === 0) {
        const pageTitle = await page.title();
        return {
          content: [
            {
              type: "text",
              text: `'${stock_name}'에 대한 뉴스를 찾지 못했습니다. (페이지 제목: ${pageTitle})\n주소: ${searchUrl}`,
            },
          ],
        };
      }

      return {
        content: [{ type: "text", text: results.join("\n") }],
      };
    } catch (error) {
      return {
        content: [
          { type: "text", text: `크롤링 중 에러 발생: ${error.message}` },
        ],
        isError: true,
      };
    } finally {
      await browser.close();
    }
  }
  throw new Error("존재하지 않는 도구입니다.");
});

// 4. 전송 계층 연결
const transport = new StdioServerTransport();
await server.connect(transport);

console.error("News MCP Server is running...");
