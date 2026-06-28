"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Zap, ExternalLink, ArrowLeft, Repeat2, Package } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ClassificationBadge } from "@/components/classification-badge";
import { FlippabilityScore } from "@/components/flippability-score";
import { SourceBadge } from "@/components/source-badge";
import { Listing, GroupedPart } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

// ── Tab definitions ───────────────────────────────────────────────────────────

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
type GemTab = "flip_opportunities" | ComponentCategory;

// ── Page ─────────────────────────────────────────────────────────────────────

export default function SuperGemsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<GemTab>("flip_opportunities");

  // Listings data
  const [listings, setListings] = useState<Listing[]>([]);
  const [listingsLoading, setListingsLoading] = useState(true);

  // Parts data per category (loaded lazily on first visit to that tab)
  const [parts, setParts] = useState<Partial<Record<ComponentCategory, GroupedPart[]>>>({});
  const [partsLoading, setPartsLoading] = useState<Partial<Record<ComponentCategory, boolean>>>({});

  useEffect(() => {
    const params = new URLSearchParams({
      claude_verdict: "GEM",
      classification: "gem",
      sort_by: "gem_score",
      limit: "100",
      min_profit: "100",
    });
    fetch(`/api/listings/?${params}`)
      .then((r) => r.json())
      .then((data) => setListings(Array.isArray(data) ? data : data.items ?? []))
      .catch(() => setListings([]))
      .finally(() => setListingsLoading(false));
  }, []);

  const loadCategory = useCallback(async (cat: ComponentCategory) => {
    if (parts[cat] !== undefined) return; // already loaded
    setPartsLoading((p) => ({ ...p, [cat]: true }));
    try {
      const data = await fetch(`/api/parts/grouped?category=${cat}`).then((r) => r.json());
      const allParts: GroupedPart[] = Array.isArray(data) ? data : [];
      const gems = allParts
        .filter((p) => p.gem_classification !== null && p.claude_verdict !== "REJECT")
        .sort((a, b) => {
          // Super gems first, then by gem_score desc
          if (a.gem_classification === "super_gem" && b.gem_classification !== "super_gem") return -1;
          if (b.gem_classification === "super_gem" && a.gem_classification !== "super_gem") return 1;
          return (b.gem_score ?? 0) - (a.gem_score ?? 0);
        });
      setParts((p) => ({ ...p, [cat]: gems }));
    } catch {
      setParts((p) => ({ ...p, [cat]: [] }));
    } finally {
      setPartsLoading((p) => ({ ...p, [cat]: false }));
    }
  }, [parts]);

  useEffect(() => {
    if (activeTab !== "flip_opportunities") {
      void loadCategory(activeTab as ComponentCategory);
    }
  }, [activeTab, loadCategory]);

  // Count gems per component category (from already-loaded data)
  const partGemCount = (cat: ComponentCategory) => parts[cat]?.length ?? null;

  return (
    <div className="min-h-screen bg-[#060d18] text-slate-100 px-4 py-6 md:px-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back</span>
        </button>
        <div className="flex items-center gap-2 ml-2">
          <Zap className="w-5 h-5 text-cyan-300" />
          <h1 className="text-xl font-black text-cyan-100">Super Gems</h1>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 flex-wrap mb-5 border-b border-white/[0.06] pb-0">
        {/* Flip opportunities tab */}
        <button
          onClick={() => setActiveTab("flip_opportunities")}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold border-b-2 -mb-px transition-all ${
            activeTab === "flip_opportunities"
              ? "border-cyan-400 text-cyan-300"
              : "border-transparent text-slate-500 hover:text-slate-300"
          }`}
        >
          💎 Flip Opportunities
          {!listingsLoading && (
            <span className="ml-1 px-1.5 py-0.5 rounded-full bg-cyan-400/15 text-cyan-400 text-[10px] font-bold">
              {listings.length}
            </span>
          )}
        </button>

        {/* Component category tabs */}
        {COMPONENT_CATEGORIES.map((cat) => {
          const count = partGemCount(cat.id);
          return (
            <button
              key={cat.id}
              onClick={() => setActiveTab(cat.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold border-b-2 -mb-px transition-all ${
                activeTab === cat.id
                  ? "border-emerald-400 text-emerald-300"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              {cat.emoji} {cat.label}
              {count !== null && count > 0 && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full bg-emerald-400/15 text-emerald-400 text-[10px] font-bold">
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {activeTab === "flip_opportunities" && (
        <ListingGemsGrid listings={listings} loading={listingsLoading} />
      )}
      {activeTab !== "flip_opportunities" && (
        <ComponentGemsGrid
          parts={parts[activeTab as ComponentCategory]}
          loading={!!partsLoading[activeTab as ComponentCategory]}
          category={activeTab as ComponentCategory}
        />
      )}
    </div>
  );
}

// ── Listing gems grid ─────────────────────────────────────────────────────────

function ListingGemsGrid({ listings, loading }: { listings: Listing[]; loading: boolean }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-500 text-sm">Loading…</div>
    );
  }
  if (listings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3 text-slate-500">
        <Zap className="w-10 h-10 opacity-20" />
        <p className="text-sm">No super gems found yet.</p>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
      {listings.map((l) => (
        <SuperGemCard key={l.id} listing={l} />
      ))}
    </div>
  );
}

// ── Component gems grid ───────────────────────────────────────────────────────

function ComponentGemsGrid({
  parts, loading, category,
}: {
  parts: GroupedPart[] | undefined;
  loading: boolean;
  category: ComponentCategory;
}) {
  const catCfg = COMPONENT_CATEGORIES.find((c) => c.id === category);

  if (loading || parts === undefined) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-500 text-sm">Loading…</div>
    );
  }
  if (parts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3 text-slate-500">
        <Package className="w-10 h-10 opacity-20" />
        <p className="text-sm">No {catCfg?.label ?? category} gems found yet.</p>
        <p className="text-xs text-slate-600">Run a parts price refresh to populate the catalogue.</p>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
      {parts.map((p) => (
        <ComponentGemCard key={`${p.category}::${p.name}`} part={p} />
      ))}
    </div>
  );
}

// ── Listing super-gem card ────────────────────────────────────────────────────

function SuperGemCard({ listing: l }: { listing: Listing }) {
  const router = useRouter();
  const [flipping, setFlipping] = useState(false);

  async function handleFlipIt() {
    setFlipping(true);
    try {
      const res = await fetch(`/api/flips/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listing_id: l.id }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail ?? "Failed to create flip");
        return;
      }
      const flip = await res.json();
      router.push(`/flips/${flip.id}`);
    } finally {
      setFlipping(false);
    }
  }

  const profit =
    l.claude_expected_profit != null && l.claude_expected_profit > 0
      ? l.claude_expected_profit
      : (l.estimated_profit ?? 0);
  const profitColor =
    profit > 200 ? "text-cyan-300" : profit > 100 ? "text-[#00dc82]" : profit > 0 ? "text-amber-400" : "text-red-400";

  return (
    <Card className="overflow-hidden flex flex-col h-full border-cyan-400/30 bg-[#05111e] shadow-[0_4px_20px_rgba(34,211,238,0.1)]">
      <div className="w-full h-40 bg-[#080f1a] overflow-hidden relative">
        {l.image_urls?.[0] ? (
          <img src={l.image_urls[0]} alt={l.title} className="w-full h-full object-contain" loading="lazy" />
        ) : (
          <div className="w-full h-full flex items-center justify-center opacity-15">
            <Zap className="w-8 h-8 text-cyan-300" />
          </div>
        )}
        <div className={`absolute top-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md backdrop-blur-sm border ${l.claude_verdict === "GEM" ? "bg-cyan-400/20 border-cyan-400/40" : "bg-emerald-400/20 border-emerald-400/40"}`}>
          <Zap className={`w-2.5 h-2.5 ${l.claude_verdict === "GEM" ? "text-cyan-300" : "text-emerald-300"}`} />
          <span className={`text-[9px] font-bold uppercase tracking-wider ${l.claude_verdict === "GEM" ? "text-cyan-200" : "text-emerald-200"}`}>
            {l.claude_verdict === "GEM" ? "Super Gem" : "Gem"}
          </span>
        </div>
      </div>

      <CardContent className="p-3 flex-1 flex flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <FlippabilityScore score={l.gem_score} size="sm" listing={l} />
          <ClassificationBadge classification={l.classification} />
        </div>
        <h3 className="text-xs font-semibold text-slate-100 line-clamp-2 leading-snug">{l.title}</h3>
        <div className="space-y-1 text-[10px] text-slate-500">
          {l.cpu && <div>🖥️ <span className="font-mono text-slate-400">{l.cpu.slice(0, 22)}</span></div>}
          <div className="flex gap-2 flex-wrap">
            {l.ram_gb && <span>🔹 {l.ram_gb}GB RAM</span>}
            {l.gpu ? (
              <span className="text-emerald-400">✓ {l.gpu.slice(0, 15)}</span>
            ) : (
              <span className="text-red-400/70">✗ No GPU</span>
            )}
          </div>
          {l.source_name && <div className="text-slate-600">📍 {l.source_name}</div>}
        </div>
        {l.claude_reasoning && (
          <p className="text-[9px] text-slate-500 italic line-clamp-2 border-t border-white/5 pt-1.5">
            {l.claude_reasoning}
          </p>
        )}
        <div className="mt-auto pt-2 border-t border-white/5 space-y-1">
          <div className="flex items-baseline justify-between">
            <span className="text-[9px] text-slate-600">Buy</span>
            <span className="text-sm font-semibold text-slate-300">{formatCurrency(l.price)}</span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-[9px] text-slate-600">Resale</span>
            <span className="text-sm font-semibold text-slate-200">{formatCurrency(l.estimated_resale ?? 0)}</span>
          </div>
          <div className={`flex items-baseline justify-between pt-1 border-t border-white/5 text-base font-black ${profitColor}`}>
            <span className="text-[9px]">Profit</span>
            <span>{profit > 0 ? "+" : ""}{formatCurrency(profit)}</span>
          </div>
        </div>
        <div className="flex gap-2 pt-2">
          {l.url && (
            <Button variant="outline" size="sm" className="h-7" onClick={() => window.open(l.url, "_blank")}>
              <ExternalLink className="w-3 h-3" />
            </Button>
          )}
          <Button
            variant="primary" size="sm"
            className="flex-1 h-7 bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
            onClick={handleFlipIt} disabled={flipping}
          >
            <Repeat2 className="w-3 h-3 mr-1" />
            {flipping ? "Starting…" : "Flip It"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Component gem card ────────────────────────────────────────────────────────

function ComponentGemCard({ part: p }: { part: GroupedPart }) {
  const isSuperGem = p.gem_classification === "super_gem";
  const aiVerified = p.claude_verdict === "GEM" || p.claude_verdict === "GOOD";
  const bestPrice = p.cheapest_good_price ?? p.cheapest_price ?? 0;
  const sourceUrl = p.cheapest_good_url ?? p.cheapest_url ?? undefined;
  const sourceName = p.cheapest_good_source ?? p.cheapest_source ?? null;

  return (
    <Card className={`overflow-hidden flex flex-col h-full ${
      isSuperGem
        ? "border-cyan-400/30 bg-[#05111e] shadow-[0_4px_20px_rgba(34,211,238,0.1)]"
        : "border-emerald-400/25 bg-[#041510] shadow-[0_4px_20px_rgba(52,211,153,0.08)]"
    }`}>
      <div className="w-full h-36 bg-[#080f1a] overflow-hidden relative flex items-center justify-center">
        {p.image_url ? (
          <img src={p.image_url} alt={p.name} className="w-full h-full object-contain opacity-85" loading="lazy" />
        ) : (
          <Package className="w-10 h-10 text-slate-700" />
        )}
        {/* Gem badge */}
        <div className={`absolute top-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md backdrop-blur-sm border text-[9px] font-bold uppercase tracking-wider ${
          isSuperGem ? "bg-cyan-400/20 border-cyan-400/40 text-cyan-200" : "bg-emerald-400/20 border-emerald-400/40 text-emerald-200"
        }`}>
          <Zap className={`w-2.5 h-2.5 ${isSuperGem ? "text-cyan-300" : "text-emerald-300"}`} />
          {isSuperGem ? "Super Gem" : "Gem"}
        </div>
        {/* Discount badge */}
        {p.gem_score != null && (
          <div className={`absolute top-2 right-2 px-1.5 py-0.5 rounded text-[9px] font-black ${
            isSuperGem ? "bg-cyan-400/15 text-cyan-300" : "bg-emerald-400/15 text-emerald-300"
          }`}>
            -{p.gem_score.toFixed(0)}% vs median
          </div>
        )}
        {/* AI status */}
        {aiVerified && (
          <div className="absolute bottom-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-violet-500/20 border border-violet-400/40 text-[8px] text-violet-300 uppercase tracking-wide">
            ✓ AI verified
          </div>
        )}
        {!p.claude_verdict && (
          <div className="absolute bottom-2 left-2 flex items-center gap-0.5 px-1.5 py-0.5 rounded-md bg-slate-700/60 border border-slate-500/30 text-[8px] text-slate-400 uppercase tracking-wide">
            ⏳ Pending AI
          </div>
        )}
      </div>

      <CardContent className="p-3 flex-1 flex flex-col gap-2">
        <div>
          <p className="text-xs font-semibold text-slate-100 line-clamp-2 leading-snug">{p.name}</p>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider mt-0.5">{p.category}</p>
        </div>

        {p.claude_reasoning && (
          <p className="text-[9px] text-slate-500 italic line-clamp-2 border-t border-white/5 pt-1.5">
            {p.claude_reasoning}
          </p>
        )}

        <div className="mt-auto pt-2 border-t border-white/5 space-y-1">
          <div className="flex items-baseline justify-between">
            <span className="text-[9px] text-slate-600">{p.cheapest_good_price ? "Best (trusted)" : "Best price"}</span>
            <span className={`text-sm font-black ${isSuperGem ? "text-cyan-300" : "text-emerald-300"}`}>
              {formatCurrency(bestPrice)}
            </span>
          </div>
          {p.price_used != null && p.price_used !== bestPrice && (
            <div className="flex items-baseline justify-between">
              <span className="text-[9px] text-slate-600">Typical used</span>
              <span className="text-xs text-slate-400">{formatCurrency(p.price_used)}</span>
            </div>
          )}
        </div>

        <div className="flex gap-2 pt-1">
          {sourceName && <SourceBadge sourceName={sourceName} url={sourceUrl} />}
          {sourceUrl && (
            <Button
              variant="outline" size="sm"
              className="ml-auto h-7"
              onClick={() => window.open(sourceUrl, "_blank")}
            >
              <ExternalLink className="w-3 h-3" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
