import { useEffect, useMemo, useState } from "react"
import { ArrowLeft, ArrowRight, ExternalLink, Play } from "lucide-react"

import { DevPage } from "@/dev-page"
import { MarketExplorer } from "@/market-explorer"
import { ResultTable } from "@/components/result-table"
import { SellerPanel } from "@/components/seller-panel"
import { createJob, downloadJobCsv, getHealth, getSellers } from "@/lib/api"
import { useJobPolling } from "@/hooks/use-job-polling"
import { GALLERY_PRESETS } from "@/lib/types"
import { getCurrentWeekRange, isCurrentOrFuture, shiftWeek, type WeekRange } from "@/lib/week-range"

const COLLECTION_SUBJECTS = ["판매", "구매", "교환", "판매/교환"]

export default function App() {
  const page = new URLSearchParams(window.location.search).get("page")
  const isCollector = window.location.pathname.endsWith("/dev") || window.location.pathname.endsWith("/dev/") || page === "dev" || page === "collector"
  return isCollector ? <DevPage /> : <MarketExplorer />
}

export function LiveConsole({ dev = false }: { dev?: boolean }) {
  const currentRange = useMemo(() => getCurrentWeekRange(), [])
  const [galleryId, setGalleryId] = useState(GALLERY_PRESETS[0].id)
  const [range, setRange] = useState<WeekRange>(currentRange)
  const [maxPosts, setMaxPosts] = useState("50")
  const [maxPages, setMaxPages] = useState("5")
  const [delay, setDelay] = useState("0.5")
  const [jobId, setJobId] = useState<string | null>(null)
  const [health, setHealth] = useState<"checking" | "online" | "offline">(import.meta.env.DEV ? "checking" : "offline")
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [sellers, setSellers] = useState<import("@/lib/types").SellerSummary[]>([])
  const { job, logs, rows, error, isPolling } = useJobPolling(jobId)

  const gallery = GALLERY_PRESETS.find((item) => item.id === galleryId) || GALLERY_PRESETS[0]
  const activeJob = job?.id === jobId ? job : null
  const visibleRows = activeJob ? rows : []
  const isBusy = isSubmitting || isPolling
  const isNextDisabled = isCurrentOrFuture(range)
  const visibleError = submitError || error

  useEffect(() => {
    if (!import.meta.env.DEV) return
    getHealth().then(() => setHealth("online")).catch(() => setHealth("offline"))
  }, [])
  useEffect(() => {
    if (activeJob?.state !== "completed") return
    getSellers(gallery.id).then((payload) => setSellers(payload.sellers)).catch(() => setSellers([]))
  }, [activeJob?.state, gallery.id])

  const moveRange = (direction: -1 | 1) => {
    if (direction === 1 && isNextDisabled) return
    setRange(shiftWeek(range, direction))
  }

  const startCollection = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitError(null)
    setIsSubmitting(true)
    try {
      const payload = await createJob({
        gallery_id: gallery.id,
        gallery_url: gallery.url,
        subject: gallery.subject,
        subjects: COLLECTION_SUBJECTS,
        since: range.since,
        until: range.until,
        max_posts: clampNumber(maxPosts, 1, 200, 50),
        max_pages: clampNumber(maxPages, 1, 20, 5),
        delay: clampNumber(delay, 0, 30, 0.5),
        buy_rate: 60,
        keep_raw: true,
        review_unmatched: true,
      })
      setJobId(payload.job_id || payload.id)
    } catch (caught) {
      setSubmitError(caught instanceof Error ? caught.message : "수집을 시작하지 못했습니다.")
    } finally { setIsSubmitting(false) }
  }

  const exportCsv = async () => {
    if (!jobId) return
    try { await downloadJobCsv(jobId) } catch (caught) { setSubmitError(caught instanceof Error ? caught.message : "CSV를 저장하지 못했습니다.") }
  }

  return (
    <main className="app-shell" id="top">
      <header className="topbar">
        <a className="brand" href={import.meta.env.BASE_URL} aria-label="TCG 수집 홈"><span className="brand-mark">TCG</span><span>수집 관제판</span></a>
        <span className={`source-state ${health === "offline" ? "offline" : ""}`}>{dev ? "DEV · " : ""}{health === "online" ? "워커 연결됨" : health === "offline" ? "워커 연결 필요" : "워커 확인 중"}</span>
      </header>

      <div className="content-wrap">
        <form className="control-panel" onSubmit={startCollection}>
          <div className="panel-heading">
            <div><p className="eyebrow">실제 수집</p><h1 id="page-title">거래글을 직접 수집합니다.</h1></div>
            <a className="text-link" href={gallery.url} target="_blank" rel="noreferrer">원본 게시판 <ExternalLink size={15} aria-hidden="true" /></a>
          </div>

          <div className="control-grid live-controls">
            <label className="field-label" htmlFor="gallery-select">게임<select id="gallery-select" value={galleryId} disabled={isBusy} onChange={(event) => setGalleryId(event.target.value)}>{GALLERY_PRESETS.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <div className="range-control"><span className="field-label">조회 기간</span><div className="range-buttons"><button className="icon-button" type="button" aria-label="이전 기간" disabled={isBusy} onClick={() => moveRange(-1)}><ArrowLeft size={17} /></button><strong>{formatRange(range)}</strong><button className="icon-button" type="button" aria-label="다음 기간" disabled={isBusy || isNextDisabled} onClick={() => moveRange(1)}><ArrowRight size={17} /></button><button className="secondary-button" type="button" disabled={isBusy || range.since === currentRange.since} onClick={() => setRange(currentRange)}>최근 기간</button></div></div>
            <div className="action-field"><span className="field-label">실행</span><button className="primary-button" type="submit" disabled={isBusy}><Play size={15} aria-hidden="true" /> {isBusy ? "수집 중" : "수집 시작"}</button></div>
          </div>
          <div className="collector-options"><NumberField id="max-posts" label="최근 게시글 수" value={maxPosts} onChange={setMaxPosts} disabled={isBusy} min="1" max="200" /><NumberField id="max-pages" label="확인할 페이지 수" value={maxPages} onChange={setMaxPages} disabled={isBusy} min="1" max="20" /><NumberField id="delay" label="요청 간격 (초)" value={delay} onChange={setDelay} disabled={isBusy} min="0" max="30" step="0.1" /></div>
        </form>

        {visibleError && <div className="notice error" role="alert">{visibleError}</div>}
        {health === "offline" && !visibleError && <div className="notice" role="status">로컬 수집 워커를 먼저 실행하세요.</div>}
        <LiveStatus job={activeJob} logs={logs} />
        <ResultTable rows={visibleRows} isLoading={isPolling && visibleRows.length === 0} onDownloadCsv={activeJob?.state === "completed" ? exportCsv : undefined} />
        {activeJob?.state === "completed" && <SellerPanel sellers={sellers} />}
      </div>
    </main>
  )
}

function LiveStatus({ job, logs }: { job: ReturnType<typeof useJobPolling>["job"]; logs: ReturnType<typeof useJobPolling>["logs"] }) {
  const counts = job?.counts || {}
  return <section className="job-panel" aria-labelledby="job-status-title"><div className="job-heading"><div><p className="eyebrow">수집 상태</p><h2 id="job-status-title">{stateLabel(job?.state || "idle")}</h2></div><span className="job-counts">원문 {counts.sources || 0} · 결과 {counts.rows || 0} · 댓글 {counts.comments || 0}</span></div>{logs.length === 0 ? <div className="empty-state compact">수집을 시작하면 단계별 로그가 표시됩니다.</div> : <div className="log-list">{logs.slice(-80).map((log, index) => <div className={`log-row ${log.level}`} key={`${log.created_at}-${index}`}><span>{log.step}</span><strong>{log.message}</strong></div>)}</div>}</section>
}

function NumberField({ id, label, value, onChange, disabled, min, max, step }: { id: string; label: string; value: string; onChange: (value: string) => void; disabled: boolean; min: string; max: string; step?: string }) {
  return <label className="field-label" htmlFor={id}>{label}<input id={id} type="number" value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} min={min} max={max} step={step} /></label>
}

function clampNumber(value: string, min: number, max: number, fallback: number) { const parsed = Number(value); return Number.isFinite(parsed) ? Math.max(min, Math.min(max, parsed)) : fallback }
function formatRange(range: WeekRange) { return `${range.since.replaceAll("-", ".")} — ${range.until.replaceAll("-", ".")}` }
function stateLabel(state: string) { if (state === "queued") return "대기 중"; if (state === "running") return "수집 중"; if (state === "completed") return "수집 완료"; if (state === "failed") return "수집 실패"; return "대기" }
