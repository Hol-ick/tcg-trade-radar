export type JobState = "queued" | "running" | "completed" | "failed"

export type GalleryPreset = {
  id: string
  name: string
  subject: string
  subjects: string[]
  url: string
  note: string
}

export const GALLERY_PRESETS: GalleryPreset[] = [
  {
    id: "tcggame",
    name: "TCG 게임",
    subject: "판매",
    subjects: ["판매"],
    url: "https://gall.dcinside.com/mgallery/board/lists?id=tcggame",
    note: "통합 TCG 매물 레이더",
  },
  {
    id: "onepiececardgame",
    name: "원피스 카드게임",
    subject: "판매",
    subjects: ["판매"],
    url: "https://gall.dcinside.com/mgallery/board/lists?id=onepiececardgame",
    note: "원피스 카드 전문 갤러리",
  },
  {
    id: "pokemoncardgame",
    name: "포켓몬 카드",
    subject: "판매",
    subjects: ["판매"],
    url: "https://gall.dcinside.com/mgallery/board/lists?id=pokemoncardgame",
    note: "포켓몬 카드 전문 갤러리",
  },
  {
    id: "digimontcg",
    name: "디지몬 카드",
    subject: "판매",
    subjects: ["판매"],
    url: "https://gall.dcinside.com/mgallery/board/lists?id=digimontcg",
    note: "디지몬 카드 전문 갤러리",
  },
  {
    id: "vg",
    name: "뱅가드",
    subject: "판매",
    subjects: ["판매"],
    url: "https://gall.dcinside.com/mgallery/board/lists?id=vg",
    note: "뱅가드 카드 전문 갤러리",
  },
]

export type JobRequest = {
  gallery_id: string
  gallery_url: string
  subject: string
  subjects: string[]
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

export type HealthResponse = { version: string }
