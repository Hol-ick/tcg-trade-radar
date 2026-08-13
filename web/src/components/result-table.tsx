import { Download, ExternalLink, PackageSearch } from "lucide-react"

import type { ResultRow } from "@/lib/types"

export function ResultTable({ rows, isLoading, onDownloadCsv }: { rows: ResultRow[]; isLoading?: boolean; onDownloadCsv?: () => void }) {
  return <section className="results-panel" aria-labelledby="results-title"><div className="results-heading"><h2 id="results-title"><PackageSearch size={18} aria-hidden="true" /> 수집 결과</h2><div className="results-actions"><span className="count-badge">{rows.length}건</span>{onDownloadCsv && <button className="secondary-button" type="button" onClick={onDownloadCsv}><Download size={15} aria-hidden="true" /> CSV 저장</button>}</div></div>{isLoading ? <div className="empty-state">결과를 읽는 중입니다.</div> : rows.length === 0 ? <div className="empty-state">아직 수집된 결과가 없습니다.</div> : <div className="table-wrap"><table><thead><tr><th>카드 / 게시글</th><th>가격</th><th>수량</th><th>분류</th><th>검토</th><th>원문</th></tr></thead><tbody>{rows.map((row, index) => <ResultRow key={row.id || `${row.post_url}-${index}`} row={row} />)}</tbody></table></div>}</section>
}

function ResultRow({ row }: { row: ResultRow }) {
  const title = row.card_name || row.card_name_raw || "이름 미확인"
  const url = row.source_url || row.post_url
  return <tr><td><strong>{title}</strong><span>{row.post_title || row.raw_line || "제목 없음"}</span></td><td className="price">{formatWon(row.price_krw)}<small className="quality-note">{priceLabel(row.price_status, row.price_scope)}</small></td><td>{row.quantity || 1}</td><td><span className="type-chip">{typeLabel(row.listing_type)}</span><small className="quality-note">{postLabel(row.post_status)}</small></td><td><span className={`review-chip ${row.analysis_status === "usable" && row.review_status !== "needs_review" ? "ok" : "review"}`}>{analysisLabel(row.analysis_status, row.review_status)}</span></td><td>{url && <a className="row-link" href={url} target="_blank" rel="noreferrer" aria-label={`${title} 원문 열기`}><ExternalLink size={15} /></a>}</td></tr>
}

function formatWon(value?: number | null): string { return value == null || value === 0 ? "-" : `${value.toLocaleString("ko-KR")}원` }
function typeLabel(value?: string): string { return value === "buy" ? "구매" : value === "sell" ? "판매" : value === "trade" ? "교환" : "미분류" }
function postLabel(value?: string): string { return value === "completed" ? "거래완료" : value === "reserved" ? "예약" : value === "price_removed" ? "가격삭제" : value === "image_only" ? "사진확인" : value === "active" ? "활성" : "상태 확인" }
function priceLabel(status?: string, scope?: string): string { if (status === "missing") return "가격 없음"; if (status === "removed") return "가격 삭제"; if (scope === "bundle") return "묶음가"; if (scope === "per_quantity") return "복수 수량가"; return status === "estimated" ? "단위 추정" : "" }
function analysisLabel(status?: string, legacy?: string): string { if (status === "context_only") return "참고용"; if (status === "excluded") return "제외"; if (status === "usable" && legacy !== "needs_review") return "분석 가능"; return "검토 필요" }
