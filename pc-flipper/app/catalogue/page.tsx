// pc-flipper/app/catalogue/page.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import {
  CheckCircle, XCircle, AlertTriangle, Package, RefreshCw
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface QueueItem {
  id: number;
  listing_title: string;
  listing_price: number;
  gem_score: number;
  slot_type: string;
  playbook_id: number;
  tier: string;
  display_price: number;
  auto_published_at: string;
}

const REJECT_REASONS = [
  "Price too high",
  "Wrong category",
  "Duplicate",
  "Low quality listing",
  "Other",
];

const TIER_COLOURS: Record<string, string> = {
  budget: "text-sky-400",
  mid: "text-amber-400",
  high: "text-emerald-400",
};

export default function CatalogueReviewQueuePage() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState(REJECT_REASONS[0]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.catalogue.reviewQueue();
      setItems(data as QueueItem[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const approve = async (id: number) => {
    setBusy(true);
    await api.catalogue.approve(id);
    setItems(prev => prev.filter(i => i.id !== id));
    setBusy(false);
  };

  const reject = async (id: number) => {
    setBusy(true);
    await api.catalogue.reject(id, rejectReason);
    setItems(prev => prev.filter(i => i.id !== id));
    setRejectingId(null);
    setBusy(false);
  };

  const approveAll = async () => {
    setBusy(true);
    await api.catalogue.approveAll();
    setItems([]);
    setBusy(false);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">Review Queue</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {items.length} variant{items.length !== 1 ? "s" : ""} awaiting approval
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          {items.length > 0 && (
            <Button size="sm" onClick={approveAll} disabled={busy}>
              <CheckCircle className="w-3.5 h-3.5 mr-1.5" />
              Approve All ({items.length})
            </Button>
          )}
        </div>
      </div>

      {loading && (
        <div className="text-center py-12 text-muted-foreground text-sm">Loading…</div>
      )}

      {!loading && items.length === 0 && (
        <div className="text-center py-16">
          <Package className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground text-sm">No variants pending review</p>
        </div>
      )}

      <div className="space-y-2">
        {items.map(item => (
          <div
            key={item.id}
            className="border rounded-lg overflow-hidden bg-card"
          >
            <div className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-3 items-center px-4 py-3">
              <div>
                <p className="font-medium text-sm truncate">{item.listing_title}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {item.slot_type.toUpperCase()} ·{" "}
                  <span className={TIER_COLOURS[item.tier] ?? ""}>
                    {item.tier}
                  </span>{" "}
                  · auto-published {new Date(item.auto_published_at).toLocaleDateString()}
                </p>
              </div>
              <div className="text-right">
                <p className="font-semibold text-sm">£{item.display_price}</p>
                <p className="text-xs text-muted-foreground">display price</p>
              </div>
              <div className="text-center">
                <p className="font-bold text-emerald-400">{item.gem_score.toFixed(0)}</p>
                <p className="text-xs text-muted-foreground">gem score</p>
              </div>
              <Button
                size="sm"
                variant="danger"
                disabled={busy}
                onClick={() => setRejectingId(rejectingId === item.id ? null : item.id)}
              >
                <XCircle className="w-3.5 h-3.5 mr-1" />
                Reject
              </Button>
              <Button
                size="sm"
                className="bg-emerald-500 hover:bg-emerald-600 text-black"
                disabled={busy}
                onClick={() => approve(item.id)}
              >
                <CheckCircle className="w-3.5 h-3.5 mr-1" />
                Approve
              </Button>
            </div>

            {rejectingId === item.id && (
              <div className="border-t px-4 py-3 bg-muted/30 flex items-center gap-3">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                <select
                  className="text-sm bg-background border rounded px-2 py-1"
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                >
                  {REJECT_REASONS.map(r => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
                <Button
                  size="sm"
                  variant="danger"
                  disabled={busy}
                  onClick={() => reject(item.id)}
                >
                  Confirm Reject
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setRejectingId(null)}
                >
                  Cancel
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
