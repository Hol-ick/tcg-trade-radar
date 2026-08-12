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
  const contentType = response.headers.get("content-type") || ""
  let payload: unknown = null

  if (text && contentType.includes("json")) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    const error = payload as { error?: string } | null
    const message = error?.error || (contentType.includes("text/html") || [502, 503, 504].includes(response.status) ? "worker에 연결할 수 없습니다." : `API 요청 실패 (${response.status})`)
    throw new ApiError(message, response.status)
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

export async function downloadJobCsv(jobId: string, token: string) {
  const headers = new Headers({ Accept: "text/csv" })
  if (token.trim()) {
    headers.set("Authorization", `Bearer ${token.trim()}`)
  }
  const response = await fetch(`${baseUrl}/jobs/${encodeURIComponent(jobId)}/csv`, { headers })
  if (!response.ok) {
    const message = await response.text()
    throw new ApiError(message || `CSV 내보내기 실패 (${response.status})`, response.status)
  }
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = objectUrl
  anchor.download = `tcg-trade-radar-${jobId}.csv`
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}
