"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Repeat2, Zap, ArrowRight, CheckCircle2, Wrench, Tag, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

type FlipStage = "selected" | "building" | "ready_for_sale" | "sold";

interface Flip {
  id: number;
  listing_id: number;
  listing?: {
    title: string;
    price: number;
    image_urls: string[];
    cpu?: string;
    gpu?: string;
    ram_gb?: number;
  };
  stage: FlipStage;
  base_cost: number;
  upgrade_cost: number;
  total_cost: number;
  current_estimated_resale?: number;
  current_estimated_profit?: number;
  created_at: string;
}

const STAGE_CONFIG: Record<FlipStage, { label: string; icon: React.ReactNode; color: string }> = {
  selected:      { label: "Selected",       icon: <Zap className="w-3.5 h-3.5" />,          color: "text-cyan-400 border-cyan-400/30 bg-cyan-400/5" },
  building:      { label: "Building",       icon: <Wrench className="w-3.5 h-3.5" />,        color: "text-amber-400 border-amber-400/30 bg-amber-400/5" },
  ready_for_sale:{ label: "Ready for Sale", icon: <Tag className="w-3.5 h-3.5" />,           color: "text-[#00dc82] border-[#00dc82]/30 bg-[#00dc82]/5" },
  sold:          { label: "Sold",           icon: <CheckCircle2 className="w-3.5 h-3.5" />,  color: "text-slate-400 border-slate-400/30 bg-slate-400/5" },
};

const ACTIVE_STAGES: FlipStage[] = ["selected", "building", "ready_for_sale"];

export default function FlipsPage() {
  const router = useRouter();
  const [flips, setFlips] = useState<Flip[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"active" | "sold">("active");

  useEffect(() => {
    api.flips
      .list()
      .then((raw) => setFlips(raw as Flip[]))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const shown = flips.filter((f) =>
    filter === "active" ? ACTIVE_STAGES.includes(f.stage) : f.stage === "sold"
  );

  const activeCount = flips.filter((f) => ACTIVE_STAGES.includes(f.stage)).length;
  const totalPotentialProfit = flips
    .filter((f) => ACTIVE_STAGES.includes(f.stage))
    .reduce((s, f) => s + (f.current_estimated_profit ?? 0), 0);

  return (
    <div className="min-h-screen bg-[#060d18] text-slate-100 px-4 py-6 md:px-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Repeat2 className="w-5 h-5 text-[#00dc82]" />
          <h1 className="text-xl font-black">Your Flips</h1>
        </div>
        <button
          onClick={() => router.push("/super-gems")}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 text-black rounded-lg transition-colors"
        >
          <Zap className="w-3.5 h-3.5" />
          Find a Flip
        </button>
      </div>

      {/* Summary row */}
      {activeCount > 0 && (
        <div className="flex gap-4 mb-6">
          <div className="flex-1 rounded-xl p-4 border border-white/[0.07] bg-white/[0.02]">
            <p className="text-xs text-slate-500 mb-1">Active flips</p>
            <p className="text-2xl font-black">{activeCount}</p>
          </div>
          <div className="flex-1 rounded-xl p-4 border border-white/[0.07] bg-white/[0.02]">
            <p className="text-xs text-slate-500 mb-1">Potential profit</p>
            <p className="text-2xl font-black text-[#00dc82]">
              {totalPotentialProfit > 0 ? `+${formatCurrency(totalPotentialProfit)}` : "—"}
            </p>
          </div>
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 border-b border-white/[0.07]">
        {(["active", "sold"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setFilter(tab)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
              filter === tab
                ? "border-[#00dc82] text-[#00dc82]"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            {tab === "active" ? "Active" : "Sold"}
            {tab === "active" && activeCount > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 text-[10px] rounded-full bg-[#00dc82]/20 text-[#00dc82]">
                {activeCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Flip list */}
      {loading ? (
        <div className="flex items-center justify-center py-24 text-slate-500 text-sm">Loading…</div>
      ) : shown.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-slate-500">
          <Repeat2 className="w-10 h-10 opacity-20" />
          {filter === "active" ? (
            <>
              <p className="text-sm">No active flips yet.</p>
              <button
                onClick={() => router.push("/super-gems")}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 text-black rounded-lg transition-colors"
              >
                <Zap className="w-3.5 h-3.5" /> Find a Super Gem to Flip
              </button>
            </>
          ) : (
            <p className="text-sm">No sold flips yet.</p>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {shown.map((f) => (
            <FlipCard key={f.id} flip={f} onClick={() => router.push(`/flips/${f.id}`)} />
          ))}
        </div>
      )}
    </div>
  );
}

function FlipCard({ flip: f, onClick }: { flip: Flip; onClick: () => void }) {
  const stage = STAGE_CONFIG[f.stage];
  const profit = f.current_estimated_profit ?? 0;
  const profitColor = profit > 150 ? "text-[#00dc82]" : profit > 50 ? "text-amber-400" : "text-red-400";
  const img = f.listing?.image_urls?.[0];

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-4 p-4 rounded-xl border border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/[0.14] transition-all text-left"
    >
      {/* Thumbnail */}
      <div className="w-16 h-12 rounded-lg bg-slate-800 overflow-hidden shrink-0">
        {img ? (
          <img src={img} alt="" className="w-full h-full object-contain" />
        ) : (
          <div className="w-full h-full flex items-center justify-center opacity-20">
            <Repeat2 className="w-5 h-5" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-100 truncate">
          {f.listing?.title ?? `Flip #${f.id}`}
        </p>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          {f.listing?.cpu && (
            <span className="text-[10px] text-slate-500 font-mono">{f.listing.cpu.slice(0, 20)}</span>
          )}
          {f.listing?.gpu ? (
            <span className="text-[10px] text-emerald-500">✓ GPU</span>
          ) : (
            <span className="text-[10px] text-red-400/70">✗ No GPU</span>
          )}
        </div>
      </div>

      {/* Stage badge */}
      <div className={`flex items-center gap-1 px-2 py-1 rounded-lg border text-[10px] font-bold uppercase tracking-wider shrink-0 ${stage.color}`}>
        {stage.icon}
        {stage.label}
      </div>

      {/* Financials */}
      <div className="text-right shrink-0 hidden sm:block">
        <p className="text-xs text-slate-500">Cost in</p>
        <p className="text-sm font-semibold">{formatCurrency(f.total_cost)}</p>
        {profit !== 0 && (
          <p className={`text-sm font-black ${profitColor}`}>
            {profit > 0 ? "+" : ""}{formatCurrency(profit)}
          </p>
        )}
      </div>

      <ArrowRight className="w-4 h-4 text-slate-600 shrink-0" />
    </button>
  );
}
