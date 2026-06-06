"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
  ResponsiveContainer, ReferenceLine, ComposedChart, Bar, Line,
} from "recharts";
import {
  TrendingUp, Gem, Zap, Clock, Bell, ArrowRight, RefreshCw,
  ChevronLeft, ChevronRight, Settings2, Check, SlidersHorizontal, Gavel, Activity,
  BookOpen, Flame, Thermometer, Snowflake, PlusCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ClassificationBadge } from "@/components/classification-badge";
import { FlippabilityScore } from "@/components/flippability-score";
import { SourceBadge } from "@/components/source-badge";
import { EmptyState } from "@/components/empty-state";
import { ScanOverlay } from "@/components/scan-overlay";
import { SellerBadge } from "@/components/seller-badge";
import { AuctionBadge, AuctionPriceDisplay, useCountdown } from "@/components/auction-display";
import { Listing, Flip, SearchConfig, DataSource, Playbook, DemandSummary, AuctionIntelItem, TrendDir, DemandStrength } from "@/lib/types";
import { ScanStatus, api, apiUrl, API_BASE_URL } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import Link from "next/link";
import CountUp from "@/components/CountUp";
import { ManualSubmitModal } from "@/components/manual-submit-modal";
import { AntiBotPreflightBanner } from "@/components/antibot-preflight-banner";

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

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timeout after ${timeoutMs}ms`)), timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      }
    );
  });
}

const TRENDING_CATEGORIES_BASE_NOW_MS = Date.now();

// ── Dashboard page ────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter();
  const [listings, setListings] = useState<Listing[]>([]);
  const [flips, setFlips] = useState<Flip[]>([]);
  const [stats, setStats] = useState({ total_listings: 0, gems_count: 0, avg_profit: 0 });
  const [swarms, setSwarms] = useState<{ id: string; name: string; next_run: string | null }[]>([]);
  const [gemOfDay, setGemOfDay] = useState<Listing | null>(null);
  const [gemOfWeek, setGemOfWeek] = useState<Listing | null>(null);
  const [searchConfig, setSearchConfig] = useState<SearchConfig | null>(null);
  const [sources, setSources] = useState<DataSource[]>([]);
  const [activePlaybooks, setActivePlaybooks] = useState<Playbook[]>([]);
  const [demandSummary, setDemandSummary] = useState<DemandSummary | null>(null);
  const [auctionIntel, setAuctionIntel] = useState<AuctionIntelItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState(6);
  const [loadingStartedAt, setLoadingStartedAt] = useState<number>(Date.now());
  const [feedsDone, setFeedsDone] = useState(0);
  const [elapsedSecs, setElapsedSecs] = useState(0);
  const [triggering, setTriggering] = useState(false);
  const [triggeringAutoCycle, setTriggeringAutoCycle] = useState(false);
  const [autoCycleMessage, setAutoCycleMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [showManualSubmit, setShowManualSubmit] = useState(false);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [retrainReady, setRetrainReady] = useState<boolean | null>(null);
  const [soldSinceCheckpoint, setSoldSinceCheckpoint] = useState<number>(0);
  const [autonomousCycleHealthy, setAutonomousCycleHealthy] = useState<boolean | null>(null);
  // Dev mode scope toggle — only active when backend reports app_env=dev
  const [devEnv, setDevEnv] = useState(false);
  const [startedAt, setStartedAt] = useState<string | null>(null);
  const [devScope, setDevScope] = useState<"all" | "since_restart">(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("ff_dev_scope") as "all" | "since_restart") ?? "since_restart";
    }
    return "since_restart";
  });
  // Refs so load() always reads current values without closure staleness
  const devScopeRef = useRef<"all" | "since_restart">("since_restart");
  const startedAtRef = useRef<string | null>(null);
  const [autonomousLastRunAt, setAutonomousLastRunAt] = useState<string | null>(null);
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
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const load = async () => {
    setLoading(true);
    setLoadProgress(6);
    setLoadingStartedAt(Date.now());
    setFeedsDone(0);
    setElapsedSecs(0);
    try {
      // Fetch health to detect dev mode and get startup timestamp
      try {
        const h = await fetch(`${API_BASE_URL}/health`).then(r => r.json());
        if (h.app_env === "dev") {
          setDevEnv(true);
          setStartedAt(h.started_at);
          startedAtRef.current = h.started_at;
        }
      } catch { /* backend offline — health check non-critical */ }

      // Rolling windows for gem picks
      const now = new Date();
      const past24hISO = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();
      const past7dISO  = new Date(now.getTime() - 7  * 24 * 60 * 60 * 1000).toISOString();

      // Dev scope filter: restrict to listings first seen since last container restart
      const scopeFilter: Record<string, string> = (devScopeRef.current === "since_restart" && startedAtRef.current)
        ? { first_seen_after: startedAtRef.current }
        : {};

      const totalCalls = 11;
      let doneCalls = 0;
      const step = async <T,>(p: Promise<T>, timeoutMs: number): Promise<T> => {
        try {
          return await withTimeout(p, timeoutMs);
        } finally {
          doneCalls += 1;
          setFeedsDone(doneCalls);
          const pct = Math.min(96, 6 + Math.floor((doneCalls / totalCalls) * 90));
          setLoadProgress((prev) => (pct > prev ? pct : prev));
        }
      };

      const results = await Promise.allSettled([
        step(api.listings.list({ sort_by: "estimated_profit", sort_desc: "true", limit: "500", ...scopeFilter }) as Promise<Listing[]>, 15000),
        step(api.listings.stats(), 12000),
        step(api.swarms.list() as Promise<{ id: string; name: string; next_run: string | null }[]>, 12000),
        step(api.flips.list() as Promise<Flip[]>, 12000),
        // Gem of Day: best LLM-judged gem from listings first scraped in last 24 h
        step(api.listings.list({
          sort_by: "claude_flipability_score", sort_desc: "true",
          limit: "1", claude_judged_only: "true", first_seen_after: past24hISO,
        }) as Promise<Listing[]>, 12000),
        // Gem of Week: best LLM-judged gem from listings first scraped in last 7 days
        step(api.listings.list({
          sort_by: "claude_flipability_score", sort_desc: "true",
          limit: "1", claude_judged_only: "true", first_seen_after: past7dISO,
        }) as Promise<Listing[]>, 12000),
        step(api.config.get() as Promise<SearchConfig>, 12000),
        step(api.sources.list() as Promise<DataSource[]>, 12000),
        step(api.playbooks.list("active").catch(() => [] as Playbook[]), 12000),
        step(api.demand.summary().catch(() => null), 12000),
        step(api.demand.auctionIntel(15).catch(() => [] as AuctionIntelItem[]), 12000),
      ]);

      const getValue = <T,>(idx: number, fallback: T): T => {
        const r = results[idx];
        return r.status === "fulfilled" ? (r.value as T) : fallback;
      };

      const l = getValue<Listing[]>(0, []);
      const s = getValue<{ total_listings: number; gems_count: number; avg_profit: number }>(1, { total_listings: 0, gems_count: 0, avg_profit: 0 });
      const sw = getValue<{ id: string; name: string; next_run: string | null }[]>(2, []);
      const fl = getValue<Flip[]>(3, []);
      const godResults = getValue<Listing[]>(4, []);
      const gowResults = getValue<Listing[]>(5, []);
      const cfg = getValue<SearchConfig | null>(6, null);
      const srcs = getValue<DataSource[]>(7, []);
      const pbs = getValue<Playbook[]>(8, []);
      const demand = getValue<DemandSummary | null>(9, null);
      const auctions = getValue<AuctionIntelItem[]>(10, []);

      setListings(l);
      setStats(s);
      setSwarms(sw);
      setFlips(fl);
      setSearchConfig(cfg);
      setSources(srcs);
      setActivePlaybooks(pbs);
      setDemandSummary(demand);
      setAuctionIntel(auctions);
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
      // Ensure the progress bar is visible for at least 1.5 s so it doesn't
      // flash and vanish when all calls fail fast (e.g. 500 errors).
      const elapsed = Date.now() - loadingStartedAt;
      const remaining = Math.max(0, 1500 - elapsed);
      setTimeout(() => {
        setLoadProgress(100);
        setTimeout(() => setLoadProgress(0), 400);
        setLoading(false);
      }, remaining);
    }
  };

  const loadAutonomousHealth = async () => {
    try {
      const [retrain, runs] = await Promise.all([
        api.intel.retrainStatus(),
        api.schedule.runs("autonomous_cycle"),
      ]);
      setRetrainReady(Boolean(retrain.retrain_ready));
      setSoldSinceCheckpoint(Number(retrain.sold_flips_since || 0));
      const last = runs && runs.length > 0 ? runs[0] : null;
      setAutonomousCycleHealthy(last ? last.status === "success" : null);
      setAutonomousLastRunAt(last?.started_at ?? null);
    } catch {
      setRetrainReady(null);
      setSoldSinceCheckpoint(0);
      setAutonomousCycleHealthy(null);
      setAutonomousLastRunAt(null);
    }
  };

  useEffect(() => {
    if (!loading) return;
    const tick = setInterval(() => {
      setElapsedSecs(Math.floor((Date.now() - loadingStartedAt) / 1000));
    }, 1000);
    const timeoutId = setTimeout(() => {
      setLoading(false);
    }, 12_000);
    return () => {
      clearInterval(tick);
      clearTimeout(timeoutId);
    };
  }, [loading, loadingStartedAt]);

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
    const id = setTimeout(() => { void load(); }, 0);
    const id2 = setTimeout(() => { void loadAutonomousHealth(); }, 0);
    return () => {
      clearTimeout(id);
      clearTimeout(id2);
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Keep ref in sync and reload when dev scope toggle changes
  useEffect(() => {
    devScopeRef.current = devScope;
    localStorage.setItem("ff_dev_scope", devScope);
    // Don't reload on initial mount (load() already handles it)
    if (startedAtRef.current) void load();
  }, [devScope]);

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

  const triggerAutonomousCycle = async () => {
    setTriggeringAutoCycle(true);
    try {
      await api.schedule.run("autonomous_cycle");
      await loadAutonomousHealth();
      setAutoCycleMessage({ type: "success", text: "Autonomous cycle completed successfully." });
      setTimeout(() => setAutoCycleMessage(null), 2500);
    } catch {
      setAutoCycleMessage({ type: "error", text: "Autonomous cycle failed. Check Scheduler runs/logs." });
      setTimeout(() => setAutoCycleMessage(null), 3000);
    } finally {
      setTriggeringAutoCycle(false);
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
  const cutoff24h = new Date(nowMs - 24 * 3600_000).toISOString();
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

  const latestListings = [...listings]
    .sort((a, b) => new Date(b.first_seen_at).getTime() - new Date(a.first_seen_at).getTime())
    .slice(0, 24);

  return (
    <div className="p-6 space-y-6 dashboard-zoom">
      <ManualSubmitModal
        open={showManualSubmit}
        onClose={() => setShowManualSubmit(false)}
        onSuccess={() => { setShowManualSubmit(false); load(); }}
      />
      <AntiBotPreflightBanner />
      {loading && (
        <div className="w-full max-w-xl rounded-2xl border border-[#1e2d45] bg-[#0d1320]/90 p-4">
          <div className="flex items-center justify-between text-base mb-2">
            <div className="flex items-center gap-2 text-slate-300">
              <RefreshCw className="w-4 h-4 animate-spin" />
              Retrieving live market data…
            </div>
            <span className="text-slate-500 tabular-nums">{Math.max(0, Math.min(100, loadProgress))}%</span>
          </div>
          <div className="h-2 rounded-full bg-[#111c2e] overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cyan-400 to-[#00dc82] transition-all duration-300"
              style={{ width: `${Math.max(2, Math.min(100, loadProgress))}%` }}
            />
          </div>
          <div className="mt-2 text-base text-slate-500">
            {loadProgress < 100
              ? `Fetched ${feedsDone}/11 dashboard feeds • ${elapsedSecs}s elapsed`
              : "Finalizing data..."}
          </div>
        </div>
      )}
      {scanStatus?.running && (
        <ScanOverlay status={scanStatus} />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <img src="/pics/logo.png" alt="FlipFlop" className="h-[144px] w-auto object-contain" />
          <p className="text-base text-[var(--nf-text-muted)] mt-0.5 font-mono">Live market intelligence</p>
        </div>
        <div className="flex items-center gap-3">
          {autonomousCycleHealthy !== null && (
            <div className={`flex items-center gap-2 px-3 py-2 rounded-xl border ${
              autonomousCycleHealthy
                ? "bg-cyan-500/10 border-cyan-400/25"
                : "bg-amber-500/10 border-amber-400/25"
            }`}>
              <Activity className={`w-3.5 h-3.5 ${autonomousCycleHealthy ? "text-cyan-300" : "text-amber-300"}`} />
              <span className={`text-base font-semibold ${autonomousCycleHealthy ? "text-cyan-300" : "text-amber-300"}`}>
                Auto Loop {autonomousCycleHealthy ? "Healthy" : "Attention"} · Retrain {retrainReady ? "Ready" : "Collecting"} ({soldSinceCheckpoint})
              </span>
              {autonomousLastRunAt && (
                <span className="text-[10px] text-slate-500">
                  last {formatRelativeTime(new Date(autonomousLastRunAt))}
                </span>
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={triggerAutonomousCycle}
                disabled={triggeringAutoCycle}
              >
                <RefreshCw className={`w-3.5 h-3.5 ${triggeringAutoCycle ? "animate-spin" : ""}`} />
                {triggeringAutoCycle ? "Running…" : "Run Auto Cycle"}
              </Button>
            </div>
          )}
          {gems.length > 0 && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#00dc82]/10 border border-[#00dc82]/25 new-badge-pulse">
              <Bell className="w-3.5 h-3.5 text-[#00dc82]" />
              <span className="text-base font-semibold text-[#00dc82]">{gems.length} gem{gems.length !== 1 ? "s" : ""} in database</span>
            </div>
          )}
          <Button variant="secondary" size="sm" onClick={() => setShowManualSubmit(true)}>
            <PlusCircle className="w-3.5 h-3.5" />
            Submit Manually
          </Button>
          <Button variant="secondary" size="sm" onClick={triggerScan} disabled={triggering}>
            <RefreshCw className={`w-3.5 h-3.5 ${triggering ? "animate-spin" : ""}`} />
            {triggering ? "Scanning…" : "Scan Now"}
          </Button>
        </div>
      </div>
      {autoCycleMessage && (
        <div className={`rounded-xl px-3 py-2 text-base border ${
          autoCycleMessage.type === "success"
            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
            : "bg-red-500/10 border-red-500/30 text-red-300"
        }`}>
          {autoCycleMessage.text}
        </div>
      )}

      {/* Dev mode scope toggle — only shown when backend is in dev mode */}
      {devEnv && (
        <div className="flex items-center gap-3 px-3 py-2 rounded-xl border border-amber-400/30 bg-amber-400/5 w-fit">
          <span className="text-[10px] font-bold uppercase tracking-widest text-amber-400">DEV</span>
          <span className="text-xs text-slate-400">Data scope:</span>
          {(["since_restart", "all"] as const).map(opt => (
            <button
              key={opt}
              onClick={() => setDevScope(opt)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold border transition-all ${
                devScope === opt
                  ? "bg-amber-400/15 text-amber-300 border-amber-400/40"
                  : "bg-transparent text-slate-500 border-slate-700 hover:border-slate-500"
              }`}
            >
              {opt === "since_restart" ? "Since Restart" : "All Data"}
            </button>
          ))}
          {startedAt && (
            <span className="text-[10px] text-slate-600">
              restarted {new Date(startedAt).toLocaleTimeString()}
            </span>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 lg:auto-rows-[minmax(0,1fr)]">
        <div className="lg:row-span-2">
          <ListingsTrackedCard total={stats.total_listings} listings={listings} />
        </div>
        <div className="lg:row-span-2">
          <GemsFoundCard total={stats.gems_count} listings={listings} />
        </div>
        <div className="grid grid-rows-2 gap-4">
          <AvgProfitCard avg={stats.avg_profit} listings={listings} compact />
          <NextScanCard swarm={swarms[0] ?? null} intervalMinutes={60} compact />
        </div>
        <div className="grid grid-rows-2 gap-4">
          <GemHighlightCard period="day" listing={gemOfDay} />
          <GemHighlightCard period="week" listing={gemOfWeek} />
        </div>
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
          {/* ── Trending Categories + Playbook ────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <TrendingCategoriesCard listings={listings} />
            </div>
            <PlaybookActivityCard config={searchConfig} sources={sources} listings={listings} nowMs={nowMs} />
          </div>

          {/* ── Current Strategy + Auction Intelligence ────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <CurrentStrategyCard playbooks={activePlaybooks} demandSummary={demandSummary} />
            <AuctionIntelCard auctions={auctionIntel} />
          </div>

          {/* ── PnL Chart ─────────────────────────────────────────────────────── */}
          <Card className="-mt-3">
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
                    className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-base text-slate-300 focus:outline-none focus:border-[#00dc82]/50"
                  />
                  <span className="text-slate-600 text-base">→</span>
                  <input
                    type="date"
                    value={pnlDateTo}
                    onChange={e => setPnlDateTo(e.target.value)}
                    className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-base text-slate-300 focus:outline-none focus:border-[#00dc82]/50"
                  />
                  <select
                    value={pnlSource}
                    onChange={e => setPnlSource(e.target.value)}
                    className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-base text-slate-300 focus:outline-none focus:border-[#00dc82]/50"
                  >
                    <option value="all">All sources</option>
                    {allSources.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  {allPlatforms.length > 0 && (
                    <select
                      value={pnlPlatform}
                      onChange={e => setPnlPlatform(e.target.value)}
                      className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-base text-slate-300 focus:outline-none focus:border-[#00dc82]/50"
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
                <div className="flex items-center justify-center h-48 text-slate-600 text-base">
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
              className="w-16 bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-base text-slate-300 focus:outline-none focus:border-[#00dc82]/50 text-center"
            />
            <span className="text-[11px] text-slate-500">by score (of {listings.length})</span>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">

            {/* Chart 1: Buy price vs resale */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Buy price vs resale — bubble = profit</CardTitle>
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
                <CardTitle className="text-base">Flippability score vs ROI% — bubble = profit</CardTitle>
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
              <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
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
              <div className="rounded-xl border border-dashed border-white/[0.07] px-6 py-5 text-center text-slate-600 text-base">
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
                  <span className="text-base font-normal text-slate-500">({listings.length} total · sorted by flippability)</span>
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
                            <span className="text-base text-slate-300">{col.label}</span>
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
                    className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-base text-slate-400 focus:outline-none focus:border-[#00dc82]/50"
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
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 p-4">
                {pagedListings.map(l => {
                  const roi = (l.price + (l.estimated_upgrade_cost ?? 0)) > 0
                    ? ((l.estimated_profit ?? 0) / (l.price + (l.estimated_upgrade_cost ?? 0))) * 100
                    : 0;
                  const profitPositive = (l.estimated_profit ?? 0) > 0;
                  return (
                    <div key={l.id} className="bg-[#0a1628] border border-white/[0.06] rounded-xl overflow-hidden flex flex-col hover:border-white/[0.12] transition-colors">
                      {/* Thumbnail + score overlay */}
                      <div className="relative w-full h-36 bg-[#060e1c] flex-shrink-0">
                        {l.image_urls[0] ? (
                          <img src={l.image_urls[0]} alt="" className="w-full h-full object-contain" loading="lazy" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center opacity-10">
                            <Gem className="w-8 h-8 text-slate-400" />
                          </div>
                        )}
                        {/* Score badge top-left */}
                        <div className="absolute top-2 left-2">
                          <FlippabilityScore score={l.gem_score} size="sm" />
                        </div>
                        {/* ROI badge top-right */}
                        <div className={`absolute top-2 right-2 text-[10px] font-bold px-1.5 py-0.5 rounded-md ${roi >= 30 ? "bg-[#00dc82]/20 text-[#00dc82]" : roi >= 0 ? "bg-yellow-400/20 text-yellow-400" : "bg-red-400/20 text-red-400"}`}>
                          {roi >= 0 ? "+" : ""}{roi.toFixed(0)}% ROI
                        </div>
                      </div>

                      {/* Body */}
                      <div className="flex flex-col gap-2 p-3 flex-1">
                        {/* Title + badges */}
                        <div>
                          <a href={l.url} target="_blank" rel="noopener noreferrer"
                            className="text-base font-semibold text-slate-200 line-clamp-2 hover:text-[#00dc82] transition-colors leading-snug">
                            {l.title}
                          </a>
                          <div className="flex flex-wrap items-center gap-1 mt-1.5">
                            <SourceBadge sourceName={l.source_name} url={l.url} />
                            <ClassificationBadge classification={l.classification} />
                            <AuctionBadge listing={l} />
                          </div>
                        </div>

                        {/* Specs */}
                        <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[10px]">
                          {l.cpu && (
                            <div className="col-span-2 flex items-center gap-1 text-slate-400 min-w-0">
                              <span className="text-slate-600 flex-shrink-0">CPU</span>
                              <span className="font-mono truncate">{l.cpu}</span>
                            </div>
                          )}
                          {l.gpu && (
                            <div className="col-span-2 flex items-center gap-1 text-slate-400 min-w-0">
                              <span className="text-slate-600 flex-shrink-0">GPU</span>
                              <span className="truncate">{l.gpu}</span>
                            </div>
                          )}
                          {l.ram_gb && (
                            <div className="flex items-center gap-1 text-slate-400">
                              <span className="text-slate-600">RAM</span>
                              <span>{l.ram_gb}GB {l.ram_type ?? ""}</span>
                            </div>
                          )}
                          {l.storage_gb && (
                            <div className="flex items-center gap-1 text-slate-400">
                              <span className="text-slate-600">SSD</span>
                              <span>{l.storage_gb}GB {l.storage_type?.toUpperCase() ?? ""}</span>
                            </div>
                          )}
                        </div>

                        {/* Financials */}
                        <div className="grid grid-cols-4 gap-1 mt-auto pt-2 border-t border-white/[0.05]">
                          <div className="flex flex-col items-center">
                            <span className="text-[9px] text-slate-600 uppercase tracking-wide">Buy</span>
                            <AuctionPriceDisplay listing={l} />
                          </div>
                          <div className="flex flex-col items-center">
                            <span className="text-[9px] text-slate-600 uppercase tracking-wide">Upgrade</span>
                            <span className="text-[10px] text-slate-400">{l.estimated_upgrade_cost != null ? formatCurrency(l.estimated_upgrade_cost) : "—"}</span>
                          </div>
                          <div className="flex flex-col items-center">
                            <span className="text-[9px] text-slate-600 uppercase tracking-wide">Resale</span>
                            <span className="text-[10px] text-slate-300">{formatCurrency(l.estimated_resale ?? 0)}</span>
                            {(l.resale_comp_count ?? 0) > 0
                              ? <span className="text-[8px] text-[#00dc82]/50">{l.resale_comp_count} comps</span>
                              : <span className="text-[8px] text-slate-700">est.</span>
                            }
                          </div>
                          <div className="flex flex-col items-center">
                            <span className="text-[9px] text-slate-600 uppercase tracking-wide">Profit</span>
                            <span className={`text-[11px] font-bold ${profitPositive ? "text-[#00dc82]" : "text-red-400"}`}>
                              {profitPositive ? "+" : ""}{formatCurrency(l.estimated_profit ?? 0)}
                            </span>
                          </div>
                        </div>

                        {/* Footer: seller + location + flip */}
                        <div className="flex items-center justify-between pt-1">
                          <div className="flex flex-col gap-0.5 min-w-0">
                            <SellerBadge listing={l} />
                            {l.location && (
                              <span className="text-[9px] text-slate-600 truncate">{l.location}</span>
                            )}
                            <span className="text-[9px] text-slate-700">
                              {l.listed_at
                                ? formatRelativeTime(new Date(l.listed_at))
                                : formatRelativeTime(new Date(l.first_seen_at))
                              }
                            </span>
                          </div>
                          <Button
                            variant="primary" size="sm"
                            disabled={flippingId === l.id}
                            onClick={() => handleFlip(l)}
                            className="flex-shrink-0"
                          >
                            {flippingId === l.id
                              ? <RefreshCw className="w-3 h-3 animate-spin" />
                              : <Zap className="w-3 h-3" />}
                            Flip
                          </Button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Pagination bar */}
              <div className="flex items-center justify-between px-5 py-3 border-t border-white/[0.06]">
                <span className="text-base text-slate-500">
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
                        ? <span key={`ellipsis-${i}`} className="px-1.5 text-base text-slate-600">…</span>
                        : (
                          <button
                            key={p}
                            onClick={() => setTablePage(p as number)}
                            className={`w-7 h-7 rounded-lg text-base transition-colors
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

      {latestListings.length > 0 && (
        <LatestListingsCarousel
          listings={latestListings}
          nowMs={nowMs}
          onOpen={(l) => router.push(`/opportunities?listing=${l.id}`)}
        />
      )}
    </div>
  );
}

function formatElapsedMMSS(firstSeen: string, nowMs: number): string {
  const elapsed = Math.max(0, Math.floor((nowMs - new Date(firstSeen).getTime()) / 1000));
  const mm = Math.floor(elapsed / 60);
  const ss = elapsed % 60;
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

function LatestListingsCarousel({
  listings,
  nowMs,
  onOpen,
}: {
  listings: Listing[];
  nowMs: number;
  onOpen: (listing: Listing) => void;
}) {
  const items = [...listings, ...listings];
  return (
    <div className="mt-2 border border-[#1e2d45] rounded-2xl bg-[#050b14]/95 backdrop-blur-md">
      <style>{`
        @keyframes flipflop-marquee {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
      <div className="px-4 pt-2 pb-1 flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-[0.18em] text-[#7ce7b6] font-semibold">Latest Listings</div>
        <div className="text-[10px] text-slate-500">newest first · live timers</div>
      </div>
      <div className="overflow-hidden pb-3">
        <div
          className="flex gap-3 w-max px-4"
          style={{
            animation: "flipflop-marquee 52s linear infinite",
          }}
        >
          {items.map((l, idx) => (
            <button
              key={`${l.id}-${idx}`}
              onClick={() => onOpen(l)}
              className="w-[280px] shrink-0 rounded-xl overflow-hidden border border-white/10 bg-[#0a1628] hover:border-[#00dc82]/50 transition-colors text-left"
              title={l.title}
            >
              <div className="relative h-28 bg-[#060e1c]">
                {l.image_urls?.[0] ? (
                  <img src={l.image_urls[0]} alt={l.title} className="w-full h-full object-cover" loading="lazy" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center opacity-20">
                    <Gem className="w-7 h-7 text-slate-400" />
                  </div>
                )}
                <div className="absolute top-1.5 left-1.5">
                  <FlippabilityScore score={l.gem_score} size="sm" showLabel={false} />
                </div>
                <div className="absolute top-1.5 right-1.5 text-[10px] font-bold px-1.5 py-0.5 rounded bg-black/60 border border-white/20 text-[#7ce7b6] tabular-nums">
                  +{formatElapsedMMSS(l.first_seen_at, nowMs)}
                </div>
                <div className="absolute inset-x-0 bottom-0 p-2 bg-gradient-to-t from-black/85 via-black/55 to-transparent">
                  <div className="text-sm font-semibold text-white line-clamp-1">{l.title}</div>
                  <div className="text-[10px] text-slate-300 mt-0.5 flex items-center justify-between">
                    <span>{l.source_name}</span>
                    <span className={(l.estimated_profit ?? 0) >= 0 ? "text-[#00dc82]" : "text-red-400"}>
                      {(l.estimated_profit ?? 0) >= 0 ? "+" : ""}{formatCurrency(l.estimated_profit ?? 0)}
                    </span>
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Auction helpers ── (imported from @/components/auction-display) ──────────
// ── Seller badge ── (imported from @/components/seller-badge) ────────────────

// ── Gem of the Day / Gem of the Week card ────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-unused-vars
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
            className="text-base font-semibold text-slate-100 line-clamp-1 hover:text-[#00dc82] transition-colors block">
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
            <div className={`text-base font-bold mt-0.5 ${profit > 0 ? "text-[#00dc82]" : "text-red-400"}`}>
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
// ── PnL Tooltip ───────────────────────────────────────────────────────────────
function PnlTooltip({ active, payload }: { active?: boolean; payload?: { payload: { date: string; profit: number; cumulative: number; label: string } }[]; label?: string }) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-xl p-3 text-base shadow-2xl" style={{ background: "rgba(8,15,26,0.97)", border: "1px solid rgba(255,255,255,0.1)" }}>
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
  const auditUrl = apiUrl(`/debug/resale?${params.toString()}`);
  const fmt = (v: number) => `${v >= 0 ? "+" : ""}${formatCurrency(v)}`;

  return (
    <div className="glass-card rounded-xl p-3 text-base shadow-2xl" style={{ maxWidth: 284, background: "rgba(8,15,26,0.97)", border: "1px solid rgba(255,255,255,0.1)" }}>
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
        <p className="text-base text-slate-100 font-semibold line-clamp-2 leading-tight">{l.title}</p>
        {specs.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {specs.map((s, i) => <span key={i} className="text-[10px] text-slate-400 bg-white/[0.05] rounded px-1.5 py-0.5 leading-none">{s}</span>)}
          </div>
        )}
        <div className="flex items-center justify-between pt-0.5">
          <AuctionPriceDisplay listing={l} />
          <span className={`text-base font-bold ${profitColor}`}>{profit > 0 ? "+" : ""}{formatCurrency(profit)}</span>
        </div>
      </div>
    </a>
  );
}

// ── Source logo helper ────────────────────────────────────────────────────────
const SOURCE_DOMAIN: Record<string, string> = {
  "eBay UK": "ebay.co.uk",
  "eBay UK Auctions": "ebay.co.uk",
  "Gumtree": "gumtree.com",
  "Facebook Marketplace": "facebook.com",
  "Amazon": "amazon.co.uk",
};

function SourceLogo({ source }: { source: string }) {
  const domain = SOURCE_DOMAIN[source] ?? source.toLowerCase().replace(/\s+/g, "") + ".com";
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=16`}
      alt={source}
      title={source}
      className="w-4 h-4 rounded-sm"
    />
  );
}

// ── Listings Tracked ──────────────────────────────────────────────────────────
function ListingsTrackedCard({ total, listings }: { total: number; listings: Listing[] }) {
  const bySource = listings.reduce<Record<string, number>>((acc, l) => {
    acc[l.source_name] = (acc[l.source_name] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <Card className="border-slate-500/25 bg-slate-950/55 shadow-[0_10px_40px_rgba(2,6,23,0.42)]">
      <CardContent className="pt-5 pb-5 min-h-[220px]">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-[0.2em]">Listings Tracked</span>
          <Gem className="w-4.5 h-4.5 text-slate-200/80" />
        </div>
        <div className="text-4xl leading-none font-black text-slate-100 tabular-nums">
          <CountUp to={total} duration={1.5} separator="," />
        </div>
        <div className="mt-3 flex flex-col gap-1.5">
          {Object.entries(bySource).map(([src, count]) => (
            <div key={src} className="flex items-center justify-between text-base text-slate-400">
              <div className="flex items-center gap-1.5">
                <SourceLogo source={src} />
                <span className="truncate max-w-[100px]">{src}</span>
              </div>
              <CountUp to={count} duration={1.2} className="text-slate-200 font-semibold tabular-nums" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Gems Found ────────────────────────────────────────────────────────────────
function GemsFoundCard({ total, listings }: { total: number; listings: Listing[] }) {
  const gems = listings.filter((l) => l.classification === "gem");
  const bySource = gems.reduce<Record<string, number>>((acc, l) => {
    acc[l.source_name] = (acc[l.source_name] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <Card className="border-[#00dc82]/30 bg-[#021b12]/55 shadow-[0_12px_44px_rgba(0,220,130,0.16)]">
      <CardContent className="pt-5 pb-5 min-h-[220px]">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] text-[#7ce7b6] font-semibold uppercase tracking-[0.2em]">Gems Found</span>
          <Gem className="w-4.5 h-4.5 text-[#00dc82]" />
        </div>
        <div className="text-4xl leading-none font-black text-[#00f49a] tabular-nums">
          <CountUp to={total} duration={1.5} separator="," />
        </div>
        <div className="mt-3 flex flex-col gap-1.5">
          {Object.entries(bySource).map(([src, count]) => (
            <div key={src} className="flex items-center justify-between text-base text-[#89eabf]/85">
              <div className="flex items-center gap-1.5">
                <SourceLogo source={src} />
                <span className="truncate max-w-[100px]">{src}</span>
              </div>
              <CountUp to={count} duration={1.2} className="text-[#00f49a] font-bold tabular-nums" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Avg Profit ────────────────────────────────────────────────────────────────
function AvgProfitCard({ avg, listings, compact = false }: { avg: number; listings: Listing[]; compact?: boolean }) {
  const profits = listings.map((l) => l.estimated_profit ?? 0).filter((p) => p !== 0);
  const minProfit = profits.length ? Math.min(...profits) : 0;
  const maxProfit = profits.length ? Math.max(...profits) : 0;

  return (
    <Card className="border-[#00dc82]/30 bg-[#041922]/55 shadow-[0_12px_44px_rgba(0,184,255,0.15)]">
      <CardContent className={compact ? "pt-4 pb-4" : "pt-5 pb-5"}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] text-cyan-300 font-semibold uppercase tracking-[0.2em]">Avg Profit</span>
          <TrendingUp className="w-4.5 h-4.5 text-cyan-300" />
        </div>
        <div className={`${compact ? "text-3xl" : "text-4xl"} leading-none font-black text-cyan-200 tabular-nums`}>
          £<CountUp to={avg} from={0} duration={1.5} />
        </div>
        {profits.length > 0 && (
          <div className="mt-3 flex items-center gap-1.5 text-base text-cyan-100/65">
            <span className="text-red-300/90">£<CountUp to={minProfit} duration={1.2} /></span>
            <span className="text-slate-600">→</span>
            <span className="text-cyan-200 font-semibold">£<CountUp to={maxProfit} duration={1.2} /></span>
            <span className="text-cyan-100/55 ml-0.5 uppercase tracking-wider">range</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function GemHighlightCard({ period, listing }: { period: "day" | "week"; listing: Listing | null }) {
  const label = period === "day" ? "Gem of the Day" : "Gem of the Week";
  if (!listing) {
    return (
      <Card className="border-[#00dc82]/20 bg-[#03150e]/45">
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] text-[#7ce7b6] font-semibold uppercase tracking-[0.18em]">{label}</span>
            <Gem className="w-4 h-4 text-[#00dc82]/70" />
          </div>
          <div className="text-base text-slate-500">No qualifying listing yet</div>
        </CardContent>
      </Card>
    );
  }
  const profit = listing.estimated_profit ?? 0;
  const resale = listing.estimated_resale ?? 0;
  return (
    <Card className="border-[#00dc82]/25 bg-[#03150e]/55">
      <CardContent className="pt-4 pb-4 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-[#7ce7b6] font-semibold uppercase tracking-[0.18em]">{label}</span>
          <Gem className="w-4 h-4 text-[#00dc82]" />
        </div>

        <div className="flex gap-3">
          <div className="w-20 h-20 rounded-lg overflow-hidden border border-[#00dc82]/20 bg-black/20 shrink-0">
            {listing.image_urls?.[0] ? (
              <img src={listing.image_urls[0]} alt={listing.title} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-slate-600 text-sm">No image</div>
            )}
          </div>

          <div className="min-w-0 flex-1">
            <a
              href={listing.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-base font-semibold text-slate-100 hover:text-[#00dc82] line-clamp-2 leading-tight"
            >
              {listing.title}
            </a>
            <div className="mt-1 text-sm text-slate-400 truncate">{listing.source_name}</div>
            <div className="mt-1 flex flex-wrap gap-1">
              {listing.cpu && <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-slate-300">{listing.cpu}</span>}
              {listing.ram_gb && <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-slate-300">{listing.ram_gb}GB {listing.ram_type ?? "RAM"}</span>}
              {listing.gpu && <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-slate-300">{listing.gpu}</span>}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-sm">
          <div className="rounded-lg px-2 py-1.5 bg-black/20 border border-white/10">
            <div className="text-slate-500">Buy</div>
            <div className="text-slate-100 font-semibold tabular-nums">{formatCurrency(listing.price)}</div>
          </div>
          <div className="rounded-lg px-2 py-1.5 bg-black/20 border border-white/10">
            <div className="text-slate-500">Resale</div>
            <div className="text-slate-100 font-semibold tabular-nums">{resale ? formatCurrency(resale) : "—"}</div>
          </div>
          <div className="rounded-lg px-2 py-1.5 bg-black/20 border border-white/10">
            <div className="text-slate-500">Profit</div>
            <div className={`${profit >= 0 ? "text-[#00dc82]" : "text-red-400"} font-bold tabular-nums`}>
              {profit >= 0 ? "+" : ""}{formatCurrency(profit)}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Next Scan countdown ───────────────────────────────────────────────────────
function NextScanCard({ swarm, intervalMinutes, compact = false }: {
  swarm: { id: string; name: string; next_run: string | null } | null;
  intervalMinutes: number;
  compact?: boolean;
}) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  if (!swarm?.next_run) {
    return (
      <Card>
        <CardContent className={compact ? "pt-4 pb-4" : "pt-5"}>
          <div className="flex items-center justify-between mb-3">
            <span className="text-base text-slate-500 font-medium uppercase tracking-wider">Next Scan</span>
            <Zap className="w-4 h-4 text-yellow-400 opacity-60" />
          </div>
          <div className={`${compact ? "text-xl" : "text-2xl"} font-bold text-yellow-400`}>—</div>
          <div className="text-base text-slate-600 mt-1">flip swarm</div>
        </CardContent>
      </Card>
    );
  }

  const nextMs = new Date(swarm.next_run).getTime();
  const remainMs = Math.max(0, nextMs - nowMs);
  const intervalMs = intervalMinutes * 60 * 1000;
  // Countdown-style progress: full just after scheduling, drains toward zero.
  const progress = Math.min(1, Math.max(0, remainMs / intervalMs));

  const mins = Math.floor(remainMs / 60000);
  const secs = Math.floor((remainMs % 60000) / 1000);
  const label = remainMs === 0 ? "Running…" : `${mins}m ${String(secs).padStart(2, "0")}s`;

  return (
    <Card>
      <CardContent className={compact ? "pt-4 pb-4" : "pt-5"}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-base text-slate-500 font-medium uppercase tracking-wider">Next Scan</span>
          <Zap className="w-4 h-4 text-yellow-400 opacity-60" />
        </div>
        <div className={`${compact ? "text-xl" : "text-2xl"} font-bold text-yellow-400 tabular-nums`}>{label}</div>
        <div className="mt-3 h-1.5 rounded-full bg-white/5 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-1000"
            // 3-color gradient aligned to app palette (cyan -> primary -> green).
            style={{
              width: `${progress * 100}%`,
              backgroundImage: "linear-gradient(90deg, #00b8ff 0%, #a4e6ff 52%, #00dc82 100%)",
            }}
          />
        </div>
        <div className="text-base text-slate-600 mt-1.5">flip swarm · every {intervalMinutes}m</div>
      </CardContent>
    </Card>
  );
}

// ── Build category types and helpers ─────────────────────────────────────────
// TrendDir and DemandStrength are imported from @/lib/types

interface BuildCategory {
  name: string;
  emoji: string;
  count: number;
  gemCount: number;
  sparkline: number[];
  trend: TrendDir;
  strength: DemandStrength;
  insight: string;
}

const CLEARANCE_SIGNALS = new Set([
  "ex office", "office clearance", "it clearance", "job lot",
  "quick sale", "need gone", "clearing out", "no longer needed",
]);

const WORKSTATION_SIGNALS = new Set([
  "elitedesk", "optiplex", "thinkcentre", "thinkstation",
  "hp workstation", "dell workstation", "hp z240", "hp z440",
  "hp z640", "hp z420", "hp z620", "dell precision", "prodesk",
]);

function computeBuildCategories(listings: Listing[], nowMs: number): BuildCategory[] {
  const DAY = 86_400_000;
  const dayBucket = (l: Listing) =>
    Math.min(6, Math.floor((nowMs - new Date(l.first_seen_at).getTime()) / DAY));

  const defs = [
    {
      name: "Gaming PCs",
      emoji: "🎮",
      match: (l: Listing) => !!l.gpu,
      insight: (gemCount: number, _count: number, avgP: number) =>
        gemCount > 0 ? `${gemCount} gems · avg £${Math.round(avgP)} profit` : "Active category — run scan for gems",
    },
    {
      name: "No-GPU Flips",
      emoji: "⚡",
      match: (l: Listing) =>
        !l.gpu && !!l.cpu && /i5|i7|i9|ryzen/i.test(l.cpu),
      insight: (gemCount: number, count: number, avgP: number) =>
        gemCount > 0 ? `Add GPU → £${Math.round(avgP)} avg profit` : `${count} candidates — add RTX 3060 to flip`,
    },
    {
      name: "Office Clearance",
      emoji: "🏢",
      match: (l: Listing) =>
        (l.gem_signals ?? []).some(s => CLEARANCE_SIGNALS.has(s)) ||
        /clearance|job.?lot|it.?clear/i.test(l.title),
      insight: (_gemCount: number, count: number, avgP: number) =>
        avgP > 50 ? `Bulk sourcing · £${Math.round(avgP)} avg profit` : `${count} clearance listings tracked`,
    },
    {
      name: "Workstations",
      emoji: "🔧",
      match: (l: Listing) =>
        (l.gem_signals ?? []).some(s => WORKSTATION_SIGNALS.has(s)) ||
        /xeon|hp.?z\d{3}|precision|thinkstation/i.test(l.title),
      insight: (_gemCount: number, _count: number, avgP: number) =>
        avgP > 80 ? `High-margin tier · £${Math.round(avgP)} avg profit` : "Premium platform — strong resale",
    },
    {
      name: "Budget Builders",
      emoji: "💰",
      match: (l: Listing) => l.price <= 60 && !l.gpu,
      insight: (gemCount: number, count: number) =>
        gemCount > 0 ? `${gemCount}/${count} are gems — low buy-in` : `Low buy-in · ${count} sub-£60 units`,
    },
  ];

  return defs.map(def => {
    const items = listings.filter(def.match);
    if (items.length === 0) return null;

    const gems = items.filter(
      l => l.classification === "gem" || l.classification === "amazing_gem",
    );

    // Build 7-day sparkline (index 0 = 6 days ago … index 6 = today)
    const sparkline = Array.from({ length: 7 }, (_, i) => {
      const targetBucket = 6 - i;
      return items.filter(l => dayBucket(l) === targetBucket).length;
    });

    // Trend: compare most recent 3 days vs previous 3 days
    const last3 = sparkline.slice(4).reduce((a, b) => a + b, 0);
    const prev3 = sparkline.slice(1, 4).reduce((a, b) => a + b, 0);
    const trend: TrendDir =
      last3 > prev3 * 1.3 ? "rising" :
      last3 < prev3 * 0.7 ? "falling" : "stable";

    const gemRate = items.length > 0 ? gems.length / items.length : 0;
    const strength: DemandStrength =
      gemRate > 0.15 ? "High" : gemRate > 0.05 ? "Medium" : "Low";

    const profitItems = gems.filter(l => l.estimated_profit != null);
    const avgProfit =
      profitItems.length > 0
        ? profitItems.reduce((a, l) => a + (l.estimated_profit ?? 0), 0) / profitItems.length
        : 0;

    return {
      name: def.name,
      emoji: def.emoji,
      count: items.length,
      gemCount: gems.length,
      sparkline,
      trend,
      strength,
      insight: def.insight(gems.length, items.length, avgProfit),
    };
  }).filter((c): c is BuildCategory => c !== null && typeof c === "object");
}

// ── Inline sparkline ──────────────────────────────────────────────────────────
function MiniSparkline({ data, trend }: { data: number[]; trend: TrendDir }) {
  const max = Math.max(...data, 1);
  const W = 64, H = 22;
  const step = data.length > 1 ? W / (data.length - 1) : W;
  const color = trend === "rising" ? "#00dc82" : trend === "falling" ? "#ef4444" : "#64748b";

  const pts = data.map((v, i) => [i * step, H - 2 - ((v / max) * (H - 4))] as [number, number]);
  const linePts = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const first = pts[0], last = pts[pts.length - 1];
  const areaPath = `M${first[0].toFixed(1)},${H} L${linePts.replace(/ /g, " L")} L${last[0].toFixed(1)},${H} Z`;

  return (
    <svg width={W} height={H} style={{ display: "block", overflow: "visible" }}>
      <path d={areaPath} fill={color} fillOpacity={0.1} />
      <polyline
        points={linePts}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Terminal dot */}
      <circle cx={last[0].toFixed(1)} cy={last[1].toFixed(1)} r={2} fill={color} />
    </svg>
  );
}

// ── Trending Build Categories card ────────────────────────────────────────────
function TrendingCategoriesCard({ listings }: { listings: Listing[] }) {
  const categories = useMemo(
    () => computeBuildCategories(listings, TRENDING_CATEGORIES_BASE_NOW_MS),
    [listings],
  );

  const trendIcon = (t: TrendDir) =>
    t === "rising" ? "↑" : t === "falling" ? "↓" : "→";
  const trendColor = (t: TrendDir) =>
    t === "rising" ? "text-[#00dc82]" : t === "falling" ? "text-red-400" : "text-slate-500";
  const strengthColor = (s: DemandStrength) =>
    s === "High" ? "text-[#00dc82]" : s === "Medium" ? "text-amber-400" : "text-slate-500";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="w-3.5 h-3.5 text-[#00dc82]" />
          Trending Build Categories
          <span className="text-base font-normal text-slate-500 ml-1">demand signals · last 7 days</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {categories.length === 0 ? (
          <div className="px-5 py-8 text-center text-slate-600 text-base">
            Run a scan to generate demand signals
          </div>
        ) : (
          <div className="divide-y divide-white/[0.04]">
            {/* Column headers */}
            <div className="flex items-center gap-4 px-5 py-1.5">
              <span className="w-36 text-[10px] text-slate-600 uppercase tracking-wider">Category</span>
              <span className="w-16 text-[10px] text-slate-600 uppercase tracking-wider">7-day trend</span>
              <span className="w-16 text-[10px] text-slate-600 uppercase tracking-wider text-center">Demand</span>
              <span className="w-8 text-[10px] text-slate-600 uppercase tracking-wider text-center">Dir.</span>
              <span className="flex-1 text-[10px] text-slate-600 uppercase tracking-wider">Signal</span>
            </div>
            {categories.map(cat => (
              <div key={cat.name} className="flex items-center gap-4 px-5 py-2.5 hover:bg-white/[0.02] transition-colors">
                <div className="w-36 flex-shrink-0">
                  <span className="text-base font-medium text-slate-200">{cat.emoji} {cat.name}</span>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    {cat.count} listings
                    {cat.gemCount > 0 && (
                      <span className="text-[#00dc82]/70 ml-1.5">· {cat.gemCount} gem{cat.gemCount !== 1 ? "s" : ""}</span>
                    )}
                  </div>
                </div>
                <div className="w-16 flex-shrink-0">
                  <MiniSparkline data={cat.sparkline} trend={cat.trend} />
                </div>
                <div className="w-16 flex-shrink-0 text-center">
                  <span className={`text-base font-semibold ${strengthColor(cat.strength)}`}>{cat.strength}</span>
                  <div className="text-[9px] text-slate-600 mt-0.5">demand</div>
                </div>
                <div className="w-8 flex-shrink-0 text-center">
                  <span className={`text-base font-bold ${trendColor(cat.trend)}`}>{trendIcon(cat.trend)}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-base text-slate-400 truncate block">{cat.insight}</span>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="px-5 py-2 border-t border-white/[0.06] flex items-center gap-3">
          {(["rising", "stable", "falling"] as TrendDir[]).map(t => (
            <div key={t} className="flex items-center gap-1">
              <span className={`text-base font-bold ${t === "rising" ? "text-[#00dc82]" : t === "falling" ? "text-red-400" : "text-slate-500"}`}>
                {t === "rising" ? "↑" : t === "falling" ? "↓" : "→"}
              </span>
              <span className="text-[10px] text-slate-600 capitalize">{t}</span>
            </div>
          ))}
          <span className="ml-auto text-[10px] text-slate-600">from {listings.length} listings</span>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Playbook Activity Feed ────────────────────────────────────────────────────
type PlaybookTab = "additions" | "updates" | "retirements";

function PlaybookActivityCard({
  config,
  sources,
  listings,
  nowMs,
}: {
  config: SearchConfig | null;
  sources: DataSource[];
  listings: Listing[];
  nowMs: number;
}) {
  const [tab, setTab] = useState<PlaybookTab>("additions");

  const categories = computeBuildCategories(listings, nowMs);
  const cutoff24h = new Date(nowMs - 24 * 3600_000).toISOString();

  // Recent Additions: rising categories + recently discovered gem categories
  const additions = categories
    .filter(c => c.trend === "rising" || c.gemCount > 0)
    .map(c => ({
      name: c.name,
      date: new Date().toLocaleDateString("en-GB", { day: "numeric", month: "short" }),
      reason: c.trend === "rising"
        ? `↑ Rising volume · ${c.count} listings tracked`
        : `${c.gemCount} gem${c.gemCount !== 1 ? "s" : ""} found · ${c.count} in category`,
      positive: true,
    }));

  // Recent Updates: source scan activity
  const updates = sources
    .filter(s => s.enabled && s.last_scraped_at)
    .sort((a, b) => (b.last_scraped_at ?? "").localeCompare(a.last_scraped_at ?? ""))
    .map(src => {
      const recentForSrc = listings.filter(
        l => l.source_name === src.name && l.first_seen_at >= cutoff24h,
      );
      const gems = recentForSrc.filter(l => l.classification === "gem" || l.classification === "amazing_gem");
      return {
        name: src.name,
        date: src.last_scraped_at
          ? formatRelativeTime(new Date(src.last_scraped_at))
          : "—",
        reason: recentForSrc.length > 0
          ? `+${recentForSrc.length} listings added · ${gems.length} gem${gems.length !== 1 ? "s" : ""}`
          : `Scanned · ${src.listings_found_total ?? 0} total tracked`,
        positive: recentForSrc.length > 0,
      };
    });

  // Recent Retirements: disabled sources + falling/empty categories
  const retirements = [
    ...sources
      .filter(s => !s.enabled)
      .map(src => ({
        name: src.name,
        date: "Disabled",
        reason: src.last_error ? `Error: ${src.last_error.slice(0, 60)}` : "Source is disabled",
        positive: false,
      })),
    ...categories
      .filter(c => c.trend === "falling" && c.count > 0)
      .map(c => ({
        name: c.name,
        date: "↓ Declining",
        reason: `Volume dropped · ${c.count} listings remain`,
        positive: false,
      })),
  ];

  const TAB_CONFIG: { key: PlaybookTab; label: string; count: number }[] = [
    { key: "additions",   label: "Additions",   count: additions.length   },
    { key: "updates",     label: "Updates",     count: updates.length     },
    { key: "retirements", label: "Retired",     count: retirements.length },
  ];

  const rows =
    tab === "additions" ? additions :
    tab === "updates"   ? updates   : retirements;

  // Strategy summary pill (always visible at top)
  const strategyLabel = config?.intent?.replace(/_/g, " ") ?? "—";
  const priceRange = config ? `£${config.min_price}–£${config.max_price}` : "—";

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-yellow-400" />
          Playbook
        </CardTitle>
        {/* Strategy summary pill */}
        {config && (
          <div className="flex items-center gap-2 mt-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.07]">
            <span className="text-[10px] text-yellow-400 font-semibold capitalize">{strategyLabel}</span>
            <span className="text-[10px] text-slate-600">·</span>
            <span className="text-[10px] text-slate-400">{priceRange}</span>
            {config.gem_keywords?.length > 0 && (
              <>
                <span className="text-[10px] text-slate-600">·</span>
                <span className="text-[10px] text-[#00dc82]/60">{config.gem_keywords.length} gem signals</span>
              </>
            )}
          </div>
        )}
        {/* Tabs */}
        <div className="flex gap-1 mt-2">
          {TAB_CONFIG.map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] font-medium transition-colors
                ${tab === key
                  ? "bg-[#00dc82]/15 text-[#00dc82] border border-[#00dc82]/30"
                  : "text-slate-500 hover:text-slate-300 border border-transparent"}`}
            >
              {label}
              {count > 0 && (
                <span className={`rounded-full px-1 text-[9px] font-bold
                  ${tab === key ? "bg-[#00dc82]/20 text-[#00dc82]" : "bg-white/[0.06] text-slate-500"}`}>
                  {count}
                </span>
              )}
            </button>
          ))}
        </div>
      </CardHeader>

      <CardContent className="flex-1">
        <div className="overflow-y-auto" style={{ maxHeight: 220 }}>
        {rows.length === 0 ? (
          <div className="text-base text-slate-600 text-center py-6">
            {tab === "additions" && "No rising categories yet — run a scan"}
            {tab === "updates"   && "No source activity recorded yet"}
            {tab === "retirements" && "Nothing retired — all systems active"}
          </div>
        ) : (
          <div className="space-y-2.5">
            {rows.map((row, i) => (
              <div key={i} className="flex items-start gap-2.5">
                {/* Dot indicator */}
                <div className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0
                  ${row.positive ? "bg-[#00dc82]" : tab === "retirements" ? "bg-red-400/60" : "bg-slate-500"}`}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-base font-medium text-slate-200 truncate">{row.name}</span>
                    <span className="text-[10px] text-slate-600 flex-shrink-0 whitespace-nowrap">{row.date}</span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-0.5 leading-snug">{row.reason}</p>
                </div>
              </div>
            ))}
          </div>
        )}
        </div>
      </CardContent>

      {/* Current Strategy footer */}
      {config && tab === "additions" && (
        <div className="px-4 py-2.5 border-t border-white/[0.06]">
          <div className="text-[10px] text-slate-600 mb-1.5 uppercase tracking-wider">Searching for</div>
          <div className="flex flex-wrap gap-1">
            {(config.gem_keywords ?? []).slice(0, 5).map(kw => (
              <span key={kw} className="text-[10px] text-[#00dc82]/60 bg-[#00dc82]/[0.08] border border-[#00dc82]/15 rounded px-1.5 py-0.5 leading-none">
                {kw}
              </span>
            ))}
            {(config.gem_keywords?.length ?? 0) > 5 && (
              <span className="text-[10px] text-slate-600">+{(config.gem_keywords?.length ?? 0) - 5} more</span>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

// ── Current Strategy card ─────────────────────────────────────────────────────
// Shows active playbooks + top-line demand health from the real API.
function CurrentStrategyCard({
  playbooks,
  demandSummary,
}: {
  playbooks: Playbook[];
  demandSummary: DemandSummary | null;
}) {
  const health = demandSummary?.market_health ?? "warm";

  const healthConfig = {
    hot:  { label: "Hot Market",  color: "text-red-400",     bg: "bg-red-400/10 border-red-400/30",     Icon: Flame      },
    warm: { label: "Warm Market", color: "text-amber-400",   bg: "bg-amber-400/10 border-amber-400/30", Icon: Thermometer },
    cold: { label: "Cold Market", color: "text-blue-400",    bg: "bg-blue-400/10 border-blue-400/30",   Icon: Snowflake   },
  } as const;

  const hc = healthConfig[health];

  const flipStructureLabel: Record<string, string> = {
    buy_upgrade_sell: "Buy → Upgrade → Sell",
    buy_clean_sell:   "Buy → Clean → Sell",
    bulk_lot:         "Bulk Lot",
  };

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BookOpen className="w-3.5 h-3.5 text-violet-400" />
          Current Strategy
          <Link href="/playbooks" className="ml-auto text-[10px] text-slate-500 hover:text-[#00dc82] transition-colors flex items-center gap-1">
            Manage <ArrowRight className="w-3 h-3" />
          </Link>
        </CardTitle>
        {/* Market health pill */}
        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-base font-semibold w-fit mt-1 ${hc.bg} ${hc.color}`}>
          <hc.Icon className="w-3.5 h-3.5" />
          {hc.label}
          {demandSummary && (
            <span className="font-normal text-slate-400 ml-1">
              · {demandSummary.gem_rate_pct}% gem rate · {demandSummary.total_listings} listings
            </span>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex-1">
        {playbooks.length === 0 ? (
          <div className="text-center py-8 text-slate-600 text-base">
            <BookOpen className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p>No active playbooks</p>
            <Link href="/playbooks" className="text-base text-[#00dc82]/70 hover:text-[#00dc82] mt-1 inline-block">
              Create your first playbook →
            </Link>
          </div>
        ) : (
          <div className="space-y-2.5">
            {playbooks.slice(0, 4).map(pb => {
              const ss = pb.search_strategy || {};
              const ps = pb.profit_strategy || {};
              const kwCount = (ss.keywords || []).length;
              const structure = flipStructureLabel[ps.flip_structure || ""] || ps.flip_structure || "—";
              const matchedCat = demandSummary?.categories.find(
                c => c.use_case === pb.target_use_case
              );
              return (
                <div key={pb.id} className="flex items-start gap-3 p-2.5 rounded-xl bg-[#111c2e] border border-[#1e2d45] hover:border-[#2a3d5c] transition-colors">
                  <span className="text-xl flex-shrink-0 mt-0.5">{pb.emoji || "🖥️"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-base font-semibold text-slate-100 truncate">{pb.name}</span>
                      {matchedCat && (
                        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border ${
                          matchedCat.strength === "High"   ? "bg-[#00dc82]/10 border-[#00dc82]/30 text-[#00dc82]" :
                          matchedCat.strength === "Medium" ? "bg-amber-400/10 border-amber-400/30 text-amber-400" :
                                                             "bg-slate-400/10 border-slate-400/30 text-slate-400"
                        }`}>
                          {matchedCat.trend === "rising" ? "↑" : matchedCat.trend === "falling" ? "↓" : "→"} {matchedCat.strength}
                        </span>
                      )}
                    </div>
                    <div className="flex gap-3 mt-1 flex-wrap">
                      {ss.price_min != null && ss.price_max != null && (
                        <span className="text-[10px] text-slate-500">£{ss.price_min}–£{ss.price_max}</span>
                      )}
                      {kwCount > 0 && (
                        <span className="text-[10px] text-slate-500">{kwCount} keywords</span>
                      )}
                      {ps.target_profit_gbp != null && (
                        <span className="text-[10px] text-[#00dc82]/70">£{ps.target_profit_gbp} target</span>
                      )}
                      <span className="text-[10px] text-slate-600">{structure}</span>
                    </div>
                  </div>
                </div>
              );
            })}
            {playbooks.length > 4 && (
              <Link href="/playbooks" className="block text-center text-base text-slate-500 hover:text-[#00dc82] transition-colors py-1">
                +{playbooks.length - 4} more active playbooks
              </Link>
            )}
          </div>
        )}
      </CardContent>

      {demandSummary && (
        <div className="px-4 py-2.5 border-t border-white/[0.06] flex items-center gap-3 text-base text-slate-500">
          {demandSummary.rising_count > 0 && (
            <span className="text-[#00dc82]">↑ {demandSummary.rising_count} rising</span>
          )}
          {demandSummary.falling_count > 0 && (
            <span className="text-red-400">↓ {demandSummary.falling_count} falling</span>
          )}
          {demandSummary.hottest_category && (
            <span className="ml-auto text-slate-600">🔥 {demandSummary.hottest_category.name}</span>
          )}
        </div>
      )}
    </Card>
  );
}

// ── Auction Intelligence card ──────────────────────────────────────────────────
function AuctionIntelCard({ auctions }: { auctions: AuctionIntelItem[] }) {
  function fmtTime(secs: number | null): string {
    if (secs == null) return "—";
    if (secs < 60) return `${secs}s`;
    if (secs < 3600) return `${Math.floor(secs / 60)}m`;
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    return `${h}h ${m}m`;
  }

  const endingSoon = auctions.filter(a => a.urgency === "ending_soon");
  const today      = auctions.filter(a => a.urgency === "today");
  const upcoming   = auctions.filter(a => a.urgency === "upcoming");
  const ordered    = [...endingSoon, ...today, ...upcoming].slice(0, 8);

  const classColor: Record<string, string> = {
    amazing_gem: "text-cyan-400",
    gem:         "text-[#00dc82]",
    no_profit:   "text-red-400",
    overpriced:  "text-orange-400",
    unclassified:"text-slate-500",
  };

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gavel className="w-3.5 h-3.5 text-amber-400" />
          Auction Intelligence
          {endingSoon.length > 0 && (
            <span className="ml-1 text-base font-semibold text-amber-400 bg-amber-400/10 border border-amber-400/30 px-2 py-0.5 rounded-full animate-pulse">
              {endingSoon.length} ending soon
            </span>
          )}
        </CardTitle>
        {auctions.length > 0 && (
          <div className="flex gap-3 text-base text-slate-500 mt-1">
            {endingSoon.length > 0 && <span className="text-amber-400">🔴 {endingSoon.length} &lt;1h</span>}
            {today.length > 0      && <span className="text-yellow-400">🟡 {today.length} today</span>}
            {upcoming.length > 0   && <span className="text-slate-400">⚪ {upcoming.length} upcoming</span>}
          </div>
        )}
      </CardHeader>

      <CardContent className="flex-1">
        {ordered.length === 0 ? (
          <div className="text-center py-8 text-slate-600 text-base">
            <Gavel className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p>No live auctions tracked</p>
            <p className="text-base mt-1 text-slate-700">Auctions appear here when scraped from eBay</p>
          </div>
        ) : (
          <div className="space-y-2">
            {ordered.map(a => {
              const isGem = a.classification === "gem" || a.classification === "amazing_gem";
              const urgColor =
                a.urgency === "ending_soon" ? "border-amber-400/40 bg-amber-400/5" :
                a.urgency === "today"        ? "border-yellow-400/20 bg-transparent" :
                                               "border-[#1e2d45] bg-transparent";
              return (
                <a key={a.id} href={a.url} target="_blank" rel="noopener noreferrer"
                  className={`flex items-center gap-2.5 p-2.5 rounded-xl border hover:border-[#2a3d5c] transition-colors ${urgColor}`}>
                  <div className="w-10 h-10 flex-shrink-0 rounded-lg overflow-hidden bg-[#0d1726]">
                    {a.image_url
                      ? <img src={a.image_url} alt="" className="w-full h-full object-cover" />
                      : <div className="w-full h-full flex items-center justify-center"><Gavel className="w-4 h-4 text-slate-600" /></div>
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-base font-medium text-slate-200 truncate">{a.title}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      {a.cpu && <span className="text-[10px] text-slate-500 truncate max-w-[90px]">{a.cpu}</span>}
                      {a.gpu && <span className="text-[10px] text-slate-500 truncate max-w-[70px]">{a.gpu}</span>}
                    </div>
                  </div>
                  <div className="flex-shrink-0 text-right">
                    <div className={`flex items-center gap-1 justify-end text-[10px] font-bold ${
                      a.urgency === "ending_soon" ? "text-amber-400" :
                      a.urgency === "today"        ? "text-yellow-400" : "text-slate-500"
                    }`}>
                      <Clock className="w-2.5 h-2.5" />
                      {fmtTime(a.time_left_secs)}
                    </div>
                    <div className="text-base font-semibold text-slate-300">
                      £{(a.expected_buy_price ?? a.price).toFixed(0)}
                    </div>
                    {a.estimated_profit != null && (
                      <div className={`text-[10px] font-bold ${a.estimated_profit > 0 ? (classColor[a.classification] || "text-[#00dc82]") : "text-red-400"}`}>
                        {a.estimated_profit > 0 ? "+" : ""}£{a.estimated_profit.toFixed(0)}
                      </div>
                    )}
                    {isGem && <div className="text-[9px] text-[#00dc82]">💎</div>}
                  </div>
                </a>
              );
            })}
          </div>
        )}
      </CardContent>

      {auctions.length > 8 && (
        <div className="px-4 py-2.5 border-t border-white/[0.06]">
          <Link href="/opportunities" className="text-base text-slate-500 hover:text-[#00dc82] transition-colors">
            View all {auctions.length} auctions →
          </Link>
        </div>
      )}
    </Card>
  );
}
