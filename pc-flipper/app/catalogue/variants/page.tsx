"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface Variant {
  id: number;
  listing_title: string;
  slot_type: string;
  playbook_id: number;
  status: string;
  tier: string;
  display_price: number;
  gem_score: number;
  consecutive_misses: number;
  last_seen_at: string;
  reviewed_at: string | null;
  reject_reason: string | null;
}

const STATUS_COLOURS: Record<string, string> = {
  active: "text-emerald-400",
  pending_review: "text-amber-400",
  hidden: "text-muted-foreground",
  rejected: "text-red-400",
};

const ALL_STATUSES = ["", "active", "pending_review", "hidden", "rejected"];

export default function CatalogueVariantsPage() {
  const [variants, setVariants] = useState<Variant[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      const data = await api.catalogue.variants(params);
      setVariants(data as Variant[]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const toggle = async (v: Variant) => {
    setBusy(v.id);
    try {
      await api.catalogue.toggleVariantStatus(v.id);
      await load();
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Component Variants</h1>
        <div className="flex items-center gap-2">
          <select
            className="text-sm bg-background border rounded px-2 py-1.5"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            {ALL_STATUSES.map(s => (
              <option key={s} value={s}>{s || "All statuses"}</option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/30">
            <tr>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground">Component</th>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground">Slot</th>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground">Status</th>
              <th className="text-right px-3 py-2 font-medium text-muted-foreground">Price</th>
              <th className="text-right px-3 py-2 font-medium text-muted-foreground">Score</th>
              <th className="text-right px-3 py-2 font-medium text-muted-foreground">Misses</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {variants.map(v => (
              <tr key={v.id} className="border-b last:border-0 hover:bg-muted/10">
                <td className="px-3 py-2.5 max-w-xs truncate">{v.listing_title}</td>
                <td className="px-3 py-2.5 uppercase text-xs font-mono">{v.slot_type}</td>
                <td className={`px-3 py-2.5 text-xs font-medium ${STATUS_COLOURS[v.status] ?? ""}`}>
                  {v.status}
                </td>
                <td className="px-3 py-2.5 text-right">£{v.display_price}</td>
                <td className="px-3 py-2.5 text-right text-emerald-400 font-bold">
                  {v.gem_score.toFixed(0)}
                </td>
                <td className={`px-3 py-2.5 text-right font-mono ${v.consecutive_misses >= 1 ? "text-amber-400" : ""}`}>
                  {v.consecutive_misses}
                </td>
                <td className="px-3 py-2.5 text-right">
                  {(v.status === "active" || v.status === "hidden") && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busy === v.id}
                      onClick={() => toggle(v)}
                    >
                      {v.status === "active"
                        ? <EyeOff className="w-3.5 h-3.5" />
                        : <Eye className="w-3.5 h-3.5" />}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && variants.length === 0 && (
          <p className="text-center text-muted-foreground text-sm py-10">No variants found</p>
        )}
      </div>
    </div>
  );
}
