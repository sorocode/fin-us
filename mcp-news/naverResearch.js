import { load as cheerioLoad } from "cheerio";
import iconv from "iconv-lite";
import { randomBytes } from "node:crypto";
import { createRequire } from "node:module";
import { promises as fs } from "node:fs";
import path from "node:path";

const require = createRequire(import.meta.url);

/** @type {((buf: Buffer) => Promise<{ text: string; numpages: number }>) | null} */
let _pdfParse = null;

function loadPdfParse() {
  if (!_pdfParse) {
    _pdfParse = require("pdf-parse");
  }
  return _pdfParse;
}

const MAX_PDF_BYTES = 80 * 1024 * 1024;

const BASE_URL = "https://finance.naver.com";
const USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

// 네이버 리서치 "산업분석" 페이지의 업종(upjong) 드롭다운 옵션.
// value = label. EUC-KR 요청 시 그대로 들어가며 `searchType=upjong&upjong=<값>`로 사용.
export const NAVER_INDUSTRIES = Object.freeze([
  "건설",
  "건자재",
  "광고",
  "금융",
  "기계",
  "휴대폰",
  "담배",
  "유통",
  "미디어",
  "바이오",
  "반도체",
  "보험",
  "석유화학",
  "섬유의류",
  "소프트웨어",
  "운수창고",
  "유틸리티",
  "은행",
  "인터넷포탈",
  "자동차",
  "전기전자",
  "제약",
  "조선",
  "종이",
  "증권",
  "철강금속",
  "타이어",
  "통신",
  "항공운송",
  "홈쇼핑",
  "음식료",
  "여행",
  "게임",
  "IT",
  "에너지",
  "해운",
  "지주회사",
  "디스플레이",
  "화장품",
  "자동차부품",
  "교육",
  "기타",
]);

// 사용자가 말하기 쉬운 이름 → 네이버 공식 업종명. 완전 일치는 따로 처리하므로 여기는 alias만.
const _INDUSTRY_ALIASES = Object.freeze({
  반도체주: "반도체",
  메모리: "반도체",
  디램: "반도체",
  파운드리: "반도체",
  "소프트에어": "소프트웨어",
  "소프트웨어/it": "소프트웨어",
  sw: "소프트웨어",
  ai: "IT",
  인공지능: "IT",
  클라우드: "IT",
  자동차산업: "자동차",
  "2차전지": "전기전자",
  이차전지: "전기전자",
  배터리: "전기전자",
  전기차: "자동차",
  디스플레이산업: "디스플레이",
  oled: "디스플레이",
  바이오시밀러: "바이오",
  제약바이오: "제약",
  금융주: "금융",
  은행주: "은행",
  증권주: "증권",
  보험주: "보험",
  카카오: "인터넷포탈",
  네이버: "인터넷포탈",
  포털: "인터넷포탈",
  플랫폼: "인터넷포탈",
  게임주: "게임",
  여행주: "여행",
  항공: "항공운송",
  항공사: "항공운송",
  조선업: "조선",
  조선주: "조선",
  철강: "철강금속",
  유틸리티주: "유틸리티",
  정유: "석유화학",
  화학: "석유화학",
  원유: "에너지",
  천연가스: "에너지",
  신재생: "에너지",
  태양광: "에너지",
  풍력: "에너지",
});

/**
 * 사용자가 입력한 업종 문자열을 네이버 공식 업종(upjong) 드롭다운 값으로 변환.
 * 정확 일치(대소문자/공백 무시) → alias 매핑 → null 순으로 해석한다.
 */
export function resolveNaverIndustry(input) {
  const raw = String(input || "").trim();
  if (!raw) return null;
  const norm = raw.replace(/\s+/g, "").toLowerCase();
  for (const label of NAVER_INDUSTRIES) {
    if (label.toLowerCase() === norm) return label;
  }
  const alias = _INDUSTRY_ALIASES[norm];
  if (alias) return alias;
  return null;
}

export const CATEGORIES = Object.freeze({
  company: {
    label: "종목분석",
    listPath: "/research/company_list.naver",
    readPath: "/research/company_read.naver",
    supportsItemCode: true,
  },
  industry: {
    label: "산업분석",
    listPath: "/research/industry_list.naver",
    readPath: "/research/industry_read.naver",
    supportsItemCode: false,
  },
  market_info: {
    label: "시황정보",
    listPath: "/research/market_info_list.naver",
    readPath: "/research/market_info_read.naver",
    supportsItemCode: false,
  },
  invest: {
    label: "투자정보",
    listPath: "/research/invest_list.naver",
    readPath: "/research/invest_read.naver",
    supportsItemCode: false,
  },
  economy: {
    label: "경제분석",
    listPath: "/research/economy_list.naver",
    readPath: "/research/economy_read.naver",
    supportsItemCode: false,
  },
  debenture: {
    label: "채권분석",
    listPath: "/research/debenture_list.naver",
    readPath: "/research/debenture_read.naver",
    supportsItemCode: false,
  },
});

function eucKrPercentEncode(value) {
  const buf = iconv.encode(String(value), "euc-kr");
  let out = "";
  for (const byte of buf) {
    out += "%" + byte.toString(16).toUpperCase().padStart(2, "0");
  }
  return out;
}

function buildQueryString(params) {
  const parts = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    parts.push(`${encodeURIComponent(k)}=${eucKrPercentEncode(v)}`);
  }
  return parts.join("&");
}

async function fetchEucKrHtml(pathname, params = {}) {
  const qs = buildQueryString(params);
  const url = `${BASE_URL}${pathname}${qs ? "?" + qs : ""}`;
  const res = await fetch(url, {
    headers: {
      "User-Agent": USER_AGENT,
      "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
      Referer: `${BASE_URL}/research/`,
    },
  });
  if (!res.ok) {
    throw new Error(
      `네이버 리서치 요청 실패 (HTTP ${res.status} ${res.statusText}) — ${url}`,
    );
  }
  const buf = Buffer.from(await res.arrayBuffer());
  const html = iconv.decode(buf, "euc-kr");
  return { $: cheerioLoad(html), url };
}

const _stockCodeCache = new Map();

/**
 * 한글/영문 종목명을 6자리 국내 종목코드로 변환.
 *
 * 네이버 Npay 증권의 모바일 자동완성 JSON API를 1차 소스로 사용한다.
 * 예) 삼성전자 → 005930, SK하이닉스 → 000660.
 * 결과는 프로세스 메모리에 캐싱한다(음수 캐시 포함).
 */
export async function resolveStockCodeByName(name) {
  const raw = String(name || "").trim();
  if (!raw) return null;
  if (/^\d{6}$/.test(raw)) return raw;

  if (_stockCodeCache.has(raw)) return _stockCodeCache.get(raw);

  try {
    const url =
      "https://m.stock.naver.com/front-api/search/autoComplete" +
      `?query=${encodeURIComponent(raw)}&target=stock`;
    const res = await fetch(url, {
      headers: {
        "User-Agent": USER_AGENT,
        Accept: "application/json",
        Referer: "https://m.stock.naver.com/",
      },
    });
    if (res.ok) {
      const json = await res.json();
      const items = json?.result?.items ?? [];
      const lower = raw.toLowerCase();
      let exact = null;
      let firstDomestic = null;
      for (const it of items) {
        const code = typeof it?.code === "string" ? it.code : "";
        const nm = String(it?.name || "");
        const nation = String(it?.nationCode || "");
        if (!/^\d{6}$/.test(code)) continue;
        if (nation && nation !== "KOR") continue;
        if (!firstDomestic) firstDomestic = code;
        if (nm.toLowerCase() === lower) {
          exact = code;
          break;
        }
      }
      const resolved = exact || firstDomestic || null;
      _stockCodeCache.set(raw, resolved);
      return resolved;
    }
  } catch {
    /* ignore */
  }

  _stockCodeCache.set(raw, null);
  return null;
}

function normalizeNaverDate(text) {
  const m = String(text || "").match(/(\d{2})\.(\d{2})\.(\d{2})/);
  if (!m) return null;
  const yy = Number(m[1]);
  const year = yy >= 80 ? 1900 + yy : 2000 + yy;
  return `${year}-${m[2]}-${m[3]}`;
}

function parseNonNegInt(text) {
  const n = parseInt(String(text || "").replace(/[^\d]/g, ""), 10);
  return Number.isFinite(n) ? n : 0;
}

function parseListRow($, $tr, category, readPath) {
  const tds = $tr.find("td");
  if (tds.length < 5 || tds.length > 7) return null;
  const $firstTd = $(tds[0]);
  if ($firstTd.attr("colspan")) return null;

  let offset = 0;
  let stock_name = null;
  let stock_code = null;
  let industry = null;

  const stockA = $firstTd.find("a.stock_item");
  if (stockA.length > 0) {
    stock_name = stockA.text().trim();
    stock_code = (stockA.attr("href") || "").match(/code=(\d{6})/)?.[1] ?? null;
    offset = 1;
  } else if (tds.length === 6) {
    industry = $firstTd.text().trim();
    offset = 1;
  }

  const titleTd = $(tds[offset]);
  const titleA = titleTd.find("a").first();
  if (!titleA.length) return null;
  const title = titleA.text().trim();
  if (!title) return null;

  const href = titleA.attr("href") || "";
  const baseForResolve = `${BASE_URL}${readPath.replace(/[^/]+$/, "")}`;
  const detail_url = new URL(href, baseForResolve).toString();
  const nid = new URL(detail_url).searchParams.get("nid");

  const broker = $(tds[offset + 1]).text().trim();
  const pdfA = $(tds[offset + 2]).find("a").first();
  const pdf_url = pdfA.attr("href") || null;
  const date = normalizeNaverDate($(tds[offset + 3]).text().trim());
  const views = parseNonNegInt($(tds[offset + 4]).text());

  return {
    category,
    stock_name,
    stock_code,
    industry,
    title,
    broker,
    date,
    views,
    nid,
    detail_url,
    pdf_url,
  };
}

export async function searchResearchReports({
  category = "company",
  query,
  from_date,
  to_date,
  broker,
  limit = 10,
} = {}) {
  const cat = CATEGORIES[category];
  if (!cat) {
    throw new Error(
      `지원하지 않는 category='${category}'. 허용: ${Object.keys(CATEGORIES).join(", ")}`,
    );
  }

  const effectiveLimit = Math.max(1, Math.min(Number(limit) || 10, 300));
  const maxPages = Math.max(1, Math.ceil(effectiveLimit / 30));

  const collected = [];

  const queryStr = query ? String(query).trim() : "";

  // company 카테고리에서 종목명이 들어오면 itemCode로 정확 매칭을 우선 시도한다.
  // (네이버 UI가 내부적으로 하는 "종목명 → 종목코드" 리졸브를 동일하게 수행)
  let resolvedItemCode = null;
  let resolvedItemName = null;
  if (queryStr && cat.supportsItemCode) {
    if (/^\d{6}$/.test(queryStr)) {
      resolvedItemCode = queryStr;
    } else {
      try {
        resolvedItemCode = await resolveStockCodeByName(queryStr);
        if (resolvedItemCode) resolvedItemName = queryStr;
      } catch {
        resolvedItemCode = null;
      }
    }
  }

  // industry 카테고리에서 업종명이 들어오면 upjong 드롭다운 값으로 정규화하여 정확 필터한다.
  const resolvedUpjong = category === "industry" ? resolveNaverIndustry(queryStr) : null;

  for (let page = 1; page <= maxPages && collected.length < effectiveLimit; page++) {
    const params = { page };

    if (resolvedItemCode) {
      params.searchType = "itemCode";
      params.itemCode = resolvedItemCode;
      if (resolvedItemName) params.itemName = resolvedItemName;
    } else if (resolvedUpjong) {
      params.searchType = "upjong";
      params.upjong = resolvedUpjong;
    } else if (queryStr) {
      params.searchType = "keyword";
      params.keyword = queryStr;
    } else if (from_date) {
      params.searchType = "writeDate";
      params.writeFromDate = from_date;
      params.writeToDate = to_date || from_date;
    }

    const { $ } = await fetchEucKrHtml(cat.listPath, params);

    let pageRows = 0;
    const trs = $("table.type_1 tr").toArray();
    for (const tr of trs) {
      if (collected.length >= effectiveLimit) break;
      const row = parseListRow($, $(tr), category, cat.readPath);
      if (!row) continue;
      if (broker && !row.broker.includes(broker)) continue;
      collected.push(row);
      pageRows++;
    }

    if (pageRows === 0) break;
  }

  return collected;
}

function sanitizeFilename(name) {
  const trimmed = String(name || "").trim();
  const cleaned = trimmed.replace(/[\\/:*?"<>|]+/g, "_").replace(/\s+/g, "_");
  return cleaned || `report_${Date.now()}.pdf`;
}

function sanitizeTextFilename(name) {
  const base = sanitizeFilename(String(name || "").replace(/\.txt$/i, ""));
  const stem = base.endsWith(".pdf") ? base.slice(0, -4) : base;
  return `${stem || `report_${Date.now()}`}.txt`;
}

function normalizeExtractedText(raw) {
  return String(raw || "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/[\t\f\v]+/g, " ")
    .replace(/[ \u00a0]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function assertPdfBufferSize(buf, label) {
  if (!Buffer.isBuffer(buf) || buf.length === 0) {
    throw new Error(`${label}: 빈 PDF 버퍼입니다.`);
  }
  if (buf.length > MAX_PDF_BYTES) {
    throw new Error(
      `${label}: PDF가 너무 큽니다 (${buf.length} bytes > ${MAX_PDF_BYTES}).`,
    );
  }
  const head = buf.subarray(0, 5).toString("ascii");
  if (head !== "%PDF-") {
    throw new Error(`${label}: PDF 시그니처가 아닙니다 (%PDF-).`);
  }
}

export async function extractTextFromPdfBuffer(buf) {
  assertPdfBufferSize(buf, "extractTextFromPdfBuffer");
  const pdfParse = loadPdfParse();
  const data = await pdfParse(buf);
  const text = normalizeExtractedText(data.text || "");
  return {
    text,
    pages: data.numpages ?? 0,
    character_count: text.length,
  };
}

async function fetchPdfBufferFromUrl(pdf_url) {
  if (!pdf_url || !/^https?:\/\//.test(String(pdf_url))) {
    throw new Error("유효한 pdf_url이 필요합니다 (http/https).");
  }
  const res = await fetch(pdf_url, {
    headers: {
      "User-Agent": USER_AGENT,
      Referer: `${BASE_URL}/research/`,
    },
  });
  if (!res.ok) {
    throw new Error(`PDF 다운로드 실패 (HTTP ${res.status} ${res.statusText}) — ${pdf_url}`);
  }
  const buf = Buffer.from(await res.arrayBuffer());
  assertPdfBufferSize(buf, "fetchPdfBufferFromUrl");
  return buf;
}

/**
 * PDF에서 텍스트만 추출해 UTF-8 .txt 파일로 저장합니다.
 * @param {{ pdf_url?: string, pdf_path?: string, save_path?: string, save_dir?: string, text_filename?: string }} opts
 */
export async function extractResearchPdfText({
  pdf_url,
  pdf_path,
  save_path,
  save_dir,
  text_filename,
} = {}) {
  const hasUrl = Boolean(pdf_url && String(pdf_url).trim());
  const hasPath = Boolean(pdf_path && String(pdf_path).trim());
  if (hasUrl === hasPath) {
    throw new Error("pdf_url 또는 pdf_path 중 정확히 하나를 지정하세요.");
  }

  let buf;
  let defaultStem;
  if (hasPath) {
    const resolved = path.resolve(String(pdf_path).trim());
    buf = await fs.readFile(resolved);
    assertPdfBufferSize(buf, "extractResearchPdfText");
    defaultStem = path.basename(resolved, path.extname(resolved));
  } else {
    buf = await fetchPdfBufferFromUrl(String(pdf_url).trim());
    try {
      defaultStem = path.basename(new URL(String(pdf_url).trim()).pathname, ".pdf");
    } catch {
      defaultStem = `report_${Date.now()}`;
    }
  }

  const { text, pages, character_count } = await extractTextFromPdfBuffer(buf);
  const outPath = save_path
    ? path.resolve(String(save_path).trim())
    : path.resolve(
        save_dir || defaultDownloadDir(),
        sanitizeTextFilename(text_filename || `${defaultStem}.txt`),
      );

  await fs.mkdir(path.dirname(outPath), { recursive: true });
  await fs.writeFile(outPath, text, "utf8");

  return {
    text_path: outPath,
    pages,
    character_count,
    preview: text.slice(0, 500),
    saved_at: new Date().toISOString(),
  };
}

function defaultDownloadDir() {
  return (
    process.env.RESEARCH_DOWNLOAD_DIR ||
    path.resolve(process.cwd(), "downloads")
  );
}

/**
 * 한 번의 리서치 파이프라인 호출마다 parent 아래에 고유 하위 폴더를 만들고 그 경로를 반환한다.
 * @param {string | undefined} saveDirOpt 미지정이면 {@link defaultDownloadDir}
 */
async function createSessionDownloadDir(saveDirOpt) {
  const parent = saveDirOpt
    ? path.resolve(String(saveDirOpt).trim())
    : defaultDownloadDir();
  await fs.mkdir(parent, { recursive: true });
  const sessionName = `run_${new Date().toISOString().replace(/[:.]/g, "-")}_${randomBytes(4).toString("hex")}`;
  const sessionDir = path.join(parent, sessionName);
  await fs.mkdir(sessionDir, { recursive: true });
  return sessionDir;
}

export async function downloadResearchPdf({
  pdf_url,
  save_dir,
  filename,
  also_extract_text = false,
} = {}) {
  const buf = await fetchPdfBufferFromUrl(pdf_url);

  const targetDir = save_dir || defaultDownloadDir();
  await fs.mkdir(targetDir, { recursive: true });

  const derivedName = (() => {
    try {
      return path.basename(new URL(pdf_url).pathname);
    } catch {
      return "";
    }
  })();
  const finalName = sanitizeFilename(filename || derivedName || `report_${Date.now()}.pdf`);
  const fullPath = path.resolve(targetDir, finalName);

  await fs.writeFile(fullPath, buf);

  let text_extract = null;
  if (also_extract_text) {
    const { text, pages, character_count } = await extractTextFromPdfBuffer(buf);
    const textPath = fullPath.replace(/\.pdf$/i, ".txt");
    await fs.writeFile(textPath, text, "utf8");
    text_extract = {
      path: textPath,
      pages,
      character_count,
      preview: text.slice(0, 400),
    };
  }

  return {
    url: pdf_url,
    path: fullPath,
    size_bytes: buf.length,
    saved_at: new Date().toISOString(),
    text_extract,
  };
}

export async function searchAndDownloadResearchReports(options = {}) {
  const { also_extract_text = false, ...searchOpts } = options;
  const reports = await searchResearchReports(searchOpts);
  const saveDir = options.save_dir || defaultDownloadDir();

  const downloads = [];
  for (const r of reports) {
    if (!r.pdf_url) {
      downloads.push({ ...r, download: null, skipped_reason: "pdf_url 없음" });
      continue;
    }
    try {
      const niceName = sanitizeFilename(
        `${r.date || "unknown"}__${r.broker || "broker"}__${r.title || "untitled"}`.slice(0, 120) +
          ".pdf",
      );
      const result = await downloadResearchPdf({
        pdf_url: r.pdf_url,
        save_dir: saveDir,
        filename: niceName,
        also_extract_text,
      });
      downloads.push({ ...r, download: result });
    } catch (err) {
      downloads.push({
        ...r,
        download: null,
        download_error: err instanceof Error ? err.message : String(err),
      });
    }
  }

  return { save_dir: saveDir, count: downloads.length, items: downloads };
}

/**
 * 리서치 리포트 종합 파이프라인: 검색 → PDF 다운로드 → 텍스트 추출 → 에이전트로 전달.
 * 단일 호출로 category/query에 맞는 리포트 목록과 각 리포트의 본문 텍스트(필요 시 절삭)를 반환합니다.
 *
 * @param {{
 *   category: string,
 *   query?: string,
 *   from_date?: string,
 *   to_date?: string,
 *   broker?: string,
 *   limit?: number,
 *   save_dir?: string,
 *   chars_per_report?: number,
 *   max_text_reports?: number,
 * }} opts `save_dir`가 있으면 그 디렉터리를 상위로 쓰고, 매 호출마다 그 아래 새 `run_*` 폴더에 PDF/TXT를 저장한다.
 */
export async function fetchResearchReportsWithText(opts = {}) {
  const {
    chars_per_report = 4000,
    max_text_reports = 5,
    save_dir: saveDirOpt,
    ...rest
  } = opts;

  const sessionDir = await createSessionDownloadDir(saveDirOpt);

  const bundle = await searchAndDownloadResearchReports({
    ...rest,
    also_extract_text: true,
    save_dir: sessionDir,
  });

  const reports = [];
  let textsAttached = 0;
  for (const item of bundle.items || []) {
    const base = {
      nid: item.nid ?? null,
      category: item.category ?? null,
      stock_name: item.stock_name ?? null,
      stock_code: item.stock_code ?? null,
      industry: item.industry ?? null,
      title: item.title ?? null,
      broker: item.broker ?? null,
      date: item.date ?? null,
      views: item.views ?? null,
      detail_url: item.detail_url ?? null,
      pdf_url: item.pdf_url ?? null,
    };
    const download = item.download || null;
    const textPath = download?.text_extract?.path || null;
    const characterCount = download?.text_extract?.character_count ?? null;
    const pages = download?.text_extract?.pages ?? null;

    let text = null;
    let truncated = false;
    if (textPath && textsAttached < max_text_reports) {
      try {
        const raw = await fs.readFile(textPath, "utf8");
        if (chars_per_report && raw.length > chars_per_report) {
          text = raw.slice(0, chars_per_report);
          truncated = true;
        } else {
          text = raw;
        }
        textsAttached += 1;
      } catch (err) {
        base.text_error = err instanceof Error ? err.message : String(err);
      }
    }

    reports.push({
      ...base,
      pdf_path: download?.path ?? null,
      text_path: textPath,
      pages,
      character_count: characterCount,
      text,
      text_truncated: truncated,
      skipped_reason: item.skipped_reason ?? null,
      download_error: item.download_error ?? null,
    });
  }

  return {
    category: opts.category ?? null,
    query: opts.query ?? null,
    save_dir: bundle.save_dir,
    count: reports.length,
    text_attached: textsAttached,
    chars_per_report,
    reports,
  };
}
