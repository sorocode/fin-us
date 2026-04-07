import express, { Request, Response } from 'express';
import { OpenAI } from 'openai';
import { spawn } from 'child_process';
import * as dotenv from 'dotenv';
import cors from 'cors';
import path from 'path';
import swaggerUi from 'swagger-ui-express';

// 1. 환경변수 및 초기 설정
dotenv.config({ path: path.join(__dirname, '../../backend/.env') }); 
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

// 2. Swagger 명세 직접 정의
const swaggerDocument: any = {
  openapi: '3.0.0',
  info: {
    title: 'Fin-Us Stock Analysis API (Express)',
    version: '1.0.0',
    description: 'MCP 기반 뉴스 수집 및 GPT 분석 투자 에이전트 서비스 (Node.js/Express/TypeScript 구현체)',
  },
  servers: [{ url: `http://localhost:${PORT}` }],
  tags: [
    { name: 'Market Data', description: '시장 데이터 조회' },
    { name: 'AI Agent', description: 'AI 기반 분석' },
    { name: 'Trading', description: '거래 및 잔고' },
    { name: 'System', description: '시스템 관리' }
  ],
  paths: {
    '/api/v1/news': {
      get: {
        tags: ['Market Data'],
        summary: '뉴스 검색',
        description: '특정 종목의 최신 뉴스 3개를 가져옵니다.',
        parameters: [{
          name: 'stock',
          in: 'query',
          required: true,
          schema: { type: 'string' },
          example: '삼성전자'
        }],
        responses: { 200: { description: '성공' } }
      }
    },
    '/api/v1/analyze': {
      get: {
        tags: ['AI Agent'],
        summary: '투자 신호 분석',
        description: '뉴스를 수집하고 GPT가 투자 신호를 분석합니다.',
        parameters: [{
          name: 'stock',
          in: 'query',
          required: true,
          schema: { type: 'string' },
          example: 'SK하이닉스'
        }],
        responses: { 200: { description: '성공' } }
      }
    },
    '/api/v1/trading/balance': {
      get: {
        tags: ['Trading'],
        summary: '계좌 잔고 조회',
        description: '한국투자증권 계좌의 잔고 현황을 조회합니다.',
        responses: { 200: { description: '성공' } }
      }
    },
    '/health': {
      get: {
        tags: ['System'],
        summary: '헬스체크',
        responses: { 200: { description: 'OK' } }
      }
    }
  }
};

app.use('/swagger', swaggerUi.serve, swaggerUi.setup(swaggerDocument));

// 3. MCP 도구 호출 로직
async function runMCPTool(toolName: string, args: any, scriptPath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn('node', [scriptPath]);
    const timeout = setTimeout(() => {
      child.kill();
      reject(new Error(`MCP Tool ${toolName} timed out`));
    }, 15000);

    child.stdout.on('data', (data) => {
      const lines = data.toString().split('\n').filter((l: string) => l.trim());
      for (const line of lines) {
        try {
          const res = JSON.parse(line);
          if (res.id === 1) {
            child.stdin.write(JSON.stringify({
              jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: toolName, arguments: args }
            }) + '\n');
          } else if (res.id === 2) {
            clearTimeout(timeout);
            if (res.error) reject(new Error(JSON.stringify(res.error)));
            else resolve(res.result.content[0].text);
            child.kill();
          }
        } catch (e) {}
      }
    });
    child.on('error', (err) => { clearTimeout(timeout); reject(err); });
    child.stdin.write(JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'express-client', version: '1.0' } }
    }) + '\n');
  });
}

// 4. API 엔드포인트 구현
app.get('/api/v1/news', async (req: Request, res: Response): Promise<any> => {
  const { stock } = req.query;
  if (!stock) return res.status(400).json({ status: 'error', message: 'stock 파라미터가 필요합니다.' });
  try {
    const news = await runMCPTool('get_market_news', { stock_name: stock }, path.join(__dirname, '../../mcp-news/index.js'));
    res.json({ status: 'success', data: { stock, news: news.split('\n') } });
  } catch (err: any) { res.status(500).json({ status: 'error', message: err.message }); }
});

app.get('/api/v1/analyze', async (req: Request, res: Response): Promise<any> => {
  const { stock } = req.query;
  if (!stock) return res.status(400).json({ status: 'error', message: 'stock 파라미터가 필요합니다.' });
  try {
    const news = await runMCPTool('get_market_news', { stock_name: stock }, path.join(__dirname, '../../mcp-news/index.js'));
    const completion = await openai.chat.completions.create({
      model: 'gpt-5.4-mini',
      messages: [
        { role: 'system', content: '금융 분석 전문가입니다. JSON으로 응답하세요.' },
        { role: 'user', content: `뉴스 분석: ${news}` }
      ],
      response_format: { type: 'json_object' }
    });
    const result = completion.choices[0]?.message.content;
    res.json({ status: 'success', data: result ? JSON.parse(result) : {} });
  } catch (err: any) { res.status(500).json({ status: 'error', message: err.message }); }
});

app.get('/api/v1/trading/balance', async (req: Request, res: Response): Promise<any> => {
  try {
    const balance = await runMCPTool('get_balance', {}, path.join(__dirname, '../../mcp-trading/index.js'));
    res.json({ status: 'success', data: { report: balance } });
  } catch (err: any) { res.status(500).json({ status: 'error', message: err.message }); }
});

app.get('/health', (req: Request, res: Response) => res.json({ status: 'alive', engine: 'express/typescript' }));

app.listen(PORT, () => {
  console.log(`Express Backend 서버 실행 중 (TypeScript): http://localhost:${PORT}`);
  console.log(`Swagger 문서: http://localhost:${PORT}/swagger`);
});
