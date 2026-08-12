import { useEffect, useState } from "react"
import { ArrowLeft, CheckCircle2, Code2, ExternalLink, FlaskConical, Server, ShieldCheck } from "lucide-react"

import { CollectorForm } from "@/components/collector-form"
import { JobLogs } from "@/components/job-logs"
import { JobStatusCard } from "@/components/job-status"
import { ResultTable } from "@/components/result-table"
import { createJob, getHealth } from "@/lib/api"
import { useJobPolling } from "@/hooks/use-job-polling"
import type { JobRequest } from "@/lib/types"

export function DevPage() {
  const [token, setToken] = useState("")
  const [jobId, setJobId] = useState<string | null>(null)
  const [health, setHealth] = useState("checking")
  const [submitError, setSubmitError] = useState<string | null>(null)
  const { job, logs, rows, error, isPolling } = useJobPolling(jobId, token)

  useEffect(() => {
    getHealth().then(() => setHealth("online")).catch(() => setHealth("offline"))
  }, [])

  const startProbe = async (request: JobRequest) => {
    setSubmitError(null)
    try {
      const response = await createJob(request, token)
      setJobId(response.job_id || response.id)
    } catch (caught) {
      setSubmitError(caught instanceof Error ? caught.message : "dev 수집을 시작하지 못했습니다.")
    }
  }

  return (
    <main className="min-h-svh overflow-hidden bg-[#0c141c] text-slate-100">
      <div className="radar-grid pointer-events-none fixed inset-0 opacity-60" />
      <header className="relative mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8 lg:px-10">
        <a href="/" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white"><ArrowLeft className="size-4" /> 관제판으로 돌아가기</a>
        <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-orange-300"><FlaskConical className="size-4" /> dev probe</div>
      </header>

      <div className="relative mx-auto max-w-7xl px-5 pb-12 sm:px-8 lg:px-10">
        <section className="grid gap-6 pb-10 pt-10 lg:grid-cols-[1.1fr_.9fr] lg:items-end">
          <div>
            <div className="eyebrow mb-4 text-cyan-300">DEVELOPMENT SURFACE / LIVE SOURCE CHECK</div>
            <h1 className="max-w-3xl text-4xl font-semibold leading-[1.04] tracking-[-0.05em] text-white sm:text-6xl">수집기가 지금도<br /><span className="text-cyan-300">읽을 수 있는지</span> 검증합니다.</h1>
            <p className="mt-5 max-w-2xl text-base leading-relaxed text-slate-400">개발용 페이지는 수집기를 숨기지 않습니다. 소스 응답, 목록 행 수, 게시글 파싱, 저장 결과를 worker 로그로 확인하고 실패하면 원인을 그대로 남깁니다.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1">
            <ProbeFact icon={<Server className="size-4" />} label="worker" value={health} />
            <ProbeFact icon={<ShieldCheck className="size-4" />} label="scope" value="public read-only" />
            <ProbeFact icon={<Code2 className="size-4" />} label="route" value="/dev" />
          </div>
        </section>

        {(submitError || error) && <div className="mb-5 rounded-xl border border-red-300/20 bg-red-300/10 px-4 py-3 text-sm text-red-100">{submitError || error}</div>}

        <section className="grid items-stretch gap-5 lg:grid-cols-[1.06fr_.94fr]">
          <CollectorForm disabled={isPolling} token={token} onTokenChange={setToken} onSubmit={startProbe} />
          <div className="flex min-w-0 flex-col gap-5"><JobStatusCard job={job} isPolling={isPolling} error={error} /><JobLogs logs={logs} /></div>
        </section>
        <section className="mt-5"><ResultTable rows={rows} /></section>

        <div className="mt-8 flex flex-col gap-3 border-t border-white/10 pt-5 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between">
          <span className="inline-flex items-center gap-2"><CheckCircle2 className="size-3.5 text-emerald-300" /> diagnostics remain visible on empty or changed responses</span>
          <a href="/" className="inline-flex items-center gap-1 hover:text-slate-300">main console <ExternalLink className="size-3" /></a>
        </div>
      </div>
    </main>
  )
}

function ProbeFact({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.035] px-4 py-3"><span className="text-cyan-300">{icon}</span><span className="min-w-0"><span className="block font-mono text-[10px] uppercase tracking-[0.15em] text-slate-600">{label}</span><span className="block truncate text-sm text-slate-300">{value}</span></span></div>
}
