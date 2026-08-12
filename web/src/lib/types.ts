export type GalleryPreset = {
  id: string
  name: string
  subject: string
  url: string
}

export const GALLERY_PRESETS: GalleryPreset[] = [
  {
    id: "tcggame",
    name: "TCG 게임",
    subject: "판매",
    url: "https://gall.dcinside.com/mgallery/board/lists?id=tcggame",
  },
  {
    id: "onepiececardgame",
    name: "원피스 카드게임",
    subject: "판매",
    url: "https://gall.dcinside.com/mgallery/board/lists?id=onepiececardgame",
  },
  {
    id: "pokemoncardgame",
    name: "포켓몬 카드",
    subject: "판매",
    url: "https://gall.dcinside.com/mgallery/board/lists?id=pokemoncardgame",
  },
  {
    id: "digimontcg",
    name: "디지몬 카드",
    subject: "거래",
    url: "https://gall.dcinside.com/mgallery/board/lists?id=digimontcg",
  },
  {
    id: "vg",
    name: "뱅가드",
    subject: "거래",
    url: "https://gall.dcinside.com/mgallery/board/lists?id=vg",
  },
]

export type ResultRow = {
  id?: string | number
  card_name?: string
  card_name_raw?: string
  rarity?: string
  post_title?: string
  post_url?: string
  source_url?: string
  price_krw?: number | null
  buy_price_krw?: number | null
  quantity?: number | null
  shipping_included?: string
  review_status?: string
  listing_type?: string
  author_name?: string
  posted_at?: string
  raw_line?: string
}

export type WeekSnapshot = {
  since: string
  until: string
  generated_at: string
  gallery_id: string
  row_count: number
  review_count: number
  rows: ResultRow[]
}

export type SnapshotState =
  | { kind: "loading" }
  | { kind: "ready"; snapshot: WeekSnapshot }
  | { kind: "missing"; snapshot: WeekSnapshot }
  | { kind: "error"; message: string }

// Kept for the existing Python API tests and old local tools; the web app no longer uses these worker contracts.
export type JobState = "queued" | "running" | "completed" | "failed"
export type JobRequest = {
  gallery_id: string
  gallery_url: string
  subject: string
  subjects: string[]
  since?: string
  until?: string
  max_posts: number
  max_pages: number
  delay: number
  buy_rate: number
  keep_raw: boolean
  review_unmatched: boolean
}
export type JobStatus = {
  id: string
  gallery_id: string
  subject: string
  since?: string | null
  until?: string | null
  state: JobState
  counts: Record<string, number>
  error_message: string | null
  created_at: string
  finished_at: string | null
  worker_version: string
  last_success_at: string | null
}
export type JobLog = {
  id?: number
  created_at: string
  level: string
  step: string
  message: string
  details?: Record<string, unknown>
}
export type HealthResponse = { version: string }
