import { useEffect, useState } from "react"

import { getJob, getJobLogs, getJobResults } from "@/lib/api"
import type { JobLog, JobStatus, ResultRow } from "@/lib/types"

const TERMINAL_STATES = new Set(["completed", "failed"])

export function useJobPolling(jobId: string | null) {
  const [job, setJob] = useState<JobStatus | null>(null)
  const [logs, setLogs] = useState<JobLog[]>([])
  const [rows, setRows] = useState<ResultRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isPolling, setIsPolling] = useState(false)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    if (!jobId) {
      return () => { cancelled = true }
    }

    let firstTick = true
    const tick = async () => {
      if (cancelled) return
      setIsPolling(true)
      try {
        const [nextJob, nextLogs] = await Promise.all([getJob(jobId), getJobLogs(jobId)])
        if (cancelled) return
        if (firstTick) { setRows([]); firstTick = false }
        setJob(nextJob); setLogs(nextLogs.logs || []); setError(null)
        if (TERMINAL_STATES.has(nextJob.state)) {
          try { const result = await getJobResults(jobId); if (!cancelled) setRows(result.rows || []) } catch (caught) { if (!cancelled) setError(caught instanceof Error ? caught.message : "결과를 읽지 못했습니다.") }
          if (!cancelled) setIsPolling(false)
          return
        }
        timer = setTimeout(() => void tick(), 1200)
      } catch (caught) {
        if (!cancelled) { setError(caught instanceof Error ? caught.message : "작업 상태를 읽지 못했습니다."); setIsPolling(false) }
      }
    }
    void tick()
    return () => { cancelled = true; if (timer) clearTimeout(timer) }
  }, [jobId])

  return { job, logs, rows, error, isPolling }
}
