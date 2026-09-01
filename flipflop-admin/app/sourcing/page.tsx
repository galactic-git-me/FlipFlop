"use client";

import { memo, Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { RefreshCw, BarChart3, Gem, Flame, Loader2, Clock, CheckCircle2, AlertTriangle, MinusCircle, Timer, Info, X, History } from "lucide-react";
import PixelCard from "../../components/ui/PixelCard";
import { VendorLogo } from "../../components/VendorLogo";
import { PriceHistorySparkline } from "../../components/listings/PriceHistorySparkline";
import { api, MarketSnapshot } from "@/lib/api";
import { fuzzyMatches } from "@/lib/fuzzy";
import { VENDOR_ORDER, VENDOR_META } from "@/lib/vendors";
import {
  ScatterChart,
  Scatter,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface Listing {
  id: number;
  listing_id: string;
  source: string;
  url: string;
  category: string | null;
  title: string;
  seller?: string;
  image_url?: string | null;
  condition?: string | null;
  actual_price: number;
  delivered_price: number;
  market_new_price?: number;
  market_used_price?: number;
  // Only set by the CPK/Phase2 classification pathway (phase2_runner.py) —
  // market_new_price/market_used_price above are never populated by it, so
  // these are the actual price + offset a listing was classified against.
  market_lower_price?: number | null;
  market_median_price?: number | null;
  market_upper_price?: number | null;
  pct_offset?: number | null;
  watch_count?: number | null;
  best_offer_enabled?: boolean;
  classification: string;
  deal_score: number;
  confidence: string;
  decision: string;
  expected_profit?: number | null;
  roi_pct?: number | null;
  walk_away_price?: number | null;
  conservative_resale_price?: number | null;
  market_confidence?: number | null;
  market_sample_size?: number | null;
  market_source_diversity?: number | null;
  market_spread_pct?: number | null;
  liquidity_score?: number | null;
  desirability_score?: number | null;
  risk_score?: number | null;
  eligible?: boolean;
  scoring_explanation?: { reasons?: string[]; risk_flags?: string[]; cost_breakdown?: Record<string, number>; market?: { comparable_urls?: string[]; basis?: string; realisation_factor?: number } } | null;
  release_year: number | null;
  scored_at: string;
  listing_observed_at: string | null;
  search_run_id: string | null;
}

interface GemData {
  title: string;
  price: number;
  seller?: string;
  condition: string;
  url: string;
  image_url?: string | null;
  cpu?: string | null;
  category?: string;
}

interface QueueStatus {
  pending: number;
  processing: number;
  completed: number;
  failed: number;
}

interface QueueItem {
  id: number;
  query: string;
  status: "pending" | "processing";
  listings_count: number;
}

interface ScanProgress {
  searchId: string;
  query: string;
  elapsedSeconds: number;
  activeSubmissions: number;
  totalListings: number;
  ingestedCount: number;
  ingestedNewCount: number;
  cpkAssignedCount: number;
  marketPricedCount: number; // Listings with non-null market price
  classifiedCount: number;   // Listings with classification (GEM, SUPER_GEM, etc)
  processedPercent: number;  // % through full pipeline
  excludedAuctionCount: number;
  byVendor: Record<string, number>;
  isComplete: boolean;
  // Demand signals (average across active search's listings)
  avgWatchCount?: number;
  avgBidCount?: number;
  // Vendors this search term is configured to query, from source_search_terms
  // (see app/api/gem_radar.py's pipeline-status endpoint) — falls back to
  // VENDOR_ORDER (all vendors) when a search has no specific configuration.
  configuredVendors?: string[];
}

interface PipelineStatusResponse {
  activeScans: ScanProgress[];
  recentHistory: Array<{ query: string; total_listings: number; ingested_count: number; elapsed_s: number; failed: boolean }>;
  binPricesCount: number;
  soldPricesCount: number;
  superGemCount: number;
  gemCount: number;
  avgGemScore: number;
  avgSuperGemScore: number;
  totalsAcrossActive: {
    listings: number;
    ingestedCount: number;
    cpkAssignedCount: number;
    marketPricedCount: number;
    classifiedCount: number;
  };
}

// Search terms are composed with a long tail of exclusion keywords (see
// FlipFlopXtension's composeSearchQuery -- "-bundle -combo -laptop -"cooler
// only"" etc.) that are meaningful to the scraper but just noise on a small
// dashboard card. Strips both quoted multi-word exclusions (-"cooler only")
// and single-word ones (-bundle), leaving only the positive search term.
function stripNegations(query: string): string {
  return query
    .replace(/-"[^"]*"/g, "")
    .replace(/-\S+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// Sort order matches FlipFlopXtension/src/lib/search-defs.ts DEFAULT_SEARCH_DEFINITIONS
const SEARCH_ORDER = [
  "amd-cpu",
  "intel-cpu",
  "nvidia-gpu",
  "amd-gpu",
  "intel-gpu",
  "asus-motherboard",
  "msi-motherboard",
  "gigabyte-motherboard",
  "ddr4-udimm-ram",
  "ddr5-udimm-ram",
  "m2-nvme-ssd",
  "psu-gold-750w-modular",
  "cpu-cooler",
  "pc-case-chassis",
  "lian-li-pc-case",
] as const;

function sortScansByDefinitionOrder(scans: ScanProgress[]): ScanProgress[] {
  return [...scans].sort((a, b) => {
    const aIdx = SEARCH_ORDER.indexOf(a.searchId as (typeof SEARCH_ORDER)[number]);
    const bIdx = SEARCH_ORDER.indexOf(b.searchId as (typeof SEARCH_ORDER)[number]);
    if (aIdx === -1 && bIdx === -1) return 0;
    if (aIdx === -1) return 1;
    if (bIdx === -1) return -1;
    return aIdx - bIdx;
  });
}

// Small circular gauge -- replaces the earlier linear progress bars per
// request. `value`/`max` drive the sweep angle; the label underneath gives
// the raw fraction since a gauge alone can't show absolute counts.
function Gauge({ value, max, label, color }: { value: number; max: number; label: string; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const radius = 24;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct / 100);
  return (
    <div className="flex flex-col items-center justify-center">
      <svg width={60} height={60} viewBox="0 0 60 60">
        <circle cx={30} cy={30} r={radius} stroke="#1e293b" strokeWidth={6} fill="none" />
        <circle
          cx={30}
          cy={30}
          r={radius}
          stroke={color}
          strokeWidth={6}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 30 30)"
          className="transition-all duration-500"
        />
        <text x={30} y={34} textAnchor="middle" className="fill-slate-100 text-[12px] font-semibold">
          {Math.round(pct)}%
        </text>
      </svg>
      <div className="text-[11px] text-slate-400 -mt-1 text-center">{label}</div>
      <div className="text-[11px] text-slate-300 text-center">{value}/{max}</div>
    </div>
  );
}

// Gauge that shows total count with new count highlighted in green
function GaugeWithBreakdown({
  value,
  max,
  newCount,
  label,
  color,
}: {
  value: number;
  max: number;
  newCount: number;
  label: string;
  color: string;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const radius = 24;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct / 100);
  return (
    <div className="flex flex-col items-center justify-center">
      <svg width={60} height={60} viewBox="0 0 60 60">
        <circle cx={30} cy={30} r={radius} stroke="#1e293b" strokeWidth={6} fill="none" />
        <circle
          cx={30}
          cy={30}
          r={radius}
          stroke={color}
          strokeWidth={6}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 30 30)"
          className="transition-all duration-500"
        />
        <text x={30} y={34} textAnchor="middle" className="fill-slate-100 text-[12px] font-semibold">
          {Math.round(pct)}%
        </text>
      </svg>
      <div className="text-[11px] text-slate-400 -mt-1 text-center">{label}</div>
      <div className="text-[11px] text-slate-300 text-center">
        {value}/{max}
        {newCount > 0 && (
          <span className="text-emerald-400 font-semibold ml-1">({newCount} new)</span>
        )}
      </div>
    </div>
  );
}

// A dash means the API did not report data for this vendor. This is distinct
// from a real zero returned for a vendor explicitly configured for the scan.
function VendorCounter({ value }: { value: number | null }) {
  return (
    <div className="text-center">
      <div
        className={`text-sm font-bold ${value == null ? "text-slate-500" : "text-slate-100"}`}
        title={value == null ? "No vendor data reported for this scan" : `${value} listings`}
      >
        {value ?? "—"}
      </div>
    </div>
  );
}

// Compact right-justified number, replaces the old full-size stat tile grid
// -- now lives on the same header row as "Current Scan Run" and the queue
// status bar instead of its own section further down the page.
function MiniStat({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="text-center leading-tight">
      <div className="text-xl font-bold" style={{ color }}>
        {value}
      </div>
      <div className="text-xs text-slate-400 whitespace-nowrap">{label}</div>
    </div>
  );
}

function formatElapsedTime(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hrs > 0) return `${hrs}h ${mins}m ${secs}s`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

function PipelineDashboard({ queueStatus }: { queueStatus: QueueStatus | null }) {
  const [status, setStatus] = useState<PipelineStatusResponse | null>(null);
  const [queueItems, setQueueItems] = useState<QueueItem[]>([]);
  const [clientElapsed, setClientElapsed] = useState(0);
  const [displayedScans, setDisplayedScans] = useState<ScanProgress[]>([]);
  const [lastRunLength, setLastRunLength] = useState(0);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const [res, queueRes] = await Promise.all([
          fetch("/api/gem-radar/pipeline-status", { cache: "no-store" }),
          fetch("/api/gem-radar/queue-items", { cache: "no-store" }),
        ]);
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
          const activeScans = data.activeScans ?? [];

          if (activeScans.length > 0) {
            setClientElapsed(activeScans[0].elapsedSeconds ?? 0);
            // If this is a new run (different length), reset displayed scans
            if (activeScans.length !== lastRunLength) {
              setLastRunLength(activeScans.length);
              setDisplayedScans(activeScans);
            } else {
              // Same run, update displayed scans with new data
              setDisplayedScans(activeScans);
            }
          } else if (displayedScans.length > 0) {
            // Backend's activeScans went empty -- it already called reset_run()
            // and archived this run into recentHistory (see pipeline_status.py).
            // Keep the cards visible until the next run starts, but flip them to
            // "complete" instead of leaving them frozen mid-progress: without this,
            // a card's isComplete/activeSubmissions/percentages stay stuck at
            // whatever they were on the LAST poll before the backend cleared its
            // state, which reads as a stalled/hung run even though it finished.
            setDisplayedScans((prev) =>
              prev.some((scan) => !scan.isComplete || scan.activeSubmissions !== 0)
                ? prev.map((scan) => ({ ...scan, isComplete: true, activeSubmissions: 0 }))
                : prev
            );
            setClientElapsed(0);
          }
        }
        if (queueRes.ok) {
          const queueData = await queueRes.json();
          setQueueItems(queueData.items ?? []);
        }
      } catch (error) {
        console.error("Error fetching pipeline status:", error);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 1000); // Update every second
    return () => clearInterval(interval);
  }, [lastRunLength, displayedScans.length]);

  useEffect(() => {
    const isProcessing = queueStatus && queueStatus.pending > 0;
    if (!isProcessing) {
      setClientElapsed(0);
      return;
    }

    const timer = setInterval(() => {
      setClientElapsed((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [queueStatus]);

  const isRunning = queueStatus && queueStatus.pending > 0;

  // Sourced from pipeline-status, scoped to THIS run's listing_ids -- NOT
  // derived from the whole-DB `listings` array (see pipeline_status.py's
  // snapshot() docstring for why that was wrong: Phase 2 re-classifies the
  // entire database under one constant search_run_id every pass, so
  // filtering the whole-DB listings array here was showing thousands of
  // SUPER_GEMs/GEMs for a run that had only ingested a few hundred).
  const superGemCount = status?.superGemCount ?? 0;
  const gemCount = status?.gemCount ?? 0;
  const avgSuperGemScore = status?.avgSuperGemScore ?? 0;
  const avgGemScore = status?.avgGemScore ?? 0;

  return (
    <div className="mb-6 p-4 rounded-lg glass-panel">
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="w-64 shrink-0">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-white">Current Scan Run</h3>
              {isRunning && (
                <div className="inline-flex items-center gap-1 px-2 py-1 rounded bg-blue-950/50 border border-blue-800">
                  <Clock size={12} className="text-blue-400 animate-pulse" />
                  <span className="text-xs text-blue-300 font-mono">{formatElapsedTime(clientElapsed)}</span>
                </div>
              )}
            </div>
            <p className="text-xs text-slate-400">
              {displayedScans.length} search{displayedScans.length !== 1 ? "es" : ""} in this run
            </p>
          </div>
          <div className="flex items-center gap-4">
            <QueueStatusBar queue={queueStatus} />
            <MiniStat label="Listings" value={status?.totalsAcrossActive.ingestedCount ?? 0} color="#e2e8f0" />
            <MiniStat label="SUPER GEMs" value={superGemCount} color="#fcd34d" />
            <MiniStat label="GEMs" value={gemCount} color="#93c5fd" />
            <MiniStat label="Avg Gem" value={avgGemScore.toFixed(1)} color="#93c5fd" />
            <MiniStat label="Avg Super Gem" value={avgSuperGemScore.toFixed(1)} color="#fcd34d" />
            <MiniStat label="BIN Prices" value={status?.binPricesCount ?? 0} color="#34d399" />
            <MiniStat label="Sold Prices" value={status?.soldPricesCount ?? 0} color="#f472b6" />
          </div>
        </div>

        {displayedScans.length === 0 ? (
          <p className="text-xs text-slate-500">No scans to display.</p>
        ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          {sortScansByDefinitionOrder(displayedScans).map((scan) => {
            // Preserve a consistent vendor row. When configuration metadata is
            // absent, an unreported vendor gets null (rendered as an em dash),
            // not a fabricated zero.
            const searchConfiguredVendors = scan.configuredVendors;
            // Render every vendor byVendor actually reports, not just the ones
            // in the hardcoded VENDOR_ORDER list -- a source key that isn't in
            // that list (e.g. "unknown", or a newly-scraped marketplace not
            // yet added here) used to be silently dropped from the tile row
            // while still counting toward the gauges' denominator above,
            // making the displayed vendor sum quietly undercount the total.
            const knownVendorEntries = VENDOR_ORDER
              .filter((v) => !searchConfiguredVendors || searchConfiguredVendors.includes(v))
              .map((v): [string, number | null] => [
                v,
                Object.prototype.hasOwnProperty.call(scan.byVendor || {}, v)
                  ? scan.byVendor[v]
                  : searchConfiguredVendors
                    ? 0
                    : null,
              ]);
            const extraVendorEntries = Object.entries(scan.byVendor || {})
              .filter(([v, count]) => count > 0 && !(VENDOR_ORDER as readonly string[]).includes(v))
              .sort((a, b) => b[1] - a[1]);
            const vendorEntries = [...knownVendorEntries, ...extraVendorEntries];
            const searchTermTotal = Object.values(scan.byVendor || {}).reduce((sum, count) => sum + count, 0) || 1;
            const { isComplete } = scan;

            return (
              <PixelCard key={scan.searchId ?? scan.query} variant={isComplete ? "emerald" : "default"}>
                <div className={`p-2 space-y-2 ${isComplete ? "opacity-80" : ""}`}>
                  <div className="flex justify-between items-start gap-2 min-w-0">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-slate-100 truncate" title={scan.query}>
                        {stripNegations(scan.query)}
                      </div>
                      <div className="text-[11px] text-slate-400 truncate">
                        {isComplete
                          ? "Complete"
                          : `${scan.activeSubmissions} page${scan.activeSubmissions !== 1 ? "s" : ""} in flight`}{" "}
                        • {scan.elapsedSeconds}s
                        {scan.excludedAuctionCount > 0 && <> • {scan.excludedAuctionCount} auctions excl.</>}
                      </div>
                      <div
                        className="text-[11px] font-medium text-green-400"
                        title="New listings ingested this run (not a dupe of a previous run)"
                      >
                        +{scan.ingestedNewCount}
                      </div>
                    </div>
                    <span
                      className="shrink-0"
                      title={isComplete ? "Complete" : scan.ingestedCount === 0 ? "Not started" : "Processing"}
                    >
                      {isComplete ? (
                        <CheckCircle2 size={15} className="text-emerald-400" />
                      ) : scan.ingestedCount === 0 ? (
                        <MinusCircle size={15} className="text-slate-500" />
                      ) : (
                        <Loader2 size={15} className="text-blue-400 animate-spin" />
                      )}
                    </span>
                  </div>

                  <div className="flex justify-center gap-3">
                    <Gauge value={scan.ingestedCount} max={searchTermTotal} label="Ingested" color="#8b5cf6" />
                    <Gauge value={scan.cpkAssignedCount} max={searchTermTotal} label="CPK" color="#10b981" />
                    <Gauge value={scan.marketPricedCount} max={searchTermTotal} label="M Prices" color="#f59e0b" />
                    <Gauge value={scan.classifiedCount} max={searchTermTotal} label="Scores" color="#ec4899" />
                  </div>

                  {vendorEntries.length > 0 && (
                    <div className="flex justify-center gap-2 pt-1 border-t border-slate-600 flex-wrap">
                      {vendorEntries.map(([vendor, count]) => {
                        const meta = VENDOR_META[vendor] ?? VENDOR_META.unknown;
                        return (
                          <div key={vendor} className="flex flex-col items-center gap-1">
                            <VendorCounter value={count} />
                            <VendorLogo vendor={vendor} />
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </PixelCard>
            );
          })}
        </div>
        )}
      </div>
    </div>
  );
}

// Whole-DB "most up to date view of the market" — every currently-active
// listing, not just the latest scan run (see PipelineDashboard's "Current
// Scan Run" panel above, which this sits beside). Same categories, same
// MiniStat visual language, deliberately so the two read as a matched pair:
// "what just happened" vs "where things stand right now".
function MarketSnapshotPanel({ snapshot }: { snapshot: MarketSnapshot | null }) {
  return (
    <div className="mb-6 p-4 rounded-lg glass-panel">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="w-64 shrink-0">
          <h3 className="text-sm font-semibold text-white">Market Snapshot</h3>
          <p className="text-xs text-slate-400">Every currently-active listing in the DB, not just this run</p>
        </div>
        <div className="flex items-center gap-4">
          <MiniStat label="Listings" value={snapshot?.ingestedCount ?? 0} color="#e2e8f0" />
          <MiniStat label="SUPER GEMs" value={snapshot?.superGemCount ?? 0} color="#fcd34d" />
          <MiniStat label="GEMs" value={snapshot?.gemCount ?? 0} color="#93c5fd" />
          <MiniStat label="Avg Gem" value={(snapshot?.avgGemScore ?? 0).toFixed(1)} color="#93c5fd" />
          <MiniStat label="Avg Super Gem" value={(snapshot?.avgSuperGemScore ?? 0).toFixed(1)} color="#fcd34d" />
          <MiniStat label="BIN Prices" value={snapshot?.binPricesCount ?? 0} color="#34d399" />
          <MiniStat label="Sold Prices" value={snapshot?.soldPricesCount ?? 0} color="#f472b6" />
        </div>
      </div>
    </div>
  );
}

// eslint-disable-next-line @next/next/no-img-element -- external eBay-hosted
// thumbnails; next/image's domain allowlist isn't worth configuring for a
// scraper whose image hosts vary listing to listing.
function ListingThumbnail({ src, alt, size = 40 }: { src?: string | null; alt: string; size?: number }) {
  if (!src) {
    return (
      <div
        className="flex items-center justify-center bg-slate-700 rounded text-slate-500 shrink-0"
        style={{ width: size, height: size, fontSize: Math.max(10, size / 8) }}
      >
        —
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      className="rounded object-contain shrink-0 bg-slate-700"
      style={{ width: size, height: size }}
      onError={(e) => {
        (e.target as HTMLImageElement).style.display = "none";
      }}
    />
  );
}

type ComponentType = "CPU" | "Motherboard" | "RAM" | "PSU" | "SSD" | "GPU" | "Cooler" | "Fan" | "Case" | "Other";
type MainTab = "stats" | "listings" | "analytics";

const COMPONENT_TABS: ComponentType[] = [
  "CPU",
  "Motherboard",
  "RAM",
  "PSU",
  "SSD",
  "GPU",
  "Cooler",
  "Fan",
  "Case",
  "Other",
];

// Maps the backend's authoritative category (app/gem_radar/identity.py —
// requires an actual model-number match for cpu/gpu, and excludes
// packaging/protector/bracket listings via is_likely_accessory) onto this
// page's display tabs. Deliberately NOT re-derived from the title here: an
// earlier version of this file did its own naive keyword scan (bare "cpu"/
// "processor" substring matching) which let CPU coolers, protector cases,
// and mounting brackets whose titles merely *mention* "CPU" flood the CPU
// tab. The backend category is already accessory-filtered — trust it.
const CATEGORY_TO_TAB: Record<string, ComponentType> = {
  cpu: "CPU",
  motherboard: "Motherboard",
  ram: "RAM",
  psu: "PSU",
  ssd: "SSD",
  gpu: "GPU",
  cooler: "Cooler",
  fan: "Fan",
  case: "Case",
};

function listingTab(listing: Listing): ComponentType {
  return (listing.category && CATEGORY_TO_TAB[listing.category]) || "Other";
}

// Minimum distinct vendors before the vendor-diversity gauge reads fully green.
// Sourcing currently only scrapes eBay, so 1 vendor pegs it red on purpose —
// it's meant to flag the missing-vendor-diversity problem, not hide it.
const VENDOR_DIVERSITY_TARGET = 3;
const RAG_RED_MAX = 40;
const RAG_AMBER_MAX = 70;

function ragColor(value: number): string {
  if (value < RAG_RED_MAX) return "#ef4444";
  if (value < RAG_AMBER_MAX) return "#f59e0b";
  return "#10b981";
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const angleRad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(angleRad), y: cy - r * Math.sin(angleRad) };
}

function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number): string {
  const start = polarToCartesian(cx, cy, r, startAngle);
  const end = polarToCartesian(cx, cy, r, endAngle);
  const largeArcFlag = Math.abs(startAngle - endAngle) <= 180 ? "0" : "1";
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 1 ${end.x} ${end.y}`;
}

function RagGauge({ label, value, sublabel }: { label: string; value: number; sublabel: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  const cx = 100;
  const cy = 100;
  const r = 80;
  const redEndAngle = 180 - (RAG_RED_MAX / 100) * 180;
  const amberEndAngle = 180 - (RAG_AMBER_MAX / 100) * 180;
  const needleAngle = 180 - (clamped / 100) * 180;
  const needleTip = polarToCartesian(cx, cy, r - 12, needleAngle);
  const color = ragColor(clamped);

  return (
    <div className="p-3 bg-slate-800 rounded border border-slate-700 flex flex-col items-center">
      <svg viewBox="0 0 200 110" className="w-full max-w-[180px]">
        <path d={describeArc(cx, cy, r, 180, redEndAngle)} stroke="#ef4444" strokeWidth={16} fill="none" strokeLinecap="butt" />
        <path d={describeArc(cx, cy, r, redEndAngle, amberEndAngle)} stroke="#f59e0b" strokeWidth={16} fill="none" strokeLinecap="butt" />
        <path d={describeArc(cx, cy, r, amberEndAngle, 0)} stroke="#10b981" strokeWidth={16} fill="none" strokeLinecap="butt" />
        <line x1={cx} y1={cy} x2={needleTip.x} y2={needleTip.y} stroke="#e2e8f0" strokeWidth={3} strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={6} fill="#e2e8f0" />
      </svg>
      <div className="text-2xl font-bold -mt-2" style={{ color }}>{clamped.toFixed(0)}%</div>
      <div className="text-xs text-slate-300 font-semibold">{label}</div>
      <div className="text-xs text-slate-500 text-center">{sublabel}</div>
    </div>
  );
}

function PipelineHealthPanel({ listings }: { listings: Listing[] }) {
  const withMarketNew = listings.filter((l) => l.market_new_price != null).length;
  const withMarketUsed = listings.filter((l) => l.market_used_price != null).length;
  const withAnyPrice = listings.filter((l) => l.market_new_price != null || l.market_used_price != null).length;
  const withCategory = listings.filter((l) => l.category != null).length;
  const noPricing = listings.filter((l) => l.market_new_price == null && l.market_used_price == null).length;
  const both = listings.filter((l) => l.market_new_price != null && l.market_used_price != null).length;

  const total = listings.length;
  const pricingRate = total > 0 ? (withAnyPrice / total) * 100 : 0;
  const categoryRate = total > 0 ? (withCategory / total) * 100 : 0;
  const vendorCount = new Set(listings.map((l) => l.source)).size;
  const vendorRate = Math.min(100, (vendorCount / VENDOR_DIVERSITY_TARGET) * 100);

  // Prepare data for bar chart
  const pipelineData = [
    { name: "Scraped", value: total, color: "#64748b" },
    { name: "Identified", value: withCategory, color: "#3b82f6" },
    { name: "Priced", value: withAnyPrice, color: "#10b981" },
  ];

  const priceBreakdownData = [
    { name: "Both New+Used", value: both, color: "#10b981" },
    { name: "New Only", value: withMarketNew - both, color: "#60a5fa" },
    { name: "Used Only", value: withMarketUsed - both, color: "#34d399" },
    { name: "No Prices", value: noPricing, color: "#ef4444" },
  ];

  const maxValue = Math.max(...pipelineData.map((d) => d.value), 1);

  return (
    <div className="space-y-6">
      <div>
        <div className="text-sm font-semibold text-slate-100 mb-4">Pipeline Flow</div>
        <p className="text-xs text-slate-400 mb-4">
          Scrapes → Identity Matching → Market Price Retrieval
        </p>
        <div className="space-y-3">
          {pipelineData.map((stage, idx) => {
            const pct = maxValue > 0 ? ((stage.value / maxValue) * 100).toFixed(0) : 0;
            return (
              <div key={stage.name}>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-slate-300">{stage.name}</span>
                  <span className="text-xs font-semibold text-slate-100">{stage.value}</span>
                </div>
                <div className="h-8 bg-slate-700 rounded overflow-hidden border border-slate-600">
                  <div
                    className="h-full flex items-center justify-center text-xs font-bold text-white transition-all"
                    style={{ width: `${pct}%`, backgroundColor: stage.color }}
                  >
                    {pct !== "0" && `${pct}%`}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <div className="text-sm font-semibold text-slate-100 mb-4">Market Price Coverage</div>
          <div className="space-y-2">
            {priceBreakdownData.map((item) => (
              <div key={item.name} className="flex items-center justify-between p-2 bg-slate-800 rounded border border-slate-700">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: item.color }} />
                  <span className="text-xs text-slate-300">{item.name}</span>
                </div>
                <span className="text-sm font-semibold text-slate-100">{item.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="text-sm font-semibold text-slate-100 mb-4">Overall Rates</div>
          <div className="grid grid-cols-3 gap-2">
            <RagGauge label="Vendor Diversity" value={vendorRate} sublabel={`${vendorCount} vendor${vendorCount === 1 ? "" : "s"} (target ${VENDOR_DIVERSITY_TARGET}+)`} />
            <RagGauge label="Priced Up" value={pricingRate} sublabel={`${withAnyPrice} / ${total}`} />
            <RagGauge label="Identified" value={categoryRate} sublabel={`${withCategory} / ${total}`} />
          </div>
        </div>
      </div>
    </div>
  );
}

const GEM_SPOTLIGHT_ACCENTS = {
  amber: { label: "text-amber-300", price: "text-amber-200", ring: "ring-amber-400/30", glow: "from-amber-500/20" },
  blue: { label: "text-blue-300", price: "text-blue-200", ring: "ring-blue-400/30", glow: "from-blue-500/20" },
  cyan: { label: "text-cyan-300", price: "text-cyan-200", ring: "ring-cyan-400/30", glow: "from-cyan-500/20" },
  purple: { label: "text-purple-300", price: "text-purple-200", ring: "ring-purple-400/30", glow: "from-purple-500/20" },
  emerald: { label: "text-emerald-300", price: "text-emerald-200", ring: "ring-emerald-400/30", glow: "from-emerald-500/20" },
  orange: { label: "text-orange-300", price: "text-orange-200", ring: "ring-orange-400/30", glow: "from-orange-500/20" },
} as const;

function GemSpotlightCard({
  gem,
  label,
  accent,
}: {
  gem: GemData;
  label: string;
  accent: keyof typeof GEM_SPOTLIGHT_ACCENTS;
}) {
  const colors = GEM_SPOTLIGHT_ACCENTS[accent];
  return (
    <a
      href={gem.url}
      target="_blank"
      rel="noopener noreferrer"
      className={`group relative block aspect-square overflow-hidden rounded-2xl ring-1 ${colors.ring} shadow-lg shadow-black/40`}
    >
      {gem.image_url ? (
        <img
          src={gem.image_url}
          alt={gem.title}
          className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-slate-800" />
      )}

      {/* Scrim so the glass panel stays legible over any photo */}
      <div className={`absolute inset-0 bg-gradient-to-t ${colors.glow} via-black/10 to-black/60`} />

      <div className="absolute top-3 left-3 rounded-full bg-black/40 backdrop-blur-md border border-white/10 px-3 py-1">
        <span className={`text-[10px] uppercase tracking-wide font-semibold ${colors.label}`}>{label}</span>
      </div>

      <div className="absolute inset-x-0 bottom-0 bg-black/35 backdrop-blur-md border-t border-white/10 p-4">
        <div className="text-sm text-white truncate group-hover:underline">{gem.title.substring(0, 40)}...</div>
        {gem.cpu && <div className="text-xs text-white/70 mt-0.5 truncate">⚡ {gem.cpu}</div>}
        <div className={`text-xl font-bold mt-1 ${colors.price}`}>£{gem.price.toFixed(2)}</div>
      </div>
    </a>
  );
}

function StatsTab({ componentGems }: { componentGems?: Record<string, GemData | null> }) {
  const [inventoryHealth, setInventoryHealth] = useState<Awaited<ReturnType<typeof api.inventory.health>> | null>(null);
  useEffect(() => {
    const timer = window.setTimeout(() => api.inventory.health().then(setInventoryHealth).catch(() => undefined), 0);
    return () => window.clearTimeout(timer);
  }, []);
  const componentLabels: Record<string, { label: string; emoji: string }> = {
    cpu: { label: "Gem CPU", emoji: "⚡" },
    gpu: { label: "Gem GPU", emoji: "🎮" },
    motherboard: { label: "Gem Motherboard", emoji: "🔧" },
    ssd: { label: "Gem SSD", emoji: "💿" },
    psu: { label: "Gem PSU", emoji: "🔌" },
  };

  return (
    <>
      {inventoryHealth && (
        <div className="mt-6 rounded-xl border border-cyan-300/15 bg-cyan-300/[0.035] p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h3 className="text-sm font-semibold text-slate-100">Inventory-aware sourcing</h3><p className="mt-1 text-xs text-slate-500">Use these signals before buying duplicates or prioritise parts blocking active builds.</p></div>
            <Link href="/inventory" className="cursor-pointer rounded-md border border-cyan-300/25 px-3 py-1.5 text-xs font-semibold text-cyan-200 transition-colors hover:bg-cyan-300/10">Open inventory</Link>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-4">
            <MiniStat label="Free units" value={inventoryHealth.free_units} color="#67e8f9" />
            <MiniStat label="Reserved units" value={inventoryHealth.reserved_units} color="#fcd34d" />
            <MiniStat label="Builds blocked" value={inventoryHealth.build_blockers.length} color="#fb7185" />
            <MiniStat label="Excess categories" value={inventoryHealth.excess_stock.length} color="#a78bfa" />
          </div>
          {inventoryHealth.build_blockers.length > 0 && <p className="mt-3 text-xs text-amber-200">Prioritise: {Array.from(new Set(inventoryHealth.build_blockers.flatMap(blocker => blocker.missing))).join(", ")}</p>}
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 mb-6 mt-6">
        {Object.keys(componentLabels).map((category) => {
          const gem = componentGems?.[category];
          return gem ? (
            <GemSpotlightCard
              key={category}
              gem={gem}
              label={componentLabels[category].label}
              accent={category === "cpu" ? "cyan" : category === "gpu" ? "purple" : category === "motherboard" ? "emerald" : category === "ssd" ? "blue" : "orange"}
            />
          ) : (
            <div key={category} className="min-h-48 rounded-2xl border border-white/10 bg-white/[0.03] p-5 flex flex-col justify-between">
              <span className="text-[10px] uppercase tracking-wide font-semibold text-slate-400">{componentLabels[category].label}</span>
              <p className="text-sm text-slate-500">No qualifying gem in the current snapshot</p>
            </div>
          );
        })}
      </div>
    </>
  );
}

const SOURCE_LABELS: Record<string, string> = {
  ebay: "eBay",
  overclockers: "Overclockers",
  amazon: "Amazon",
  scan: "Scan.co.uk",
  awd_it: "AWD-IT",
  computer_orbit: "Computer Orbit",
  bargain_hardware: "Bargain Hardware",
};
const SOURCE_COLORS: Record<string, string> = {
  ebay: "bg-sky-600 text-white",
  overclockers: "bg-orange-600 text-white",
  amazon: "bg-amber-700 text-white",
  scan: "bg-blue-700 text-white",
  awd_it: "bg-rose-700 text-white",
  computer_orbit: "bg-violet-700 text-white",
  bargain_hardware: "bg-teal-700 text-white",
};
// No eBay/Vinted logo files are bundled in this repo, so this pulls each
// site's own favicon at render time rather than embedding a logo asset
// ourselves — small, official, no local file to keep in sync. Swap for a
// bundled SVG under /public if a proper wordmark is ever wanted instead.
const SOURCE_DOMAINS: Record<string, string> = {
  ebay: "ebay.co.uk",
  overclockers: "overclockers.co.uk",
  amazon: "amazon.co.uk",
  scan: "scan.co.uk",
  awd_it: "awd-it.co.uk",
  computer_orbit: "computerorbit.com",
  bargain_hardware: "bargainhardware.co.uk",
};

function SourceBadge({ source }: { source: string }) {
  const domain = SOURCE_DOMAINS[source];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${SOURCE_COLORS[source] || "bg-slate-600 text-slate-200"}`}>
      {domain && (
        // eslint-disable-next-line @next/next/no-img-element -- tiny external favicon, not worth next/image's domain allowlist
        <img
          src={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
          alt=""
          width={14}
          height={14}
          className="shrink-0"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
      )}
      {SOURCE_LABELS[source] || source}
    </span>
  );
}

// Condition strings vary a lot across scrapers (eBay's own condition IDs,
// Vinted's free-text, etc.), so this matches on keywords rather than an
// exact lookup table like SOURCE_LABELS above.
function conditionStyle(condition: string): string {
  const c = condition.toLowerCase();
  if (c.includes("new")) return "bg-emerald-600 text-white";
  if (c.includes("refurb")) return "bg-cyan-600 text-white";
  if (c.includes("part") || c.includes("fault") || c.includes("broken") || c.includes("spares")) {
    return "bg-red-700 text-white";
  }
  if (c.includes("used") || c.includes("good") || c.includes("acceptable") || c.includes("pre-owned")) {
    return "bg-indigo-600 text-white";
  }
  return "bg-slate-600 text-slate-200";
}

function ConditionBadge({ condition }: { condition?: string | null }) {
  if (!condition) return <span className="text-slate-500">—</span>;
  return (
    <span className={`px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${conditionStyle(condition)}`}>
      {condition}
    </span>
  );
}

// Phase 2 classifies against the robust same-condition median. Keep the table
// variance anchored to that same value so the displayed economics agree with
// the classification rather than legacy new/used asking-price fields.
function priceVariance(listing: Listing): { amount: number; percent: number } | null {
  const marketPrice = listing.market_median_price ?? listing.conservative_resale_price;
  if (marketPrice == null || listing.delivered_price <= 0) return null;
  const amount = marketPrice - listing.delivered_price;
  return { amount, percent: (amount / listing.delivered_price) * 100 };
}

function PriceVarianceCell({ listing }: { listing: Listing }) {
  const variance = priceVariance(listing);
  if (!variance) return <span className="text-slate-500">—</span>;
  const positive = variance.amount >= 0;
  const sign = positive ? "+" : "-";
  return (
    <span className={`font-semibold whitespace-nowrap ${positive ? "text-emerald-400" : "text-red-400"}`}>
      {sign}£{Math.abs(variance.amount).toFixed(0)} ({sign}{Math.abs(variance.percent).toFixed(0)}%)
    </span>
  );
}

// The most recent scraping run represented in the currently loaded listings
// — grouping by search_run_id rather than a timestamp-proximity threshold,
// since listings within one run can be observed a little apart from each
// other as the scraper works through it.
function findLatestRunId(listings: Listing[]): string | null {
  let latest: Listing | null = null;
  for (const listing of listings) {
    if (!listing.search_run_id || !listing.listing_observed_at) continue;
    if (!latest || !latest.listing_observed_at || listing.listing_observed_at > latest.listing_observed_at) {
      latest = listing;
    }
  }
  return latest?.search_run_id ?? null;
}

type GemFilter = "all" | "SUPER_GEM" | "GEM" | "EVIDENCE_LIMITED_DEAL" | "EMERGING_OPPORTUNITY" | "OK_DEAL" | "AVERAGE_DEAL" | "POOR_DEAL" | "INSUFFICIENT_DATA" | "INELIGIBLE";
type StockLane = "all" | "new" | "open_box" | "used";

const STOCK_LANES: { value: StockLane; label: string; description: string }[] = [
  { value: "all", label: "All stock", description: "Every retained sourcing opportunity" },
  { value: "new", label: "New build stock", description: "Factory-new components suitable for an all-new build" },
  { value: "open_box", label: "Open-box / B-grade", description: "Refurbished, open-box and new-other stock requiring disclosure" },
  { value: "used", label: "Used flip opportunities", description: "Pre-owned components for value-led or refurbished builds" },
];

function stockLaneFor(listing: Listing): Exclude<StockLane, "all"> | "unknown" {
  const condition = (listing.condition ?? "").trim().toLowerCase().replace(/[ -]+/g, "_");
  if (condition === "new") return "new";
  if (condition.includes("refurb") || condition.includes("open_box") || condition.includes("new_other") || condition.includes("b_grade")) return "open_box";
  if (condition.includes("used") || condition.includes("pre_owned")) return "used";
  return "unknown";
}

type SortKey = "source" | "title" | "seller" | "condition" | "price_variance" | "delivered_price" | "market_lower_price" | "market_median_price" | "market_upper_price" | "classification" | "decision" | "deal_score" | "watch_count" | "best_offer_enabled";
type SortDir = "asc" | "desc";

const CLASSIFICATION_RANK: Record<string, number> = {
  SUPER_GEM: 4,
  GEM: 3,
  EVIDENCE_LIMITED_DEAL: 2.5,
  EMERGING_OPPORTUNITY: 2.5,
  OK_DEAL: 2,
  AVERAGE_DEAL: 1,
  POOR_DEAL: 0,
  INSUFFICIENT_DATA: -1,
  INELIGIBLE: -2,
};

// Best deal to worst — shared between the filter tags and the row badge so
// the two stay visually consistent.
const CLASSIFICATION_BADGE_ORDER: string[] = ["SUPER_GEM", "GEM", "EVIDENCE_LIMITED_DEAL", "OK_DEAL", "AVERAGE_DEAL", "POOR_DEAL", "INSUFFICIENT_DATA", "INELIGIBLE"];
const CLASSIFICATION_BADGE_COLORS: Record<string, string> = {
  SUPER_GEM: "bg-amber-600 text-white",
  GEM: "bg-blue-600 text-white",
  EVIDENCE_LIMITED_DEAL: "bg-sky-600 text-white",
  EMERGING_OPPORTUNITY: "bg-sky-600 text-white",
  OK_DEAL: "bg-emerald-700 text-white",
  AVERAGE_DEAL: "bg-slate-600 text-slate-100",
  POOR_DEAL: "bg-red-800 text-white",
  INSUFFICIENT_DATA: "bg-slate-700 text-slate-300",
  INELIGIBLE: "bg-rose-950 text-rose-300",
};
const CLASSIFICATION_TAG_INACTIVE: Record<string, string> = {
  SUPER_GEM: "bg-amber-900/20 text-amber-300 border border-amber-700/30 hover:bg-amber-900/40",
  GEM: "bg-blue-900/20 text-blue-300 border border-blue-700/30 hover:bg-blue-900/40",
  EVIDENCE_LIMITED_DEAL: "bg-sky-900/20 text-sky-300 border border-sky-700/30 hover:bg-sky-900/40",
  EMERGING_OPPORTUNITY: "bg-sky-900/20 text-sky-300 border border-sky-700/30 hover:bg-sky-900/40",
  OK_DEAL: "bg-emerald-900/20 text-emerald-300 border border-emerald-700/30 hover:bg-emerald-900/40",
  AVERAGE_DEAL: "bg-slate-700/40 text-slate-300 border border-slate-600/40 hover:bg-slate-700/70",
  POOR_DEAL: "bg-red-900/20 text-red-300 border border-red-700/30 hover:bg-red-900/40",
  INSUFFICIENT_DATA: "bg-slate-900/30 text-slate-400 border border-slate-700/40 hover:bg-slate-800/50",
  INELIGIBLE: "bg-rose-950/30 text-rose-400 border border-rose-900/50 hover:bg-rose-950/50",
};

function ClassificationBadge({ classification }: { classification: string }) {
  return (
    <span className={`px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${CLASSIFICATION_BADGE_COLORS[classification] || "bg-slate-600 text-slate-200"}`}>
      {classification}
    </span>
  );
}

// BUY_NOW, MAKE_OFFER, WATCH, INVESTIGATE, IGNORE (app/gem_radar/scoring.py)
const DECISION_COLORS: Record<string, string> = {
  BUY_NOW: "bg-emerald-600 text-white",
  MAKE_OFFER: "bg-blue-600 text-white",
  WATCH: "bg-amber-600 text-white",
  INVESTIGATE: "bg-purple-600 text-white",
  IGNORE: "bg-slate-600 text-slate-300",
};

// Mirrors the branches in scoring.compute_decision (flipflop-api) so the
// tooltip explains the ACTUAL rule that produced this decision, not a
// generic description of the label.
function explainDecision(decision: string, classification: string, confidence: string): string {
  const cls = classification.replace(/_/g, " ");
  switch (decision) {
    case "BUY_NOW":
      return `${cls} with ${confidence} confidence — strong, well-identified deal worth acting on now.`;
    case "MAKE_OFFER":
      return `${cls} with ${confidence} confidence — a real deal, but confidence isn't high enough to buy outright at the asking price; consider negotiating.`;
    case "WATCH":
      return `${cls}${confidence === "low" ? " with low confidence" : ""} — not strong enough to act on yet, but worth monitoring for a price drop or better comps.`;
    case "INVESTIGATE":
      return classification === "SUPER_GEM" || classification === "GEM"
        ? `${cls} score, but ${confidence === "low" ? "the identity-match confidence is low" : "a high-severity risk flag was detected"} — verify manually before buying; don't take the score at face value.`
        : "Flagged for manual review before acting.";
    case "IGNORE":
      return "POOR_DEAL classification — priced at or above real market value, not worth pursuing.";
    default:
      return decision;
  }
}

// Generic meaning of each tier, used only when a listing has no pct_offset/
// market_median_price to explain itself with (e.g. scored by the older
// LLM-assisted pathway rather than the CPK/Phase2 one — see
// phase2_runner.py, the only writer of those two fields).
const CLASSIFICATION_TIER_MEANING: Record<string, string> = {
  SUPER_GEM: "Priced far below real market value — an exceptional deal.",
  GEM: "Priced clearly below real market value — a solid deal.",
  EVIDENCE_LIMITED_DEAL: "Promising economics with fewer than five robust comparables — manually verify identity and price before buying.",
  EMERGING_OPPORTUNITY: "Promising positive economics with only 3–4 robust sold comparables — manually verify before buying.",
  OK_DEAL: "Priced somewhat below market value — a fair deal.",
  AVERAGE_DEAL: "Priced close to market value — not a notable deal either way.",
  POOR_DEAL: "Priced at or above real market value — not worth pursuing.",
  INSUFFICIENT_DATA: "Not enough completed-sale evidence to classify this listing yet.",
  INELIGIBLE: "Rejected by an identity, accessory, bundle, retro-platform, or market-quality veto.",
};

// Mirrors app/gem_radar/deal_classification.py's classify_by_offset +
// deal_score_from_offset: both the classification tier and the 0-10 score
// are derived purely from pct_offset (listing price vs the settled CPK
// market price). Shows the ACTUAL numbers this listing was classified
// against, not just a description of what the tier name means.
function explainClassification(listing: Listing): string {
  const cls = listing.classification.replace(/_/g, " ");
  const meaning = CLASSIFICATION_TIER_MEANING[listing.classification] ?? "";

  if (listing.pct_offset == null || listing.market_median_price == null) {
    return `${cls} (score ${listing.deal_score.toFixed(1)}/10) — ${meaning}`;
  }

  const direction = listing.pct_offset < 0 ? "below" : "above";
  return (
    `${cls} (score ${listing.deal_score.toFixed(1)}/10) — ${meaning} ` +
    `Listed at £${listing.delivered_price.toFixed(2)}, ${Math.abs(listing.pct_offset).toFixed(1)}% ${direction} ` +
    `the £${listing.market_median_price.toFixed(2)} median market price for this product.`
  );
}

function DecisionBadge({
  decision,
  classification,
  confidence,
}: {
  decision: string;
  classification: string;
  confidence: string;
}) {
  return (
    <span
      title={explainDecision(decision, classification, confidence)}
      className={`px-2 py-1 rounded text-xs font-semibold whitespace-nowrap cursor-help ${DECISION_COLORS[decision] || "bg-slate-600 text-slate-200"}`}
    >
      {decision.replace(/_/g, " ")}
    </span>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 min-w-0">
      <div className="text-xs text-slate-400 uppercase tracking-wide truncate">{label}</div>
      <div className="text-lg font-semibold text-slate-100 truncate">{value}</div>
    </div>
  );
}

function TopListingTile({ label, listing }: { label: string; listing: Listing | null }) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 min-w-0">
      <div className="text-xs text-slate-400 uppercase tracking-wide truncate">{label}</div>
      {listing ? (
        <>
          <div className="text-sm font-semibold text-slate-100 truncate" title={listing.title}>{listing.title}</div>
          <div className="text-xs text-slate-400">score {listing.deal_score.toFixed(1)} · £{listing.delivered_price.toFixed(2)}</div>
        </>
      ) : (
        <div className="text-lg font-semibold text-slate-500">—</div>
      )}
    </div>
  );
}

// Recomputed from whatever's currently on screen (post component-tab and
// classification-filter selection), so it updates for all three triggers
// the stats bar is meant to react to: new data, a different component tab,
// or a different classification filter.
function StatsBar({ listings }: { listings: Listing[] }) {
  const count = listings.length;
  const variances = listings.map((l) => priceVariance(l)?.amount).filter((v): v is number => v != null);
  const avgVariance = variances.length ? variances.reduce((a, b) => a + b, 0) / variances.length : null;
  const avgScore = count ? listings.reduce((a, l) => a + l.deal_score, 0) / count : null;

  const gems = listings.filter((l) => l.classification === "GEM");
  const superGems = listings.filter((l) => l.classification === "SUPER_GEM");
  const topGem = gems.length ? gems.reduce((a, b) => (b.deal_score > a.deal_score ? b : a)) : null;
  const topSuperGem = superGems.length ? superGems.reduce((a, b) => (b.deal_score > a.deal_score ? b : a)) : null;

  const decisionCounts = new Map<string, number>();
  for (const l of listings) decisionCounts.set(l.decision, (decisionCounts.get(l.decision) ?? 0) + 1);

  // Not just the two known sources — any value that actually shows up in
  // the data, so a new marketplace appears here automatically (with the
  // same raw-value/grey fallback SourceBadge already uses) rather than
  // silently being left off a hardcoded list.
  const sourceCounts = new Map<string, number>();
  for (const l of listings) sourceCounts.set(l.source, (sourceCounts.get(l.source) ?? 0) + 1);
  const sourcesByCount = [...sourceCounts.entries()].sort((a, b) => b[1] - a[1]);

  return (
    <div className="mb-4 space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatTile label="Listings" value={String(count)} />
        <StatTile label="Avg Variance" value={avgVariance == null ? "—" : `${avgVariance >= 0 ? "+" : "-"}£${Math.abs(avgVariance).toFixed(0)}`} />
        <StatTile label="Avg Score" value={avgScore == null ? "—" : avgScore.toFixed(1)} />
        <StatTile label="Gems" value={String(gems.length)} />
        <StatTile label="Super Gems" value={String(superGems.length)} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <TopListingTile label="Top Gem" listing={topGem} />
        <TopListingTile label="Top Super Gem" listing={topSuperGem} />
      </div>
      <div className="flex flex-wrap gap-2">
        {sourcesByCount.map(([source, sourceCount]) => (
          <div
            key={source}
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-semibold whitespace-nowrap ${SOURCE_COLORS[source] || "bg-slate-600 text-slate-200"}`}
          >
            {SOURCE_LABELS[source] || source}
            <span className="bg-black/25 rounded px-1.5">{sourceCount}</span>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {Object.keys(DECISION_COLORS).map((decision) => (
          <div
            key={decision}
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-semibold whitespace-nowrap ${DECISION_COLORS[decision]}`}
          >
            {decision.replace(/_/g, " ")}
            <span className="bg-black/25 rounded px-1.5">{decisionCounts.get(decision) ?? 0}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Nulls/undefined always sort last regardless of direction — an absent
// market price isn't "less than zero", it's unknown, and burying unknowns
// at the bottom of a descending sort is more useful than surfacing them at
// the top just because `null < 5`.
function compareSortValue(a: Listing, b: Listing, key: SortKey): number {
  if (key === "classification") {
    return CLASSIFICATION_RANK[a.classification] - CLASSIFICATION_RANK[b.classification];
  }
  if (key === "price_variance") {
    const av = priceVariance(a)?.amount;
    const bv = priceVariance(b)?.amount;
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return av - bv;
  }
  const av = a[key as keyof Listing];
  const bv = b[key as keyof Listing];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  if (typeof av === "string" || typeof bv === "string") {
    return String(av).localeCompare(String(bv));
  }
  return Number(av) - Number(bv);
}

function SortHeader({
  label,
  sortKey,
  activeSort,
  sortDir,
  onSort,
  align = "left",
  widthClassName = "",
}: {
  label: string;
  sortKey: SortKey;
  activeSort: SortKey;
  sortDir: SortDir;
  onSort: (key: SortKey) => void;
  align?: "left" | "right";
  widthClassName?: string;
}) {
  const isActive = activeSort === sortKey;
  return (
    <th
      className={`px-1.5 py-2 text-xs text-slate-200 font-semibold cursor-pointer select-none hover:text-white transition ${
        align === "right" ? "text-right" : "text-left"
      } ${widthClassName}`}
      onClick={() => onSort(sortKey)}
    >
      {label}
      <span className={`ml-1 inline-block w-3 ${isActive ? "text-blue-400" : "text-slate-600"}`}>
        {isActive ? (sortDir === "asc" ? "▲" : "▼") : "▼"}
      </span>
    </th>
  );
}

// Per-vendor breakdown across the full (unfiltered) listing set — total plus
// a column per classification tier, worst to best left-to-right so the
// "good stuff" columns land next to each other on the right.
const VENDOR_TABLE_TIERS: string[] = [...CLASSIFICATION_BADGE_ORDER].reverse();
const VENDOR_SUMMARY_TABLE_TIERS = VENDOR_TABLE_TIERS.filter(
  (tier) => tier !== "AVERAGE_DEAL" && tier !== "EVIDENCE_LIMITED_DEAL",
);

// Hex equivalents of CLASSIFICATION_BADGE_COLORS' Tailwind classes — recharts
// fills need real colour values, not class names, but these are picked to
// match the badges/table exactly so the chart and table read as one system.
const CLASSIFICATION_CHART_COLORS: Record<string, string> = {
  SUPER_GEM: "#d97706",
  GEM: "#2563eb",
  EVIDENCE_LIMITED_DEAL: "#0284c7",
  OK_DEAL: "#047857",
  AVERAGE_DEAL: "#475569",
  POOR_DEAL: "#991b1b",
  INSUFFICIENT_DATA: "#334155",
  INELIGIBLE: "#881337",
};

function VendorStackedBarChart({ listings }: { listings: Listing[] }) {
  const sources = [...new Set(listings.map((l) => l.source))].sort(
    (a, b) => listings.filter((l) => l.source === b).length - listings.filter((l) => l.source === a).length
  );

  if (sources.length === 0) return null;

  const chartData = sources.map((source) => {
    const vendorListings = listings.filter((l) => l.source === source);
    const row: Record<string, string | number> = { vendor: SOURCE_LABELS[source] || source };
    for (const tier of VENDOR_TABLE_TIERS) {
      row[tier] = vendorListings.filter((l) => l.classification === tier).length;
    }
    return row;
  });

  return (
    <div className="mb-4 bg-slate-800 rounded-lg border border-slate-700 p-3 lg:w-[420px] lg:shrink-0">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="vendor" stroke="#94a3b8" tick={{ fill: "#94a3b8", fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={50} />
          <YAxis stroke="#94a3b8" tick={{ fill: "#94a3b8", fontSize: 12 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 6 }}
            labelStyle={{ color: "#e2e8f0" }}
          />
          {VENDOR_TABLE_TIERS.map((tier) => (
            <Bar
              key={tier}
              dataKey={tier}
              name={tier.replace(/_/g, " ")}
              stackId="classification"
              fill={CLASSIFICATION_CHART_COLORS[tier]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-3 flex flex-wrap justify-center gap-x-3 gap-y-2 border-t border-slate-700 pt-3" aria-label="Classification legend">
        {VENDOR_TABLE_TIERS.map((tier) => (
          <div key={tier} className="flex items-center gap-1.5 text-[11px] text-slate-300">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ backgroundColor: CLASSIFICATION_CHART_COLORS[tier] }}
            />
            <span>{tier.replace(/_/g, " ")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function VendorSummaryTable({ listings }: { listings: Listing[] }) {
  const sources = [...new Set(listings.map((l) => l.source))].sort(
    (a, b) => listings.filter((l) => l.source === b).length - listings.filter((l) => l.source === a).length
  );

  if (sources.length === 0) return null;

  return (
    <div className="mb-4 overflow-x-auto bg-slate-800 rounded-lg border border-slate-700 flex-1">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-700 border-b border-slate-600">
          <tr>
            <th className="text-left p-2.5 text-slate-200 font-semibold">Vendor</th>
            <th className="text-right p-2.5 text-slate-200 font-semibold">Total</th>
            {VENDOR_SUMMARY_TABLE_TIERS.map((tier) => (
              <th key={tier} className="text-right p-2.5 text-slate-200 font-semibold whitespace-nowrap">
                {tier.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => {
            const vendorListings = listings.filter((l) => l.source === source);
            return (
              <tr key={source} className="border-b border-slate-700 last:border-b-0">
                <td className="p-2.5">
                  <SourceBadge source={source} />
                </td>
                <td className="p-2.5 text-right text-slate-100 font-semibold">{vendorListings.length}</td>
                {VENDOR_SUMMARY_TABLE_TIERS.map((tier) => (
                  <td key={tier} className="p-2.5 text-right text-slate-300">
                    {vendorListings.filter((l) => l.classification === tier).length}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ListingsTab({ listings, highlightListingId }: { listings: Listing[]; highlightListingId?: string | null }) {
  const PAGE_SIZE = 100;
  const [componentTab, setComponentTab] = useState<ComponentType>("CPU");
  const [stockLane, setStockLane] = useState<StockLane>("all");
  const [gemFilter, setGemFilter] = useState<GemFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("deal_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [titleQuery, setTitleQuery] = useState("");
  const [explanationListing, setExplanationListing] = useState<Listing | null>(null);
  const [page, setPage] = useState(1);

  // Jump straight to a specific listing when arriving from a favourite-match
  // toast/notification link (?listing=<listing_id>) — switch to its tab so
  // the row isn't hidden behind whatever component filter was last active,
  // then scroll it into view and briefly highlight it once rendered.
  useEffect(() => {
    if (!highlightListingId) return;
    const match = listings.find((l) => l.listing_id === highlightListingId);
    if (match) {
      setComponentTab(listingTab(match));
      setGemFilter("all");
    }
  }, [highlightListingId, listings]);

  const [highlightActive, setHighlightActive] = useState(true);
  useEffect(() => {
    if (!highlightListingId) return;
    setHighlightActive(true);
    const el = document.getElementById(`listing-row-${highlightListingId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    const timer = setTimeout(() => setHighlightActive(false), 4000);
    return () => clearTimeout(timer);
  }, [highlightListingId, componentTab]);

  // Computed against the full unfiltered set so switching component/gem
  // filters doesn't change what counts as "the last scrape".
  const latestRunId = findLatestRunId(listings);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const byLane = stockLane === "all" ? listings : listings.filter((listing) => stockLaneFor(listing) === stockLane);
  const byComponent = byLane.filter((l) => listingTab(l) === componentTab);
  const byTitle = titleQuery.trim()
    ? byComponent.filter((l) => fuzzyMatches(titleQuery, l.title))
    : byComponent;
  const byClassification = gemFilter === "all" ? byTitle : byTitle.filter((listing) => listing.classification === gemFilter);
  const filtered = [...byClassification].sort((a, b) => {
    const cmp = compareSortValue(a, b, sortKey);
    return sortDir === "asc" ? cmp : -cmp;
  });
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageStart = (currentPage - 1) * PAGE_SIZE;
  const visibleListings = filtered.slice(pageStart, pageStart + PAGE_SIZE);

  useEffect(() => {
    setPage(1);
  }, [componentTab, stockLane, gemFilter, sortKey, sortDir, titleQuery]);

  useEffect(() => {
    if (!highlightListingId) return;
    const index = filtered.findIndex((listing) => listing.listing_id === highlightListingId);
    if (index >= 0) setPage(Math.floor(index / PAGE_SIZE) + 1);
  }, [highlightListingId, componentTab]);
  const tabCounts = COMPONENT_TABS.map((tab) => ({
    tab,
    count: byLane.filter((l) => listingTab(l) === tab).length,
  }));
  const classificationCounts = CLASSIFICATION_BADGE_ORDER.map((classification) => ({
    classification,
    count: byComponent.filter((l) => l.classification === classification).length,
  }));

  return (
    <>
      <div className="flex flex-col lg:flex-row gap-4">
        <VendorSummaryTable listings={listings} />
        <VendorStackedBarChart listings={listings} />
      </div>

      <div className="flex gap-2 overflow-x-auto pb-2 border-b border-slate-700 mb-4">
        {tabCounts.map(({ tab, count }) => (
          <button
            key={tab}
            onClick={() => setComponentTab(tab)}
            className={`px-4 py-2 rounded whitespace-nowrap transition ${
              componentTab === tab
                ? "bg-blue-600 text-white"
                : "bg-slate-700 text-slate-300 hover:bg-slate-600"
            }`}
          >
            {tab} ({count})
          </button>
        ))}
      </div>

      <div className="flex gap-2 mb-4 flex-wrap">
        <button
          onClick={() => setGemFilter("all")}
          className={`px-4 py-2 rounded whitespace-nowrap transition font-semibold ${
            gemFilter === "all"
              ? "bg-slate-500 text-white"
              : "bg-slate-700/40 text-slate-300 border border-slate-600/40 hover:bg-slate-700/70"
          }`}
        >
          All ({byComponent.length})
        </button>
        {classificationCounts.map(({ classification, count }) => (
          <button
            key={classification}
            onClick={() => setGemFilter(gemFilter === classification ? "all" : (classification as GemFilter))}
            className={`px-4 py-2 rounded whitespace-nowrap transition font-semibold ${
              gemFilter === classification
                ? CLASSIFICATION_BADGE_COLORS[classification]
                : CLASSIFICATION_TAG_INACTIVE[classification]
            }`}
          >
            {classification.replace(/_/g, " ")} ({count})
          </button>
        ))}
      </div>

      <StatsBar listings={filtered} />

      <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-sm">
        <span className="text-slate-400">
          Showing {filtered.length === 0 ? 0 : pageStart + 1}–{Math.min(pageStart + PAGE_SIZE, filtered.length)} of {filtered.length}
        </span>
        <div className="flex items-center gap-2">
          <button type="button" disabled={currentPage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded border border-slate-600 bg-slate-700 px-3 py-1.5 text-slate-200 disabled:cursor-not-allowed disabled:opacity-40">Previous</button>
          <span className="min-w-24 text-center text-slate-300">Page {currentPage} of {totalPages}</span>
          <button type="button" disabled={currentPage >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))} className="rounded border border-slate-600 bg-slate-700 px-3 py-1.5 text-slate-200 disabled:cursor-not-allowed disabled:opacity-40">Next</button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto bg-slate-800 rounded-lg border border-slate-700">
        {filtered.length === 0 ? (
          <div className="flex items-center justify-center h-full text-slate-400">
            No {gemFilter === "all" ? "listings" : gemFilter.replace(/_/g, " ").toLowerCase()} yet for {componentTab}
            {titleQuery.trim() && <> matching &quot;{titleQuery}&quot;</>}
          </div>
        ) : (
          <table className="w-full table-fixed text-xs [&_th]:px-1.5 [&_th]:py-2 [&_td]:overflow-hidden [&_td]:px-1.5 [&_td]:py-2">
            <thead className="sticky top-0 bg-slate-700 border-b border-slate-600">
              <tr>
                <th className="text-left text-slate-200 font-semibold w-10"></th>
                <SortHeader label="Source" sortKey="source" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} widthClassName="w-16" />
                <th className="text-left text-slate-200 font-semibold w-auto">
                  <div
                    className="cursor-pointer select-none hover:text-white transition inline-flex items-center"
                    onClick={() => handleSort("title")}
                  >
                    Title
                    <span className={`ml-1 inline-block w-3 ${sortKey === "title" ? "text-blue-400" : "text-slate-600"}`}>
                      {sortKey === "title" ? (sortDir === "asc" ? "▲" : "▼") : "▼"}
                    </span>
                  </div>
                  <input
                    value={titleQuery}
                    onChange={(e) => setTitleQuery(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    placeholder="Fuzzy search title..."
                    className="mt-1 w-full rounded border border-slate-600 bg-slate-800 px-2 py-1 text-xs font-normal text-slate-100 placeholder:text-slate-500 outline-none focus:border-blue-500"
                  />
                </th>
                <SortHeader label="Condition" sortKey="condition" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} widthClassName="w-20" />
                <SortHeader label="Price" sortKey="delivered_price" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} align="right" widthClassName="w-20" />
                <th className="text-left text-slate-200 font-semibold w-28">History</th>
                <SortHeader label="Low" sortKey="market_lower_price" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} align="right" widthClassName="w-20" />
                <SortHeader label="Median" sortKey="market_median_price" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} align="right" widthClassName="w-20" />
                <SortHeader label="High" sortKey="market_upper_price" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} align="right" widthClassName="w-20" />
                <SortHeader label="Vs Median" sortKey="price_variance" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} align="right" widthClassName="w-24" />
                <SortHeader label="Class" sortKey="classification" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} widthClassName="w-24" />
                <SortHeader label="Decision" sortKey="decision" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} widthClassName="w-20" />
                <SortHeader label="Score" sortKey="deal_score" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} align="right" widthClassName="w-14" />
                <th className="text-left text-slate-200 font-semibold w-16">Evidence</th>
                <SortHeader label="Watches" sortKey="watch_count" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} align="right" widthClassName="w-16" />
                <SortHeader label="Offers" sortKey="best_offer_enabled" activeSort={sortKey} sortDir={sortDir} onSort={handleSort} align="right" widthClassName="w-14" />
              </tr>
            </thead>
            <tbody>
              {visibleListings.map((listing, idx) => {
                const isGem = listing.classification === "SUPER_GEM";
                const isDeal = listing.classification === "GEM";
                const isHighlighted = highlightActive && listing.listing_id === highlightListingId;
                const bgColor = isHighlighted
                  ? "bg-emerald-500/25 ring-2 ring-inset ring-emerald-400"
                  : isGem
                  ? "bg-amber-900/20"
                  : isDeal
                  ? "bg-blue-900/20"
                  : idx % 2 === 0
                  ? "bg-slate-800"
                  : "bg-slate-750";

                return (
                  <tr
                    key={listing.id}
                    id={`listing-row-${listing.listing_id}`}
                    className={`border-b border-slate-700 hover:bg-slate-700 transition ${bgColor}`}
                  >
                    <td className="p-3">
                      <ListingThumbnail src={listing.image_url} alt={listing.title} />
                    </td>
                    <td className="p-3">
                      <SourceBadge source={listing.source} />
                    </td>
                    <td className="p-3 text-slate-100 max-w-xs break-words">
                      {latestRunId && listing.search_run_id === latestRunId && (
                        <Flame
                          size={14}
                          className="inline-block mr-1.5 -mt-0.5 text-orange-400"
                          aria-label="New since the last scrape"
                        />
                      )}
                      <a
                        href={listing.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:underline hover:text-blue-300"
                      >
                        {listing.title}
                      </a>
                    </td>
                    <td className="p-3">
                      <ConditionBadge condition={listing.condition} />
                    </td>
                    <td className="p-3 text-right text-slate-100 font-semibold">£{listing.delivered_price.toFixed(2)}</td>
                    <td className="p-3">
                      <PriceHistorySparkline listingId={listing.listing_id} listingTitle={listing.title} />
                    </td>
                    <td className="p-3 text-right text-slate-100">
                      {listing.market_lower_price == null ? "—" : `£${listing.market_lower_price.toFixed(2)}`}
                    </td>
                    <td className="p-3 text-right text-slate-100">
                      {(listing.market_median_price ?? listing.conservative_resale_price) != null ? (
                        <span title="Median of the robust, same-condition comparable cohort used by classification.">
                          £{(listing.market_median_price ?? listing.conservative_resale_price)!.toFixed(2)}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="p-3 text-right text-slate-100">
                      {listing.market_upper_price == null ? "—" : `£${listing.market_upper_price.toFixed(2)}`}
                    </td>
                    <td className="p-3 text-right">
                      <PriceVarianceCell listing={listing} />
                    </td>
                    <td className="p-3" title={explainClassification(listing)}>
                      <ClassificationBadge classification={listing.classification} />
                    </td>
                    <td className="p-3">
                      <DecisionBadge
                        decision={listing.decision}
                        classification={listing.classification}
                        confidence={listing.confidence}
                      />
                    </td>
                    <td className="p-3 text-right text-slate-100 font-semibold" title={explainClassification(listing)}>
                      {listing.deal_score.toFixed(1)}
                    </td>
                    <td className="p-3">
                      <button
                        type="button"
                        onClick={() => setExplanationListing(listing)}
                        className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-cyan-400/25 bg-cyan-400/10 px-2 py-1 text-xs font-semibold text-cyan-300 transition-colors duration-200 hover:bg-cyan-400/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                      >
                        <Info className="h-3.5 w-3.5" /> Why?
                      </button>
                    </td>
                    <td className="p-3 text-right text-cyan-300">
                      {listing.watch_count ?? "—"}
                    </td>
                    <td className={`p-3 text-right ${listing.best_offer_enabled ? "text-emerald-300" : "text-slate-500"}`}>
                      {listing.best_offer_enabled ? "Yes" : "No"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="mb-4 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3" role="group" aria-label="Stock condition lane">
        {STOCK_LANES.map((lane) => {
          const count = lane.value === "all" ? listings.length : listings.filter((listing) => stockLaneFor(listing) === lane.value).length;
          const active = stockLane === lane.value;
          return (
            <button
              key={lane.value}
              type="button"
              onClick={() => setStockLane(lane.value)}
              aria-pressed={active}
              className={`cursor-pointer rounded-lg border p-4 text-left transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${active ? "border-blue-500 bg-blue-950/60" : "border-slate-700 bg-slate-800 hover:border-slate-500 hover:bg-slate-750"}`}
            >
              <span className="flex items-center justify-between gap-3">
                <span className="font-semibold text-slate-100">{lane.label}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${active ? "bg-blue-500 text-white" : "bg-slate-700 text-slate-200"}`}>{count}</span>
              </span>
              <span className="mt-1 block text-xs leading-5 text-slate-400">{lane.description}</span>
            </button>
          );
        })}
      </div>
      {explanationListing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" role="dialog" aria-modal="true" aria-labelledby="opportunity-explanation-title">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-white/10 bg-[#0b1422] p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-mono uppercase tracking-wider text-cyan-400">Decision evidence</p>
                <h2 id="opportunity-explanation-title" className="mt-1 text-lg font-bold text-white">{explanationListing.title}</h2>
              </div>
              <button type="button" onClick={() => setExplanationListing(null)} className="cursor-pointer rounded-md p-2 text-slate-400 hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400" aria-label="Close explanation">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                ["Expected profit", explanationListing.expected_profit == null ? "—" : `£${explanationListing.expected_profit.toFixed(2)}`],
                ["ROI", explanationListing.roi_pct == null ? "—" : `${explanationListing.roi_pct.toFixed(1)}%`],
                ["Walk-away", explanationListing.walk_away_price == null ? "—" : `£${explanationListing.walk_away_price.toFixed(2)}`],
                ["Conservative resale", explanationListing.conservative_resale_price == null ? "—" : `£${explanationListing.conservative_resale_price.toFixed(2)}`],
                ["Comparables", explanationListing.market_sample_size ?? 0],
                ["Market evidence", (explanationListing.scoring_explanation?.market?.basis ?? "NONE").replace(/_/g, " ")],
                ["Market confidence", `${(explanationListing.market_confidence ?? 0).toFixed(0)}/100`],
                ["Liquidity", explanationListing.liquidity_score == null ? "Unknown" : `${explanationListing.liquidity_score.toFixed(0)}/100`],
                ["Build fit", explanationListing.desirability_score == null ? "Unknown" : `${explanationListing.desirability_score.toFixed(0)}/100`],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3">
                  <p className="text-[11px] text-slate-500">{label}</p><p className="mt-1 font-semibold text-slate-100">{value}</p>
                </div>
              ))}
            </div>
            {!!explanationListing.scoring_explanation?.risk_flags?.length && (
              <div className="mt-4 rounded-xl border border-amber-400/25 bg-amber-400/5 p-4">
                <p className="text-sm font-semibold text-amber-300">Qualification warnings</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">{explanationListing.scoring_explanation.risk_flags.map((flag) => <li key={flag}>{flag.replace(/_/g, " ")}</li>)}</ul>
              </div>
            )}
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div><p className="text-sm font-semibold text-white">Reasons</p><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">{(explanationListing.scoring_explanation?.reasons ?? ["Awaiting recalculation under the new model."]).map((reason) => <li key={reason}>{reason}</li>)}</ul></div>
              <div><p className="text-sm font-semibold text-white">Cost stack</p><dl className="mt-2 space-y-1 text-sm">{Object.entries(explanationListing.scoring_explanation?.cost_breakdown ?? {}).map(([name, amount]) => <div key={name} className="flex justify-between gap-3"><dt className="text-slate-400">{name.replace(/_/g, " ")}</dt><dd className="text-slate-200">£{amount.toFixed(2)}</dd></div>)}</dl></div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

const CLASSIFICATION_ORDER = ["SUPER_GEM", "GEM", "EVIDENCE_LIMITED_DEAL", "OK_DEAL", "AVERAGE_DEAL", "POOR_DEAL", "INSUFFICIENT_DATA", "INELIGIBLE"] as const;
const CLASSIFICATION_COLORS: Record<string, string> = {
  SUPER_GEM: "#f59e0b",
  GEM: "#3b82f6",
  EVIDENCE_LIMITED_DEAL: "#0ea5e9",
  EMERGING_OPPORTUNITY: "#0ea5e9",
  OK_DEAL: "#10b981",
  AVERAGE_DEAL: "#64748b",
  POOR_DEAL: "#ef4444",
  INSUFFICIENT_DATA: "#475569",
  INELIGIBLE: "#9f1239",
};

interface ScatterPoint {
  title: string;
  dealScore: number;
  roiPercent: number;
  roiPlotted: number;
  profit: number;
  absProfit: number;
  classification: string;
}

// Only plot economics produced by the scoring model. Falling back to the
// listing's own delivered price manufactured a 0% ROI for every unscored
// listing and flattened the useful 1,500-point distribution into one line.
function buildScatterPoints(listings: Listing[]): ScatterPoint[] {
  return listings
    .filter((l) => Number.isFinite(l.roi_pct) && Number.isFinite(l.expected_profit))
    .map((l) => ({
        title: l.title,
        dealScore: l.deal_score,
        roiPercent: l.roi_pct!,
        roiPlotted: l.roi_pct!,
        profit: l.expected_profit!,
        absProfit: Math.abs(l.expected_profit!),
        classification: l.classification,
      }));
}

function computeRoiDomain(values: number[]): [number, number] {
  if (values.length === 0) return [-10, 10];
  const sorted = [...values].sort((a, b) => a - b);
  const percentile = (fraction: number) => sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * fraction))];
  const lower = Math.min(0, percentile(0.02));
  const upper = Math.max(0, percentile(0.98));
  const padding = Math.max(2, (upper - lower) * 0.08);
  return [Math.floor(lower - padding), Math.ceil(upper + padding)];
}

function ScatterTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ScatterPoint }> }) {
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0].payload;
  return (
    <div className="bg-slate-900 border border-slate-600 rounded p-3 text-xs max-w-xs">
      <div className="text-slate-100 font-semibold mb-1 truncate">{p.title}</div>
      <div className="text-slate-300">Deal Score: {p.dealScore.toFixed(1)}</div>
      <div className="text-slate-300">Model ROI: {p.roiPercent.toFixed(1)}%</div>
      <div className="text-slate-300">Est. Profit: £{p.profit.toFixed(2)}</div>
    </div>
  );
}

const DealScoreRoiChart = memo(function DealScoreRoiChart({ listings }: { listings: Listing[] }) {
  const points = useMemo(() => buildScatterPoints(listings), [listings]);
  const yDomain = useMemo(() => computeRoiDomain(points.map((p) => p.roiPercent)), [points]);
  const plottedPoints = useMemo(() => points.map((point) => ({
    ...point,
    roiPlotted: Math.max(yDomain[0], Math.min(yDomain[1], point.roiPercent)),
  })), [points, yDomain]);
  const byClassification = useMemo(() => CLASSIFICATION_ORDER.map((c) => ({
    classification: c,
    data: plottedPoints.filter((p) => p.classification === c),
  })).filter((g) => g.data.length > 0), [plottedPoints]);

  if (points.length === 0) {
    return (
      <div className="p-4 bg-slate-800 rounded-lg border border-slate-700 text-slate-400 text-sm">
        No priced listings yet to plot.
      </div>
    );
  }

  const pinnedCount = points.filter((point) => point.roiPercent < yDomain[0] || point.roiPercent > yDomain[1]).length;

  return (
    <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
      <div className="mb-3">
        <div className="text-sm text-slate-300">Deal Score vs Model ROI (dot size = expected profit)</div>
        <div className="mt-0.5 text-xs text-slate-500">
          {points.length.toLocaleString()} listings with model-backed economics. The central 96% sets the scale{pinnedCount > 0 ? `; ${pinnedCount} extreme values are pinned to the chart edges.` : "."}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={360}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            type="number"
            dataKey="dealScore"
            name="Deal Score"
            stroke="#94a3b8"
            tick={{ fill: "#94a3b8", fontSize: 12 }}
            label={{ value: "Deal Score", position: "insideBottom", offset: -5, fill: "#94a3b8" }}
          />
          <YAxis
            type="number"
            dataKey="roiPlotted"
            name="Model ROI"
            unit="%"
            domain={yDomain}
            stroke="#94a3b8"
            tick={{ fill: "#94a3b8", fontSize: 12 }}
            label={{ value: "Model ROI %", angle: -90, position: "insideLeft", fill: "#94a3b8" }}
          />
          <ZAxis type="number" dataKey="absProfit" range={[30, 500]} name="Est. Profit" />
          <Tooltip content={<ScatterTooltip />} cursor={{ strokeDasharray: "3 3" }} />
          {byClassification.map(({ classification, data }) => (
            <Scatter
              key={classification}
              name={classification}
              data={data}
              fill={CLASSIFICATION_COLORS[classification]}
              fillOpacity={0.7}
              isAnimationActive={false}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
      <div className="flex gap-4 mt-2 flex-wrap">
        {byClassification.map(({ classification }) => (
          <div key={classification} className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: CLASSIFICATION_COLORS[classification] }} />
            {classification}
          </div>
        ))}
      </div>
    </div>
  );
});

interface ScanRunHistory {
  id: number;
  searchTerm: string;
  totalListingsFound: number;
  vendors: string[];
  runBy: string;
  durationSeconds: number;
  occurredAt: string;
}

type ScanChartMetric = "processed" | "observations";

const SCAN_SESSION_GAP_MS = 10 * 60 * 1000;
const FALLBACK_VENDOR_COLORS = ["#06b6d4", "#84cc16", "#ec4899", "#a855f7"];

function groupScanHistoryIntoSessions(runs: ScanRunHistory[]) {
  const validRuns = runs
    .map((run) => ({ ...run, timestamp: new Date(run.occurredAt).getTime() }))
    .filter((run) => Number.isFinite(run.timestamp))
    .sort((a, b) => a.timestamp - b.timestamp);
  const sessions: typeof validRuns[] = [];

  for (const run of validRuns) {
    const current = sessions.at(-1);
    const previous = current?.at(-1);
    if (!current || !previous || run.timestamp - previous.timestamp > SCAN_SESSION_GAP_MS) {
      sessions.push([run]);
    } else {
      current.push(run);
    }
  }

  return sessions.map((session, sessionIndex) => {
    const startedAt = session[0].timestamp;
    const vendorTotals: Record<string, number> = {};

    for (const run of session) {
      const vendors = run.vendors.length > 0 ? run.vendors : ["unknown"];
      // Current history records contain one vendor. If an older record
      // combines vendors, divide its collective result without inflating the
      // session total.
      const baseShare = Math.floor(run.totalListingsFound / vendors.length);
      let remainder = run.totalListingsFound % vendors.length;
      for (const vendor of vendors) {
        vendorTotals[vendor] = (vendorTotals[vendor] ?? 0) + baseShare + (remainder-- > 0 ? 1 : 0);
      }
    }

    return {
      sessionId: sessionIndex,
      occurredAtLabel: new Date(startedAt).toLocaleString(undefined, {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      }),
      runBy: session.every((run) => run.runBy === session[0].runBy) ? session[0].runBy : "Mixed",
      searchCount: session.length,
      totalListings: session.reduce((total, run) => total + run.totalListingsFound, 0),
      ...vendorTotals,
    };
  });
}

const ScanRunsOverTimeChart = memo(function ScanRunsOverTimeChart() {
  const [metric, setMetric] = useState<ScanChartMetric>("processed");
  const [runs, setRuns] = useState<ScanRunHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/gem-radar/scan-run-history?limit=10000&basis=${metric}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Scan history request failed (${res.status})`);
        return res.json();
      })
      .then((data: ScanRunHistory[]) => {
        if (!cancelled) setRuns(data);
      })
      .catch((requestError: unknown) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "Could not load scan history");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [metric]);

  const chartData = useMemo(() => groupScanHistoryIntoSessions(runs), [runs]);
  const vendorKeys = useMemo(() => {
    const presentVendors = new Set(runs.flatMap((run) => (run.vendors.length > 0 ? run.vendors : ["unknown"])));
    return [
      ...VENDOR_ORDER.filter((vendor) => presentVendors.has(vendor)),
      ...[...presentVendors].filter((vendor) => !VENDOR_ORDER.includes(vendor as (typeof VENDOR_ORDER)[number])).sort(),
    ];
  }, [runs]);

  if (loading) {
    return (
      <div className="p-4 bg-slate-800 rounded-lg border border-slate-700 text-slate-400 text-sm">
        Loading run history…
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-950/30 rounded-lg border border-red-700/40 text-red-200 text-sm">
        Scan history could not be loaded. {error}
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="p-4 bg-slate-800 rounded-lg border border-slate-700 text-slate-400 text-sm">
        No scan-run history yet. New extension runs will appear here at the time they occurred.
      </div>
    );
  }

  return (
    <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-slate-200">Scan Runs Over Time</div>
          <div className="mt-0.5 text-xs text-slate-400">
            {metric === "processed"
              ? "Exact listings returned by each scan since total-history recording began, split by vendor."
              : "New or changed listing observations written during each scan, split by vendor."}
          </div>
        </div>
        <fieldset className="flex rounded-lg border border-slate-600 bg-slate-900/70 p-1" aria-label="Scan chart metric">
          <legend className="sr-only">Choose the scan chart measurement</legend>
          {([
            ["processed", "Total processed"],
            ["observations", "New/changed"],
          ] as const).map(([value, label]) => (
            <label
              key={value}
              className={`cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium transition-colors duration-200 focus-within:ring-2 focus-within:ring-blue-400 ${metric === value ? "bg-blue-600 text-white" : "text-slate-400 hover:bg-slate-700 hover:text-slate-200"}`}
            >
              <input
                type="radio"
                name="scanChartMetric"
                value={value}
                checked={metric === value}
                onChange={() => {
                  setLoading(true);
                  setError(null);
                  setMetric(value);
                }}
                className="sr-only"
              />
              {label}
            </label>
          ))}
        </fieldset>
      </div>
      <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
        {vendorKeys.map((vendor, index) => (
          <span key={vendor} className="flex items-center gap-1.5">
            <span
              className="h-3 w-3 rounded-sm"
              style={{ backgroundColor: VENDOR_META[vendor]?.color ?? FALLBACK_VENDOR_COLORS[index % FALLBACK_VENDOR_COLORS.length] }}
            />
            {VENDOR_META[vendor]?.label ?? vendor}
          </span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} margin={{ top: 10, right: 20, bottom: 34, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="occurredAtLabel"
            stroke="#94a3b8"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            angle={-25}
            textAnchor="end"
            interval="preserveStartEnd"
            minTickGap={36}
          />
          <YAxis
            stroke="#94a3b8"
            tick={{ fill: "#94a3b8", fontSize: 12 }}
            allowDecimals={false}
            domain={[0, "dataMax"]}
            label={{ value: metric === "processed" ? "Listings processed" : "New/changed observations", angle: -90, position: "insideLeft", fill: "#94a3b8" }}
          />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 6 }}
            labelFormatter={(_, payload) => {
              const session = payload?.[0]?.payload;
              return session
                ? `${session.occurredAtLabel} · ${session.runBy} · ${session.totalListings.toLocaleString()} listings`
                : "";
            }}
          />
          {vendorKeys.map((vendor, index) => (
            <Bar
              key={vendor}
              dataKey={vendor}
              name={VENDOR_META[vendor]?.label ?? vendor}
              stackId="vendors"
              fill={VENDOR_META[vendor]?.color ?? FALLBACK_VENDOR_COLORS[index % FALLBACK_VENDOR_COLORS.length]}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
});

const AnalyticsTab = memo(function AnalyticsTab({ listings }: { listings: Listing[] }) {
  return (
    <div className="space-y-6">
      <ScanRunsOverTimeChart />
      <DealScoreRoiChart listings={listings} />

      <div className="p-4 bg-blue-900/20 rounded-lg border border-blue-700/30">
        <p className="text-blue-200">
          <strong>More Analytics Coming Soon:</strong> Graphs showing revenue by playbook, profit by playbook, time to sell, and component prioritization insights will appear here once build data is available.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
          <div className="text-sm text-slate-400 mb-2">Components by Profit</div>
          <div className="text-slate-400 text-xs">Data not yet available</div>
        </div>

        <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
          <div className="text-sm text-slate-400 mb-2">Time to Sell by Type</div>
          <div className="text-slate-400 text-xs">Data not yet available</div>
        </div>

        <div className="p-4 bg-slate-800 rounded-lg border border-slate-700 col-span-2">
          <div className="text-sm text-slate-400 mb-2">Playbook Performance</div>
          <div className="text-slate-400 text-xs">Build data needed for analysis</div>
        </div>
      </div>
    </div>
  );
});

// Submissions the extension has fired at /scans-queued but the worker
// hasn't drained yet — pending+processing is "left to process", completed
// is the running total ever finished (never reset, so it only grows).
function QueueStatusBar({ queue }: { queue: QueueStatus | null }) {
  if (!queue) return null;

  const left = queue.pending + queue.processing;
  const total = left + queue.completed;
  const pct = total > 0 ? Math.round((queue.completed / total) * 100) : 100;
  const isIdle = left === 0;

  return (
    <div className="flex items-center gap-3 px-3 py-1.5 rounded-lg glass-panel">
      <div className="flex items-center gap-1.5 shrink-0">
        {isIdle ? (
          <CheckCircle2 size={15} className="text-emerald-400" />
        ) : (
          <Loader2 size={15} className="text-blue-400 animate-spin" />
        )}
        <span className="text-xs font-semibold text-slate-200 whitespace-nowrap">
          {isIdle ? "Queue idle" : `${queue.processing} processing · ${queue.pending} waiting`}
        </span>
      </div>

      <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden shrink-0">
        <div
          className="h-full bg-blue-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="flex items-center gap-3 text-[11px] text-slate-400 shrink-0">
        <span className="flex items-center gap-1 text-emerald-400" title="Total processed successfully">
          <CheckCircle2 size={12} />
          {queue.completed}
        </span>
        {queue.failed > 0 && (
          <span className="flex items-center gap-1 text-red-400" title="Gave up after max retries">
            <AlertTriangle size={12} />
            {queue.failed}
          </span>
        )}
      </div>
    </div>
  );
}

export default function SourcingPage() {
  return (
    <Suspense fallback={null}>
      <SourcingPageInner />
    </Suspense>
  );
}

function SourcingPageInner() {
  const searchParams = useSearchParams();
  const highlightListingId = searchParams.get("listing");
  const [mainTab, setMainTab] = useState<MainTab>("stats");
  const [listings, setListings] = useState<Listing[]>([]);
  const [componentGems, setComponentGems] = useState<Record<string, GemData | null> | null>(null);
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [nextRefreshIn, setNextRefreshIn] = useState(0);
  const [nextScanAt, setNextScanAt] = useState<Date | null>(null);
  const [lastScanAt, setLastScanAt] = useState<Date | null>(null);
  const [scanIntervalMinutes, setScanIntervalMinutes] = useState<number | null>(null);
  const [nowTick, setNowTick] = useState(() => Date.now());
  const [marketSnapshot, setMarketSnapshot] = useState<MarketSnapshot | null>(null);
  const dataRequestInFlight = useRef(false);

  useEffect(() => {
    if (highlightListingId) setMainTab("listings");
  }, [highlightListingId]);

  // Scanning happens client-side in the browser extension on its own
  // timer, not a backend-scheduled job (the old "flip_opportunities"
  // APScheduler job this used to query was disabled when that queue/
  // extension architecture replaced it) — so next_scan_at here is a
  // best-effort estimate derived from real activity (scan-wave start +
  // the configured interval), not a guarantee. See
  // /gem-radar/scan-schedule-status's docstring.
  const fetchScanSchedule = async () => {
    try {
      const status = await api.gemRadar.scanScheduleStatus();
      const scanStart = status.scan_started_at ?? status.last_scan_at;
      setLastScanAt(scanStart ? new Date(scanStart) : null);
      setNextScanAt(status.next_scan_at ? new Date(status.next_scan_at) : null);
      setScanIntervalMinutes(status.scan_interval_minutes);
    } catch (error) {
      console.error("Error fetching scan schedule:", error);
    }
  };

  const fetchMarketSnapshot = async () => {
    try {
      setMarketSnapshot(await api.gemRadar.marketSnapshot());
    } catch (error) {
      console.error("Error fetching market snapshot:", error);
    }
  };

  const fetchData = async () => {
    if (dataRequestInFlight.current) return;
    dataRequestInFlight.current = true;
    try {
      // Do not let one unhealthy Gem Radar endpoint leave the whole page in
      // its initial loading state forever. Each poll gets a bounded lifetime;
      // the next scheduled refresh can recover normally.
      const signal = AbortSignal.timeout(15_000);
      const [listingsRes, componentRes, queueRes] = await Promise.all([
        fetch(`/api/gem-radar/scored-listings-latest-run`, { cache: "no-store", signal }),
        fetch(`/api/gem-radar/gem-by-component`, { cache: "no-store", signal }),
        fetch(`/api/gem-radar/queue-status`, { cache: "no-store", signal }),
      ]);

      if (listingsRes.ok) {
        const data = await listingsRes.json();
        setListings(data);
        if (data.length === 0) {
          console.debug("scored-listings returned empty (queue still processing or listings not recently observed)");
        } else {
          const gems = data.filter((l: Listing) => l.classification === "GEM").length;
          const superGems = data.filter((l: Listing) => l.classification === "SUPER_GEM").length;
          console.debug(`scored-listings: ${data.length} total, ${superGems} SUPER_GEM, ${gems} GEM`);
        }
      } else {
        console.warn(`scored-listings returned ${listingsRes.status}`);
      }
      if (componentRes.ok) {
        const data = await componentRes.json();
        setComponentGems(data);
      }
      if (queueRes.ok) {
        const data = await queueRes.json();
        setQueueStatus(data);
      }

      setLastUpdate(new Date());
      setNextRefreshIn(5);
    } catch (error) {
      console.error("Error fetching data:", error);
    } finally {
      dataRequestInFlight.current = false;
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);

    // Countdown timer for next refresh
    const countdown = setInterval(() => {
      setNextRefreshIn((prev) => (prev > 0 ? prev - 1 : 5));
    }, 1000);

    return () => {
      clearInterval(interval);
      clearInterval(countdown);
    };
  }, []);

  useEffect(() => {
    fetchScanSchedule();
    fetchMarketSnapshot();
    // Re-poll every 30s (cheap enough, and catches a scan that just landed
    // so the countdown snaps to the new estimate promptly).
    const scheduleInterval = setInterval(fetchScanSchedule, 30000);
    const snapshotInterval = setInterval(fetchMarketSnapshot, 30000);
    // Tick every second purely to re-render the countdown display.
    const tickInterval = setInterval(() => setNowTick(Date.now()), 1000);

    return () => {
      clearInterval(scheduleInterval);
      clearInterval(snapshotInterval);
      clearInterval(tickInterval);
    };
  }, []);

  const scanCountdownLabel = (() => {
    if (!nextScanAt) return "No scan activity yet";
    const remainingMs = nextScanAt.getTime() - nowTick;
    if (remainingMs <= 0) return "Due now (est.)";
    const totalSeconds = Math.floor(remainingMs / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const pad = (n: number) => String(n).padStart(2, "0");
    return hours > 0 ? `~${hours}:${pad(minutes)}:${pad(seconds)}` : `~${minutes}:${pad(seconds)}`;
  })();

  return (
    <div className="relative flex flex-col h-full gap-4 p-6 bg-slate-950 overflow-hidden">
      {/* Ambient glow blobs — the colour backdrop glass panels refract against */}
      <div className="pointer-events-none absolute -top-32 -left-24 w-[420px] h-[420px] rounded-full bg-blue-600/25 blur-[110px]" />
      <div className="pointer-events-none absolute top-40 -right-32 w-[480px] h-[480px] rounded-full bg-purple-600/20 blur-[120px]" />
      <div className="pointer-events-none absolute bottom-0 left-1/3 w-[380px] h-[380px] rounded-full bg-emerald-500/10 blur-[100px]" />

      {/* Header */}
      <div className="relative flex items-center justify-between gap-4 mb-2">
        <div className="flex items-center gap-4 rounded-2xl border border-white/10 bg-white/[0.06] backdrop-blur-xl px-5 py-3 shadow-[0_8px_32px_rgba(0,0,0,0.35)]">
          <h1 className="text-2xl font-bold text-white tracking-tight">Sourcing Dashboard</h1>
        </div>

        <div className="flex items-center gap-3">
          {/* Next scan countdown — estimate only, see fetchScanSchedule's comment */}
          <div
            className="flex items-center gap-2.5 rounded-2xl border border-white/10 bg-white/[0.06] backdrop-blur-xl px-4 py-3 shadow-[0_8px_32px_rgba(0,0,0,0.35)]"
            title={
              nextScanAt
                ? `Expected from scan start (${lastScanAt?.toLocaleTimeString() ?? "unknown"}) + the configured ${scanIntervalMinutes ?? "?"}-minute interval. Scanning runs client-side in the browser extension, so this remains an estimate while the extension's browser is open.`
                : "No scan activity observed yet"
            }
          >
            <Timer className={`w-4 h-4 ${nextScanAt ? "text-emerald-400" : "text-slate-500"}`} />
            <div className="flex flex-col leading-tight">
              <span className="text-[10px] uppercase tracking-wider text-slate-400">Next scan (est.)</span>
              <span className={`font-mono text-sm font-semibold tabular-nums ${nextScanAt ? "text-white" : "text-slate-500"}`}>
                {scanCountdownLabel}
              </span>
            </div>
          </div>

          <Link
            href="/sourcing/history"
            aria-label="Open run history"
            title="Open run history"
            className="grid h-[50px] w-[50px] cursor-pointer place-items-center rounded-2xl border border-white/10 bg-white/[0.06] text-slate-300 shadow-[0_8px_32px_rgba(0,0,0,0.35)] backdrop-blur-xl transition-colors duration-200 hover:border-blue-400/40 hover:bg-blue-500/15 hover:text-blue-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            <History className="h-5 w-5" />
          </Link>

          <button
            onClick={fetchData}
            disabled={loading}
            className="p-3 rounded-2xl border border-white/10 bg-white/[0.06] backdrop-blur-xl hover:bg-white/[0.12] transition disabled:opacity-50 shadow-[0_8px_32px_rgba(0,0,0,0.35)]"
            title="Refresh data now"
          >
            <RefreshCw className={`w-5 h-5 text-white ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Main Tabs */}
      <div className="relative flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-xl px-3 py-2 shadow-[0_8px_32px_rgba(0,0,0,0.35)]">
        <div className="flex gap-2">
          {[
            { id: "stats", label: "Stats", icon: BarChart3 },
            { id: "listings", label: "Listings", icon: Gem },
            { id: "analytics", label: "Analytics", icon: BarChart3 },
          ].map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setMainTab(id as MainTab)}
              className={`px-4 py-2 rounded-xl transition font-semibold ${
                mainTab === id
                  ? "bg-blue-500/90 text-white shadow-[0_4px_16px_rgba(59,130,246,0.4)]"
                  : "text-slate-300 hover:bg-white/[0.08]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto">
        {mainTab === "stats" && (
          <>
            <MarketSnapshotPanel snapshot={marketSnapshot} />
            <PipelineDashboard queueStatus={queueStatus} />
            <StatsTab componentGems={componentGems || undefined} />
          </>
        )}
        {mainTab === "listings" && <ListingsTab listings={listings} highlightListingId={highlightListingId} />}
        {mainTab === "analytics" && <AnalyticsTab listings={listings} />}
      </div>
    </div>
  );
}
