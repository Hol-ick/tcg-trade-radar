import { Clipboard, FileWarning, Radio } from "lucide-react"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { JobLog } from "@/lib/types"

export function JobLogs({ logs }: { logs: JobLog[] }) {
  const [copied, setCopied] = useState(false)
  const copyLogs = async () => {
    await navigator.clipboard.writeText(logs.map((log) => `[${log.level}] ${log.step} ${log.message}`).join("\n"))
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1200)
  }

  return (
    <Card className="ink-panel border-0 shadow-none">
      <CardHeader className="flex flex-row items-center justify-between border-b border-white/10 px-5 py-4 sm:px-6">
        <CardTitle className="flex items-center gap-2 text-base text-white"><Radio className="size-4 text-cyan-300" /> 수집 로그 <Badge className="bg-white/10 text-slate-400">{logs.length}</Badge></CardTitle>
        <Button variant="ghost" size="sm" onClick={copyLogs} disabled={!logs.length} className="text-slate-400 hover:bg-white/10 hover:text-white">
          <Clipboard className="size-3.5" /> {copied ? "복사됨" : "복사"}
        </Button>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-64 px-5 py-4 sm:px-6">
          {logs.length ? (
            <div className="space-y-3">
              {logs.map((log, index) => <LogLine key={`${log.id || "log"}-${index}`} log={log} />)}
            </div>
          ) : (
            <div className="flex h-48 flex-col items-center justify-center gap-2 text-center text-sm text-slate-500">
              <FileWarning className="size-5 text-slate-600" />
              <span>작업을 시작하면 원본 응답과 파서 판정이 표시됩니다.</span>
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

function LogLine({ log }: { log: JobLog }) {
  const tone = log.level === "error" ? "text-red-300" : log.level === "warning" ? "text-amber-300" : "text-slate-300"
  return (
    <div className="border-l border-white/10 pl-3">
      <div className="flex flex-wrap items-center gap-2 font-mono text-[10px] uppercase tracking-[0.12em] text-slate-600">
        <span>{formatTime(log.created_at)}</span><span>{log.step}</span><span className={tone}>{log.level}</span>
      </div>
      <p className={`mt-1 text-sm ${tone}`}>{log.message}</p>
      {log.details && <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-all text-[10px] leading-relaxed text-slate-600">{JSON.stringify(log.details)}</pre>}
    </div>
  )
}

function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString("ko-KR")
}
