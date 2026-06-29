import type { ProviderInfo } from "./types";

// Mirrors backend/app/llm/registry.py. Used to seed the picker so it's always
// populated and properly labeled — even before /api/providers responds or if the
// backend is cold/unreachable. Refreshed with live data once the fetch succeeds.
export const FALLBACK_PROVIDERS: ProviderInfo[] = [
  {
    key: "gemini",
    label: "Google Gemini",
    env_key_name: "GOOGLE_API_KEY",
    free_tier: true,
    notes: "Generous free tier — great for a free live demo.",
    default_model: "gemini-2.0-flash",
    models: [
      { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash", free: true },
      { id: "gemini-1.5-flash", label: "Gemini 1.5 Flash", free: true },
      { id: "gemini-1.5-pro", label: "Gemini 1.5 Pro", free: true },
    ],
  },
  {
    key: "groq",
    label: "Groq (open models)",
    env_key_name: "GROQ_API_KEY",
    free_tier: true,
    notes: "Free and very fast. Great for a free live demo.",
    default_model: "llama-3.3-70b-versatile",
    models: [
      { id: "llama-3.3-70b-versatile", label: "Llama 3.3 70B", free: true },
      { id: "llama-3.1-8b-instant", label: "Llama 3.1 8B (fast)", free: true },
    ],
  },
  {
    key: "anthropic",
    label: "Anthropic (Claude)",
    env_key_name: "ANTHROPIC_API_KEY",
    free_tier: false,
    notes: "Premium quality. Paid API key required.",
    default_model: "claude-opus-4-8",
    models: [
      { id: "claude-opus-4-8", label: "Claude Opus 4.8", free: false },
      { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6", free: false },
      { id: "claude-haiku-4-5", label: "Claude Haiku 4.5", free: false },
    ],
  },
  {
    key: "openai",
    label: "OpenAI (GPT)",
    env_key_name: "OPENAI_API_KEY",
    free_tier: false,
    notes: "Widely recognized. Paid API key required.",
    default_model: "gpt-4o-mini",
    models: [
      { id: "gpt-4o", label: "GPT-4o", free: false },
      { id: "gpt-4o-mini", label: "GPT-4o mini", free: false },
    ],
  },
];
