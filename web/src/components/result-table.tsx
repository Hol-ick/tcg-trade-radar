import { Download, ExternalLink, PackageSearch } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { ResultRow } from "@/lib/types"

export function ResultTable({ rows, onDownloadCsv }: { rows: ResultRow[]; onDownloadCsv?: () => void }) {
  return (
    <Card className="paper-panel border-0 shadow-none">
      <CardHeader className="flex flex-row items-center justify-between gap-3 border-b border-slate-900/10 px-5 py-4 sm:px-6">
        <CardTitle className="flex items-center gap-2 text-base text-slate-900"><PackageSearch className="size-4 text-orange-600" /> 추출 결과</CardTitle>
        <div className="flex items-center gap-2">
          {rows.length > 0 && onDownloadCsv && <Button type="button" size="sm" variant="outline" className="border-slate-900/15 text-slate-700" onClick={onDownloadCsv}><Download className="mr-1.5 size-3.5" /> CSV 저장</Button>}
          <Badge className="bg-slate-900 text-white">{rows.length} rows</Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {rows.length ? (
          <Table>
            <TableHeader><TableRow className="border-slate-900/10 hover:bg-transparent"><TableHead className="pl-5 text-slate-500 sm:pl-6">카드 / 원문</TableHead><TableHead className="text-slate-500">가격</TableHead><TableHead className="text-slate-500">분류</TableHead><TableHead className="pr-5 text-right text-slate-500 sm:pr-6">검토</TableHead></TableRow></TableHeader>
            <TableBody>
              {rows.map((row, index) => <ResultRowView key={row.id || `${row.post_url}-${index}`} row={row} />)}
            </TableBody>
          </Table>
        ) : (
          <div className="flex min-h-40 items-center justify-center px-6 text-center text-sm text-slate-500">
            아직 추출된 행이 없습니다. 0 rows도 원본 응답·파서 판정과 함께 기록됩니다.
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ResultRowView({ row }: { row: ResultRow }) {
  const title = row.card_name || row.card_name_raw || "이름 미매칭"
  return (
    <TableRow className="border-slate-900/10 hover:bg-slate-900/[0.03]">
      <TableCell className="max-w-64 pl-5 sm:pl-6">
        <div className="truncate font-medium text-slate-900">{title}</div>
        <div className="truncate text-xs text-slate-500">{row.post_title || row.raw_line || "원문 제목 없음"}</div>
      </TableCell>
      <TableCell className="font-mono text-sm text-slate-900">{formatWon(row.price_krw)}</TableCell>
      <TableCell><Badge variant="outline" className="border-slate-900/15 text-slate-600">{row.listing_type || "unknown"}</Badge></TableCell>
      <TableCell className="pr-5 text-right sm:pr-6">
        <div className="flex items-center justify-end gap-2">
          <Badge className={row.review_status === "needs_review" ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}>{row.review_status || "raw"}</Badge>
          {row.source_url && <a href={row.source_url} target="_blank" rel="noreferrer" aria-label="원문 열기" className="text-slate-500 hover:text-orange-600"><ExternalLink className="size-3.5" /></a>}
        </div>
      </TableCell>
    </TableRow>
  )
}

function formatWon(value?: number | null) {
  return value == null ? "—" : `${value.toLocaleString("ko-KR")}원`
}
