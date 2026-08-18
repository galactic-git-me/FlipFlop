"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowDown, Check, ExternalLink, Loader2, RefreshCw, ShieldCheck, TrendingUp } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

type ComponentValuation = {
  slot: string; name: string; price_paid: number; estimated_resale: number;
  estimate_basis: string; confidence: "low" | "medium" | "high"; evidence_count: number;
};
type Comparable = {
  source: string; title: string; price: number; status: "sold" | "active";
  observed_or_sold_at: string | null; url: string | null; match_basis: string;
};
type Recommendation = {
  market_low: number; market_mid: number; market_high: number;
  recommended_price: number; floor_price: number; auto_accept_at: number;
  counter_offer_from: number; auto_reject_below: number; fee_rate_pct: number;
  confidence: "low" | "medium" | "high"; rationale: string;
  automation: { day: number; action: string; price: number; rationale: string }[];
};
type PricingData = {
  cost_price: number; delivery_cost: number; component_resale_total: number;
  component_valuations: ComponentValuation[]; market_comparables: Comparable[];
  recommendation: Recommendation; fetched_at: string;
};

function Confidence({ value }: { value: string }) {
  const tone = value === "high" ? "text-emerald-300 bg-emerald-400/10 border-emerald-400/20" : value === "medium" ? "text-amber-300 bg-amber-400/10 border-amber-400/20" : "text-slate-400 bg-white/[0.03] border-white/[0.08]";
  return <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${tone}`}>{value}</span>;
}

export function PricingIntelligence({ buildId, onUsePrice }: { buildId: number; onUsePrice: (price: number) => void }) {
  const [data, setData] = useState<PricingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (fresh: boolean) => {
    setLoading(true); setError(null);
    try {
      const response = await fetch(`/api/builds/${buildId}/pricing?fetch_sold=${fresh}`);
      if (!response.ok) throw new Error(fresh ? "Could not refresh sold-market evidence" : "Could not load pricing analysis");
      setData(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load pricing analysis");
    } finally { setLoading(false); }
  }, [buildId]);

  useEffect(() => { void load(false); }, [load]);

  if (loading && !data) return <div className="flex min-h-64 items-center justify-center text-sm text-slate-400"><Loader2 className="mr-2 h-4 w-4 animate-spin" />Calculating pricing evidence…</div>;
  if (error && !data) return <div className="rounded-xl border border-red-400/20 bg-red-400/5 p-4 text-sm text-red-300">{error}</div>;
  if (!data) return null;
  const r = data.recommendation;
  const sold = data.market_comparables.filter((item) => item.status === "sold");
  const active = data.market_comparables.filter((item) => item.status === "active");

  return <div className="space-y-5">
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {[
        ["Actual build cost", data.cost_price, "What you paid"],
        ["Parts resale context", data.component_resale_total, "Standalone estimates; not the PC price"],
        ["Recommended list price", r.recommended_price, `${r.confidence} confidence`],
        ["Protected offer floor", r.floor_price, `After ${r.fee_rate_pct}% configured fees`],
      ].map(([label, value, detail]) => <div key={String(label)} className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
        <p className="text-[11px] font-mono uppercase tracking-wider text-slate-500">{label}</p>
        <p className="mt-2 text-2xl font-black text-slate-100">{formatCurrency(Number(value))}</p>
        <p className="mt-1 text-xs text-slate-500">{detail}</p>
      </div>)}
    </section>

    <section className="rounded-xl border border-cyan-400/15 bg-cyan-400/[0.035] p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2"><TrendingUp className="h-4 w-4 text-cyan-400" /><h2 className="font-semibold">Market recommendation</h2><Confidence value={r.confidence} /></div>
          <p className="mt-2 text-sm text-slate-300">Range {formatCurrency(r.market_low)}–{formatCurrency(r.market_high)} · midpoint {formatCurrency(r.market_mid)}</p>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{r.rationale}. The recommended price includes negotiating room; the floor protects a 10% margin after configured marketplace fees.</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button onClick={() => void load(true)} disabled={loading} className="flex cursor-pointer items-center gap-2 rounded-lg border border-white/[0.1] px-3 py-2 text-xs font-semibold text-slate-300 transition-colors hover:bg-white/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:opacity-50"><RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />Refresh sold evidence</button>
          <button onClick={() => onUsePrice(r.recommended_price)} className="flex cursor-pointer items-center gap-2 rounded-lg bg-cyan-400 px-3 py-2 text-xs font-bold text-slate-950 transition-colors hover:bg-cyan-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200"><Check className="h-3.5 w-3.5" />Use {formatCurrency(r.recommended_price)}</button>
        </div>
      </div>
      {error && <p className="mt-3 text-xs text-amber-300"><AlertTriangle className="mr-1 inline h-3.5 w-3.5" />{error}; showing the previous analysis.</p>}
    </section>

    <section className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
      <div className="mb-3 flex items-end justify-between"><div><h2 className="font-semibold">Component valuation</h2><p className="mt-1 text-xs text-slate-500">Useful resale context, but never added together as proof of a complete-PC selling price.</p></div><span className="text-sm font-semibold text-slate-300">Paid {formatCurrency(data.cost_price)}</span></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-white/[0.07] text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="px-2 py-2">Component</th><th className="px-2 py-2 text-right">Paid</th><th className="px-2 py-2 text-right">Est. resale</th><th className="px-2 py-2 text-right">Difference</th><th className="px-2 py-2">Evidence</th></tr></thead>
        <tbody>{data.component_valuations.map((item) => <tr key={item.slot} className="border-b border-white/[0.045] last:border-0">
          <td className="px-2 py-3"><p className="font-medium text-slate-200">{item.name}</p><p className="text-[10px] font-mono uppercase text-slate-600">{item.slot.replaceAll("_", " ")}</p></td>
          <td className="px-2 py-3 text-right text-slate-400">{formatCurrency(item.price_paid)}</td><td className="px-2 py-3 text-right font-semibold text-cyan-300">{formatCurrency(item.estimated_resale)}</td>
          <td className={`px-2 py-3 text-right ${item.estimated_resale >= item.price_paid ? "text-emerald-300" : "text-slate-500"}`}>{item.estimated_resale >= item.price_paid ? "+" : ""}{formatCurrency(item.estimated_resale - item.price_paid)}</td>
          <td className="px-2 py-3"><div className="flex items-center gap-2"><Confidence value={item.confidence} /><span className="max-w-xs text-xs text-slate-500">{item.estimate_basis}</span></div></td>
        </tr>)}</tbody>
        <tfoot className="border-t border-white/[0.1] font-semibold"><tr><td className="px-2 py-3">Totals</td><td className="px-2 py-3 text-right">{formatCurrency(data.cost_price)}</td><td className="px-2 py-3 text-right text-cyan-300">{formatCurrency(data.component_resale_total)}</td><td colSpan={2} /></tr></tfoot>
      </table></div>
    </section>

    <section className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
      <div className="flex items-center justify-between"><div><h2 className="font-semibold">Same and similar builds</h2><p className="mt-1 text-xs text-slate-500">Completed eBay prices take priority; retailer prices are asking-price context only.</p></div><span className="text-xs text-slate-500">{sold.length} sold · {active.length} active</span></div>
      {data.market_comparables.length === 0 ? <div className="mt-4 rounded-lg border border-dashed border-white/[0.1] p-5 text-center text-sm text-slate-500">No cached comparable builds yet. Use “Refresh sold evidence” to search eBay; Overclockers will appear here when a matching prebuilt is in the live catalogue.</div> :
      <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="border-b border-white/[0.07] text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="px-2 py-2">Source / build</th><th className="px-2 py-2">Evidence date</th><th className="px-2 py-2">Type</th><th className="px-2 py-2 text-right">Price</th><th className="px-2 py-2" /></tr></thead><tbody>{data.market_comparables.map((item, index) => <tr key={`${item.url}-${index}`} className="border-b border-white/[0.045]"><td className="px-2 py-3"><p className="max-w-xl truncate text-slate-200">{item.title}</p><p className="text-xs text-slate-500">{item.source} · {item.match_basis}</p></td><td className="px-2 py-3 text-slate-400">{item.observed_or_sold_at ? new Date(item.observed_or_sold_at).toLocaleDateString("en-GB") : "—"}</td><td className="px-2 py-3"><span className={`rounded px-2 py-1 text-[10px] font-semibold uppercase ${item.status === "sold" ? "bg-emerald-400/10 text-emerald-300" : "bg-amber-400/10 text-amber-300"}`}>{item.status}</span></td><td className="px-2 py-3 text-right font-semibold">{formatCurrency(item.price)}</td><td className="px-2 py-3 text-right">{item.url && <a href={item.url} target="_blank" rel="noreferrer" aria-label={`Open ${item.title}`} className="inline-flex cursor-pointer rounded p-1 text-slate-500 transition-colors hover:text-cyan-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"><ExternalLink className="h-4 w-4" /></a>}</td></tr>)}</tbody></table></div>}
    </section>

    <section className="grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
      <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4"><div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-300" /><h2 className="font-semibold">Offer guardrails</h2></div><div className="mt-4 space-y-3 text-sm">{[["Auto-accept at or above", r.auto_accept_at, "text-emerald-300"],["Always counter from", r.counter_offer_from, "text-cyan-300"],["Auto-reject below", r.auto_reject_below, "text-red-300"],["Never reduce below", r.floor_price, "text-amber-300"]].map(([label,value,tone]) => <div key={String(label)} className="flex items-center justify-between border-b border-white/[0.05] pb-3 last:border-0"><span className="text-slate-400">{label}</span><strong className={String(tone)}>{formatCurrency(Number(value))}</strong></div>)}</div></div>
      <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4"><h2 className="font-semibold">Suggested price automation</h2><div className="mt-4 space-y-0">{r.automation.map((step, index) => <div key={step.day} className="grid grid-cols-[52px_18px_1fr_auto] gap-2"><span className="pt-0.5 text-xs font-mono text-slate-500">Day {step.day}</span><div className="flex flex-col items-center"><span className="mt-1 h-2 w-2 rounded-full bg-cyan-400" />{index < r.automation.length - 1 && <span className="min-h-12 w-px flex-1 bg-white/[0.08]" />}</div><div className="pb-4"><p className="text-sm text-slate-200">{step.action}</p><p className="mt-1 text-xs text-slate-600">{step.rationale}</p></div><strong className="text-sm text-slate-300">{formatCurrency(step.price)}</strong></div>)}</div></div>
    </section>
  </div>;
}
