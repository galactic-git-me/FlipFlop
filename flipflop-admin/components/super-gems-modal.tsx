"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { X, Zap, ExternalLink, TrendingUp, Cpu, HardDrive, MemoryStick, RefreshCw, Package } from "lucide-react";
import { Listing, GroupedPart } from "@/lib/types";
import { api, API_BASE_URL } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const COMPONENT_CATEGORIES = [
  { id: "gpu",         label: "GPU",         emoji: "🎮" },
  { id: "cpu",         label: "CPU",         emoji: "⚡" },
  { id: "ram",         label: "RAM",         emoji: "💾" },
  { id: "ssd",         label: "SSD",         emoji: "💿" },
  { id: "psu",         label: "PSU",         emoji: "🔌" },
  { id: "motherboard", label: "Motherboard", emoji: "🔧" },
  { id: "cooler",      label: "Cooler",      emoji: "❄️"  },
] as const;

type ComponentCategory = typeof COMPONENT_CATEGORIES[number]["id"];
type ModalTab = "flip_opportunities" | ComponentCategory;

// ── Fetch helpers ─────────────────────────────────────────────────────────────
async function fetchGems(superOnly: boolean): Promise<Listing[]> {
  // Fetch from gem-radar scored listings (all marketplaces)
  const res = await fetch(`${API_BASE_URL}/gem-radar/scored-listings`);
  const data = await res.json();
  const allListings = Array.isArray(data) ? data : [];

  // Filter and sort by deal_score
  const filtered = allListings
    .filter((l: any) => {
      if (superOnly) {
        return l.classification === 'SUPER_GEM';
      } else {
        return ['GEM', 'SUPER_GEM'].includes(l.classification);
      }
    })
    .sort((a: any, b: any) => (b.deal_score || 0) - (a.deal_score || 0))
    .slice(0, superOnly ? 60 : 100)
    .map((l: any): Listing => ({
      id: l.listing_id || l.id,
      external_id: String(l.listing_id || l.external_id || l.id),
      source_name: l.source || l.source_name,
      title: l.title,
      price: l.delivered_price || l.price || 0,
      url: l.url || `https://www.ebay.co.uk/itm/${l.listing_id}/`,
      image_urls: l.image_url ? [l.image_url] : [],
      location: l.location || null,
      condition: l.condition || null,
      cpu: l.category === 'cpu' ? l.title : null,
      ram_gb: l.ram_gb || null,
      ram_type: l.ram_type || null,
      storage_gb: l.storage_gb || null,
      storage_type: l.storage_type || null,
      gpu: l.category === 'gpu' ? l.title : null,
      has_psu: l.has_psu || false,
      gem_score: l.deal_score || 0,
      classification: l.classification === 'SUPER_GEM' ? 'amazing_gem' : 'gem',
      gem_signals: l.gem_signals || [],
      estimated_resale: l.market_used_price || l.market_new_price || 0,
      estimated_upgrade_cost: l.estimated_upgrade_cost || null,
      resale_low: l.resale_low || null,
      resale_high: l.resale_high || null,
      resale_comp_count: l.resale_comp_count || null,
      estimated_profit: (l.market_used_price || l.market_new_price || 0) - (l.delivered_price || l.price || 0),
      listing_type: l.listing_type || null,
      listing_ends_at: l.listing_ends_at || null,
      expected_buy_price: l.expected_buy_price || null,
      seller_name: l.seller || l.seller_name || null,
      seller_feedback_count: l.seller_feedback_count || null,
      seller_feedback_pct: l.seller_feedback_pct || null,
      seller_type: l.seller_type || null,
      seller_has_shop: l.seller_has_shop || false,
      listed_at: l.listing_observed_at || l.listed_at || null,
      status: l.status || 'active',
      first_seen_at: l.listing_observed_at || l.first_seen_at || new Date().toISOString(),
      last_seen_at: l.listing_observed_at || l.last_seen_at || new Date().toISOString(),
      watch_count: l.watch_count || null,
      bid_count: l.bid_count || null,
      claude_verdict: l.classification === 'SUPER_GEM' ? 'GEM' : 'GOOD',
      claude_flipability_score: l.claude_flipability_score || null,
      claude_expected_profit: l.claude_expected_profit || null,
      claude_roi: l.claude_roi || null,
      claude_confidence: l.confidence || l.claude_confidence || null,
      claude_capital_efficiency: l.claude_capital_efficiency || null,
      claude_resale_demand: l.claude_resale_demand || null,
      claude_upgrade_complexity: l.claude_upgrade_complexity || null,
      claude_reasoning: l.reasoning_summary || l.claude_reasoning || null,
      claude_main_risk: l.claude_main_risk || null,
      claude_judged_at: l.claude_judged_at || null,
    }));

  return filtered;
}

async function fetchCategoryGems(category: ComponentCategory): Promise<GroupedPart[]> {
  const res = await fetch(`${API_BASE_URL}/parts/grouped?category=${category}`);
  const data: GroupedPart[] = await res.json();
  return (Array.isArray(data) ? data : [])
    .filter(p => p.gem_classification !== null && p.claude_verdict !== "REJECT")
    .sort((a, b) => {
      if (a.gem_classification === "super_gem" && b.gem_classification !== "super_gem") return -1;
      if (b.gem_classification === "super_gem" && a.gem_classification !== "super_gem") return 1;
      return (b.gem_score ?? 0) - (a.gem_score ?? 0);
    });
}

// ── Modal shell ───────────────────────────────────────────────────────────────
export function SuperGemsModal({
  open,
  onClose,
  superOnly = true,
}: {
  open: boolean;
  onClose: () => void;
  superOnly?: boolean;
}) {
  const [mounted, setMounted] = useState(false);
  const [activeTab, setActiveTab] = useState<ModalTab>("flip_opportunities");
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(false);
  const [parts, setParts] = useState<Partial<Record<ComponentCategory, GroupedPart[]>>>({});
  const [partsLoading, setPartsLoading] = useState<Partial<Record<ComponentCategory, boolean>>>({});

  useEffect(() => { setMounted(true); }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try { setListings(await fetchGems(superOnly)); }
    catch { setListings([]); }
    finally { setLoading(false); }
  }, [superOnly]);

  const loadCategory = useCallback(async (cat: ComponentCategory) => {
    if (parts[cat] !== undefined) return;
    setPartsLoading(p => ({ ...p, [cat]: true }));
    try { setParts(p => ({ ...p, [cat]: [] })); // mark as started
          const gems = await fetchCategoryGems(cat);
          setParts(p => ({ ...p, [cat]: gems }));
    } catch { setParts(p => ({ ...p, [cat]: [] })); }
    finally { setPartsLoading(p => ({ ...p, [cat]: false })); }
  }, [parts]);

  useEffect(() => { if (open) void load(); }, [open, load]);

  useEffect(() => {
    if (open && activeTab !== "flip_opportunities") void loadCategory(activeTab as ComponentCategory);
  }, [open, activeTab, loadCategory]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!mounted || !open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex flex-col bg-black/85 backdrop-blur-md"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-cyan-400/20 bg-[#030d1a]/90 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-cyan-300 animate-pulse" />
          <h2 className="text-lg font-black text-cyan-100 tracking-wide">{superOnly ? "Super Gems" : "All Gems"}</h2>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => activeTab === "flip_opportunities" ? void load() : void loadCategory(activeTab as ComponentCategory)}
            disabled={loading || !!partsLoading[activeTab as ComponentCategory]}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={`w-4 h-4 ${(loading || !!partsLoading[activeTab as ComponentCategory]) ? "animate-spin" : ""}`} />
          </button>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-white/10 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-0 border-b border-white/[0.06] bg-[#030d1a]/70 flex-shrink-0 px-4 overflow-x-auto">
        <button
          onClick={() => setActiveTab("flip_opportunities")}
          className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-all ${
            activeTab === "flip_opportunities"
              ? "border-cyan-400 text-cyan-300"
              : "border-transparent text-slate-500 hover:text-slate-300"
          }`}
        >
          💎 Flip Opportunities
          {!loading && listings.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full bg-cyan-400/15 text-cyan-400 text-[10px] font-bold">{listings.length}</span>
          )}
        </button>
        {COMPONENT_CATEGORIES.map(cat => {
          const catParts = parts[cat.id];
          const isLoading = !!partsLoading[cat.id];
          return (
            <button
              key={cat.id}
              onClick={() => setActiveTab(cat.id)}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-all ${
                activeTab === cat.id
                  ? "border-emerald-400 text-emerald-300"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              {cat.emoji} {cat.label}
              {!isLoading && catParts && catParts.length > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-emerald-400/15 text-emerald-400 text-[10px] font-bold">{catParts.length}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Scrollable gallery */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {activeTab === "flip_opportunities" && (
          loading ? (
            <div className="flex items-center justify-center h-64 text-slate-500 text-sm gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" /> Loading gems…
            </div>
          ) : listings.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-slate-600">
              <Zap className="w-12 h-12 opacity-20" />
              <p className="text-sm">No {superOnly ? "super gems" : "gems"} found yet — run a scan first.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {listings.map((l) => <FlipCard key={l.id} listing={l} />)}
            </div>
          )
        )}

        {activeTab !== "flip_opportunities" && (() => {
          const cat = activeTab as ComponentCategory;
          const catParts = parts[cat];
          const isLoading = !!partsLoading[cat];
          const catCfg = COMPONENT_CATEGORIES.find(c => c.id === cat);
          if (isLoading || catParts === undefined) return (
            <div className="flex items-center justify-center h-64 text-slate-500 text-sm gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" /> Loading…
            </div>
          );
          if (catParts.length === 0) return (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-slate-600">
              <Package className="w-12 h-12 opacity-20" />
              <p className="text-sm">No {catCfg?.label ?? cat} gems found yet.</p>
            </div>
          );
          return (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {catParts.map((p) => <ComponentCard key={`${p.category}::${p.name}`} part={p} />)}
            </div>
          );
        })()}
      </div>
    </div>,
    document.body
  );
}

// ── Component gem card (modal) ────────────────────────────────────────────────
function ComponentCard({ part: p }: { part: GroupedPart }) {
  const isSuperGem = p.gem_classification === "super_gem";
  const aiVerified = p.claude_verdict === "GEM" || p.claude_verdict === "GOOD";
  const bestPrice = p.cheapest_good_price ?? p.cheapest_price ?? 0;
  const sourceUrl = p.cheapest_good_url ?? p.cheapest_url ?? undefined;

  return (
    <div
      className={`rounded-xl overflow-hidden border flex flex-col ${
        isSuperGem
          ? "border-cyan-400/30 bg-[#030f1c] shadow-[0_4px_20px_rgba(34,211,238,0.12)]"
          : "border-emerald-400/25 bg-[#031209] shadow-[0_4px_16px_rgba(52,211,153,0.08)]"
      }`}
      style={{ height: "220px" }}
    >
      {/* Image / icon */}
      <div className="h-20 flex-shrink-0 bg-[#050e1a] flex items-center justify-center relative overflow-hidden">
        {p.image_url ? (
          <img src={p.image_url} alt={p.name} className="w-full h-full object-contain opacity-80" />
        ) : (
          <Package className="w-8 h-8 text-slate-700" />
        )}
        <div className={`absolute top-1.5 left-1.5 flex items-center gap-0.5 px-1.5 py-0.5 rounded backdrop-blur-sm border text-[8px] font-bold uppercase tracking-wide ${
          isSuperGem ? "bg-cyan-400/20 border-cyan-400/40 text-cyan-200" : "bg-emerald-400/20 border-emerald-400/40 text-emerald-200"
        }`}>
          <Zap className={`w-2 h-2 ${isSuperGem ? "text-cyan-300" : "text-emerald-300"}`} />
          {isSuperGem ? "Super" : "Gem"}
        </div>
        {p.gem_score != null && (
          <div className={`absolute top-1.5 right-1.5 px-1 py-0.5 rounded text-[8px] font-black ${
            isSuperGem ? "text-cyan-300" : "text-emerald-300"
          }`}>
            -{p.gem_score.toFixed(0)}%
          </div>
        )}
      </div>

      {/* Details */}
      <div className="flex-1 p-2.5 flex flex-col gap-1.5 min-h-0">
        <p className="text-[10px] font-semibold text-slate-100 line-clamp-2 leading-tight">{p.name}</p>
        <p className="text-[9px] text-slate-600 uppercase tracking-wide">{p.category}</p>

        {aiVerified && (
          <span className="inline-flex items-center gap-0.5 text-[8px] text-violet-400">✓ AI verified</span>
        )}

        <div className="mt-auto flex items-center justify-between">
          <span className={`text-sm font-black ${isSuperGem ? "text-cyan-300" : "text-emerald-300"}`}>
            {formatCurrency(bestPrice)}
          </span>
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="flex items-center gap-0.5 px-2 py-1 rounded-md bg-white/5 border border-white/10 text-[9px] text-slate-400 hover:text-white transition-colors"
            >
              <ExternalLink className="w-2.5 h-2.5" /> View
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

// ── 3D flip card ──────────────────────────────────────────────────────────────
function FlipCard({ listing: l }: { listing: Listing }) {
  const [flipped, setFlipped] = useState(false);
  const [flipping, setFlipping] = useState(false);

  const profit =
    l.claude_expected_profit != null && l.claude_expected_profit > 0
      ? l.claude_expected_profit
      : (l.estimated_profit ?? 0);

  const profitColor =
    profit > 200 ? "#22d3ee" : profit > 100 ? "#00dc82" : profit > 0 ? "#fbbf24" : "#f87171";

  const handleFlip = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setFlipping(true);
    try {
      await api.flips.create({ listing_id: l.id });
      window.location.href = "/flips";
    } catch {
      setFlipping(false);
    }
  };

  const scoreColor =
    (l.gem_score ?? 0) >= 80 ? "#22d3ee" :
    (l.gem_score ?? 0) >= 60 ? "#00dc82" :
    "#fbbf24";

  return (
    <div
      className="relative cursor-pointer"
      style={{ height: "280px", perspective: "1000px" }}
      onMouseEnter={() => setFlipped(true)}
      onMouseLeave={() => setFlipped(false)}
    >
      {/* The card that flips */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          transformStyle: "preserve-3d",
          transition: "transform 0.55s cubic-bezier(0.23, 1, 0.32, 1)",
          transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)",
        }}
      >
        {/* ── FRONT ─────────────────────────────────────────────────────────── */}
        <div
          style={{ backfaceVisibility: "hidden" }}
          className="absolute inset-0 rounded-xl overflow-hidden border border-cyan-400/25 shadow-[0_4px_24px_rgba(34,211,238,0.12)]"
        >
          {/* Full-bleed image */}
          {l.image_urls?.[0] ? (
            <img
              src={l.image_urls[0]}
              alt={l.title}
              className="absolute inset-0 w-full h-full object-cover"
            />
          ) : (
            <div className="absolute inset-0 bg-gradient-to-br from-[#05111e] to-[#0a1f35] flex items-center justify-center">
              <Zap className="w-12 h-12 text-cyan-400/20" />
            </div>
          )}

          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/40 to-black/10" />

          {/* Top badge */}
          {l.claude_verdict === "GEM" ? (
            <div className="absolute top-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-cyan-400/20 border border-cyan-400/40 backdrop-blur-sm">
              <Zap className="w-2.5 h-2.5 text-cyan-300" />
              <span className="text-[9px] font-bold text-cyan-200 uppercase tracking-wider">Super Gem</span>
            </div>
          ) : (
            <div className="absolute top-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-emerald-400/20 border border-emerald-400/40 backdrop-blur-sm">
              <Zap className="w-2.5 h-2.5 text-emerald-300" />
              <span className="text-[9px] font-bold text-emerald-200 uppercase tracking-wider">Gem</span>
            </div>
          )}

          {/* Score top-right */}
          {l.gem_score != null && (
            <div
              className="absolute top-2 right-2 rounded-md px-2 py-0.5 backdrop-blur-sm border text-xs font-black"
              style={{
                color: scoreColor,
                borderColor: `${scoreColor}50`,
                background: `${scoreColor}18`,
              }}
            >
              {l.gem_score.toFixed(0)}
            </div>
          )}

          {/* Bottom: semi-transparent info box */}
          <div className="absolute bottom-0 left-0 right-0 p-3 bg-black/70 backdrop-blur-sm">
            <p className="text-xs font-semibold text-white leading-snug line-clamp-2 mb-1.5">
              {l.title}
            </p>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-400">{formatCurrency(l.price)}</span>
              {profit > 0 && (
                <span className="text-xs font-black" style={{ color: profitColor }}>
                  +{formatCurrency(profit)}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* ── BACK ──────────────────────────────────────────────────────────── */}
        <div
          style={{
            backfaceVisibility: "hidden",
            transform: "rotateY(180deg)",
          }}
          className="absolute inset-0 rounded-xl overflow-hidden border border-cyan-400/40 bg-[#030d1a] shadow-[0_4px_30px_rgba(34,211,238,0.18)] flex flex-col"
        >
          {/* Subtle top image strip */}
          {l.image_urls?.[0] && (
            <div className="h-16 flex-shrink-0 relative overflow-hidden">
              <img
                src={l.image_urls[0]}
                alt=""
                className="absolute inset-0 w-full h-full object-cover opacity-30 blur-sm scale-110"
              />
              <div className="absolute inset-0 bg-gradient-to-b from-transparent to-[#030d1a]" />
              {/* Score badge */}
              {l.gem_score != null && (
                <div className="absolute top-2 left-2 flex items-center gap-1">
                  <Zap className="w-3 h-3 text-cyan-300" />
                  <span className="text-sm font-black" style={{ color: scoreColor }}>
                    {l.gem_score.toFixed(0)}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Details */}
          <div className="flex-1 overflow-hidden p-3 flex flex-col gap-2 min-h-0">
            <p className="text-[11px] font-semibold text-slate-100 leading-snug line-clamp-2">
              {l.title}
            </p>

            {/* Specs grid */}
            <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[10px]">
              {l.cpu && (
                <div className="col-span-2 flex items-center gap-1 text-slate-400">
                  <Cpu className="w-2.5 h-2.5 text-slate-600 flex-shrink-0" />
                  <span className="truncate font-mono">{l.cpu.slice(0, 28)}</span>
                </div>
              )}
              {l.gpu && (
                <div className="col-span-2 flex items-center gap-1 text-emerald-400">
                  <span className="text-slate-600 flex-shrink-0">GPU</span>
                  <span className="truncate font-mono">{l.gpu.slice(0, 24)}</span>
                </div>
              )}
              {l.ram_gb && (
                <div className="flex items-center gap-1 text-slate-400">
                  <MemoryStick className="w-2.5 h-2.5 text-slate-600 flex-shrink-0" />
                  <span>{l.ram_gb}GB RAM</span>
                </div>
              )}
              {l.storage_gb && (
                <div className="flex items-center gap-1 text-slate-400">
                  <HardDrive className="w-2.5 h-2.5 text-slate-600 flex-shrink-0" />
                  <span>{l.storage_gb}GB {l.storage_type ?? "SSD"}</span>
                </div>
              )}
            </div>

            {/* AI reasoning */}
            {l.claude_reasoning && (
              <p className="text-[9px] text-slate-500 italic line-clamp-2 border-t border-white/5 pt-1.5">
                {l.claude_reasoning}
              </p>
            )}

            {/* Demand Signals */}
            {(l.watch_count != null || l.bid_count != null) && (
              <div className="border-t border-white/8 pt-2 space-y-0.5">
                {l.watch_count != null && (
                  <div className="flex items-baseline justify-between text-[10px]">
                    <span className="text-slate-600">Watches</span>
                    <span className="text-slate-300 font-semibold">{l.watch_count}</span>
                  </div>
                )}
                {l.bid_count != null && (
                  <div className="flex items-baseline justify-between text-[10px]">
                    <span className="text-slate-600">Bids</span>
                    <span className="text-slate-300 font-semibold">{l.bid_count}</span>
                  </div>
                )}
              </div>
            )}

            {/* Pricing */}
            <div className="border-t border-white/8 pt-2 space-y-0.5">
              <div className="flex items-baseline justify-between text-[10px]">
                <span className="text-slate-600">Buy</span>
                <span className="text-slate-300 font-semibold">{formatCurrency(l.price)}</span>
              </div>
              <div className="flex items-baseline justify-between text-[10px]">
                <span className="text-slate-600">Resale</span>
                <span className="text-slate-200 font-semibold">{formatCurrency(l.estimated_resale ?? 0)}</span>
              </div>
              <div className="flex items-baseline justify-between text-[11px] font-black pt-0.5">
                <span className="text-slate-500 flex items-center gap-1">
                  <TrendingUp className="w-2.5 h-2.5" /> Profit
                </span>
                <span style={{ color: profitColor }}>
                  {profit > 0 ? "+" : ""}{formatCurrency(profit)}
                </span>
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-1.5 px-3 pb-3 flex-shrink-0">
            {l.url && (
              <a
                href={l.url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-[10px] font-semibold bg-white/6 border border-white/10 text-slate-300 hover:bg-white/12 hover:text-white transition-colors"
              >
                <ExternalLink className="w-2.5 h-2.5" /> View
              </a>
            )}
            <button
              onClick={handleFlip}
              disabled={flipping}
              className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-[10px] font-bold bg-cyan-500/20 border border-cyan-400/40 text-cyan-300 hover:bg-cyan-500/35 hover:text-cyan-100 transition-colors disabled:opacity-50"
            >
              <Zap className="w-2.5 h-2.5" />
              {flipping ? "Adding…" : "Flip"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
