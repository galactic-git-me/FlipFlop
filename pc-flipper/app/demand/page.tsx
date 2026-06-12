"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LabelList,
} from "recharts";
import { RefreshCw, TrendingUp, TrendingDown, Minus, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { ClassificationBadge } from "@/components/classification-badge";
import type { DemandCategory, AuctionIntelItem, DemandSummary } from "@/lib/types";

// ── Local types ───────────────────────────────────────────────────────────────

interface ExternalSignalItem {
  id?: number;
  source: string;
  topic: string;
  query: string | null;
  score: number;
  confidence: number;
  sample_size: number | null;
  signal_time: string;
  notes: string | null;
}

type Tab = "categories" | "signals" | "auctions";

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

// ── External Signals tab ──────────────────────────────────────────────────────

type SigSource = "All" | "Reddit" | "Google Trends" | "Steam";
type SigSort = "Score ↓" | "Confidence ↓" | "Date ↓";

const SOURCE_LABEL: Record<string, string> = {
  reddit: "Reddit",
  google_trends: "Google Trends",
  steam_hardware: "Steam",
};

const SOURCE_COLOR: Record<string, string> = {
  reddit: "#ff6b6b",
  google_trends: "#4fc3f7",
  steam_hardware: "#81c784",
};

function ExternalSignalsTab({ data, loading, error, onRetry }: {
  data: { summary: Record<string, { count: number; avg_score: number; avg_confidence: number }>; items: Record<string, ExternalSignalItem[]> };
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const [source, setSource] = useState<SigSource>("All");
  const [sort, setSort] = useState<SigSort>("Score ↓");

  const allItems: ExternalSignalItem[] = useMemo(() => {
    return Object.values(data.items ?? {}).flat() as ExternalSignalItem[];
  }, [data.items]);

  const filtered = useMemo(() => {
    let rows = [...allItems];
    if (source !== "All") {
      const key = source === "Reddit" ? "reddit" : source === "Google Trends" ? "google_trends" : "steam_hardware";
      rows = rows.filter((r) => r.source === key);
    }
    if (sort === "Score ↓") rows.sort((a, b) => b.score - a.score);
    else if (sort === "Confidence ↓") rows.sort((a, b) => b.confidence - a.confidence);
    else if (sort === "Date ↓") rows.sort((a, b) => new Date(b.signal_time).getTime() - new Date(a.signal_time).getTime());
    return rows;
  }, [allItems, source, sort]);

  // Build chart data: avg score per topic per source
  const chartData = useMemo(() => {
    const topicMap: Record<string, Record<string, { total: number; count: number }>> = {};
    allItems.forEach((item) => {
      if (!topicMap[item.topic]) topicMap[item.topic] = {};
      if (!topicMap[item.topic][item.source]) topicMap[item.topic][item.source] = { total: 0, count: 0 };
      topicMap[item.topic][item.source].total += item.score;
      topicMap[item.topic][item.source].count += 1;
    });
    return Object.entries(topicMap).map(([topic, sources]) => ({
      topic: topic.replace(/_/g, " ").slice(0, 18),
      reddit: sources.reddit ? Math.round(sources.reddit.total / sources.reddit.count) : 0,
      google_trends: sources.google_trends ? Math.round(sources.google_trends.total / sources.google_trends.count) : 0,
      steam_hardware: sources.steam_hardware ? Math.round(sources.steam_hardware.total / sources.steam_hardware.count) : 0,
    }));
  }, [allItems]);

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner msg={`Failed to load signals — ${error}`} onRetry={onRetry} />;
  if (!allItems.length) return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-500">
      <p className="text-sm">No external signals — click Refresh to fetch.</p>
    </div>
  );

  return (
    <div className="space-y-4">
      {/* Slicers */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Source</span>
          <Pills<SigSource>
            options={["All", "Reddit", "Google Trends", "Steam"]}
            value={source}
            onChange={setSource}
          />
        </div>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as SigSort)}
          className="ml-auto bg-[#0a1628] border border-white/10 text-slate-300 text-xs rounded-md px-2 py-1"
        >
          {(["Score ↓", "Confidence ↓", "Date ↓"] as SigSort[]).map((o) => (
            <option key={o}>{o}</option>
          ))}
        </select>
      </div>

      {/* Chart */}
      <div className="bg-[#070e1a] rounded-lg border border-white/5 p-3">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 36, left: 0 }}>
            <XAxis dataKey="topic" tick={{ fill: "#64748b", fontSize: 10 }} angle={-30} textAnchor="end" interval={0} />
            <YAxis tick={{ fill: "#64748b", fontSize: 10 }} domain={[0, 100]} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="reddit" name="Reddit" fill={SOURCE_COLOR.reddit} radius={[2, 2, 0, 0]} />
            <Bar dataKey="google_trends" name="Google Trends" fill={SOURCE_COLOR.google_trends} radius={[2, 2, 0, 0]} />
            <Bar dataKey="steam_hardware" name="Steam" fill={SOURCE_COLOR.steam_hardware} radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <div className="flex gap-4 justify-center mt-1">
          {["reddit", "google_trends", "steam_hardware"].map((s) => (
            <div key={s} className="flex items-center gap-1 text-[10px] text-slate-500">
              <div className="w-2 h-2 rounded-sm" style={{ background: SOURCE_COLOR[s] }} />
              {SOURCE_LABEL[s]}
            </div>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-white/5">
        <table className="w-full text-xs text-left">
          <thead className="bg-[#070e1a] text-slate-500 uppercase text-[10px] tracking-wide">
            <tr>
              {["Query", "Topic", "Source", "Score", "Confidence", "Samples", "Collected", "Notes"].map((h) => (
                <th key={h} className="px-3 py-2 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filtered.map((item, i) => (
              <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-3 py-2 text-slate-300 max-w-[200px] truncate" title={item.query ?? ""}>{item.query ?? "—"}</td>
                <td className="px-3 py-2">
                  <span className="px-1.5 py-0.5 rounded bg-white/5 text-slate-400 text-[10px]">
                    {item.topic.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="px-3 py-2 whitespace-nowrap" style={{ color: SOURCE_COLOR[item.source] ?? "#94a3b8" }}>
                  {SOURCE_LABEL[item.source] ?? item.source}
                </td>
                <td className="px-3 py-2 font-mono" style={{
                  color: item.score >= 60 ? "#00dc82" : item.score >= 35 ? "#f59e0b" : "#ef4444"
                }}>
                  {Math.round(item.score)}
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1.5">
                    <div className="w-12 h-1.5 rounded-full bg-white/10 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[#4fc3f7]"
                        style={{ width: `${Math.round(item.confidence * 100)}%` }}
                      />
                    </div>
                    <span className="text-slate-400 text-[10px]">{Math.round(item.confidence * 100)}%</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-slate-500">{item.sample_size ?? "—"}</td>
                <td className="px-3 py-2 text-slate-500 whitespace-nowrap">{fmtRelative(item.signal_time)}</td>
                <td className="px-3 py-2 text-slate-600 max-w-[160px] truncate" title={item.notes ?? ""}>{item.notes ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="text-center py-8 text-slate-600 text-xs">No signals match filters.</div>
        )}
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
              <LabelList dataKey="profit" position="right" style={{ fill: "#94a3b8", fontSize: 10 }} formatter={(v: number) => `£${v}`} />
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

// ── Page ──────────────────────────────────────────────────────────────────────

const EMPTY_SIGNALS = { summary: {}, items: {} };

export default function DemandPage() {
  const [tab, setTab] = useState<Tab>("categories");

  const [summary, setSummary] = useState<DemandSummary | null>(null);
  const [categories, setCategories] = useState<DemandCategory[]>([]);
  const [signals, setSignals] = useState<typeof EMPTY_SIGNALS>(EMPTY_SIGNALS);
  const [auctions, setAuctions] = useState<AuctionIntelItem[]>([]);

  const [loadingSummary, setLoadingSummary] = useState(true);
  const [loadingCat, setLoadingCat] = useState(true);
  const [loadingSig, setLoadingSig] = useState(true);
  const [loadingAuc, setLoadingAuc] = useState(true);

  const [errorCat, setErrorCat] = useState<string | null>(null);
  const [errorSig, setErrorSig] = useState<string | null>(null);
  const [errorAuc, setErrorAuc] = useState<string | null>(null);

  const fetchAll = useCallback(() => {
    setLoadingSummary(true);
    setLoadingCat(true);
    setLoadingSig(true);
    setLoadingAuc(true);
    setErrorCat(null);
    setErrorSig(null);
    setErrorAuc(null);

    api.demand.summary()
      .then(setSummary)
      .catch(() => {})
      .finally(() => setLoadingSummary(false));

    api.demand.categories()
      .then(setCategories)
      .catch((e: Error) => setErrorCat(e.message))
      .finally(() => setLoadingCat(false));

    api.demand.externalSignals()
      .then((d) => setSignals(d as typeof EMPTY_SIGNALS))
      .catch((e: Error) => setErrorSig(e.message))
      .finally(() => setLoadingSig(false));

    api.demand.auctionIntel(50)
      .then(setAuctions)
      .catch((e: Error) => setErrorAuc(e.message))
      .finally(() => setLoadingAuc(false));
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const tabs: { id: Tab; label: string }[] = [
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
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-white/10 text-slate-400 hover:text-[#00dc82] hover:border-[#00dc82]/30 transition-all text-xs"
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
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-all -mb-px ${
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
            data={signals as { summary: Record<string, { count: number; avg_score: number; avg_confidence: number }>; items: Record<string, ExternalSignalItem[]> }}
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
