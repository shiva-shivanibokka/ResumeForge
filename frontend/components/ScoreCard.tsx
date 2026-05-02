"use client"
import type { Scores } from "@/lib/types"
import { CheckCircle2, XCircle, TrendingUp, Shield } from "lucide-react"

interface Props { scores: Scores }

function ScoreRing({ score, label, icon: Icon, color }: {
  score: number; label: string; icon: React.ElementType; color: string
}) {
  const pct = (score / 10) * 100
  const r   = 36; const circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-24 h-24">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r={r} fill="none" strokeWidth="10" className="stroke-slate-100" />
          <circle cx="50" cy="50" r={r} fill="none" strokeWidth="10"
            stroke={color}
            strokeDasharray={`${dash} ${circ}`}
            strokeLinecap="round"
            style={{ transition: "stroke-dasharray 0.6s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-black" style={{ color }}>{score}</span>
          <span className="text-xs text-slate-400 font-medium">/10</span>
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <Icon className="w-4 h-4" style={{ color }} />
        <span className="text-sm font-bold text-slate-700">{label}</span>
      </div>
    </div>
  )
}

function scoreColor(n: number): string {
  if (n >= 8) return "#10b981"  // emerald
  if (n >= 6) return "#f59e0b"  // amber
  return "#f43f5e"               // rose
}

export default function ScoreCard({ scores }: Props) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="bg-gradient-to-r from-indigo-50 to-purple-50 px-6 py-4 border-b border-slate-100">
        <h3 className="font-bold text-slate-800 text-base">Resume Scores</h3>
      </div>

      <div className="p-6">
        {/* Score rings */}
        <div className="flex items-center justify-around mb-6">
          <ScoreRing score={scores.ats_score}   label={`ATS — ${scores.ats_label}`}      icon={Shield}    color={scoreColor(scores.ats_score)} />
          <ScoreRing score={scores.match_score} label={`JD Match — ${scores.match_label}`} icon={TrendingUp} color={scoreColor(scores.match_score)} />
        </div>

        {/* Tips */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          {(scores.ats_feedback ?? []).length > 0 && (
            <div>
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">ATS Tips</p>
              <ul className="space-y-1.5">
                {(scores.ats_feedback ?? []).map((t, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-xs text-slate-600">
                    <span className="text-indigo-400 mt-0.5 shrink-0">✦</span>{t}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(scores.match_feedback ?? []).length > 0 && (
            <div>
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Match Tips</p>
              <ul className="space-y-1.5">
                {(scores.match_feedback ?? []).map((t, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-xs text-slate-600">
                    <span className="text-indigo-400 mt-0.5 shrink-0">✦</span>{t}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Keywords */}
        {((scores.matched_keywords ?? []).length > 0 || (scores.missing_keywords ?? []).length > 0) && (
          <div className="pt-4 border-t border-slate-100 space-y-3">
            {(scores.matched_keywords ?? []).length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  <span className="text-xs font-bold text-emerald-700">Keywords matched</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(scores.matched_keywords ?? []).slice(0, 14).map(kw => (
                    <span key={kw} className="px-2 py-0.5 rounded-full text-xs bg-emerald-50 text-emerald-700 border border-emerald-200">{kw}</span>
                  ))}
                </div>
              </div>
            )}
            {(scores.missing_keywords ?? []).length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <XCircle className="w-3.5 h-3.5 text-rose-500" />
                  <span className="text-xs font-bold text-rose-700">Keywords missing</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(scores.missing_keywords ?? []).slice(0, 8).map(kw => (
                    <span key={kw} className="px-2 py-0.5 rounded-full text-xs bg-rose-50 text-rose-700 border border-rose-200">{kw}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
