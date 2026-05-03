export interface ScanSite {
  name: string;
  url: string;
  status: "pending" | "scanning" | "done" | "error";
  found: number;
  gems: number;
  error: string | null;
}

export interface ScanStatus {
  running: boolean;
  total: number;
  completed: number;
  current_sites: string[];
  sites: ScanSite[];
  started_at: string | null;
  finished_at: string | null;
  total_found: number;
  total_gems: number;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8088/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    signal: AbortSignal.timeout(10_000),
    ...init,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

function qs(params?: Record<string, string | undefined>): string {
  if (!params) return "";
  const p = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined)) as Record<string, string>;
  return Object.keys(p).length ? "?" + new URLSearchParams(p).toString() : "";
}

export const api = {
  listings: {
    list: (params?: Record<string, string>) => request<unknown[]>(`/listings${qs(params)}`),
    stats: () => request<{ total_listings: number; gems_count: number; avg_profit: number }>("/listings/stats"),
    get: (id: number) => request<unknown>(`/listings/${id}`),
  },

  flips: {
    list: () => request<unknown[]>("/flips"),
    create: (data: Record<string, unknown>) =>
      request<unknown>("/flips", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/flips/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    markSold: (id: number, data: { actual_sale_price: number; sale_platform: string }) =>
      request<unknown>(`/flips/${id}/sold`, { method: "POST", body: JSON.stringify(data) }),
    generateListing: (id: number) =>
      request<{ titles: string[]; description: string }>(`/flips/${id}/generate-listing`, { method: "POST" }),
    generateImages: (id: number) =>
      request<{ images: string[] }>(`/flips/${id}/generate-images`, { method: "POST" }),
  },

  parts: {
    list: (category?: string) => request<unknown[]>(`/parts${category ? `?category=${category}` : ""}`),
    cases: (params?: Record<string, string>) => request<unknown[]>(`/parts/cases${qs(params)}`),
    themes: () => request<string[]>("/parts/themes"),
  },

  sources: {
    list: () => request<unknown[]>("/sources"),
    create: (data: Record<string, unknown>) =>
      request<unknown>("/sources", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/sources/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: number) => request<void>(`/sources/${id}`, { method: "DELETE" }),
    trigger: (id: number) => request<unknown>(`/sources/${id}/scrape`, { method: "POST" }),
  },

  config: {
    get: () => request<unknown>("/config/search"),
    update: (data: Record<string, unknown>) =>
      request<unknown>("/config/search", { method: "PUT", body: JSON.stringify(data) }),
  },

  settings: {
    get: () => request<unknown>("/settings"),
    update: (data: Record<string, unknown>) =>
      request<unknown>("/settings", { method: "PUT", body: JSON.stringify(data) }),
  },

  intel: {
    summary: () =>
      request<{
        total_flips: number;
        total_profit: number;
        avg_profit: number;
        avg_roi_pct: number;
        avg_days_to_sell: number;
        best_source: string | null;
        best_cpu_tier: string | null;
      }>("/intel/summary"),
    bySource: () => request<{ source: string; count: number; avg_profit: number; total_profit: number }[]>("/intel/by-source"),
    byCpuTier: () => request<{ cpu_tier: string; count: number; avg_profit: number }[]>("/intel/by-cpu"),
    byPlatform: () => request<{ platform: string; count: number; avg_profit: number }[]>("/intel/by-platform"),
    history: (params?: Record<string, string>) => request<unknown[]>(`/intel/history${qs(params)}`),
    recommendations: () => request<{ insight: string; action: string; confidence: number }[]>("/intel/recommendations"),
  },

  chat: {
    send: (message: string, history: { role: string; content: string }[], listing_id?: number) =>
      request<{ response: string; model_used: string }>("/chat", {
        method: "POST",
        body: JSON.stringify({ message, history, listing_id }),
      }),
  },

  swarms: {
    list: () => request<unknown[]>("/swarms"),
    trigger: (id: string) => request<unknown>(`/swarms/${id}/trigger`, { method: "POST" }),
    scanStatus: () => request<ScanStatus>("/swarms/scan/status"),
  },
};
