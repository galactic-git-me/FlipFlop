"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart, Bar, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LabelList,
} from "recharts";
import { RefreshCw, TrendingUp, TrendingDown, Minus, ExternalLink, BrainCircuit, Database, Activity } from "lucide-react";
import { api } from "@/lib/api";
import { ClassificationBadge } from "@/components/classification-badge";
import type { DemandCategory, AuctionIntelItem, DemandSummary, SoldMarketDemand, SoldMarketInsight, SoldMarketListing, SoldComponentCategory } from "@/lib/types";

// ── Local types ───────────────────────────────────────────────────────────────

type RichSignals = {
  google_trends: {
    queries: string[];
    timeseries: Record<string, { date: string; value: number }[]>;
    geo: Record<string, { region: string; code: string | null; value: number }[]>;
  };
  reddit: {
    posts: {
      reddit_id: string; query: string; topic: string; title: string;
      subreddit: string; score: number; comments: number;
      url: string | null; created_utc: string | null;
    }[];
  };
  steam: {
    stats: { category: string; name: string; percentage: number; change: number | null; collected_at: string | null }[];
  };
};

const EMPTY_RICH: RichSignals = {
  google_trends: { queries: [], timeseries: {}, geo: {} },
  reddit: { posts: [] },
  steam: { stats: [] },
};

type Tab = "sold" | "categories" | "signals" | "auctions";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined, prefix = "£") {
  if (n == null) return "—";
  return `${prefix}${Math.round(n).toLocaleString()}`;
}

function fmtPct(n: number | null | undefined) {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
}

function fmtRelative(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return `${Math.floor(diff / 60000)}m ago`;
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function fmtTimeLeft(secs: number | null | undefined) {
  if (secs == null || secs <= 0) return "Ended";
  if (secs < 3600) return `${Math.round(secs / 60)} min`;
  if (secs < 86400) return `${Math.round(secs / 3600)} hr`;
  return `${Math.round(secs / 86400)} days`;
}

function strengthColor(s: string) {
  if (s === "High") return "#00dc82";
  if (s === "Medium") return "#f59e0b";
  return "#ef4444";
}

function urgencyColor(u: string) {
  if (u === "ending_soon") return "#ef4444";
  if (u === "today") return "#f59e0b";
  return "#374151";
}

// ── Pill slicer ───────────────────────────────────────────────────────────────

function Pills<T extends string>({
  options,
  value,
  onChange,
}: {
  options: T[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          className={`px-3 py-1 rounded-full text-xs font-medium border transition-all ${
            value === o
              ? "bg-[#00dc82]/15 border-[#00dc82]/50 text-[#00dc82]"
              : "bg-transparent border-white/10 text-slate-400 hover:border-white/25 hover:text-slate-300"
          }`}
        >
          {o}
        </button>
      ))}
    </div>
  );
}

// ── Sparkline ─────────────────────────────────────────────────────────────────

function Sparkline({ data }: { data: number[] }) {
  if (!data || data.length === 0) return <span className="text-slate-600 text-xs">—</span>;
  const max = Math.max(...data, 1);
  return (
    <div className="flex items-end gap-0.5 h-5 w-[60px]">
      {data.map((v, i) => (
        <div
          key={i}
          className="flex-1 rounded-sm bg-[#00dc82] opacity-70"
          style={{ height: `${Math.round((v / max) * 100)}%`, minHeight: 2 }}
        />
      ))}
    </div>
  );
}

// ── Error banner ──────────────────────────────────────────────────────────────

function ErrorBanner({ msg, onRetry }: { msg: string; onRetry: () => void }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-md border border-red-500/30 bg-red-500/10 text-red-300 text-sm">
      <span className="flex-1">{msg}</span>
      <button onClick={onRetry} className="underline hover:text-red-200 text-xs">Retry</button>
    </div>
  );
}

// ── Custom tooltip ────────────────────────────────────────────────────────────

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Record<string, unknown> }[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as Record<string, unknown>;
  return (
    <div className="bg-[#0a1628] border border-white/10 rounded-md px-3 py-2 text-xs text-slate-300 shadow-xl space-y-0.5">
      {Object.entries(d).map(([k, v]) =>
        typeof v !== "object" && v != null ? (
          <div key={k}>
            <span className="text-slate-500">{k}: </span>
            <span>{String(v)}</span>
          </div>
        ) : null
      )}
    </div>
  );
}

// ── Categories tab ────────────────────────────────────────────────────────────

type CatStrength = "All" | "High" | "Medium" | "Low";
type CatTrend = "All" | "Rising" | "Stable" | "Falling";
type CatSort = "Count ↓" | "Gem Count ↓" | "Avg Profit ↓" | "Avg Price ↓";
type CatMetric = "Listings" | "Avg Profit";

function CategoriesTab({ categories, loading, error, onRetry }: {
  categories: DemandCategory[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const [strength, setStrength] = useState<CatStrength>("All");
  const [trend, setTrend] = useState<CatTrend>("All");
  const [sort, setSort] = useState<CatSort>("Count ↓");
  const [metric, setMetric] = useState<CatMetric>("Listings");

  const filtered = useMemo(() => {
    let rows = [...categories];
    if (strength !== "All") rows = rows.filter((r) => r.strength === strength);
    if (trend !== "All") rows = rows.filter((r) => r.trend === trend.toLowerCase());
    if (sort === "Count ↓") rows.sort((a, b) => b.count - a.count);
    else if (sort === "Gem Count ↓") rows.sort((a, b) => b.gem_count - a.gem_count);
    else if (sort === "Avg Profit ↓") rows.sort((a, b) => (b.avg_profit ?? 0) - (a.avg_profit ?? 0));
    else if (sort === "Avg Price ↓") rows.sort((a, b) => (b.avg_price ?? 0) - (a.avg_price ?? 0));
    return rows;
  }, [categories, strength, trend, sort]);

  const chartData = filtered.slice(0, 12).map((c) => ({
    name: `${c.emoji} ${c.name.slice(0, 12)}`,
    value: metric === "Listings" ? c.count : (c.avg_profit ?? 0),
    strength: c.strength,
    count: c.count,
    gem_count: c.gem_count,
    avg_profit: c.avg_profit != null ? `£${Math.round(c.avg_profit)}` : "—",
    trend: c.trend,
  }));

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner msg={`Failed to load categories — ${error}`} onRetry={onRetry} />;
  if (!categories.length) return <Empty label="No category data yet." />;

  return (
    <div className="space-y-4">
      {/* Slicers */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Strength</span>
          <Pills<CatStrength>
            options={["All", "High", "Medium", "Low"]}
            value={strength}
            onChange={setStrength}
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Trend</span>
          <Pills<CatTrend>
            options={["All", "Rising", "Stable", "Falling"]}
            value={trend}
            onChange={setTrend}
          />
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-xs text-slate-500">Chart</span>
          <Pills<CatMetric> options={["Listings", "Avg Profit"]} value={metric} onChange={setMetric} />
        </div>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as CatSort)}
          className="bg-[#0a1628] border border-white/10 text-slate-300 text-xs rounded-md px-2 py-1"
        >
          {(["Count ↓", "Gem Count ↓", "Avg Profit ↓", "Avg Price ↓"] as CatSort[]).map((o) => (
            <option key={o}>{o}</option>
          ))}
        </select>
      </div>

      {/* Chart */}
      <div className="bg-[#070e1a] rounded-lg border border-white/5 p-3">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 40, left: 0 }}>
            <XAxis
              dataKey="name"
              tick={{ fill: "#64748b", fontSize: 10 }}
              angle={-35}
              textAnchor="end"
              interval={0}
            />
            <YAxis tick={{ fill: "#64748b", fontSize: 10 }} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="value" radius={[3, 3, 0, 0]}>
              {chartData.map((d, i) => (
                <Cell key={i} fill={strengthColor(d.strength)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-white/5">
        <table className="w-full text-xs text-left">
          <thead className="bg-[#070e1a] text-slate-500 uppercase text-[10px] tracking-wide">
            <tr>
              {["Category", "Strength", "Trend", "Listings", "Gems", "Gem Rate", "Avg Profit", "Avg Price", "Insight", "7-Day"].map((h) => (
                <th key={h} className="px-3 py-2 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filtered.map((c) => {
              const gemRate = c.count > 0 ? ((c.gem_count / c.count) * 100).toFixed(1) : "0.0";
              return (
                <tr key={c.name} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-3 py-2 whitespace-nowrap font-medium text-slate-200">
                    {c.emoji} {c.name}
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-semibold" style={{ color: strengthColor(c.strength) }}>
                      {c.strength}
                    </span>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-slate-400">
                    <TrendIcon trend={c.trend} />
                  </td>
                  <td className="px-3 py-2 text-slate-300">{c.count}</td>
                  <td className="px-3 py-2 text-[#00dc82]">{c.gem_count}</td>
                  <td className="px-3 py-2 text-slate-400">{gemRate}%</td>
                  <td className="px-3 py-2" style={{ color: (c.avg_profit ?? 0) > 100 ? "#00dc82" : "#f59e0b" }}>
                    {fmt(c.avg_profit)}
                  </td>
                  <td className="px-3 py-2 text-slate-400">{fmt(c.avg_price)}</td>
                  <td className="px-3 py-2 text-slate-500 max-w-[180px] truncate" title={c.insight}>
                    {c.insight}
                  </td>
                  <td className="px-3 py-2">
                    <Sparkline data={c.sparkline} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="text-center py-8 text-slate-600 text-xs">No categories match filters.</div>
        )}
      </div>
    </div>
  );
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === "rising") return <span className="flex items-center gap-1 text-[#00dc82]"><TrendingUp className="w-3 h-3" /> rising</span>;
  if (trend === "falling") return <span className="flex items-center gap-1 text-red-400"><TrendingDown className="w-3 h-3" /> falling</span>;
  return <span className="flex items-center gap-1 text-slate-500"><Minus className="w-3 h-3" /> stable</span>;
}

// ── External Signals tab — three sub-source views ────────────────────────────

type SigSubTab = "google" | "reddit" | "steam";

function ExternalSignalsTab({ data, loading, error, onRetry }: {
  data: RichSignals;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const [subTab, setSubTab] = useState<SigSubTab>("google");

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner msg={`Failed to load signals — ${error}`} onRetry={onRetry} />;

  const isEmpty =
    data.google_trends.queries.length === 0 &&
    data.reddit.posts.length === 0 &&
    data.steam.stats.length === 0;

  if (isEmpty) return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-500">
      <p className="text-sm">No signal data yet — click <strong>Refresh</strong> to fetch from Google Trends, Reddit, and Steam.</p>
    </div>
  );

  const subTabs: { id: SigSubTab; label: string }[] = [
    { id: "google", label: "📈 Google Trends" },
    { id: "reddit", label: "💬 Reddit" },
    { id: "steam", label: "🎮 Steam Hardware" },
  ];

  return (
    <div className="space-y-4">
      {/* Sub-tab bar */}
      <div className="flex gap-1 border-b border-white/8">
        {subTabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setSubTab(t.id)}
            className={`px-4 py-2 text-xs font-medium border-b-2 -mb-px transition-all ${
              subTab === t.id
                ? "border-[#4fc3f7] text-[#4fc3f7]"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {subTab === "google" && <GoogleTrendsView data={data.google_trends} />}
      {subTab === "reddit" && <RedditView posts={data.reddit.posts} />}
      {subTab === "steam" && <SteamView stats={data.steam.stats} />}
    </div>
  );
}

// ── Google Trends view ────────────────────────────────────────────────────────

function GoogleTrendsView({ data }: {
  data: RichSignals["google_trends"];
}) {
  const queries = data.queries;
  const [selectedQuery, setSelectedQuery] = useState<string>(queries[0] ?? "");

  const tsData = useMemo(
    () => (selectedQuery && data.timeseries[selectedQuery]) ? data.timeseries[selectedQuery] : [],
    [data.timeseries, selectedQuery],
  );

  const geoData = useMemo(
    () => (selectedQuery && data.geo[selectedQuery]) ? data.geo[selectedQuery].slice(0, 15) : [],
    [data.geo, selectedQuery],
  );

  if (queries.length === 0) return <Empty label="No Google Trends data — click Refresh." />;

  return (
    <div className="space-y-4">
      {/* Query picker */}
      <div className="flex flex-wrap gap-1.5">
        {queries.map((q) => (
          <button
            key={q}
            onClick={() => setSelectedQuery(q)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-all ${
              selectedQuery === q
                ? "bg-[#4fc3f7]/15 border-[#4fc3f7]/50 text-[#4fc3f7]"
                : "bg-transparent border-white/10 text-slate-400 hover:border-white/25 hover:text-slate-300"
            }`}
          >
            {q}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Time series chart */}
        <div className="bg-[#070e1a] rounded-lg border border-white/5 p-3">
          <p className="text-[10px] text-slate-500 mb-2">Interest over time (7 days) — <span className="text-[#4fc3f7]">{selectedQuery}</span></p>
          {tsData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={tsData} margin={{ top: 4, right: 8, bottom: 20, left: 0 }}>
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#64748b", fontSize: 9 }}
                  angle={-30}
                  textAnchor="end"
                  interval={Math.floor(tsData.length / 6)}
                />
                <YAxis tick={{ fill: "#64748b", fontSize: 10 }} domain={[0, 100]} />
                <Tooltip content={<ChartTooltip />} />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#4fc3f7"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: "#4fc3f7" }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[180px] text-slate-600 text-xs">No time-series data</div>
          )}
        </div>

        {/* Geo chart */}
        <div className="bg-[#070e1a] rounded-lg border border-white/5 p-3">
          <p className="text-[10px] text-slate-500 mb-2">Top regions by interest — <span className="text-[#4fc3f7]">{selectedQuery}</span></p>
          {geoData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={geoData} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 80 }}>
                <XAxis type="number" tick={{ fill: "#64748b", fontSize: 9 }} domain={[0, 100]} />
                <YAxis
                  type="category"
                  dataKey="region"
                  tick={{ fill: "#94a3b8", fontSize: 9 }}
                  width={76}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="value" fill="#4fc3f7" radius={[0, 3, 3, 0]} opacity={0.8}>
                  <LabelList dataKey="value" position="right" style={{ fill: "#64748b", fontSize: 9 }} formatter={(v: unknown) => `${v}`} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[180px] text-slate-600 text-xs">No geo data</div>
          )}
        </div>
      </div>

      {/* All queries summary table */}
      <div className="overflow-x-auto rounded-lg border border-white/5">
        <table className="w-full text-xs text-left">
          <thead className="bg-[#070e1a] text-slate-500 uppercase text-[10px] tracking-wide">
            <tr>
              <th className="px-3 py-2">Search Term</th>
              <th className="px-3 py-2">Data Points</th>
              <th className="px-3 py-2">Latest Value</th>
              <th className="px-3 py-2">Peak (7d)</th>
              <th className="px-3 py-2">Top Region</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {queries.map((q) => {
              const ts = data.timeseries[q] ?? [];
              const geo = data.geo[q] ?? [];
              const latest = ts[ts.length - 1]?.value ?? 0;
              const peak = ts.length ? Math.max(...ts.map((r) => r.value)) : 0;
              return (
                <tr
                  key={q}
                  className="hover:bg-white/[0.02] transition-colors cursor-pointer"
                  onClick={() => setSelectedQuery(q)}
                >
                  <td className="px-3 py-2 font-medium" style={{ color: selectedQuery === q ? "#4fc3f7" : "#cbd5e1" }}>{q}</td>
                  <td className="px-3 py-2 text-slate-500">{ts.length}</td>
                  <td className="px-3 py-2 font-mono" style={{ color: latest >= 60 ? "#00dc82" : latest >= 30 ? "#f59e0b" : "#ef4444" }}>
                    {Math.round(latest)}
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-400">{Math.round(peak)}</td>
                  <td className="px-3 py-2 text-slate-500">{geo[0]?.region ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Reddit view ───────────────────────────────────────────────────────────────

function RedditView({ posts }: { posts: RichSignals["reddit"]["posts"] }) {
  const [topicFilter, setTopicFilter] = useState("All");
  const [queryFilter, setQueryFilter] = useState("All");
  const [sort, setSort] = useState<"Score ↓" | "Comments ↓" | "Date ↓">("Score ↓");

  const topics = useMemo(() => ["All", ...Array.from(new Set(posts.map((p) => p.topic)))], [posts]);
  const queries = useMemo(() => {
    const filtered = topicFilter === "All" ? posts : posts.filter((p) => p.topic === topicFilter);
    return ["All", ...Array.from(new Set(filtered.map((p) => p.query)))];
  }, [posts, topicFilter]);

  const filtered = useMemo(() => {
    let rows = [...posts];
    if (topicFilter !== "All") rows = rows.filter((p) => p.topic === topicFilter);
    if (queryFilter !== "All") rows = rows.filter((p) => p.query === queryFilter);
    if (sort === "Score ↓") rows.sort((a, b) => b.score - a.score);
    else if (sort === "Comments ↓") rows.sort((a, b) => b.comments - a.comments);
    else if (sort === "Date ↓") rows.sort((a, b) => new Date(b.created_utc ?? 0).getTime() - new Date(a.created_utc ?? 0).getTime());
    return rows;
  }, [posts, topicFilter, queryFilter, sort]);

  // Subreddit bar chart
  const subredditChart = useMemo(() => {
    const counts: Record<string, number> = {};
    filtered.forEach((p) => { counts[p.subreddit] = (counts[p.subreddit] ?? 0) + 1; });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([sub, cnt]) => ({ sub, cnt }));
  }, [filtered]);

  if (posts.length === 0) return <Empty label="No Reddit posts — click Refresh." />;

  return (
    <div className="space-y-4">
      {/* Slicers */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Topic</span>
          <select value={topicFilter} onChange={(e) => { setTopicFilter(e.target.value); setQueryFilter("All"); }}
            className="bg-[#0a1628] border border-white/10 text-slate-300 text-xs rounded-md px-2 py-1">
            {topics.map((t) => <option key={t}>{t.replace(/_/g, " ")}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Query</span>
          <select value={queryFilter} onChange={(e) => setQueryFilter(e.target.value)}
            className="bg-[#0a1628] border border-white/10 text-slate-300 text-xs rounded-md px-2 py-1">
            {queries.map((q) => <option key={q}>{q}</option>)}
          </select>
        </div>
        <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}
          className="ml-auto bg-[#0a1628] border border-white/10 text-slate-300 text-xs rounded-md px-2 py-1">
          {(["Score ↓", "Comments ↓", "Date ↓"] as const).map((o) => <option key={o}>{o}</option>)}
        </select>
      </div>

      {/* Subreddit distribution chart */}
      {subredditChart.length > 0 && (
        <div className="bg-[#070e1a] rounded-lg border border-white/5 p-3">
          <p className="text-[10px] text-slate-500 mb-2">Posts by subreddit</p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={subredditChart} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 90 }}>
              <XAxis type="number" tick={{ fill: "#64748b", fontSize: 9 }} />
              <YAxis type="category" dataKey="sub" tick={{ fill: "#94a3b8", fontSize: 9 }} width={86} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="cnt" fill="#ff6b6b" radius={[0, 3, 3, 0]} opacity={0.8}>
                <LabelList dataKey="cnt" position="right" style={{ fill: "#64748b", fontSize: 9 }} formatter={(v: unknown) => `${v}`} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Posts table */}
      <div className="overflow-x-auto rounded-lg border border-white/5">
        <div className="px-3 py-2 bg-[#070e1a] text-[10px] text-slate-500">{filtered.length} posts</div>
        <table className="w-full text-xs text-left">
          <thead className="bg-[#070e1a] text-slate-500 uppercase text-[10px] tracking-wide border-t border-white/5">
            <tr>
              {["Title", "Subreddit", "Score", "Comments", "Query", "Posted"].map((h) => (
                <th key={h} className="px-3 py-2 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filtered.slice(0, 100).map((p) => (
              <tr key={p.reddit_id} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-3 py-2 max-w-[280px]">
                  {p.url ? (
                    <a href={p.url} target="_blank" rel="noopener noreferrer"
                      className="flex items-start gap-1 text-slate-200 hover:text-[#ff6b6b] transition-colors line-clamp-2">
                      <ExternalLink className="w-3 h-3 flex-shrink-0 mt-0.5 opacity-50" />
                      {p.title}
                    </a>
                  ) : (
                    <span className="text-slate-300 line-clamp-2">{p.title}</span>
                  )}
                </td>
                <td className="px-3 py-2 whitespace-nowrap text-[#ff6b6b]/80">r/{p.subreddit}</td>
                <td className="px-3 py-2 font-mono text-slate-300">{p.score.toLocaleString()}</td>
                <td className="px-3 py-2 text-slate-500">{p.comments}</td>
                <td className="px-3 py-2">
                  <span className="px-1.5 py-0.5 rounded bg-white/5 text-slate-400 text-[10px]">{p.query}</span>
                </td>
                <td className="px-3 py-2 text-slate-600 whitespace-nowrap">
                  {p.created_utc ? fmtRelative(p.created_utc) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="text-center py-8 text-slate-600 text-xs">No posts match filters.</div>
        )}
      </div>
    </div>
  );
}

// ── Steam view ────────────────────────────────────────────────────────────────

type SteamCat = "GPU" | "CPU" | "RAM" | "OS";

function SteamView({ stats }: { stats: RichSignals["steam"]["stats"] }) {
  const [cat, setCat] = useState<SteamCat>("GPU");

  const categories = useMemo(
    () => Array.from(new Set(stats.map((s) => s.category))) as SteamCat[],
    [stats],
  );

  const filtered = useMemo(
    () => stats.filter((s) => s.category === cat).sort((a, b) => b.percentage - a.percentage).slice(0, 20),
    [stats, cat],
  );

  const collectedAt = stats[0]?.collected_at ? fmtRelative(stats[0].collected_at) : null;

  if (stats.length === 0) return <Empty label="No Steam data — click Refresh." />;

  return (
    <div className="space-y-4">
      {/* Category pills + collected timestamp */}
      <div className="flex items-center gap-3">
        <div className="flex gap-1.5">
          {(categories.length > 0 ? categories : (["GPU", "CPU", "RAM", "OS"] as SteamCat[])).map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition-all ${
                cat === c
                  ? "bg-[#81c784]/15 border-[#81c784]/50 text-[#81c784]"
                  : "bg-transparent border-white/10 text-slate-400 hover:border-white/25 hover:text-slate-300"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
        {collectedAt && <span className="ml-auto text-[10px] text-slate-600">Updated {collectedAt}</span>}
      </div>

      {/* Bar chart */}
      <div className="bg-[#070e1a] rounded-lg border border-white/5 p-3">
        <p className="text-[10px] text-slate-500 mb-2">Market share % — Steam Hardware Survey</p>
        {filtered.length > 0 ? (
          <ResponsiveContainer width="100%" height={filtered.length * 26 + 20}>
            <BarChart data={filtered} layout="vertical" margin={{ top: 0, right: 60, bottom: 0, left: 160 }}>
              <XAxis type="number" tick={{ fill: "#64748b", fontSize: 9 }} tickFormatter={(v) => `${v}%`} />
              <YAxis type="category" dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9 }} width={156} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="percentage" fill="#81c784" radius={[0, 3, 3, 0]} opacity={0.85}>
                <LabelList
                  dataKey="percentage"
                  position="right"
                  style={{ fill: "#64748b", fontSize: 9 }}
                  formatter={(v: unknown) => `${v}%`}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-24 text-slate-600 text-xs">No {cat} data</div>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-white/5">
        <table className="w-full text-xs text-left">
          <thead className="bg-[#070e1a] text-slate-500 uppercase text-[10px] tracking-wide">
            <tr>
              <th className="px-3 py-2">Item</th>
              <th className="px-3 py-2">Market Share</th>
              <th className="px-3 py-2">Change</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filtered.map((s, i) => (
              <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-3 py-2 text-slate-200">{s.name}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-1.5 rounded-full bg-white/10 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[#81c784]"
                        style={{ width: `${Math.min(100, (s.percentage / (filtered[0]?.percentage || 1)) * 100)}%` }}
                      />
                    </div>
                    <span className="font-mono text-slate-300">{s.percentage.toFixed(2)}%</span>
                  </div>
                </td>
                <td className="px-3 py-2 font-mono whitespace-nowrap" style={{
                  color: s.change == null ? "#64748b" : s.change > 0 ? "#00dc82" : s.change < 0 ? "#ef4444" : "#64748b"
                }}>
                  {s.change != null ? `${s.change > 0 ? "+" : ""}${s.change.toFixed(2)}%` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Auction Intel tab ─────────────────────────────────────────────────────────

type AucUrgency = "All" | "Ending Soon" | "Today" | "Upcoming";
type AucSort = "Time Left ↑" | "Price ↑" | "Profit ↓" | "Score ↓";

function AuctionIntelTab({ auctions, loading, error, onRetry }: {
  auctions: AuctionIntelItem[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const [urgency, setUrgency] = useState<AucUrgency>("All");
  const [sort, setSort] = useState<AucSort>("Time Left ↑");

  const filtered = useMemo(() => {
    let rows = [...auctions];
    if (urgency === "Ending Soon") rows = rows.filter((r) => r.urgency === "ending_soon");
    else if (urgency === "Today") rows = rows.filter((r) => r.urgency === "today");
    else if (urgency === "Upcoming") rows = rows.filter((r) => r.urgency === "upcoming");
    if (sort === "Time Left ↑") rows.sort((a, b) => (a.time_left_secs ?? 9e9) - (b.time_left_secs ?? 9e9));
    else if (sort === "Price ↑") rows.sort((a, b) => a.price - b.price);
    else if (sort === "Profit ↓") rows.sort((a, b) => (b.estimated_profit ?? 0) - (a.estimated_profit ?? 0));
    else if (sort === "Score ↓") rows.sort((a, b) => b.gem_score - a.gem_score);
    return rows;
  }, [auctions, urgency, sort]);

  const top10 = useMemo(
    () => [...auctions]
      .sort((a, b) => (b.estimated_profit ?? 0) - (a.estimated_profit ?? 0))
      .slice(0, 10)
      .map((a) => ({
        name: a.title.slice(0, 25),
        profit: Math.round(a.estimated_profit ?? 0),
        urgency: a.urgency,
      })),
    [auctions],
  );

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner msg={`Failed to load auctions — ${error}`} onRetry={onRetry} />;
  if (!auctions.length) return <Empty label="No live auctions found." />;

  return (
    <div className="space-y-4">
      {/* Slicers */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Urgency</span>
          <Pills<AucUrgency>
            options={["All", "Ending Soon", "Today", "Upcoming"]}
            value={urgency}
            onChange={setUrgency}
          />
        </div>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as AucSort)}
          className="ml-auto bg-[#0a1628] border border-white/10 text-slate-300 text-xs rounded-md px-2 py-1"
        >
          {(["Time Left ↑", "Price ↑", "Profit ↓", "Score ↓"] as AucSort[]).map((o) => (
            <option key={o}>{o}</option>
          ))}
        </select>
      </div>

      {/* Chart — top 10 by profit (horizontal) */}
      <div className="bg-[#070e1a] rounded-lg border border-white/5 p-3">
        <p className="text-[10px] text-slate-500 mb-2">Top 10 by estimated profit</p>
        <ResponsiveContainer width="100%" height={top10.length * 26 + 20}>
          <BarChart data={top10} layout="vertical" margin={{ top: 0, right: 50, bottom: 0, left: 140 }}>
            <XAxis type="number" tick={{ fill: "#64748b", fontSize: 10 }} />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              width={130}
            />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="profit" radius={[0, 3, 3, 0]}>
              <LabelList dataKey="profit" position="right" style={{ fill: "#94a3b8", fontSize: 10 }} formatter={(v: unknown) => `£${v}`} />
              {top10.map((d, i) => (
                <Cell key={i} fill={urgencyColor(d.urgency)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-white/5">
        <table className="w-full text-xs text-left">
          <thead className="bg-[#070e1a] text-slate-500 uppercase text-[10px] tracking-wide">
            <tr>
              {["Listing", "CPU / GPU", "Bid", "Est. Profit", "Score", "Classification", "Time Left", "Urgency"].map((h) => (
                <th key={h} className="px-3 py-2 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filtered.map((a) => (
              <tr
                key={a.id}
                className="hover:bg-white/[0.02] transition-colors"
                style={{ borderLeft: `3px solid ${urgencyColor(a.urgency)}` }}
              >
                <td className="px-3 py-2 max-w-[200px]">
                  <a
                    href={a.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-1 text-slate-200 hover:text-[#00dc82] transition-colors line-clamp-2"
                  >
                    <ExternalLink className="w-3 h-3 flex-shrink-0 mt-0.5 opacity-60" />
                    {a.title}
                  </a>
                </td>
                <td className="px-3 py-2 text-slate-500 whitespace-nowrap">
                  {[a.cpu?.slice(0, 12), a.gpu?.slice(0, 12)].filter(Boolean).join(" · ") || "—"}
                </td>
                <td className="px-3 py-2 text-slate-300 whitespace-nowrap">{fmt(a.price)}</td>
                <td className="px-3 py-2 whitespace-nowrap font-semibold" style={{
                  color: (a.estimated_profit ?? 0) > 100 ? "#00dc82" : (a.estimated_profit ?? 0) > 0 ? "#f59e0b" : "#ef4444"
                }}>
                  {fmt(a.estimated_profit)}
                </td>
                <td className="px-3 py-2 text-slate-400">{Math.round(a.gem_score)}</td>
                <td className="px-3 py-2">
                  <ClassificationBadge classification={a.classification as never} />
                </td>
                <td className="px-3 py-2 text-slate-400 whitespace-nowrap">{fmtTimeLeft(a.time_left_secs)}</td>
                <td className="px-3 py-2 whitespace-nowrap">
                  <span
                    className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                    style={{
                      color: urgencyColor(a.urgency),
                      background: `${urgencyColor(a.urgency)}18`,
                    }}
                  >
                    {a.urgency === "ending_soon" ? "🔴 Ending Soon" : a.urgency === "today" ? "🟡 Today" : "⬜ Upcoming"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="text-center py-8 text-slate-600 text-xs">No auctions match filters.</div>
        )}
      </div>
    </div>
  );
}

// ── Loading / Empty ───────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16 text-slate-600 text-sm gap-2">
      <RefreshCw className="w-4 h-4 animate-spin" />
      Loading…
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center py-16 text-slate-600 text-xs">{label}</div>
  );
}

// ── Header KPIs ───────────────────────────────────────────────────────────────

function MarketHealthBadge({ health }: { health: string }) {
  const cfg = {
    hot: { label: "🔥 Hot", color: "text-[#00dc82]", bg: "bg-[#00dc82]/10 border-[#00dc82]/30" },
    warm: { label: "🌤 Warm", color: "text-amber-400", bg: "bg-amber-400/10 border-amber-400/30" },
    cold: { label: "❄️ Cold", color: "text-blue-400", bg: "bg-blue-400/10 border-blue-400/30" },
  }[health] ?? { label: health, color: "text-slate-400", bg: "bg-white/5 border-white/10" };

  return (
    <span className={`px-2.5 py-1 rounded-md text-xs font-bold border ${cfg.color} ${cfg.bg}`}>
      {cfg.label}
    </span>
  );
}

function KpiChip({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="flex flex-col items-center px-3 py-1.5 rounded-md border border-white/8 bg-white/[0.02]">
      <span className="text-[10px] text-slate-500 uppercase tracking-wide">{label}</span>
      <span className={`text-sm font-bold ${color ?? "text-slate-200"}`}>{value}</span>
    </div>
  );
}

function SoldMarketTab({ data, insight, loading, error, refreshingInsight, onRetry, onRefreshInsight }: {
  data: SoldMarketDemand | null;
  insight: SoldMarketInsight | null;
  loading: boolean;
  error: string | null;
  refreshingInsight: boolean;
  onRetry: () => void;
  onRefreshInsight: () => void;
}) {
  const componentOptions: Array<{ value: SoldComponentCategory; label: string }> = [
    { value: "cpu", label: "CPUs" }, { value: "gpu", label: "GPUs" },
    { value: "motherboard", label: "Motherboards" }, { value: "ram", label: "RAM" },
    { value: "case", label: "PC Cases" }, { value: "psu", label: "PSUs" },
  ];
  const [soldCategory, setSoldCategory] = useState<SoldComponentCategory>("cpu");
  const [soldRows, setSoldRows] = useState<SoldMarketListing[]>([]);
  const [soldRowsLoading, setSoldRowsLoading] = useState(false);
  const [soldRowsError, setSoldRowsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSoldRowsLoading(true);
    setSoldRowsError(null);
    api.demand.soldMarketListings(soldCategory, 90, 250)
      .then((rows) => { if (!cancelled) setSoldRows(rows); })
      .catch((e: Error) => { if (!cancelled) { setSoldRows([]); setSoldRowsError(e.message); } })
      .finally(() => { if (!cancelled) setSoldRowsLoading(false); });
    return () => { cancelled = true; };
  }, [soldCategory]);

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner msg={`Failed to load sold-market demand — ${error}`} onRetry={onRetry} />;
  if (!data) return <Empty label="No sold-market snapshot is available yet." />;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {[
          ["Completed evidence", data.totals.sold_observations],
          ["Matched evidence", data.totals.matched_sold_observations],
          ["Live supply", data.totals.active_listings],
          ["Products covered", data.totals.products_with_sold_evidence],
          ["Unmatched", data.totals.unmatched_sold_observations],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-white/10 bg-[#081323] p-4">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
            <div className="mt-1 text-2xl font-black text-slate-100">{Number(value).toLocaleString()}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-lg border border-cyan-400/20 bg-gradient-to-br from-cyan-400/[0.06] to-purple-500/[0.04] p-4" aria-labelledby="ai-demand-heading">
          <div className="flex items-center gap-2">
            <BrainCircuit className="h-4 w-4 text-cyan-300" />
            <h2 id="ai-demand-heading" className="text-sm font-bold text-cyan-100">AI market brief</h2>
            {insight && <span className="text-[10px] text-slate-500">{insight.model}</span>}
            <button onClick={onRefreshInsight} disabled={refreshingInsight} className="ml-auto cursor-pointer rounded-md border border-cyan-300/20 px-2.5 py-1 text-xs text-cyan-200 transition-colors hover:bg-cyan-300/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 disabled:opacity-50">
              {refreshingInsight ? "Analysing…" : "Reanalyse"}
            </button>
          </div>
          <div className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300">
            {insight?.insight ?? "AI analysis is unavailable; the evidence tables below remain fully usable."}
          </div>
        </section>

        <section className="rounded-lg border border-white/10 bg-[#070e1a] p-4" aria-labelledby="evidence-trend-heading">
          <div className="mb-2 flex items-center gap-2">
            <Activity className="h-4 w-4 text-emerald-300" />
            <h2 id="evidence-trend-heading" className="text-sm font-bold text-slate-200">Completed evidence collected</h2>
          </div>
          <ResponsiveContainer width="100%" height={165}>
            <LineChart data={data.weekly} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis dataKey="week" tick={{ fill: "#64748b", fontSize: 10 }} />
              <YAxis tick={{ fill: "#64748b", fontSize: 10 }} />
              <Tooltip content={<ChartTooltip />} />
              <Line type="monotone" dataKey="sold_observations" stroke="#00dc82" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </section>
      </div>

      <div className="overflow-x-auto rounded-lg border border-white/10">
        <table className="w-full min-w-[900px] text-left text-xs">
          <thead className="bg-white/[0.03] text-[10px] uppercase tracking-wider text-slate-500">
            <tr>{["Category", "Demand", "Completed", "Live", "Evidence balance", "Confidence", "Sold median", "Live median", "30d change"].map((h) => <th key={h} className="px-3 py-2.5">{h}</th>)}</tr>
          </thead>
          <tbody>
            {data.categories.map((row) => (
              <tr key={row.category} className="border-t border-white/[0.06] text-slate-300">
                <td className="px-3 py-3 font-semibold text-slate-100">{row.label}</td>
                <td className="px-3 py-3"><span style={{ color: strengthColor(row.strength) }}>{row.demand_score.toFixed(0)}/100 · {row.strength}</span></td>
                <td className="px-3 py-3">{row.sold_observations}</td><td className="px-3 py-3">{row.active_listings}</td>
                <td className="px-3 py-3">{fmtPct(row.evidence_ratio_pct)}</td><td className="px-3 py-3">{fmtPct(row.sample_confidence_pct)}</td>
                <td className="px-3 py-3">{fmt(row.median_sold_price)}</td><td className="px-3 py-3">{fmt(row.median_active_price)}</td>
                <td className={`px-3 py-3 ${row.trend_pct == null ? "text-slate-500" : row.trend_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>{row.trend_pct == null ? "New sample" : `${row.trend_pct > 0 ? "+" : ""}${row.trend_pct}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="rounded-lg border border-white/10 bg-[#070e1a] p-4">
        <div className="mb-3 flex items-center gap-2"><Database className="h-4 w-4 text-purple-300" /><h2 className="text-sm font-bold text-slate-200">Products with the strongest completed-sale evidence</h2></div>
        <div className="grid gap-2 md:grid-cols-2">
          {data.top_products.slice(0, 10).map((product) => (
            <div key={product.cpk} className="flex items-center gap-3 rounded-md border border-white/[0.07] bg-white/[0.02] px-3 py-2.5">
              <div className="min-w-0 flex-1"><div className="truncate text-xs font-semibold text-slate-200" title={product.name}>{product.name}</div><div className="mt-0.5 text-[10px] uppercase text-slate-500">{product.category}</div></div>
              <div className="text-right"><div className="text-xs text-emerald-300">{product.sold_observations} completed</div><div className="text-[10px] text-slate-500">{product.active_listings} live · {fmt(product.median_sold_price)}</div></div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-white/10 bg-[#070e1a]" aria-labelledby="sold-listings-heading">
        <div className="flex flex-wrap items-center gap-3 border-b border-white/[0.07] p-4">
          <div>
            <h2 id="sold-listings-heading" className="text-sm font-bold text-slate-200">Completed listings</h2>
            <p className="mt-0.5 text-[11px] text-slate-500">Most recently collected eBay sold evidence from the last 90 days.</p>
          </div>
          <label htmlFor="sold-component-category" className="ml-auto text-xs font-medium text-slate-400">Component type</label>
          <select
            id="sold-component-category"
            value={soldCategory}
            onChange={(event) => setSoldCategory(event.target.value as SoldComponentCategory)}
            className="cursor-pointer rounded-md border border-white/15 bg-[#0a1628] px-3 py-2 text-xs text-slate-200 outline-none transition-colors hover:border-emerald-300/40 focus-visible:ring-2 focus-visible:ring-emerald-300"
          >
            {componentOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </div>
        {soldRowsLoading ? <Spinner /> : soldRowsError ? (
          <div className="p-4 text-xs text-red-300">Could not load completed listings: {soldRowsError}</div>
        ) : soldRows.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">No matched sold evidence for this component type.</div>
        ) : (
          <div className="max-h-[560px] overflow-auto">
            <table className="w-full min-w-[820px] text-left text-xs">
              <thead className="sticky top-0 z-10 bg-[#0a1628] text-[10px] uppercase tracking-wider text-slate-500">
                <tr>{["Sold item", "Condition", "Item price", "Postage", "Delivered", "Observed", "Source"].map((heading) => <th key={heading} className="px-3 py-2.5">{heading}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-white/[0.06]">
                {soldRows.map((row) => (
                  <tr key={row.id} className="transition-colors hover:bg-white/[0.025]">
                    <td className="max-w-[360px] px-3 py-3 font-medium text-slate-200"><span className="line-clamp-2" title={row.name}>{row.name}</span></td>
                    <td className="px-3 py-3 capitalize text-slate-400">{row.condition}</td>
                    <td className="px-3 py-3 font-mono text-slate-300">{fmt(row.item_price)}</td>
                    <td className="px-3 py-3 font-mono text-slate-400">{fmt(row.postage)}</td>
                    <td className="px-3 py-3 font-mono font-semibold text-emerald-300">{fmt(row.delivered_price)}</td>
                    <td className="whitespace-nowrap px-3 py-3 text-slate-400" title={new Date(row.observed_at).toLocaleString()}>{fmtRelative(row.observed_at)}</td>
                    <td className="px-3 py-3">{row.source_url ? <a href={row.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex cursor-pointer items-center gap-1 text-cyan-300 transition-colors hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"><ExternalLink className="h-3 w-3" /> eBay</a> : <span className="text-slate-600">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="border-t border-white/[0.07] px-4 py-2 text-[10px] text-slate-500">Showing {soldRows.length.toLocaleString()} most recent matched observations (maximum 250).</div>
      </section>

      <p className="rounded-md border border-amber-400/15 bg-amber-400/[0.05] px-3 py-2 text-xs leading-5 text-amber-100/70">{data.methodology}</p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DemandPage() {
  const [tab, setTab] = useState<Tab>("sold");

  const [summary, setSummary] = useState<DemandSummary | null>(null);
  const [categories, setCategories] = useState<DemandCategory[]>([]);
  const [richSignals, setRichSignals] = useState<RichSignals>(EMPTY_RICH);
  const [auctions, setAuctions] = useState<AuctionIntelItem[]>([]);
  const [soldMarket, setSoldMarket] = useState<SoldMarketDemand | null>(null);
  const [soldInsight, setSoldInsight] = useState<SoldMarketInsight | null>(null);

  const [loadingSummary, setLoadingSummary] = useState(true);
  const [loadingCat, setLoadingCat] = useState(true);
  const [loadingSig, setLoadingSig] = useState(true);
  const [loadingAuc, setLoadingAuc] = useState(true);
  const [loadingSold, setLoadingSold] = useState(true);
  const [refreshingInsight, setRefreshingInsight] = useState(false);

  const [errorCat, setErrorCat] = useState<string | null>(null);
  const [errorSig, setErrorSig] = useState<string | null>(null);
  const [errorAuc, setErrorAuc] = useState<string | null>(null);
  const [errorSold, setErrorSold] = useState<string | null>(null);

  const fetchAll = useCallback(() => {
    setLoadingSummary(true);
    setLoadingCat(true);
    setLoadingSig(true);
    setLoadingAuc(true);
    setLoadingSold(true);
    setErrorCat(null);
    setErrorSig(null);
    setErrorAuc(null);
    setErrorSold(null);

    Promise.all([api.demand.soldMarket(90), api.demand.soldMarketInsights(90)])
      .then(([market, insight]) => { setSoldMarket(market); setSoldInsight(insight); })
      .catch((e: Error) => setErrorSold(e.message))
      .finally(() => setLoadingSold(false));

    api.demand.summary()
      .then(setSummary)
      .catch(() => {})
      .finally(() => setLoadingSummary(false));

    api.demand.categories()
      .then(setCategories)
      .catch((e: Error) => setErrorCat(e.message))
      .finally(() => setLoadingCat(false));

    api.demand.richSignals()
      .then(setRichSignals)
      .catch((e: Error) => setErrorSig(e.message))
      .finally(() => setLoadingSig(false));

    api.demand.auctionIntel(50)
      .then(setAuctions)
      .catch((e: Error) => setErrorAuc(e.message))
      .finally(() => setLoadingAuc(false));
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(fetchAll, 0);
    return () => window.clearTimeout(timer);
  }, [fetchAll]);

  const refreshSoldInsight = useCallback(() => {
    setRefreshingInsight(true);
    api.demand.soldMarketInsights(90, true)
      .then(setSoldInsight)
      .catch((e: Error) => setErrorSold(e.message))
      .finally(() => setRefreshingInsight(false));
  }, []);

  const tabs: { id: Tab; label: string }[] = [
    { id: "sold", label: "Sold Market" },
    { id: "categories", label: "📦 Categories" },
    { id: "signals", label: "📡 External Signals" },
    { id: "auctions", label: "⏱ Auction Intel" },
  ];

  return (
    <div className="min-h-screen bg-[#060d18] text-slate-100 px-4 py-6 md:px-8">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-[#00dc82]" />
          <h1 className="text-xl font-black text-slate-100">Demand Explorer</h1>
        </div>

        {summary && !loadingSummary && (
          <>
            <MarketHealthBadge health={summary.market_health} />
            <div className="flex gap-2 flex-wrap">
              <KpiChip label="Gems" value={summary.total_gems} color="text-[#00dc82]" />
              <KpiChip label="Gem Rate" value={fmtPct(summary.gem_rate_pct)} />
              <KpiChip label="Rising" value={`↑ ${summary.rising_count}`} color="text-[#00dc82]" />
              <KpiChip label="Falling" value={`↓ ${summary.falling_count}`} color="text-red-400" />
              {summary.hottest_category && (
                <KpiChip
                  label="Hottest"
                  value={`${summary.hottest_category.emoji} ${summary.hottest_category.name}`}
                  color="text-amber-400"
                />
              )}
            </div>
          </>
        )}

        <button
          onClick={fetchAll}
          className="ml-auto flex cursor-pointer items-center gap-1.5 px-3 py-1.5 rounded-md border border-white/10 text-slate-400 hover:text-[#00dc82] hover:border-[#00dc82]/30 transition-all text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00dc82]"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-white/8 pb-0">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px cursor-pointer border-b-2 px-4 py-2 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00dc82] ${
              tab === t.id
                ? "border-[#00dc82] text-[#00dc82]"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {tab === "sold" && (
          <SoldMarketTab data={soldMarket} insight={soldInsight} loading={loadingSold} error={errorSold} refreshingInsight={refreshingInsight} onRetry={fetchAll} onRefreshInsight={refreshSoldInsight} />
        )}
        {tab === "categories" && (
          <CategoriesTab
            categories={categories}
            loading={loadingCat}
            error={errorCat}
            onRetry={fetchAll}
          />
        )}
        {tab === "signals" && (
          <ExternalSignalsTab
            data={richSignals}
            loading={loadingSig}
            error={errorSig}
            onRetry={fetchAll}
          />
        )}
        {tab === "auctions" && (
          <AuctionIntelTab
            auctions={auctions}
            loading={loadingAuc}
            error={errorAuc}
            onRetry={fetchAll}
          />
        )}
      </div>
    </div>
  );
}
