import { useState } from "react"
import { ArrowUpRight, Gauge, LockKeyhole, Play } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
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
      <CardHeader className="border-b border-white/10 px-5 py-4 sm:px-6">
        <CardTitle className="text-lg text-white">수집 설정</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5 px-5 py-5 sm:px-6">
        <div className="space-y-2">
          <Label className="text-xs font-semibold text-slate-400">갤러리</Label>
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
              </button>
            ))}
          </div>
          <a className="inline-flex items-center gap-1 text-xs text-cyan-300 underline-offset-4 hover:underline" href={selected.url} target="_blank" rel="noreferrer">
            원본 갤러리 열기 <ArrowUpRight className="size-3" />
          </a>
        </div>

        <form className="space-y-5" onSubmit={submit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="게시글 분류">
              <Select value={subject} onValueChange={setSubject} disabled={disabled}>
                <SelectTrigger className="w-full border-white/10 bg-white/5 text-slate-100"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="판매">판매글</SelectItem>
                  <SelectItem value="구매">구매글</SelectItem>
                  <SelectItem value="교환">교환글</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <NumberField id="max-posts" label="최대 게시글" value={maxPosts} onChange={setMaxPosts} min="1" max="200" disabled={disabled} />
            <NumberField id="max-pages" label="최대 페이지" value={maxPages} onChange={setMaxPages} min="1" max="20" disabled={disabled} />
            <NumberField id="delay" label="요청 간격 (초)" value={delay} onChange={setDelay} min="0" step="0.1" disabled={disabled} />
          </div>

          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <div className="space-y-2">
              <Label htmlFor="token" className="flex items-center gap-2 text-slate-300"><LockKeyhole className="size-3.5" /> API 토큰 (선택)</Label>
              <Input id="token" type="password" autoComplete="off" placeholder="worker에 토큰을 설정한 경우 입력" value={token} onChange={(event) => onTokenChange(event.target.value)} disabled={disabled} className="border-white/10 bg-white/5 text-white placeholder:text-slate-600" />
            </div>
            <NumberField id="buy-rate" label="매입률 %" value={buyRate} onChange={setBuyRate} min="0" max="100" disabled={disabled} icon={<Gauge className="size-3.5" />} />
          </div>

          <Button type="submit" disabled={disabled} className="h-10 w-full bg-orange-400 font-semibold text-slate-950 hover:bg-orange-300">
            <Play className="size-4" /> 수집 시작
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-2"><Label className="text-slate-300">{label}</Label>{children}</div>
}

function NumberField({ id, label, value, onChange, disabled, icon, ...props }: { id: string; label: string; value: string; onChange: (value: string) => void; disabled: boolean; icon?: React.ReactNode; min?: string; max?: string; step?: string }) {
  return <div className="space-y-2"><Label htmlFor={id} className="flex items-center gap-2 text-slate-300">{icon}{label}</Label><Input id={id} type="number" value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} className="border-white/10 bg-white/5 text-white" {...props} /></div>
}
