"use client";

import { useEffect, useState } from "react";
import { BarChart3, Search, Loader2, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

// Playbook rows 16, 37, 38 — cross-build, store-wide utilities, not scoped
// to any single build's page (see docs/build-details-automation-plan.md).

type Summary = {
  window_days: number;
  sold_count: number;
  active_count: number;
  total_revenue: number;
  total_profit: number;
  avg_margin_pct: number;
  avg_days_to_sell: number;
  sell_through_rate: number | null;
};

type SellerStandards = { available: boolean; note: string | null; metrics: unknown };

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-1">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{label}</p>
      <p className="text-2xl font-bold text-slate-100 font-mono">{value}</p>
      {sub && <p className="text-xs text-slate-600">{sub}</p>}
    </div>
  );
}

export default function PerformancePage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [standards, setStandards] = useState<SellerStandards | null>(null);
  const [loading, setLoading] = useState(true);

  const [keywordQuery, setKeywordQuery] = useState("");
  const [keywordResult, setKeywordResult] = useState<{
    sample_titles: string[];
    frequent_tokens: [string, number][];
    note: string;
  } | null>(null);
  const [searchingKeywords, setSearchingKeywords] = useState(false);

  useEffect(() => {
    Promise.all([api.adminPerformance.summary(90), api.adminPerformance.sellerStandards()])
      .then(([s, st]) => {
        setSummary(s);
        setStandards(st);
      })
      .finally(() => setLoading(false));
  }, []);

  async function runKeywordSearch() {
    if (!keywordQuery.trim()) return;
    setSearchingKeywords(true);
    try {
      const result = await api.adminPerformance.keywordResearch(keywordQuery.trim());
      setKeywordResult(result);
    } finally {
      setSearchingKeywords(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading performance dashboard…
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-slate-400" /> Performance &amp; Margin
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Real revenue, margin, and sell-through numbers (row 37) plus eBay&apos;s 5 seller-performance
          metrics (row 16) — cross-build store metrics, not per-listing vanity counts.
        </p>
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatTile label={`Revenue (${summary.window_days}d)`} value={`£${summary.total_revenue.toFixed(0)}`} />
          <StatTile label="Profit" value={`£${summary.total_profit.toFixed(0)}`} />
          <StatTile label="Avg margin" value={`${summary.avg_margin_pct.toFixed(1)}%`} />
          <StatTile
            label="Sell-through"
            value={summary.sell_through_rate != null ? `${(summary.sell_through_rate * 100).toFixed(0)}%` : "—"}
            sub={`${summary.sold_count} sold / ${summary.active_count} active`}
          />
        </div>
      )}

      <Card>
        <CardHeader><CardTitle>Seller-performance metrics (row 16)</CardTitle></CardHeader>
        <CardContent className="pt-0">
          {standards?.available ? (
            <pre className="text-xs text-slate-300 bg-slate-900/50 rounded-lg p-3 overflow-x-auto">
              {JSON.stringify(standards.metrics, null, 2)}
            </pre>
          ) : (
            <div className="flex items-start gap-2 text-sm text-amber-400 bg-amber-500/5 border border-amber-500/30 rounded-lg p-3">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              {standards?.note ?? "Not available."}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Search className="w-4 h-4" /> Title keyword research (row 38)</CardTitle></CardHeader>
        <CardContent className="pt-0 space-y-3">
          <div className="flex gap-2">
            <input
              value={keywordQuery}
              onChange={(e) => setKeywordQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runKeywordSearch()}
              placeholder="e.g. RTX 4070 gaming pc"
              className="flex-1 px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-200"
            />
            <button
              onClick={runKeywordSearch}
              disabled={searchingKeywords || !keywordQuery.trim()}
              className="px-3 py-2 text-xs bg-[#00dc82] text-[#04120d] rounded-lg font-semibold disabled:opacity-40"
            >
              {searchingKeywords ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Search"}
            </button>
          </div>
          {keywordResult && (
            <div className="space-y-2">
              <p className="text-xs text-slate-600">{keywordResult.note}</p>
              {keywordResult.sample_titles.length > 0 && (
                <div>
                  <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Sample real titles</p>
                  {keywordResult.sample_titles.map((t, i) => (
                    <p key={i} className="text-sm text-slate-300">{t}</p>
                  ))}
                </div>
              )}
              {keywordResult.frequent_tokens.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {keywordResult.frequent_tokens.map(([token, count]) => (
                    <span key={token} className="text-xs px-2 py-0.5 bg-slate-800 rounded text-slate-300">
                      {token} <span className="text-slate-600">×{count}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
