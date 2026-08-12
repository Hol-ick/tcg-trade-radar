import type { ResultRow, SnapshotState, WeekSnapshot } from "./types"
import type { WeekRange } from "./week-range"

const EMPTY_SNAPSHOT = (range: WeekRange, galleryId: string): WeekSnapshot => ({
  since: range.since,
  until: range.until,
  generated_at: "",
  gallery_id: galleryId,
  row_count: 0,
  review_count: 0,
  rows: [],
})

export async function loadWeekSnapshot(range: WeekRange, galleryId: string): Promise<SnapshotState> {
  const base = import.meta.env.BASE_URL.endsWith("/") ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`
  const url = `${base}data/weeks/${encodeURIComponent(galleryId)}/${range.since}.json`

  try {
    const response = await fetch(url, { cache: "no-store" })
    const contentType = response.headers.get("content-type") || ""
    if (response.status === 404 || !contentType.includes("application/json")) return { kind: "missing", snapshot: EMPTY_SNAPSHOT(range, galleryId) }
    if (!response.ok) throw new Error(`스냅샷을 읽지 못했습니다. (${response.status})`)
    const payload = (await response.json()) as Partial<WeekSnapshot>
    if (!Array.isArray(payload.rows) || payload.since !== range.since || payload.until !== range.until) {
      throw new Error("스냅샷 형식이 올바르지 않습니다.")
    }
    const rows = payload.rows as ResultRow[]
    return {
      kind: "ready",
      snapshot: {
        since: payload.since,
        until: payload.until,
        generated_at: String(payload.generated_at || ""),
        gallery_id: String(payload.gallery_id || galleryId),
        row_count: Number(payload.row_count ?? rows.length),
        review_count: Number(payload.review_count ?? rows.filter((row) => row.review_status === "needs_review").length),
        rows,
      },
    }
  } catch (error) {
    if (error instanceof SyntaxError && String(error.message).includes("Unexpected token '<'")) {
      return { kind: "missing", snapshot: EMPTY_SNAPSHOT(range, galleryId) }
    }
    return { kind: "error", message: error instanceof Error ? error.message : "스냅샷을 읽지 못했습니다." }
  }
}

export function snapshotCsvUrl(range: WeekRange, galleryId: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/") ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`
  return `${base}data/weeks/${encodeURIComponent(galleryId)}/${range.since}.csv`
}
