"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  CalendarClock, Play, Pause, RefreshCw, CheckCircle2,
  XCircle, Clock, AlertCircle, Zap, Database, Brain,
  TrendingUp, Tag, ChevronDown, ChevronUp,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";

/* ── Types ──────────────────────────────────────────────────────────────── */

type RunStatus = "success" | "running" | "failed" | "skipped";

interface JobRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: RunStatus;
  message: string;
  duration_ms: number | null;
}

interface ScheduledJob {
  id: string;
  name: string;
  description: string;
  cron: string;
  cron_label: string;
  enabled: boolean;
  last_run_at: string | null;
  last_status: RunStatus | null;
  next_run_at: string | null;
  category: "scraping" | "analysis" | "selling" | "maintenance";
  runs?: JobRun[];
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */

const CATEGORY_ICONS: Record<ScheduledJob["category"], React.ElementType> = {
  scraping:    Database,
  analysis:    Brain,
  selling:     Tag,
  maintenance: TrendingUp,
};

const CATEGORY_COLORS: Record<ScheduledJob["category"], string> = {
  scraping:    "text-purple-400",
  analysis:    "text-cyan-400",
  selling:     "text-yellow-400",
  maintenance: "text-emerald-400",
};

function StatusDot({ status }: { status: RunStatus | null }) {
  if (!status) return <span className="w-1.5 h-1.5 rounded-full bg-slate-700 inline-block" />;
  const cls = {
    success: "bg-emerald-500",
    running: "bg-blue-400 animate-pulse",
    failed:  "bg-red-500",
    skipped: "bg-slate-600",
  }[status];
  return <span className={`w-1.5 h-1.5 rounded-full inline-block ${cls}`} />;
}

function StatusBadge({ status }: { status: RunStatus | null }) {
  if (!status) return <Badge variant="muted">Never run</Badge>;
  const map: Record<RunStatus, { variant: "success" | "danger" | "info" | "muted"; label: string }> = {
    success: { variant: "success", label: "Success" },
    running: { variant: "info",    label: "Running" },
    failed:  { variant: "danger",  label: "Failed" },
    skipped: { variant: "muted",   label: "Skipped" },
  };
  const { variant, label } = map[status];
  return <Badge variant={variant}>{label}</Badge>;
}

function fmtDuration(ms: number | null) {
  if (!ms) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

/* ── Default jobs (used when backend returns nothing) ───────────────────── */

const DEFAULT_JOBS: ScheduledJob[] = [
  {
    id: "scrape-ebay",
    name: "eBay Scraper",
    description: "Scan eBay for new listings matching all active search configs",
    cron: "*/15 * * * *",
    cron_label: "Every 15 min",
    enabled: true,
    last_run_at: null,
    last_status: null,
    next_run_at: null,
    category: "scraping",
  },
  {
    id: "scrape-gumtree",
    name: "Gumtree Scraper",
    description: "Scrape Gumtree UK for PC & laptop listings",
    cron: "*/30 * * * *",
    cron_label: "Every 30 min",
    enabled: true,
    last_run_at: null,
    last_status: null,
    next_run_at: null,
    category: "scraping",
  },
  {
    id: "scrape-fb",
    name: "Facebook Marketplace",
    description: "Check Facebook Marketplace listings near your postcode",
    cron: "0 * * * *",
    cron_label: "Hourly",
    enabled: false,
    last_run_at: null,
    last_status: null,
    next_run_at: null,
    category: "scraping",
  },
  {
    id: "classify-new",
    name: "Classifier Sweep",
    description: "Score & classify all unscored listings from the last 2 hours",
    cron: "*/20 * * * *",
    cron_label: "Every 20 min",
    enabled: true,
    last_run_at: null,
    last_status: null,
    next_run_at: null,
    category: "analysis",
  },
  {
    id: "price-sync",
    name: "Price Reference Sync",
    description: "Refresh resale price data from eBay sold listings",
    cron: "0 */6 * * *",
    cron_label: "Every 6 hrs",
    enabled: true,
    last_run_at: null,
    last_status: null,
    next_run_at: null,
    category: "analysis",
  },
  {
    id: "gem-alert",
    name: "Gem Alerts",
    description: "Check for new top-scored gems and push notifications",
    cron: "*/10 * * * *",
    cron_label: "Every 10 min",
    enabled: true,
    last_run_at: null,
    last_status: null,
    next_run_at: null,
    category: "analysis",
  },
  {
    id: "listing-refresh",
    name: "Active Listing Refresh",
    description: "Re-sync sold / ended status on active eBay listings",
    cron: "0 */2 * * *",
    cron_label: "Every 2 hrs",
    enabled: true,
    last_run_at: null,
    last_status: null,
    next_run_at: null,
    category: "selling",
  },
  {
    id: "db-prune",
    name: "DB Prune",
    description: "Remove listings older than 30 days and compress logs",
    cron: "0 3 * * *",
    cron_label: "Daily 03:00",
    enabled: true,
    last_run_at: null,
    last_status: null,
    next_run_at: null,
    category: "maintenance",
  },
];

/* ── Main component ──────────────────────────────────────────────────────── */

export default function SchedulePage() {
  const [jobs, setJobs] = useState<ScheduledJob[]>(DEFAULT_JOBS);
  const [loading, setLoading] = useState(true);
  const [runningIds, setRunningIds] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<string | null>(null);
  const [runHistory, setRunHistory] = useState<Record<string, JobRun[]>>({});

  /* fetch jobs from backend (non-fatal) */
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await (api as unknown as {
        schedule?: { list: () => Promise<ScheduledJob[]> }
      }).schedule?.list?.();
      if (data && Array.isArray(data) && data.length > 0) setJobs(data);
    } catch { /* use defaults */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  /* toggle enabled */
  const toggleJob = async (id: string) => {
    setJobs(prev => prev.map(j => j.id === id ? { ...j, enabled: !j.enabled } : j));
    try {
      await (api as unknown as {
        schedule?: { toggle: (id: string) => Promise<void> }
      }).schedule?.toggle?.(id);
    } catch { /* optimistic — ignore */ }
  };

  /* run now */
  const runNow = async (id: string) => {
    setRunningIds(prev => new Set(prev).add(id));
    setJobs(prev => prev.map(j => j.id === id ? { ...j, last_status: "running" } : j));
    try {
      await (api as unknown as {
        schedule?: { run: (id: string) => Promise<{ status: RunStatus; duration_ms: number }> }
      }).schedule?.run?.(id);
      setJobs(prev => prev.map(j =>
        j.id === id
          ? { ...j, last_status: "success", last_run_at: new Date().toISOString() }
          : j
      ));
    } catch {
      setJobs(prev => prev.map(j =>
        j.id === id ? { ...j, last_status: "failed" } : j
      ));
    } finally {
      setRunningIds(prev => { const s = new Set(prev); s.delete(id); return s; });
    }
  };

  /* expand / fetch run history */
  const toggleExpand = async (id: string) => {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    if (!runHistory[id]) {
      try {
        const runs = await (api as unknown as {
          schedule?: { runs: (id: string) => Promise<JobRun[]> }
        }).schedule?.runs?.(id) ?? [];
        setRunHistory(prev => ({ ...prev, [id]: runs }));
      } catch {
        setRunHistory(prev => ({ ...prev, [id]: [] }));
      }
    }
  };

  /* stats */
  const active = jobs.filter(j => j.enabled).length;
  const lastFailed = jobs.find(j => j.last_status === "failed");

  /* group by category */
  const grouped = (["scraping", "analysis", "selling", "maintenance"] as const).map(cat => ({
    cat,
    items: jobs.filter(j => j.category === cat),
  })).filter(g => g.items.length > 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-500 text-sm gap-2">
        <RefreshCw className="w-4 h-4 animate-spin" /> Loading schedule…
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <CalendarClock className="w-5 h-5 text-[#00dc82]" /> Job Scheduler
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {active} of {jobs.length} jobs active
            {lastFailed && <span className="text-red-400 ml-2">· {lastFailed.name} last failed</span>}
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={load}>
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </Button>
      </div>

      {/* Stat pills */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Active jobs",   value: active,                            color: "text-emerald-400" },
          { label: "Paused jobs",   value: jobs.length - active,              color: "text-slate-500"   },
          { label: "Last failures", value: jobs.filter(j => j.last_status === "failed").length,  color: "text-red-400" },
          { label: "Total jobs",    value: jobs.length,                       color: "text-slate-300"   },
        ].map(stat => (
          <Card key={stat.label}>
            <CardContent className="pt-3 pb-3">
              <div className={`text-2xl font-black ${stat.color}`}>{stat.value}</div>
              <div className="text-[11px] text-slate-600 mt-0.5">{stat.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Job groups */}
      {grouped.map(({ cat, items }) => {
        const Icon = CATEGORY_ICONS[cat];
        const color = CATEGORY_COLORS[cat];
        return (
          <Card key={cat}>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 capitalize">
                <Icon className={`w-3.5 h-3.5 ${color}`} />
                {cat}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#1e2d45]">
                    {["Job", "Schedule", "Last Run", "Status", ""].map(h => (
                      <th key={h} className="px-5 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e2d45]">
                  {items.map(job => {
                    const isRunning = runningIds.has(job.id);
                    const isExpanded = expanded === job.id;
                    const history = runHistory[job.id] ?? [];
                    return (
                      <React.Fragment key={job.id}>
                        <tr
                          className={`hover:bg-white/[0.02] transition-colors cursor-pointer ${!job.enabled ? "opacity-50" : ""}`}
                          onClick={() => toggleExpand(job.id)}
                        >
                          {/* Job name */}
                          <td className="px-5 py-3.5">
                            <div className="flex items-center gap-2">
                              <StatusDot status={isRunning ? "running" : job.last_status} />
                              <div>
                                <div className="font-medium text-slate-200">{job.name}</div>
                                <div className="text-xs text-slate-600 mt-0.5">{job.description}</div>
                              </div>
                            </div>
                          </td>
                          {/* Cron schedule */}
                          <td className="px-5 py-3.5">
                            <div className="flex items-center gap-1.5">
                              <Clock className="w-3 h-3 text-slate-600" />
                              <span className="text-xs text-slate-400">{job.cron_label}</span>
                            </div>
                            <div className="font-mono text-[10px] text-slate-700 mt-0.5">{job.cron}</div>
                          </td>
                          {/* Last run */}
                          <td className="px-5 py-3.5">
                            <span className="text-xs text-slate-500">
                              {job.last_run_at ? formatRelativeTime(new Date(job.last_run_at)) : "Never"}
                            </span>
                          </td>
                          {/* Status */}
                          <td className="px-5 py-3.5">
                            <StatusBadge status={isRunning ? "running" : job.last_status} />
                          </td>
                          {/* Actions */}
                          <td className="px-5 py-3.5">
                            <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => runNow(job.id)}
                                disabled={isRunning}
                              >
                                {isRunning
                                  ? <RefreshCw className="w-3 h-3 animate-spin" />
                                  : <Zap className="w-3 h-3" />}
                                {isRunning ? "Running…" : "Run now"}
                              </Button>
                              <button
                                onClick={() => toggleJob(job.id)}
                                title={job.enabled ? "Pause job" : "Enable job"}
                                className={`p-1.5 rounded border transition-colors ${
                                  job.enabled
                                    ? "border-[#1e2d45] text-slate-500 hover:text-yellow-400 hover:border-yellow-400/30"
                                    : "border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                                }`}
                              >
                                {job.enabled ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                              </button>
                              {isExpanded
                                ? <ChevronUp className="w-3.5 h-3.5 text-slate-600" />
                                : <ChevronDown className="w-3.5 h-3.5 text-slate-600" />}
                            </div>
                          </td>
                        </tr>

                        {/* Run history drawer */}
                        {isExpanded && (
                          <tr>
                            <td colSpan={5} className="px-5 pb-3 pt-1 bg-black/20">
                              <div className="text-[11px] text-slate-600 font-medium uppercase tracking-wider mb-2">
                                Recent runs
                              </div>
                              {history.length === 0 ? (
                                <div className="text-xs text-slate-700 py-2">No run history available yet.</div>
                              ) : (
                                <div className="space-y-1">
                                  {history.slice(0, 8).map(run => (
                                    <div key={run.id}
                                      className="flex items-center gap-3 text-xs py-1.5 px-3 rounded-lg bg-[#060a10] border border-[#1e2d45]">
                                      {run.status === "success" && <CheckCircle2 className="w-3 h-3 text-emerald-500 shrink-0" />}
                                      {run.status === "failed"  && <XCircle      className="w-3 h-3 text-red-500    shrink-0" />}
                                      {run.status === "running" && <RefreshCw    className="w-3 h-3 text-blue-400   shrink-0 animate-spin" />}
                                      {run.status === "skipped" && <AlertCircle  className="w-3 h-3 text-slate-600  shrink-0" />}
                                      <span className="text-slate-400 font-mono w-20 shrink-0">
                                        {new Date(run.started_at).toLocaleTimeString("en-GB", { hour12: false })}
                                      </span>
                                      <span className="text-slate-400 w-14 shrink-0">{fmtDuration(run.duration_ms)}</span>
                                      <span className="text-slate-600 truncate">{run.message}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
