import { ShieldAlert, Users } from "lucide-react"

import type { SellerSummary } from "@/lib/types"

export function SellerPanel({ sellers }: { sellers: SellerSummary[] }) {
  return <section className="seller-panel" aria-labelledby="seller-panel-title">
    <div className="results-heading"><h2 id="seller-panel-title"><Users size={18} aria-hidden="true" /> 판매자 활동</h2><span className="count-badge">{sellers.length}명</span></div>
    {sellers.length === 0 ? <div className="empty-state compact">판매자 정보가 없습니다.</div> : <div className="seller-grid">{sellers.slice(0, 12).map((seller) => <article className="seller-card" key={seller.seller_id}><div className="seller-card-heading"><strong>{seller.display_name || "미상"}</strong><span className={`risk-chip risk-${seller.risk_level}`}><ShieldAlert size={13} aria-hidden="true" /> {riskLabel(seller.risk_level, seller.risk_score)}</span></div><p>{seller.observed_post_count}개 게시글 · 판매 {seller.sell_post_count} · 구매 {seller.buy_post_count}</p><p>반복 등록 {seller.repost_count} · 검토 신호 {seller.open_signal_count}</p><small>{reviewLabel(seller.review_status)}</small></article>)}</div>}
  </section>
}

function riskLabel(level: SellerSummary["risk_level"], score: number) { return `${level === "high" ? "높은" : level === "medium" ? "주의" : "낮은"} 위험 ${score}` }
function reviewLabel(status: string) { return status === "confirmed" ? "검토자가 위험 확인" : status === "safe" ? "검토자가 안전 표시" : status === "watching" ? "관찰 중" : "자동 분석 결과" }
