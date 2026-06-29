import { create } from "zustand";
import { ApiError, getJson, post, streamPost } from "./lib/api";
import { FALLBACK_PROVIDERS } from "./lib/providers";
import type {
  AnalyseResponse,
  CoverLetterDone,
  GenerateDone,
  KeywordItem,
  Project,
  ProviderInfo,
  Scores,
  SseEvent,
} from "./lib/types";

export type StepId = "materials" | "projects" | "forge" | "letter";

type Op =
  | "providers"
  | "analyse"
  | "projects"
  | "generate"
  | "editResume"
  | "coverLetter"
  | "editCover";

interface State {
  // config
  providers: ProviderInfo[];
  provider: string;
  model: string;
  apiKey: string;
  ghToken: string;

  // inputs
  jdUrl: string;
  jdText: string;
  linkedinUrl: string;
  githubUrl: string;
  resumeFile: File | null;
  pageOption: "1-page" | "2-page";
  fontFamily: string;

  // flow
  step: StepId;
  reached: Record<StepId, boolean>;
  busy: Op | null;
  error: string | null;

  // analyse results
  analysis: AnalyseResponse | null;
  selectedKeywords: string[];

  // projects
  ranked: Project[];
  selectedProjects: Project[];
  projectsLog: string[];
  cacheStatus: { enabled: boolean; cached: boolean; count: number; embedded_at: string | null } | null;

  // forge (resume)
  matchedPayload: Record<string, unknown> | null;
  resume: { docxId: string | null; pdfId: string | null; docxName: string | null; pdfName: string | null };
  scores: Scores | null;
  scoresMd: string;
  jobLabel: string;
  generateLog: string[];

  // cover letter
  tone: string;
  extraInstructions: string;
  letterText: string;
  cover: { docxId: string | null; pdfId: string | null; docxName: string | null; pdfName: string | null };

  // actions
  set: <K extends keyof State>(key: K, value: State[K]) => void;
  loadProviders: () => Promise<void>;
  onProviderChange: (key: string) => void;
  toggleKeyword: (k: string) => void;
  toggleProject: (p: Project) => void;
  analyse: () => Promise<void>;
  loadCacheStatus: () => Promise<void>;
  fetchProjects: (force?: boolean) => Promise<void>;
  generate: () => Promise<void>;
  editResume: (instructions: string) => Promise<void>;
  generateCover: () => Promise<void>;
  editCover: (instructions: string) => Promise<void>;
  cancel: () => void;
  goTo: (s: StepId) => void;
}

let controller: AbortController | null = null;

function creds(s: State, form: FormData) {
  form.set("provider", s.provider);
  form.set("model", s.model);
  form.set("api_key", s.apiKey);
}

export const useStore = create<State>((set, get) => ({
  providers: FALLBACK_PROVIDERS,
  provider: "gemini",
  model: "gemini-2.0-flash",
  apiKey: "",
  ghToken: "",

  jdUrl: "",
  jdText: "",
  linkedinUrl: "",
  githubUrl: "",
  resumeFile: null,
  pageOption: "1-page",
  fontFamily: "Calibri",

  step: "materials",
  reached: { materials: true, projects: false, forge: false, letter: false },
  busy: null,
  error: null,

  analysis: null,
  selectedKeywords: [],

  ranked: [],
  selectedProjects: [],
  projectsLog: [],
  cacheStatus: null,

  matchedPayload: null,
  resume: { docxId: null, pdfId: null, docxName: null, pdfName: null },
  scores: null,
  scoresMd: "",
  jobLabel: "",
  generateLog: [],

  tone: "Professional",
  extraInstructions: "",
  letterText: "",
  cover: { docxId: null, pdfId: null, docxName: null, pdfName: null },

  set: (key, value) => set({ [key]: value } as Pick<State, typeof key>),

  goTo: (s) => {
    if (get().reached[s]) set({ step: s, error: null });
  },

  loadProviders: async () => {
    try {
      const { providers } = await getJson<{ providers: ProviderInfo[] }>("/api/providers");
      set({ providers });
      // Default to the first free provider so the demo works without a paid key.
      const free = providers.find((p) => p.free_tier) ?? providers[0];
      if (free) set({ provider: free.key, model: free.default_model });
    } catch {
      /* picker will show empty; user can still type a key */
    }
  },

  onProviderChange: (key) => {
    const p = get().providers.find((x) => x.key === key);
    set({ provider: key, model: p?.default_model ?? "" });
  },

  toggleKeyword: (k) => {
    const cur = get().selectedKeywords;
    set({ selectedKeywords: cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k] });
  },

  toggleProject: (p) => {
    const cur = get().selectedProjects;
    const has = cur.some((x) => x.name === p.name);
    set({ selectedProjects: has ? cur.filter((x) => x.name !== p.name) : [...cur, p] });
  },

  analyse: async () => {
    const s = get();
    if (!s.resumeFile) {
      set({ error: "Add your resume (PDF or DOCX) to start." });
      return;
    }
    if (!s.jdUrl.trim() && !s.jdText.trim()) {
      set({ error: "Add a job posting — paste a URL or the text." });
      return;
    }
    set({ busy: "analyse", error: null });
    try {
      const form = new FormData();
      creds(s, form);
      form.set("jd_url", s.jdUrl);
      form.set("jd_text", s.jdText);
      form.set("linkedin_url", s.linkedinUrl);
      form.set("resume_file", s.resumeFile);
      const data = await post<AnalyseResponse>("/api/analyse", form);
      set({
        analysis: data,
        linkedinUrl: data.linkedin_url || s.linkedinUrl,
        selectedKeywords: [],
        reached: { ...get().reached, projects: true },
        step: "projects",
      });
      get().loadCacheStatus();
    } catch (e) {
      set({ error: msg(e) });
    } finally {
      set({ busy: null });
    }
  },

  loadCacheStatus: async () => {
    const s = get();
    if (!s.githubUrl.trim()) {
      set({ cacheStatus: null });
      return;
    }
    try {
      const status = await getJson<State["cacheStatus"]>(
        `/api/projects/cache?github_url=${encodeURIComponent(s.githubUrl)}`,
      );
      set({ cacheStatus: status });
    } catch {
      set({ cacheStatus: null });
    }
  },

  fetchProjects: async (force = false) => {
    const s = get();
    if (!s.githubUrl.trim()) {
      set({ error: "Add your GitHub profile URL to pull projects." });
      return;
    }
    if (!s.analysis) return;
    controller = new AbortController();
    set({ busy: "projects", error: null, projectsLog: [], ranked: [] });
    try {
      const form = new FormData();
      creds(s, form);
      form.set("github_url", s.githubUrl);
      form.set("gh_token", s.ghToken);
      form.set("jd_structured", JSON.stringify(s.analysis.jd_structured));
      form.set("force_reembed", String(force));
      await streamPost("/api/fetch-projects", form, handleStream(set, get, "projectsLog", (done) => {
        const ranked = (done.ranked as Project[]) ?? [];
        set({ ranked, selectedProjects: ranked.slice(0, 4) });
      }), controller.signal);
      await get().loadCacheStatus();
    } catch (e) {
      if (!aborted(e)) set({ error: msg(e) });
    } finally {
      set({ busy: null });
    }
  },

  generate: async () => {
    const s = get();
    if (!s.analysis || s.selectedProjects.length === 0) {
      set({ error: "Pick at least one project to feature." });
      return;
    }
    controller = new AbortController();
    // Jump to the Forge dashboard immediately so the user watches the build live.
    set({
      busy: "generate",
      error: null,
      generateLog: [],
      reached: { ...s.reached, forge: true, letter: true },
      step: "forge",
    });
    try {
      const form = new FormData();
      creds(s, form);
      form.set("jd_structured", JSON.stringify(s.analysis.jd_structured));
      form.set("jd_raw", s.analysis.jd_raw);
      form.set("resume_data", JSON.stringify(s.analysis.resume_data));
      form.set("resume_raw_text", s.analysis.resume_raw_text);
      form.set("selected_projects", JSON.stringify(s.selectedProjects));
      form.set("selected_keywords", JSON.stringify(s.selectedKeywords));
      form.set("linkedin_url", s.linkedinUrl);
      form.set("github_url", s.githubUrl);
      form.set("page_option", s.pageOption);
      form.set("font_family", s.fontFamily);
      await streamPost("/api/generate", form, handleStream(set, get, "generateLog", (done) => {
        const d = done as unknown as GenerateDone;
        set({
          matchedPayload: d.matched_payload,
          resume: { docxId: d.docx_id, pdfId: d.pdf_id, docxName: d.docx_name, pdfName: d.pdf_name },
          scores: d.scores,
          scoresMd: d.scores_md,
          jobLabel: d.job_label ?? "",
          reached: { ...get().reached, forge: true, letter: true },
          step: "forge",
        });
      }), controller.signal);
    } catch (e) {
      if (!aborted(e)) set({ error: msg(e) });
    } finally {
      set({ busy: null });
    }
  },

  // Empty instructions => pure reformat (rebuild with current page/font, no LLM edit).
  editResume: async (instructions) => {
    const s = get();
    if (!s.matchedPayload || !s.analysis) return;
    set({ busy: "editResume", error: null });
    try {
      const form = new FormData();
      creds(s, form);
      form.set("edit_instructions", instructions.trim() || "Keep all content exactly as-is.");
      form.set("matched_payload", JSON.stringify(s.matchedPayload));
      form.set("resume_data", JSON.stringify(s.analysis.resume_data));
      form.set("jd_raw", s.analysis.jd_raw);
      form.set("page_option", s.pageOption);
      form.set("font_family", s.fontFamily);
      const d = await post<GenerateDone>("/api/edit-resume", form);
      set({
        matchedPayload: d.matched_payload,
        resume: { docxId: d.docx_id, pdfId: d.pdf_id, docxName: d.docx_name, pdfName: d.pdf_name },
        scores: d.scores ?? s.scores,
        scoresMd: d.scores_md || s.scoresMd,
      });
    } catch (e) {
      set({ error: msg(e) });
    } finally {
      set({ busy: null });
    }
  },

  generateCover: async () => {
    const s = get();
    if (!s.analysis || !s.matchedPayload) return;
    set({ busy: "coverLetter", error: null });
    try {
      const form = new FormData();
      creds(s, form);
      form.set("tone", s.tone);
      form.set("extra_instructions", s.extraInstructions);
      form.set("jd_structured", JSON.stringify(s.analysis.jd_structured));
      form.set("resume_data", JSON.stringify(s.analysis.resume_data));
      form.set("matched_payload", JSON.stringify(s.matchedPayload));
      form.set("selected_keywords", JSON.stringify(s.selectedKeywords));
      const d = await post<CoverLetterDone>("/api/cover-letter", form);
      set({
        letterText: d.letter_text,
        cover: { docxId: d.docx_id, pdfId: d.pdf_id, docxName: d.docx_name, pdfName: d.pdf_name },
      });
    } catch (e) {
      set({ error: msg(e) });
    } finally {
      set({ busy: null });
    }
  },

  editCover: async (instructions) => {
    const s = get();
    if (!s.analysis || !s.letterText || !instructions.trim()) return;
    set({ busy: "editCover", error: null });
    try {
      const form = new FormData();
      creds(s, form);
      form.set("edit_instructions", instructions);
      form.set("letter_text", s.letterText);
      form.set("jd_structured", JSON.stringify(s.analysis.jd_structured));
      form.set("resume_data", JSON.stringify(s.analysis.resume_data));
      const d = await post<CoverLetterDone>("/api/edit-cover-letter", form);
      set({
        letterText: d.letter_text,
        cover: { docxId: d.docx_id, pdfId: d.pdf_id, docxName: d.docx_name, pdfName: d.pdf_name },
      });
    } catch (e) {
      set({ error: msg(e) });
    } finally {
      set({ busy: null });
    }
  },

  cancel: () => {
    controller?.abort();
    set({ busy: null });
  },
}));

function handleStream(
  set: (p: Partial<State>) => void,
  get: () => State,
  logKey: "projectsLog" | "generateLog",
  onDone: (done: Record<string, unknown>) => void,
) {
  return (e: SseEvent) => {
    if (e.type === "progress") {
      set({ [logKey]: [...get()[logKey], e.message] } as Partial<State>);
    } else if (e.type === "error") {
      set({ error: e.message });
    } else if (e.type === "done") {
      onDone(e as Record<string, unknown>);
    }
  };
}

function msg(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "Something went wrong. Please try again.";
}

function aborted(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

export type { KeywordItem, Project };
