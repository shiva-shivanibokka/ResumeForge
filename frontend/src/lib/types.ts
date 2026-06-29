// Shapes returned by the ResumeForge API. Hand-maintained to mirror the backend
// routers; api.ts validates the few fields the UI depends on at runtime.

export interface ModelInfo {
  id: string;
  label: string;
  free: boolean;
}
export interface ProviderInfo {
  key: string;
  label: string;
  env_key_name: string;
  free_tier: boolean;
  notes: string;
  default_model: string;
  models: ModelInfo[];
}

export interface KeywordItem {
  keyword: string;
  explanation: string;
}

export interface AnalyseResponse {
  jd_structured: Record<string, unknown>;
  jd_raw: string;
  resume_data: Record<string, unknown>;
  resume_raw_text: string;
  linkedin_url: string;
  gap: Record<string, unknown>;
  gap_markdown: string;
  required_keywords: KeywordItem[];
  preferred_keywords: KeywordItem[];
}

export interface Project {
  name: string;
  one_line?: string;
  category?: string;
  tech_stack?: string[];
  relevance_reason?: string;
  match_score?: number;
  github_url?: string;
  stars?: number;
  [k: string]: unknown;
}

export interface FetchProjectsDone {
  ranked: Project[];
  all_projects: Project[];
  count: number;
}

export interface Scores {
  ats_score?: number;
  ats_label?: string;
  ats_feedback?: string[];
  match_score?: number;
  match_label?: string;
  match_feedback?: string[];
  matched_keywords?: string[];
  missing_keywords?: string[];
  [k: string]: unknown;
}

export interface GenerateDone {
  matched_payload: Record<string, unknown>;
  docx_id: string | null;
  pdf_id: string | null;
  docx_name: string | null;
  pdf_name: string | null;
  scores: Scores | null;
  before_scores?: Scores | null;
  scores_md: string;
  job_label?: string;
}

export interface CoverLetterDone {
  letter_text: string;
  docx_id: string | null;
  pdf_id: string | null;
  docx_name: string | null;
  pdf_name: string | null;
}

// SSE event envelope emitted by streaming endpoints.
export type SseEvent =
  | { type: "progress"; message: string }
  | { type: "error"; message: string }
  | ({ type: "done" } & Record<string, unknown>);
