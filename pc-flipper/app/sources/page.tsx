"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { RefreshCw, Play, Gem, CheckCircle2, XCircle, Loader2, Clock, AlertTriangle } from "lucide-react";
import { api, SearchTelemetryItem, ScheduleJob, ScanStatus, SourceSearchTerm, API_BASE_URL } from "@/lib/api";

// ─── Constants ────────────────────────────────────────────────────────────────

const REFRESH_MS = 3_000;

const SCOPES = ["flip_opportunities", "upgrade_parts", "cases", "accessories"] as const;
type Scope = typeof SCOPES[number];

const SCOPE_LABELS: Record<Scope, string> = {
  flip_opportunities: "flip_opportuni…",
  upgrade_parts: "components",
  cases: "cases",
  accessories: "accessories",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function ageStr(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const secs = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
    const m = Math.floor(secs / 60), h = Math.floor(m / 60);
    if (h > 0) return `${h}h ${(m % 60).toString().padStart(2, "0")}m`;
    return `${m.toString().padStart(2, "0")}m ${(secs % 60).toString().padStart(2, "0")}s`;
  } catch { return "—"; }
}

type CellState = "success" | "error" | "retry" | "zero" | "blank";

function cellState(item: SearchTelemetryItem | undefined): [CellState, number] {
  if (!item) return ["blank", 0];
  const err = (item.error ?? "").toLowerCase();
  const found = item.found ?? 0;
  if (err) {
    if (["retry","blocked","backoff","429","chromium_not_installed","source_timeout","captcha","login_required"].some(k => err.includes(k)))
      return ["retry", found];
    return ["error", found];
  }
  return found > 0 ? ["success", found] : ["zero", 0];
}

function scopedSrc(scope: Scope, vendor: string): string {
  const prefix: Record<string, string> = {
    cases: "Cases:",
    accessories: "Accessories:",
    upgrade_parts: "UpgradeParts:",
  };
  return (prefix[scope] ?? "") + vendor;
}

const EBAY_CANONICAL = "eBay UK";
const EBAY_ALIASES = ["eBay UK", "eBay", "eBay (Worldwide)", "eBay UK Auctions", "eBay Auctions", "eBay (UK)"];

function normaliseVendor(name: string): string {
  if (name.toLowerCase().startsWith("ebay")) return EBAY_CANONICAL;
  return name;
}

// ─── Compute top vendors by yield (matching Python logic) ────────────────────

function computeTopVendors(telemetry: Record<string, SearchTelemetryItem[]>, maxCols = 5): [string, number][] {
  const totals: Record<string, number> = {};
  for (const [rawSrc, rows] of Object.entries(telemetry)) {
    const src = normaliseVendor(rawSrc.replace(/^(?:Cases|Accessories|UpgradeParts):/, ""));
    const seenTerms = new Set<string>();
    for (const r of rows ?? []) {
      const term = (r.term ?? "").trim().toLowerCase();
      if (!term || seenTerms.has(term)) continue;
      seenTerms.add(term);
      const found = r.found ?? 0;
      if (found > 0) totals[src] = (totals[src] ?? 0) + found;
    }
  }
  return Object.entries(totals).sort((a, b) => b[1] - a[1]).slice(0, maxCols);
}

// ─── Log streaming ────────────────────────────────────────────────────────────

interface LogLine { ts: string; level: string; msg: string; extra: Record<string, string>; }

function useLogStream() {
  const [lines, setLines] = useState<LogLine[]>([]);
  useEffect(() => {
    let mounted = true;
    const es = new EventSource(`${API_BASE_URL}/logs/stream`);
    es.onmessage = (e) => {
      if (!mounted) return;
      try {
        const entry = JSON.parse(e.data) as LogLine;
        setLines(prev => {
          const next = [...prev, entry];
          return next.length > 120 ? next.slice(-120) : next;
        });
      } catch {}
    };
    return () => { mounted = false; es.close(); };
  }, []);
  return lines;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function KpiPanel({ stats, demand, scan }: {
  stats: { total_listings: number; gems_count: number; avg_profit: number } | null;
  demand: { gem_rate_pct?: number } | null;
  scan: ScanStatus | null;
}) {
  const listings  = stats?.total_listings ?? 0;
  const gems      = stats?.gems_count ?? 0;
  const gemRate   = demand?.gem_rate_pct ?? 0;
  const avgProfit = stats?.avg_profit ?? 0;
  const running   = scan?.running ?? false;
  const done      = scan?.completed ?? 0;
  const total     = scan?.total ?? 0;
  const found     = scan?.total_found ?? 0;
  const pct       = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <div className="border border-[#1e3a5f] rounded-sm font-mono">
      {/* Panel title */}
      <div className="border-b border-[#1e3a5f] px-2 py-0.5 text-center text-[11px] text-[#4499ff]">
        FlipFlop Live Stats
      </div>
      <div className="grid grid-cols-5 divide-x divide-[#1e3a5f]">
        {/* Listings */}
        <div className="px-3 py-2 text-center">
          <div className="text-base font-bold text-slate-100">{listings.toLocaleString()}</div>
          <div className="text-[10px] text-slate-500">listings</div>
        </div>
        {/* Gems */}
        <div className="px-3 py-2 text-center">
          <div className="text-base font-bold text-[#00dc82]">{gems.toLocaleString()}</div>
          <div className="text-[10px] text-slate-500">gems</div>
        </div>
        {/* Gem rate */}
        <div className="px-3 py-2 text-center">
          <div className="text-base font-bold text-yellow-400">{gemRate.toFixed(1)}%</div>
          <div className="text-[10px] text-slate-500">gem-rate</div>
        </div>
        {/* Avg profit */}
        <div className="px-3 py-2 text-center">
          <div className="text-base font-bold text-cyan-400">£{Math.round(avgProfit)}</div>
          <div className="text-[10px] text-slate-500">avg-profit</div>
        </div>
        {/* Scan status */}
        <div className="px-3 py-2 text-center flex flex-col items-center justify-center gap-0.5">
          {running ? (
            <>
              <div className="text-[11px] font-bold text-[#00dc82]">scanning&nbsp;&nbsp;{pct}%</div>
              {/* Progress bar */}
              <div className="w-full h-1 bg-[#1e2d45] rounded-full overflow-hidden relative">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${pct}%`, background: "linear-gradient(90deg,#00dc82,#00b8ff)", boxShadow: "0 0 8px rgba(0,220,130,0.6)" }}
                />
              </div>
              <div className="text-[9px] text-slate-500">{done}/{total}&nbsp;search&nbsp;+{found}&nbsp;found</div>
            </>
          ) : total > 0 ? (
            <>
              <div className="text-[11px] font-bold text-[#00dc82]">done</div>
              <div className="w-full h-1 bg-[#1e2d45] rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{ width: "100%", background: "linear-gradient(90deg,#00dc82,#00b8ff)" }} />
              </div>
              <div className="text-[9px] text-slate-500">{done}/{total}&nbsp;+{found}&nbsp;found</div>
            </>
          ) : (
            <div className="text-[11px] text-slate-500">idle</div>
          )}
        </div>
      </div>
    </div>
  );
}

const JOB_ORDER = [
  "flip_opportunities","upgrade_parts","cases","accessories",
  "external_demand","playbook_evolution","autonomous",
  "outcome_capture","model_retraining","retrain_checkpoint_watchdog",
];

function SchedulerPanel({ jobs }: { jobs: ScheduleJob[] }) {
  const sorted = [...jobs].sort((a, b) => {
    const ai = JOB_ORDER.indexOf(a.id), bi = JOB_ORDER.indexOf(b.id);
    return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi);
  });

  return (
    <div className="border border-[#1e3a5f] rounded-sm font-mono flex-1 min-h-0 flex flex-col">
      <div className="border-b border-[#1e3a5f] px-2 py-0.5 text-center text-[11px] text-[#00b8ff] shrink-0">
        Scheduler
      </div>
      <div className="overflow-y-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="border-b border-[#1e3a5f]">
              {["Job","Last","Next","Status"].map(h => (
                <th key={h} className="px-2 py-1 text-left text-[10px] text-slate-500 font-normal">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr><td colSpan={4} className="px-2 py-2 text-slate-600 text-center">—</td></tr>
            ) : sorted.map(j => {
              const status = j.last_status ?? "";
              return (
                <tr key={j.id} className="border-b border-[#0d1320]">
                  <td className="px-2 py-0.5 text-cyan-400">{j.id}</td>
                  <td className="px-2 py-0.5 text-slate-400">{ageStr(j.last_run_at)}</td>
                  <td className="px-2 py-0.5 text-slate-400">{ageStr(j.next_run_at)}</td>
                  <td className="px-2 py-0.5">
                    {status === "success"  ? <span className="text-[#00dc82]">success</span>
                   : status === "failed"   ? <span className="text-red-400">failed</span>
                   : status === "running"  ? <span className="text-yellow-400">running</span>
                   : <span className="text-slate-600">—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LogsPanel({ lines }: { lines: LogLine[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [lines]);

  function lineColor(level: string, msg: string) {
    const l = level.toLowerCase();
    if (l === "error" || l === "critical") return "text-red-400";
    if (l === "warning" || l === "warn")   return "text-yellow-400";
    if (msg.includes("/api/"))             return "text-cyan-400";
    if (l === "debug")                     return "text-slate-600";
    return "text-[#00dc82]";
  }

  return (
    <div className="border border-[#1e3a5f] rounded-sm font-mono flex flex-col" style={{ height: "240px" }}>
      <div className="border-b border-[#1e3a5f] px-2 py-0.5 text-center text-[11px] text-[#00dc82] shrink-0">
        Backend Logs: docker/flipflop-backend
      </div>
      <div className="flex-1 overflow-y-auto p-2 text-[10px] leading-relaxed bg-[#050a0f]">
        {lines.length === 0
          ? <span className="text-slate-600">Waiting for backend logs…</span>
          : lines.map((l, i) => {
              const extras = Object.entries(l.extra ?? {}).map(([k,v]) => `${k}=${v}`).join(" ");
              return (
                <div key={i} className={lineColor(l.level, l.msg)}>
                  <span className="text-slate-600 mr-1">{l.ts?.slice(11,19)}</span>
                  <span className="text-slate-500 mr-1">[{l.level}]</span>
                  {l.msg}
                  {extras ? <span className="text-slate-500 ml-1">{extras}</span> : null}
                </div>
              );
            })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// Spinner frames
const SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏";

function TermsPanel({ terms, telemetry, scheduleJobs, tick }: {
  terms: SourceSearchTerm[];
  telemetry: Record<string, SearchTelemetryItem[]>;
  scheduleJobs: ScheduleJob[];
  tick: number;
}) {
  // Build latest lookup
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

  // Dynamic top vendors — Vinted is always pinned as a column
  const topVendors = computeTopVendors(telemetry, 5);
  const topNames = topVendors.length > 0
    ? topVendors.map(([v]) => v)
    : [EBAY_CANONICAL, "Gumtree", "Amazon", "BargainHardware"];
  // Insert Vinted after the first column if not already present
  const vendorNames = topNames.includes("Vinted")
    ? topNames
    : [topNames[0], "Vinted", ...topNames.slice(1)];
  const vendorTotals = Object.fromEntries(topVendors);

  // Scope → job status map
  const scopeStatus: Record<string, string> = {};
  for (const j of scheduleJobs) {
    if ((SCOPES as readonly string[]).includes(j.id)) scopeStatus[j.id] = j.last_status ?? "";
  }

  function scopeIndicator(scope: Scope): string {
    const st = scopeStatus[scope] ?? "";
    if (st === "running") return SPINNER[tick % SPINNER.length];
    if (st === "success") return "✓";
    if (st === "failed" || st === "error") return "✗";
    return "";
  }

  function renderCell(scope: Scope, term: SourceSearchTerm, vendor: string): React.ReactNode {
    const termLower = term.term.toLowerCase();
    const key = `${scopedSrc(scope, vendor)}::${termLower}`;
    let [st, found] = cellState(latest.get(key));

    // Try all eBay aliases
    if (st === "blank" && vendor === EBAY_CANONICAL) {
      let totalFound = 0, bestSt: CellState = "blank";
      for (const alt of EBAY_ALIASES) {
        const altKey = `${scopedSrc(scope, alt)}::${termLower}`;
        const [altSt, altFound] = cellState(latest.get(altKey));
        totalFound += Math.max(0, altFound);
        if (altSt === "error") bestSt = "error";
        else if (altSt === "retry" && bestSt !== "error") bestSt = "retry";
        else if ((altSt === "success" || altSt === "zero") && bestSt === "blank") bestSt = altSt;
      }
      if (bestSt !== "blank") { st = bestSt; found = totalFound; }
    }

    if (st === "error")   return <span className="text-red-400">✗</span>;
    if (st === "retry")   return <span className="text-yellow-400">~</span>;
    if (found > 0)        return <span className="text-[#00dc82]">✓{found}</span>;
    if (st === "zero")    return <span className="text-slate-600">0</span>;
    return null;
  }

  return (
    <div className="border border-[#1e3a5f] rounded-sm font-mono flex flex-col h-full">
      <div className="border-b border-[#1e3a5f] px-2 py-0.5 text-center text-[11px] text-[#4499ff] shrink-0">
        Search Terms × Vendors&nbsp;&nbsp;<span className="text-slate-600">(sorted by yield ↓)</span>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead className="sticky top-0 bg-[#070d16] z-10">
            <tr className="border-b border-[#1e3a5f]">
              <th className="px-2 py-1 text-left text-cyan-500 w-[120px]">Catalogue</th>
              <th className="px-2 py-1 text-left text-yellow-500 w-[200px]">Search Term</th>
              {vendorNames.map(v => {
                const label = v.length > 10 ? v.slice(0, 9) + "…" : v;
                const total = vendorTotals[v] ?? 0;
                return (
                  <th key={v} className="px-2 py-1 text-center text-slate-500 w-[80px]">
                    {label}
                    {total > 0 && <div className="text-[9px] text-slate-600">Σ{total}</div>}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {SCOPES.map(scope => {
              // Sort: terms with any scraped data first (by total found desc), then alphabetically
              const scopePrefix: Record<Scope, string | null> = {
                flip_opportunities: null,        // no prefix — raw source names
                upgrade_parts: "UpgradeParts:",
                cases: "Cases:",
                accessories: "Accessories:",
              };
              const pfx = scopePrefix[scope];
              function termTotalFound(t: SourceSearchTerm): number {
                const tl = t.term.toLowerCase();
                let total = 0;
                for (const [src, rows] of Object.entries(telemetry)) {
                  // for flip_opportunities match un-prefixed sources; for others match the prefix
                  const prefixMatch = pfx === null ? !src.includes(":") : src.startsWith(pfx);
                  if (!prefixMatch) continue;
                  for (const r of rows ?? []) {
                    if ((r.term ?? "").toLowerCase() === tl) total += (r.found ?? 0);
                  }
                }
                return total;
              }
              const rows = [...byScope[scope]]
                .sort((a, b) => {
                  const af = termTotalFound(a), bf = termTotalFound(b);
                  if (bf !== af) return bf - af;  // data-first
                  return a.term.localeCompare(b.term);
                })
                .slice(0, 14);
              if (rows.length === 0) return null;
              const ind = scopeIndicator(scope);
              return rows.map((term, idx) => (
                <tr key={term.id} className="border-b border-[#0d1320] hover:bg-white/[0.02]">
                  <td className="px-2 py-0.5 text-cyan-400 whitespace-nowrap">
                    {idx === 0 ? (
                      <span>
                        {SCOPE_LABELS[scope]}
                        {ind && (
                          <span className={ind === "✓" ? "text-[#00dc82]" : ind === "✗" ? "text-red-400" : "text-yellow-400"}>
                            {"\n"}{ind}
                          </span>
                        )}
                      </span>
                    ) : ""}
                  </td>
                  <td className="px-2 py-0.5 text-yellow-300 max-w-[200px] truncate">{term.term}</td>
                  {vendorNames.map(v => (
                    <td key={v} className="px-2 py-0.5 text-center">{renderCell(scope, term, v)}</td>
                  ))}
                </tr>
              ));
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="border-t border-[#1e3a5f] px-2 py-1 text-[9px] text-slate-600 flex gap-3 flex-wrap shrink-0">
        <span><span className="text-[#00dc82]">✓n</span>=listings found</span>
        <span><span className="text-slate-600">0</span>=ran/none</span>
        <span><span className="text-red-400">✗</span>=error</span>
        <span><span className="text-yellow-400">~</span>=retry/blocked</span>
        <span>blank=not run</span>
        <span><span className="text-slate-600">Σ</span>=total scraped</span>
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
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [tick, setTick]         = useState(0);

  const logLines = useLogStream();

  const fetchAll = useCallback(async (quiet = false) => {
    if (quiet) setRefreshing(true); else setLoading(true);
    try {
      const [s, d, sc, j, t, tel] = await Promise.allSettled([
        api.listings.stats(),
        api.demand.summary(),
        api.swarms.scanStatus(),
        api.schedule.list(),
        api.sourceSearchTerms.list(),
        api.searchTelemetry.bySource(50000),
      ]);
      if (s.status === "fulfilled")  setStats(s.value as typeof stats);
      if (d.status === "fulfilled")  setDemand(d.value as typeof demand);
      if (sc.status === "fulfilled") setScan(sc.value as ScanStatus);
      if (j.status === "fulfilled")  setJobs((j.value as ScheduleJob[]) ?? []);
      if (t.status === "fulfilled") {
        const payload = t.value as { items?: SourceSearchTerm[] } | SourceSearchTerm[];
        setTerms(Array.isArray(payload) ? payload : (payload?.items ?? []));
      }
      if (tel.status === "fulfilled") {
        const payload = tel.value as { items?: Record<string, SearchTelemetryItem[]> };
        setTelemetry(payload?.items ?? {});
      }
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

  // Spinner tick
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 100);
    return () => clearInterval(id);
  }, []);

  const triggerScan = async () => {
    setTriggering(true);
    try { await api.swarms.trigger("flip_opportunities"); } catch {}
    finally { setTriggering(false); await fetchAll(true); }
  };

  return (
    <div className="h-screen flex flex-col bg-[#070d16] font-mono overflow-hidden">

      {/* Top bar */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[#1e3a5f] shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-[12px] text-[#4499ff] font-bold tracking-wider">FLIPFLOP&nbsp;·&nbsp;SOURCING&nbsp;CONSOLE</span>
          {refreshing && <span className="text-[10px] text-[#00dc82] animate-pulse">● live</span>}
          {lastRefresh && <span className="text-[10px] text-slate-600">{lastRefresh.toLocaleTimeString()}</span>}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchAll(true)}
            disabled={refreshing}
            className="flex items-center gap-1 px-2 py-0.5 text-[10px] border border-[#1e3a5f] text-slate-400 hover:text-slate-200 hover:border-slate-500 rounded-sm transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
            refresh
          </button>
          <button
            onClick={triggerScan}
            disabled={triggering || scan?.running}
            className="flex items-center gap-1 px-2 py-0.5 text-[10px] border border-[#00dc82]/40 text-[#00dc82] hover:bg-[#00dc82]/10 rounded-sm transition-colors disabled:opacity-40"
          >
            <Play className="w-3 h-3" />
            {scan?.running ? "running…" : triggering ? "starting…" : "run scan"}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-[#00dc82] text-[11px]">
          Loading…
        </div>
      ) : (
        /* Main layout: left col + right col */
        <div className="flex-1 flex gap-0 min-h-0 overflow-hidden">

          {/* LEFT column */}
          <div className="flex flex-col gap-2 p-2 w-[380px] shrink-0 min-h-0">
            {/* KPI bar */}
            <KpiPanel stats={stats} demand={demand} scan={scan} />

            {/* Scheduler */}
            <SchedulerPanel jobs={jobs} />

            {/* Backend logs */}
            <LogsPanel lines={logLines} />
          </div>

          {/* Divider */}
          <div className="w-px bg-[#1e3a5f] shrink-0" />

          {/* RIGHT column: search terms matrix */}
          <div className="flex-1 p-2 min-h-0 flex flex-col">
            <TermsPanel terms={terms} telemetry={telemetry} scheduleJobs={jobs} tick={tick} />
          </div>

        </div>
      )}
    </div>
  );
}
