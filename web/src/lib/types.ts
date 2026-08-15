export type GalleryPreset = {
  id: string
  name: string
  shortName: string
  subject: string
  description: string
  url: string
  logoUrl?: string
  accent: string
}

export const GALLERY_PRESETS: GalleryPreset[] = [
  {
    id: "tcggame",
    name: "유희왕",
    shortName: "유희왕",
    subject: "판매",
    description: "유희왕 카드 거래",
    url: "https://gall.dcinside.com/mgallery/board/lists?id=tcggame",
    logoUrl: "https://ramfspcoxshnrxnvqkio.supabase.co/storage/v1/object/public/game-images/games/1776415303381-jalap8.png",
    accent: "#5b4bdb",
  },
  {
    id: "onepiececardgame",
    name: "원피스 카드게임",
    shortName: "원피스",
    subject: "판매",
    description: "원피스 카드 거래",
    url: "https://gall.dcinside.com/mgallery/board/lists?id=onepiececardgame",
    logoUrl: "https://ramfspcoxshnrxnvqkio.supabase.co/storage/v1/object/public/game-images/games/1776415685939-6afve5.webp",
    accent: "#d9683b",
  },
  {
    id: "pokemoncardgame",
    name: "포켓몬 카드",
    shortName: "포켓몬",
    subject: "판매",
    description: "포켓몬 카드 거래",
    url: "https://gall.dcinside.com/mgallery/board/lists?id=pokemoncardgame",
    accent: "#2f72d6",
  },
  {
    id: "digimontcg",
    name: "디지몬 카드",
    shortName: "디지몬",
    subject: "거래",
    description: "디지몬 카드 거래",
    url: "https://gall.dcinside.com/mgallery/board/lists?id=digimontcg",
    logoUrl: "https://ramfspcoxshnrxnvqkio.supabase.co/storage/v1/object/public/game-images/games/1776415720755-8t6cs3.jfif",
    accent: "#198da3",
  },
  {
    id: "vg",
    name: "뱅가드",
    shortName: "뱅가드",
    subject: "거래",
    description: "뱅가드 카드 거래",
    url: "https://gall.dcinside.com/mgallery/board/lists?id=vg",
    accent: "#c9822f",
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
  post_status?: "active" | "completed" | "reserved" | "price_removed" | "image_only" | "unknown"
  price_status?: "exact" | "estimated" | "missing" | "removed" | "unknown"
  price_scope?: "per_card" | "per_quantity" | "bundle" | "unknown"
  price_origin?: "text" | "ocr" | "comment" | "inferred" | "unknown"
  analysis_status?: "usable" | "needs_review" | "context_only" | "excluded"
  card_match_status?: "matched" | "candidate" | "unmatched" | "image_review"
  seller_id?: string
  seller_name?: string
  seller_risk_score?: number
  seller_risk_level?: "low" | "medium" | "high"
  seller_review_status?: "unreviewed" | "watching" | "safe" | "confirmed" | "noted"
  is_repost?: number
}

export type MarketIntent = "sell" | "buy" | "trade" | "unknown"
export type MarketQuality = "usable" | "needs_review" | "context_only" | "excluded"

export type MarketRow = {
  id: string
  galleryId: string
  cardName: string
  cardKey: string
  sellerName: string
  listingType: MarketIntent
  priceKrw: number | null
  quantity: number
  dateKey: string
  postedAt: string
  title: string
  rawLine: string
  postUrl: string
  reviewStatus: string
  quality: MarketQuality
  priceStatus: "exact" | "estimated" | "missing" | "removed" | "unknown"
  priceScope: "per_card" | "per_quantity" | "bundle" | "unknown"
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

// Worker contracts used by the live collection console.
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
export type SellerSummary = {
  seller_id: string
  display_name: string
  author_type: string
  identity_scope: string
  observed_post_count: number
  sell_post_count: number
  buy_post_count: number
  completed_post_count: number
  repost_count: number
  risk_score: number
  risk_level: "low" | "medium" | "high"
  review_status: string
  open_signal_count: number
}
