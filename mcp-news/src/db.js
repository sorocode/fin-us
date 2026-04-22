import Database from "better-sqlite3";
import path from "node:path";
import fs from "node:fs";

let db = null;

export function defaultDownloadDir() {
  return (
    process.env.RESEARCH_DOWNLOAD_DIR ||
    path.resolve(process.cwd(), "downloads")
  );
}

function defaultDbPath() {
  return (
    process.env.RESEARCH_DB_PATH ||
    path.join(defaultDownloadDir(), "index.sqlite3")
  );
}

export function getDb() {
  if (db) return db;
  const dbPath = defaultDbPath();
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  db = new Database(dbPath);
  db.pragma("journal_mode = WAL");
  db.pragma("synchronous = NORMAL");

  db.exec(`
    CREATE TABLE IF NOT EXISTS reports (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      nid             TEXT,
      category        TEXT,
      stock_name      TEXT,
      stock_code      TEXT,
      industry        TEXT,
      title           TEXT,
      broker          TEXT,
      date            TEXT,          -- YYYY-MM-DD
      date_ts         INTEGER,       -- epoch ms
      views           INTEGER,
      detail_url      TEXT,
      pdf_url         TEXT,
      pdf_path        TEXT UNIQUE,
      text_path       TEXT UNIQUE,
      pages           INTEGER,
      character_count INTEGER,
      text            TEXT,
      indexed_at      INTEGER
    );
    CREATE UNIQUE INDEX IF NOT EXISTS uq_reports_nid ON reports(nid) WHERE nid IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_reports_code ON reports(stock_code);
    CREATE INDEX IF NOT EXISTS idx_reports_cat_date ON reports(category, date_ts DESC);
    CREATE INDEX IF NOT EXISTS idx_reports_broker ON reports(broker);
    CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(date_ts DESC);
  `);

  const hasFts = db
    .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='reports_fts'")
    .get();

  if (!hasFts) {
    try {
      db.exec(`
        CREATE VIRTUAL TABLE reports_fts USING fts5(
          title,
          broker,
          stock_name,
          text,
          tokenize='unicode61'
        );
        CREATE TRIGGER reports_ai AFTER INSERT ON reports BEGIN
          INSERT INTO reports_fts(rowid, title, broker, stock_name, text)
          VALUES (new.id,
                  COALESCE(new.title,''),
                  COALESCE(new.broker,''),
                  COALESCE(new.stock_name,''),
                  COALESCE(new.text,''));
        END;
        CREATE TRIGGER reports_ad AFTER DELETE ON reports BEGIN
          DELETE FROM reports_fts WHERE rowid = old.id;
        END;
        CREATE TRIGGER reports_au AFTER UPDATE ON reports BEGIN
          DELETE FROM reports_fts WHERE rowid = old.id;
          INSERT INTO reports_fts(rowid, title, broker, stock_name, text)
          VALUES (new.id,
                  COALESCE(new.title,''),
                  COALESCE(new.broker,''),
                  COALESCE(new.stock_name,''),
                  COALESCE(new.text,''));
        END;
      `);
    } catch (err) {
      console.error("[db] FTS5 테이블 생성 실패:", err?.message || err);
    }
  }

  return db;
}

export function closeDb() {
  if (db) {
    db.close();
    db = null;
  }
}

const ALL_FIELDS = [
  "nid",
  "category",
  "stock_name",
  "stock_code",
  "industry",
  "title",
  "broker",
  "date",
  "date_ts",
  "views",
  "detail_url",
  "pdf_url",
  "pdf_path",
  "text_path",
  "pages",
  "character_count",
  "text",
];

/**
 * 하나의 리포트 행을 upsert.
 *  - 동일성 판단: nid / pdf_path / text_path 중 하나라도 일치하면 기존 행 업데이트
 *  - UPDATE 시에는 COALESCE로 non-null 필드만 병합 (여러 단계에 걸쳐 메타가 보강되는 flow 지원)
 * 반환: { id, inserted: boolean }
 */
export function upsertReport(input) {
  const d = getDb();
  const row = { ...input };

  if (!row.date_ts && row.date && /^\d{4}-\d{2}-\d{2}$/.test(row.date)) {
    row.date_ts = new Date(row.date + "T00:00:00Z").getTime();
  }

  const findStmt = d.prepare(`
    SELECT id FROM reports
    WHERE (@nid IS NOT NULL AND @nid != '' AND nid = @nid)
       OR (@pdf_path IS NOT NULL AND @pdf_path != '' AND pdf_path = @pdf_path)
       OR (@text_path IS NOT NULL AND @text_path != '' AND text_path = @text_path)
    LIMIT 1
  `);

  const existing = findStmt.get({
    nid: row.nid || "",
    pdf_path: row.pdf_path || "",
    text_path: row.text_path || "",
  });

  const now = Date.now();

  if (existing) {
    const sets = ALL_FIELDS.map((f) => `${f} = COALESCE(@${f}, ${f})`).join(", ");
    const params = { id: existing.id, now };
    for (const f of ALL_FIELDS) params[f] = row[f] ?? null;
    d.prepare(
      `UPDATE reports SET ${sets}, indexed_at = @now WHERE id = @id`
    ).run(params);
    return { id: existing.id, inserted: false };
  }

  const cols = ALL_FIELDS.join(", ");
  const vals = ALL_FIELDS.map((f) => `@${f}`).join(", ");
  const params = { now };
  for (const f of ALL_FIELDS) params[f] = row[f] ?? null;
  const info = d
    .prepare(
      `INSERT INTO reports (${cols}, indexed_at) VALUES (${vals}, @now)`
    )
    .run(params);
  return { id: info.lastInsertRowid, inserted: true };
}

export function getReport({ id, nid, pdf_path, text_path }) {
  const d = getDb();
  let sql = "SELECT * FROM reports WHERE ";
  const params = {};
  if (id != null) {
    sql += "id = @id";
    params.id = id;
  } else if (nid) {
    sql += "nid = @nid";
    params.nid = nid;
  } else if (pdf_path) {
    sql += "pdf_path = @pdf_path";
    params.pdf_path = pdf_path;
  } else if (text_path) {
    sql += "text_path = @text_path";
    params.text_path = text_path;
  } else {
    throw new Error("id / nid / pdf_path / text_path 중 하나 필요");
  }
  sql += " LIMIT 1";
  return d.prepare(sql).get(params) || null;
}

/**
 * FTS5 기반 빠른 검색 (title, broker, stock_name, text 대상).
 * FTS 결과가 비면 title/stock_name/text에 대한 LIKE 폴백 (한글 부분 검색 보정).
 */
export function searchReports({ query, category, stock_code, broker, limit = 20 }) {
  if (!query || !query.trim()) return [];
  const d = getDb();

  const where = [];
  const params = { q: query.trim(), limit: Math.min(Math.max(1, limit), 500) };
  if (category) {
    where.push("r.category = @category");
    params.category = category;
  }
  if (stock_code) {
    where.push("r.stock_code = @stock_code");
    params.stock_code = stock_code;
  }
  if (broker) {
    where.push("r.broker LIKE @broker_pat");
    params.broker_pat = `%${broker}%`;
  }
  const extraWhere = where.length ? "AND " + where.join(" AND ") : "";

  const ftsSql = `
    SELECT r.id, r.nid, r.category, r.stock_name, r.stock_code, r.industry,
           r.title, r.broker, r.date, r.views,
           r.pdf_path, r.text_path, r.character_count,
           snippet(reports_fts, 3, '⟨', '⟩', '…', 15) AS text_snippet,
           snippet(reports_fts, 0, '⟨', '⟩', '…', 10) AS title_snippet,
           bm25(reports_fts) AS rank
      FROM reports_fts
      JOIN reports r ON r.id = reports_fts.rowid
     WHERE reports_fts MATCH @q ${extraWhere}
     ORDER BY rank ASC
     LIMIT @limit
  `;

  try {
    const rows = d.prepare(ftsSql).all(params);
    if (rows.length > 0) return rows.map(formatRow);
  } catch (err) {
    console.error("[db] FTS 쿼리 실패, LIKE 폴백:", err?.message || err);
  }

  // LIKE 폴백
  const likeWhere = ["(r.title LIKE @pat OR r.stock_name LIKE @pat OR r.text LIKE @pat OR r.broker LIKE @pat)"];
  if (category) likeWhere.push("r.category = @category");
  if (stock_code) likeWhere.push("r.stock_code = @stock_code");
  if (broker) likeWhere.push("r.broker LIKE @broker_pat");
  const likeParams = { ...params, pat: `%${query.trim()}%` };
  const likeSql = `
    SELECT r.id, r.nid, r.category, r.stock_name, r.stock_code, r.industry,
           r.title, r.broker, r.date, r.views,
           r.pdf_path, r.text_path, r.character_count,
           substr(r.text, 1, 200) AS text_snippet,
           r.title AS title_snippet,
           NULL AS rank
      FROM reports r
     WHERE ${likeWhere.join(" AND ")}
     ORDER BY r.date_ts DESC NULLS LAST, r.id DESC
     LIMIT @limit
  `;
  const likeRows = d.prepare(likeSql).all(likeParams);
  return likeRows.map((r) => ({ ...formatRow(r), matched_by: "like" }));
}

/** 구조화된 복합 조회 (query는 선택 — 있으면 FTS 결합). */
export function queryReports({
  query,
  category,
  stock_code,
  stock_name,
  broker,
  nid,
  from_date,
  to_date,
  has_text,
  limit = 50,
  offset = 0,
  order_by = "date_desc",
} = {}) {
  const d = getDb();
  const where = [];
  const params = {
    limit: Math.min(Math.max(1, Number(limit) || 50), 500),
    offset: Math.max(0, Number(offset) || 0),
  };

  if (category) {
    where.push("r.category = @category");
    params.category = category;
  }
  if (stock_code) {
    where.push("r.stock_code = @stock_code");
    params.stock_code = stock_code;
  }
  if (stock_name) {
    where.push("r.stock_name LIKE @stock_name_pat");
    params.stock_name_pat = `%${stock_name}%`;
  }
  if (broker) {
    where.push("r.broker LIKE @broker_pat");
    params.broker_pat = `%${broker}%`;
  }
  if (nid) {
    where.push("r.nid = @nid");
    params.nid = nid;
  }
  if (from_date) {
    where.push("r.date_ts >= @from_ts");
    params.from_ts = new Date(from_date + "T00:00:00Z").getTime();
  }
  if (to_date) {
    where.push("r.date_ts <= @to_ts");
    params.to_ts = new Date(to_date + "T23:59:59Z").getTime();
  }
  if (has_text === true) where.push("r.text IS NOT NULL AND length(r.text) > 0");
  if (has_text === false) where.push("(r.text IS NULL OR length(r.text) = 0)");

  let sql;
  if (query && query.trim()) {
    params.q = query.trim();
    const wc = where.length ? "AND " + where.join(" AND ") : "";
    sql = `
      SELECT r.id, r.nid, r.category, r.stock_name, r.stock_code, r.industry,
             r.title, r.broker, r.date, r.views,
             r.pdf_path, r.text_path, r.character_count,
             snippet(reports_fts, 3, '⟨', '⟩', '…', 15) AS text_snippet,
             bm25(reports_fts) AS rank
        FROM reports_fts
        JOIN reports r ON r.id = reports_fts.rowid
       WHERE reports_fts MATCH @q ${wc}
       ORDER BY ${order_by === "rank" ? "rank ASC" : "r.date_ts DESC"}
       LIMIT @limit OFFSET @offset
    `;
  } else {
    const wc = where.length ? "WHERE " + where.join(" AND ") : "";
    sql = `
      SELECT r.id, r.nid, r.category, r.stock_name, r.stock_code, r.industry,
             r.title, r.broker, r.date, r.views,
             r.pdf_path, r.text_path, r.character_count,
             substr(r.text, 1, 200) AS text_snippet,
             NULL AS rank
        FROM reports r
        ${wc}
        ORDER BY r.date_ts DESC NULLS LAST, r.id DESC
        LIMIT @limit OFFSET @offset
    `;
  }
  const rows = d.prepare(sql).all(params);
  return rows.map(formatRow);
}

function formatRow(r) {
  return {
    id: r.id,
    nid: r.nid,
    category: r.category,
    stock_name: r.stock_name,
    stock_code: r.stock_code,
    industry: r.industry,
    title: r.title,
    broker: r.broker,
    date: r.date,
    views: r.views,
    pdf_path: r.pdf_path,
    text_path: r.text_path,
    character_count: r.character_count,
    title_snippet: r.title_snippet,
    text_snippet: r.text_snippet,
    rank: r.rank,
  };
}

export function reportsStats() {
  const d = getDb();
  const total = d.prepare("SELECT COUNT(*) AS n FROM reports").get().n;
  const withText = d
    .prepare(
      "SELECT COUNT(*) AS n FROM reports WHERE text IS NOT NULL AND length(text) > 0"
    )
    .get().n;
  const withPdf = d
    .prepare("SELECT COUNT(*) AS n FROM reports WHERE pdf_path IS NOT NULL")
    .get().n;
  const byCategory = d
    .prepare(
      "SELECT category, COUNT(*) AS n FROM reports GROUP BY category ORDER BY n DESC"
    )
    .all();
  const byBroker = d
    .prepare(
      "SELECT broker, COUNT(*) AS n FROM reports WHERE broker IS NOT NULL GROUP BY broker ORDER BY n DESC LIMIT 20"
    )
    .all();
  const range = d
    .prepare(
      "SELECT MIN(date_ts) AS min_ts, MAX(date_ts) AS max_ts FROM reports WHERE date_ts IS NOT NULL"
    )
    .get();
  return {
    db_path: defaultDbPath(),
    total,
    with_text: withText,
    with_pdf: withPdf,
    by_category: byCategory,
    top_brokers: byBroker,
    oldest_date: range?.min_ts ? new Date(range.min_ts).toISOString().slice(0, 10) : null,
    newest_date: range?.max_ts ? new Date(range.max_ts).toISOString().slice(0, 10) : null,
  };
}

/**
 * downloads/ 폴더의 기존 PDF/TXT 파일을 스캔해 DB에 일괄 등록.
 *  - 파일명이 'YYYY-MM-DD__broker__title.pdf' 형식이면 메타 추정
 *  - 같은 basename의 .txt가 있으면 함께 인덱싱
 *  - DB에 누락된 텍스트(.pdf만 있고 text 없는 항목)에 대해선 기존 .txt 읽어 업데이트
 * 제거(pruneMissing=true): DB에 등록됐지만 파일이 사라진 행 제거
 */
export function reindexDownloads({ dir, pruneMissing = true } = {}) {
  const d = getDb();
  const target = dir
    ? path.isAbsolute(dir)
      ? dir
      : path.resolve(process.cwd(), dir)
    : defaultDownloadDir();
  if (!fs.existsSync(target)) {
    return { dir: target, scanned: 0, inserted: 0, updated: 0, pruned: 0, note: "디렉터리 없음" };
  }

  let scanned = 0;
  let inserted = 0;
  let updated = 0;

  const entries = fs.readdirSync(target);
  const txtSet = new Set(entries.filter((f) => f.toLowerCase().endsWith(".txt")));

  for (const f of entries) {
    if (!f.toLowerCase().endsWith(".pdf")) continue;
    scanned += 1;
    const pdfPath = path.join(target, f);

    const stem = f.replace(/\.pdf$/i, "");
    const parts = stem.split("__");
    let date = null;
    let broker = null;
    let title = stem;
    if (parts.length >= 3 && /^\d{4}-\d{2}-\d{2}$/.test(parts[0])) {
      date = parts[0];
      broker = parts[1];
      title = parts.slice(2).join("__");
    }

    const txtName = stem + ".txt";
    let text = null;
    let textPath = null;
    let characterCount = null;
    if (txtSet.has(txtName)) {
      textPath = path.join(target, txtName);
      try {
        text = fs.readFileSync(textPath, "utf-8");
        characterCount = text.length;
      } catch {
        text = null;
      }
    }

    const r = upsertReport({
      title,
      broker,
      date,
      pdf_path: pdfPath,
      text_path: textPath,
      text,
      character_count: characterCount,
    });
    if (r.inserted) inserted += 1;
    else updated += 1;
  }

  // .txt만 있고 .pdf가 없는 경우도 인덱싱
  for (const f of entries) {
    if (!f.toLowerCase().endsWith(".txt")) continue;
    const stem = f.replace(/\.txt$/i, "");
    const pdfTwin = stem + ".pdf";
    if (entries.includes(pdfTwin)) continue; // 이미 위에서 처리
    scanned += 1;
    const txtPath = path.join(target, f);
    let text = null;
    try {
      text = fs.readFileSync(txtPath, "utf-8");
    } catch {
      continue;
    }
    const parts = stem.split("__");
    let date = null;
    let broker = null;
    let title = stem;
    if (parts.length >= 3 && /^\d{4}-\d{2}-\d{2}$/.test(parts[0])) {
      date = parts[0];
      broker = parts[1];
      title = parts.slice(2).join("__");
    }
    const r = upsertReport({
      title,
      broker,
      date,
      text_path: txtPath,
      text,
      character_count: text.length,
    });
    if (r.inserted) inserted += 1;
    else updated += 1;
  }

  let pruned = 0;
  if (pruneMissing) {
    const rows = d
      .prepare("SELECT id, pdf_path, text_path FROM reports")
      .all();
    const del = d.prepare("DELETE FROM reports WHERE id = ?");
    const tx = d.transaction((items) => {
      for (const row of items) {
        // 메타 전용 행(경로가 아예 없는 항목)은 prune 대상이 아님 —
        // searchResearchReports로 기록한 "아직 다운로드 안 한 리포트" 목록 보존.
        const hadAnyPath = Boolean(row.pdf_path) || Boolean(row.text_path);
        if (!hadAnyPath) continue;
        const pdfMissing = !row.pdf_path || !fs.existsSync(row.pdf_path);
        const txtMissing = !row.text_path || !fs.existsSync(row.text_path);
        if (pdfMissing && txtMissing) {
          del.run(row.id);
          pruned += 1;
        }
      }
    });
    tx(rows);
  }

  return { dir: target, scanned, inserted, updated, pruned };
}
