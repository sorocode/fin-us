import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { chromium } from "playwright";
import {
  CATEGORIES,
  NAVER_INDUSTRIES,
  fetchResearchReportsWithText,
} from "./naverResearch.js";

const CATEGORY_KEYS = Object.keys(CATEGORIES);
const CATEGORY_HINT = CATEGORY_KEYS
  .map((k) => `${k}(${CATEGORIES[k].label})`)
  .join(", ");

const server = new Server(
  { name: "news-tool", version: "1.0.0" },
  { capabilities: { tools: {} } },
);

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
    {
      name: "get_investor_trading",
      description: "특정 주식 종목의 외국인 및 기관 순매수 현황을 가져옵니다.",
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
    {
      name: "get_research_reports",
      description:
        "네이버 금융 리서치를 카테고리별로 검색하고 발견된 리포트 PDF를 로컬에 저장한 뒤 본문 텍스트까지 추출해 한 번에 반환합니다. " +
        `카테고리: ${CATEGORY_HINT}. ` +
        "종목 리포트(company)는 query에 종목명(예: '삼성전자') 또는 6자리 종목코드(예: '005930')를 넣으면 내부에서 네이버 공식 자동완성으로 코드를 resolve하여 정확 매칭합니다. " +
        `산업 리포트(industry)는 query에 네이버 업종 드롭다운 값 중 하나를 넣으세요. 가능한 값: ${NAVER_INDUSTRIES.join(", ")}. ` +
        "시황(market_info)/투자(invest)/경제(economy)/채권(debenture)은 query가 제목+내용 키워드 검색입니다. " +
        "응답의 reports[].text에는 상위 max_text_reports 건의 본문이 chars_per_report 길이까지 절삭되어 인라인됩니다.",
      inputSchema: {
        type: "object",
        properties: {
          category: {
            type: "string",
            enum: CATEGORY_KEYS,
            description: "리포트 카테고리 (종목=company, 시황=market_info, 산업=industry 등)",
          },
          query: {
            type: "string",
            description: "검색어. 예: '삼성전자', '005930', '반도체', '원전'. 비워두면 최신 리포트를 가져옵니다.",
          },
          from_date: { type: "string", description: "시작일 YYYY-MM-DD (query 비어있을 때만 적용)" },
          to_date: { type: "string", description: "종료일 YYYY-MM-DD" },
          broker: { type: "string", description: "증권사명 포함 필터 (예: '한화')" },
          limit: {
            type: "number",
            minimum: 1,
            maximum: 50,
            description: "검색·다운로드할 리포트 최대 개수 (기본 5)",
          },
          chars_per_report: {
            type: "number",
            minimum: 500,
            maximum: 20000,
            description: "각 리포트에 인라인할 텍스트 최대 길이 (기본 4000자)",
          },
          max_text_reports: {
            type: "number",
            minimum: 1,
            maximum: 20,
            description: "본문 텍스트를 실제로 붙여 반환할 리포트 개수 (기본 5)",
          },
          save_dir: {
            type: "string",
            description:
              "상위 저장 디렉터리 (미지정 시 RESEARCH_DOWNLOAD_DIR 또는 downloads/). " +
              "매 호출마다 이 경로 아래에 run_<타임스탬프>_<랜덤> 형식의 새 폴더가 만들어지고, PDF·TXT는 그 안에만 저장됩니다.",
          },
        },
        required: ["category"],
      },
    },
  ],
}));

function jsonText(obj) {
  return { content: [{ type: "text", text: JSON.stringify(obj, null, 2) }] };
}

function errorText(message) {
  return { content: [{ type: "text", text: message }], isError: true };
}

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === "get_research_reports") {
    try {
      if (!args?.category) {
        return errorText("category가 필요합니다 (company/industry/market_info/invest/economy/debenture).");
      }
      const result = await fetchResearchReportsWithText({
        category: args.category,
        query: args?.query,
        from_date: args?.from_date,
        to_date: args?.to_date,
        broker: args?.broker,
        limit: args?.limit ?? 5,
        save_dir: args?.save_dir,
        chars_per_report: args?.chars_per_report ?? 4000,
        max_text_reports: args?.max_text_reports ?? 5,
      });
      return jsonText(result);
    } catch (err) {
      return errorText(
        `리서치 종합 조회 실패: ${err instanceof Error ? err.message : err}`,
      );
    }
  }

  const stock_name = args?.stock_name;
  if (!stock_name) {
    return errorText("에러: stock_name 파라미터가 누락되었습니다.");
  }

  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({
      userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    });
    const page = await context.newPage();

    if (name === "get_market_news") {
      const searchUrl = `https://search.naver.com/search.naver?where=news&query=${encodeURIComponent(stock_name)}&sm=tab_opt&sort=0`;
      await page.goto(searchUrl, { waitUntil: "load" });

      await Promise.race([
        page.waitForSelector(".news_tit", { timeout: 8000 }),
        page.waitForSelector(".list_news", { timeout: 8000 }),
      ]).catch(() => null);

      const results = await page.evaluate(() => {
        const traditional = Array.from(document.querySelectorAll(".news_tit"))
          .map((t) => t.textContent.trim())
          .filter((t) => t.length > 0);
        if (traditional.length > 0) return traditional.slice(0, 3);
        const listNews = document.querySelector(".list_news");
        if (!listNews) return [];
        const titles = [];
        const links = Array.from(listNews.querySelectorAll('a[target="_blank"]'));
        for (const link of links) {
          const text = link.textContent.trim();
          if (text.length > 10 && text.length < 100 && !text.includes("저장") && !text.includes("바로가기") && !text.endsWith("...") && !link.className.includes("press")) {
            if (!titles.includes(text)) titles.push(text);
          }
          if (titles.length >= 3) break;
        }
        return titles;
      });

      return { content: [{ type: "text", text: results.length > 0 ? results.join("\n") : `'${stock_name}'에 대한 뉴스를 찾지 못했습니다.` }] };

    } else if (name === "get_investor_trading") {
      const searchUrl = `https://search.naver.com/search.naver?query=${encodeURIComponent(stock_name + " 주가")}`;
      await page.goto(searchUrl, { waitUntil: "load" });
      
      const code = await page.evaluate(() => {
        const links = Array.from(document.querySelectorAll("a"));
        for (const link of links) {
          const href = link.getAttribute("href") || "";
          const match = href.match(/code=(\d{6})/);
          if (match) return match[1];
        }
        return null;
      });

      if (!code) {
        return { content: [{ type: "text", text: `'${stock_name}'의 종목 코드를 찾을 수 없습니다.` }], isError: true };
      }

      await page.goto(`https://finance.naver.com/item/frgn.naver?code=${code}`, { waitUntil: "load" });
      const tradingData = await page.evaluate((sName) => {
        const rows = Array.from(document.querySelectorAll("table.type2 tr"))
          .map(tr => Array.from(tr.querySelectorAll("td")).map(td => td.innerText.trim()))
          .filter(cells => cells.length >= 7 && cells[0].match(/^\d{4}\.\d{2}\.\d{2}$/))
          .slice(0, 5);
        
        if (rows.length === 0) return `데이터를 불러올 수 없습니다.`;
        
        let report = `[${sName}] 최근 5일 외국인/기관 매매동향\n`;
        rows.forEach(row => {
          const change = row[2].replace(/\n/g, " ");
          report += `${row[0]} | 종가: ${row[1]} | 변동: ${change} (${row[3]}) | 외인: ${row[5]} | 기관: ${row[6]} | 거래량: ${row[4]}\n`;
        });
        return report;
      }, stock_name);

      return { content: [{ type: "text", text: tradingData }] };
    }
  } catch (error) {
    return { content: [{ type: "text", text: `에러 발생: ${error.message}` }], isError: true };
  } finally {
    await browser.close();
  }

  return errorText(`존재하지 않는 도구: ${name}`);
});

const transport = new StdioServerTransport();
await server.connect(transport);

console.error("News MCP Server is running...");
