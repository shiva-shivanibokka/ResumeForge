"use client"
import { useEffect, useRef } from "react"
import { Terminal } from "lucide-react"

interface Props {
  lines: string[]
  title?: string
}

export default function ProgressLog({ lines, title = "Progress" }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [lines])

  if (lines.length === 0) return null

  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-900 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 border-b border-slate-700">
        <Terminal className="w-4 h-4 text-slate-400" />
        <span className="text-xs font-semibold text-slate-300">{title}</span>
      </div>
      <div className="p-4 max-h-64 overflow-y-auto font-mono text-xs space-y-1">
        {lines.map((line, i) => (
          <div key={i} className="fade-in text-slate-300 leading-relaxed">
            <span className="text-indigo-400 mr-2">›</span>{line}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
