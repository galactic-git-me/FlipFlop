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

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined"
    ? `http://${window.location.hostname}:8088/api`
    : "http://localhost:8088/api");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Ensure trailing slash to avoid 307 redirect which breaks cross-origin requests
  const url = `${BASE_URL}${path}`.replace(/([^/])(\?|$)/, "$1/$2");
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    signal: AbortSignal.timeout(10_000),
    redirect: "follow",
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
    grouped: (category?: string) => request<unknown[]>(`/parts/grouped${category ? `?category=${category}` : ""}`),
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

  manual: {
    submitUrl: (url: string, price_override?: number) =>
      request<import("./types").Listing>("/manual-submit/url", {
        method: "POST",
        body: JSON.stringify({ url, price_override: price_override ?? null }),
      }),
    submitImage: (file: File, title?: string, price?: number) => {
      const form = new FormData();
      form.append("file", file);
      if (title) form.append("title", title);
      if (price != null) form.append("price", String(price));
      // Don't set Content-Type — browser sets multipart boundary automatically
      const url = `${(typeof window !== "undefined" ? `http://${window.location.hostname}:8088/api` : "http://localhost:8088/api")}/manual-submit/image/`;
      return fetch(url, { method: "POST", body: form, signal: AbortSignal.timeout(45_000) })
        .then(r => { if (!r.ok) return r.json().then(d => { throw new Error(d.detail || `HTTP ${r.status}`); }); return r.json(); }) as Promise<import("./types").Listing>;
    },
  },

  demand: {
    categories: () => request<import("./types").DemandCategory[]>("/demand/categories"),
    auctionIntel: (limit?: number) => request<import("./types").AuctionIntelItem[]>(`/demand/auction-intel${limit ? `?limit=${limit}` : ""}`),
    summary: () => request<import("./types").DemandSummary>("/demand/summary"),
  },

  facebook: {
    status: () => request<{exists: boolean; valid: boolean; expired: boolean; expiry_warning: boolean; message: string; days_remaining?: number}>("/facebook/status"),
    updateCookies: (cookies_json: string) => request<{ok: boolean; message: string}>("/facebook/cookies", {
      method: "PUT",
      body: JSON.stringify({ cookies_json }),
    }),
  },

  playbooks: {
    list: (status?: string) => request<import("./types").Playbook[]>(`/playbooks${status ? `?status=${status}` : ""}`),
    get: (id: number) => request<import("./types").Playbook>(`/playbooks/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Playbook>("/playbooks", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Playbook>(`/playbooks/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: number) => request<void>(`/playbooks/${id}`, { method: "DELETE" }),
    activeKeywords: () => request<string[]>("/playbooks/active-keywords"),
    proposals: {
      list: (status?: string) =>
        request<import("./types").PlaybookProposal[]>(`/playbooks/proposals${status ? `?status=${status}` : ""}`),
      create: (data: Record<string, unknown>) =>
        request<import("./types").PlaybookProposal>("/playbooks/proposals", { method: "POST", body: JSON.stringify(data) }),
      approve: (id: number, resolved_by?: string) =>
        request<import("./types").Playbook>(`/playbooks/proposals/${id}/approve`, {
          method: "POST",
          body: JSON.stringify({ approved: true, resolved_by: resolved_by ?? "user" }),
        }),
      reject: (id: number, reason?: string) =>
        request<import("./types").PlaybookProposal>(`/playbooks/proposals/${id}/reject`, {
          method: "POST",
          body: JSON.stringify({ approved: false, rejection_reason: reason }),
        }),
    },
  },
};
