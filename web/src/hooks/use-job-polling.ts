import { useEffect, useState } from "react"

import { getJob, getJobLogs, getJobResults } from "@/lib/api"
import type { JobLog, JobStatus, ResultRow } from "@/lib/types"

const TERMINAL_STATES = new Set(["completed", "failed"])

export function useJobPolling(jobId: string | null, token: string) {
  const [job, setJob] = useState<JobStatus | null>(null)
  const [logs, setLogs] = useState<JobLog[]>([])
  const [rows, setRows] = useState<ResultRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isPolling, setIsPolling] = useState(false)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    if (!jobId) {
      return () => {
        cancelled = true
      }
    }

    const tick = async () => {
      setIsPolling(true)
      try {
        const [nextJob, nextLogs] = await Promise.all([
          getJob(jobId, token),
          getJobLogs(jobId, token),
        ])
        if (cancelled) return

        setJob(nextJob)
        setLogs(nextLogs.logs || [])
        setError(null)

        if (TERMINAL_STATES.has(nextJob.state)) {
          try {
            const result = await getJobResults(jobId, token)
            if (!cancelled) setRows(result.rows || [])
          } catch {
            // A failed job can legitimately have no result payload.
          }
          if (!cancelled) setIsPolling(false)
          return
        }

        timer = setTimeout(tick, 1200)
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "작업 상태를 읽지 못했습니다.")
          setIsPolling(false)
        }
      }
    }

    void tick()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [jobId, token])

  return { job, logs, rows, error, isPolling }
}
