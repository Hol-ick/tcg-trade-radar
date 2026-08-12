import { CheckCircle2, CircleAlert, LoaderCircle, Timer } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import type { JobStatus } from "@/lib/types"

type JobStatusCardProps = { job: JobStatus | null; isPolling: boolean; error: string | null }

const stateMeta = {
  queued: { label: "대기 중", className: "bg-slate-500/20 text-slate-300", icon: Timer },
  running: { label: "수집 중", className: "bg-cyan-300/15 text-cyan-200", icon: LoaderCircle },
  completed: { label: "완료", className: "bg-emerald-300/15 text-emerald-200", icon: CheckCircle2 },
  failed: { label: "실패", className: "bg-red-300/15 text-red-200", icon: CircleAlert },
}

export function JobStatusCard({ job, isPolling, error }: JobStatusCardProps) {
  const state = job ? stateMeta[job.state] : null
  const StateIcon = state?.icon
  const counts = job?.counts || {}
  const isActive = Boolean(job && (job.state === "queued" || job.state === "running"))

  return (
    <Card className="ink-panel border-0 shadow-none">
      <CardHeader className="flex flex-row items-center justify-between border-b border-white/10 px-5 py-4 sm:px-6">
        <CardTitle className="text-lg text-white">실행 상태</CardTitle>
        {state && StateIcon ? <Badge className={state.className}><StateIcon className={`size-3.5 ${job?.state === "running" ? "animate-spin" : ""}`} />{state.label}</Badge> : <Badge className="bg-white/10 text-slate-400">대기</Badge>}
      </CardHeader>
      <CardContent className="space-y-4 px-5 py-5 sm:px-6">
        {error && <div className="rounded-lg border border-red-300/20 bg-red-300/10 p-3 text-sm text-red-100">{error}</div>}
        {job?.error_message && <div className="rounded-lg border border-red-300/20 bg-red-300/10 p-3 text-sm text-red-100">{job.error_message}</div>}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Metric label="sources" value={counts.sources || 0} />
          <Metric label="rows" value={counts.rows || 0} />
          <Metric label="comments" value={counts.comments || 0} />
          <Metric label="review" value={counts.needs_review || 0} />
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-500"><span>{job ? `job ${job.id.slice(0, 8)}` : "작업 전"}</span><span>{isPolling ? "확인 중" : state?.label || "대기"}</span></div>
          <Progress value={job?.state === "completed" || job?.state === "failed" ? 100 : isActive ? 55 : 0} className="bg-white/10 [&_[data-slot=progress-indicator]]:bg-orange-300" />
        </div>
        <div className="grid gap-2 text-xs text-slate-500 sm:grid-cols-2"><p>worker: <span className="text-slate-300">{job?.worker_version || "연결 대기"}</span></p><p className="sm:text-right">완료: <span className="text-slate-300">{formatDate(job?.finished_at)}</span></p></div>
      </CardContent>
    </Card>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="rounded-xl border border-white/10 bg-white/[0.035] p-3"><div className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">{label}</div><div className="mt-1 text-2xl font-semibold tracking-tight text-white">{value.toLocaleString()}</div></div>
}

function formatDate(value?: string | null) {
  if (!value) return "—"
  return new Date(value).toLocaleString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}
