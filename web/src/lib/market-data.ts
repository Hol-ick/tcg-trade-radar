import type { MarketIntent, MarketQuality, MarketRow } from "./types"

export type MarketDataset = {
  name: string
  rows: MarketRow[]
  headers: string[]
  loadedAt: string
}

const SELL_SIGNALS = /판매|팔아요|팝니다|파는|파는데|판매중|ㅍㅍ|ㅍㅇ|sell|selling/i
const BUY_SIGNALS = /구매|구합니다|삽니다|찾습니다|구해요|매입|buy|wanted/i
const TRADE_SIGNALS = /교환|트레이드|교환합니다|trade/i

export function parseMarketCsv(text: string, name: string): MarketDataset {
  const records = parseCsvRecords(text)
  const headers = records[0] || []
  const rows = records.slice(1).map((values, index) => {
    const record = Object.fromEntries(headers.map((header, column) => [header.trim(), values[column] ?? ""]))
    return normalizeMarketRow(record, `${name}-${index}`)
  }).filter((row): row is MarketRow => Boolean(row))
  return { name, rows, headers, loadedAt: new Date().toISOString() }
}

export function parseMarketRows(records: Record<string, string>[], name: string): MarketDataset {
  const headers = records.length ? Object.keys(records[0]) : []
  const rows = records.map((record, index) => normalizeMarketRow(record, `${name}-${index}`)).filter((row): row is MarketRow => Boolean(row))
  return { name, rows, headers, loadedAt: new Date().toISOString() }
}

export function datasetUrl(fileName: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/") ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`
  return `${base}data/analysis/${encodeURIComponent(fileName)}`
}

export function normalizeCardName(value: string): string {
  return value
    .replace(/\b(?:sell|buy|trade|wanted)\b/gi, " ")
    .replace(/(?:장당|매당|개당|통당|한장|준등포|준등기|택포|택배포함|배송비 포함|직거래)/g, " ")
    .replace(/\d[\d,.]*\s*(?:만원|만|원)?/g, " ")
    .replace(/[()[\]{}\\/:,;|]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

function normalizeMarketRow(record: Record<string, string>, id: string): MarketRow | null {
  const cardName = first(record, "card_name", "card_name_raw", "card", "name") || normalizeCardName(first(record, "raw_line", "post_title"))
  const title = first(record, "post_title", "title")
  const rawLine = first(record, "raw_line")
  const postedAt = first(record, "posted_at", "date", "created_at")
  const dateKey = postedAt.slice(0, 10)
  const priceKrw = positiveNumber(first(record, "price_krw_observed", "price_krw", "buy_price_krw"))
  const quantity = Math.max(1, Math.round(positiveNumber(first(record, "quantity")) || 1))
  const listingType = normalizeIntent(first(record, "listing_type"), `${title} ${rawLine}`)
  const reviewStatus = first(record, "review_status", "status") || "unknown"
  const quality = normalizeQuality(first(record, "analysis_status"), reviewStatus, priceKrw)
  const priceStatus = normalizePriceStatus(first(record, "price_status"), first(record, "price_unit"), priceKrw)
  const priceScope = normalizePriceScope(first(record, "price_scope"), quantity, rawLine)
  const cardKey = normalizeCardName(cardName).toLocaleLowerCase("ko-KR") || cardName.trim().toLocaleLowerCase("ko-KR")
  if (!cardKey && !title) return null
  return {
    id: first(record, "row_id", "id") || id,
    galleryId: first(record, "gallery_id", "game_id"),
    cardName: cardName || "이름 미확인",
    cardKey,
    sellerName: first(record, "seller_name", "seller_display_name", "author_name") || "판매자 미상",
    listingType,
    priceKrw,
    quantity,
    dateKey: /^\d{4}-\d{2}-\d{2}$/.test(dateKey) ? dateKey : "",
    postedAt,
    title: title || "제목 없음",
    rawLine: rawLine || cardName,
    postUrl: first(record, "post_url", "source_url"),
    reviewStatus,
    quality,
    priceStatus,
    priceScope,
  }
}

function first(record: Record<string, string>, ...keys: string[]): string {
  for (const key of keys) {
    const value = String(record[key] ?? "").trim()
    if (value) return value
  }
  return ""
}

function positiveNumber(value: string): number | null {
  const parsed = Number(String(value).replaceAll(",", "").replace(/원$/, "").trim())
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function normalizeIntent(value: string, context: string): MarketIntent {
  const normalized = value.trim().toLowerCase()
  if (normalized === "sell" || normalized === "buy" || normalized === "trade") return normalized
  if (BUY_SIGNALS.test(context)) return "buy"
  if (TRADE_SIGNALS.test(context)) return "trade"
  if (SELL_SIGNALS.test(context)) return "sell"
  return "unknown"
}

function normalizeQuality(value: string, reviewStatus: string, price: number | null): MarketQuality {
  if (["usable", "needs_review", "context_only", "excluded"].includes(value)) return value as MarketQuality
  if (reviewStatus === "rejected") return "excluded"
  if (reviewStatus === "needs_review" || price == null) return "needs_review"
  return "usable"
}

function normalizePriceStatus(value: string, unit: string, price: number | null): MarketRow["priceStatus"] {
  if (["exact", "estimated", "missing", "removed", "unknown"].includes(value)) return value as MarketRow["priceStatus"]
  if (price == null) return "missing"
  return /추정|단위|만원|만/.test(unit) ? "estimated" : "exact"
}

function normalizePriceScope(value: string, quantity: number, rawLine: string): MarketRow["priceScope"] {
  if (["per_card", "per_quantity", "bundle", "unknown"].includes(value)) return value as MarketRow["priceScope"]
  if (/[+,/&]/.test(rawLine)) return "bundle"
  if (quantity > 1 && !/장당|매당|개당/.test(rawLine)) return "per_quantity"
  return "per_card"
}

function parseCsvRecords(text: string): string[][] {
  const records: string[][] = []
  let row: string[] = []
  let field = ""
  let quoted = false
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index]
    const next = text[index + 1]
    if (character === '"') {
      if (quoted && next === '"') { field += '"'; index += 1 } else quoted = !quoted
    } else if (character === "," && !quoted) {
      row.push(field); field = ""
    } else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && next === "\n") index += 1
      row.push(field); field = ""
      if (row.some((value) => value.trim())) records.push(row)
      row = []
    } else field += character
  }
  if (field || row.length) {
    row.push(field)
    if (row.some((value) => value.trim())) records.push(row)
  }
  return records
}
