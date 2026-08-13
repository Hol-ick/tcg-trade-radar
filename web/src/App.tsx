import { useEffect, useMemo, useState } from "react"
import { ArrowLeft, ArrowRight, ExternalLink, RefreshCw } from "lucide-react"

import { DevPage } from "@/dev-page"
import { ResultTable } from "@/components/result-table"
import { GALLERY_PRESETS } from "@/lib/types"
import { loadWeekSnapshot, snapshotCsvUrl } from "@/lib/snapshot"
import { formatRange, getCurrentWeekRange, isCurrentOrFuture, rangeFromSince, shiftWeek, type WeekRange } from "@/lib/week-range"
import type { SnapshotState } from "@/lib/types"

export default function App() {
  const isDevPage = window.location.pathname.endsWith("/dev") || window.location.pathname.endsWith("/dev/") || new URLSearchParams(window.location.search).get("page") === "dev"
  return isDevPage ? <DevPage /> : <WeeklyConsole />
}

export function WeeklyConsole({ dev = false }: { dev?: boolean }) {
  const currentRange = useMemo(() => getCurrentWeekRange(), [])
  const params = useMemo(() => new URLSearchParams(window.location.search), [])
  const initialRange = rangeFromSince(params.get("since") || "") || currentRange
  const initialGallery = GALLERY_PRESETS.some((gallery) => gallery.id === params.get("gallery")) ? params.get("gallery")! : GALLERY_PRESETS[0].id
  const [range, setRange] = useState<WeekRange>(initialRange)
  const [galleryId, setGalleryId] = useState(initialGallery)
  const [snapshotState, setSnapshotState] = useState<SnapshotState>({ kind: "loading" })
  const [loadedKey, setLoadedKey] = useState("")

  const gallery = GALLERY_PRESETS.find((item) => item.id === galleryId) || GALLERY_PRESETS[0]
  const isNextDisabled = isCurrentOrFuture(range)

  const syncUrl = (nextRange: WeekRange, nextGallery = galleryId) => {
    const url = new URL(window.location.href)
    url.searchParams.set("since", nextRange.since)
    url.searchParams.set("gallery", nextGallery)
    window.history.replaceState(null, "", url)
  }

  const selectionKey = `${galleryId}:${range.since}`

  useEffect(() => {
    const url = new URL(window.location.href)
    url.searchParams.set("since", range.since)
    url.searchParams.set("gallery", galleryId)
    window.history.replaceState(null, "", url)
    let active = true
    loadWeekSnapshot(range, galleryId).then((nextState) => {
      if (active) {
        setSnapshotState(nextState)
        setLoadedKey(selectionKey)
      }
    })
    return () => {
      active = false
    }
  }, [range, galleryId, selectionKey])

  const moveWeek = (direction: -1 | 1) => {
    if (direction === 1 && isNextDisabled) return
    setRange(shiftWeek(range, direction))
  }

  const selectGallery = (nextGallery: string) => {
    setGalleryId(nextGallery)
    syncUrl(range, nextGallery)
  }

  const visibleState = loadedKey === selectionKey ? snapshotState : { kind: "loading" as const }
  const snapshot = visibleState.kind === "ready" || visibleState.kind === "missing" ? visibleState.snapshot : null
  const rowCount = snapshot?.row_count ?? 0
  const reviewCount = snapshot?.review_count ?? 0

  return (
    <main className="app-shell" id="top">
      <header className="topbar">
        <a className="brand" href={import.meta.env.BASE_URL} aria-label="TCG 수집 홈">
          <span className="brand-mark">TCG</span>
          <span>수집 목록</span>
        </a>
        {dev ? <span className="dev-tag">DEV</span> : <span className="source-state">정적 주간 스냅샷</span>}
      </header>

      <div className="content-wrap">
        <section className="control-panel" aria-labelledby="page-title">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">주간 수집</p>
              <h1 id="page-title">거래글을 주 단위로 확인합니다.</h1>
            </div>
            <a className="text-link" href={gallery.url} target="_blank" rel="noreferrer">
              원본 게시판 <ExternalLink size={15} aria-hidden="true" />
            </a>
          </div>

          <div className="control-grid">
            <label className="field-label" htmlFor="gallery-select">
              수집 대상
              <select id="gallery-select" value={galleryId} onChange={(event) => selectGallery(event.target.value)}>
                {GALLERY_PRESETS.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>

            <div className="week-control" aria-label="주간 범위 선택">
              <span className="field-label">조회 기간</span>
              <div className="week-buttons">
                <button className="icon-button" type="button" aria-label="이전 주" onClick={() => moveWeek(-1)}><ArrowLeft size={17} /></button>
                <strong>{formatRange(range)}</strong>
                <button className="icon-button" type="button" aria-label="다음 주" disabled={isNextDisabled} onClick={() => moveWeek(1)}><ArrowRight size={17} /></button>
                <button className="secondary-button" type="button" onClick={() => setRange(currentRange)} disabled={range.since === currentRange.since}>이번 주</button>
              </div>
            </div>

            <div className="action-field">
              <span className="field-label">수집 작업</span>
              <a className="primary-button" href="https://github.com/Hol-ick/tcg-trade-radar/actions/workflows/collect-week.yml" target="_blank" rel="noreferrer">
                주간 수집 실행 <ExternalLink size={15} aria-hidden="true" />
              </a>
            </div>
          </div>
        </section>

        <section className="summary-row" aria-label="수집 요약">
          <SummaryCell label="기간" value={formatRange(range)} />
          <SummaryCell label="거래 행" value={`${rowCount}건`} accent="blue" />
          <SummaryCell label="검토 필요" value={`${reviewCount}건`} accent="amber" />
          <SummaryCell label="상태" value={visibleState.kind === "ready" ? "확인 가능" : visibleState.kind === "loading" ? "읽는 중" : visibleState.kind === "missing" ? "수집 대기" : "읽기 실패"} accent="green" />
        </section>

        {visibleState.kind === "error" && <div className="notice error" role="alert">{visibleState.message}</div>}
        {visibleState.kind === "missing" && (
          <div className="notice" role="status">
            <div><strong>이 기간의 수집 데이터가 없습니다.</strong><span>위의 주간 수집 실행에서 같은 기간을 선택해 스냅샷을 만들 수 있습니다.</span></div>
            <RefreshCw size={18} aria-hidden="true" />
          </div>
        )}

        <ResultTable rows={snapshot?.rows || []} isLoading={visibleState.kind === "loading"} downloadUrl={snapshot && rowCount > 0 ? snapshotCsvUrl(range, galleryId) : undefined} />
        <footer className="footer-note">원본 게시글을 읽어 저장한 주간 결과만 표시합니다. 수집 실행은 일회성 작업으로 처리됩니다.</footer>
      </div>
    </main>
  )
}

function SummaryCell({ label, value, accent = "" }: { label: string; value: string; accent?: string }) {
  return <div className={`summary-cell ${accent}`}><span>{label}</span><strong>{value}</strong></div>
}
