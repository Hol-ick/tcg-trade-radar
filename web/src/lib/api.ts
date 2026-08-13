import type { HealthResponse, JobLog, JobRequest, JobStatus, ResultRow, SellerSummary } from "./types"

const baseUrl = (import.meta.env.VITE_WORKER_URL || "/api").replace(/\/$/, "")

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set("Accept", "application/json")
  if (init.body) headers.set("Content-Type", "application/json")
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers })
  const text = await response.text()
  const contentType = response.headers.get("content-type") || ""
  let payload: unknown = null
  if (text && contentType.includes("json")) {
    try { payload = JSON.parse(text) } catch { payload = null }
  }
  if (!response.ok) {
    const error = payload as { error?: string } | null
    const message = error?.error || (contentType.includes("text/html") || [502, 503, 504].includes(response.status) ? "수집 워커에 연결할 수 없습니다." : `수집 요청 실패 (${response.status})`)
    throw new ApiError(message, response.status)
  }
  return payload as T
}

export function getHealth() { return request<HealthResponse>("/health") }
export function createJob(payload: JobRequest) { return request<{ job_id: string; id: string }>("/jobs", { method: "POST", body: JSON.stringify(payload) }) }
export function getJob(jobId: string) { return request<JobStatus>(`/jobs/${encodeURIComponent(jobId)}`) }
export function getJobLogs(jobId: string) { return request<{ job_id: string; logs: JobLog[] }>(`/jobs/${encodeURIComponent(jobId)}/logs?limit=500`) }
export function getJobResults(jobId: string) { return request<{ job_id: string; rows: ResultRow[] }>(`/jobs/${encodeURIComponent(jobId)}/results`) }
export function getSellers(gameId: string) { return request<{ sellers: SellerSummary[] }>(`/market/sellers?game_id=${encodeURIComponent(gameId)}&limit=100`) }

export async function downloadJobCsv(jobId: string) {
  const response = await fetch(`${baseUrl}/jobs/${encodeURIComponent(jobId)}/csv`, { headers: { Accept: "text/csv" } })
  if (!response.ok) throw new ApiError(`CSV 저장 실패 (${response.status})`, response.status)
  const objectUrl = URL.createObjectURL(await response.blob())
  const anchor = document.createElement("a")
  anchor.href = objectUrl
  anchor.download = `tcg-trade-radar-${jobId}.csv`
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}
