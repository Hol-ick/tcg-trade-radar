import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent, type ReactNode } from "react"
import { Activity, ArrowUpRight, BarChart3, Database, FileUp, LayoutDashboard, Search, Table2, UploadCloud, Users, X } from "lucide-react"

import { PriceTrendChart, SupplyDemandChart } from "@/components/market-charts"
import { datasetUrl, marketCatalogUrl, MARKET_CATALOG_ID, parseMarketCsv, parsePartitionCatalog, type MarketCatalogEntry, type MarketDataset } from "@/lib/market-data"
import type { MarketIntent, MarketQuality, MarketRow } from "@/lib/types"

const SAMPLE_FILES = [
  { file: "tcggame-sales-50-20260812.csv", label: "TCGgame · 거래 샘플" },
  { file: "tcggame-live-20260812.csv", label: "TCGgame · 실시간 1행" },
]

type DatasetOption = { file: string; label: string; source: "sample" | "git" }

type IntentFilter = MarketIntent | "all"
type QualityFilter = MarketQuality | "all"

export function MarketExplorer() {
  const [dataset, setDataset] = useState<MarketDataset | null>(null)
  const [loadError, setLoadError] = useState("")
  const [catalog, setCatalog] = useState<MarketCatalogEntry[]>([])
  const [catalogError, setCatalogError] = useState("")
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
      if (!response.ok) throw new Error(`샘플 CSV를 불러오지 못했습니다 (${response.status})`)
      setDataset(parseMarketCsv(await response.text(), fileName))
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "CSV를 불러오지 못했습니다")
    }
  }

  useEffect(() => {
    let cancelled = false
    void fetchSample(SAMPLE_FILES[0].file).then((nextDataset) => {
      if (!cancelled) setDataset(nextDataset)
    }).catch((error) => {
      if (!cancelled) setLoadError(error instanceof Error ? error.message : "CSV를 불러오지 못했습니다")
    })
    void fetch(marketCatalogUrl(), { cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error(`GitHub CSV 카탈로그를 불러오지 못했습니다 (${response.status})`)
      return parsePartitionCatalog(await response.text())
    }).then((entries) => {
      if (!cancelled) setCatalog(entries)
    }).catch((error) => {
      if (!cancelled) setCatalogError(error instanceof Error ? error.message : "GitHub CSV 카탈로그를 불러오지 못했습니다")
    })
    return () => { cancelled = true }
  }, [])

  const filteredRows = useMemo(() => {
    if (!dataset) return []
    const needle = query.trim().toLocaleLowerCase("ko-KR")
    return dataset.rows.filter((row) => {
      const matchesQuery = !needle || [row.cardKey, row.cardName, row.sellerName, row.title, row.rawLine].some((value) => value.toLocaleLowerCase("ko-KR").includes(needle))
      const matchesIntent = intent === "all" || row.listingType === intent
      const matchesQuality = quality === "all" || row.quality === quality
      const matchesSince = !since || (row.dateKey && row.dateKey >= since)
      const matchesUntil = !until || (row.dateKey && row.dateKey <= until)
      return matchesQuery && matchesIntent && matchesQuality && matchesSince && matchesUntil
    })
  }, [dataset, intent, quality, query, since, until])

  const signalRows = useMemo(() => quality === "excluded" ? filteredRows : filteredRows.filter((row) => row.quality !== "excluded"), [filteredRows, quality])
  const summary = useMemo(() => summarize(signalRows), [signalRows])
  const dateRange = useMemo(() => getDateRange(dataset?.rows || []), [dataset])
  const hasFilters = Boolean(query || intent !== "all" || quality !== "all" || since || until)
  const datasetOptions = useMemo<DatasetOption[]>(() => [
    ...SAMPLE_FILES.map((sample) => ({ ...sample, source: "sample" as const })),
    ...catalog.map((entry) => ({ file: `${MARKET_CATALOG_ID}/${entry.path}`, label: `Git · ${entry.gameName} · ${entry.yearMonth} · ${entry.listingTypeLabel} · ${entry.rows.toLocaleString("ko-KR")}행`, source: "git" as const })),
  ], [catalog])
  const selectedOption = datasetOptions.find((option) => option.file === dataset?.name)
  const sourceLabel = selectedOption?.source === "git" ? "GitHub CSV" : selectedOption?.source === "sample" ? "Bundled sample" : "Uploaded CSV"
  const openFilePicker = () => fileInput.current?.click()

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0]
    if (!file) return
    setLoadError("")
    const reader = new FileReader()
    reader.onload = () => {
      try { setDataset(parseMarketCsv(String(reader.result || ""), file.name)) } catch { setLoadError("CSV 형식을 읽지 못했습니다") }
    }
    reader.onerror = () => setLoadError("파일을 읽지 못했습니다")
    reader.readAsText(file, "utf-8")
  }

  const onDrop = (event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault()
    setIsDragging(false)
    handleFiles(event.dataTransfer.files)
  }

  const resetFilters = () => {
    setQuery("")
    setIntent("all")
    setQuality("all")
    setSince("")
    setUntil("")
  }

  return <main className="explorer-shell">
    <aside className="saas-sidebar">
      <a className="saas-brand" href={import.meta.env.BASE_URL} aria-label="TCG Trade Radar 홈">
        <span className="brand-mark">TR</span>
        <span><strong>Trade Radar</strong><small>Market intelligence</small></span>
      </a>

      <div className="sidebar-section-label">Workspace</div>
      <nav className="sidebar-nav" aria-label="주 메뉴">
        <a className="active" href="#overview"><LayoutDashboard size={16} />Overview</a>
        <a href="#signals"><Table2 size={16} />Card signals</a>
        <a href="?page=collector"><Activity size={16} />Collector<ArrowUpRight size={13} className="nav-external" /></a>
      </nav>

      <div className="sidebar-divider" />
      <div className="sidebar-section-label">Data source</div>
      <div className="sidebar-source">
        <span className="source-icon"><Database size={15} /></span>
        <span><strong>{dataset?.name || "Loading CSV"}</strong><small>{dataset ? `${sourceLabel} · ${dataset.rows.length.toLocaleString("ko-KR")} rows` : "Preparing workspace"}</small></span>
      </div>
      <div className="sidebar-spacer" />
      <div className="sidebar-workspace"><span>TCG</span><span><strong>Personal workspace</strong><small>CSV market analysis</small></span></div>
    </aside>

    <section className="saas-main">
      <header className="saas-header">
        <div className="breadcrumbs"><span>Workspace</span><span>/</span><strong>Market explorer</strong></div>
        <div className="header-actions"><span className="connection-pill"><i />GitHub CSV + local file</span><a className="header-collector-link" href="?page=collector">Open collector <ArrowUpRight size={14} /></a></div>
      </header>

      <div className="saas-content">
        <section className="page-heading" id="overview">
          <div><span className="eyebrow">MARKET EXPLORER</span><h1>Market overview</h1><p>카드 거래 CSV를 불러와 가격, 수요, 공급 신호를 한 화면에서 확인하세요.</p></div>
          <button className="button button-primary" type="button" onClick={openFilePicker}><UploadCloud size={16} />Open CSV</button>
        </section>

        <section className="source-card" aria-label="데이터 소스">
          <div className="source-card-main"><span className="source-avatar"><Database size={17} /></span><span><small>{dataset ? sourceLabel : "Current dataset"}</small><strong>{dataset?.name || "CSV 준비 중"}</strong><em>{dataset ? `${dataset.rows.length.toLocaleString("ko-KR")} rows · ${dataset.headers.length} columns` : "Loading data"}</em></span></div>
          <div className="source-card-actions"><select aria-label="GitHub 또는 샘플 CSV 선택" value={dataset?.name || SAMPLE_FILES[0].file} onChange={(event) => void loadSample(event.target.value)}><optgroup label="Bundled samples">{datasetOptions.filter((option) => option.source === "sample").map((option) => <option key={option.file} value={option.file}>{option.label}</option>)}</optgroup>{catalog.length > 0 && <optgroup label={`GitHub CSV · ${catalog.length} partitions`}>{datasetOptions.filter((option) => option.source === "git").map((option) => <option key={option.file} value={option.file}>{option.label}</option>)}</optgroup>}</select><button className={`button button-secondary ${isDragging ? "dragging" : ""}`} type="button" onClick={openFilePicker} onDragOver={(event) => { event.preventDefault(); setIsDragging(true) }} onDragLeave={() => setIsDragging(false)} onDrop={onDrop}><FileUp size={15} />Choose file</button><input ref={fileInput} className="sr-only" type="file" accept=".csv,text/csv" onChange={(event: ChangeEvent<HTMLInputElement>) => handleFiles(event.target.files)} /></div>
        </section>
        {catalogError && <div className="catalog-status" role="status">{catalogError} · 샘플 CSV와 로컬 파일은 계속 사용할 수 있습니다.</div>}
        {loadError && <div className="explorer-error" role="alert">{loadError}</div>}

        <section className="filter-card" aria-label="시장 데이터 필터">
          <div className="filter-card-header"><div><span className="eyebrow">FILTERS</span><h2>Refine this view</h2></div>{hasFilters && <button className="clear-button" type="button" onClick={resetFilters}><X size={14} />Clear filters</button>}</div>
          <div className="filter-controls">
            <label className="saas-field search-control" htmlFor="market-search"><span>Search</span><div><Search size={15} /><input id="market-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Card, seller, or post title" /><kbd>/</kbd></div></label>
            <div className="saas-field"><span>Listing type</span><div className="intent-tabs">{(["all", "sell", "buy", "trade"] as IntentFilter[]).map((value) => <button key={value} className={intent === value ? "active" : ""} type="button" onClick={() => setIntent(value)}>{intentLabel(value)}</button>)}</div></div>
            <label className="saas-field" htmlFor="quality-filter"><span>Data quality</span><select id="quality-filter" value={quality} onChange={(event) => setQuality(event.target.value as QualityFilter)}><option value="all">All quality levels</option><option value="usable">Analysis ready</option><option value="needs_review">Needs review</option><option value="context_only">Context only</option><option value="excluded">Excluded</option></select></label>
            <div className="saas-field date-controls"><span>Date range</span><div><input id="date-since" aria-label="시작일" type="date" value={since} min={dateRange.min} max={dateRange.max} onChange={(event) => setSince(event.target.value)} /><span>to</span><input id="date-until" aria-label="종료일" type="date" value={until} min={dateRange.min} max={dateRange.max} onChange={(event) => setUntil(event.target.value)} /></div></div>
          </div>
          <div className="filter-footer"><span>{filteredRows.length.toLocaleString("ko-KR")} of {(dataset?.rows.length || 0).toLocaleString("ko-KR")} observations shown</span><span>Price-less rows remain available for volume analysis</span></div>
        </section>

        <section className="metric-grid" aria-label="현재 데이터 요약">
          <Metric icon={<BarChart3 size={17} />} label="Observations" value={summary.rows} detail={hasFilters ? "Filtered result" : "Full CSV"} tone="blue" />
          <Metric icon={<Database size={17} />} label="Card keys" value={summary.cards} detail={`${summary.missingPrice.toLocaleString("ko-KR")} missing prices`} tone="violet" />
          <Metric icon={<Activity size={17} />} label="Supply / demand" value={`${summary.supply} / ${summary.demand}`} detail={`Qty ${summary.supplyQuantity.toLocaleString("ko-KR")} / ${summary.demandQuantity.toLocaleString("ko-KR")}`} tone="green" />
          <Metric icon={<Users size={17} />} label="Sellers" value={summary.sellers} detail={`${summary.pricePoints} price points`} tone="amber" />
        </section>

        <div className="section-heading"><div><span className="eyebrow">ANALYTICS</span><h2>Market signals</h2></div><span className="section-meta">Updated from current dataset</span></div>
        <div className="charts-grid"><PriceTrendChart rows={signalRows} /><SupplyDemandChart rows={signalRows} /></div>
        <CardTable rows={signalRows} />
      </div>
    </section>
  </main>
}

async function fetchSample(fileName: string): Promise<MarketDataset> {
  const response = await fetch(datasetUrl(fileName), { cache: "no-store" })
  if (!response.ok) throw new Error(`샘플 CSV를 불러오지 못했습니다 (${response.status})`)
  return parseMarketCsv(await response.text(), fileName)
}

function Metric({ icon, label, value, detail, tone }: { icon: ReactNode; label: string; value: string | number; detail: string; tone: string }) {
  return <article className={`metric-card ${tone}`}><div className="metric-icon">{icon}</div><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>
}

function CardTable({ rows }: { rows: MarketRow[] }) {
  const groups = useMemo(() => {
    const grouped = new Map<string, { name: string; count: number; supply: number; demand: number; unknown: number; prices: number[]; sellers: Set<string>; date: string }>()
    for (const row of rows) {
      const current = grouped.get(row.cardKey) || { name: row.cardName, count: 0, supply: 0, demand: 0, unknown: 0, prices: [], sellers: new Set<string>(), date: "" }
      current.count += 1
      if (row.listingType === "sell") current.supply += 1
      else if (row.listingType === "buy") current.demand += 1
      else current.unknown += 1
      if (row.priceKrw != null && row.priceScope === "per_card") current.prices.push(row.priceKrw)
      if (row.sellerName) current.sellers.add(row.sellerName)
      if (row.dateKey > current.date) current.date = row.dateKey
      grouped.set(row.cardKey, current)
    }
    return [...grouped.values()].sort((left, right) => (right.supply + right.demand) - (left.supply + left.demand) || right.count - left.count).slice(0, 12)
  }, [rows])
  return <section className="table-card" id="signals"><div className="table-card-header"><div><span className="eyebrow">CARD SIGNALS</span><h2>Card-level market signals</h2></div><span className="table-count">{groups.length} cards shown</span></div>{groups.length === 0 ? <div className="chart-empty">현재 필터에 맞는 카드가 없습니다.</div> : <div className="card-table-wrap"><table><thead><tr><th>Card</th><th>Supply</th><th>Demand</th><th>Unclassified</th><th>Observed median</th><th>Sellers</th><th>Last posted</th></tr></thead><tbody>{groups.map((group) => <tr key={group.name}><td><strong>{group.name}</strong><small>{group.count} observations</small></td><td><span className="table-number supply-text">{group.supply}</span></td><td><span className="table-number demand-text">{group.demand}</span></td><td><span className="table-number unknown-text">{group.unknown || "—"}</span></td><td>{group.prices.length ? `${Math.round(median(group.prices)).toLocaleString("ko-KR")}원` : "—"}</td><td>{group.sellers.size}</td><td>{group.date ? group.date.replaceAll("-", ".") : "—"}</td></tr>)}</tbody></table></div>}<div className="table-card-footer"><span>Top 12 cards by classified activity and observations</span><span>{rows.length.toLocaleString("ko-KR")} total observations</span></div></section>
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
function intentLabel(value: IntentFilter) { return value === "all" ? "All" : value === "sell" ? "Sell" : value === "buy" ? "Buy" : "Trade" }
