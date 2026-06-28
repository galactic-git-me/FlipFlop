"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Loader2,
  TrendingUp,
} from "lucide-react";
import { api } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

function SummaryCard({
  label,
  value,
  currency = true,
  bgColor = "bg-slate-800/30",
  textColor = "text-slate-300",
}: {
  label: string;
  value: string | number;
  currency?: boolean;
  bgColor?: string;
  textColor?: string;
}) {
  return (
    <div className={`${bgColor} rounded-lg p-4 border border-slate-700`}>
      <p className="text-xs text-slate-500 uppercase tracking-wider mb-2 font-semibold">
        {label}
      </p>
      <p className={`text-lg font-bold ${textColor} font-mono`}>
        {currency ? "£" : ""}{typeof value === "number" ? value.toFixed(2) : value}
      </p>
    </div>
  );
}

export default function ProfitBreakdownPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [breakdown, setBreakdown] = useState<ProfitBreakdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.flips
      .profitBreakdown(Number(id))
      .then((data) => {
        setBreakdown(data as ProfitBreakdown);
        setError(null);
      })
      .catch((err) => {
        console.error("Failed to load profit breakdown:", err);
        setError("Failed to load profit breakdown");
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading profit breakdown…
      </div>
    );
  }

  if (error || !breakdown) {
    return (
      <div className="flex flex-col h-full min-h-0 p-6 gap-5 max-w-3xl mx-auto w-full">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back
          </button>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">
          {error || "Failed to load profit breakdown"}
        </div>
      </div>
    );
  }

  const isPositiveProfit = breakdown.profit >= 0;

  return (
    <div className="flex flex-col h-full min-h-0 p-6 gap-5 max-w-3xl mx-auto w-full">
      {/* ── Header ── */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back
        </button>
        <span className="text-slate-700">/</span>
        <h1 className="text-2xl font-bold text-slate-200 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-[#00dc82]" />
          Flip #{breakdown.flip_id} Profit Breakdown
        </h1>
      </div>

      {/* ── Summary Cards (4 columns) ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard
          label="Sale Price"
          value={breakdown.sale_price}
          bgColor="bg-slate-800/50"
          textColor="text-slate-200"
        />
        <SummaryCard
          label="Selling Fee"
          value={breakdown.selling_fee}
          bgColor="bg-red-500/10"
          textColor="text-red-400"
        />
        <SummaryCard
          label="Total Inventory Cost"
          value={breakdown.total_landed_cost}
          bgColor="bg-amber-500/10"
          textColor="text-amber-400"
        />
        <SummaryCard
          label="Net Profit"
          value={breakdown.profit}
          bgColor={isPositiveProfit ? "bg-green-500/10" : "bg-red-500/10"}
          textColor={isPositiveProfit ? "text-green-400" : "text-red-400"}
        />
      </div>

      {/* ── Profit Margin Badge ── */}
      {breakdown.profit !== 0 && (
        <div className="flex items-center justify-center">
          <div
            className={`px-4 py-2 rounded-lg font-semibold text-sm font-mono ${
              isPositiveProfit
                ? "bg-green-500/10 text-green-400 border border-green-500/30"
                : "bg-red-500/10 text-red-400 border border-red-500/30"
            }`}
          >
            {breakdown.profit_margin_pct.toFixed(1)}% Margin
          </div>
        </div>
      )}

      {/* ── Cost Breakdown Section ── */}
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-6 flex flex-col gap-4">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Cost Breakdown
        </p>

        <div className="space-y-3 text-sm font-mono">
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Sale Price</span>
            <span className="text-slate-300 font-semibold">£{breakdown.sale_price.toFixed(2)}</span>
          </div>

          <div className="flex justify-between items-center">
            <span className="text-slate-400">− Selling Fee</span>
            <span className="text-red-400">−£{breakdown.selling_fee.toFixed(2)}</span>
          </div>

          <div className="flex justify-between items-center border-t border-slate-700 pt-3">
            <span className="text-blue-400 font-medium">= Net Proceeds</span>
            <span className="text-blue-400 font-bold">£{breakdown.net_proceeds.toFixed(2)}</span>
          </div>

          <div className="flex justify-between items-center">
            <span className="text-slate-400">− Inventory Costs</span>
            <span className="text-amber-400">−£{breakdown.total_landed_cost.toFixed(2)}</span>
          </div>

          <div className="flex justify-between items-center border-t border-slate-700 pt-3">
            <span className={`font-medium ${isPositiveProfit ? "text-green-400" : "text-red-400"}`}>
              = Profit
            </span>
            <span className={`font-bold ${isPositiveProfit ? "text-green-400" : "text-red-400"}`}>
              £{breakdown.profit.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* ── Allocated Inventory Section ── */}
      {breakdown.allocations.length > 0 ? (
        <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-6 flex flex-col gap-4">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Allocated Inventory
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left text-xs text-slate-500 uppercase tracking-wider font-semibold py-2 px-3">
                    Item
                  </th>
                  <th className="text-right text-xs text-slate-500 uppercase tracking-wider font-semibold py-2 px-3">
                    Qty
                  </th>
                  <th className="text-right text-xs text-slate-500 uppercase tracking-wider font-semibold py-2 px-3">
                    Cost per Unit
                  </th>
                  <th className="text-right text-xs text-slate-500 uppercase tracking-wider font-semibold py-2 px-3">
                    Total Cost
                  </th>
                </tr>
              </thead>
              <tbody>
                {breakdown.allocations.map((alloc) => (
                  <tr key={alloc.inventory_item_id} className="border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors">
                    <td className="text-slate-300 py-3 px-3">
                      Item #{alloc.inventory_item_id}
                    </td>
                    <td className="text-right text-slate-400 py-3 px-3">
                      {alloc.quantity}
                    </td>
                    <td className="text-right text-amber-400 font-mono py-3 px-3">
                      £{alloc.cost_per_unit.toFixed(2)}
                    </td>
                    <td className="text-right text-slate-400 font-mono py-3 px-3">
                      £{alloc.total_cost.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="border-t border-slate-700 pt-3 mt-2 flex justify-between text-sm font-mono">
            <span className="text-slate-500">Total allocated cost</span>
            <span className="text-slate-300 font-semibold">£{breakdown.total_landed_cost.toFixed(2)}</span>
          </div>
        </div>
      ) : (
        <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-6">
          <p className="text-slate-500 text-sm text-center">
            No inventory allocations yet
          </p>
        </div>
      )}
    </div>
  );
}
