import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from "react"
import { ArrowUpRight, Database, FileUp, Search, SlidersHorizontal, X } from "lucide-react"

import { PriceTrendChart, SupplyDemandChart } from "@/components/market-charts"
import { datasetUrl, parseMarketCsv, type MarketDataset } from "@/lib/market-data"
import type { MarketIntent, MarketQuality, MarketRow } from "@/lib/types"

const SAMPLE_FILES = [
  { file: "tcggame-sales-50-20260812.csv", label: "TCGgame · 거래 샘플" },
  { file: "tcggame-live-20260812.csv", label: "TCGgame · 실시간 1행" },
]

type IntentFilter = MarketIntent | "all"
type QualityFilter = MarketQuality | "all"

export function MarketExplorer() {
  const [dataset, setDataset] = useState<MarketDataset | null>(null)
  const [loadError, setLoadError] = useState("")
  const [query, setQuery] = useState("")
  const [intent, setIntent] = useState<IntentFilter>("all")
  const [quality, setQuality] = useState<QualityFilter>("all")
  const [since, setSince] = useState("")
  const [until, setUntil] = useState("")
  const [isDragging, setIsDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const loadSample = async (fileName: string) => {
    setLoadError("")
    try {
      const response = await fetch(datasetUrl(fileName), { cache: "no-store" })
      if (!response.ok) throw new Error("샘플 CSV를 불러오지 못했습니다. (" + response.status + ")")
      setDataset(parseMarketCsv(await response.text(), fileName))
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "CSV를 불러오지 못했습니다.")
    }
  }

  useEffect(() => {
    let cancelled = false
    void fetchSample(SAMPLE_FILES[0].file).then((nextDataset) => {
      if (!cancelled) setDataset(nextDataset)
    }).catch((error) => {
      if (!cancelled) setLoadError(error instanceof Error ? error.message : "CSV를 불러오지 못했습니다.")
    })
    return () => { cancelled = true }
  }, [])

  const filteredRows = useMemo(() => {
    if (!dataset) return []
    const needle = query.trim().toLocaleLowerCase("ko-KR")
    return dataset.rows.filter((row) => {
      const matchesQuery = !needle || [row.cardName, row.sellerName, row.title, row.rawLine].some((value) => value.toLocaleLowerCase("ko-KR").includes(needle))
      const matchesIntent = intent === "all" || row.listingType === intent
      const matchesQuality = quality === "all" || row.quality === quality
      const matchesSince = !since || (row.dateKey && row.dateKey >= since)
      const matchesUntil = !until || (row.dateKey && row.dateKey <= until)
      return matchesQuery && matchesIntent && matchesQuality && matchesSince && matchesUntil
    })
  }, [dataset, intent, quality, query, since, until])

  const summary = useMemo(() => summarize(filteredRows), [filteredRows])
  const dateRange = useMemo(() => getDateRange(dataset?.rows || []), [dataset])
  const hasFilters = Boolean(query || intent !== "all" || quality !== "all" || since || until)

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0]
    if (!file) return
    setLoadError("")
    const reader = new FileReader()
    reader.onload = () => {
      try { setDataset(parseMarketCsv(String(reader.result || ""), file.name)) } catch { setLoadError("CSV 형식을 읽지 못했습니다.") }
    }
    reader.onerror = () => setLoadError("파일을 읽지 못했습니다.")
    reader.readAsText(file, "utf-8")
  }

  const onDrop = (event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault()
    setIsDragging(false)
    handleFiles(event.dataTransfer.files)
  }

  return <main className="explorer-shell">
    <header className="explorer-topbar">
      <a className="explorer-brand" href={import.meta.env.BASE_URL} aria-label="TCG Trade Radar 홈"><span className="brand-stamp">TR</span><span>TCG Trade Radar</span></a>
      <nav className="top-nav" aria-label="보조 메뉴"><span className="live-dot" />CSV MARKET LENS<a href="?page=collector">수집 관제판 <ArrowUpRight size={14} /></a></nav>
    </header>

    <div className="explorer-layout">
      <aside className="filter-rail">
        <div className="rail-title"><span className="section-kicker">CONTROL ROOM</span><h2><SlidersHorizontal size={18} /> 필터</h2></div>
        <label className="search-field" htmlFor="market-search"><Search size={16} /><input id="market-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="카드, 판매자, 원문 검색" /><kbd>/</kbd></label>
        <div className="filter-section"><span className="filter-label">거래 의도</span><div className="intent-pills">{(["all", "sell", "buy", "trade"] as IntentFilter[]).map((value) => <button key={value} className={intent === value ? "active" : ""} type="button" onClick={() => setIntent(value)}>{intentLabel(value)}</button>)}</div></div>
        <div className="filter-section"><span className="filter-label">데이터 품질</span><select value={quality} onChange={(event) => setQuality(event.target.value as QualityFilter)}><option value="all">전체 품질</option><option value="usable">분석 가능</option><option value="needs_review">검수 필요</option><option value="context_only">참고 전용</option><option value="excluded">제외</option></select></div>
        <div className="filter-section date-filter"><span className="filter-label">게시 날짜</span><label htmlFor="date-since">시작일<input id="date-since" type="date" value={since} min={dateRange.min} max={dateRange.max} onChange={(event) => setSince(event.target.value)} /></label><label htmlFor="date-until">종료일<input id="date-until" type="date" value={until} min={dateRange.min} max={dateRange.max} onChange={(event) => setUntil(event.target.value)} /></label></div>
        {hasFilters && <button className="clear-button" type="button" onClick={() => { setQuery(""); setIntent("all"); setQuality("all"); setSince(""); setUntil("") }}><X size={14} /> 필터 초기화</button>}
        <div className="rail-note"><Database size={16} /><p>가격이 없는 행은 거래량에 남기고 가격 통계에서는 제외합니다.</p></div>
      </aside>

      <section className="explorer-main">
        <div className="explorer-hero"><div><span className="section-kicker">TCG MARKET OBSERVATORY</span><h1>거래 글을<br /><em>시장 신호</em>로 읽기</h1><p>CSV 하나로 카드 가격의 흐름과 매도·매수 온도를 빠르게 확인합니다.</p></div><div className="hero-pulse" aria-hidden="true"><span>SUPPLY</span><i /><span>DEMAND</span></div></div>

        <section className="dataset-bar" aria-label="데이터 소스"><div className="dataset-meta"><span className="data-icon"><Database size={16} /></span><div><strong>{dataset?.name || "CSV 준비 중"}</strong><span>{dataset ? dataset.rows.length.toLocaleString("ko-KR") + "행 · " + dataset.headers.length + "개 컬럼" : "불러오는 중"}</span></div></div><div className="dataset-actions"><select aria-label="샘플 CSV 선택" value={dataset?.name || SAMPLE_FILES[0].file} onChange={(event) => void loadSample(event.target.value)}>{SAMPLE_FILES.map((sample) => <option key={sample.file} value={sample.file}>{sample.label}</option>)}</select><button className={"upload-button " + (isDragging ? "dragging" : "")} type="button" onClick={() => fileInput.current?.click()} onDragOver={(event) => { event.preventDefault(); setIsDragging(true) }} onDragLeave={() => setIsDragging(false)} onDrop={onDrop}><FileUp size={16} /> CSV 열기</button><input ref={fileInput} className="sr-only" type="file" accept=".csv,text/csv" onChange={(event: ChangeEvent<HTMLInputElement>) => handleFiles(event.target.files)} /></div></section>
        {loadError && <div className="explorer-error" role="alert">{loadError}</div>}

        <section className="metric-grid" aria-label="현재 데이터 요약"><Metric label="분석 행" value={summary.rows} detail={hasFilters ? "필터 결과" : "전체 CSV"} tone="coral" /><Metric label="카드 키" value={summary.cards} detail={summary.missingPrice.toLocaleString("ko-KR") + "건 가격 미기재"} tone="ink" /><Metric label="공급 / 수요" value={summary.supply + " / " + summary.demand} detail={"수량 " + summary.supplyQuantity.toLocaleString("ko-KR") + " / " + summary.demandQuantity.toLocaleString("ko-KR")} tone="lime" /><Metric label="판매자" value={summary.sellers} detail={summary.pricePoints + "개 가격 포인트"} tone="mint" /></section>

        <div className="charts-grid"><PriceTrendChart rows={filteredRows} /><SupplyDemandChart rows={filteredRows} /></div>
        <CardTable rows={filteredRows} />
      </section>
    </div>
  </main>
}

async function fetchSample(fileName: string): Promise<MarketDataset> {
  const response = await fetch(datasetUrl(fileName), { cache: "no-store" })
  if (!response.ok) throw new Error("샘플 CSV를 불러오지 못했습니다. (" + response.status + ")")
  return parseMarketCsv(await response.text(), fileName)
}

function Metric({ label, value, detail, tone }: { label: string; value: string | number; detail: string; tone: string }) { return <article className={"metric-card " + tone}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article> }

function CardTable({ rows }: { rows: MarketRow[] }) {
  const groups = useMemo(() => {
    const grouped = new Map<string, { name: string; count: number; supply: number; demand: number; prices: number[]; sellers: Set<string>; date: string }>()
    for (const row of rows) {
      const current = grouped.get(row.cardKey) || { name: row.cardName, count: 0, supply: 0, demand: 0, prices: [], sellers: new Set<string>(), date: "" }
      current.count += 1
      if (row.listingType === "sell") { current.supply += 1; if (row.priceKrw != null && row.priceScope === "per_card") current.prices.push(row.priceKrw) }
      if (row.listingType === "buy") { current.demand += 1; if (row.priceKrw != null && row.priceScope === "per_card") current.prices.push(row.priceKrw) }
      if (row.sellerName) current.sellers.add(row.sellerName)
      if (row.dateKey > current.date) current.date = row.dateKey
      grouped.set(row.cardKey, current)
    }
    return [...grouped.values()].sort((left, right) => (right.demand - right.supply) - (left.demand - left.supply) || right.count - left.count).slice(0, 12)
  }, [rows])
  return <section className="card-table-panel"><div className="panel-bar"><div><span className="section-kicker">CARD SIGNALS</span><h2>카드별 시장 신호</h2></div><span>{groups.length}개 카드 표시</span></div>{groups.length === 0 ? <div className="chart-empty">현재 필터에 맞는 카드가 없습니다.</div> : <div className="card-table-wrap"><table><thead><tr><th>카드</th><th>공급</th><th>수요</th><th>가격 중앙값</th><th>판매자</th><th>최근 게시</th></tr></thead><tbody>{groups.map((group) => <tr key={group.name}><td><strong>{group.name}</strong><small>{group.count}개 관측</small></td><td><span className="table-number supply-text">{group.supply}</span></td><td><span className="table-number demand-text">{group.demand}</span></td><td>{group.prices.length ? Math.round(median(group.prices)).toLocaleString("ko-KR") + "원" : "-"}</td><td>{group.sellers.size}명</td><td>{group.date ? group.date.replaceAll("-", ".") : "-"}</td></tr>)}</tbody></table></div>}</section>
}

function summarize(rows: MarketRow[]) {
  const prices = rows.filter((row) => row.priceKrw != null && row.priceScope === "per_card")
  return {
    rows: rows.length,
    cards: new Set(rows.map((row) => row.cardKey).filter(Boolean)).size,
    sellers: new Set(rows.map((row) => row.sellerName).filter(Boolean)).size,
    supply: rows.filter((row) => row.listingType === "sell").length,
    demand: rows.filter((row) => row.listingType === "buy").length,
    supplyQuantity: rows.filter((row) => row.listingType === "sell").reduce((sum, row) => sum + row.quantity, 0),
    demandQuantity: rows.filter((row) => row.listingType === "buy").reduce((sum, row) => sum + row.quantity, 0),
    pricePoints: prices.length,
    missingPrice: rows.filter((row) => row.priceKrw == null).length,
  }
}

function getDateRange(rows: MarketRow[]) { const dates = rows.map((row) => row.dateKey).filter(Boolean).sort(); return { min: dates[0] || "", max: dates[dates.length - 1] || "" } }
function median(values: number[]) { const sorted = [...values].sort((left, right) => left - right); const middle = Math.floor(sorted.length / 2); return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2 }
function intentLabel(value: IntentFilter) { return value === "all" ? "전체" : value === "sell" ? "판매" : value === "buy" ? "구매" : "교환" }
