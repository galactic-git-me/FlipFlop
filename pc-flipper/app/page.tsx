"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
  ResponsiveContainer, ReferenceLine, ComposedChart, Bar, Line,
} from "recharts";
import {
  TrendingUp, Gem, Zap, Clock, Bell, ArrowRight, RefreshCw,
  ChevronLeft, ChevronRight, Settings2, Check, SlidersHorizontal, Gavel,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ClassificationBadge } from "@/components/classification-badge";
import { FlippabilityScore } from "@/components/flippability-score";
import { SourceBadge } from "@/components/source-badge";
import { EmptyState } from "@/components/empty-state";
import { ScanOverlay } from "@/components/scan-overlay";
import { TraeBg } from "@/components/trae-bg";
import { SellerBadge, SELLER_TYPE_CONFIG } from "@/components/seller-badge";
import { AuctionBadge, AuctionPriceDisplay, useCountdown } from "@/components/auction-display";
import { Listing, Flip } from "@/lib/types";
import { ScanStatus, api } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import Link from "next/link";

// ── Column definitions ───────────────────────────────────────────────────────
const ALL_COLS = [
  { key: "score",    label: "Score"         },
  { key: "listing",  label: "Listing"        },
  { key: "source",   label: "Source"         },
  { key: "cpu",      label: "CPU"            },
  { key: "ram",      label: "RAM"            },
  { key: "storage",  label: "Storage"        },
  { key: "gpu",      label: "GPU"            },
  { key: "buy",      label: "Buy Price"      },
  { key: "upgrade",  label: "Upgrade Cost"   },
  { key: "resale",   label: "Resale"         },
  { key: "profit",   label: "Profit"         },
  { key: "roi",      label: "ROI %"          },
  { key: "class",    label: "Classification" },
  { key: "location", label: "Location"       },
  { key: "seen",     label: "First Seen"     },
  { key: "seller",   label: "Seller"         },
] as const;
type ColKey = (typeof ALL_COLS)[number]["key"];
const DEFAULT_COLS: ColKey[] = ["score", "listing", "source", "cpu", "gpu", "buy", "resale", "profit", "class"];

// ── Dashboard page ────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter();
  const [listings, setListings] = useState<Listing[]>([]);
  const [flips, setFlips] = useState<Flip[]>([]);
  const [stats, setStats] = useState({ total_listings: 0, gems_count: 0, avg_profit: 0 });
  const [swarms, setSwarms] = useState<{ id: string; name: string; next_run: string | null }[]>([]);
  const [gemOfDay, setGemOfDay] = useState<Listing | null>(null);
  const [gemOfWeek, setGemOfWeek] = useState<Listing | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [flippingId, setFlippingId] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Table state
  const [tablePage, setTablePage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [visibleCols, setVisibleCols] = useState<Set<ColKey>>(new Set(DEFAULT_COLS));
  const [colPickerOpen, setColPickerOpen] = useState(false);

  // PnL chart filter state
  const today = new Date().toISOString().slice(0, 10);
  const [pnlDateFrom, setPnlDateFrom] = useState("2026-05-01");
  const [pnlDateTo, setPnlDateTo] = useState(today);
  const [pnlSource, setPnlSource] = useState("all");
  const [pnlPlatform, setPnlPlatform] = useState("all");

  // Scatter chart top-N filter (0 = show all)
  const [topN, setTopN] = useState(50);

  const load = async () => {
    setLoading(true);
    try {
      // Today midnight and 7-days-ago midnight in ISO format
      const todayMidnight  = new Date(); todayMidnight.setHours(0,0,0,0);
      const weekAgoMidnight = new Date(Date.now() - 7 * 86_400_000); weekAgoMidnight.setHours(0,0,0,0);
      const todayISO  = todayMidnight.toISOString();
      const weekISO   = weekAgoMidnight.toISOString();

      const [l, s, sw, fl, godResults, gowResults] = await Promise.all([
        api.listings.list({ sort_by: "estimated_profit", sort_desc: "true", limit: "500" }) as Promise<Listing[]>,
        api.listings.stats(),
        api.swarms.list() as Promise<{ id: string; name: string; next_run: string | null }[]>,
        api.flips.list() as Promise<Flip[]>,
        // Gem of Day: top estimated_profit from today, profit > 0
        api.listings.list({
          sort_by: "estimated_profit", sort_desc: "true",
          limit: "1", min_profit: "0", first_seen_after: todayISO,
        }) as Promise<Listing[]>,
        // Gem of Week: top estimated_profit from last 7 days, profit > 0
        api.listings.list({
          sort_by: "estimated_profit", sort_desc: "true",
          limit: "1", min_profit: "0", first_seen_after: weekISO,
        }) as Promise<Listing[]>,
      ]);
      setListings(l);
      setStats(s);
      setSwarms(sw);
      setFlips(fl);
      setGemOfDay(godResults[0] ?? null);
      // Only show week gem if it differs from day gem
      const gowListing = gowResults[0] ?? null;
      setGemOfWeek(
        gowListing && godResults[0] && gowListing.id === godResults[0].id
          ? null
          : gowListing
      );
    } catch {
      // API offline — show empty state
    } finally {
      setLoading(false);
    }
  };

  const startScanPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.swarms.scanStatus();
        setScanStatus(s);
        if (!s.running) {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          setTimeout(() => { setScanStatus(null); load(); }, 3000);
        }
      } catch { }
    }, 800);
  };

  useEffect(() => {
    load();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const triggerScan = async () => {
    setTriggering(true);
    try {
      await api.swarms.trigger("flip_opportunities");
      setTimeout(startScanPolling, 300);
    } catch { } finally { setTriggering(false); }
  };

  const handleFlip = async (listing: Listing) => {
    setFlippingId(listing.id);
    try {
      await api.flips.create({ listing_id: listing.id });
      router.push("/flips");
    } catch {
      setFlippingId(null);
    }
  };

  const toggleCol = (key: ColKey) => {
    setVisibleCols(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  // ── Derived chart data ───────────────────────────────────────────────────────
  // gemOfDay / gemOfWeek are fetched directly via dedicated API calls in load()

  const gems = listings.filter(l => l.classification === "amazing_gem" || l.classification === "gem");

  // Recent gems: only amazing_gem / gem found in last 24 h, sorted newest first
  const cutoff24h = new Date(Date.now() - 24 * 3600_000).toISOString();
  const recentGems = listings
    .filter(l =>
      (l.classification === "amazing_gem" || l.classification === "gem") &&
      l.first_seen_at >= cutoff24h
    )
    .sort((a, b) => b.gem_score - a.gem_score)
    .slice(0, 10);

  // Scatter chart data — listings already sorted by gem_score desc from the API
  const chartListings = topN > 0 ? listings.slice(0, topN) : listings;
  const maxProfit = Math.max(...chartListings.map(l => l.estimated_profit ?? 0), 1);
  const scatterData = chartListings.map(l => ({ ...l, x: l.price, y: l.estimated_resale ?? 0, profit: l.estimated_profit ?? 0 }));
  const allVals = scatterData.flatMap(d => [d.x, d.y]).filter(v => v > 0);
  const axisMax = allVals.length ? Math.ceil(Math.max(...allVals) / 50) * 50 + 50 : 600;

  const roiScatterData = chartListings
    .filter(l => l.estimated_profit != null)
    .map(l => {
      const totalInvested = l.price + (l.estimated_upgrade_cost ?? 0);
      const roi = totalInvested > 0 ? ((l.estimated_profit ?? 0) / totalInvested) * 100 : 0;
      return { ...l, x: l.gem_score, y: Math.round(roi * 10) / 10, profit: l.estimated_profit ?? 0 };
    });
  const scoreMax = Math.ceil((Math.max(...roiScatterData.map(d => d.x), 80) + 10) / 10) * 10;
  const roiVals = roiScatterData.map(d => d.y);
  const roiMin = Math.floor((Math.min(...roiVals, -10)) / 10) * 10;
  const roiMax = Math.ceil((Math.max(...roiVals, 50)) / 10) * 10;

  // ── PnL chart data ───────────────────────────────────────────────────────────
  const allSources  = [...new Set(flips.map(f => f.listing?.source_name).filter((s): s is string => !!s))];
  const allPlatforms = [...new Set(flips.map(f => f.sale_platform).filter((p): p is string => !!p))];

  const soldFiltered = flips
    .filter(f => f.stage === "sold" && f.actual_profit != null && f.sold_at)
    .filter(f => { const d = f.sold_at!.slice(0, 10); return d >= pnlDateFrom && d <= pnlDateTo; })
    .filter(f => pnlSource === "all" || f.listing?.source_name === pnlSource)
    .filter(f => pnlPlatform === "all" || f.sale_platform === pnlPlatform)
    .sort((a, b) => a.sold_at!.localeCompare(b.sold_at!));

  let cumPnl = 0;
  const pnlData = soldFiltered.map(f => {
    cumPnl += f.actual_profit ?? 0;
    return {
      date: f.sold_at!.slice(0, 10),
      profit: Math.round(f.actual_profit ?? 0),
      cumulative: Math.round(cumPnl),
      label: `Flip #${f.id}`,
    };
  });
  const pnlYMin = Math.min(...pnlData.map(d => Math.min(d.profit, d.cumulative)), 0);
  const pnlYMax = Math.max(...pnlData.map(d => Math.max(d.profit, d.cumulative)), 100);

  // ── Table pagination ─────────────────────────────────────────────────────────
  const totalPages = Math.ceil(listings.length / pageSize);
  const pagedListings = listings.slice((tablePage - 1) * pageSize, tablePage * pageSize);

  // ── Loading ──────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <>
        <TraeBg />
        <div className="flex items-center justify-center h-full">
          <div className="flex items-center gap-3 text-slate-500 text-sm">
            <RefreshCw className="w-4 h-4 animate-spin" /> Loading live data…
          </div>
        </div>
      </>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <TraeBg />
      {scanStatus && (scanStatus.running || (scanStatus.sites && scanStatus.sites.length > 0)) && (
        <ScanOverlay status={scanStatus} />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">Live market intelligence</p>
        </div>
        <div className="flex items-center gap-3">
          {gems.length > 0 && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#00dc82]/10 border border-[#00dc82]/25 new-badge-pulse">
              <Bell className="w-3.5 h-3.5 text-[#00dc82]" />
              <span className="text-xs font-semibold text-[#00dc82]">{gems.length} gem{gems.length !== 1 ? "s" : ""} in database</span>
            </div>
          )}
          <Button variant="secondary" size="sm" onClick={triggerScan} disabled={triggering}>
            <RefreshCw className={`w-3.5 h-3.5 ${triggering ? "animate-spin" : ""}`} />
            {triggering ? "Scanning…" : "Scan Now"}
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Listings Tracked" value={stats.total_listings.toString()} sub="in database" icon={<Gem className="w-4 h-4" />} color="text-slate-400" />
        <StatCard label="Gems Found" value={stats.gems_count.toString()} sub="buy signals" icon={<Gem className="w-4 h-4" />} color="text-[#00dc82]" accent />
        <StatCard label="Avg Profit" value={formatCurrency(stats.avg_profit)} sub="per gem" icon={<TrendingUp className="w-4 h-4" />} color="text-[#00dc82]" accent />
        <StatCard label="Next Scan" value={swarms[0]?.next_run ? new Date(swarms[0].next_run).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "—"} sub="flip swarm" icon={<Zap className="w-4 h-4" />} color="text-yellow-400" />
      </div>

      {listings.length === 0 ? (
        <EmptyState
          icon={Gem}
          title="No listings yet"
          description='Click "Scan Now" above to run the first sweep — Hermes will find gems from your configured sources.'
          action={{ label: "Run First Scan", onClick: triggerScan }}
        />
      ) : (
        <>
          {/* ── Gem of the Day / Gem of the Week ──────────────────────────────── */}
          {(gemOfDay || gemOfWeek) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {gemOfDay && <GemOfPeriod period="day" listing={gemOfDay} onFlip={handleFlip} flippingId={flippingId} />}
              {gemOfWeek && <GemOfPeriod period="week" listing={gemOfWeek} onFlip={handleFlip} flippingId={flippingId} />}
            </div>
          )}

          {/* ── PnL Chart ─────────────────────────────────────────────────────── */}
          <Card>
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="w-3.5 h-3.5 text-[#00dc82]" />
                  Profit &amp; Loss — cumulative PnL
                </CardTitle>
                {/* Slicer bar */}
                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex items-center gap-1.5">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-slate-500" />
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider">Filters</span>
                  </div>
                  <input
                    type="date"
                    value={pnlDateFrom}
                    onChange={e => setPnlDateFrom(e.target.value)}
                    className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-[#00dc82]/50"
                  />
                  <span className="text-slate-600 text-xs">→</span>
                  <input
                    type="date"
                    value={pnlDateTo}
                    onChange={e => setPnlDateTo(e.target.value)}
                    className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-[#00dc82]/50"
                  />
                  <select
                    value={pnlSource}
                    onChange={e => setPnlSource(e.target.value)}
                    className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-[#00dc82]/50"
                  >
                    <option value="all">All sources</option>
                    {allSources.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  {allPlatforms.length > 0 && (
                    <select
                      value={pnlPlatform}
                      onChange={e => setPnlPlatform(e.target.value)}
                      className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-[#00dc82]/50"
                    >
                      <option value="all">All platforms</option>
                      {allPlatforms.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {pnlData.length === 0 ? (
                <div className="flex items-center justify-center h-48 text-slate-600 text-sm">
                  No sold flips in this date range yet — PnL will appear as you log sales.
                </div>
              ) : (
                <div style={{ width: "100%", height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={pnlData} margin={{ top: 10, right: 60, bottom: 28, left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: "#64748b", fontSize: 11 }}
                        axisLine={{ stroke: "#1e2d45" }}
                        tickLine={false}
                        label={{ value: "Sale date", position: "insideBottom", offset: -10, fill: "#475569", fontSize: 11 }}
                      />
                      {/* Left Y axis — individual flip profit (bars) */}
                      <YAxis
                        yAxisId="left"
                        orientation="left"
                        tickFormatter={v => `£${v}`}
                        tick={{ fill: "#64748b", fontSize: 11 }}
                        axisLine={{ stroke: "#1e2d45" }}
                        tickLine={false}
                        domain={[Math.min(pnlYMin, 0), pnlYMax]}
                        label={{ value: "Flip profit (£)", angle: -90, position: "insideLeft", offset: 16, fill: "#475569", fontSize: 11 }}
                      />
                      {/* Right Y axis — cumulative PnL (line) */}
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        tickFormatter={v => `£${v}`}
                        tick={{ fill: "#64748b", fontSize: 11 }}
                        axisLine={{ stroke: "#1e2d45" }}
                        tickLine={false}
                        label={{ value: "Cumulative PnL (£)", angle: 90, position: "insideRight", offset: 16, fill: "#475569", fontSize: 11 }}
                      />
                      <Tooltip content={<PnlTooltip />} />
                      {/* Break-even reference line */}
                      <ReferenceLine yAxisId="left" y={0} stroke="#475569" strokeDasharray="4 4" strokeOpacity={0.5} />
                      {/* Individual flip profits as bars */}
                      <Bar
                        yAxisId="left"
                        dataKey="profit"
                        name="Flip profit"
                        radius={[3, 3, 0, 0]}
                        maxBarSize={40}
                      >
                        {pnlData.map((entry, i) => (
                          <Cell key={i} fill={entry.profit >= 0 ? "#00dc82" : "#ef4444"} fillOpacity={0.85} />
                        ))}
                      </Bar>
                      {/* Cumulative PnL as a line */}
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="cumulative"
                        name="Cumulative PnL"
                        stroke="#60a5fa"
                        strokeWidth={2.5}
                        dot={false}
                        activeDot={{ r: 4, fill: "#60a5fa", stroke: "#1e2d45", strokeWidth: 2 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              )}
              {/* Legend */}
              <div className="flex items-center gap-4 mt-2 px-2">
                <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-sm bg-[#00dc82]" /><span className="text-[10px] text-slate-500">Flip profit (bars · left axis)</span></div>
                <div className="flex items-center gap-1.5"><div className="w-4 h-0.5 bg-[#60a5fa]" /><span className="text-[10px] text-slate-500">Cumulative PnL (line · right axis)</span></div>
                <div className="ml-auto text-[10px] text-slate-600">{pnlData.length} flips · total {formatCurrency(cumPnl)}</div>
              </div>
            </CardContent>
          </Card>

          {/* ── Scatter charts ─────────────────────────────────────────────────── */}
          {/* Shared top-N control */}
          <div className="flex items-center gap-2 justify-end -mb-2">
            <span className="text-[11px] text-slate-500">Show top</span>
            <input
              type="number"
              min={1}
              max={listings.length}
              value={topN}
              onChange={e => setTopN(Math.max(1, Math.min(listings.length, Number(e.target.value) || 1)))}
              className="w-16 bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-[#00dc82]/50 text-center"
            />
            <span className="text-[11px] text-slate-500">by score (of {listings.length})</span>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">

            {/* Chart 1: Buy price vs resale */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Buy price vs resale — bubble = profit</CardTitle>
                <p className="text-[10px] text-slate-600 mt-0.5">🟢 &gt;£100 profit · 🟡 £0–100 · 🔴 loss · click bubble for detail</p>
              </CardHeader>
              <CardContent>
                <div style={{ width: "100%", height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 10, right: 20, bottom: 28, left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" />
                      <XAxis
                        dataKey="x"
                        name="Cost"
                        type="number"
                        domain={[0, axisMax]}
                        tickFormatter={v => `£${v}`}
                        tick={{ fill: "#64748b", fontSize: 11 }}
                        axisLine={{ stroke: "#1e2d45" }}
                        tickLine={false}
                        label={{ value: "Buy Price (£)", position: "insideBottom", offset: -10, fill: "#475569", fontSize: 11 }}
                      />
                      <YAxis
                        dataKey="y"
                        name="Resale"
                        type="number"
                        domain={[0, axisMax]}
                        tickFormatter={v => `£${v}`}
                        tick={{ fill: "#64748b", fontSize: 11 }}
                        axisLine={{ stroke: "#1e2d45" }}
                        tickLine={false}
                        label={{ value: "Resale after upgrades (£)", angle: -90, position: "insideLeft", offset: 18, fill: "#475569", fontSize: 11 }}
                      />
                      <Tooltip
                        content={<ScatterTooltip />}
                        trigger="click"
                        wrapperStyle={{ pointerEvents: "auto", zIndex: 50 }}
                      />
                      <ReferenceLine
                        segment={[{ x: 0, y: 0 }, { x: axisMax, y: axisMax }] as const}
                        stroke="#475569"
                        strokeDasharray="4 4"
                        strokeOpacity={0.4}
                      />
                      <Scatter
                        data={scatterData}
                        shape={(props: { cx?: number; cy?: number; payload?: Listing & { profit: number } }) => {
                          const { cx = 0, cy = 0, payload } = props;
                          const profit = payload?.profit ?? 0;
                          const r = Math.max(5, Math.min(18, (Math.abs(profit) / maxProfit) * 18));
                          const fill = profit > 100 ? "#00dc82" : profit > 0 ? "#f59e0b" : "#ef4444";
                          return (
                            <circle cx={cx} cy={cy} r={r}
                              fill={fill} fillOpacity={0.8}
                              stroke={fill} strokeWidth={1.5} strokeOpacity={0.5}
                              style={{ cursor: "pointer" }}
                            />
                          );
                        }}
                      />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Chart 2: Flippability score vs ROI% */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Flippability score vs ROI% — bubble = profit</CardTitle>
                <p className="text-[10px] text-slate-600 mt-0.5">🟢 &gt;£100 profit · 🟡 £0–100 · 🔴 loss · click bubble for detail</p>
              </CardHeader>
              <CardContent>
                <div style={{ width: "100%", height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 10, right: 20, bottom: 28, left: 16 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" />
                      <XAxis
                        dataKey="x"
                        name="Score"
                        type="number"
                        domain={[0, scoreMax]}
                        tick={{ fill: "#64748b", fontSize: 11 }}
                        axisLine={{ stroke: "#1e2d45" }}
                        tickLine={false}
                        label={{ value: "Flippability Score", position: "insideBottom", offset: -10, fill: "#475569", fontSize: 11 }}
                      />
                      <YAxis
                        dataKey="y"
                        name="ROI"
                        type="number"
                        domain={[roiMin, roiMax]}
                        tickFormatter={v => `${v}%`}
                        tick={{ fill: "#64748b", fontSize: 11 }}
                        axisLine={{ stroke: "#1e2d45" }}
                        tickLine={false}
                        label={{ value: "ROI %", angle: -90, position: "insideLeft", offset: 14, fill: "#475569", fontSize: 11 }}
                      />
                      <Tooltip
                        content={<ScatterTooltip />}
                        trigger="click"
                        wrapperStyle={{ pointerEvents: "auto", zIndex: 50 }}
                      />
                      <ReferenceLine y={0} stroke="#475569" strokeDasharray="4 4" strokeOpacity={0.5} />
                      <Scatter
                        data={roiScatterData}
                        shape={(props: { cx?: number; cy?: number; payload?: Listing & { y: number; profit: number } }) => {
                          const { cx = 0, cy = 0, payload } = props;
                          const profit = payload?.profit ?? 0;
                          const r = Math.max(5, Math.min(18, (Math.abs(profit) / maxProfit) * 18));
                          const fill = profit > 100 ? "#00dc82" : profit > 0 ? "#f59e0b" : "#ef4444";
                          return (
                            <circle cx={cx} cy={cy} r={r}
                              fill={fill} fillOpacity={0.8}
                              stroke={fill} strokeWidth={1.5} strokeOpacity={0.5}
                              style={{ cursor: "pointer" }}
                            />
                          );
                        }}
                      />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Recent Gems — last 24 h gems/amazing_gems only */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Clock className="w-3.5 h-3.5 text-[#00dc82]" /> Gems Found (last 24 h)
                {recentGems.length > 0
                  ? <Badge variant="success">{recentGems.length}</Badge>
                  : <span className="text-[11px] text-slate-600 font-normal">— none yet, run a scan</span>
                }
              </h2>
            </div>
            {recentGems.length > 0 ? (
              <div className="flex gap-3 overflow-x-auto pb-2" style={{ scrollbarWidth: "thin" }}>
                {recentGems.map(l => (
                  <RecentCard key={l.id} listing={l} />
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-white/[0.07] px-6 py-5 text-center text-slate-600 text-sm">
                No gem or amazing-gem listings found in the last 24 hours. Trigger a scan to refresh.
              </div>
            )}
          </div>

          {/* ── All Listings Table — paginated, customisable columns ──────────── */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="flex items-center gap-2">
                  <Gem className="w-3.5 h-3.5 text-[#00dc82]" />
                  All Listings
                  <span className="text-xs font-normal text-slate-500">({listings.length} total · sorted by flippability)</span>
                </CardTitle>
                <div className="flex items-center gap-2">
                  {/* Column picker */}
                  <div className="relative">
                    <Button
                      variant="ghost" size="sm"
                      onClick={() => setColPickerOpen(o => !o)}
                      className={colPickerOpen ? "text-[#00dc82]" : ""}
                    >
                      <Settings2 className="w-3.5 h-3.5" /> Columns
                    </Button>
                    {colPickerOpen && (
                      <div className="absolute right-0 top-full mt-1 z-50 bg-[#0d1a2a] border border-white/10 rounded-xl shadow-2xl p-3 min-w-44">
                        <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2 px-1">Show / hide columns</p>
                        {ALL_COLS.map(col => (
                          <button
                            key={col.key}
                            onClick={() => toggleCol(col.key)}
                            className="w-full flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-white/[0.05] transition-colors text-left"
                          >
                            <div className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors
                              ${visibleCols.has(col.key) ? "bg-[#00dc82]/20 border-[#00dc82]/60" : "border-white/20"}`}>
                              {visibleCols.has(col.key) && <Check className="w-2.5 h-2.5 text-[#00dc82]" />}
                            </div>
                            <span className="text-xs text-slate-300">{col.label}</span>
                          </button>
                        ))}
                        <div className="border-t border-white/10 mt-2 pt-2 flex gap-1">
                          <button
                            onClick={() => setVisibleCols(new Set(DEFAULT_COLS))}
                            className="flex-1 text-[10px] text-slate-500 hover:text-slate-300 py-1 transition-colors"
                          >
                            Reset
                          </button>
                          <button
                            onClick={() => setVisibleCols(new Set(ALL_COLS.map(c => c.key)))}
                            className="flex-1 text-[10px] text-slate-500 hover:text-slate-300 py-1 transition-colors"
                          >
                            All
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                  {/* Page size selector */}
                  <select
                    value={pageSize}
                    onChange={e => { setPageSize(Number(e.target.value)); setTablePage(1); }}
                    className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-400 focus:outline-none focus:border-[#00dc82]/50"
                  >
                    {[10, 20, 50, 100].map(n => <option key={n} value={n}>{n} / page</option>)}
                  </select>
                  <Link href="/opportunities">
                    <Button variant="ghost" size="sm">View opportunities <ArrowRight className="w-3 h-3" /></Button>
                  </Link>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {/* Click outside to close col picker */}
              {colPickerOpen && (
                <div className="fixed inset-0 z-40" onClick={() => setColPickerOpen(false)} />
              )}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      {visibleCols.has("score")    && <Th>Score</Th>}
                      {visibleCols.has("listing")  && <Th>Listing</Th>}
                      {visibleCols.has("source")   && <Th>Source</Th>}
                      {visibleCols.has("cpu")      && <Th>CPU</Th>}
                      {visibleCols.has("ram")      && <Th>RAM</Th>}
                      {visibleCols.has("storage")  && <Th>Storage</Th>}
                      {visibleCols.has("gpu")      && <Th>GPU</Th>}
                      {visibleCols.has("buy")      && <Th>Buy</Th>}
                      {visibleCols.has("upgrade")  && <Th>Upgrade</Th>}
                      {visibleCols.has("resale")   && <Th>Resale</Th>}
                      {visibleCols.has("profit")   && <Th>Profit</Th>}
                      {visibleCols.has("roi")      && <Th>ROI%</Th>}
                      {visibleCols.has("class")    && <Th>Class.</Th>}
                      {visibleCols.has("location") && <Th>Location</Th>}
                      {visibleCols.has("seen")     && <Th>Seen</Th>}
                      {visibleCols.has("seller")   && <Th>Seller</Th>}
                      <Th>Action</Th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {pagedListings.map(l => {
                      const roi = (l.price + (l.estimated_upgrade_cost ?? 0)) > 0
                        ? ((l.estimated_profit ?? 0) / (l.price + (l.estimated_upgrade_cost ?? 0))) * 100
                        : 0;
                      return (
                        <tr key={l.id} className="hover:bg-white/[0.02] transition-colors group">
                          {visibleCols.has("score") && (
                            <td className="px-4 py-3 pl-5">
                              <FlippabilityScore score={l.gem_score} size="sm" />
                            </td>
                          )}
                          {visibleCols.has("listing") && (
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-lg overflow-hidden flex-shrink-0 bg-[#080f1a]">
                                  {l.image_urls[0] ? (
                                    <img src={l.image_urls[0]} alt="" className="w-full h-full object-contain" loading="lazy" />
                                  ) : (
                                    <div className="w-full h-full flex items-center justify-center opacity-20">
                                      <Gem className="w-4 h-4 text-slate-400" />
                                    </div>
                                  )}
                                </div>
                                <div className="min-w-0">
                                  <a href={l.url} target="_blank" rel="noopener noreferrer"
                                    className="text-xs text-slate-200 font-medium line-clamp-1 max-w-44 hover:text-[#00dc82] transition-colors">
                                    {l.title}
                                  </a>
                                  <p className="text-[10px] text-slate-500 mt-0.5">
                                    {l.listed_at
                                      ? <>Listed {formatRelativeTime(new Date(l.listed_at))}</>
                                      : <>Seen {formatRelativeTime(new Date(l.first_seen_at))}</>
                                    }
                                  </p>
                                  <div className="flex flex-wrap items-center gap-1 mt-0.5">
                                    <AuctionBadge listing={l} />
                                    <SellerBadge listing={l} />
                                  </div>
                                </div>
                              </div>
                            </td>
                          )}
                          {visibleCols.has("source") && (
                            <td className="px-4 py-3">
                              <SourceBadge sourceName={l.source_name} url={l.url} />
                            </td>
                          )}
                          {visibleCols.has("cpu") && (
                            <td className="px-4 py-3">
                              <span className="text-xs text-slate-400 font-mono">{l.cpu ?? <span className="text-slate-700">—</span>}</span>
                            </td>
                          )}
                          {visibleCols.has("ram") && (
                            <td className="px-4 py-3">
                              <span className="text-xs text-slate-400">{l.ram_gb ? `${l.ram_gb}GB ${l.ram_type ?? ""}` : <span className="text-slate-700">—</span>}</span>
                            </td>
                          )}
                          {visibleCols.has("storage") && (
                            <td className="px-4 py-3">
                              <span className="text-xs text-slate-400">{l.storage_gb ? `${l.storage_gb}GB ${l.storage_type?.toUpperCase() ?? ""}` : <span className="text-slate-700">—</span>}</span>
                            </td>
                          )}
                          {visibleCols.has("gpu") && (
                            <td className="px-4 py-3">
                              <span className="text-xs text-slate-400">{l.gpu ?? <span className="text-slate-700 italic text-[10px]">No GPU</span>}</span>
                            </td>
                          )}
                          {visibleCols.has("buy") && (
                            <td className="px-4 py-3">
                              <AuctionPriceDisplay listing={l} />
                            </td>
                          )}
                          {visibleCols.has("upgrade") && (
                            <td className="px-4 py-3">
                              <span className="text-xs text-slate-400">{l.estimated_upgrade_cost != null ? formatCurrency(l.estimated_upgrade_cost) : <span className="text-slate-700">—</span>}</span>
                            </td>
                          )}
                          {visibleCols.has("resale") && (
                            <td className="px-4 py-3">
                              <span className="text-sm text-slate-300">{formatCurrency(l.estimated_resale ?? 0)}</span>
                              {l.resale_low != null && l.resale_high != null && l.resale_low !== l.resale_high && (
                                <div className="text-[10px] text-slate-600 mt-0.5">{formatCurrency(l.resale_low)}–{formatCurrency(l.resale_high)}</div>
                              )}
                              {(l.resale_comp_count ?? 0) > 0
                                ? <div className="text-[9px] text-[#00dc82]/60 mt-0.5">{l.resale_comp_count} comps</div>
                                : <div className="text-[9px] text-slate-700 mt-0.5">est.</div>
                              }
                            </td>
                          )}
                          {visibleCols.has("profit") && (
                            <td className="px-4 py-3">
                              <span className={`text-sm font-bold ${(l.estimated_profit ?? 0) > 0 ? "text-[#00dc82]" : "text-red-400"}`}>
                                {(l.estimated_profit ?? 0) > 0 ? "+" : ""}{formatCurrency(l.estimated_profit ?? 0)}
                              </span>
                            </td>
                          )}
                          {visibleCols.has("roi") && (
                            <td className="px-4 py-3">
                              <span className={`text-xs font-semibold ${roi >= 30 ? "text-[#00dc82]" : roi >= 0 ? "text-yellow-400" : "text-red-400"}`}>
                                {roi >= 0 ? "+" : ""}{roi.toFixed(1)}%
                              </span>
                            </td>
                          )}
                          {visibleCols.has("class") && (
                            <td className="px-4 py-3"><ClassificationBadge classification={l.classification} /></td>
                          )}
                          {visibleCols.has("location") && (
                            <td className="px-4 py-3">
                              <span className="text-xs text-slate-500">{l.location ?? <span className="text-slate-700">—</span>}</span>
                            </td>
                          )}
                          {visibleCols.has("seen") && (
                            <td className="px-4 py-3">
                              <div className="text-[10px] text-slate-500">
                                {l.listed_at
                                  ? <><span className="text-slate-600">Listed</span><br />{formatRelativeTime(new Date(l.listed_at))}</>
                                  : <><span className="text-slate-600">Seen</span><br />{formatRelativeTime(new Date(l.first_seen_at))}</>
                                }
                              </div>
                            </td>
                          )}
                          {visibleCols.has("seller") && (
                            <td className="px-4 py-3">
                              {l.seller_name && (
                                <div className="text-[10px] text-slate-400 font-medium truncate max-w-24" title={l.seller_name}>
                                  {l.seller_name}
                                </div>
                              )}
                              <SellerBadge listing={l} />
                            </td>
                          )}
                          <td className="px-4 py-3 pr-5">
                            <Button
                              variant="primary" size="sm"
                              disabled={flippingId === l.id}
                              onClick={() => handleFlip(l)}
                            >
                              {flippingId === l.id
                                ? <RefreshCw className="w-3 h-3 animate-spin" />
                                : <Zap className="w-3 h-3" />}
                              Flip
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination bar */}
              <div className="flex items-center justify-between px-5 py-3 border-t border-white/[0.06]">
                <span className="text-xs text-slate-500">
                  Showing {(tablePage - 1) * pageSize + 1}–{Math.min(tablePage * pageSize, listings.length)} of {listings.length}
                </span>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost" size="sm"
                    disabled={tablePage === 1}
                    onClick={() => setTablePage(p => Math.max(1, p - 1))}
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </Button>
                  {/* Page number buttons — show up to 7, with ellipsis */}
                  {Array.from({ length: totalPages }, (_, i) => i + 1)
                    .filter(p => p === 1 || p === totalPages || Math.abs(p - tablePage) <= 2)
                    .reduce<(number | "…")[]>((acc, p, i, arr) => {
                      if (i > 0 && (p as number) - (arr[i - 1] as number) > 1) acc.push("…");
                      acc.push(p);
                      return acc;
                    }, [])
                    .map((p, i) =>
                      p === "…"
                        ? <span key={`ellipsis-${i}`} className="px-1.5 text-xs text-slate-600">…</span>
                        : (
                          <button
                            key={p}
                            onClick={() => setTablePage(p as number)}
                            className={`w-7 h-7 rounded-lg text-xs transition-colors
                              ${tablePage === p ? "bg-[#00dc82]/20 text-[#00dc82] font-semibold" : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"}`}
                          >
                            {p}
                          </button>
                        )
                    )}
                  <Button
                    variant="ghost" size="sm"
                    disabled={tablePage === totalPages}
                    onClick={() => setTablePage(p => Math.min(totalPages, p + 1))}
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

// ── Auction helpers ── (imported from @/components/auction-display) ──────────
// ── Seller badge ── (imported from @/components/seller-badge) ────────────────

// ── Gem of the Day / Gem of the Week card ────────────────────────────────────
function GemOfPeriod({
  period, listing: l, onFlip, flippingId,
}: {
  period: "day" | "week";
  listing: Listing;
  onFlip: (l: Listing) => void;
  flippingId: number | null;
}) {
  const countdown = useCountdown(l.listing_ends_at);
  const profit = l.estimated_profit ?? 0;
  const specs = [
    l.cpu ? l.cpu.replace(/Intel\s+|AMD\s+/i, "") : null,
    l.ram_gb  ? `${l.ram_gb}GB ${l.ram_type ?? "RAM"}` : null,
    l.storage_gb ? `${l.storage_gb}GB ${l.storage_type?.toUpperCase() ?? "SSD"}` : null,
    l.gpu ?? null,
  ].filter(Boolean) as string[];

  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-[#00dc82]/30 bg-gradient-to-br from-[#00dc82]/[0.06] to-[#0d1a2a]"
      style={{ boxShadow: "0 0 40px rgba(0,220,130,0.08), inset 0 0 0 1px rgba(0,220,130,0.12)" }}
    >
      {/* Glowing corner accent */}
      <div className="absolute top-0 right-0 w-40 h-40 bg-[#00dc82]/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative p-4 flex gap-4">
        {/* Image */}
        <div className="flex-shrink-0 w-24 h-24 rounded-xl overflow-hidden bg-[#0a1119]">
          {l.image_urls?.[0] ? (
            <img src={l.image_urls[0]} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Gem className="w-8 h-8 text-[#00dc82]/30" />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Period label */}
          <div className="flex items-center gap-2 mb-1.5">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#00dc82]/15 border border-[#00dc82]/30">
              <Gem className="w-3 h-3 text-[#00dc82]" />
              <span className="text-[10px] font-bold text-[#00dc82] uppercase tracking-wider">
                Gem of the {period === "day" ? "Day" : "Week"}
              </span>
            </div>
            {/* Score badge */}
            <div className="text-[10px] font-bold text-slate-400">
              Score <span className="text-[#00dc82]">{l.gem_score.toFixed(0)}</span>
            </div>
          </div>

          {/* Title */}
          <a href={l.url} target="_blank" rel="noopener noreferrer"
            className="text-sm font-semibold text-slate-100 line-clamp-1 hover:text-[#00dc82] transition-colors block">
            {l.title}
          </a>

          {/* Spec chips */}
          <div className="flex flex-wrap gap-1 mt-1.5">
            {specs.map((s, i) => (
              <span key={i} className="text-[10px] text-slate-400 bg-white/[0.05] border border-white/[0.06] rounded-md px-1.5 py-0.5 leading-none">
                {s}
              </span>
            ))}
            {l.listing_type === "auction" && countdown && (
              <span className="text-[10px] text-amber-400 bg-amber-400/10 border border-amber-400/25 rounded-md px-1.5 py-0.5 leading-none flex items-center gap-1">
                <Gavel className="w-2.5 h-2.5" />
                {countdown === "Ended" ? "Ended" : `${countdown} left`}
              </span>
            )}
          </div>
        </div>

        {/* Right side — financials + action */}
        <div className="flex-shrink-0 flex flex-col items-end justify-between">
          <div className="text-right">
            <AuctionPriceDisplay listing={l} />
            <div className={`text-sm font-bold mt-0.5 ${profit > 0 ? "text-[#00dc82]" : "text-red-400"}`}>
              {profit > 0 ? "+" : ""}{formatCurrency(profit)} profit
            </div>
            {l.resale_low != null && l.resale_high != null && l.resale_low !== l.resale_high && (
              <div className="text-[9px] text-slate-600">
                {formatCurrency(l.resale_low)}–{formatCurrency(l.resale_high)}
              </div>
            )}
          </div>
          <Button
            variant="primary" size="sm"
            disabled={flippingId === l.id}
            onClick={() => onFlip(l)}
          >
            {flippingId === l.id
              ? <RefreshCw className="w-3 h-3 animate-spin" />
              : <Zap className="w-3 h-3" />}
            Flip it
          </Button>
        </div>
      </div>

      {/* Source + classification + seller strip at bottom */}
      <div className="px-4 pb-3 flex items-center gap-2 flex-wrap">
        <SourceBadge sourceName={l.source_name} url={l.url} />
        <ClassificationBadge classification={l.classification} />
        {l.seller_type && <SellerBadge listing={l} />}
        <span className="ml-auto text-[10px] text-slate-600">
          {l.listed_at
            ? <>listed {formatRelativeTime(new Date(l.listed_at))}</>
            : <>found {formatRelativeTime(new Date(l.first_seen_at))}</>
          }
        </span>
      </div>
    </div>
  );
}

// ── Helper components ─────────────────────────────────────────────────────────
function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 uppercase tracking-wider whitespace-nowrap first:pl-5 last:pr-5">
      {children}
    </th>
  );
}

// ── PnL Tooltip ───────────────────────────────────────────────────────────────
function PnlTooltip({ active, payload, label }: { active?: boolean; payload?: { payload: { date: string; profit: number; cumulative: number; label: string } }[]; label?: string }) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-xl p-3 text-xs shadow-2xl" style={{ background: "rgba(8,15,26,0.97)", border: "1px solid rgba(255,255,255,0.1)" }}>
      <p className="text-slate-200 font-semibold mb-1.5">{d.date} · {d.label}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-6">
          <span className="text-slate-400 font-medium">Flip profit</span>
          <span className={d.profit > 100 ? "text-[#00dc82] font-bold" : d.profit > 0 ? "text-amber-400 font-bold" : "text-red-400 font-bold"}>
            {d.profit >= 0 ? "+" : ""}{formatCurrency(d.profit)}
          </span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="text-slate-400 font-medium">Cumulative PnL</span>
          <span className={d.cumulative >= 0 ? "text-[#60a5fa] font-bold" : "text-red-400 font-bold"}>
            {d.cumulative >= 0 ? "+" : ""}{formatCurrency(d.cumulative)}
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Waterfall mini-chart ──────────────────────────────────────────────────────
const FC = {
  GPU_COST:    185,
  SSD_COST:     65,
  PSU_COST:     50,
  RAM_COST:     65,
  CASE_COST:    70,
  GPU_RESALE:  240,
  SSD_RESALE:   70,
  RAM_RESALE:   60,
  CASE_PREMIUM: 140,
  PRESENTATION:  75,
  FEE: 0.127,
} as const;

function WaterfallMini({ d }: { d: Listing & { profit: number } }) {
  const resale = d.estimated_resale ?? 0;
  const needsGpu = !d.gpu;
  const needsSsd = !d.storage_gb;
  const needsPsu = !d.has_psu;
  const needsRam = !d.ram_gb || d.ram_gb < 32;

  const gpuAdd  = needsGpu ? FC.GPU_RESALE  : 0;
  const ramAdd  = needsRam ? FC.RAM_RESALE  : 0;
  const ssdAdd  = needsSsd ? FC.SSD_RESALE  : 0;
  const cpuBase = resale - FC.CASE_PREMIUM - FC.PRESENTATION - gpuAdd - ramAdd - ssdAdd;

  const fees        = Math.round(resale * FC.FEE);
  const upgradeCost = (needsGpu ? FC.GPU_COST : 0) + (needsRam ? FC.RAM_COST : 0)
                    + (needsSsd ? FC.SSD_COST : 0) + (needsPsu ? FC.PSU_COST : 0) + FC.CASE_COST;
  const totalCost   = d.price + upgradeCost + fees;
  const profit      = d.estimated_profit ?? Math.round(resale - totalCost);

  const LW = 78, CW = 88, VW = 50;
  const W  = LW + CW + VW;
  const RH = 14, BH = 8;
  const scale = resale > 0 ? CW / resale : 1;
  const bx = (v: number) => LW + Math.max(Math.abs(v) * scale, 1.5);

  type RowKind = "base" | "resale_add" | "buy" | "cost" | "fee";
  const colour: Record<RowKind, string> = {
    base: "#60a5fa", resale_add: "#34d399", buy: "#f87171", cost: "#fb923c", fee: "#94a3b8",
  };

  type BarRow = { label: string; value: number; kind: RowKind };
  const valueRows: BarRow[] = [
    { label: "CPU/chassis tier", value: cpuBase,          kind: "base"       },
    ...(needsGpu ? [{ label: "GPU → resale",  value: gpuAdd,   kind: "resale_add" as RowKind }] : []),
    ...(needsRam ? [{ label: "RAM → resale",  value: ramAdd,   kind: "resale_add" as RowKind }] : []),
    ...(needsSsd ? [{ label: "SSD → resale",  value: ssdAdd,   kind: "resale_add" as RowKind }] : []),
    { label: "Case (2×)",        value: FC.CASE_PREMIUM, kind: "resale_add" },
    { label: "Presentation",     value: FC.PRESENTATION, kind: "resale_add" },
  ];
  const costRows: BarRow[] = [
    { label: "Buy price",       value: d.price,         kind: "buy"  },
    ...(needsGpu ? [{ label: "GPU (RTX 3060)", value: FC.GPU_COST, kind: "cost" as RowKind }] : []),
    ...(needsRam ? [{ label: "RAM (32 GB)",    value: FC.RAM_COST, kind: "cost" as RowKind }] : []),
    ...(needsSsd ? [{ label: "SSD (1 TB)",     value: FC.SSD_COST, kind: "cost" as RowKind }] : []),
    ...(needsPsu ? [{ label: "PSU (650 W)",    value: FC.PSU_COST, kind: "cost" as RowKind }] : []),
    { label: "Case",            value: FC.CASE_COST,    kind: "cost" },
    { label: "eBay fees",       value: fees,            kind: "fee"  },
  ];

  const sectionLabelH = 13, dividerH = 14, totalRowH = 14, reconcileH = 12;
  const H = sectionLabelH + valueRows.length * RH + dividerH
          + sectionLabelH + costRows.length  * RH + dividerH
          + totalRowH + reconcileH + 2;

  const renderRow = (row: BarRow, y: number) => {
    const barY = y + Math.floor((RH - BH) / 2);
    return (
      <g key={row.label}>
        <text x={LW - 4} y={barY + 6} textAnchor="end" fontSize={8} fill="#64748b">{row.label}</text>
        <rect x={LW} y={barY} width={bx(row.value) - LW} height={BH} fill={colour[row.kind]} rx={1.5} opacity={0.85} />
        <text x={LW + CW + 3} y={barY + 6} fontSize={8} fill={colour[row.kind]} fontWeight={500}>+£{Math.round(row.value)}</text>
      </g>
    );
  };
  const renderCostRow = (row: BarRow, y: number) => {
    const barY = y + Math.floor((RH - BH) / 2);
    return (
      <g key={row.label}>
        <text x={LW - 4} y={barY + 6} textAnchor="end" fontSize={8} fill="#64748b">{row.label}</text>
        <rect x={LW} y={barY} width={bx(row.value) - LW} height={BH} fill={colour[row.kind]} rx={1.5} opacity={0.85} />
        <text x={LW + CW + 3} y={barY + 6} fontSize={8} fill={colour[row.kind]} fontWeight={500}>−£{Math.round(row.value)}</text>
      </g>
    );
  };

  let cy = 0;
  const resaleSectionY = cy; cy += sectionLabelH;
  const valueRowsY = cy;     cy += valueRows.length * RH;
  const resaleDividerY = cy; cy += dividerH;
  const costSectionY = cy;   cy += sectionLabelH;
  const costRowsY = cy;      cy += costRows.length * RH;
  const costDividerY = cy;   cy += dividerH;
  const profitRowY = cy;     cy += totalRowH;
  const reconcileY = cy;

  const profitColor = profit >= 0 ? "#00dc82" : "#f87171";
  const profitSign  = profit >= 0 ? "+" : "−";
  const profitBw    = Math.max(Math.abs(profit) * scale, 1.5);

  return (
    <svg width={W} height={H} style={{ display: "block", overflow: "visible" }}>
      <text x={0} y={resaleSectionY + 9} fontSize={7.5} fill="#475569" fontWeight={700} letterSpacing="0.06em">RESALE BUILD-UP</text>
      {valueRows.map((row, i) => renderRow(row, valueRowsY + i * RH))}
      <line x1={LW - 2} y1={resaleDividerY + 4} x2={W} y2={resaleDividerY + 4} stroke="#334155" strokeWidth={0.75} />
      <text x={LW - 4} y={resaleDividerY + 11} textAnchor="end" fontSize={8} fill="#94a3b8" fontWeight={600}>= Resale</text>
      <text x={LW + CW + 3} y={resaleDividerY + 11} fontSize={8} fill="#60a5fa" fontWeight={700}>£{Math.round(resale)}</text>
      <text x={0} y={costSectionY + 9} fontSize={7.5} fill="#475569" fontWeight={700} letterSpacing="0.06em">COSTS</text>
      {costRows.map((row, i) => renderCostRow(row, costRowsY + i * RH))}
      <line x1={LW - 2} y1={costDividerY + 4} x2={W} y2={costDividerY + 4} stroke="#334155" strokeWidth={0.75} />
      <text x={LW - 4} y={costDividerY + 11} textAnchor="end" fontSize={8} fill="#94a3b8" fontWeight={600}>= Total cost</text>
      <text x={LW + CW + 3} y={costDividerY + 11} fontSize={8} fill="#fb923c" fontWeight={700}>£{Math.round(totalCost)}</text>
      <line x1={0} y1={profitRowY} x2={W} y2={profitRowY} stroke="#334155" strokeWidth={0.5} strokeDasharray="3,2" />
      <text x={LW - 4} y={profitRowY + 9} textAnchor="end" fontSize={8.5} fill="#94a3b8" fontWeight={700}>Profit</text>
      <rect x={LW} y={profitRowY + 1} width={profitBw} height={BH + 1} fill={profitColor} rx={2} />
      <text x={LW + CW + 3} y={profitRowY + 9} fontSize={9} fill={profitColor} fontWeight={800}>
        {profitSign}£{Math.round(Math.abs(profit))}
      </text>
      <text x={LW} y={reconcileY + 10} fontSize={7.5} fill="#475569">
        £{Math.round(resale)} − £{Math.round(totalCost)} = {" "}
        <tspan fill={profitColor} fontWeight={700}>{profitSign}£{Math.round(Math.abs(profit))}</tspan>
      </text>
    </svg>
  );
}

function ScatterTooltip({ active, payload }: { active?: boolean; payload?: { payload: Listing & { profit: number } }[] }) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  const hasLiveComps = (d.resale_comp_count ?? 0) > 0;
  const hasRange     = d.resale_low != null && d.resale_high != null && d.resale_low !== d.resale_high;
  const upgradeCost  = d.estimated_upgrade_cost ?? 0;
  const profitAt     = (r: number) => r * (1 - FC.FEE) - d.price - upgradeCost;
  const profitLow    = d.resale_low  != null ? profitAt(d.resale_low)  : null;
  const profitHigh   = d.resale_high != null ? profitAt(d.resale_high) : null;
  const profitMid    = d.estimated_profit ?? 0;
  const isRejected   = profitLow !== null && profitLow < 0;
  const verdictColor = isRejected
    ? "text-red-400 bg-red-400/10 border-red-400/30"
    : "text-[#00dc82] bg-[#00dc82]/10 border-[#00dc82]/30";
  const params = new URLSearchParams();
  if (d.cpu)          params.set("cpu", d.cpu);
  if (d.gpu)          params.set("gpu", d.gpu);
  if (d.ram_gb)       params.set("ram_gb", String(d.ram_gb));
  if (d.ram_type)     params.set("ram_type", d.ram_type);
  if (d.storage_gb)   params.set("storage_gb", String(d.storage_gb));
  if (d.storage_type) params.set("storage_type", d.storage_type);
  params.set("buy_price", String(d.price));
  const auditUrl = `http://localhost:8000/api/debug/resale?${params.toString()}`;
  const fmt = (v: number) => `${v >= 0 ? "+" : ""}${formatCurrency(v)}`;

  return (
    <div className="glass-card rounded-xl p-3 text-xs shadow-2xl" style={{ maxWidth: 284, background: "rgba(8,15,26,0.97)", border: "1px solid rgba(255,255,255,0.1)" }}>
      <p className="text-slate-100 font-semibold mb-2 leading-snug line-clamp-2">{d.title}</p>
      <div className="flex justify-between items-start gap-3 mb-1">
        <span className="text-slate-400 font-medium shrink-0">
          Market&nbsp;
          {hasLiveComps
            ? <span className="text-[9px] text-[#00dc82] font-bold uppercase tracking-wide">{d.resale_comp_count} live comps</span>
            : <span className="text-[9px] text-slate-500 uppercase tracking-wide">estimated</span>}
        </span>
        <span className="text-slate-100 font-semibold text-right tabular-nums">
          {hasRange
            ? <>{formatCurrency(d.resale_low!)} – {formatCurrency(d.resale_high!)}<br />
                <span className="text-slate-400 text-[9px] font-normal">mid {formatCurrency(d.estimated_resale ?? 0)}</span></>
            : formatCurrency(d.estimated_resale ?? 0)}
        </span>
      </div>
      {(profitLow !== null || profitHigh !== null) && (
        <div className="flex justify-between gap-3 mb-2">
          <span className="text-slate-400 font-medium">Profit range</span>
          <span className="tabular-nums text-right text-[10px]">
            <span className={profitLow != null && profitLow < 0 ? "text-red-400 font-semibold" : "text-slate-300 font-semibold"}>{profitLow != null ? fmt(profitLow) : "—"}</span>
            <span className="text-slate-500"> / </span>
            <span className={profitMid > 100 ? "text-[#00dc82] font-bold" : profitMid > 0 ? "text-amber-400 font-bold" : "text-red-400 font-bold"}>{fmt(profitMid)}</span>
            <span className="text-slate-500"> / </span>
            <span className="text-slate-300 font-semibold">{profitHigh != null ? fmt(profitHigh) : "—"}</span>
          </span>
        </div>
      )}
      <div className={`flex items-center justify-between gap-2 rounded-lg px-2 py-1 mb-2 border text-[9px] font-bold uppercase tracking-wide ${verdictColor}`}>
        <span>{isRejected ? "REJECT – risk of loss" : "ACCEPT"}</span>
        {isRejected && <span className="font-normal normal-case">conservative price = loss</span>}
      </div>
      <div className="border-t border-slate-700/60 pt-2 mt-1">
        <WaterfallMini d={d} />
      </div>
      <div className="flex items-center justify-between gap-3 mt-2 pt-1 border-t border-slate-700/40">
        <span className="text-slate-400 font-medium">Score <span className="text-[#00dc82] font-bold">{d.gem_score.toFixed(0)}</span></span>
        <button
          onClick={() => window.open(auditUrl, "_blank", "noopener,noreferrer")}
          className="text-[9px] text-slate-400 hover:text-[#00dc82] transition-colors underline underline-offset-2 cursor-pointer font-medium"
        >Full audit →</button>
      </div>
    </div>
  );
}

function RoiTooltip({ active, payload }: { active?: boolean; payload?: { payload: Listing & { y: number; profit: number } }[] }) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  return (
    <div className="glass-card rounded-xl p-3 text-xs shadow-2xl max-w-52">
      <p className="text-slate-300 font-medium mb-2 line-clamp-2">{d.title}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4"><span className="text-slate-500">Score</span><span className="text-slate-200">{d.gem_score.toFixed(0)}</span></div>
        <div className="flex justify-between gap-4"><span className="text-slate-500">ROI</span><span className={d.y >= 30 ? "text-[#00dc82] font-semibold" : d.y >= 0 ? "text-yellow-400" : "text-red-400"}>{d.y >= 0 ? "+" : ""}{d.y.toFixed(1)}%</span></div>
        <div className="flex justify-between gap-4"><span className="text-slate-500">Profit</span><span className={d.profit > 0 ? "text-[#00dc82] font-semibold" : "text-red-400"}>{formatCurrency(d.profit)}</span></div>
      </div>
    </div>
  );
}

function RecentCard({ listing: l }: { listing: Listing }) {
  const domain = (() => { try { return new URL(l.url).hostname.replace("www.", ""); } catch { return ""; } })();
  const faviconUrl = domain ? `https://www.google.com/s2/favicons?domain=${domain}&sz=64` : null;
  const specs = [
    l.cpu ? l.cpu.replace(/Intel\s+|AMD\s+/i, "") : null,
    l.ram_gb ? `${l.ram_gb}GB ${l.ram_type ?? "RAM"}` : null,
    l.storage_gb ? `${l.storage_gb}GB ${l.storage_type?.toUpperCase() ?? "SSD"}` : null,
    l.gpu ?? null,
  ].filter(Boolean);
  const profit = l.estimated_profit ?? 0;
  const profitColor = profit > 100 ? "text-[#00dc82]" : profit > 0 ? "text-amber-400" : "text-red-400";
  const isAmazingGem = l.classification === "amazing_gem";

  return (
    <a href={l.url} target="_blank" rel="noopener noreferrer"
      className={`flex-shrink-0 w-52 rounded-xl glass-card overflow-hidden transition-all hover:-translate-y-0.5 group
        ${isAmazingGem ? "hover:border-cyan-400/50 border-cyan-400/20" : "hover:border-[#00dc82]/40"}`}
      style={{ minWidth: 204 }}>
      {/* Image — fixed 1:1 square, object-contain so nothing is cropped */}
      <div className="relative bg-[#080f1a] overflow-hidden" style={{ aspectRatio: "4/3" }}>
        {l.image_urls?.[0] ? (
          <img
            src={l.image_urls[0]}
            alt={l.title}
            className="w-full h-full object-contain group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center opacity-15">
            <Gem className="w-10 h-10 text-slate-400" />
          </div>
        )}
        {/* Score badge */}
        <div className="absolute top-2 left-2"><FlippabilityScore score={l.gem_score} size="sm" showLabel={false} /></div>
        {/* Amazing gem crown */}
        {isAmazingGem && (
          <div className="absolute top-2 right-2 text-base" title="Amazing Gem">💎</div>
        )}
        {/* Source favicon */}
        {!isAmazingGem && faviconUrl && (
          <div className="absolute top-2 right-2 w-5 h-5 rounded bg-black/60 p-0.5 flex items-center justify-center">
            <img src={faviconUrl} alt="" className="w-full h-full object-contain" onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
          </div>
        )}
      </div>
      <div className="p-2.5 space-y-1.5">
        <p className="text-xs text-slate-100 font-semibold line-clamp-2 leading-tight">{l.title}</p>
        {specs.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {specs.map((s, i) => <span key={i} className="text-[10px] text-slate-400 bg-white/[0.05] rounded px-1.5 py-0.5 leading-none">{s}</span>)}
          </div>
        )}
        <div className="flex items-center justify-between pt-0.5">
          <AuctionPriceDisplay listing={l} />
          <span className={`text-xs font-bold ${profitColor}`}>{profit > 0 ? "+" : ""}{formatCurrency(profit)}</span>
        </div>
      </div>
    </a>
  );
}

function StatCard({ label, value, sub, icon, color, accent }: {
  label: string; value: string; sub: string; icon: React.ReactNode; color: string; accent?: boolean;
}) {
  return (
    <Card className={accent ? "border-[#00dc82]/20 shadow-[0_0_24px_rgba(0,220,130,0.06)]" : ""}>
      <CardContent className="pt-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">{label}</span>
          <div className={`${color} opacity-60`}>{icon}</div>
        </div>
        <div className={`text-2xl font-bold ${color}`}>{value}</div>
        <div className="text-xs text-slate-600 mt-1">{sub}</div>
      </CardContent>
    </Card>
  );
}
