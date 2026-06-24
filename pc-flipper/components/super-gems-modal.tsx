"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { X, Zap, ExternalLink, TrendingUp, Cpu, HardDrive, MemoryStick, RefreshCw, Package } from "lucide-react";
import { Listing, GroupedPart } from "@/lib/types";
import { api, API_BASE_URL } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

type ModalTab = "flip_opportunities" | "components";

// ── Fetch gems ────────────────────────────────────────────────────────────────
async function fetchGems(superOnly: boolean): Promise<Listing[]> {
  const params = new URLSearchParams(
    superOnly
      ? { claude_verdict: "GEM", classification: "gem", sort_by: "gem_score", sort_desc: "true", limit: "60", min_profit: "100" }
      : { gem_only: "true", sort_by: "gem_score", sort_desc: "true", limit: "100", whole_pc_only: "true", min_price: "50", min_profit: "80" }
  );
  const res = await fetch(`${API_BASE_URL}/listings/?${params}`);
  const data = await res.json();
  return Array.isArray(data) ? data : (data.items ?? []);
}

async function fetchComponentGems(): Promise<GroupedPart[]> {
  const res = await fetch(`${API_BASE_URL}/parts/grouped`);
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
  const [componentGems, setComponentGems] = useState<GroupedPart[]>([]);
  const [loading, setLoading] = useState(false);
  const [componentsLoading, setComponentsLoading] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setListings(await fetchGems(superOnly));
    } catch {
      setListings([]);
    } finally {
      setLoading(false);
    }
  }, [superOnly]);

  const loadComponents = useCallback(async () => {
    if (componentGems.length > 0) return;
    setComponentsLoading(true);
    try {
      setComponentGems(await fetchComponentGems());
    } catch {
      setComponentGems([]);
    } finally {
      setComponentsLoading(false);
    }
  }, [componentGems.length]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  useEffect(() => {
    if (open && activeTab === "components") void loadComponents();
  }, [open, activeTab, loadComponents]);

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
            onClick={() => activeTab === "flip_opportunities" ? void load() : void loadComponents()}
            disabled={loading || componentsLoading}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={`w-4 h-4 ${(loading || componentsLoading) ? "animate-spin" : ""}`} />
          </button>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-white/10 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-0 border-b border-white/[0.06] bg-[#030d1a]/70 flex-shrink-0 px-4">
        <button
          onClick={() => setActiveTab("flip_opportunities")}
          className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 transition-all ${
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
        <button
          onClick={() => setActiveTab("components")}
          className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 transition-all ${
            activeTab === "components"
              ? "border-emerald-400 text-emerald-300"
              : "border-transparent text-slate-500 hover:text-slate-300"
          }`}
        >
          🔧 Components
          {!componentsLoading && componentGems.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full bg-emerald-400/15 text-emerald-400 text-[10px] font-bold">{componentGems.length}</span>
          )}
        </button>
      </div>

      {/* Scrollable gallery */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {activeTab === "flip_opportunities" && (
          loading ? (
            <div className="flex items-center justify-center h-64 text-slate-500 text-sm gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" />
              Loading gems…
            </div>
          ) : listings.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-slate-600">
              <Zap className="w-12 h-12 opacity-20" />
              <p className="text-sm">No {superOnly ? "super gems" : "gems"} found yet — run a scan first.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {listings.map((l) => (
                <FlipCard key={l.id} listing={l} />
              ))}
            </div>
          )
        )}

        {activeTab === "components" && (
          componentsLoading ? (
            <div className="flex items-center justify-center h-64 text-slate-500 text-sm gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" />
              Loading component gems…
            </div>
          ) : componentGems.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-slate-600">
              <Package className="w-12 h-12 opacity-20" />
              <p className="text-sm">No component gems found yet — refresh the parts catalogue.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {componentGems.map((p) => (
                <ComponentCard key={`${p.category}::${p.name}`} part={p} />
              ))}
            </div>
          )
        )}
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

            {/* Pricing */}
            <div className="mt-auto border-t border-white/8 pt-2 space-y-0.5">
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
