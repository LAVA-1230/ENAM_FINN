// API client. Base URL from NEXT_PUBLIC_API_BASE. Replay responses carry X-Finn-Replay, which feeds the banner.
export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/$/, "");

type Listener<T> = (v: T) => void;
let replayLabel: string | null = null;
const replayListeners = new Set<Listener<string | null>>();
const slowListeners = new Set<Listener<boolean>>();

export function onReplay(fn: Listener<string | null>) {
  replayListeners.add(fn);
  fn(replayLabel);
  return () => { replayListeners.delete(fn); };
}

export function onSlow(fn: Listener<boolean>) {
  slowListeners.add(fn);
  return () => { slowListeners.delete(fn); };
}

function setReplay(v: string | null) {
  if (v !== replayLabel) {
    replayLabel = v;
    replayListeners.forEach((l) => l(v));
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, msg: string) { super(msg); this.status = status; }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  // free hosts sleep: if an answer takes more than 4s the UI says "Waking up FINN"
  const timer = setTimeout(() => slowListeners.forEach((l) => l(true)), 4000);
  try {
    const r = await fetch(`${API_BASE}/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
    if (!init?.method || init.method === "GET") setReplay(r.headers.get("X-Finn-Replay"));
    if (!r.ok) {
      let msg = `Request failed (${r.status})`;
      try { msg = (await r.json()).detail || msg; } catch { /* not JSON */ }
      throw new ApiError(r.status, msg);
    }
    return (await r.json()) as T;
  } finally {
    clearTimeout(timer);
    slowListeners.forEach((l) => l(false));
  }
}

export function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  return api<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
}
