"use client";

import React, { useState, useEffect } from "react";
import {
  BarChart3, TrendingUp, Package, AlertCircle, CheckCircle2,
  Filter, Download, RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface VendorStats {
  source_name: string;
  total_listings: number;
  gems: number;
  gem_rate: number;
  active: boolean;
  last_scraped?: string;
  success_rate: number;
  avg_profit: number;
}

interface CatalogueStats {
  total_listings: number;
  total_gems: number;
  gem_rate: number;
  false_positive_rate: number;
  vendors_active: number;
  last_updated: string;
}

export function VendorAnalytics() {
  const [vendors, setVendors] = useState<VendorStats[]>([]);
  const [catalogue, setCatalogue] = useState<CatalogueStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<"listings" | "gems" | "rate">("listings");

  useEffect(() => {
    fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/analytics/vendors");
      if (res.ok) {
        const data = await res.json();
        setVendors(data.vendors);
        setCatalogue(data.catalogue);
      }
    } catch (err) {
      console.error("Failed to fetch vendor analytics", err);
    } finally {
      setLoading(false);
    }
  };

  const sorted = [...vendors].sort((a, b) => {
    switch (sortBy) {
      case "gems":
        return b.gems - a.gems;
      case "rate":
        return b.gem_rate - a.gem_rate;
      default:
        return b.total_listings - a.total_listings;
    }
  });

  if (loading || !catalogue) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-slate-400">Loading vendor analytics...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">Vendor Analytics</h2>
          <p className="text-sm text-slate-500 mt-1">Catalogue health & source performance</p>
        </div>
        <button
          onClick={fetchAnalytics}
          className="p-2 rounded-lg bg-[#00dc82]/10 hover:bg-[#00dc82]/20 text-[#00dc82] transition"
          title="Refresh analytics"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Catalogue Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <AnalyticsCard
          label="Total Listings"
          value={catalogue.total_listings}
          icon="📦"
          color="cyan"
        />
        <AnalyticsCard
          label="Quality Gems"
          value={catalogue.total_gems}
          subtext={`${catalogue.gem_rate.toFixed(1)}% gem rate`}
          icon="💎"
          color="emerald"
        />
        <AnalyticsCard
          label="Active Vendors"
          value={catalogue.vendors_active}
          icon="🏪"
          color="yellow"
        />
        <AnalyticsCard
          label="False Positive Rate"
          value={`${catalogue.false_positive_rate.toFixed(1)}%`}
          subtext="filtered by validator"
          icon="🎯"
          color="red"
        />
      </div>

      {/* Vendor Breakdown */}
      <div className="bg-[#0d1320] border border-[#1e2d45] rounded-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-semibold text-slate-100 flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            Vendor Performance
          </h3>
          <div className="flex gap-2">
            <SortButton
              label="By Listings"
              active={sortBy === "listings"}
              onClick={() => setSortBy("listings")}
            />
            <SortButton
              label="By Gems"
              active={sortBy === "gems"}
              onClick={() => setSortBy("gems")}
            />
            <SortButton
              label="By Rate"
              active={sortBy === "rate"}
              onClick={() => setSortBy("rate")}
            />
          </div>
        </div>

        {/* Vendor List */}
        <div className="space-y-3">
          {sorted.map((vendor) => (
            <VendorCard key={vendor.source_name} vendor={vendor} />
          ))}
        </div>

        {/* Summary Stats */}
        <div className="mt-6 pt-6 border-t border-[#1e2d45]">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatSummary
              label="Avg Listings/Vendor"
              value={Math.round(catalogue.total_listings / catalogue.vendors_active)}
            />
            <StatSummary
              label="Avg Gems/Vendor"
              value={Math.round(catalogue.total_gems / catalogue.vendors_active)}
            />
            <StatSummary
              label="Overall Gem Rate"
              value={`${catalogue.gem_rate.toFixed(1)}%`}
            />
          </div>
        </div>
      </div>

      {/* Top Performers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <TopPerformerCard
          title="Most Listings"
          vendor={sorted[0]}
          icon="📊"
          metric="total_listings"
        />
        <TopPerformerCard
          title="Best Gem Rate"
          vendor={sorted.reduce((best, v) => (v.gem_rate > best.gem_rate ? v : best))}
          icon="💎"
          metric="gem_rate"
          unit="%"
        />
      </div>

      {/* Processing Health */}
      <div className="bg-[#0d1320] border border-[#1e2d45] rounded-lg p-6">
        <h3 className="font-semibold text-slate-100 mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4" />
          Processing Health
        </h3>

        <div className="space-y-3">
          <HealthIndicator
            label="Listing Validator"
            status="active"
            detail="Filtering false positives from ingestion"
          />
          <HealthIndicator
            label="Spec Parser"
            status="active"
            detail="Extracting component specs from titles"
          />
          <HealthIndicator
            label="Classification Engine"
            status="active"
            detail="Scoring and ranking listings"
          />
          <HealthIndicator
            label="Resale Estimator"
            status="active"
            detail="Calculating profit estimates"
          />
        </div>
      </div>

      {/* Quality Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <QualityCard
          title="Validation Pipeline"
          items={[
            { label: "Pass Rate", value: `${(100 - catalogue.false_positive_rate).toFixed(1)}%` },
            { label: "Reject Rate", value: `${catalogue.false_positive_rate.toFixed(1)}%` },
            { label: "Main Issue", value: "Game/software matches" },
          ]}
        />
        <QualityCard
          title="Catalogue Distribution"
          items={[
            { label: "eBay Ratio", value: sorted[0] ? `${(sorted[0].total_listings / catalogue.total_listings * 100).toFixed(0)}%` : "N/A" },
            { label: "Secondary Sources", value: `${catalogue.vendors_active - 1}` },
            { label: "Backup Vendors", value: sorted.filter(v => v.total_listings < 100).length.toString() },
          ]}
        />
      </div>

      {/* Latest Update */}
      <div className="text-xs text-slate-500 text-right">
        Last updated: {catalogue.last_updated}
      </div>
    </div>
  );
}

function AnalyticsCard({
  label,
  value,
  subtext,
  icon,
  color,
}: {
  label: string;
  value: number | string;
  subtext?: string;
  icon: string;
  color: "cyan" | "emerald" | "yellow" | "red";
}) {
  const colors = {
    cyan: "bg-cyan-400/10 border-cyan-400/30",
    emerald: "bg-emerald-400/10 border-emerald-400/30",
    yellow: "bg-yellow-400/10 border-yellow-400/30",
    red: "bg-red-400/10 border-red-400/30",
  };

  return (
    <div className={cn("p-4 rounded-lg border", colors[color])}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs text-slate-500 mb-2">{label}</div>
          <div className="text-2xl font-bold text-slate-100">{value}</div>
          {subtext && <div className="text-xs text-slate-400 mt-1">{subtext}</div>}
        </div>
        <div className="text-3xl">{icon}</div>
      </div>
    </div>
  );
}

function VendorCard({ vendor }: { vendor: VendorStats }) {
  const gemPercentage = (vendor.gems / vendor.total_listings) * 100;

  return (
    <div className="p-4 bg-[#0a0f1a] rounded border border-[#1e2d45] hover:border-[#00dc82]/30 transition">
      <div className="flex items-start justify-between gap-4">
        {/* Left side */}
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-slate-100 mb-2">{vendor.source_name}</div>
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <div className="text-xs text-slate-600">Listings</div>
              <div className="text-base font-semibold text-slate-200">
                {vendor.total_listings}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-600">Gems</div>
              <div className="text-base font-semibold text-emerald-400">{vendor.gems}</div>
            </div>
            <div>
              <div className="text-xs text-slate-600">Rate</div>
              <div className="text-base font-semibold text-yellow-400">
                {vendor.gem_rate.toFixed(1)}%
              </div>
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="flex-1 flex flex-col gap-2">
          <div className="h-2 bg-[#1e2d45] rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-400 to-cyan-400"
              style={{ width: `${Math.min(gemPercentage * 4, 100)}%` }}
            />
          </div>
          <div className="text-xs text-slate-500 text-right">
            {vendor.success_rate.toFixed(0)}% success
          </div>
        </div>
      </div>
    </div>
  );
}

function SortButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2 py-1 rounded text-xs font-medium transition",
        active
          ? "bg-[#00dc82] text-[#0a0f1a]"
          : "bg-[#1e2d45] text-slate-400 hover:text-slate-200"
      )}
    >
      {label}
    </button>
  );
}

function StatSummary({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="p-3 bg-[#0a0f1a] rounded border border-[#1e2d45]">
      <div className="text-xs text-slate-600 mb-1">{label}</div>
      <div className="text-xl font-bold text-slate-200">{value}</div>
    </div>
  );
}

function TopPerformerCard({
  title,
  vendor,
  icon,
  metric,
  unit,
}: {
  title: string;
  vendor: VendorStats;
  icon: string;
  metric: keyof VendorStats;
  unit?: string;
}) {
  return (
    <div className="p-4 bg-[#0d1320] border border-[#1e2d45] rounded-lg">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm text-slate-500 mb-2">{title}</div>
          <div className="text-3xl font-bold text-slate-100 flex items-center gap-1">
            {vendor[metric]}
            {unit}
          </div>
          <div className="text-xs text-slate-400 mt-2">{vendor.source_name}</div>
        </div>
        <div className="text-3xl">{icon}</div>
      </div>
    </div>
  );
}

function HealthIndicator({
  label,
  status,
  detail,
}: {
  label: string;
  status: "active" | "warning" | "error";
  detail: string;
}) {
  const statusColor = {
    active: "text-emerald-400",
    warning: "text-yellow-400",
    error: "text-red-400",
  };

  const statusIcon = {
    active: <CheckCircle2 className="w-4 h-4" />,
    warning: <AlertCircle className="w-4 h-4" />,
    error: <AlertCircle className="w-4 h-4" />,
  };

  return (
    <div className="flex items-start gap-3 p-3 bg-[#0a0f1a] rounded border border-[#1e2d45]">
      <div className={cn("flex-shrink-0 mt-0.5", statusColor[status])}>
        {statusIcon[status]}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-slate-200">{label}</div>
        <div className="text-sm text-slate-500 mt-0.5">{detail}</div>
      </div>
    </div>
  );
}

function QualityCard({
  title,
  items,
}: {
  title: string;
  items: Array<{ label: string; value: string }>;
}) {
  return (
    <div className="p-4 bg-[#0d1320] border border-[#1e2d45] rounded-lg">
      <h4 className="font-semibold text-slate-100 mb-3">{title}</h4>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.label} className="flex justify-between items-center text-sm">
            <span className="text-slate-500">{item.label}</span>
            <span className="font-semibold text-slate-200">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
