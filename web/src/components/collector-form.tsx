import { useState } from "react"
import { ArrowUpRight, Database, Gauge, LockKeyhole, Play, Rss } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { GALLERY_PRESETS, type GalleryPreset, type JobRequest } from "@/lib/types"

type CollectorFormProps = {
  disabled: boolean
  token: string
  onTokenChange: (value: string) => void
  onSubmit: (request: JobRequest) => Promise<void>
}

export function CollectorForm({ disabled, token, onTokenChange, onSubmit }: CollectorFormProps) {
  const [selectedId, setSelectedId] = useState(GALLERY_PRESETS[0].id)
  const [subject, setSubject] = useState(GALLERY_PRESETS[0].subject)
  const [maxPosts, setMaxPosts] = useState("10")
  const [maxPages, setMaxPages] = useState("1")
  const [delay, setDelay] = useState("1")
  const [buyRate, setBuyRate] = useState("60")

  const selected = GALLERY_PRESETS.find((preset) => preset.id === selectedId) || GALLERY_PRESETS[0]

  const selectPreset = (preset: GalleryPreset) => {
    setSelectedId(preset.id)
    setSubject(preset.subject)
  }

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await onSubmit({
      gallery_id: selected.id,
      gallery_url: selected.url,
      subject,
      subjects: [subject],
      max_posts: Math.max(1, Math.min(200, Number(maxPosts) || 10)),
      max_pages: Math.max(1, Math.min(20, Number(maxPages) || 1)),
      delay: Math.max(0, Number(delay) || 0),
      buy_rate: Math.max(0, Math.min(100, Number(buyRate) || 60)),
      keep_raw: true,
      review_unmatched: true,
    })
  }

  return (
    <Card className="ink-panel h-full overflow-hidden border-0 shadow-none">
      <CardHeader className="border-b border-white/10 px-5 py-5 sm:px-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="eyebrow mb-2 text-cyan-300">01 / SOURCE SETUP</div>
            <CardTitle className="text-xl text-white">수집 범위를 고르세요</CardTitle>
            <CardDescription className="mt-1 text-slate-400">
              작은 샘플부터 시작해 응답 구조와 실제 결과를 확인합니다.
            </CardDescription>
          </div>
          <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 p-2 text-cyan-200">
            <Rss className="size-4" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6 px-5 py-5 sm:px-6">
        <div className="space-y-3">
          <Label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Gallery preset</Label>
          <div className="grid gap-2 sm:grid-cols-2">
            {GALLERY_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                disabled={disabled}
                onClick={() => selectPreset(preset)}
                className={`source-tile text-left ${selected.id === preset.id ? "source-tile-active" : ""}`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-medium text-slate-100">{preset.name}</span>
                  {selected.id === preset.id && <Badge className="bg-orange-400 text-slate-950">선택</Badge>}
                </span>
                <span className="mt-1 block text-xs leading-relaxed text-slate-500">{preset.note}</span>
              </button>
            ))}
          </div>
          <a
            className="inline-flex items-center gap-1 text-xs text-cyan-300 underline-offset-4 hover:underline"
            href={selected.url}
            target="_blank"
            rel="noreferrer"
          >
            원본 갤러리 열기 <ArrowUpRight className="size-3" />
          </a>
        </div>

        <form className="space-y-5" onSubmit={submit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="subject" className="text-slate-300">게시글 분류</Label>
              <Select value={subject} onValueChange={setSubject} disabled={disabled}>
                <SelectTrigger id="subject" className="w-full border-white/10 bg-white/5 text-slate-100">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="판매">판매글</SelectItem>
                  <SelectItem value="구매">구매글</SelectItem>
                  <SelectItem value="교환">교환글</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="max-posts" className="text-slate-300">최대 게시글</Label>
              <Input id="max-posts" type="number" min="1" max="200" value={maxPosts} onChange={(event) => setMaxPosts(event.target.value)} disabled={disabled} className="border-white/10 bg-white/5 text-white" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="max-pages" className="text-slate-300">최대 페이지</Label>
              <Input id="max-pages" type="number" min="1" max="20" value={maxPages} onChange={(event) => setMaxPages(event.target.value)} disabled={disabled} className="border-white/10 bg-white/5 text-white" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="delay" className="text-slate-300">요청 간격 (초)</Label>
              <Input id="delay" type="number" min="0" step="0.1" value={delay} onChange={(event) => setDelay(event.target.value)} disabled={disabled} className="border-white/10 bg-white/5 text-white" />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <div className="space-y-2">
              <Label htmlFor="token" className="flex items-center gap-2 text-slate-300">
                <LockKeyhole className="size-3.5" /> API 토큰 (선택)
              </Label>
              <Input id="token" type="password" autoComplete="off" placeholder="WORKER_API_TOKEN을 쓰는 경우에만 입력" value={token} onChange={(event) => onTokenChange(event.target.value)} disabled={disabled} className="border-white/10 bg-white/5 text-white placeholder:text-slate-600" />
            </div>
            <div className="space-y-2 sm:min-w-28">
              <Label htmlFor="buy-rate" className="flex items-center gap-2 text-slate-300">
                <Gauge className="size-3.5" /> 매입률 %
              </Label>
              <Input id="buy-rate" type="number" min="0" max="100" value={buyRate} onChange={(event) => setBuyRate(event.target.value)} disabled={disabled} className="border-white/10 bg-white/5 text-white" />
            </div>
          </div>

          <div className="flex flex-col gap-3 rounded-xl border border-orange-300/15 bg-orange-300/5 p-4 text-xs leading-relaxed text-slate-400 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex gap-3">
              <Database className="mt-0.5 size-4 shrink-0 text-orange-300" />
              <span>원본 HTML은 수집기 정책에 따라 보존되고, 결과는 검토 상태와 함께 SQLite에 기록됩니다.</span>
            </div>
            <Button type="submit" disabled={disabled} className="h-10 shrink-0 bg-orange-400 px-4 font-semibold text-slate-950 hover:bg-orange-300">
              <Play className="size-4" /> 실제 수집 시작
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
