"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { X, Zap, ExternalLink, TrendingUp, Cpu, HardDrive, MemoryStick, RefreshCw } from "lucide-react";
import { Listing } from "@/lib/types";
import { api, API_BASE_URL } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

// ── Fetch super gems ──────────────────────────────────────────────────────────
async function fetchSuperGems(): Promise<Listing[]> {
  const params = new URLSearchParams({
    classification: "amazing_gem",
    sort_by: "gem_score",
    page: "1",
    page_size: "60",
  });
  const res = await fetch(`${API_BASE_URL}/listings/?${params}`);
  const data = await res.json();
  return Array.isArray(data) ? data : (data.items ?? []);
}

// ── Modal shell ───────────────────────────────────────────────────────────────
export function SuperGemsModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [mounted, setMounted] = useState(false);
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setListings(await fetchSuperGems());
    } catch {
      setListings([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

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
          <h2 className="text-lg font-black text-cyan-100 tracking-wide">Super Gems</h2>
          {!loading && listings.length > 0 && (
            <span className="text-xs text-slate-500 ml-1">{listings.length} found</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => void load()}
            disabled={loading}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Scrollable gallery */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {loading ? (
          <div className="flex items-center justify-center h-64 text-slate-500 text-sm gap-2">
            <RefreshCw className="w-4 h-4 animate-spin" />
            Loading super gems…
          </div>
        ) : listings.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-slate-600">
            <Zap className="w-12 h-12 opacity-20" />
            <p className="text-sm">No super gems found yet — run a scan first.</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {listings.map((l) => (
              <FlipCard key={l.id} listing={l} />
            ))}
          </div>
        )}
      </div>
    </div>,
    document.body
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
          <div className="absolute top-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-cyan-400/20 border border-cyan-400/40 backdrop-blur-sm">
            <Zap className="w-2.5 h-2.5 text-cyan-300" />
            <span className="text-[9px] font-bold text-cyan-200 uppercase tracking-wider">Super Gem</span>
          </div>

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
