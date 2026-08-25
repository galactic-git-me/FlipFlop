"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  ExternalLink,
  Loader2,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";

type ComponentValuation = {
  slot: string;
  name: string;
  price_paid: number;
  estimated_resale: number;
  estimate_basis: string;
  confidence: "low" | "medium" | "high";
  evidence_count: number;
};
type Comparable = {
  source: string;
  title: string;
  price: number;
  status: "sold" | "active";
  observed_or_sold_at: string | null;
  url: string | null;
  match_basis: string;
  date_kind: "sold" | "observed" | "unknown";
};
type Recommendation = {
  market_low: number;
  market_mid: number;
  market_high: number;
  recommended_price: number;
  floor_price: number;
  auto_accept_at: number;
  counter_offer_from: number;
  auto_reject_below: number;
  fee_rate_pct: number;
  confidence: "low" | "medium" | "high";
  rationale: string;
  automation: {
    day: number;
    action: string;
    price: number;
    rationale: string;
  }[];
};
type PricingData = {
  cost_price: number;
  delivery_cost: number;
  component_resale_total: number;
  component_valuations: ComponentValuation[];
  market_comparables: Comparable[];
  recommendation: Recommendation;
  price_bridge: {
    expected_sold_price: number;
    build_cost: number;
    delivery_cost: number;
    insurance_cost: number;
    packaging_cost: number;
    warranty_reserve_pct: number;
    warranty_reserve: number;
    marketplace_fee_allowance: number;
    negotiation_headroom_pct: number;
    negotiation_headroom: number;
    recommended_listing_price: number;
  };
  fetched_at: string;
};

function Confidence({ value }: { value: string }) {
  const tone =
    value === "high"
      ? "text-emerald-300 bg-emerald-400/10 border-emerald-400/20"
      : value === "medium"
      ? "text-amber-300 bg-amber-400/10 border-amber-400/20"
      : "text-slate-400 bg-white/[0.03] border-white/[0.08]";
  return (
    <span
      className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${tone}`}
    >
      {value}
    </span>
  );
}

function cohortStats(items: Comparable[]) {
  const prices = items.map((item) => item.price).sort((a, b) => a - b);
  if (!prices.length) return null;
  const percentile = (fraction: number) => {
    const index = (prices.length - 1) * fraction;
    const lower = Math.floor(index);
    const upper = Math.min(lower + 1, prices.length - 1);
    const weight = index - lower;
    return prices[lower] * (1 - weight) + prices[upper] * weight;
  };
  return {
    low: percentile(0.25),
    mid: percentile(0.5),
    high: percentile(0.75),
  };
}

function PriceSummary({ items }: { items: Comparable[] }) {
  const stats = cohortStats(items);
  if (!stats)
    return (
      <div className="rounded-lg border border-dashed border-white/10 p-4 text-center text-xs text-slate-500">
        No evidence in this cohort.
      </div>
    );
  return (
    <div className="grid grid-cols-3 gap-2 rounded-lg border border-white/[0.07] bg-white/[0.025] p-3 text-center">
      <div>
        <p className="text-[10px] uppercase text-slate-500">Low</p>
        <p className="mt-1 text-lg font-bold">{formatCurrency(stats.low)}</p>
      </div>
      <div>
        <p className="text-[10px] uppercase text-slate-500">Midpoint</p>
        <p className="mt-1 text-lg font-bold text-cyan-300">
          {formatCurrency(stats.mid)}
        </p>
      </div>
      <div>
        <p className="text-[10px] uppercase text-slate-500">High</p>
        <p className="mt-1 text-lg font-bold">{formatCurrency(stats.high)}</p>
      </div>
    </div>
  );
}

function SoldPriceChart({ items }: { items: Comparable[] }) {
  const points = items
    .filter((item) => item.date_kind === "sold" && item.observed_or_sold_at)
    .sort(
      (a, b) =>
        new Date(a.observed_or_sold_at!).getTime() -
        new Date(b.observed_or_sold_at!).getTime()
    );
  if (points.length < 2)
    return (
      <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-white/10 px-5 text-center text-xs leading-5 text-slate-500">
        A sold-price trend will appear once at least two genuine eBay sold dates
        are captured. Retrieval dates are deliberately excluded.
      </div>
    );
  const width = 600,
    height = 150,
    pad = 22;
  const min = Math.min(...points.map((item) => item.price));
  const max = Math.max(...points.map((item) => item.price));
  const span = Math.max(max - min, 1);
  const coordinates = points.map((item, index) => ({
    x: pad + index * ((width - pad * 2) / Math.max(points.length - 1, 1)),
    y: height - pad - ((item.price - min) / span) * (height - pad * 2),
    item,
  }));
  return (
    <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-2">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-36 w-full"
        role="img"
        aria-label="Sold price over time"
      >
        <path
          d={`M ${coordinates
            .map((point) => `${point.x} ${point.y}`)
            .join(" L ")}`}
          fill="none"
          stroke="#22d3ee"
          strokeWidth="3"
        />
        {coordinates.map((point, index) => (
          <circle key={index} cx={point.x} cy={point.y} r="4" fill="#67e8f9">
            <title>{`${new Date(
              point.item.observed_or_sold_at!
            ).toLocaleDateString("en-GB")}: ${formatCurrency(
              point.item.price
            )}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

function EvidenceTable({
  items,
  sold,
}: {
  items: Comparable[];
  sold: boolean;
}) {
  const ordered = [...items].sort((a, b) => {
    const aTime = a.observed_or_sold_at
      ? new Date(a.observed_or_sold_at).getTime()
      : 0;
    const bTime = b.observed_or_sold_at
      ? new Date(b.observed_or_sold_at).getTime()
      : 0;
    return bTime - aTime;
  });
  return (
    <div className="max-h-[36vh] overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 border-b border-white/10 bg-slate-950 text-left text-[10px] uppercase text-slate-500">
          <tr>
            <th className="py-2 pr-3">Source / listing</th>
            <th className="py-2 pr-3">{sold ? "Sold date" : "Observed"}</th>
            <th className="py-2 text-right">Price</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((item, index) => (
            <tr
              key={`${item.url}-${index}`}
              className="border-b border-white/[0.06]"
            >
              <td className="py-3 pr-3 text-slate-200">
                <span className="block max-w-sm truncate">{item.title}</span>
                <span className="block text-xs text-slate-500">
                  {item.source} · {item.match_basis}
                </span>
              </td>
              <td className="whitespace-nowrap py-3 pr-3 text-xs text-slate-400">
                {sold && item.date_kind !== "sold"
                  ? "Unavailable"
                  : item.observed_or_sold_at
                  ? new Date(item.observed_or_sold_at).toLocaleDateString(
                      "en-GB"
                    )
                  : "—"}
              </td>
              <td className="whitespace-nowrap py-3 text-right font-semibold">
                {formatCurrency(item.price)}
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="ml-2 inline-block text-slate-500 hover:text-cyan-300"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MarketEvidence({
  sold,
  active,
}: {
  sold: Comparable[];
  active: Comparable[];
}) {
  return (
    <div className="mt-5 grid gap-5 lg:grid-cols-2 lg:divide-x lg:divide-white/10">
      <section className="space-y-4 lg:pr-5">
        <div>
          <h3 className="font-semibold text-emerald-300">Sold prices</h3>
          <p className="mt-1 text-xs text-slate-500">
            Completed sales, newest genuine sold date first.
          </p>
        </div>
        <PriceSummary items={sold} />
        <SoldPriceChart items={sold} />
        <EvidenceTable items={sold} sold />
      </section>
      <section className="space-y-4 lg:pl-5">
        <div>
          <h3 className="font-semibold text-amber-300">Buy It Now prices</h3>
          <p className="mt-1 text-xs text-slate-500">
            Current matched asking prices from eBay and other vendors.
          </p>
        </div>
        <PriceSummary items={active} />
        <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-white/10 px-5 text-center text-xs leading-5 text-slate-500">
          Build-level BIN price history is not retained yet, so no historical
          chart is shown.
        </div>
        <EvidenceTable items={active} sold={false} />
      </section>
    </div>
  );
}

export function PricingIntelligence({
  buildId,
  onUsePrice,
}: {
  buildId: number;
  onUsePrice: (price: number) => void;
}) {
  const [data, setData] = useState<PricingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detailModal, setDetailModal] = useState<
    "cost" | "resale" | "market" | null
  >(null);

  const load = useCallback(
    async (fresh: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `/api/builds/${buildId}/pricing?fetch_sold=${fresh}`
        );
        if (!response.ok)
          throw new Error(
            fresh
              ? "Could not refresh sold-market evidence"
              : "Could not load pricing analysis"
          );
        setData(await response.json());
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Could not load pricing analysis"
        );
      } finally {
        setLoading(false);
      }
    },
    [buildId]
  );

  useEffect(() => {
    void load(false);
  }, [load]);

  if (loading && !data)
    return (
      <div className="flex min-h-64 items-center justify-center text-sm text-slate-400">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Calculating pricing evidence…
      </div>
    );
  if (error && !data)
    return (
      <div className="rounded-xl border border-red-400/20 bg-red-400/5 p-4 text-sm text-red-300">
        {error}
      </div>
    );
  if (!data) return null;
  const r = data.recommendation;
  const sold = data.market_comparables.filter((item) => item.status === "sold");
  const active = data.market_comparables.filter(
    (item) => item.status === "active"
  );
  const hasMarketEvidence = data.market_comparables.length > 0;

  return (
    <div className="space-y-5">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Actual build cost", data.cost_price, "What you paid"],
          [
            "Parts market value",
            data.component_resale_total,
            "Current component values; no depreciation",
          ],
          [
            hasMarketEvidence
              ? "Recommended list price"
              : "Provisional list price",
            r.recommended_price,
            hasMarketEvidence
              ? `${r.confidence} confidence`
              : "Cost and margin fallback; no market comps",
          ],
          [
            "Protected offer floor",
            r.floor_price,
            `After ${r.fee_rate_pct}% configured fees`,
          ],
        ].map(([label, value, detail]) => (
          <button
            type="button"
            onClick={() =>
              setDetailModal(
                label === "Actual build cost"
                  ? "cost"
                  : label === "Parts market value"
                  ? "resale"
                  : label === "Recommended list price" ||
                    label === "Provisional list price"
                  ? "market"
                  : null
              )
            }
            key={String(label)}
            className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-4 text-left transition-colors hover:border-cyan-400/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          >
            <p className="text-[11px] font-mono uppercase tracking-wider text-slate-500">
              {label}
            </p>
            <p className="mt-2 text-2xl font-black text-slate-100">
              {formatCurrency(Number(value))}
            </p>
            <p className="mt-1 text-xs text-slate-500">{detail}</p>
          </button>
        ))}
      </section>

      <section className="rounded-xl border border-cyan-400/15 bg-cyan-400/[0.035] p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-cyan-400" />
              <h2 className="font-semibold">
                {hasMarketEvidence
                  ? "Market recommendation"
                  : "Provisional pricing"}
              </h2>
              {hasMarketEvidence && <Confidence value={r.confidence} />}
            </div>
            {hasMarketEvidence ? (
              <button
                type="button"
                onClick={() => setDetailModal("market")}
                className="mt-2 cursor-pointer text-left text-sm text-slate-300 hover:text-cyan-300"
              >
                Range {formatCurrency(r.market_low)}–
                {formatCurrency(r.market_high)} · midpoint{" "}
                {formatCurrency(r.market_mid)} · view evidence
              </button>
            ) : (
              <p className="mt-2 text-sm font-semibold text-amber-300">
                No sourced market range is available.
              </p>
            )}
            <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">
              {hasMarketEvidence
                ? r.rationale
                : "The displayed provisional price is derived from component values and the fee-aware margin floor, not comparable PC sales"}
              . The floor protects a 10% margin after configured marketplace
              fees.
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <button
              onClick={() => void load(true)}
              disabled={loading}
              className="flex cursor-pointer items-center gap-2 rounded-lg border border-white/[0.1] px-3 py-2 text-xs font-semibold text-slate-300 transition-colors hover:bg-white/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:opacity-50"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
              />
              Refresh sold evidence
            </button>
            <button
              onClick={() => onUsePrice(r.recommended_price)}
              className="flex cursor-pointer items-center gap-2 rounded-lg bg-cyan-400 px-3 py-2 text-xs font-bold text-slate-950 transition-colors hover:bg-cyan-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200"
            >
              <Check className="h-3.5 w-3.5" />
              Use {formatCurrency(r.recommended_price)}
            </button>
          </div>
        </div>
        {error && (
          <p className="mt-3 text-xs text-amber-300">
            <AlertTriangle className="mr-1 inline h-3.5 w-3.5" />
            {error}; showing the previous analysis.
          </p>
        )}
      </section>

      <section className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.025] p-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="font-semibold text-slate-100">Expected sale → listing price</h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">The market valuation stays separate from fulfilment costs, risk reserves, fees and offer headroom.</p>
          </div>
          <p className="text-right text-xs text-slate-500">Recommended<br/><strong className="text-xl text-emerald-300">{formatCurrency(data.price_bridge.recommended_listing_price)}</strong></p>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <tbody>
              {[
                ["Normalised expected sold price", data.price_bridge.expected_sold_price, "Evidence-based target—not an asking price"],
                ["Delivery", data.price_bridge.delivery_cost, "Baked into free-delivery pricing"],
                ["Shipping insurance", data.price_bridge.insurance_cost, "Saved live quote"],
                ["Packaging", data.price_bridge.packaging_cost, "Box and protective materials"],
                [`Warranty reserve (${data.price_bridge.warranty_reserve_pct}%)`, data.price_bridge.warranty_reserve, "Reserve against claims and repairs"],
                ["Marketplace fee allowance", data.price_bridge.marketplace_fee_allowance, `Configured rate ${r.fee_rate_pct}%`],
                [`Offer headroom (${data.price_bridge.negotiation_headroom_pct}%)`, data.price_bridge.negotiation_headroom, "Room for offers and price reductions"],
              ].map(([label, value, note]) => (
                <tr key={String(label)} className="border-b border-white/[0.055] last:border-0">
                  <td className="py-2.5 text-slate-300">{label}<span className="ml-2 text-xs text-slate-600">{note}</span></td>
                  <td className="py-2.5 text-right font-semibold text-slate-200">{formatCurrency(Number(value))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex items-center justify-between rounded-lg border border-emerald-300/20 bg-emerald-300/[0.06] px-3 py-3">
          <span className="text-sm font-bold text-slate-100">Recommended listing price</span>
          <strong className="text-xl text-emerald-300">{formatCurrency(data.price_bridge.recommended_listing_price)}</strong>
        </div>
      </section>

      <section className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
        <div className="mb-3 flex items-end justify-between">
          <div>
            <h2 className="font-semibold">Component valuation</h2>
            <p className="mt-1 text-xs text-slate-500">
              Useful resale context, but never added together as proof of a
              complete-PC selling price.
            </p>
          </div>
          <span className="text-sm font-semibold text-slate-300">
            Paid {formatCurrency(data.cost_price)}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-white/[0.07] text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-2 py-2">Component</th>
                <th className="px-2 py-2 text-right">Paid</th>
                <th className="px-2 py-2 text-right">Est. resale</th>
                <th className="px-2 py-2 text-right">Difference</th>
                <th className="px-2 py-2">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {data.component_valuations.map((item) => (
                <tr
                  key={item.slot}
                  className="border-b border-white/[0.045] last:border-0"
                >
                  <td className="px-2 py-3">
                    <p className="font-medium text-slate-200">{item.name}</p>
                    <p className="text-[10px] font-mono uppercase text-slate-600">
                      {item.slot.replaceAll("_", " ")}
                    </p>
                  </td>
                  <td className="px-2 py-3 text-right text-slate-400">
                    {formatCurrency(item.price_paid)}
                  </td>
                  <td className="px-2 py-3 text-right font-semibold text-cyan-300">
                    {formatCurrency(item.estimated_resale)}
                  </td>
                  <td
                    className={`px-2 py-3 text-right ${
                      item.estimated_resale >= item.price_paid
                        ? "text-emerald-300"
                        : "text-slate-500"
                    }`}
                  >
                    {item.estimated_resale >= item.price_paid ? "+" : ""}
                    {formatCurrency(item.estimated_resale - item.price_paid)}
                  </td>
                  <td className="px-2 py-3">
                    <div className="flex items-center gap-2">
                      <Confidence value={item.confidence} />
                      <span className="max-w-xs text-xs text-slate-500">
                        {item.estimate_basis}
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t border-white/[0.1] font-semibold">
              <tr>
                <td className="px-2 py-3">Totals</td>
                <td className="px-2 py-3 text-right">
                  {formatCurrency(data.cost_price)}
                </td>
                <td className="px-2 py-3 text-right text-cyan-300">
                  {formatCurrency(data.component_resale_total)}
                </td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold">Same and similar builds</h2>
            <p className="mt-1 text-xs text-slate-500">
              Completed eBay prices take priority; retailer prices are
              asking-price context only.
            </p>
          </div>
          <span className="text-xs text-slate-500">
            {sold.length} sold · {active.length} active
          </span>
        </div>
        {data.market_comparables.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed border-white/[0.1] p-5 text-center text-sm text-slate-500">
            No cached comparable builds yet. Use “Refresh sold evidence” to
            search eBay; Overclockers will appear here when a matching prebuilt
            is in the live catalogue.
          </div>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-white/[0.07] text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-2 py-2">Source / build</th>
                  <th className="px-2 py-2">Evidence date</th>
                  <th className="px-2 py-2">Type</th>
                  <th className="px-2 py-2 text-right">Price</th>
                  <th className="px-2 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.market_comparables.map((item, index) => (
                  <tr
                    key={`${item.url}-${index}`}
                    className="border-b border-white/[0.045]"
                  >
                    <td className="px-2 py-3">
                      <p className="max-w-xl truncate text-slate-200">
                        {item.title}
                      </p>
                      <p className="text-xs text-slate-500">
                        {item.source} · {item.match_basis}
                      </p>
                    </td>
                    <td className="px-2 py-3 text-slate-400">
                      {item.observed_or_sold_at
                        ? new Date(item.observed_or_sold_at).toLocaleDateString(
                            "en-GB"
                          )
                        : "—"}
                    </td>
                    <td className="px-2 py-3">
                      <span
                        className={`rounded px-2 py-1 text-[10px] font-semibold uppercase ${
                          item.status === "sold"
                            ? "bg-emerald-400/10 text-emerald-300"
                            : "bg-amber-400/10 text-amber-300"
                        }`}
                      >
                        {item.status}
                      </span>
                    </td>
                    <td className="px-2 py-3 text-right font-semibold">
                      {formatCurrency(item.price)}
                    </td>
                    <td className="px-2 py-3 text-right">
                      {item.url && (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          aria-label={`Open ${item.title}`}
                          className="inline-flex cursor-pointer rounded p-1 text-slate-500 transition-colors hover:text-cyan-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-300" />
            <h2 className="font-semibold">Offer guardrails</h2>
          </div>
          <div className="mt-4 space-y-3 text-sm">
            {[
              ["Auto-accept at or above", r.auto_accept_at, "text-emerald-300"],
              ["Always counter from", r.counter_offer_from, "text-cyan-300"],
              ["Auto-reject below", r.auto_reject_below, "text-red-300"],
              ["Never reduce below", r.floor_price, "text-amber-300"],
            ].map(([label, value, tone]) => (
              <div
                key={String(label)}
                className="flex items-center justify-between border-b border-white/[0.05] pb-3 last:border-0"
              >
                <span className="text-slate-400">{label}</span>
                <strong className={String(tone)}>
                  {formatCurrency(Number(value))}
                </strong>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
          <h2 className="font-semibold">Suggested price automation</h2>
          <div className="mt-4 space-y-0">
            {r.automation.map((step, index) => (
              <div
                key={step.day}
                className="grid grid-cols-[52px_18px_1fr_auto] gap-2"
              >
                <span className="pt-0.5 text-xs font-mono text-slate-500">
                  Day {step.day}
                </span>
                <div className="flex flex-col items-center">
                  <span className="mt-1 h-2 w-2 rounded-full bg-cyan-400" />
                  {index < r.automation.length - 1 && (
                    <span className="min-h-12 w-px flex-1 bg-white/[0.08]" />
                  )}
                </div>
                <div className="pb-4">
                  <p className="text-sm text-slate-200">{step.action}</p>
                  <p className="mt-1 text-xs text-slate-600">
                    {step.rationale}
                  </p>
                </div>
                <strong className="text-sm text-slate-300">
                  {formatCurrency(step.price)}
                </strong>
              </div>
            ))}
          </div>
        </div>
      </section>
      {detailModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4"
          onClick={() => setDetailModal(null)}
        >
          <div
            className={`max-h-[90vh] w-full overflow-auto rounded-2xl border border-cyan-400/20 bg-slate-950 p-5 shadow-2xl ${
              detailModal === "market" ? "max-w-7xl" : "max-w-3xl"
            }`}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">
                  {detailModal === "cost"
                    ? "Actual build cost"
                    : detailModal === "resale"
                    ? "Parts market value"
                    : "Market recommendation evidence"}
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Every value shown comes from the current build record or
                  recorded market evidence.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDetailModal(null)}
                className="rounded px-2 py-1 text-slate-400 hover:bg-white/10"
              >
                Close
              </button>
            </div>
            {detailModal !== "market" ? (
              <table className="mt-5 w-full text-sm">
                <thead className="border-b border-white/10 text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2">Component</th>
                    <th className="py-2 text-right">Paid</th>
                    {detailModal === "resale" && (
                      <th className="py-2 text-right">Market value</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {data.component_valuations.map((item) => (
                    <tr
                      key={item.slot}
                      className="border-b border-white/[0.06]"
                    >
                      <td className="py-3 text-slate-200">
                        {item.name}
                        <span className="ml-2 text-[10px] uppercase text-slate-600">
                          {item.slot.replaceAll("_", " ")}
                        </span>
                      </td>
                      <td className="py-3 text-right text-slate-300">
                        {formatCurrency(item.price_paid)}
                      </td>
                      {detailModal === "resale" && (
                        <td className="py-3 text-right text-cyan-300">
                          {formatCurrency(item.estimated_resale)}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
                <tfoot className="font-semibold">
                  <tr>
                    <td className="py-3">Total</td>
                    <td className="py-3 text-right">
                      {formatCurrency(data.cost_price)}
                    </td>
                    {detailModal === "resale" && (
                      <td className="py-3 text-right text-cyan-300">
                        {formatCurrency(data.component_resale_total)}
                      </td>
                    )}
                  </tr>
                </tfoot>
              </table>
            ) : !hasMarketEvidence ? (
              <div className="mt-5 rounded-lg border border-dashed border-amber-400/20 bg-amber-400/5 p-5 text-sm text-amber-200">
                No completed or active comparable builds were found. No market
                range can be supported yet; the provisional list price is a
                cost-and-margin calculation only.
              </div>
            ) : (
              <MarketEvidence sold={sold} active={active} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
