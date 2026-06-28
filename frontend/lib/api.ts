
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export function apiUrl(path: string) {
  return `${BASE}${path}`
}


function buildForm(data: Record<string, string | File | Blob>): FormData {
  const fd = new FormData()
  for (const [k, v] of Object.entries(data)) {
    if (v !== undefined && v !== null) fd.append(k, v as string | Blob)
  }
  return fd
}

async function post<T>(path: string, body: FormData): Promise<T> {
  const res = await fetch(apiUrl(path), { method: "POST", body })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? "Request failed")
  }
  return res.json()
}

// Calls onProgress for each progress line, resolves with the final "done" payload.

export async function streamPost<T>(
  path: string,
  body: FormData,
  onProgress: (msg: string) => void,
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(apiUrl(path), { method: "POST", body, signal })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? "Request failed")
  }
  if (!res.body) throw new Error("No response body")

  const reader  = res.body.getReader()
  const decoder = new TextDecoder()
  let   buffer  = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split("\n\n")
    buffer = lines.pop() ?? ""

    for (const chunk of lines) {
      const line = chunk.trim()
      if (!line.startsWith("data:")) continue
      const json = line.slice(5).trim()
      try {
        const event = JSON.parse(json)
        if (event.type === "progress") {
          onProgress(event.message)
        } else if (event.type === "error") {
          throw new Error(event.message)
        } else if (event.type === "done") {
          return event as T
        }
      } catch (e) {
        if (e instanceof SyntaxError) continue
        throw e
      }
    }
  }
  throw new Error("Stream ended without a done event")
}


import type {
  AnalyseResponse, GenerateDoneEvent, CoverLetterResponse, MatchedPayload,
  JdStructured, ResumeData, Project
} from "./types"

export async function analyseJdAndResume(params: {
  jdUrl: string
  jdText: string
  resumeFile: File
  linkedinUrl: string
  apiKey: string
}): Promise<AnalyseResponse> {
  return post("/api/analyse", buildForm({
    jd_url:       params.jdUrl,
    jd_text:      params.jdText,
    resume_file:  params.resumeFile,
    linkedin_url: params.linkedinUrl,
    api_key:      params.apiKey,
  }))
}

export async function fetchAndRankProjects(params: {
  githubUrl: string
  ghToken: string
  apiKey: string
  jdStructured: JdStructured
  onProgress: (msg: string) => void
  signal?: AbortSignal
}): Promise<{ ranked: Project[]; all_projects: Project[]; count: number }> {
  return streamPost(
    "/api/fetch-projects",
    buildForm({
      github_url:    params.githubUrl,
      gh_token:      params.ghToken,
      api_key:       params.apiKey,
      jd_structured: JSON.stringify(params.jdStructured),
    }),
    params.onProgress,
    params.signal,
  )
}

export async function generateResume(params: {
  jdStructured: JdStructured
  jdRaw: string
  resumeData: ResumeData
  resumeRawText: string
  selectedProjects: Project[]
  selectedKeywords: string[]
  linkedinUrl: string
  githubUrl: string
  pageOption: "1-page" | "2-page"
  fontFamily: string
  apiKey: string
  onProgress: (msg: string) => void
  signal?: AbortSignal
}): Promise<GenerateDoneEvent> {
  return streamPost(
    "/api/generate",
    buildForm({
      jd_structured:     JSON.stringify(params.jdStructured),
      jd_raw:            params.jdRaw,
      resume_data:       JSON.stringify(params.resumeData),
      resume_raw_text:   params.resumeRawText,
      selected_projects: JSON.stringify(params.selectedProjects),
      selected_keywords: JSON.stringify(params.selectedKeywords),
      linkedin_url:      params.linkedinUrl,
      github_url:        params.githubUrl,
      page_option:       params.pageOption,
      font_family:       params.fontFamily,
      api_key:           params.apiKey,
    }),
    params.onProgress,
    params.signal,
  )
}

export async function editResume(params: {
  editInstructions: string
  matchedPayload: MatchedPayload
  resumeData: ResumeData
  jdRaw: string
  pageOption: "1-page" | "2-page"
  fontFamily: string
  apiKey: string
}): Promise<{
  matched_payload: MatchedPayload
  docx_id: string | null
  pdf_id: string | null
  docx_name: string | null
  pdf_name: string | null
  scores: import("./types").Scores | null
  scores_md: string
}> {
  return post("/api/edit-resume", buildForm({
    edit_instructions: params.editInstructions,
    matched_payload:   JSON.stringify(params.matchedPayload),
    resume_data:       JSON.stringify(params.resumeData),
    jd_raw:            params.jdRaw,
    page_option:       params.pageOption,
    font_family:       params.fontFamily,
    api_key:           params.apiKey,
  }))
}

export async function generateCoverLetter(params: {
  tone: string
  extraInstructions: string
  jdStructured: JdStructured
  resumeData: ResumeData
  matchedPayload: MatchedPayload
  selectedKeywords: string[]
  fontSize: string
  boldBody: boolean
  apiKey: string
}): Promise<CoverLetterResponse> {
  return post("/api/cover-letter", buildForm({
    tone:               params.tone,
    extra_instructions: params.extraInstructions,
    jd_structured:      JSON.stringify(params.jdStructured),
    resume_data:        JSON.stringify(params.resumeData),
    matched_payload:    JSON.stringify(params.matchedPayload),
    selected_keywords:  JSON.stringify(params.selectedKeywords),
    font_size:          params.fontSize,
    bold_body:          params.boldBody ? "true" : "false",
    api_key:            params.apiKey,
  }))
}

export async function editCoverLetter(params: {
  editInstructions: string
  letterText: string
  jdStructured: JdStructured
  resumeData: ResumeData
  fontSize: string
  boldBody: boolean
  apiKey: string
}): Promise<CoverLetterResponse> {
  return post("/api/edit-cover-letter", buildForm({
    edit_instructions: params.editInstructions,
    letter_text:       params.letterText,
    jd_structured:     JSON.stringify(params.jdStructured),
    resume_data:       JSON.stringify(params.resumeData),
    font_size:         params.fontSize,
    bold_body:         params.boldBody ? "true" : "false",
    api_key:           params.apiKey,
  }))
}

export function downloadUrl(fileId: string): string {
  // Relative path — proxied through Next.js to the backend (same-origin, fixes cross-origin PDF iframe blocking)
  return `/api/download/${fileId}`
}
