import { useEffect, useState } from "react"
import { ExternalLink, Radar } from "lucide-react"

import { CollectorForm } from "@/components/collector-form"
import { JobLogs } from "@/components/job-logs"
import { JobStatusCard } from "@/components/job-status"
import { ResultTable } from "@/components/result-table"
import { createJob, getHealth } from "@/lib/api"
import { useJobPolling } from "@/hooks/use-job-polling"
import type { JobRequest } from "@/lib/types"
import { DevPage } from "@/dev-page"

export function App() {
  const isDevPage =
    window.location.pathname === "/dev" ||
    window.location.pathname.endsWith("/dev/") ||
    new URLSearchParams(window.location.search).get("page") === "dev"

  return isDevPage ? <DevPage /> : <Dashboard />
}

function Dashboard() {
  const [token, setToken] = useState("")
  const [jobId, setJobId] = useState<string | null>(null)
  const [health, setHealth] = useState<HealthState>({ state: "checking" })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const { job, logs, rows, error: pollingError, isPolling } = useJobPolling(jobId, token)

  useEffect(() => {
    getHealth()
      .then((payload) => setHealth({ state: "online", version: payload.version }))
      .catch((caught) =>
        setHealth({
          state: "offline",
          message: caught instanceof Error ? caught.message : "worker에 연결할 수 없습니다.",
        }),
      )
  }, [])

  const startJob = async (request: JobRequest) => {
    setIsSubmitting(true)
    setSubmitError(null)
    try {
      const payload = await createJob(request, token)
      setJobId(payload.job_id || payload.id)
    } catch (caught) {
      setSubmitError(caught instanceof Error ? caught.message : "수집을 시작하지 못했습니다.")
    } finally {
      setIsSubmitting(false)
    }
  }

  const isBusy = isSubmitting || isPolling
  const visibleError = submitError || pollingError || (health.state === "offline" ? health.message : null)

  return (
    <main className="min-h-svh bg-[#0c141c] text-slate-100">
      <Header health={health} />
      <div className="mx-auto max-w-7xl px-5 pb-10 pt-5 sm:px-8 lg:px-10">
        {visibleError && <ConnectionNotice message={visibleError} />}

        <section className="grid items-stretch gap-5 lg:grid-cols-[1.06fr_0.94fr]">
          <CollectorForm disabled={isBusy} token={token} onTokenChange={setToken} onSubmit={startJob} />
          <div className="flex min-w-0 flex-col gap-5">
            <JobStatusCard job={job} isPolling={isPolling} error={pollingError} />
            <JobLogs logs={logs} />
          </div>
        </section>

        <section className="mt-5">
          <ResultTable rows={rows} />
        </section>
      </div>
    </main>
  )
}

type HealthState = {
  state: "checking" | "online" | "offline"
  version?: string
  message?: string
}

function Header({ health }: { health: HealthState }) {
  const devUrl = `${import.meta.env.BASE_URL}dev/`
  const statusLabel =
    health.state === "online"
      ? `worker 연결됨 · ${health.version || "ready"}`
      : health.state === "offline"
        ? "worker 연결 필요"
        : "worker 확인 중"

  return (
    <header className="border-b border-white/10 bg-[#0c141c]/95">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 sm:px-8 lg:px-10">
        <a href="#top" className="flex items-center gap-3" aria-label="TCG Trade Radar 홈">
          <span className="grid size-8 place-items-center rounded-lg bg-orange-400 text-slate-950">
            <Radar className="size-4" />
          </span>
          <span className="font-semibold tracking-tight text-white">수집 관제판</span>
        </a>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <a href={devUrl} className="rounded-md border border-cyan-300/20 px-2 py-1 text-cyan-200 hover:bg-cyan-300/10">
            DEV
          </a>
          <span className={`status-dot ${health.state === "online" ? "status-online" : health.state === "offline" ? "status-offline" : "status-checking"}`} />
          <span>{statusLabel}</span>
        </div>
      </div>
    </header>
  )
}

function ConnectionNotice({ message }: { message: string }) {
  return (
    <div className="mb-5 flex items-center justify-between gap-4 rounded-lg border border-red-300/20 bg-red-300/10 px-4 py-3 text-sm text-red-100">
      <span>{message}</span>
      <a href="https://github.com/Hol-ick/tcg-trade-radar#tcg-trade-radar-web-ui" target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-1 text-xs text-red-200 underline underline-offset-4">
        실행 방법 <ExternalLink className="size-3" />
      </a>
    </div>
  )
}

export default App
