import type { MarketRow } from "@/lib/types"

type DayBucket = {
  date: string
  supply: number
  demand: number
  supplyQuantity: number
  demandQuantity: number
  sellPrices: number[]
  buyPrices: number[]
}

export function PriceTrendChart({ rows }: { rows: MarketRow[] }) {
  const buckets = buildBuckets(rows)
  const points = buckets.map((bucket) => ({
    date: bucket.date,
    sell: median(bucket.sellPrices),
    buy: median(bucket.buyPrices),
  }))
  const prices = points.flatMap((point) => [point.sell, point.buy]).filter((value): value is number => value != null)
  const max = Math.max(...prices, 1)
  return <ChartCard title="가격 궤적" note="날짜별 매도·매수 가격 중앙값">
    {prices.length === 0 ? <ChartEmpty>가격이 있는 행이 아직 없습니다.</ChartEmpty> : <svg className="market-chart" viewBox="0 0 720 260" role="img" aria-label="날짜별 매도와 매수 가격 중앙값 추이">
      <ChartGrid max={max} suffix="원" />
      <path className="chart-line chart-line-sell" d={linePath(points, "sell", max)} />
      <path className="chart-line chart-line-buy" d={linePath(points, "buy", max)} />
      {points.map((point, index) => <g key={point.date}>
        {point.sell != null && <circle className="chart-dot chart-dot-sell" cx={xFor(index, points.length)} cy={yFor(point.sell, max)} r="4" />}
        {point.buy != null && <circle className="chart-dot chart-dot-buy" cx={xFor(index, points.length)} cy={yFor(point.buy, max)} r="4" />}
      </g>)}
      <DateLabels dates={points.map((point) => point.date)} />
    </svg>}
    <div className="chart-legend"><span><i className="legend-dot sell" />판매 가격</span><span><i className="legend-dot buy" />구매 희망가</span></div>
  </ChartCard>
}

export function SupplyDemandChart({ rows }: { rows: MarketRow[] }) {
  const buckets = buildBuckets(rows)
  const max = Math.max(...buckets.flatMap((bucket) => [bucket.supply, bucket.demand]), 1)
  return <ChartCard title="수요 · 공급" note="행 수 기준 · 수량은 카드 요약에서 확인">
    {buckets.length === 0 ? <ChartEmpty>날짜가 있는 행이 아직 없습니다.</ChartEmpty> : <svg className="market-chart" viewBox="0 0 720 260" role="img" aria-label="날짜별 판매 공급량과 구매 수요량">
      <ChartGrid max={max} suffix="건" />
      {buckets.map((bucket, index) => {
        const x = xFor(index, buckets.length)
        const width = Math.max(8, Math.min(22, 260 / Math.max(buckets.length, 1)))
        return <g key={bucket.date}>
          <rect className="chart-bar supply" x={x - width - 2} y={yFor(bucket.supply, max)} width={width} height={240 - yFor(bucket.supply, max)} rx="2" />
          <rect className="chart-bar demand" x={x + 2} y={yFor(bucket.demand, max)} width={width} height={240 - yFor(bucket.demand, max)} rx="2" />
        </g>
      })}
      <DateLabels dates={buckets.map((bucket) => bucket.date)} />
    </svg>}
    <div className="chart-legend"><span><i className="legend-dot supply" />공급 · 판매</span><span><i className="legend-dot demand" />수요 · 구매</span></div>
  </ChartCard>
}

function ChartCard({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return <article className="chart-card"><div className="chart-heading"><div><p className="section-kicker">시장 흐름</p><h3>{title}</h3></div><span>{note}</span></div>{children}</article>
}

function ChartEmpty({ children }: { children: React.ReactNode }) { return <div className="chart-empty">{children}</div> }

function buildBuckets(rows: MarketRow[]): DayBucket[] {
  const map = new Map<string, DayBucket>()
  for (const row of rows) {
    if (!row.dateKey) continue
    const bucket = map.get(row.dateKey) || { date: row.dateKey, supply: 0, demand: 0, supplyQuantity: 0, demandQuantity: 0, sellPrices: [], buyPrices: [] }
    if (row.listingType === "sell") { bucket.supply += 1; bucket.supplyQuantity += row.quantity; if (row.priceKrw != null && row.priceScope === "per_card") bucket.sellPrices.push(row.priceKrw) }
    if (row.listingType === "buy") { bucket.demand += 1; bucket.demandQuantity += row.quantity; if (row.priceKrw != null && row.priceScope === "per_card") bucket.buyPrices.push(row.priceKrw) }
    map.set(row.dateKey, bucket)
  }
  return [...map.values()].sort((left, right) => left.date.localeCompare(right.date))
}

function median(values: number[]): number | null {
  if (!values.length) return null
  const sorted = [...values].sort((left, right) => left - right)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : Math.round((sorted[middle - 1] + sorted[middle]) / 2)
}

function xFor(index: number, count: number): number { return count <= 1 ? 360 : 58 + (index / (count - 1)) * 604 }
function yFor(value: number, max: number): number { return 240 - (value / max) * 196 }
function linePath(points: { sell: number | null; buy: number | null; date: string }[], key: "sell" | "buy", max: number): string {
  const path: string[] = []
  points.forEach((point, index) => {
    const value = point[key]
    if (value == null) return
    const command = path.length ? "L" : "M"
    path.push(`${command} ${xFor(index, points.length)} ${yFor(value, max)}`)
  })
  return path.join(" ")
}

function ChartGrid({ max, suffix }: { max: number; suffix: string }) {
  return <g className="chart-grid">{[0, 1, 2, 3].map((step) => { const value = max * (1 - step / 3); const y = 44 + step * 65.33; return <g key={step}><line x1="58" x2="662" y1={y} y2={y} /><text x="48" y={y + 4} textAnchor="end">{formatCompact(value)}{suffix}</text></g> })}</g>
}

function DateLabels({ dates }: { dates: string[] }) {
  const indexes = dates.length <= 6 ? dates.map((_, index) => index) : [0, Math.floor((dates.length - 1) / 2), dates.length - 1]
  return <g className="chart-labels">{indexes.map((index) => <text key={`${dates[index]}-${index}`} x={xFor(index, dates.length)} y="258" textAnchor={index === 0 ? "start" : index === dates.length - 1 ? "end" : "middle"}>{dates[index].slice(5).replace("-", ".")}</text>)}</g>
}

function formatCompact(value: number): string {
  if (value >= 10000) return `${Math.round(value / 10000)}만 `
  if (value >= 1000) return `${Math.round(value / 1000)}천 `
  return `${Math.round(value)} `
}
