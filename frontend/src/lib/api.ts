// API client. Base URL comes solely from VITE_API_URL; when unset (dev) it falls
// back to a same-origin relative path so the Vite proxy handles /api. Downloads
// use the same base, so previews/downloads never break the way the old
// hardcoded-localhost proxy did.
import type { SseEvent } from "./types";

const BASE = import.meta.env.VITE_API_URL?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {}

async function detail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (body && typeof body.detail === "string") return body.detail;
  } catch {
    /* not JSON */
  }
  return `Request failed (${res.status})`;
}

/** POST form data, parse JSON. */
export async function post<T>(
  path: string,
  form: FormData,
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "POST", body: form, signal });
  if (!res.ok) throw new ApiError(await detail(res));
  return (await res.json()) as T;
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal });
  if (!res.ok) throw new ApiError(await detail(res));
  return (await res.json()) as T;
}

/**
 * POST form data and consume the Server-Sent Events stream.
 * Invokes onEvent for each progress/done/error event; resolves when the stream
 * ends. Honors an AbortSignal so the UI can cancel long generations.
 */
export async function streamPost(
  path: string,
  form: FormData,
  onEvent: (e: SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: "POST", body: form, signal });
  if (!res.ok) throw new ApiError(await detail(res));
  if (!res.body) throw new ApiError("No response stream.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    let sep: number;
    while ((sep = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(5).trim()) as SseEvent);
      } catch {
        /* ignore malformed frame */
      }
    }
  }
}

export function downloadUrl(fileId: string): string {
  return `${BASE}/api/download/${fileId}`;
}
