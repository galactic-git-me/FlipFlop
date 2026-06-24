"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Zap, ExternalLink, ArrowLeft, Repeat2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ClassificationBadge } from "@/components/classification-badge";
import { FlippabilityScore } from "@/components/flippability-score";
import { SourceBadge } from "@/components/source-badge";
import { Listing } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function SuperGemsPage() {
  const router = useRouter();
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams({
      claude_verdict: "GEM",
      classification: "gem",
      sort_by: "gem_score",
      limit: "100",
    });
    fetch(`${API_BASE}/api/listings/?${params}`)
      .then((r) => r.json())
      .then((data) => {
        setListings(Array.isArray(data) ? data : data.items ?? []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-[#060d18] text-slate-100 px-4 py-6 md:px-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
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
        {!loading && (
          <span className="ml-auto text-sm text-slate-500">
            {listings.length} listing{listings.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-24 text-slate-500 text-sm">
          Loading…
        </div>
      ) : listings.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-3 text-slate-500">
          <Zap className="w-10 h-10 opacity-20" />
          <p className="text-sm">No super gems found yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {listings.map((l) => (
            <SuperGemCard key={l.id} listing={l} />
          ))}
        </div>
      )}
    </div>
  );
}

function SuperGemCard({ listing: l }: { listing: Listing }) {
  const router = useRouter();
  const [flipping, setFlipping] = useState(false);

  async function handleFlipIt() {
    setFlipping(true);
    try {
      const res = await fetch(`${API_BASE}/api/flips/`, {
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
      {/* Image */}
      <div className="w-full h-40 bg-[#080f1a] overflow-hidden relative">
        {l.image_urls?.[0] ? (
          <img
            src={l.image_urls[0]}
            alt={l.title}
            className="w-full h-full object-contain"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center opacity-15">
            <Zap className="w-8 h-8 text-cyan-300" />
          </div>
        )}
        {/* Super gem glow badge */}
        <div className="absolute top-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-cyan-400/20 border border-cyan-400/40 backdrop-blur-sm">
          <Zap className="w-2.5 h-2.5 text-cyan-300" />
          <span className="text-[9px] font-bold text-cyan-200 uppercase tracking-wider">Super Gem</span>
        </div>
      </div>

      <CardContent className="p-3 flex-1 flex flex-col gap-2">
        {/* Score + Classification */}
        <div className="flex items-start justify-between gap-2">
          <FlippabilityScore score={l.gem_score} size="sm" listing={l} />
          <ClassificationBadge classification={l.classification} />
        </div>

        {/* Title */}
        <h3 className="text-xs font-semibold text-slate-100 line-clamp-2 leading-snug">
          {l.title}
        </h3>

        {/* Specs */}
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

        {/* AI reasoning */}
        {l.claude_reasoning && (
          <p className="text-[9px] text-slate-500 italic line-clamp-2 border-t border-white/5 pt-1.5">
            {l.claude_reasoning}
          </p>
        )}

        {/* Pricing */}
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

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          {l.url && (
            <Button
              variant="outline"
              size="sm"
              className="h-7"
              onClick={() => window.open(l.url, "_blank")}
            >
              <ExternalLink className="w-3 h-3" />
            </Button>
          )}
          <Button
            variant="primary"
            size="sm"
            className="flex-1 h-7 bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
            onClick={handleFlipIt}
            disabled={flipping}
          >
            <Repeat2 className="w-3 h-3 mr-1" />
            {flipping ? "Starting…" : "Flip It"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
