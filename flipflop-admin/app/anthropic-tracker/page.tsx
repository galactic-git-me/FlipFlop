"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, CalendarDays, Coins, RefreshCw, Sparkles, Zap } from "lucide-react";

type Bucket = Record<string, unknown>;
type Report = { messages: Bucket[]; web_search: Bucket[]; start: string; end: string; fetched_at: string };
type UsageRow = { date: string; model: string; requests: number; input: number; output: number; cacheRead: number; cacheWrite: number; cost: number };
const dateInput = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const asNumber = (value: unknown) => typeof value === "number" ? value : Number(value ?? 0) || 0;
const fmt = (value: number) => new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 }).format(value);
const gbp = (value: number) => new Intl.NumberFormat("en-GB", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value).replace("US$", "$" );

function toRows(report: Report): UsageRow[] {
  return report.messages.flatMap((bucket) => {
    const date = typeof bucket.starting_at === "string" ? bucket.starting_at : "";
    const entries = Array.isArray(bucket.results) ? bucket.results as Bucket[] : [];
    return entries.map((item) => ({
      date, model: String(item.model ?? "Unknown model"), requests: asNumber(item.request_count),
      input: asNumber(item.uncached_input_tokens), output: asNumber(item.output_tokens),
      cacheRead: asNumber(item.cache_read_input_tokens), cacheWrite: asNumber(item.cache_creation_input_tokens),
      cost: asNumber(item.cost),
    }));
  });
}

function Metric({ title, value, note, icon: Icon }: { title: string; value: string; note: string; icon: typeof Activity }) {
  return <article className="rounded-2xl border border-white/10 bg-[#101821]/90 p-5 shadow-lg shadow-black/10">
    <div className="flex items-center justify-between"><p className="text-sm text-slate-400">{title}</p><Icon className="h-4 w-4 text-cyan-300" /></div>
    <p className="mt-4 text-3xl font-semibold tracking-tight text-white tabular-nums">{value}</p><p className="mt-2 text-xs text-slate-500">{note}</p>
  </article>;
}

export default function AnthropicTrackerPage() {
  const [start, setStart] = useState(() => dateInput(new Date(new Date().getFullYear(), new Date().getMonth(), 1)));
  const [end, setEnd] = useState(() => dateInput(new Date()));
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [modelFilter, setModelFilter] = useState("all");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ start: new Date(`${start}T00:00:00Z`).toISOString(), end: new Date(`${end}T23:59:59Z`).toISOString() });
      const response = await fetch(`/api/anthropic-usage?${params}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to load Anthropic usage");
      setReport(data);
    } catch (e) { setReport(null); setError(e instanceof Error ? e.message : "Unable to load Anthropic usage"); }
    finally { setLoading(false); }
  }, [start, end]);
  useEffect(() => { void load(); }, [load]);

  const rows = useMemo(() => report ? toRows(report) : [], [report]);
  const models = useMemo(() => Array.from(new Set(rows.map((row) => row.model))).sort(), [rows]);
  const filtered = modelFilter === "all" ? rows : rows.filter((row) => row.model === modelFilter);
  const totals = filtered.reduce((sum, row) => ({ requests: sum.requests + row.requests, input: sum.input + row.input,
    output: sum.output + row.output, cacheRead: sum.cacheRead + row.cacheRead, cacheWrite: sum.cacheWrite + row.cacheWrite, cost: sum.cost + row.cost }),
  { requests: 0, input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0 });
  const byDay = Array.from(filtered.reduce((map, row) => map.set(row.date, (map.get(row.date) ?? 0) + row.cost), new Map<string, number>()).entries()).sort(([a], [b]) => a.localeCompare(b));
  const maxCost = Math.max(0.000001, ...byDay.map(([, cost]) => cost));
  const dateLabel = report ? `${new Date(report.start).toLocaleDateString("en-GB")} – ${new Date(report.end).toLocaleDateString("en-GB")}` : `${start} – ${end}`;

  return <main className="mx-auto max-w-[1500px] space-y-6 p-5 text-slate-100 md:p-8">
    <header className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
      <div><div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[.22em] text-cyan-300"><Sparkles className="h-4 w-4" />Provider intelligence</div>
        <h1 className="text-3xl font-semibold tracking-tight text-white md:text-4xl">Anthropic tracker</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">Organization level Claude API usage and cost, reported directly by Anthropic.</p></div>
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-white/10 bg-[#101821]/90 p-3">
        <label className="text-xs text-slate-400">From<input aria-label="From date" type="date" value={start} max={end} onChange={(e) => setStart(e.target.value)} className="mt-1 block rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white" /></label>
        <label className="text-xs text-slate-400">To<input aria-label="To date" type="date" value={end} max={dateInput(new Date())} onChange={(e) => setEnd(e.target.value)} className="mt-1 block rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white" /></label>
        <button onClick={() => void load()} disabled={loading} className="inline-flex h-10 items-center gap-2 rounded-lg bg-cyan-300 px-3 text-sm font-semibold text-slate-950 hover:bg-cyan-200 disabled:opacity-60"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</button>
      </div>
    </header>

    {error && <section role="alert" className="rounded-xl border border-amber-300/25 bg-amber-300/5 p-4"><p className="font-medium text-amber-100">Usage report unavailable</p><p className="mt-1 text-sm text-amber-100/70">{error}</p><p className="mt-2 text-xs text-slate-400">Configure an Anthropic Admin API key as <code className="text-cyan-200">ANTHROPIC_ADMIN_API_KEY</code> in the admin server environment.</p></section>}
    {report && <>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500"><span className="inline-flex items-center gap-2"><CalendarDays className="h-3.5 w-3.5" />{dateLabel}</span><label className="flex items-center gap-2">Model<select value={modelFilter} onChange={(e) => setModelFilter(e.target.value)} className="rounded-md border border-white/10 bg-slate-950 px-2 py-1.5 text-slate-200"><option value="all">All models</option>{models.map((model) => <option key={model}>{model}</option>)}</select></label></div>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric title="Estimated API cost" value={gbp(totals.cost)} note="Anthropic reported cost · USD" icon={Coins} />
        <Metric title="Requests" value={fmt(totals.requests)} note="Completed API requests" icon={Zap} />
        <Metric title="Input tokens" value={fmt(totals.input + totals.cacheRead + totals.cacheWrite)} note={`${fmt(totals.cacheRead)} cache read · ${fmt(totals.cacheWrite)} cache write`} icon={Activity} />
        <Metric title="Output tokens" value={fmt(totals.output)} note="Generated tokens" icon={Sparkles} />
      </section>
      <section className="grid gap-5 xl:grid-cols-[1.3fr_.7fr]">
        <article className="rounded-2xl border border-white/10 bg-[#101821]/90 p-5"><div className="flex items-start justify-between"><div><h2 className="font-semibold text-white">Daily spend</h2><p className="mt-1 text-xs text-slate-500">Reported cost by UTC day · USD</p></div><span className="rounded-full border border-cyan-300/15 bg-cyan-300/5 px-2.5 py-1 text-xs text-cyan-100">{byDay.length} days</span></div>
          {byDay.length ? <div className="mt-7 flex h-48 items-end gap-1.5 overflow-x-auto border-b border-white/10 pb-0">{byDay.map(([day, cost]) => <div key={day} title={`${day}: ${gbp(cost)}`} className="group flex h-full min-w-4 flex-1 flex-col justify-end"><div className="w-full rounded-t bg-gradient-to-t from-cyan-500/40 to-cyan-300 transition-colors group-hover:to-white" style={{ height: `${Math.max(3, cost / maxCost * 100)}%` }} /><span className="mt-2 text-center text-[9px] text-slate-600">{new Date(day).getUTCDate()}</span></div>)}</div> : <p className="mt-12 text-center text-sm text-slate-500">No reported usage in this range.</p>}
        </article>
        <article className="rounded-2xl border border-white/10 bg-[#101821]/90 p-5"><h2 className="font-semibold text-white">Usage mix</h2><p className="mt-1 text-xs text-slate-500">Token categories across selected models</p><div className="mt-6 space-y-5">{[["Uncached input", totals.input, "bg-cyan-300"], ["Cache reads", totals.cacheRead, "bg-violet-300"], ["Cache writes", totals.cacheWrite, "bg-amber-300"], ["Output", totals.output, "bg-emerald-300"]].map(([label, value, color]) => { const amount = Number(value); const max = Math.max(1, totals.input, totals.cacheRead, totals.cacheWrite, totals.output); return <div key={String(label)}><div className="mb-1.5 flex justify-between text-xs"><span className="text-slate-300">{label}</span><span className="tabular-nums text-slate-400">{fmt(amount)}</span></div><div className="h-1.5 rounded-full bg-white/5"><div className={`h-full rounded-full ${color}`} style={{ width: `${amount / max * 100}%` }} /></div></div>; })}</div>
          <p className="mt-6 border-t border-white/10 pt-4 text-xs text-slate-500">Web search buckets: {report.web_search.length ? "included in usage report" : "no usage reported"}</p>
        </article>
      </section>
      <section className="overflow-hidden rounded-2xl border border-white/10 bg-[#101821]/90"><div className="border-b border-white/10 px-5 py-4"><h2 className="font-semibold text-white">Model breakdown</h2><p className="mt-1 text-xs text-slate-500">Daily aggregates from Anthropic’s organization usage report</p></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-white/[.025] text-xs uppercase tracking-wide text-slate-500"><tr>{["Day (UTC)", "Model", "Requests", "Input", "Cache read", "Output", "Cost (USD)"].map((label) => <th key={label} className="px-5 py-3 font-medium">{label}</th>)}</tr></thead><tbody className="divide-y divide-white/[.06]">{filtered.slice().sort((a, b) => b.date.localeCompare(a.date) || a.model.localeCompare(b.model)).map((row, i) => <tr key={`${row.date}-${row.model}-${i}`} className="text-slate-300"><td className="px-5 py-3">{row.date ? new Date(row.date).toLocaleDateString("en-GB", { timeZone: "UTC" }) : "—"}</td><td className="px-5 py-3 font-medium text-white">{row.model}</td><td className="px-5 py-3 tabular-nums">{fmt(row.requests)}</td><td className="px-5 py-3 tabular-nums">{fmt(row.input)}</td><td className="px-5 py-3 tabular-nums">{fmt(row.cacheRead)}</td><td className="px-5 py-3 tabular-nums">{fmt(row.output)}</td><td className="px-5 py-3 tabular-nums">{gbp(row.cost)}</td></tr>)}</tbody></table>{filtered.length === 0 && <p className="p-8 text-center text-sm text-slate-500">No usage rows for this selection.</p>}</div>
      </section>
      <p className="text-xs text-slate-600">Anthropic organization-level data may be delayed. Costs are returned in USD by Anthropic. Last fetched {new Date(report.fetched_at).toLocaleString("en-GB")}.</p>
    </>}
  </main>;
}
