import { useEffect, useState } from "react"
import { ArrowLeft } from "lucide-react"

import { CollectorForm } from "@/components/collector-form"
import { JobLogs } from "@/components/job-logs"
import { JobStatusCard } from "@/components/job-status"
import { ResultTable } from "@/components/result-table"
import { createJob, downloadJobCsv, getHealth } from "@/lib/api"
import { useJobPolling } from "@/hooks/use-job-polling"
import type { JobRequest } from "@/lib/types"

export function DevPage() {
  const [token, setToken] = useState("")
  const [jobId, setJobId] = useState<string | null>(null)
  const [health, setHealth] = useState<"checking" | "online" | "offline">("checking")
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isExporting, setIsExporting] = useState(false)
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
      setSubmitError(caught instanceof Error ? caught.message : "수집을 시작하지 못했습니다.")
    }
  }

  const exportCsv = async () => {
    if (!jobId) return
    setIsExporting(true)
    setSubmitError(null)
    try {
      await downloadJobCsv(jobId, token)
    } catch (caught) {
      setSubmitError(caught instanceof Error ? caught.message : "CSV를 저장하지 못했습니다.")
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <main className="min-h-svh bg-[#0c141c] text-slate-100">
      <header className="border-b border-white/10 bg-[#0c141c]/95">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 sm:px-8 lg:px-10">
          <a href={import.meta.env.BASE_URL} className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white">
            <ArrowLeft className="size-4" /> 관제판
          </a>
          <span className={`text-xs ${health === "online" ? "text-emerald-300" : health === "offline" ? "text-red-300" : "text-slate-500"}`}>
            {health === "online" ? "worker 연결됨" : health === "offline" ? "worker 연결 필요" : "worker 확인 중"}
          </span>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-5 pb-10 pt-5 sm:px-8 lg:px-10">
        {(submitError || error || health === "offline") && (
          <div className="mb-5 rounded-lg border border-red-300/20 bg-red-300/10 px-4 py-3 text-sm text-red-100">
            {submitError || error || "worker에 연결할 수 없습니다. 로컬 worker를 먼저 실행하세요."}
          </div>
        )}

        <section className="grid items-stretch gap-5 lg:grid-cols-[1.06fr_0.94fr]">
          <CollectorForm disabled={isPolling} token={token} onTokenChange={setToken} onSubmit={startProbe} />
          <div className="flex min-w-0 flex-col gap-5">
            <JobStatusCard job={job} isPolling={isPolling} error={error} />
            <JobLogs logs={logs} />
          </div>
        </section>
        <section className="mt-5">
          <ResultTable rows={rows} onDownloadCsv={isExporting ? undefined : exportCsv} />
        </section>
      </div>
    </main>
  )
}
