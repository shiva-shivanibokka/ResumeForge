"use client"
import { Sparkles } from "lucide-react"

export default function Header() {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
      <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-md">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="text-xl font-black text-slate-900 tracking-tight">ResumeForge</span>
            <span className="ml-2 text-xs font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">AI</span>
          </div>
        </div>
        <p className="text-sm text-slate-500 hidden sm:block">
          Tailored tech resumes from your GitHub + any job link
        </p>
      </div>
    </header>
  )
}
