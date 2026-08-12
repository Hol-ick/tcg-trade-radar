import type {
  HealthResponse,
  JobLog,
  JobRequest,
  JobStatus,
  ResultRow,
} from "@/lib/types"

const baseUrl = (import.meta.env.VITE_WORKER_URL || "/api").replace(/\/$/, "")

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function request<T>(path: string, token = "", init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  headers.set("Accept", "application/json")
  if (init.body) {
    headers.set("Content-Type", "application/json")
  }
  if (token.trim()) {
    headers.set("Authorization", `Bearer ${token.trim()}`)
  }

  const response = await fetch(`${baseUrl}${path}`, { ...init, headers })
  const text = await response.text()
  let payload: unknown = null

  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = { error: text }
    }
  }

  if (!response.ok) {
    const error = payload as { error?: string } | null
    throw new ApiError(error?.error || `API 요청 실패 (${response.status})`, response.status)
  }

  return payload as T
}

export function getHealth() {
  return request<HealthResponse>("/health")
}

export function createJob(payload: JobRequest, token: string) {
  return request<{ job_id: string; id: string }>("/jobs", token, {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export function getJob(jobId: string, token: string) {
  return request<JobStatus>(`/jobs/${encodeURIComponent(jobId)}`, token)
}

export function getJobLogs(jobId: string, token: string) {
  return request<{ job_id: string; logs: JobLog[] }>(
    `/jobs/${encodeURIComponent(jobId)}/logs?limit=500`,
    token
  )
}

export function getJobResults(jobId: string, token: string) {
  return request<{ job_id: string; rows: ResultRow[] }>(
    `/jobs/${encodeURIComponent(jobId)}/results`,
    token
  )
}
