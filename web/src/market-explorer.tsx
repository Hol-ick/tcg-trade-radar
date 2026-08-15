import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent, type MouseEvent, type ReactNode } from "react"
import { Activity, ArrowUpRight, BarChart3, Database, FileUp, LayoutDashboard, Search, Table2, UploadCloud, Users, X } from "lucide-react"

import { GameLogo } from "@/components/game-logo"
import { PriceTrendChart, SupplyDemandChart } from "@/components/market-charts"
import { datasetUrl, marketCatalogUrl, MARKET_CATALOG_ID, parseMarketCsv, parsePartitionCatalog, type MarketCatalogEntry, type MarketDataset } from "@/lib/market-data"
import { GALLERY_PRESETS, type MarketIntent, type MarketQuality, type MarketRow } from "@/lib/types"

const SAMPLE_FILES = [
  { file: "tcggame-sales-50-20260812.csv", label: "TCGgame · 거래 샘플" },
  { file: "tcggame-live-20260812.csv", label: "TCGgame · 실시간 1행" },
]

type DatasetOption = { file: string; label: string; source: "sample" | "git" }

type IntentFilter = MarketIntent | "all"
type QualityFilter = MarketQuality | "all"
const INTENT_FILTERS: IntentFilter[] = ["all", "sell", "buy", "trade", "unknown"]

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
  const [selectedGameId, setSelectedGameId] = useState(GALLERY_PRESETS[0].id)
  const [isGameLoading, setIsGameLoading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [selectedCardKey, setSelectedCardKey] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const loadDatasetFile = async (fileName: string) => {
    setLoadError("")
    setIsGameLoading(true)
    try {
      const response = await fetch(datasetUrl(fileName), { cache: "no-store" })
      if (!response.ok) throw new Error(`CSV를 불러오지 못했습니다 (${response.status})`)
      const nextDataset = parseMarketCsv(await response.text(), fileName)
      setDataset(nextDataset)
      const detectedGameId = nextDataset.rows.find((row) => row.galleryId)?.galleryId
      if (detectedGameId) setSelectedGameId(detectedGameId)
      setSelectedCardKey(null)
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "CSV를 불러오지 못했습니다")
    } finally {
      setIsGameLoading(false)
    }
  }

  const loadCatalogGame = async (gameId: string) => {
    const entries = catalog.filter((entry) => entry.gameId === gameId)
    const game = GALLERY_PRESETS.find((item) => item.id === gameId)
    if (!entries.length) {
      setSelectedGameId(gameId)
      setLoadError(`${game?.name || "선택한 게임"}의 공개 CSV가 아직 없습니다.`)
      return
    }

    setSelectedGameId(gameId)
    setLoadError("")
    setIsGameLoading(true)
    try {
      const datasets = await Promise.all(entries.map(async (entry) => {
        const fileName = `${MARKET_CATALOG_ID}/${entry.path}`
        const response = await fetch(datasetUrl(fileName), { cache: "no-store" })
        if (!response.ok) throw new Error(`${entry.gameName} ${entry.yearMonth} ${entry.listingTypeLabel} CSV를 불러오지 못했습니다 (${response.status})`)
        return parseMarketCsv(await response.text(), fileName)
      }))
      const loadedRows = datasets.flatMap((item) => item.rows)
      const loadedHeaders = [...new Set(datasets.flatMap((item) => item.headers))]
      setDataset({
        name: `${MARKET_CATALOG_ID}/${gameId}/all`,
        rows: loadedRows,
        headers: loadedHeaders,
        loadedAt: new Date().toISOString(),
      })
      setIntent("all")
      setSelectedCardKey(null)
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "게임 데이터를 불러오지 못했습니다")
    } finally {
      setIsGameLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    void fetchSample(SAMPLE_FILES[0].file).then((nextDataset) => {
      if (!cancelled) {
        setDataset(nextDataset)
        setSelectedGameId(nextDataset.rows.find((row) => row.galleryId)?.galleryId || GALLERY_PRESETS[0].id)
      }
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
      const matchesGame = row.galleryId === selectedGameId || !row.galleryId
      const matchesQuery = !needle || [row.cardKey, row.cardName, row.sellerName, row.title, row.rawLine].some((value) => value.toLocaleLowerCase("ko-KR").includes(needle))
      const matchesIntent = intent === "all" || row.listingType === intent
      const matchesQuality = quality === "all" || row.quality === quality
      const matchesSince = !since || (row.dateKey && row.dateKey >= since)
      const matchesUntil = !until || (row.dateKey && row.dateKey <= until)
      return matchesGame && matchesQuery && matchesIntent && matchesQuality && matchesSince && matchesUntil
    })
  }, [dataset, intent, quality, query, selectedGameId, since, until])

  const signalRows = useMemo(() => quality === "excluded" ? filteredRows : filteredRows.filter((row) => row.quality !== "excluded"), [filteredRows, quality])
  const selectedRows = useMemo(() => selectedCardKey ? signalRows.filter((row) => row.cardKey === selectedCardKey) : [], [selectedCardKey, signalRows])
  const summary = useMemo(() => summarize(signalRows), [signalRows])
  const dateRange = useMemo(() => getDateRange(dataset?.rows || []), [dataset])
  const hasFilters = Boolean(query || intent !== "all" || quality !== "all" || since || until)
  const datasetOptions = useMemo<DatasetOption[]>(() => [
    ...SAMPLE_FILES.map((sample) => ({ ...sample, source: "sample" as const })),
    ...catalog.map((entry) => ({ file: `${MARKET_CATALOG_ID}/${entry.path}`, label: `공개 · ${entry.gameName} · ${entry.yearMonth} · ${entry.listingTypeLabel} · ${entry.rows.toLocaleString("ko-KR")}행`, source: "git" as const })),
  ], [catalog])
  const selectedOption = datasetOptions.find((option) => option.file === dataset?.name)
  const sourceLabel = dataset?.name.startsWith(`${MARKET_CATALOG_ID}/`) ? "공개 CSV" : selectedOption?.source === "sample" ? "기본 샘플" : "업로드한 CSV"
  const activeGame = GALLERY_PRESETS.find((game) => game.id === selectedGameId) || GALLERY_PRESETS[0]
  const activeGameEntries = catalog.filter((entry) => entry.gameId === activeGame.id)
  const availableGameRows = new Map(GALLERY_PRESETS.map((game) => [game.id, catalog.filter((entry) => entry.gameId === game.id).reduce((total, entry) => total + entry.rows, 0)]))
  const activeIntentCounts = useMemo(() => {
    const counts = new Map<IntentFilter, number>(INTENT_FILTERS.map((value) => [value, 0]))
    for (const row of dataset?.rows || []) {
      if (row.galleryId !== selectedGameId) continue
      counts.set(row.listingType, (counts.get(row.listingType) || 0) + 1)
    }
    return counts
  }, [dataset, selectedGameId])
  const openFilePicker = () => fileInput.current?.click()

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0]
    if (!file) return
    setLoadError("")
    const reader = new FileReader()
    reader.onload = () => {
      try { setDataset(parseMarketCsv(String(reader.result || ""), file.name)); setSelectedCardKey(null) } catch { setLoadError("CSV 형식을 읽지 못했습니다") }
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
    setSelectedCardKey(null)
  }

  const currentDatasetName = dataset?.name.startsWith(`${MARKET_CATALOG_ID}/`)
    ? `${activeGame.name} · 전체 거래 데이터`
    : dataset?.name || "CSV 준비 중"

  return <main className="explorer-shell">
    <aside className="saas-sidebar">
      <a className="saas-brand" href={import.meta.env.BASE_URL} aria-label="TCG Trade Radar 홈">
        <span className="brand-mark">TR</span>
        <span><strong>Trade Radar</strong><small>거래 시장 분석</small></span>
      </a>

      <div className="sidebar-section-label">작업공간</div>
      <nav className="sidebar-nav" aria-label="주 메뉴">
        <a className="active" href="#overview"><LayoutDashboard size={16} />시장 개요</a>
        <a href="#signals"><Table2 size={16} />카드 신호</a>
        <a href="?page=collector"><Activity size={16} />수집기<ArrowUpRight size={13} className="nav-external" /></a>
      </nav>

      <div className="sidebar-divider" />
      <div className="sidebar-section-label">데이터 원본</div>
      <div className="sidebar-source">
        <span className="source-icon"><Database size={15} /></span>
        <span><strong>{currentDatasetName}</strong><small>{dataset ? `${sourceLabel} · ${dataset.rows.length.toLocaleString("ko-KR")}행` : "데이터 준비 중"}</small></span>
      </div>
      <div className="sidebar-spacer" />
      <div className="sidebar-workspace"><span>TCG</span><span><strong>개인 작업공간</strong><small>CSV 시장 분석</small></span></div>
    </aside>

    <section className="saas-main">
      <header className="saas-header">
        <div className="breadcrumbs"><span>작업공간</span><span>/</span><strong>시장 탐색기</strong></div>
        <div className="header-actions"><span className="connection-pill"><i />공개 CSV · 로컬 파일</span><a className="header-collector-link" href="?page=collector">수집기 열기 <ArrowUpRight size={14} /></a></div>
      </header>

      <div className="saas-content">
        <section className="page-heading" id="overview">
          <div><span className="eyebrow">시장 탐색기</span><h1>거래 시장 개요</h1><p>게임을 고르고 판매·구매·교환 데이터를 바로 확인하세요.</p></div>
          <button className="button button-primary" type="button" onClick={openFilePicker}><UploadCloud size={16} />CSV 열기</button>
        </section>

        <section className="source-card" aria-label="데이터 소스">
          <div className="source-card-main"><span className="source-avatar"><Database size={17} /></span><span><small>{dataset ? sourceLabel : "현재 데이터"}</small><strong>{currentDatasetName}</strong><em>{dataset ? `${dataset.rows.length.toLocaleString("ko-KR")}행 · ${dataset.headers.length}개 열` : "데이터 불러오는 중"}</em></span></div>
          <div className="source-card-actions"><select aria-label="공개 또는 샘플 CSV 선택" value={dataset?.name || SAMPLE_FILES[0].file} onChange={(event) => void loadDatasetFile(event.target.value)}>{dataset && !datasetOptions.some((option) => option.file === dataset.name) && <option value={dataset.name}>{currentDatasetName} · 현재 선택</option>}<optgroup label="기본 샘플">{datasetOptions.filter((option) => option.source === "sample").map((option) => <option key={option.file} value={option.file}>{option.label}</option>)}</optgroup>{catalog.length > 0 && <optgroup label={`공개 CSV · ${catalog.length}개 파일`}>{datasetOptions.filter((option) => option.source === "git").map((option) => <option key={option.file} value={option.file}>{option.label}</option>)}</optgroup>}</select><button className={`button button-secondary ${isDragging ? "dragging" : ""}`} type="button" onClick={openFilePicker} onDragOver={(event) => { event.preventDefault(); setIsDragging(true) }} onDragLeave={() => setIsDragging(false)} onDrop={onDrop}><FileUp size={15} />파일 선택</button><input ref={fileInput} className="sr-only" type="file" accept=".csv,text/csv" onChange={(event: ChangeEvent<HTMLInputElement>) => handleFiles(event.target.files)} /></div>
        </section>
        {catalogError && <div className="catalog-status" role="status">{catalogError} · 샘플 CSV와 로컬 파일은 계속 사용할 수 있습니다.</div>}
        {loadError && <div className="explorer-error" role="alert">{loadError}</div>}

        <section className="game-filter-card" aria-label="게임 및 거래 유형 선택">
          <div className="game-filter-heading"><div><span className="eyebrow">게임 분류</span><h2>게임을 선택하세요</h2></div><span className="game-filter-status">{isGameLoading ? "데이터 불러오는 중" : !catalog.length ? "카탈로그 준비 중" : `${activeGame.name} · ${activeGameEntries.length}개 파일`}</span></div>
          <div className="game-picker" role="group" aria-label="게임 선택">
            {GALLERY_PRESETS.map((game) => {
              const rowCount = availableGameRows.get(game.id) || 0
              const isActive = game.id === selectedGameId
              const isDisabled = isGameLoading || !catalog.length || rowCount === 0
              return <button key={game.id} className={`game-picker-button ${isActive ? "active" : ""}`} type="button" aria-pressed={isActive} disabled={isDisabled} onClick={() => void loadCatalogGame(game.id)}>
                <GameLogo game={game} />
                <span><strong>{game.name}</strong><small>{rowCount ? `${rowCount.toLocaleString("ko-KR")}행` : "데이터 준비 중"}</small></span>
              </button>
            })}
          </div>
          <div className="sub-filter-row"><span className="sub-filter-label">거래 유형</span><div className="intent-tabs intent-tabs-prominent" role="group" aria-label="거래 유형 선택">{INTENT_FILTERS.map((value) => <button key={value} className={intent === value ? "active" : ""} type="button" aria-pressed={intent === value} onClick={() => { setIntent(value); setSelectedCardKey(null) }}><span>{intentLabel(value)}</span>{value !== "all" && <small>{activeIntentCounts.get(value) || 0}</small>}</button>)}</div></div>
        </section>

        <section className="filter-card" aria-label="시장 데이터 필터">
          <div className="filter-card-header"><div><span className="eyebrow">세부 필터</span><h2>조건 좁히기</h2></div>{hasFilters && <button className="clear-button" type="button" onClick={resetFilters}><X size={14} />필터 초기화</button>}</div>
          <div className="filter-controls">
            <label className="saas-field search-control" htmlFor="market-search"><span>검색</span><div><Search size={15} /><input id="market-search" value={query} onChange={(event) => { setQuery(event.target.value); setSelectedCardKey(null) }} placeholder="카드명, 판매자, 제목" /><kbd>/</kbd></div></label>
            <label className="saas-field" htmlFor="quality-filter"><span>데이터 품질</span><select id="quality-filter" value={quality} onChange={(event) => { setQuality(event.target.value as QualityFilter); setSelectedCardKey(null) }}><option value="all">전체 품질</option><option value="usable">분석 가능</option><option value="needs_review">검토 필요</option><option value="context_only">참고용</option><option value="excluded">제외됨</option></select></label>
            <div className="saas-field date-controls"><span>기간</span><div><input id="date-since" aria-label="시작일" type="date" value={since} min={dateRange.min} max={dateRange.max} onChange={(event) => { setSince(event.target.value); setSelectedCardKey(null) }} /><span>~</span><input id="date-until" aria-label="종료일" type="date" value={until} min={dateRange.min} max={dateRange.max} onChange={(event) => { setUntil(event.target.value); setSelectedCardKey(null) }} /></div></div>
          </div>
          <div className="filter-footer"><span>전체 {(dataset?.rows.length || 0).toLocaleString("ko-KR")}행 중 {filteredRows.length.toLocaleString("ko-KR")}행 표시</span><span>가격이 없어도 거래량 분석에는 포함됩니다.</span></div>
        </section>

        <section className="metric-grid" aria-label="현재 데이터 요약">
          <Metric icon={<BarChart3 size={17} />} label="관측 행" value={summary.rows} detail={hasFilters ? "현재 조건 결과" : "전체 CSV"} tone="blue" />
          <Metric icon={<Database size={17} />} label="카드 종류" value={summary.cards} detail={`${summary.missingPrice.toLocaleString("ko-KR")}개 가격 없음`} tone="violet" />
          <Metric icon={<Activity size={17} />} label="공급 / 수요" value={`${summary.supply} / ${summary.demand}`} detail={`수량 ${summary.supplyQuantity.toLocaleString("ko-KR")} / ${summary.demandQuantity.toLocaleString("ko-KR")}`} tone="green" />
          <Metric icon={<Users size={17} />} label="판매자" value={summary.sellers} detail={`${summary.pricePoints}개 가격 관측`} tone="amber" />
        </section>

        <div className="section-heading"><div><span className="eyebrow">분석</span><h2>시장 신호</h2></div><span className="section-meta">현재 데이터 기준</span></div>
        <div className="charts-grid"><PriceTrendChart rows={signalRows} /><SupplyDemandChart rows={signalRows} /></div>
        <CardTable rows={signalRows} onSelect={setSelectedCardKey} />
      </div>
    </section>
    {selectedRows.length > 0 && <CardDetailModal rows={selectedRows} onClose={() => setSelectedCardKey(null)} />}
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

type CardGroup = {
  cardKey: string
  name: string
  count: number
  supply: number
  demand: number
  unknown: number
  prices: number[]
  sellers: Set<string>
  date: string
}

function CardTable({ rows, onSelect }: { rows: MarketRow[]; onSelect: (cardKey: string) => void }) {
  const groups = useMemo(() => {
    const grouped = new Map<string, CardGroup>()
    for (const row of rows) {
      const current = grouped.get(row.cardKey) || { cardKey: row.cardKey, name: row.cardName, count: 0, supply: 0, demand: 0, unknown: 0, prices: [], sellers: new Set<string>(), date: "" }
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
  return <section className="table-card" id="signals"><div className="table-card-header"><div><span className="eyebrow">카드 신호</span><h2>카드별 시장 신호</h2></div><span className="table-count">{groups.length}개 카드 표시</span></div>{groups.length === 0 ? <div className="chart-empty">현재 조건에 맞는 카드가 없습니다.</div> : <div className="card-table-wrap"><table><thead><tr><th>카드</th><th>공급</th><th>수요</th><th>미분류</th><th>관측 중앙값</th><th>판매자</th><th>최근 등록</th></tr></thead><tbody>{groups.map((group) => <tr key={group.cardKey} className="card-table-row" tabIndex={0} role="button" aria-label={`${group.name} 상세 보기`} onClick={() => onSelect(group.cardKey)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(group.cardKey) } }}><td><strong>{group.name}</strong><small>{group.count}행 · 상세 보기</small></td><td><span className="table-number supply-text">{group.supply}</span></td><td><span className="table-number demand-text">{group.demand}</span></td><td><span className="table-number unknown-text">{group.unknown || "—"}</span></td><td>{group.prices.length ? `${Math.round(median(group.prices)).toLocaleString("ko-KR")}원` : "—"}</td><td>{group.sellers.size}</td><td>{group.date ? group.date.replaceAll("-", ".") : "—"}</td></tr>)}</tbody></table></div>}<div className="table-card-footer"><span>분류된 거래량과 관측 수가 많은 카드 12개</span><span>{rows.length.toLocaleString("ko-KR")}개 관측</span></div></section>
}

function CardDetailModal({ rows, onClose }: { rows: MarketRow[]; onClose: () => void }) {
  const closeButton = useRef<HTMLButtonElement>(null)
  const sortedRows = useMemo(() => [...rows].sort((left, right) => `${right.dateKey}${right.postedAt}`.localeCompare(`${left.dateKey}${left.postedAt}`)), [rows])
  const recentRows = useMemo(() => {
    const seen = new Set<string>()
    return sortedRows.filter((row) => {
      const key = [row.postUrl || row.id, row.priceKrw ?? "", row.quantity, row.sellerName, row.listingType].join("|")
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [sortedRows])
  const pricedRows = useMemo(() => rows.filter((row) => row.priceKrw != null && row.priceScope === "per_card"), [rows])
  const cardName = rows[0]?.cardName || rows[0]?.cardKey || "선택한 카드"
  const prices = pricedRows.map((row) => row.priceKrw as number)
  const latestPrice = sortedRows.find((row) => row.priceKrw != null && row.priceScope === "per_card")?.priceKrw ?? null
  const sellers = new Set(rows.map((row) => row.sellerName).filter(Boolean)).size
  const supply = rows.filter((row) => row.listingType === "sell")
  const demand = rows.filter((row) => row.listingType === "buy")

  useEffect(() => {
    closeButton.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onClose() }
    window.addEventListener("keydown", onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener("keydown", onKeyDown)
    }
  }, [onClose])

  const closeOnBackdrop = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) onClose()
  }

  return <div className="modal-backdrop" role="presentation" onMouseDown={closeOnBackdrop}>
    <section className="card-detail-modal" role="dialog" aria-modal="true" aria-labelledby="card-detail-title" onMouseDown={(event) => event.stopPropagation()}>
      <header className="card-detail-header">
        <div>
          <span className="eyebrow">카드 상세</span>
          <h2 id="card-detail-title">{cardName}</h2>
          <p>{rows[0]?.cardKey || "카드 키 없음"}</p>
        </div>
        <button ref={closeButton} className="modal-close-button" type="button" aria-label="카드 상세 닫기" onClick={onClose}><X size={18} /></button>
      </header>

      <div className="detail-stat-grid" aria-label="카드 요약">
        <DetailStat label="관측" value={rows.length.toLocaleString("ko-KR")} detail="현재 필터 기준" tone="blue" />
        <DetailStat label="최근 가격" value={formatPrice(latestPrice)} detail={`${pricedRows.length.toLocaleString("ko-KR")}개 가격 확인`} tone="violet" />
        <DetailStat label="판매 / 구매" value={`${supply.length} / ${demand.length}`} detail={`수량 ${quantityOf(supply)} / ${quantityOf(demand)}`} tone="green" />
        <DetailStat label="판매자" value={sellers.toLocaleString("ko-KR")} detail={prices.length ? `가격 범위 ${formatPrice(Math.min(...prices))}–${formatPrice(Math.max(...prices))}` : "가격 확인 가능한 관측 없음"} tone="amber" />
      </div>

      <div className="card-detail-chart"><PriceTrendChart rows={rows} /></div>

      <section className="recent-observations" aria-labelledby="recent-observations-title">
        <div className="detail-section-heading"><div><span className="eyebrow">최근 관측</span><h3 id="recent-observations-title">최근 거래글</h3></div><span>{Math.min(recentRows.length, 8)} / {recentRows.length}</span></div>
        {recentRows.length === 0 ? <div className="detail-empty">관측 데이터가 없습니다.</div> : <div className="detail-observations-wrap"><table><thead><tr><th>날짜</th><th>구분</th><th>가격</th><th>수량</th><th>작성자</th><th>원문</th></tr></thead><tbody>{recentRows.slice(0, 8).map((row) => <tr key={`${row.id}-${row.postUrl}`}><td>{formatDate(row.dateKey || row.postedAt)}</td><td><span className={`detail-intent ${row.listingType}`}>{intentLabel(row.listingType)}</span></td><td>{formatPrice(row.priceKrw)}{row.priceScope !== "per_card" && row.priceKrw != null ? <small className="detail-price-scope">{row.priceScope === "bundle" ? "묶음" : "수량 기준"}</small> : null}</td><td>{row.quantity.toLocaleString("ko-KR")}</td><td>{row.sellerName || "—"}</td><td>{row.postUrl ? <a href={row.postUrl} target="_blank" rel="noreferrer">열기 <ArrowUpRight size={12} /></a> : "—"}</td></tr>)}</tbody></table></div>}
      </section>
    </section>
  </div>
}

function DetailStat({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: string }) {
  return <article className={`detail-stat ${tone}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>
}

function quantityOf(rows: MarketRow[]) { return rows.reduce((total, row) => total + row.quantity, 0).toLocaleString("ko-KR") }
function formatPrice(value: number | null) { return value == null ? "—" : `${Math.round(value).toLocaleString("ko-KR")}원` }
function formatDate(value: string) { return value ? value.slice(0, 10).replaceAll("-", ".") : "—" }

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
function intentLabel(value: IntentFilter) { return value === "all" ? "전체" : value === "sell" ? "판매" : value === "buy" ? "구매" : value === "trade" ? "교환" : "미분류" }
