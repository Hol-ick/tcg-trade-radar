export const WEEK_DAYS = 7

export type WeekRange = {
  since: string
  until: string
}

function dateOnly(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

export function toDateKey(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, "0")
  const day = String(value.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

export function parseDateKey(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const [year, month, day] = value.split("-").map(Number)
  const parsed = new Date(year, month - 1, day)
  return parsed.getFullYear() === year && parsed.getMonth() === month - 1 && parsed.getDate() === day ? parsed : null
}

export function getCurrentWeekRange(today = new Date()): WeekRange {
  const until = dateOnly(today)
  const since = new Date(until)
  since.setDate(since.getDate() - (WEEK_DAYS - 1))
  return { since: toDateKey(since), until: toDateKey(until) }
}

export function rangeFromSince(since: string): WeekRange | null {
  const start = parseDateKey(since)
  if (!start) return null
  const until = new Date(start)
  until.setDate(until.getDate() + WEEK_DAYS - 1)
  return { since: toDateKey(start), until: toDateKey(until) }
}

export function shiftWeek(range: WeekRange, direction: -1 | 1): WeekRange {
  const since = parseDateKey(range.since)
  const until = parseDateKey(range.until)
  if (!since || !until) throw new Error("유효하지 않은 주간 범위입니다.")
  const shiftedSince = new Date(since)
  const shiftedUntil = new Date(until)
  shiftedSince.setDate(shiftedSince.getDate() + direction * WEEK_DAYS)
  shiftedUntil.setDate(shiftedUntil.getDate() + direction * WEEK_DAYS)
  return { since: toDateKey(shiftedSince), until: toDateKey(shiftedUntil) }
}

export function isCurrentOrFuture(range: WeekRange, today = new Date()): boolean {
  const end = parseDateKey(range.until)
  const currentEnd = parseDateKey(getCurrentWeekRange(today).until)
  return Boolean(end && currentEnd && end >= currentEnd)
}

export function formatRange(range: WeekRange): string {
  return `${range.since.replaceAll("-", ".")} — ${range.until.replaceAll("-", ".")}`
}
