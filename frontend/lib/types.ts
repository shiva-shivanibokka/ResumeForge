// ─── Shared types used across the app ────────────────────────────────────────

export interface JdStructured {
  job_title: string
  company: string
  location: string
  job_type: string
  required_skills: string[]
  preferred_skills: string[]
  responsibilities: string[]
  qualifications: string[]
  keywords: string[]
}

export interface EducationEntry {
  school: string
  degree: string
  dates: string
  gpa: string | null
  location: string
}

export interface ExperienceEntry {
  company: string
  title: string
  dates: string
  location: string
  bullets: string[]
}

export interface ResumeData {
  name: string
  email: string
  phone: string
  linkedin: string
  linkedin_url: string
  github: string
  github_url: string
  location: string
  education: EducationEntry[]
  experience: ExperienceEntry[]
  skills: string[]
  summary: string
}

export interface Keyword {
  keyword: string
  explanation: string
}

export interface Project {
  name: string
  one_line: string
  tech_stack: string[]
  category: string
  keywords: string[]
  bullets: string[]
  github_url: string
  repo_name: string
  relevance_reason?: string
  is_relevant_for_tech: boolean
}

export interface SelectedProject {
  name: string
  tech_stack: string[]
  bullets: string[]
  github_url: string
}

export interface MatchedPayload {
  job_title: string
  company: string
  resume_title: string
  selected_projects: SelectedProject[]
  tailored_skills: Record<string, string>
  tailored_experience: ExperienceEntry[]
  ats_keywords_used: string[]
}

export interface Scores {
  ats_score: number
  ats_label: string
  ats_feedback: string[]
  match_score: number
  match_label: string
  match_feedback: string[]
  matched_keywords: string[]
  missing_keywords: string[]
  error: string | null
}

export interface AnalyseResponse {
  jd_structured: JdStructured
  jd_raw: string
  resume_data: ResumeData
  resume_raw_text: string
  linkedin_url: string
  gap: {
    required_missing: Keyword[]
    preferred_missing: Keyword[]
    already_have: string[]
    skill_categories: Record<string, { have: string[]; missing: string[] }>
    summary: string
  }
  gap_markdown: string
  required_keywords: Keyword[]
  preferred_keywords: Keyword[]
}

export interface GenerateDoneEvent {
  matched_payload: MatchedPayload
  docx_id: string | null
  pdf_id: string | null
  docx_name: string | null
  pdf_name: string | null
  scores: Scores
  scores_md: string
  job_label: string
}

export interface CoverLetterResponse {
  letter_text: string
  docx_id: string | null
  pdf_id: string | null
  docx_name: string | null
  pdf_name: string | null
}

// App-level state
export interface AppState {
  // Step 1
  jdStructured: JdStructured | null
  jdRaw: string
  resumeData: ResumeData | null
  resumeRawText: string
  linkedinUrl: string
  requiredKeywords: Keyword[]
  preferredKeywords: Keyword[]
  selectedRequired: string[]
  selectedPreferred: string[]

  // Step 2
  githubUrl: string
  rankedProjects: Project[]
  allProjects: Project[]
  selectedProjectNames: string[]

  // Step 3
  matchedPayload: MatchedPayload | null
  docxId: string | null
  pdfId: string | null
  docxName: string | null
  pdfName: string | null
  scores: Scores | null
  scoresMd: string

  // Cover letter
  coverLetterText: string
  clDocxId: string | null
  clPdfId: string | null
  clDocxName: string | null
  clPdfName: string | null
}

export const INITIAL_STATE: AppState = {
  jdStructured: null, jdRaw: "", resumeData: null, resumeRawText: "",
  linkedinUrl: "", requiredKeywords: [], preferredKeywords: [],
  selectedRequired: [], selectedPreferred: [],
  githubUrl: "", rankedProjects: [], allProjects: [], selectedProjectNames: [],
  matchedPayload: null, docxId: null, pdfId: null, docxName: null, pdfName: null,
  scores: null, scoresMd: "",
  coverLetterText: "", clDocxId: null, clPdfId: null, clDocxName: null, clPdfName: null,
}
