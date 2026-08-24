"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Clock3,
  History,
  ListChecks,
  Loader2,
  RefreshCw,
  TableProperties,
  XCircle,
} from "lucide-react";

interface ScanRunHistoryRecord {
  id: number;
  searchTerm: string;
  totalListingsFound: number;
  vendors: string[];
  runBy: string;
  durationSeconds: number;
  occurredAt: string;
}

interface TermResult {
  listingsProcessed: number;
  durationSeconds: number;
  vendors: Set<string>;
  completed: boolean;
}

interface ScanSession {
  id: string;
  startedAt: number;
  endedAt: number;
  durationSeconds: number;
  runBy: string;
  terms: Map<string, TermResult>;
}

type PageTab = "summary" | "terms";
type MatrixMetric = "listings" | "duration" | "completed" | "vendors";

const SESSION_GAP_MS = 10 * 60 * 1000;

const METRICS: Array<{ value: MatrixMetric; label: string }> = [
  { value: "listings", label: "Listings processed" },
  { value: "duration", label: "Duration" },
  { value: "completed", label: "Completed?" },
  { value: "vendors", label: "Number of vendors" },
];

function buildSessions(records: ScanRunHistoryRecord[]): ScanSession[] {
  const ordered = records
    .map((record) => ({ ...record, timestamp: new Date(record.occurredAt).getTime() }))
    .filter((record) => Number.isFinite(record.timestamp))
    .sort((a, b) => a.timestamp - b.timestamp);
  const groups: typeof ordered[] = [];

  for (const record of ordered) {
    const current = groups.at(-1);
    const previous = current?.at(-1);
    if (!current || !previous || record.timestamp - previous.timestamp > SESSION_GAP_MS) {
      groups.push([record]);
    } else {
      current.push(record);
    }
  }

  return groups
    .map((group) => {
      const terms = new Map<string, TermResult>();
      let startedAt = Number.POSITIVE_INFINITY;
      let endedAt = 0;

      for (const record of group) {
        startedAt = Math.min(startedAt, record.timestamp - Math.max(0, record.durationSeconds) * 1000);
        endedAt = Math.max(endedAt, record.timestamp);
        const existing = terms.get(record.searchTerm) ?? {
          listingsProcessed: 0,
          durationSeconds: 0,
          vendors: new Set<string>(),
          completed: true,
        };
        existing.listingsProcessed += record.totalListingsFound;
        // Vendor searches run concurrently, so the slowest vendor is the
        // best representation of the term's elapsed duration.
        existing.durationSeconds = Math.max(existing.durationSeconds, record.durationSeconds);
        for (const vendor of record.vendors) existing.vendors.add(vendor);
        terms.set(record.searchTerm, existing);
      }

      const runTypes = [...new Set(group.map((record) => record.runBy))];
      return {
        id: `${startedAt}-${group[0].id}`,
        startedAt,
        endedAt,
        durationSeconds: Math.max(0, (endedAt - startedAt) / 1000),
        runBy: runTypes.length === 1 ? runTypes[0] : "Mixed",
        terms,
      };
    })
    .sort((a, b) => b.startedAt - a.startedAt);
}

function formatDateTime(timestamp: number) {
  return new Date(timestamp).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(seconds: number) {
  if (!Number.isFinite(seconds)) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.round(seconds % 60);
  return `${minutes}m ${String(remaining).padStart(2, "0")}s`;
}

function formatRunBy(value: string) {
  if (value.toLowerCase() === "automatic") return "Auto-trigger";
  return value;
}

function MatrixValue({ result, metric }: { result?: TermResult; metric: MatrixMetric }) {
  if (!result) {
    return metric === "completed" ? (
      <span className="inline-flex items-center gap-1 text-red-300"><XCircle className="h-3.5 w-3.5" /> No</span>
    ) : (
      <span className="text-slate-600">—</span>
    );
  }
  if (metric === "listings") return <>{result.listingsProcessed.toLocaleString()}</>;
  if (metric === "duration") return <>{formatDuration(result.durationSeconds)}</>;
  if (metric === "vendors") return <>{result.vendors.size}</>;
  return result.completed ? (
    <span className="inline-flex items-center gap-1 text-emerald-300"><CheckCircle2 className="h-3.5 w-3.5" /> Yes</span>
  ) : (
    <span className="inline-flex items-center gap-1 text-red-300"><XCircle className="h-3.5 w-3.5" /> No</span>
  );
}

async function fetchRunHistory(): Promise<ScanRunHistoryRecord[]> {
  const response = await fetch("/api/gem-radar/scan-run-history?limit=500", {
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) throw new Error(`Run history request failed (${response.status})`);
  return response.json();
}

export default function RunHistoryPage() {
  const [records, setRecords] = useState<ScanRunHistoryRecord[]>([]);
  const [activeTab, setActiveTab] = useState<PageTab>("summary");
  const [metric, setMetric] = useState<MatrixMetric>("listings");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      setRecords(await fetchRunHistory());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Run history could not be loaded");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    fetchRunHistory()
      .then((history) => {
        if (!cancelled) setRecords(history);
      })
      .catch((loadError: unknown) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Run history could not be loaded");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const sessions = useMemo(() => buildSessions(records), [records]);
  const searchTerms = useMemo(
    () => [...new Set(records.map((record) => record.searchTerm))].sort((a, b) => a.localeCompare(b)),
    [records],
  );
  const expectedTermCount = sessions.reduce((largest, session) => Math.max(largest, session.terms.size), 0);

  return (
    <main className="relative flex h-full min-h-0 flex-col overflow-hidden bg-slate-950 p-4 text-slate-100 sm:p-6">
      <div className="pointer-events-none absolute -left-24 -top-32 h-[420px] w-[420px] rounded-full bg-blue-600/20 blur-[110px]" />
      <div className="pointer-events-none absolute -right-32 top-40 h-[460px] w-[460px] rounded-full bg-cyan-500/10 blur-[120px]" />

      <header className="relative mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/sourcing"
            aria-label="Back to Sourcing dashboard"
            title="Back to Sourcing dashboard"
            className="grid h-11 w-11 shrink-0 cursor-pointer place-items-center rounded-xl border border-white/10 bg-white/[0.06] text-slate-300 transition-colors duration-200 hover:border-blue-400/40 hover:bg-blue-500/15 hover:text-blue-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <History className="h-5 w-5 text-blue-400" />
              <h1 className="truncate text-xl font-bold tracking-tight sm:text-2xl">Run History</h1>
            </div>
            <p className="mt-0.5 text-xs text-slate-400 sm:text-sm">Completed sourcing scans and search-term performance</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void loadHistory()}
          disabled={loading}
          className="inline-flex h-11 cursor-pointer items-center gap-2 rounded-xl border border-white/10 bg-white/[0.06] px-4 text-sm font-medium text-slate-200 transition-colors duration-200 hover:border-blue-400/40 hover:bg-blue-500/15 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </header>

      <section className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] shadow-[0_12px_40px_rgba(0,0,0,0.35)] backdrop-blur-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 p-3">
          <div role="tablist" aria-label="Run history views" className="flex rounded-xl bg-slate-900/70 p-1">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "summary"}
              onClick={() => setActiveTab("summary")}
              className={`inline-flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${activeTab === "summary" ? "bg-blue-500 text-white" : "text-slate-400 hover:bg-white/[0.06] hover:text-slate-200"}`}
            >
              <ListChecks className="h-4 w-4" /> Summary
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "terms"}
              onClick={() => setActiveTab("terms")}
              className={`inline-flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${activeTab === "terms" ? "bg-blue-500 text-white" : "text-slate-400 hover:bg-white/[0.06] hover:text-slate-200"}`}
            >
              <TableProperties className="h-4 w-4" /> By Search Term
            </button>
          </div>

          {activeTab === "terms" && (
            <fieldset className="flex flex-wrap gap-1.5" aria-label="Matrix value">
              <legend className="sr-only">Choose the value displayed in each search-term cell</legend>
              {METRICS.map((option) => (
                <label
                  key={option.value}
                  className={`cursor-pointer rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors duration-200 ${metric === option.value ? "border-blue-400/60 bg-blue-500/20 text-blue-200" : "border-white/10 bg-slate-900/50 text-slate-400 hover:border-white/20 hover:text-slate-200"}`}
                >
                  <input
                    type="radio"
                    name="matrixMetric"
                    value={option.value}
                    checked={metric === option.value}
                    onChange={() => setMetric(option.value)}
                    className="mr-1.5 accent-blue-500"
                  />
                  {option.label}
                </label>
              ))}
            </fieldset>
          )}
          {activeTab === "summary" && expectedTermCount > 0 && (
            <p className="text-xs text-slate-500">
              Complete = all {expectedTermCount} terms recorded in the fullest scan
            </p>
          )}
        </div>

        {loading ? (
          <div className="grid flex-1 place-items-center text-sm text-slate-400"><span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Loading run history…</span></div>
        ) : error ? (
          <div className="m-4 rounded-xl border border-red-500/30 bg-red-950/30 p-4 text-sm text-red-200">{error}</div>
        ) : sessions.length === 0 ? (
          <div className="grid flex-1 place-items-center p-6 text-center text-sm text-slate-400">No recorded sourcing runs yet.</div>
        ) : activeTab === "summary" ? (
          <div role="tabpanel" className="min-h-0 flex-1 overflow-auto">
            <table className="w-full min-w-[820px] border-collapse text-left text-sm">
              <thead className="sticky top-0 z-10 bg-slate-900/95 text-xs uppercase tracking-wide text-slate-400 backdrop-blur">
                <tr>
                  <th className="px-4 py-3 font-semibold">Date/time</th>
                  <th className="px-4 py-3 font-semibold">Search terms completed</th>
                  <th className="px-4 py-3 font-semibold">Completed?</th>
                  <th className="px-4 py-3 font-semibold">Duration</th>
                  <th className="px-4 py-3 font-semibold">Run by</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.06]">
                {sessions.map((session) => {
                  const complete = session.terms.size >= expectedTermCount;
                  return (
                    <tr key={session.id} className="transition-colors duration-150 hover:bg-white/[0.04]">
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-200">{formatDateTime(session.startedAt)}</td>
                      <td className="px-4 py-3 font-semibold text-slate-100">{session.terms.size} <span className="font-normal text-slate-500">/ {expectedTermCount}</span></td>
                      <td className="px-4 py-3">
                        {complete ? <span className="inline-flex items-center gap-1.5 text-emerald-300"><CheckCircle2 className="h-4 w-4" /> Yes</span> : <span className="inline-flex items-center gap-1.5 text-amber-300"><XCircle className="h-4 w-4" /> No</span>}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3"><span className="inline-flex items-center gap-1.5 text-slate-300"><Clock3 className="h-4 w-4 text-slate-500" /> {formatDuration(session.durationSeconds)}</span></td>
                      <td className="px-4 py-3"><span className="rounded-md border border-white/10 bg-white/[0.05] px-2 py-1 text-xs font-medium text-slate-300">{formatRunBy(session.runBy)}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div role="tabpanel" className="min-h-0 flex-1 overflow-auto">
            <table className="min-w-max border-separate border-spacing-0 text-left text-xs">
              <thead className="sticky top-0 z-20 bg-slate-900/95 text-slate-400 backdrop-blur">
                <tr>
                  <th className="sticky left-0 z-30 min-w-[190px] border-b border-r border-white/10 bg-slate-900 px-4 py-3 font-semibold uppercase tracking-wide">Date/time</th>
                  {searchTerms.map((term) => (
                    <th key={term} title={term} className="max-w-[220px] min-w-[170px] border-b border-r border-white/10 px-3 py-3 align-bottom font-semibold">
                      <span className="block line-clamp-3 leading-4">{term}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={session.id} className="group">
                    <th className="sticky left-0 z-10 whitespace-nowrap border-b border-r border-white/[0.06] bg-slate-950 px-4 py-3 font-mono font-normal text-slate-300 group-hover:bg-slate-900">{formatDateTime(session.startedAt)}</th>
                    {searchTerms.map((term) => (
                      <td key={term} className="border-b border-r border-white/[0.06] px-3 py-3 text-center font-mono text-slate-200 transition-colors duration-150 group-hover:bg-white/[0.035]">
                        <MatrixValue result={session.terms.get(term)} metric={metric} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
