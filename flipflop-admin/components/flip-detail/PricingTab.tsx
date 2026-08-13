"use client";

import { useEffect, useState } from "react";
import { Loader2, RefreshCw, TrendingUp, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import type { Flip, TabProps } from "./types";

function money(v: number | null | undefined) {
  return v === null || v === undefined ? "—" : `£${v.toFixed(2)}`;
}

interface ProfitBreakdown {
  flip_id: number;
  sale_price: number;
  selling_fee: number;
  net_proceeds: number;
  total_landed_cost: number;
  profit: number;
  profit_margin_pct: number;
  allocations: Array<{
    inventory_item_id: number;
    quantity: number;
    cost_per_unit: number;
    total_cost: number;
  }>;
}

export function PricingTab({ flip, onFlipUpdated }: TabProps) {
  const [minOffer, setMinOffer] = useState(flip.min_offer_price?.toString() ?? "");
  const [offersEnabled, setOffersEnabled] = useState(flip.offers_enabled);
  const [savingOffer, setSavingOffer] = useState(false);
  const [checkingDemand, setCheckingDemand] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [testOffer, setTestOffer] = useState("");
  const [testResult, setTestResult] = useState<{ action: string; counter_price: number | null; reason: string } | null>(null);
  const [testingOffer, setTestingOffer] = useState(false);

  const fees = flip.current_estimated_resale ? flip.current_estimated_resale * flip.platform_fee_pct : 0;

  const [breakdown, setBreakdown] = useState<ProfitBreakdown | null>(null);
  useEffect(() => {
    if (flip.stage !== "sold") return;
    api.flips
      .profitBreakdown(flip.id)
      .then((data) => setBreakdown(data as ProfitBreakdown))
      .catch(() => setBreakdown(null));
  }, [flip.id, flip.stage]);

  async function saveOfferSettings() {
    setSavingOffer(true);
    try {
      const updated = await api.flips.patch(flip.id, {
        min_offer_price: minOffer ? parseFloat(minOffer) : null,
        offers_enabled: offersEnabled,
      });
      onFlipUpdated(updated as Flip);
    } finally {
      setSavingOffer(false);
    }
  }

  async function runDemandCheck() {
    setCheckingDemand(true);
    try {
      await api.flips.demandCheck(flip.id);
      const updated = await api.flips.get(flip.id);
      onFlipUpdated(updated as Flip);
    } finally {
      setCheckingDemand(false);
    }
  }

  async function runRecalculatePricing() {
    setRecalculating(true);
    try {
      await api.flips.recalculatePricing(flip.id);
      const updated = await api.flips.get(flip.id);
      onFlipUpdated(updated as Flip);
    } finally {
      setRecalculating(false);
    }
  }

  async function runTestOffer() {
    if (!testOffer) return;
    setTestingOffer(true);
    try {
      const result = await api.flips.counterOffer(flip.id, parseFloat(testOffer));
      setTestResult(result);
      const updated = await api.flips.get(flip.id);
      onFlipUpdated(updated as Flip);
    } finally {
      setTestingOffer(false);
    }
  }

  const demandRatioLabel =
    flip.demand_active_count == null
      ? "Not checked yet"
      : flip.demand_sold_count_90d == null
      ? `${flip.demand_active_count} active listings · sold data unavailable (needs Marketplace Insights API access)`
      : `${flip.demand_sold_count_90d} sold / ${flip.demand_active_count} active (last 90 days)`;

  return (
    <div className="flex flex-col gap-4">
      {/* Financials */}
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Financials</p>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-500">Base cost</span>
            <span className="font-mono text-slate-300">{money(flip.base_cost)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Upgrade cost</span>
            <span className="font-mono text-slate-300">{money(flip.upgrade_cost)}</span>
          </div>
          <div className="flex justify-between border-t border-slate-800 pt-2">
            <span className="text-slate-400 font-medium">Total in</span>
            <span className="font-mono text-slate-200 font-semibold">{money(flip.total_cost)}</span>
          </div>
          {flip.stage !== "sold" && flip.current_estimated_resale && (
            <>
              <div className="flex justify-between text-xs text-slate-600 pt-1">
                <span>Est. resale</span>
                <span className="font-mono">{money(flip.current_estimated_resale)}</span>
              </div>
              <div className="flex justify-between text-xs text-slate-600">
                <span>eBay fees (~{(flip.platform_fee_pct * 100).toFixed(1)}%)</span>
                <span className="font-mono">−{money(fees)}</span>
              </div>
              <div className="flex justify-between border-t border-slate-800 pt-2">
                <span className="text-[#00dc82] font-medium">Est. profit</span>
                <span className="font-mono text-[#00dc82] font-bold">{money(flip.current_estimated_profit)}</span>
              </div>
            </>
          )}
          {flip.stage === "sold" && (
            <>
              <div className="flex justify-between border-t border-slate-800 pt-2">
                <span className="text-slate-400">Sold for</span>
                <span className="font-mono text-slate-200">{money(flip.actual_sale_price)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-emerald-400 font-medium">Actual profit</span>
                <span className={`font-mono font-bold ${(flip.actual_profit ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {money(flip.actual_profit)}
                </span>
              </div>
              <div className="text-xs text-slate-600">via {flip.sale_platform}</div>
            </>
          )}
        </div>
        <p className="text-[11px] text-slate-600">
          Row 35: shipping cost is baked into these numbers as a flat, listed price — never
          shown as calculated shipping at checkout.
        </p>
      </div>

      {breakdown && breakdown.allocations.length > 0 && (
        <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Allocated inventory</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="text-left text-slate-500 uppercase tracking-wider font-semibold py-1.5 px-2">Item</th>
                  <th className="text-right text-slate-500 uppercase tracking-wider font-semibold py-1.5 px-2">Qty</th>
                  <th className="text-right text-slate-500 uppercase tracking-wider font-semibold py-1.5 px-2">Cost/unit</th>
                  <th className="text-right text-slate-500 uppercase tracking-wider font-semibold py-1.5 px-2">Total</th>
                </tr>
              </thead>
              <tbody>
                {breakdown.allocations.map((a) => (
                  <tr key={a.inventory_item_id} className="border-b border-slate-800/50">
                    <td className="text-slate-300 py-2 px-2">Item #{a.inventory_item_id}</td>
                    <td className="text-right text-slate-400 py-2 px-2">{a.quantity}</td>
                    <td className="text-right text-amber-400 font-mono py-2 px-2">{money(a.cost_per_unit)}</td>
                    <td className="text-right text-slate-400 font-mono py-2 px-2">{money(a.total_cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-between text-xs pt-1 border-t border-slate-800">
            <span className="text-slate-500">Margin</span>
            <span className="text-slate-300 font-mono font-semibold">{breakdown.profit_margin_pct.toFixed(1)}%</span>
          </div>
        </div>
      )}

      {/* Demand check */}
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Demand check</p>
          <button
            onClick={runDemandCheck}
            disabled={checkingDemand}
            className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] border border-slate-700 text-slate-400 rounded-md hover:border-slate-500 transition-colors disabled:opacity-40"
          >
            {checkingDemand ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            Re-check
          </button>
        </div>
        <p className="text-sm text-slate-300">{demandRatioLabel}</p>
        {flip.demand_active_count != null && flip.demand_sold_count_90d != null && (
          <p className={`text-xs font-medium ${flip.demand_sold_count_90d / Math.max(flip.demand_active_count, 1) >= 0.15 ? "text-emerald-400" : "text-amber-400"}`}>
            {flip.demand_sold_count_90d / Math.max(flip.demand_active_count, 1) >= 0.15
              ? "Healthy sold-vs-active ratio."
              : "Low sold-vs-active ratio — long sell time is likely regardless of listing quality."}
          </p>
        )}
      </div>

      {/* Sold-comp pricing engine */}
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5" /> Sold-comp pricing engine
          </p>
          <button
            onClick={runRecalculatePricing}
            disabled={recalculating}
            className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] border border-slate-700 text-slate-400 rounded-md hover:border-slate-500 transition-colors disabled:opacity-40"
          >
            {recalculating ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            Recalculate now
          </button>
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <p className="text-slate-600 uppercase tracking-wider text-[10px] mb-0.5">Current BIN anchor</p>
            <p className="font-mono text-slate-200 text-sm">{money(flip.listing_price)}</p>
          </div>
          <div>
            <p className="text-slate-600 uppercase tracking-wider text-[10px] mb-0.5">Sold-comp target</p>
            <p className="font-mono text-slate-200 text-sm">{money(flip.sold_comp_target)}</p>
          </div>
          <div>
            <p className="text-slate-600 uppercase tracking-wider text-[10px] mb-0.5">Active range ceiling</p>
            <p className="font-mono text-slate-200 text-sm">{money(flip.active_range_ceiling)}</p>
          </div>
          <div>
            <p className="text-slate-600 uppercase tracking-wider text-[10px] mb-0.5">Price floor (cost + 10%)</p>
            <p className="font-mono text-slate-200 text-sm">{money(flip.price_floor)}</p>
          </div>
        </div>
        {flip.price_floor_hit_review_needed && (
          <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-500/5 border border-amber-500/30 rounded-lg px-3 py-2">
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
            Price hit the floor with no sale — demand read at creation may have been wrong, or the market moved. Needs human review.
          </div>
        )}
        <p className="text-[11px] text-slate-600">
          Re-anchors from fresh eBay data every time — never carries a prior cycle&apos;s stale number forward. Auto-drops toward the sold-comp target after 7 days unsold (default, confirm once), never below the floor.
        </p>
      </div>

      {/* Offers & counter-offer engine */}
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Offers</p>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={offersEnabled}
              onChange={(e) => setOffersEnabled(e.target.checked)}
              className="accent-[#00dc82]"
            />
            Accept offers (Best Offer enabled)
          </label>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500 w-28 flex-shrink-0">Minimum offer (£)</label>
          <input
            type="number"
            value={minOffer}
            onChange={(e) => setMinOffer(e.target.value)}
            placeholder="e.g. 700"
            className="flex-1 bg-slate-800 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-[#00dc82] transition-colors"
          />
        </div>
        <button
          onClick={saveOfferSettings}
          disabled={savingOffer}
          className="self-start px-3 py-1.5 text-xs bg-[#00dc82] text-[#04120d] rounded-md font-semibold hover:bg-[#00b86d] transition-colors disabled:opacity-40"
        >
          {savingOffer ? <Loader2 className="w-3 h-3 animate-spin" /> : "Save"}
        </button>

        <div className="border-t border-slate-800 pt-3 flex flex-col gap-2">
          <p className="text-[11px] text-slate-600">
            Rule 1: an offer within tolerance of the minimum gets countered roughly halfway
            between their offer and the listing price. Rule 2: a second counter gets one more
            counter at £5 off, then stops. Round used so far: <span className="text-slate-400 font-mono">{flip.counter_offer_round}/2</span>.
          </p>
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={testOffer}
              onChange={(e) => setTestOffer(e.target.value)}
              placeholder="Simulate a buyer offer (£)"
              className="flex-1 bg-slate-800 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-[#00dc82] transition-colors"
            />
            <button
              onClick={runTestOffer}
              disabled={testingOffer || !testOffer}
              className="px-3 py-1.5 text-xs border border-slate-700 text-slate-400 rounded-md hover:border-slate-500 transition-colors disabled:opacity-40"
            >
              {testingOffer ? <Loader2 className="w-3 h-3 animate-spin" /> : "Test"}
            </button>
          </div>
          {testResult && (
            <p className="text-xs text-slate-400">
              → <span className="text-slate-200 font-semibold">{testResult.action}</span>
              {testResult.counter_price != null && <> at {money(testResult.counter_price)}</>} — {testResult.reason}
            </p>
          )}
        </div>
      </div>

      {/* Promoted Listings */}
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-2">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Promoted Listings (row 40)</p>
        <p className="text-sm text-slate-300">
          Suggested ad rate: <span className="font-mono text-slate-200">5%</span> (default, confirm once — capped so
          ad spend never exceeds 15% of estimated profit margin).
        </p>
        {flip.current_estimated_profit != null && flip.current_estimated_profit < (flip.total_cost * 0.1) && (
          <p className="text-xs text-amber-400">Margin too thin to promote profitably — not suggested for this build.</p>
        )}
      </div>
    </div>
  );
}
