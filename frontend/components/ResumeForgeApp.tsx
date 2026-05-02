"use client"

import { useState, useCallback } from "react"
import {
  Sparkles, GitBranch, Upload,
  Search, Loader2, CheckCircle2, AlertCircle, Eye, EyeOff,
  Wand2, Mail, RefreshCw, Settings2, X, Trash2,
} from "lucide-react"
import type { AppState } from "@/lib/types"
import { INITIAL_STATE } from "@/lib/types"
import {
  analyseJdAndResume, fetchAndRankProjects, generateResume,
  editResume, generateCoverLetter, editCoverLetter, downloadUrl,
} from "@/lib/api"
import ProgressLog from "./ProgressLog"
import ScoreCard from "./ScoreCard"
import DownloadButtons from "./DownloadButtons"

const FONTS = ["Calibri","Arial","Georgia","Times New Roman","Garamond","Cambria","Trebuchet MS"]

// ── Small reusable UI ─────────────────────────────────────────────────────────

function SectionPill({ step, label }: { step: number; label: string }) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-black shadow-md">
        {step}
      </div>
      <span className="font-black text-slate-800 text-lg">{label}</span>
    </div>
  )
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200 shadow-sm p-6 ${className}`}>
      {children}
    </div>
  )
}

function Input({ label, placeholder, value, onChange, type = "text", info }: {
  label: string; placeholder?: string; value: string
  onChange: (v: string) => void; type?: string; info?: string
}) {
  return (
    <div>
      <label className="block text-sm font-semibold text-slate-700 mb-1.5">{label}</label>
      {info && <p className="text-xs text-slate-400 mb-1.5">{info}</p>}
      <input
        type={type}
        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm placeholder-slate-400 shadow-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all"
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
      />
    </div>
  )
}

function Textarea({ label, placeholder, value, onChange, rows = 4, className = "" }: {
  label: string; placeholder?: string; value: string
  onChange: (v: string) => void; rows?: number; className?: string
}) {
  return (
    <div className={`flex flex-col ${className}`}>
      <label className="block text-sm font-semibold text-slate-700 mb-1.5">{label}</label>
      <textarea
        rows={rows}
        className="flex-1 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm placeholder-slate-400 shadow-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all resize-none"
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
      />
    </div>
  )
}

function StatusBadge({ type, message }: { type: "success"|"error"|"info"; message: string }) {
  const styles = {
    success: "bg-emerald-50 border-emerald-200 text-emerald-800",
    error:   "bg-rose-50    border-rose-200    text-rose-800",
    info:    "bg-indigo-50  border-indigo-200  text-indigo-800",
  }
  const icons = {
    success: <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />,
    error:   <AlertCircle  className="w-4 h-4 shrink-0 text-rose-500" />,
    info:    <Loader2      className="w-4 h-4 shrink-0 text-indigo-500 animate-spin" />,
  }
  return (
    <div className={`flex items-start gap-2 p-3 rounded-xl border text-sm font-medium ${styles[type]}`}>
      {icons[type]}<span dangerouslySetInnerHTML={{ __html: message }} />
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────

export default function ResumeForgeApp() {
  const [state, setState]         = useState<AppState>(INITIAL_STATE)
  const [apiKey, setApiKey]       = useState("")
  const [ghToken, setGhToken]     = useState("")
  const [showKeys, setShowKeys]   = useState(false)

  // Form inputs
  const [jdUrl, setJdUrl]             = useState("")
  const [jdText, setJdText]           = useState("")
  const [linkedinUrl, setLinkedinUrl] = useState("")
  const [githubUrl, setGithubUrl]     = useState("")
  const [pageOption, setPageOption]   = useState<"1-page"|"2-page">("1-page")
  const [fontFamily, setFontFamily]   = useState("Calibri")
  const [resumeFile, setResumeFile]   = useState<File | null>(null)

  // Progress logs
  const [analyseLogs, setAnalyseLogs]   = useState<string[]>([])
  const [projectLogs, setProjectLogs]   = useState<string[]>([])
  const [generateLogs, setGenerateLogs] = useState<string[]>([])

  // Loading states
  const [analyseLoading, setAnalyseLoading]   = useState(false)
  const [projectLoading, setProjectLoading]   = useState(false)
  const [generateLoading, setGenerateLoading] = useState(false)
  const [editLoading, setEditLoading]         = useState(false)
  const [clLoading, setClLoading]             = useState(false)
  const [clEditLoading, setClEditLoading]     = useState(false)

  // Status messages
  const [analyseStatus, setAnalyseStatus]   = useState<{type:"success"|"error"|"info";msg:string}|null>(null)
  const [projectStatus, setProjectStatus]   = useState<{type:"success"|"error"|"info";msg:string}|null>(null)
  const [generateStatus, setGenerateStatus] = useState<{type:"success"|"error"|"info";msg:string}|null>(null)
  const [editStatus, setEditStatus]         = useState<{type:"success"|"error"|"info";msg:string}|null>(null)
  const [clStatus, setClStatus]             = useState<{type:"success"|"error"|"info";msg:string}|null>(null)

  // Edit / cover letter inputs
  const [editInstructions, setEditInstructions]     = useState("")
  const [clTone, setClTone]                         = useState("Professional")
  const [clExtra, setClExtra]                       = useState("")
  const [clEditInstructions, setClEditInstructions] = useState("")

  // Preview visibility
  const [showPreview, setShowPreview]   = useState(true)
  const [showClPreview, setShowClPreview] = useState(true)

  const update = useCallback((patch: Partial<AppState>) =>
    setState(s => ({ ...s, ...patch })), [])

  // ── STEP 1: Analyse ──────────────────────────────────────────────────────

  async function handleAnalyse() {
    if (!resumeFile) { setAnalyseStatus({type:"error",msg:"Upload your resume first."}); return }
    if (!jdUrl.trim() && !jdText.trim()) { setAnalyseStatus({type:"error",msg:"Provide a job URL or paste the JD."}); return }

    setAnalyseLoading(true)
    setAnalyseStatus({type:"info", msg:"Analysing JD + resume…"})
    setAnalyseLogs(["Fetching job description…"])

    try {
      const res = await analyseJdAndResume({ jdUrl, jdText, resumeFile, linkedinUrl, apiKey })
      setAnalyseLogs(l => [...l, `Parsed: ${res.jd_structured.job_title} @ ${res.jd_structured.company}`,
        `Resume: ${res.resume_data.name}`,
        `Gap analysis: ${res.required_keywords.length} required missing, ${res.preferred_keywords.length} preferred missing`])
      update({
        jdStructured: res.jd_structured, jdRaw: res.jd_raw,
        resumeData: res.resume_data, resumeRawText: res.resume_raw_text,
        linkedinUrl: res.linkedin_url || linkedinUrl,
        requiredKeywords: res.required_keywords,
        preferredKeywords: res.preferred_keywords,
        selectedRequired:  res.required_keywords.map(k => k.keyword),
        selectedPreferred: res.preferred_keywords.map(k => k.keyword),
      })
      setAnalyseStatus({type:"success", msg:`✓ Analysed <strong>${res.jd_structured.job_title} @ ${res.jd_structured.company}</strong> — select keywords below then continue`})
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setAnalyseStatus({type:"error", msg})
      setAnalyseLogs(l => [...l, `ERROR: ${msg}`])
    } finally {
      setAnalyseLoading(false)
    }
  }

  // ── STEP 2: Fetch projects ────────────────────────────────────────────────

  async function handleFetchProjects() {
    if (!state.jdStructured) { setProjectStatus({type:"error",msg:"Complete Step 1 first."}); return }
    if (!githubUrl.trim()) { setProjectStatus({type:"error",msg:"Enter your GitHub profile URL."}); return }

    setProjectLoading(true)
    setProjectStatus({type:"info", msg:"Fetching and ranking GitHub repos…"})
    setProjectLogs(["Connecting to GitHub…"])

    try {
      const res = await fetchAndRankProjects({
        githubUrl, ghToken, apiKey,
        jdStructured: state.jdStructured,
        onProgress: msg => setProjectLogs(l => [...l, msg]),
      })
      update({ rankedProjects: res.ranked, allProjects: res.all_projects,
               selectedProjectNames: res.ranked.slice(0, 4).map(p => p.name) })
      setProjectStatus({type:"success", msg:`✓ Found <strong>${res.count} relevant projects</strong> — select at least 3 below`})
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setProjectStatus({type:"error", msg})
    } finally {
      setProjectLoading(false)
    }
  }

  // ── STEP 3: Generate ─────────────────────────────────────────────────────

  async function handleGenerate() {
    if (!state.jdStructured || !state.resumeData) { setGenerateStatus({type:"error",msg:"Complete Step 1 first."}); return }
    if (state.rankedProjects.length === 0) { setGenerateStatus({type:"error",msg:"Fetch GitHub projects first."}); return }
    const selected = state.rankedProjects.filter(p => state.selectedProjectNames.includes(p.name))
    if (selected.length < 3) { setGenerateStatus({type:"error",msg:`Select at least 3 projects (${selected.length} selected).`}); return }

    setGenerateLoading(true)
    setGenerateStatus({type:"info", msg:"Generating tailored resume…"})
    setGenerateLogs(["Starting pipeline…"])

    const allKeywords = [...state.selectedRequired, ...state.selectedPreferred]

    try {
      const res = await generateResume({
        jdStructured: state.jdStructured, jdRaw: state.jdRaw,
        resumeData: state.resumeData, resumeRawText: state.resumeRawText,
        selectedProjects: selected, selectedKeywords: allKeywords,
        linkedinUrl: state.linkedinUrl || linkedinUrl,
        githubUrl: githubUrl,
        pageOption, fontFamily, apiKey,
        onProgress: msg => setGenerateLogs(l => [...l, msg]),
      })
      update({
        matchedPayload: res.matched_payload,
        docxId: res.docx_id, pdfId: res.pdf_id,
        docxName: res.docx_name, pdfName: res.pdf_name,
        scores: res.scores, scoresMd: res.scores_md,
      })
      setGenerateStatus({type:"success", msg:`✓ Resume ready: <strong>${res.job_label}</strong>`})
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setGenerateStatus({type:"error", msg})
    } finally {
      setGenerateLoading(false)
    }
  }

  // ── Edit ──────────────────────────────────────────────────────────────────

  async function handleEdit() {
    if (!state.matchedPayload || !state.resumeData) { setEditStatus({type:"error",msg:"Generate a resume first."}); return }
    if (!editInstructions.trim()) { setEditStatus({type:"error",msg:"Enter edit instructions."}); return }

    setEditLoading(true)
    setEditStatus({type:"info", msg:"Applying edits…"})

    try {
      const res = await editResume({
        editInstructions, matchedPayload: state.matchedPayload,
        resumeData: state.resumeData, jdRaw: state.jdRaw,
        pageOption, fontFamily, apiKey,
      })
      // Only overwrite scores if the backend returned a real scores object
      // (it returns null when jd_raw was empty or build failed)
      const hasNewScores = res.scores && typeof res.scores.ats_score === "number"
      update({
        matchedPayload: res.matched_payload,
        docxId: res.docx_id, pdfId: res.pdf_id,
        docxName: res.docx_name, pdfName: res.pdf_name,
        ...(hasNewScores ? { scores: res.scores, scoresMd: res.scores_md ?? "" } : {}),
      })
      setEditStatus({type:"success", msg: hasNewScores
        ? "✓ Resume updated — scores recalculated"
        : "✓ Resume updated"
      })
      setEditInstructions("")
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setEditStatus({type:"error", msg})
    } finally {
      setEditLoading(false)
    }
  }

  // ── Clear resume result ───────────────────────────────────────────────────

  function handleClearResume() {
    update({
      matchedPayload: null,
      docxId: null, pdfId: null, docxName: null, pdfName: null,
      scores: null, scoresMd: "",
    })
    setGenerateLogs([])
    setGenerateStatus(null)
    setEditStatus(null)
    setEditInstructions("")
  }

  // ── Clear cover letter result ─────────────────────────────────────────────

  function handleClearCoverLetter() {
    update({
      coverLetterText: "",
      clDocxId: null, clPdfId: null, clDocxName: null, clPdfName: null,
    })
    setClStatus(null)
    setClEditInstructions("")
  }

  // ── Cover letter ──────────────────────────────────────────────────────────

  async function handleCoverLetter() {
    if (!state.jdStructured || !state.resumeData || !state.matchedPayload) {
      setClStatus({type:"error",msg:"Generate the resume first."}); return
    }
    setClLoading(true)
    setClStatus({type:"info", msg:"Writing cover letter…"})
    const allKeywords = [...state.selectedRequired, ...state.selectedPreferred]

    try {
      const res = await generateCoverLetter({
        tone: clTone, extraInstructions: clExtra,
        jdStructured: state.jdStructured, resumeData: state.resumeData,
        matchedPayload: state.matchedPayload, selectedKeywords: allKeywords, apiKey,
      })
      update({ coverLetterText: res.letter_text,
               clDocxId: res.docx_id, clPdfId: res.pdf_id,
               clDocxName: res.docx_name, clPdfName: res.pdf_name })
      setClStatus({type:"success", msg:"✓ Cover letter ready"})
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setClStatus({type:"error", msg})
    } finally {
      setClLoading(false)
    }
  }

  async function handleCoverLetterEdit() {
    if (!state.coverLetterText) { setClStatus({type:"error",msg:"Generate a cover letter first."}); return }
    if (!clEditInstructions.trim()) { setClStatus({type:"error",msg:"Enter edit instructions."}); return }

    setClEditLoading(true)
    setClStatus({type:"info", msg:"Applying cover letter edits…"})

    try {
      const res = await editCoverLetter({
        editInstructions: clEditInstructions,
        letterText: state.coverLetterText,
        jdStructured: state.jdStructured!,
        resumeData: state.resumeData!,
        apiKey,
      })
      update({ coverLetterText: res.letter_text,
               clDocxId: res.docx_id, clPdfId: res.pdf_id,
               clDocxName: res.docx_name, clPdfName: res.pdf_name })
      setClStatus({type:"success", msg:"✓ Cover letter updated"})
      setClEditInstructions("")
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setClStatus({type:"error", msg})
    } finally {
      setClEditLoading(false)
    }
  }

  // ── Toggle keyword selection ──────────────────────────────────────────────
  function toggleRequired(kw: string) {
    update({ selectedRequired: state.selectedRequired.includes(kw)
      ? state.selectedRequired.filter(k => k !== kw)
      : [...state.selectedRequired, kw] })
  }
  function togglePreferred(kw: string) {
    update({ selectedPreferred: state.selectedPreferred.includes(kw)
      ? state.selectedPreferred.filter(k => k !== kw)
      : [...state.selectedPreferred, kw] })
  }
  function toggleProject(name: string) {
    update({ selectedProjectNames: state.selectedProjectNames.includes(name)
      ? state.selectedProjectNames.filter(n => n !== name)
      : [...state.selectedProjectNames, name] })
  }

  // ── Render ────────────────────────────────────────────────────────────────

  const hasAnalysed  = !!state.jdStructured
  const hasProjects  = state.rankedProjects.length > 0
  const hasResume    = !!state.docxId
  const hasCoverLetter = !!state.coverLetterText

  return (
    <div className="min-h-screen bg-slate-50">
      {/* ── Header ── */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-md">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-black text-slate-900 tracking-tight">ResumeForge</span>
            <span className="text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-100">AI</span>
          </div>
          <p className="text-sm text-slate-400 hidden md:block">Tailored tech resumes from your GitHub + any job link</p>
          <button onClick={() => setShowKeys(v => !v)}
            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors">
            <Settings2 className="w-4 h-4" /><span className="hidden sm:inline">Settings</span>
          </button>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        {/* ── API Keys ── */}
        {showKeys && (
          <Card className="border-indigo-100 bg-indigo-50/40">
            <div className="flex items-center justify-between mb-4">
              <span className="font-bold text-slate-800">API Keys & Settings</span>
              <button onClick={() => setShowKeys(false)}><X className="w-4 h-4 text-slate-400" /></button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input label="Anthropic API Key" type="password"
                placeholder="sk-ant-... (or set in .env)" value={apiKey} onChange={setApiKey} />
              <Input label="GitHub Personal Access Token" type="password"
                placeholder="ghp_... (optional — raises rate limit)" value={ghToken} onChange={setGhToken}
                info="Read-only public repos token. Leave blank to use GITHUB_TOKEN from .env." />
            </div>
          </Card>
        )}

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* STEP 1 — Analyse                                               */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        <Card>
          <SectionPill step={1} label="Analyse Job Description & Resume" />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 md:items-stretch">
            {/* Left: JD */}
            <div className="flex flex-col gap-4">
              <Input label="Job Posting URL"
                placeholder="Paste any job link — Jobright, LinkedIn, Greenhouse…"
                value={jdUrl} onChange={setJdUrl} />
              <Textarea label="Or paste JD text directly (fallback if URL fails)"
                placeholder="Paste the full job description here…"
                value={jdText} onChange={setJdText} rows={5} className="flex-1" />
            </div>
            {/* Right: Resume + LinkedIn + GitHub */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Resume (PDF or .docx)</label>
                <label
                  htmlFor="resume-upload"
                  className="block border-2 border-dashed border-slate-200 rounded-xl p-6 text-center cursor-pointer hover:border-indigo-400 hover:bg-indigo-50/30 transition-all"
                >
                  {resumeFile ? (
                    <div className="flex items-center justify-center gap-2 text-sm text-emerald-700 font-semibold">
                      <CheckCircle2 className="w-5 h-5" />{resumeFile.name}
                    </div>
                  ) : (
                    <div className="text-slate-400">
                      <Upload className="w-8 h-8 mx-auto mb-2" />
                      <p className="text-sm font-medium">Click to upload PDF or .docx</p>
                    </div>
                  )}
                </label>
                <input
                  id="resume-upload"
                  type="file"
                  accept=".pdf,.docx,.doc"
                  className="hidden"
                  onChange={e => setResumeFile(e.target.files?.[0] ?? null)}
                />
              </div>
              <Input label="LinkedIn Profile URL"
                placeholder="https://linkedin.com/in/your-profile"
                value={linkedinUrl} onChange={setLinkedinUrl}
                info="Appears as a clickable link in your resume header" />
              <Input label="GitHub Profile URL"
                placeholder="https://github.com/your-username"
                value={githubUrl} onChange={setGithubUrl}
                info="Used to fetch & rank your projects for the resume" />
            </div>
          </div>

          <div className="mt-5 flex items-center gap-4">
            <button onClick={handleAnalyse} disabled={analyseLoading}
              className="inline-flex items-center gap-2 px-7 py-3 rounded-xl bg-indigo-600 text-white font-bold shadow-md hover:bg-indigo-700 active:scale-95 disabled:opacity-50 transition-all">
              {analyseLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              Analyse JD + Resume
            </button>
            {analyseStatus && <StatusBadge type={analyseStatus.type} message={analyseStatus.msg} />}
          </div>

          <ProgressLog lines={analyseLogs} title="Analysis Log" />
        </Card>

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* GAP ANALYSIS                                                   */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        {hasAnalysed && (
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-2 h-2 rounded-full bg-indigo-500" />
              <span className="font-bold text-slate-800">Keyword Gap Analysis</span>
              <span className="text-xs text-slate-400 ml-1">Select keywords to weave into your resume</span>
            </div>

            {/* Skill categories */}
            {state.jdStructured && (
              <div className="mb-5 p-4 bg-slate-50 rounded-xl border border-slate-100">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">
                  {state.jdStructured.job_title} @ {state.jdStructured.company}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {state.jdStructured.required_skills.slice(0, 12).map(s => (
                    <span key={s} className="px-2.5 py-1 rounded-full text-xs bg-indigo-50 text-indigo-700 border border-indigo-100 font-medium">{s}</span>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Required */}
              <div>
                <p className="text-xs font-bold text-rose-600 uppercase tracking-wider mb-2">
                  Required keywords missing ({state.requiredKeywords.length})
                </p>
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {state.requiredKeywords.length === 0
                    ? <p className="text-xs text-slate-400 italic">All required keywords already in your resume!</p>
                    : state.requiredKeywords.map(kw => (
                      <label key={kw.keyword} className="flex items-start gap-3 p-2.5 rounded-lg hover:bg-slate-50 cursor-pointer group">
                        <input type="checkbox"
                          className="mt-0.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-400"
                          checked={state.selectedRequired.includes(kw.keyword)}
                          onChange={() => toggleRequired(kw.keyword)} />
                        <div>
                          <span className="text-sm font-semibold text-slate-800 group-hover:text-indigo-700">{kw.keyword}</span>
                          <p className="text-xs text-slate-400 mt-0.5">{kw.explanation}</p>
                        </div>
                      </label>
                    ))
                  }
                </div>
              </div>

              {/* Preferred */}
              <div>
                <p className="text-xs font-bold text-amber-600 uppercase tracking-wider mb-2">
                  Preferred keywords missing ({state.preferredKeywords.length})
                </p>
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {state.preferredKeywords.length === 0
                    ? <p className="text-xs text-slate-400 italic">All preferred keywords already covered!</p>
                    : state.preferredKeywords.map(kw => (
                      <label key={kw.keyword} className="flex items-start gap-3 p-2.5 rounded-lg hover:bg-slate-50 cursor-pointer group">
                        <input type="checkbox"
                          className="mt-0.5 rounded border-slate-300 text-amber-500 focus:ring-amber-400"
                          checked={state.selectedPreferred.includes(kw.keyword)}
                          onChange={() => togglePreferred(kw.keyword)} />
                        <div>
                          <span className="text-sm font-semibold text-slate-800 group-hover:text-amber-700">{kw.keyword}</span>
                          <p className="text-xs text-slate-400 mt-0.5">{kw.explanation}</p>
                        </div>
                      </label>
                    ))
                  }
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* STEP 2 — Profile + GitHub                                      */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        {hasAnalysed && (
          <Card>
            <SectionPill step={2} label="Profile Links & GitHub Projects" />

            <div className="flex items-end gap-6 mb-5">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Resume Length</label>
                <div className="flex gap-2">
                  {(["1-page","2-page"] as const).map(opt => (
                    <button key={opt} onClick={() => setPageOption(opt)}
                      className={`px-5 py-2.5 rounded-xl text-sm font-semibold border transition-all ${
                        pageOption === opt
                          ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                          : "bg-white text-slate-600 border-slate-200 hover:border-indigo-300"
                      }`}>
                      {opt === "1-page" ? "1 Page" : "2 Pages"}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Font */}
            <div className="mb-5">
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">Resume Font</label>
              <p className="text-xs text-slate-400 mb-2">Font sizes are auto-calculated to fill the page — just pick the family.</p>
              <div className="flex flex-wrap gap-2">
                {FONTS.map(f => (
                  <button key={f} onClick={() => setFontFamily(f)}
                    className={`px-3.5 py-1.5 rounded-lg text-sm border transition-all ${
                      fontFamily === f
                        ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                        : "bg-white text-slate-600 border-slate-200 hover:border-indigo-300"
                    }`} style={{ fontFamily: f }}>
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-4">
              <button onClick={handleFetchProjects} disabled={projectLoading}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-purple-600 text-white font-bold shadow-md hover:bg-purple-700 active:scale-95 disabled:opacity-50 transition-all">
                {projectLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <GitBranch className="w-4 h-4" />}
                Fetch & Rank Projects
              </button>
              {projectStatus && <StatusBadge type={projectStatus.type} message={projectStatus.msg} />}
            </div>

            <ProgressLog lines={projectLogs} title="GitHub Log" />

            {/* Project selection */}
            {hasProjects && (
              <div className="mt-5">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">
                  Top 10 Projects (select at least 3 — top 4 pre-selected)
                </p>
                <div className="space-y-2">
                  {state.rankedProjects.map((p, i) => {
                    const selected = state.selectedProjectNames.includes(p.name)
                    return (
                      <label key={p.name}
                        className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${
                          selected
                            ? "border-indigo-300 bg-indigo-50"
                            : "border-slate-200 bg-white hover:border-slate-300"
                        }`}>
                        <input type="checkbox"
                          className="mt-0.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-400 shrink-0"
                          checked={selected}
                          onChange={() => toggleProject(p.name)} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-slate-400 font-mono">#{i+1}</span>
                            <span className="text-sm font-bold text-slate-800">{p.name}</span>
                            {p.category && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">{p.category}</span>
                            )}
                          </div>
                          {p.relevance_reason && (
                            <p className="text-xs text-indigo-600 mt-0.5 font-medium">{p.relevance_reason}</p>
                          )}
                          <p className="text-xs text-slate-400 mt-0.5 truncate">{p.one_line}</p>
                          {p.tech_stack.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {p.tech_stack.slice(0, 6).map(t => (
                                <span key={t} className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">{t}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </label>
                    )
                  })}
                </div>
                <p className="text-xs text-slate-400 mt-2">
                  {state.selectedProjectNames.length} selected
                  {state.selectedProjectNames.length < 3 && (
                    <span className="text-rose-500 ml-1">— need at least 3</span>
                  )}
                </p>
              </div>
            )}
          </Card>
        )}

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* STEP 3 — Generate                                              */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        {hasAnalysed && hasProjects && (
          <Card>
            <SectionPill step={3} label="Generate Tailored Resume" />

            <div className="flex items-center gap-4 mb-4">
              <button onClick={handleGenerate} disabled={generateLoading}
                className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-black text-base shadow-lg hover:shadow-xl hover:scale-105 active:scale-95 disabled:opacity-50 transition-all">
                {generateLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                Generate Tailored Resume
              </button>
              {generateStatus && <StatusBadge type={generateStatus.type} message={generateStatus.msg} />}
            </div>

            <ProgressLog lines={generateLogs} title="Generation Log" />
          </Card>
        )}

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* RESULTS                                                         */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        {hasResume && (
          <>
            {/* Score card */}
            {state.scores && <ScoreCard scores={state.scores} />}

            {/* Preview + Downloads */}
            <Card>
              <div className="flex items-center justify-between mb-4">
                <span className="font-bold text-slate-800">Resume Preview & Download</span>
                <div className="flex items-center gap-3">
                  <button onClick={() => setShowPreview(v => !v)}
                    className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors">
                    {showPreview ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    {showPreview ? "Hide" : "Show"} Preview
                  </button>
                  <button onClick={handleClearResume}
                    className="flex items-center gap-1.5 text-sm text-rose-500 hover:text-rose-700 transition-colors"
                    title="Clear resume result">
                    <Trash2 className="w-4 h-4" />
                    Clear
                  </button>
                </div>
              </div>

              <DownloadButtons
                docxId={state.docxId} pdfId={state.pdfId}
                docxName={state.docxName} pdfName={state.pdfName}
                label="Download Resume"
              />

              {showPreview && state.pdfId && (
                <div className="mt-4 rounded-xl overflow-hidden border border-slate-200">
                  <iframe
                    src={`${downloadUrl(state.pdfId)}#toolbar=0`}
                    className="w-full h-[1000px]"
                    title="Resume Preview"
                  />
                </div>
              )}
            </Card>

            {/* Edit */}
            <Card className="border-amber-100">
              <div className="flex items-center gap-2 mb-4">
                <Wand2 className="w-5 h-5 text-amber-500" />
                <span className="font-bold text-slate-800">Request Edits</span>
              </div>
              <Textarea label="Edit Instructions"
                placeholder="'Swap project 1 for Sepsis ML'  |  'Make bullets more concise'  |  'Emphasise RAG and NLP more'  |  'Change title to Senior ML Engineer'"
                value={editInstructions} onChange={setEditInstructions} rows={3} />
              <div className="flex items-center gap-3 mt-3">
                <button onClick={handleEdit} disabled={editLoading}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500 text-white font-bold shadow-sm hover:bg-amber-600 active:scale-95 disabled:opacity-50 transition-all">
                  {editLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  Apply Edits & Rebuild
                </button>
                {editStatus && <StatusBadge type={editStatus.type} message={editStatus.msg} />}
              </div>
            </Card>

            {/* ═══════════════════════════════════════════════════════════ */}
            {/* COVER LETTER                                               */}
            {/* ═══════════════════════════════════════════════════════════ */}
            <Card className="border-emerald-100">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                  <Mail className="w-5 h-5 text-emerald-600" />
                  <span className="font-bold text-slate-800 text-lg">Generate Cover Letter</span>
                </div>
                {hasCoverLetter && (
                  <button onClick={handleClearCoverLetter}
                    className="flex items-center gap-1.5 text-sm text-rose-500 hover:text-rose-700 transition-colors"
                    title="Clear cover letter result">
                    <Trash2 className="w-4 h-4" />
                    Clear
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-1.5">Tone</label>
                  <div className="flex gap-2">
                    {["Professional","Conversational","Concise"].map(t => (
                      <button key={t} onClick={() => setClTone(t)}
                        className={`flex-1 py-2 rounded-xl text-xs font-bold border transition-all ${
                          clTone === t
                            ? "bg-emerald-600 text-white border-emerald-600"
                            : "bg-white text-slate-600 border-slate-200 hover:border-emerald-300"
                        }`}>
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
                <Textarea label="Additional instructions (optional)"
                  placeholder="e.g. 'Mention my interest in AI for construction', 'Keep under 250 words'"
                  value={clExtra} onChange={setClExtra} rows={2} />
              </div>

              <div className="flex items-center gap-3 mb-4">
                <button onClick={handleCoverLetter} disabled={clLoading}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 text-white font-bold shadow-sm hover:bg-emerald-700 active:scale-95 disabled:opacity-50 transition-all">
                  {clLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                  Generate Cover Letter
                </button>
                {clStatus && <StatusBadge type={clStatus.type} message={clStatus.msg} />}
              </div>

              {/* Cover letter result */}
              {hasCoverLetter && (
                <div className="space-y-4 border-t border-emerald-100 pt-4">
                  <DownloadButtons
                    docxId={state.clDocxId} pdfId={state.clPdfId}
                    docxName={state.clDocxName} pdfName={state.clPdfName}
                    label="Download Cover Letter"
                  />

                  {/* Preview toggle */}
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-700">Preview</span>
                    <button onClick={() => setShowClPreview(v => !v)}
                      className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 transition-colors">
                      {showClPreview ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      {showClPreview ? "Hide" : "Show"}
                    </button>
                  </div>

                  {showClPreview && state.clPdfId && (
                    <div className="rounded-xl overflow-hidden border border-slate-200">
                      <iframe
                        src={`${downloadUrl(state.clPdfId)}#toolbar=0`}
                        className="w-full h-[900px]"
                        title="Cover Letter Preview"
                      />
                    </div>
                  )}

                  {/* Text preview fallback */}
                  {showClPreview && !state.clPdfId && state.coverLetterText && (
                    <div className="bg-slate-50 rounded-xl border border-slate-200 p-5 font-mono text-sm text-slate-700 whitespace-pre-wrap leading-relaxed max-h-[600px] overflow-y-auto">
                      {state.coverLetterText}
                    </div>
                  )}

                  {/* Edit cover letter */}
                  <div className="pt-2">
                    <Textarea label="Edit Cover Letter"
                      placeholder="'Make it more concise'  |  'Add enthusiasm about the company's AI work'  |  'Remove the last paragraph'"
                      value={clEditInstructions} onChange={setClEditInstructions} rows={2} />
                    <button onClick={handleCoverLetterEdit} disabled={clEditLoading}
                      className="mt-2 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-700 text-white text-sm font-bold hover:bg-slate-800 active:scale-95 disabled:opacity-50 transition-all">
                      {clEditLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                      Apply Edits
                    </button>
                  </div>
                </div>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  )
}
