"use client"
import { FileText, Download } from "lucide-react"
import { downloadUrl } from "@/lib/api"

interface Props {
  docxId: string | null
  pdfId:  string | null
  docxName?: string | null
  pdfName?:  string | null
  label?: string
}

export default function DownloadButtons({ docxId, pdfId, docxName, pdfName, label }: Props) {
  if (!docxId && !pdfId) return null

  return (
    <div>
      {label && <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">{label}</p>}
      <div className="flex flex-wrap gap-3">
        {docxId && (
          <a
            href={downloadUrl(docxId)}
            download={docxName ?? "resume.docx"}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-semibold shadow-sm hover:bg-indigo-700 active:scale-95 transition-all"
          >
            <FileText className="w-4 h-4" />
            Download Word
          </a>
        )}
        {pdfId && (
          <a
            href={downloadUrl(pdfId)}
            download={pdfName ?? "resume.pdf"}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-sm font-semibold shadow-sm hover:bg-emerald-700 active:scale-95 transition-all"
          >
            <Download className="w-4 h-4" />
            Download PDF
          </a>
        )}
      </div>
    </div>
  )
}
