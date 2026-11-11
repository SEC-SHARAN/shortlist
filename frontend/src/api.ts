import type { User } from "./types";

let token: string | null = sessionStorage.getItem("ats_token");
export const setToken = (t: string | null) => { token = t; t ? sessionStorage.setItem("ats_token", t) : sessionStorage.removeItem("ats_token"); };
export const hasToken = () => !!token;

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

async function parse(res: Response) {
  if (res.ok) return res.status === 204 ? null : res.headers.get("content-type")?.includes("json") ? res.json() : res;
  let msg = res.statusText;
  try {
    const b = await res.json();
    msg = Array.isArray(b.errors) && b.errors.length ? b.errors.map((e: any) => `${e.field}: ${e.message}`).join("; ") : typeof b.detail === "string" ? b.detail : msg;
  } catch { /* non-JSON error */ }
  if (res.status === 401 && token) { setToken(null); window.location.assign("/login"); }
  throw new ApiError(res.status, msg);
}

const API_BASE = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; form?: FormData; params?: Record<string, any> } = {}): Promise<T> {
  const qs = new URLSearchParams();
  Object.entries(opts.params ?? {}).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    (Array.isArray(v) ? v : [v]).forEach((x) => qs.append(k, String(x)));
  });
  const q = qs.toString();
  const res = await fetch(`${API_BASE}${path}${q ? "?" + q : ""}`, {
    method: opts.method ?? (opts.body || opts.form ? "POST" : "GET"),
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(opts.body ? { "Content-Type": "application/json" } : {}) },
    body: opts.form ?? (opts.body ? JSON.stringify(opts.body) : undefined),
  });
  return parse(res) as Promise<T>;
}

export async function download(path: string, params: Record<string, any>, filename: string) {
  const res = (await api<Response>(path, { params })) as unknown as Response;
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click(); URL.revokeObjectURL(url);
}

export const login = async (email: string, password: string): Promise<User> => {
  const r = await api<{ access_token: string; user: User }>("/auth/login", { body: { email, password } });
  setToken(r.access_token); return r.user;
};
