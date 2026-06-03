"use client";

import React, { useState, useEffect } from "react";
import {
  TrendingUp, DollarSign, Package, Clock, Target,
  AlertCircle, CheckCircle2, Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Sale {
  id: number;
  title: string;
  sale_price: number;
  profit: number;
  sold_at: string;
  profit_margin_pct: number;
}

interface DashboardData {
  summary: {
    total_flips_sold: number;
    total_revenue: number;
    total_profit: number;
    total_invested: number;
    active_listings: number;
    success_rate: number;
  };
  averages: {
    profit_per_flip: number;
    sale_price: number;
    time_to_sell_days: number;
  };
  recent_sales: Sale[];
}

interface ActiveListing {
  id: number;
  ebay_listing_id: string;
  title: string;
  price: number;
  estimated_profit: number;
  listed_at: string;
  days_listed: number;
  status: string;
}

export function SalesDashboard() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [activeSales, setActiveSales] = useState<ActiveListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        setLoading(true);
        const [dashRes, salesRes] = await Promise.all([
          fetch("/api/reselling/sales-dashboard"),
          fetch("/api/reselling/active-sales"),
        ]);

        if (!dashRes.ok || !salesRes.ok) {
          throw new Error("Failed to fetch sales data");
        }

        const dashData = await dashRes.json();
        const salesData = await salesRes.json();

        setDashboard(dashData);
        setActiveSales(salesData.active_listings || []);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
    const interval = setInterval(fetchDashboard, 30000); // Refresh every 30 seconds

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-slate-400">Loading sales dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-400/10 border border-red-400/30 rounded-lg">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-red-300">Error Loading Dashboard</div>
            <div className="text-sm text-red-300/80 mt-1">{error}</div>
          </div>
        </div>
      </div>
    );
  }

  if (!dashboard) {
    return null;
  }

  const { summary, averages, recent_sales } = dashboard;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Sales Dashboard</h2>
        <p className="text-sm text-slate-500 mt-1">Track your flips from listing to sold</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          label="Total Sold"
          value={summary.total_flips_sold}
          icon={<CheckCircle2 className="w-5 h-5" />}
          unit="flips"
          color="emerald"
        />
        <MetricCard
          label="Total Profit"
          value={`£${summary.total_profit.toFixed(0)}`}
          icon={<TrendingUp className="w-5 h-5" />}
          color="cyan"
        />
        <MetricCard
          label="Success Rate"
          value={summary.success_rate.toFixed(1)}
          icon={<Target className="w-5 h-5" />}
          unit="%"
          color="yellow"
        />
      </div>

      {/* Detailed Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <DetailMetric
          label="Revenue"
          value={`£${summary.total_revenue.toFixed(0)}`}
          subtext={`${summary.total_flips_sold} sales`}
        />
        <DetailMetric
          label="Avg Profit"
          value={`£${averages.profit_per_flip.toFixed(0)}`}
          subtext="per flip"
        />
        <DetailMetric
          label="Avg Price"
          value={`£${averages.sale_price.toFixed(0)}`}
          subtext="sale price"
        />
        <DetailMetric
          label="Time to Sell"
          value={`${averages.time_to_sell_days.toFixed(1)}`}
          subtext="days"
        />
      </div>

      {/* Active Listings */}
      <div className="bg-[#0d1320] border border-[#1e2d45] rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-100">
            <Package className="w-4 h-4 inline mr-2" />
            Active Listings ({summary.active_listings})
          </h3>
          <a
            href="/chat"
            className="text-xs text-[#00dc82] hover:text-[#00dc82]/80 transition"
          >
            View on eBay →
          </a>
        </div>

        {activeSales.length === 0 ? (
          <div className="text-center py-8">
            <Zap className="w-8 h-8 text-slate-600 mx-auto mb-2" />
            <p className="text-sm text-slate-500">No active listings</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[200px] overflow-y-auto">
            {activeSales.map((listing) => (
              <div
                key={listing.id}
                className="p-3 bg-[#0a0f1a] rounded border border-[#1e2d45] hover:border-[#00dc82]/30 transition"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-slate-200 truncate">
                      {listing.title}
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      Listed {listing.days_listed} day{listing.days_listed !== 1 ? "s" : ""} ago
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="text-sm font-semibold text-[#00dc82]">
                      £{listing.estimated_profit.toFixed(0)}
                    </div>
                    <div className="text-xs text-slate-500">profit</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Sales */}
      <div className="bg-[#0d1320] border border-[#1e2d45] rounded-lg p-6">
        <h3 className="font-semibold text-slate-100 mb-4">
          <TrendingUp className="w-4 h-4 inline mr-2" />
          Recent Sales (Last 7 Days)
        </h3>

        {recent_sales.length === 0 ? (
          <div className="text-center py-8">
            <Clock className="w-8 h-8 text-slate-600 mx-auto mb-2" />
            <p className="text-sm text-slate-500">No recent sales</p>
          </div>
        ) : (
          <div className="space-y-3">
            {recent_sales.map((sale) => (
              <SaleRecord key={sale.id} sale={sale} />
            ))}
          </div>
        )}
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <StatBox
          label="Investment"
          value={`£${summary.total_invested.toFixed(0)}`}
          subtext={`${summary.total_flips_sold} flips`}
          icon="📊"
        />
        <StatBox
          label="ROI"
          value={`${((summary.total_profit / summary.total_invested) * 100).toFixed(0)}%`}
          subtext="return on investment"
          icon="📈"
        />
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon,
  unit,
  color,
}: {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  unit?: string;
  color: "emerald" | "cyan" | "yellow";
}) {
  const colorClasses = {
    emerald: "bg-emerald-400/10 text-emerald-400 border-emerald-400/30",
    cyan: "bg-cyan-400/10 text-cyan-400 border-cyan-400/30",
    yellow: "bg-yellow-400/10 text-yellow-400 border-yellow-400/30",
  };

  return (
    <div className={cn("p-4 rounded-lg border", colorClasses[color])}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs text-slate-500 mb-1">{label}</div>
          <div className="text-2xl font-bold">
            {value}
            {unit && <span className="text-sm ml-1">{unit}</span>}
          </div>
        </div>
        <div className="opacity-50">{icon}</div>
      </div>
    </div>
  );
}

function DetailMetric({
  label,
  value,
  subtext,
}: {
  label: string;
  value: string;
  subtext?: string;
}) {
  return (
    <div className="p-3 bg-[#0a0f1a] rounded border border-[#1e2d45]">
      <div className="text-xs text-slate-600 uppercase tracking-wider">{label}</div>
      <div className="text-lg font-bold text-slate-200 mt-1">{value}</div>
      {subtext && <div className="text-xs text-slate-500 mt-1">{subtext}</div>}
    </div>
  );
}

function SaleRecord({ sale }: { sale: Sale }) {
  const date = new Date(sale.sold_at);
  const timeAgo = getTimeAgo(date);

  return (
    <div className="p-3 bg-[#0a0f1a] rounded border border-[#1e2d45] hover:border-emerald-400/30 transition">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-slate-200 truncate">{sale.title}</div>
          <div className="text-xs text-slate-500 mt-0.5">Sold {timeAgo}</div>
        </div>
        <div className="text-right flex-shrink-0">
          <div className="text-sm font-semibold text-emerald-400">
            +£{sale.profit.toFixed(0)}
          </div>
          <div className="text-xs text-slate-500">
            {sale.profit_margin_pct.toFixed(0)}% margin
          </div>
        </div>
      </div>
    </div>
  );
}

function StatBox({
  label,
  value,
  subtext,
  icon,
}: {
  label: string;
  value: string;
  subtext?: string;
  icon: string;
}) {
  return (
    <div className="p-4 bg-[#0d1320] border border-[#1e2d45] rounded-lg">
      <div className="flex items-start gap-3">
        <div className="text-2xl">{icon}</div>
        <div className="flex-1">
          <div className="text-xs text-slate-600 uppercase tracking-wider">{label}</div>
          <div className="text-xl font-bold text-slate-200 mt-1">{value}</div>
          {subtext && <div className="text-xs text-slate-500 mt-0.5">{subtext}</div>}
        </div>
      </div>
    </div>
  );
}

function getTimeAgo(date: Date): string {
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;

  const days = Math.floor(seconds / 86400);
  return `${days}d ago`;
}
