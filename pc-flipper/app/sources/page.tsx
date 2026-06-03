"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  RefreshCw, Plus, Trash2, CheckCircle, XCircle,
  Globe, Code, AlertTriangle, Database,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, SearchTelemetryItem, ScheduleJob, ScanStatus, SourceSearchTerm, API_BASE_URL } from "@/lib/api";
import { DataSource } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

// ─── Constants ────────────────────────────────────────────────────────────────

const REFRESH_MS = 8_000;

const VENDOR_GROUPS: Record<string, string[]> = {
  eBay:    ["eBay", "eBay UK", "eBay (Worldwide)", "eBay UK Auctions"],
  Amazon:  ["Amazon", "Amazon UK"],
  Temu:    ["Temu"],
  Others:  ["AliExpress","Alibaba","BargainHardware","CherryTree Inc","Gumtree",
             "BidSpotter","Apex Auctions","Wilsons Auctions","i-bidder","Preloved",
             "John Pye","Manual Submission","Manual Photo","Merkandi",
             "Wholesale Clearance UK"],
};

const SCOPES = ["flip_opportunities", "upgrade_parts", "cases", "accessories"] as const;
type Scope = typeof SCOPES[number];

const SCOPE_LABELS: Record<Scope, string> = {
  flip_opportunities: "flip_opp",
  upgrade_parts:      "components",
  cases:              "cases",
  accessories:        "accessories",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function ageStr(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const secs = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
    const m = Math.floor(secs / 60), h = Math.floor(m / 60);
    if (h > 0) return `${h}h ${(m % 60).toString().padStart(2,"0")}m`;
    return `${m.toString().padStart(2,"0")}m ${(secs % 60).toString().padStart(2,"0")}s`;
  } catch { return "—"; }
}

function nextAgeStr(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const secs = Math.floor((new Date(iso).getTime() - Date.now()) / 1000);
    if (secs <= 0) return "now";
    const m = Math.floor(secs / 60), h = Math.floor(m / 60);
    if (h > 0) return `in ${h}h ${(m % 60).toString().padStart(2,"0")}m`;
    return `in ${m}m ${(secs % 60).toString().padStart(2,"0")}s`;
  } catch { return "—"; }
}

type CellState = "success" | "error" | "retry" | "zero" | "blank";

function cellState(item: SearchTelemetryItem | undefined): [CellState, number] {
  if (!item) return ["blank", 0];
  const err = (item.error ?? "").toLowerCase();
  const found = item.found ?? 0;
  if (err) {
    if (["retry","blocked","backoff","429","chromium_not_installed"].some(k => err.includes(k)))
      return ["retry", found];
    return ["error", found];
  }
  return found > 0 ? ["success", found] : ["zero", 0];
}

function scopeVendorSources(scope: Scope, vendor: string): string[] {
  const aliases: Record<string, string[]> = {
    eBay:   ["eBay","eBay UK","eBay (Worldwide)","eBay UK Auctions"],
    Amazon: ["Amazon","Amazon UK"],
    Temu:   ["Temu"],
  };
  const names = aliases[vendor] ?? [vendor];
  if (scope === "cases")        return names.map(n => `Cases:${n}`);
  if (scope === "accessories")  return names.map(n => `Accessories:${n}`);
  if (scope === "upgrade_parts") return names.map(n => `UpgradeParts:${n}`);
  return names;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function KpiBar({ stats, demand, scan }: {
  stats: { total_listings: number; gems_count: number; avg_profit: number } | null;
  demand: { gem_rate_pct?: number } | null;
  scan: ScanStatus | null;
}) {
  const listings   = stats?.total_listings ?? 0;
  const gems       = stats?.gems_count ?? 0;
  const gemRate    = demand?.gem_rate_pct ?? 0;
  const avgProfit  = stats?.avg_profit ?? 0;
  const running    = scan?.running ?? false;
  const done       = scan?.completed ?? 0;
  const total      = scan?.total ?? 0;
  const found      = scan?.total_found ?? 0;

  const cells = [
    { label: "listings",    value: listings.toLocaleString(),         color: "text-slate-200" },
    { label: "gems",        value: gems.toLocaleString(),              color: "text-[#00dc82]" },
    { label: "gem-rate",    value: `${gemRate.toFixed(1)}%`,           color: "text-yellow-400" },
    { label: "avg-profit",  value: `£${Math.round(avgProfit)}`,        color: "text-cyan-400" },
    { label: running ? `${done}/${total} · ${found} found` : "idle",
      value: running ? "RUNNING" : "IDLE",
      color: running ? "text-[#00dc82]" : "text-slate-500" },
  ];

  return (
    <div className="grid grid-cols-5 gap-px bg-[#1e2d45] rounded-lg overflow-hidden border border-[#1e2d45]">
      {cells.map((c, i) => (
        <div key={i} className="bg-[#0a1119] px-3 py-2.5 text-center">
          <div className={`text-lg font-bold font-mono ${c.color}`}>{c.value}</div>
          <div className="text-[10px] text-slate-500 uppercase tracking-widest mt-0.5">{c.label}</div>
        </div>
      ))}
    </div>
  );
}

function SchedulerTable({ jobs }: { jobs: ScheduleJob[] }) {
  const shown = jobs.slice(0, 10);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="border-b border-[#1e2d45]">
            {["Job", "Last", "Next", "Status"].map(h => (
              <th key={h} className="px-2 py-1.5 text-left text-[10px] uppercase tracking-wider text-slate-500">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[#1e2d45]">
          {shown.length === 0 ? (
            <tr><td colSpan={4} className="px-2 py-3 text-slate-600 text-center">—</td></tr>
          ) : shown.map(j => (
            <tr key={j.id} className="hover:bg-white/[0.02]">
              <td className="px-2 py-1.5 text-cyan-400 truncate max-w-[120px]">{j.id}</td>
              <td className="px-2 py-1.5 text-slate-400">{ageStr(j.last_run_at)}</td>
              <td className="px-2 py-1.5 text-slate-400">{nextAgeStr(j.next_run_at)}</td>
              <td className="px-2 py-1.5">
                {j.last_status === "success"
                  ? <span className="text-[#00dc82]">✓ ok</span>
                  : j.last_status === "failed"
                  ? <span className="text-red-400">✗ fail</span>
                  : j.last_status === "running"
                  ? <span className="text-yellow-400">▶ run</span>
                  : <span className="text-slate-600">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface LogLine { ts: string; level: string; msg: string; extra: Record<string, string>; }

function MiniLogs() {
  const [lines, setLines] = useState<LogLine[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    const es = new EventSource(`${API_BASE_URL}/logs/stream`);
    es.onmessage = (e) => {
      if (!isMountedRef.current) return;
      try {
        const entry = JSON.parse(e.data) as LogLine;
        setLines(prev => {
          if (!isMountedRef.current) return prev;
          const next = [...prev, entry];
          return next.length > 80 ? next.slice(-80) : next;
        });
      } catch {}
    };
    return () => {
      isMountedRef.current = false;
      es.close();
    };
  }, []);

  useEffect(() => {
    if (!isMountedRef.current) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  function lineColor(level: string) {
    const l = level.toLowerCase();
    if (l === "error" || l === "critical") return "text-red-400";
    if (l === "warning" || l === "warn")    return "text-yellow-400";
    if (l === "debug")                      return "text-slate-600";
    return "text-emerald-400";
  }

  return (
    <div className="h-52 overflow-y-auto bg-[#050a0f] rounded-lg border border-[#1e2d45] p-2 font-mono text-[10px] leading-relaxed">
      {lines.length === 0
        ? <span className="text-slate-600">Waiting for backend logs…</span>
        : lines.map((l, i) => {
            const extras = Object.entries(l.extra ?? {}).map(([k,v]) => `${k}=${v}`).join(" ");
            return (
              <div key={i} className={lineColor(l.level)}>
                <span className="text-slate-600 mr-1">{l.ts?.slice(11,19)}</span>
                <span className="text-slate-500 mr-1.5">[{l.level}]</span>
                {l.msg}{extras ? <span className="text-slate-500 ml-1">{extras}</span> : null}
              </div>
            );
          })}
      <div ref={bottomRef} />
    </div>
  );
}

function TermsMatrix({ terms, telemetry, enabledSources }: {
  terms: SourceSearchTerm[];
  telemetry: Record<string, SearchTelemetryItem[]>;
  enabledSources: Set<string>;
}) {
  // Build latest telemetry lookup: (source, term_lower) → item
  const latest = new Map<string, SearchTelemetryItem>();
  for (const [src, rows] of Object.entries(telemetry)) {
    for (const r of rows ?? []) {
      const key = `${src}::${(r.term ?? "").toLowerCase()}`;
      if (!latest.has(key)) latest.set(key, r);
    }
  }

  // Group by scope
  const byScope: Record<Scope, SourceSearchTerm[]> = {
    flip_opportunities: [],
    upgrade_parts: [],
    cases: [],
    accessories: [],
  };
  for (const t of terms) {
    const s = t.scope as Scope;
    if (s in byScope && t.enabled) byScope[s].push(t);
  }

  const vendors = Object.keys(VENDOR_GROUPS);

  function renderCell(scope: Scope, term: SourceSearchTerm, vendor: string) {
    const members = VENDOR_GROUPS[vendor];
    const allowed = new Set(term.source_names ?? []);
    let state: CellState = "blank";
    let totalFound = 0;

    for (const v of members) {
      if (allowed.size > 0 && !allowed.has(v)) continue;
      for (const src of scopeVendorSources(scope, v)) {
        const item = latest.get(`${src}::${term.term.toLowerCase()}`);
        const [st, found] = cellState(item);
        totalFound += Math.max(0, found);
        if (st === "error") state = "error";
        else if (st === "retry" && state !== "error") state = "retry";
        else if (st === "success" && !["error","retry"].includes(state)) state = "success";
        else if (st === "zero" && state === "blank") state = "zero";
      }
    }

    if (state === "error")   return <span className="text-red-400">✗</span>;
    if (state === "retry")   return <span className="text-yellow-400">🚦</span>;
    if (state === "success") return <span className="text-[#00dc82]">✓{totalFound}</span>;
    if (state === "zero")    return <span className="text-slate-600">0</span>;
    return <span className="text-slate-800">—</span>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="border-b border-[#1e2d45]">
            <th className="px-2 py-1.5 text-left text-[10px] uppercase tracking-wider text-cyan-500 w-24">Catalogue</th>
            <th className="px-2 py-1.5 text-left text-[10px] uppercase tracking-wider text-yellow-500">Search Term</th>
            {vendors.map(v => (
              <th key={v} className="px-2 py-1.5 text-center text-[10px] uppercase tracking-wider text-slate-500 w-16">{v}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[#0d1320]">
          {SCOPES.map(scope => {
            const rows = [...byScope[scope]].sort((a,b) => a.term.localeCompare(b.term));
            if (rows.length === 0) return null;
            return rows.map((term, idx) => (
              <tr key={term.id} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-2 py-1 text-cyan-400 font-bold whitespace-nowrap">
                  {idx === 0 ? SCOPE_LABELS[scope] : ""}
                </td>
                <td className="px-2 py-1 text-yellow-300 max-w-[220px] truncate">{term.term}</td>
                {vendors.map(v => (
                  <td key={v} className="px-2 py-1 text-center">{renderCell(scope, term, v)}</td>
                ))}
              </tr>
            ));
          })}
        </tbody>
      </table>
      <div className="mt-2 text-[10px] text-slate-600 font-mono px-2">
        <span className="text-[#00dc82]">✓N</span> scraped &nbsp;
        <span className="text-slate-600">0</span> searched/none &nbsp;
        <span className="text-red-400">✗</span> error &nbsp;
        <span className="text-yellow-400">🚦</span> retry &nbsp;
        <span className="text-slate-800">—</span> not run
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SourcesPage() {
  const [stats, setStats]       = useState<{ total_listings: number; gems_count: number; avg_profit: number } | null>(null);
  const [demand, setDemand]     = useState<{ gem_rate_pct?: number } | null>(null);
  const [scan, setScan]         = useState<ScanStatus | null>(null);
  const [jobs, setJobs]         = useState<ScheduleJob[]>([]);
  const [terms, setTerms]       = useState<SourceSearchTerm[]>([]);
  const [telemetry, setTelemetry] = useState<Record<string, SearchTelemetryItem[]>>({});
  const [enabledSources, setEnabledSources] = useState<Set<string>>(new Set());
  const [sources, setSources]   = useState<DataSource[]>([]);
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  // Source management state
  const [showAdd, setShowAdd]   = useState(false);
  const [scrapingId, setScrapingId] = useState<number | null>(null);
  const [newSource, setNewSource] = useState({ name: "", url: "", type: "scrape" as "api" | "scrape" });
  const [saving, setSaving]     = useState(false);

  const fetchAll = useCallback(async (quiet = false) => {
    if (quiet) setRefreshing(true); else setLoading(true);
    try {
      const [s, d, sc, j, t, tel, health, srcs] = await Promise.allSettled([
        api.listings.stats(),
        api.demand.summary(),
        api.swarms.scanStatus(),
        api.schedule.list(),
        api.sourceSearchTerms.list(),
        api.searchTelemetry.bySource(2500),
        api.sources.health(),
        api.sources.list(),
      ]);
      if (s.status === "fulfilled") setStats(s.value as typeof stats);
      if (d.status === "fulfilled") setDemand(d.value as typeof demand);
      if (sc.status === "fulfilled") setScan(sc.value as ScanStatus);
      if (j.status === "fulfilled") setJobs((j.value as ScheduleJob[]) ?? []);
      if (t.status === "fulfilled") {
        const payload = t.value as { items?: SourceSearchTerm[] } | SourceSearchTerm[];
        setTerms(Array.isArray(payload) ? payload : (payload?.items ?? []));
      }
      if (tel.status === "fulfilled") {
        const payload = tel.value as { items?: Record<string, SearchTelemetryItem[]> };
        setTelemetry(payload?.items ?? {});
      }
      if (health.status === "fulfilled") {
        const items = (health.value as { items?: { name: string; enabled: boolean }[] })?.items ?? [];
        setEnabledSources(new Set(items.filter(x => x.enabled).map(x => x.name)));
      }
      if (srcs.status === "fulfilled") setSources((srcs.value as DataSource[]) ?? []);
      setLastRefresh(new Date());
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchAll(false);
    const id = setInterval(() => fetchAll(true), REFRESH_MS);
    return () => clearInterval(id);
  }, [fetchAll]);

  const toggle = async (source: DataSource) => {
    try {
      const updated = await api.sources.update(source.id, { enabled: !source.enabled }) as DataSource;
      setSources(prev => prev.map(s => s.id === source.id ? updated : s));
    } catch {}
  };

  const remove = async (id: number) => {
    try {
      await api.sources.delete(id);
      setSources(prev => prev.filter(s => s.id !== id));
    } catch {}
  };

  const add = async () => {
    if (!newSource.name || !newSource.url) return;
    setSaving(true);
    try {
      const created = await api.sources.create({ name: newSource.name, url: newSource.url, source_type: newSource.type, enabled: true }) as DataSource;
      setSources(prev => [...prev, created]);
      setNewSource({ name: "", url: "", type: "scrape" });
      setShowAdd(false);
    } finally { setSaving(false); }
  };

  const scrape = async (id: number) => {
    setScrapingId(id);
    try {
      await api.sources.trigger(id);
      await fetchAll(true);
    } finally { setScrapingId(null); }
  };

  return (
    <div className="p-4 space-y-4 min-h-screen bg-[#070d16]">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            <Database className="w-5 h-5" /> Source_Control
          </h1>
          <p className="text-[11px] text-slate-500 font-mono mt-0.5">
            {lastRefresh ? `Last refresh: ${lastRefresh.toLocaleTimeString()}` : "Loading…"}
            {refreshing && <span className="ml-2 text-[#00dc82] animate-pulse">● refreshing</span>}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => fetchAll(true)} disabled={refreshing}>
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          </Button>
          <Button variant="primary" size="sm" onClick={() => setShowAdd(!showAdd)}>
            <Plus className="w-3.5 h-3.5" /> Add Source
          </Button>
        </div>
      </div>

      {/* KPI Bar */}
      <KpiBar stats={stats} demand={demand} scan={scan} />

      {/* Main 2-column layout */}
      <div className="grid grid-cols-[320px_1fr] gap-4">

        {/* Left column: Scheduler + Logs */}
        <div className="space-y-4">
          <Card>
            <CardContent className="pt-3 pb-3">
              <p className="text-[10px] uppercase tracking-wider text-cyan-500 font-mono mb-2">Scheduler</p>
              <SchedulerTable jobs={jobs} />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-3 pb-3">
              <p className="text-[10px] uppercase tracking-wider text-[#00dc82] font-mono mb-2">Backend Logs</p>
              <MiniLogs />
            </CardContent>
          </Card>
        </div>

        {/* Right column: Search Terms Matrix */}
        <Card>
          <CardContent className="pt-3 pb-3">
            <p className="text-[10px] uppercase tracking-wider text-[#00dc82] font-mono mb-2">
              Search Terms × Vendor Groups
            </p>
            {loading
              ? <div className="text-xs text-slate-500 py-8 text-center">Loading…</div>
              : <TermsMatrix terms={terms} telemetry={telemetry} enabledSources={enabledSources} />
            }
          </CardContent>
        </Card>
      </div>

      {/* Source management */}
      {showAdd && (
        <Card className="border-[#00dc82]/20">
          <CardContent className="pt-4 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input placeholder="Source name" value={newSource.name}
                onChange={e => setNewSource(p => ({ ...p, name: e.target.value }))}
                className="px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50" />
              <input placeholder="URL" value={newSource.url}
                onChange={e => setNewSource(p => ({ ...p, url: e.target.value }))}
                className="px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50" />
              <select value={newSource.type} onChange={e => setNewSource(p => ({ ...p, type: e.target.value as "api" | "scrape" }))}
                className="px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 outline-none focus:border-[#00dc82]/50">
                <option value="scrape">Web Scraping</option>
                <option value="api">API</option>
              </select>
            </div>
            <div className="flex gap-2">
              <Button variant="primary" size="sm" onClick={add} disabled={saving}>{saving ? "Saving…" : "Save"}</Button>
              <Button variant="ghost" size="sm" onClick={() => setShowAdd(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e2d45]">
                {["Source","Type","Status","Last Scraped","Listings",""].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[10px] font-medium text-slate-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1e2d45]">
              {sources.map(source => (
                <tr key={source.id} className="hover:bg-white/[0.02]">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Globe className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                      <div>
                        <div className="font-medium text-slate-200 text-sm">{source.name}</div>
                        <div className="text-xs text-slate-500">{source.url}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={source.source_type === "api" ? "info" : "muted"}>
                      {source.source_type === "api" ? <Code className="w-3 h-3" /> : <Globe className="w-3 h-3" />}
                      {source.source_type === "api" ? "API" : "Scraping"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggle(source)}
                      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                        source.enabled
                          ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30 hover:bg-red-500/10 hover:text-red-400 hover:border-red-400/30"
                          : "bg-slate-700/30 text-slate-500 border-slate-700/50 hover:bg-[#00dc82]/10 hover:text-[#00dc82] hover:border-[#00dc82]/30"
                      }`}>
                      {source.enabled ? <><CheckCircle className="w-3 h-3" /> Active</> : <><XCircle className="w-3 h-3" /> Disabled</>}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400 font-mono">
                    {source.last_scraped_at ? formatRelativeTime(new Date(source.last_scraped_at)) : "Never"}
                  </td>
                  <td className="px-4 py-3 text-sm font-semibold text-slate-300">
                    {(source.listings_found ?? 0).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Button variant="secondary" size="sm" onClick={() => scrape(source.id)} disabled={scrapingId === source.id}>
                        <RefreshCw className={`w-3 h-3 ${scrapingId === source.id ? "animate-spin" : ""}`} />
                        {scrapingId === source.id ? "Scraping…" : "Scrape"}
                      </Button>
                      <Button variant="danger" size="sm" onClick={() => remove(source.id)}>
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {sources.length === 0 && !loading && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-slate-500">No sources configured</td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

    </div>
  );
}
