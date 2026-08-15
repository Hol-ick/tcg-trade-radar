import type { MarketIntent, MarketQuality, MarketRow } from "./types"

export type MarketDataset = {
  name: string
  rows: MarketRow[]
  headers: string[]
  loadedAt: string
}

export type MarketCatalogEntry = {
  path: string
  gameId: string
  gameName: string
  yearMonth: string
  listingType: string
  listingTypeLabel: string
  rows: number
  bytes: number
  priceCandidateRows: number
  strictPriceRows: number
  minPostedAt: string
  maxPostedAt: string
}

export const MARKET_CATALOG_ID = "market-20260814"

const SELL_SIGNALS = /판매|팔아요|팝니다|파는|파는데|판매중|ㅍㅍ|ㅍㅇ|sell|selling/i
const BUY_SIGNALS = /구매|구합니다|삽니다|찾습니다|구해요|매입|buy|wanted/i
const TRADE_SIGNALS = /교환|트레이드|교환합니다|trade/i
const TRADE_WORDS = /(?:\b(?:sell|buy|trade|wanted|selling|buying)\b|판매합니다|판매|팝니다|팜|삽니다|구매합니다|구매|구합니다|구해요|구함|찾습니다|찾아요|찾음|교환합니다|교환|파는\s*사람|사는\s*사람)/gi
const QUANTITY_NOISE = /(?<![A-Za-z가-힣])\d+\s*(?:장|매|개|통|세트)(?:분)?(?![A-Za-z가-힣])/gi
const PER_UNIT_NOISE = /(?:장|매|개|통)\s*당(?![A-Za-z가-힣])|한\s*장(?![A-Za-z가-힣])/gi
const PRICE_NOISE = /(?<![A-Za-z가-힣0-9.-])\d[\d,]*(?:\.\d+)?\s*(?:원|만원|만)?(?=$|[^A-Za-z가-힣0-9])/gi
const SHIPPING_NOISE = /(?:준등포|준등기|등포|등기|택포|택배포함|배송비\s*포함|직거래)/gi
const ARTIFACT_CARD_TEXT = /(?:https?:\/\/|javascript\s*:|<\/?script\b|loadscript\b|adsbygoogle|googlesyndication|(?:window|document)\s*[.[]|queryselector\s*\(|appendchild\s*\(|\b(?:var|const|let)\s+\w+\s*=|function\s*\(|DOM\s*삽입|스크립트|광고\s*삽입)/i
const NON_CARD_LABEL = /^(?:(?:\d+\s*)?(?:장|매|개|통)(?:분)?|한\s*장|(?:장|매|개|통)\s*당|준등포|준등기|등포|등기|택포|반택포|편택포|배송|배송비|가격|합계|총액|일괄\s*(?:시|판매|구매)?|구매|판매|교환|\d+(?:[.,]\d+)?(?:\s+\d+(?:[.,]\d+)?)+|(?:준등포|준등기|등포|등기|택포|배송|배송비|가격|합계|총액|일괄)\s*\d+(?:[.,]\d+)?\s*(?:원|만원|만|천)?)$/i

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
  const path = fileName.split("/").map((segment) => encodeURIComponent(segment)).join("/")
  return `${base}data/analysis/${path}`
}

export function marketCatalogUrl(): string {
  return datasetUrl(`${MARKET_CATALOG_ID}/index/partitions.csv`)
}

export function parsePartitionCatalog(text: string): MarketCatalogEntry[] {
  const records = parseCsvRecords(text)
  const headers = records[0] || []
  return records.slice(1).map((values) => {
    const record = Object.fromEntries(headers.map((header, column) => [header.trim(), values[column] ?? ""]))
    return {
      path: String(record.path || "").trim(),
      gameId: String(record.game_id || "").trim(),
      gameName: String(record.game_name || record.game_id || "").trim(),
      yearMonth: String(record.year_month || "").trim(),
      listingType: String(record.listing_type || "").trim(),
      listingTypeLabel: String(record.listing_type_label || record.listing_type || "").trim(),
      rows: catalogNumber(record.rows),
      bytes: catalogNumber(record.bytes),
      priceCandidateRows: catalogNumber(record.price_candidate_rows),
      strictPriceRows: catalogNumber(record.strict_price_rows),
      minPostedAt: String(record.min_posted_at || "").trim(),
      maxPostedAt: String(record.max_posted_at || "").trim(),
    }
  }).filter((entry) => Boolean(entry.path && entry.gameId && entry.yearMonth))
}

export function normalizeCardName(value: string): string {
  return value
    .replace(TRADE_WORDS, " ")
    .replace(QUANTITY_NOISE, " ")
    .replace(PER_UNIT_NOISE, " ")
    .replace(SHIPPING_NOISE, " ")
    .replace(PRICE_NOISE, " ")
    .replace(/[()[\]{}\\/:,;|]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^[\s\-._~]+|[\s\-._~]+$/g, "")
}

function normalizeMarketRow(record: Record<string, string>, id: string): MarketRow | null {
  const title = first(record, "post_title", "title")
  const rawLine = first(record, "raw_line")
  const sourceCardName = first(record, "card_name_normalized", "card_name", "card_name_raw", "card", "name")
  const candidateCardName = sourceCardName || rawLine || title
  const normalizedCardName = normalizeCardName(candidateCardName)
  const cardName = normalizedCardName || (sourceCardName && !NON_CARD_LABEL.test(sourceCardName) ? sourceCardName : "이름 미확인")
  const canonicalCardKeySource = first(record, "card_key")
  const postedAt = first(record, "posted_at", "date", "created_at")
  const dateKey = postedAt.slice(0, 10)
  const priceKrw = positiveNumber(first(record, "price_krw_observed", "price_krw", "buy_price_krw"))
  const quantity = Math.max(1, Math.round(positiveNumber(first(record, "quantity")) || 1))
  const listingType = normalizeIntent(first(record, "listing_type"), `${title} ${rawLine}`)
  const reviewStatus = first(record, "review_status", "status") || "unknown"
  const quality = isLikelyArtifact(sourceCardName, rawLine, normalizedCardName, canonicalCardKeySource) || !normalizedCardName ? "excluded" : normalizeQuality(first(record, "analysis_status"), reviewStatus, priceKrw)
  const priceStatus = normalizePriceStatus(first(record, "price_status"), first(record, "price_unit"), priceKrw)
  const priceScope = normalizePriceScope(first(record, "price_scope"), quantity, rawLine)
  const canonicalCardKey = canonicalCardKeySource.toLocaleLowerCase("ko-KR")
  const cardKey = canonicalCardKey || normalizeCardName(sourceCardName || rawLine || title).toLocaleLowerCase("ko-KR")
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

function catalogNumber(value: unknown): number {
  const parsed = Number(String(value ?? "").replaceAll(",", "").trim())
  return Number.isFinite(parsed) ? parsed : 0
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
  if (/일괄|세트|전부|구성|소스|덱|[+,/&]|\s(?:및|외)\s/.test(rawLine)) return "bundle"
  if (quantity > 1 && !/(?:장|매|개|통)\s*당/.test(rawLine)) return "per_quantity"
  return "per_card"
}

function isLikelyArtifact(...values: string[]): boolean {
  return values.some((value) => ARTIFACT_CARD_TEXT.test(value) || NON_CARD_LABEL.test(value.trim()))
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
