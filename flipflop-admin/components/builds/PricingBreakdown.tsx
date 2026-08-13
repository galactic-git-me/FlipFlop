"use client";

import { useState } from "react";
import {
  ChevronDown, Download, Info, TrendingUp, Clock, AlertCircle,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";

interface SoldCompDetail {
  title: string | null;
  price: number;
  condition: string;
  sold_at: string;
  url: string | null;
  ram_gb?: number | null;
}

interface CacheInfo {
  seconds_ago?: number | null;
  seconds_until_expiry?: number | null;
  is_cached: boolean;
}

interface PricingDetail {
  type: string;
  value: number;
  description: string;
}

interface PricingBreakdownData {
  estimated_price: number;
  primary_reasoning: PricingDetail;
  sold_comps: SoldCompDetail[];
  bin_prices: number[];
  demand_signals?: Record<string, unknown> | null;
  cache_info: CacheInfo;
  cost_price: number;
  delivery_cost: number;
  estimated_profit: number;
  is_loss: boolean;
  fetched_at: string;
}

type Props = {
  buildId: string;
  onPricingUpdate?: (price: number) => void;
};

export function PricingBreakdown({ buildId, onPricingUpdate }: Props) {
  const [showDetails, setShowDetails] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<PricingBreakdownData | null>(null);
  const [confirmedLoss, setConfirmedLoss] = useState(false);

  const fetchPricing = async (fetchSold: boolean): Promise<PricingBreakdownData> => {
    const response = await fetch(`/api/builds/${buildId}/pricing?fetch_sold=${fetchSold}`);
    if (!response.ok) throw new Error("Failed to fetch pricing data");
    return (await response.json()) as PricingBreakdownData;
  };

  const handleImportSoldData = async () => {
    setLoading(true);
    setError(null);
    setConfirmedLoss(false);
    try {
      const pricing = await fetchPricing(true);
      setData(pricing);
      // Only auto-apply the price if it wouldn't cause a loss — a loss-making
      // price requires the explicit confirmation below before it's applied.
      if (!pricing.is_loss && onPricingUpdate) {
        onPricingUpdate(pricing.estimated_price);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmLossPrice = () => {
    setConfirmedLoss(true);
    if (data && onPricingUpdate) {
      onPricingUpdate(data.estimated_price);
    }
  };

  const handleViewDetails = async () => {
    if (!data) {
      setLoading(true);
      setError(null);
      try {
        setData(await fetchPricing(false));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }
    setShowDetails(!showDetails);
  };

  const formatTimeAgo = (seconds: number | null | undefined): string => {
    if (seconds == null) return "Unknown";
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const formatTimeRemaining = (seconds: number | null | undefined): string => {
    if (seconds == null) return "Unknown";
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
    return `${Math.floor(seconds / 86400)}d`;
  };

  const totalCost = (data?.cost_price ?? 0) + (data?.delivery_cost ?? 0);
  const marginPercent = data && totalCost > 0 ? ((data.estimated_profit / totalCost) * 100).toFixed(1) : "0";

  return (
    <div className="space-y-3">
      {/* Summary line */}
      <div className={`flex items-center justify-between p-3 rounded-lg border ${
        data?.is_loss ? "bg-red-900/20 border-red-700/50" : "bg-slate-900/50 border-slate-700/50"
      }`}>
        <div className="space-y-1 flex-1">
          <p className="text-sm text-slate-400">Estimated listing price</p>
          <p className="text-2xl font-bold text-cyan-400">
            £{Math.round(data?.estimated_price ?? 0)}
          </p>

          {data && (
            <div className="text-xs space-y-1 mt-2 pt-2 border-t border-slate-700/50">
              <div className="flex justify-between text-slate-400">
                <span>Cost (components + delivery):</span>
                <span>£{Math.round(totalCost)}</span>
              </div>
              <div className={`flex justify-between font-semibold ${
                data.is_loss ? "text-red-400" : "text-emerald-400"
              }`}>
                <span>Estimated {data.is_loss ? "loss" : "profit"}:</span>
                <span>
                  {data.is_loss ? "-" : "+"}£{Math.abs(Math.round(data.estimated_profit))} ({marginPercent}%)
                </span>
              </div>

              {data.is_loss && !confirmedLoss && (
                <div className="mt-2 p-2 bg-red-950/40 border border-red-700/50 rounded space-y-2">
                  <p className="text-red-400 font-semibold text-xs">
                    ⚠️ This price would result in a £{Math.abs(Math.round(data.estimated_profit))} loss.
                    The suggested price has NOT been applied to the asking price field.
                  </p>
                  <button
                    onClick={handleConfirmLossPrice}
                    className="w-full px-2 py-1.5 bg-red-700 hover:bg-red-600 text-white text-xs rounded font-semibold transition-colors"
                  >
                    I understand — apply this price anyway
                  </button>
                </div>
              )}

              {data.is_loss && confirmedLoss && (
                <p className="text-amber-400 font-semibold text-xs mt-1">
                  ✓ Loss-making price confirmed and applied.
                </p>
              )}
            </div>
          )}

          {data && (
            <p className="text-xs text-slate-500 mt-2">
              {data.primary_reasoning.description}
            </p>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleImportSoldData}
            disabled={loading}
            className="px-3 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-700 text-white text-sm rounded-lg flex items-center gap-2 transition-colors"
          >
            <Download size={16} />
            {loading ? "Importing..." : "Import Sold Data"}
          </button>

          <button
            onClick={handleViewDetails}
            className="px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded-lg flex items-center gap-2 transition-colors"
          >
            <Info size={16} />
            Details
            <ChevronDown size={16} className={`transition-transform ${showDetails ? "rotate-180" : ""}`} />
          </button>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="p-3 bg-red-900/20 border border-red-700/50 rounded-lg flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Details panel */}
      {showDetails && data && (
        <div className="space-y-3 p-4 bg-slate-800/50 border border-slate-700/50 rounded-lg">
          {/* Cache info */}
          {data.cache_info.is_cached && (
            <div className="p-2 bg-slate-700/30 rounded text-xs text-slate-400 flex items-center gap-2">
              <Clock size={14} />
              Cached {formatTimeAgo(data.cache_info.seconds_ago)}, expires in{" "}
              {formatTimeRemaining(data.cache_info.seconds_until_expiry)}
            </div>
          )}

          {/* Sold comps table */}
          {data.sold_comps.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                <TrendingUp size={16} />
                Recently Sold Builds ({data.sold_comps.length})
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700/50">
                      <th className="text-left p-2 text-slate-400">Build</th>
                      <th className="text-right p-2 text-slate-400">Price</th>
                      <th className="text-left p-2 text-slate-400">RAM</th>
                      <th className="text-left p-2 text-slate-400">Condition</th>
                      <th className="text-left p-2 text-slate-400">Link</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.sold_comps.map((comp, idx) => (
                      <tr key={comp.url ?? `${comp.title}-${idx}`} className="border-b border-slate-700/30 hover:bg-slate-700/20">
                        <td className="p-2 text-slate-300 truncate max-w-xs">
                          {comp.title || "Unknown build"}
                        </td>
                        <td className="p-2 text-right text-cyan-400 font-semibold">
                          {formatCurrency(comp.price)}
                        </td>
                        <td className="p-2 text-slate-400">
                          {comp.ram_gb ? `${comp.ram_gb}GB` : "—"}
                        </td>
                        <td className="p-2 text-slate-400 text-xs capitalize">
                          {comp.condition.toLowerCase()}
                        </td>
                        <td className="p-2">
                          {comp.url ? (
                            <a
                              href={comp.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-400 hover:text-blue-300 underline text-xs"
                            >
                              eBay
                            </a>
                          ) : (
                            <span className="text-slate-500 text-xs">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* BIN prices */}
          {data.bin_prices.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-300">Current Listings (BIN)</h4>
              <p className="text-sm text-slate-400">
                Average: {formatCurrency(data.bin_prices.reduce((a, b) => a + b) / data.bin_prices.length)}
                {" "}
                from {data.bin_prices.length} active listings
              </p>
              <p className="text-xs text-slate-500">
                Range: {formatCurrency(Math.min(...data.bin_prices))} —{" "}
                {formatCurrency(Math.max(...data.bin_prices))}
              </p>
            </div>
          )}

          {/* Reasoning breakdown */}
          <div className="space-y-2 pt-2 border-t border-slate-700/50">
            <h4 className="text-sm font-semibold text-slate-300">Pricing Reasoning</h4>
            <div className="text-sm space-y-1">
              <p className="text-slate-400">
                Primary source: <span className="text-slate-300 font-semibold capitalize">{data.primary_reasoning.type.replace(/_/g, " ")}</span>
              </p>
              <p className="text-slate-400">
                Estimated price: <span className="text-cyan-400 font-semibold">{formatCurrency(data.primary_reasoning.value)}</span>
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
