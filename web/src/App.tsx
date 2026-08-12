import { useEffect, useState } from "react"
import { Activity, ArrowDown, CircleHelp, ExternalLink, ShieldCheck, Sparkles } from "lucide-react"

import { CollectorForm } from "@/components/collector-form"
import { JobLogs } from "@/components/job-logs"
import { JobStatusCard } from "@/components/job-status"
import { ResultTable } from "@/components/result-table"
import { createJob, getHealth } from "@/lib/api"
import { useJobPolling } from "@/hooks/use-job-polling"
import type { JobRequest } from "@/lib/types"
import { DevPage } from "@/dev-page"

export function App() {
  if (window.location.pathname === "/dev") {
    return <DevPage />
  }

  return <Dashboard />
}

function Dashboard() {
  const [token, setToken] = useState("")
  const [jobId, setJobId] = useState<string | null>(null)
  const [health, setHealth] = useState<{ state: "checking" | "online" | "offline"; version?: string; message?: string }>({ state: "checking" })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const { job, logs, rows, error: pollingError, isPolling } = useJobPolling(jobId, token)

  useEffect(() => {
    getHealth()
      .then((payload) => setHealth({ state: "online", version: payload.version }))
      .catch((caught) => setHealth({ state: "offline", message: caught instanceof Error ? caught.message : "worker offline" }))
  }, [jobId])

  const startJob = async (request: JobRequest) => {
    setIsSubmitting(true)
    setSubmitError(null)
    try {
      const payload = await createJob(request, token)
      setJobId(payload.job_id || payload.id)
    } catch (caught) {
      setSubmitError(caught instanceof Error ? caught.message : "수집 작업을 시작하지 못했습니다.")
    } finally {
      setIsSubmitting(false)
    }
  }

  const isBusy = isSubmitting || isPolling

  return (
    <main className="min-h-svh overflow-hidden bg-[#0c141c] text-slate-100">
      <div className="radar-grid pointer-events-none fixed inset-0 opacity-60" />
      <header className="relative mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8 lg:px-10">
        <a href="#top" className="flex items-center gap-3" aria-label="TCG Trade Radar 홈">
          <div className="grid size-9 place-items-center rounded-xl bg-orange-400 text-slate-950 shadow-[0_0_30px_rgba(251,146,60,0.2)]"><Sparkles className="size-4" /></div>
          <div><div className="font-mono text-[10px] uppercase tracking-[0.25em] text-slate-500">TCG / TRADE RADAR</div><div className="font-semibold tracking-tight text-white">수집 관제판</div></div>
        </a>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <a href="/dev" className="rounded-full border border-cyan-300/20 px-2.5 py-1 text-cyan-200 hover:bg-cyan-300/10">DEV</a>
          <span className={`status-dot ${health.state === "online" ? "status-online" : health.state === "offline" ? "status-offline" : "status-checking"}`} />
          <span>{health.state === "online" ? `worker online · ${health.version || "ready"}` : health.state === "offline" ? "worker 연결 필요" : "worker 확인 중"}</span>
        </div>
      </header>

      <div id="top" className="relative mx-auto max-w-7xl px-5 pb-12 sm:px-8 lg:px-10">
        <section className="grid gap-10 pb-12 pt-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-end lg:pt-16">
          <div>
            <div className="mb-5 flex flex-wrap gap-2 text-xs font-medium">
              <span className="pill pill-orange"><Activity className="size-3" /> live collection</span>
              <span className="pill"><ShieldCheck className="size-3" /> public read-only</span>
              <span className="pill"><CircleHelp className="size-3" /> evidence first</span>
            </div>
            <h1 className="max-w-3xl text-4xl font-semibold leading-[1.04] tracking-[-0.05em] text-white sm:text-6xl">
              거래 글이 실제로<br /><span className="text-orange-300">읽히는지</span>, 먼저 확인합니다.
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-slate-400 sm:text-lg">
              갤러리별로 작은 수집 작업을 실행하고, HTTP 응답·파서 판정·추출 결과를 한 화면에서 확인하세요. 빈 결과도 실패로 숨기지 않습니다.
            </p>
            <div className="mt-8 flex items-center gap-2 text-xs text-slate-500"><ArrowDown className="size-4 text-orange-300" /> 아래에서 범위를 정하고 첫 샘플을 실행하세요</div>
          </div>
          <div className="evidence-note ml-auto max-w-md">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-orange-700">FIELD NOTE / 2026.08.12</div>
            <p className="mt-3 text-lg font-medium leading-snug text-slate-900">“200 OK”만으로는 수집 성공이 아닙니다. 목록 구조가 읽히고, 게시글이 파싱되고, 결과가 저장되는지까지 봅니다.</p>
            <div className="mt-5 flex items-center justify-between border-t border-slate-900/10 pt-3 text-xs text-slate-500"><span>diagnostic contract</span><span className="font-mono text-orange-700">v0.1</span></div>
          </div>
        </section>

        {(health.state === "offline" || submitError || pollingError) && (
          <div className="mb-5 rounded-xl border border-red-300/20 bg-red-300/10 px-4 py-3 text-sm text-red-100">
            {submitError || pollingError || `Worker가 아직 응답하지 않습니다. ${health.message || "먼저 Python API를 8787 포트에서 실행하세요."}`}
          </div>
        )}

        <section className="grid items-stretch gap-5 lg:grid-cols-[1.06fr_0.94fr]">
          <CollectorForm disabled={isBusy} token={token} onTokenChange={setToken} onSubmit={startJob} />
          <div className="flex min-w-0 flex-col gap-5">
            <JobStatusCard job={job} isPolling={isPolling} error={pollingError} />
            <JobLogs logs={logs} />
          </div>
        </section>

        <section className="mt-5"><ResultTable rows={rows} /></section>

        <footer className="mt-8 flex flex-col gap-3 border-t border-white/10 pt-5 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between">
          <span>Python worker · SQLite audit trail · React + shadcn/ui surface</span>
          <a href="https://github.com/Hol-ick/tcg-trade-radar" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-slate-300">source repository <ExternalLink className="size-3" /></a>
        </footer>
      </div>
    </main>
  )
}

export default App
