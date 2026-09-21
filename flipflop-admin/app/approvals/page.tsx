"use client";

import { useEffect, useState } from "react";
import { Check, X, Clock, Package, Image, Sparkles, DollarSign, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/utils";
import { readJsonResponse } from "@/lib/read-json-response";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:4311").replace(/\/$/, "");

interface ApprovalItem {
  id: number;
  approval_type: string;
  status: string;
  subject_sku?: string;
  subject_category?: string;
  playbook_id?: string;
  payload: Record<string, unknown>;
  sell_price_gbp?: number;
  total_cost_gbp?: number;
  est_margin_pct?: number;
  submitted_by?: string;
  submitted_at: string;
  reviewed_by?: string;
  reviewed_at?: string;
  rejection_reason?: string;
  notes?: string;
}

interface ApprovalSummary {
  total_pending: number;
  pending_photo_packs: number;
  pending_models_3d: number;
  pending_playbooks: number;
  pending_prebuilts: number;
  pending_pricing: number;
}

const typeLabels: Record<string, string> = {
  photo_pack: "Photo Pack",
  model_3d: "3D Model",
  playbook: "Playbook",
  prebuilt: "Pre-built",
  pricing: "Pricing",
};

const typeIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  photo_pack: Image,
  model_3d: Sparkles,
  playbook: Package,
  prebuilt: Package,
  pricing: DollarSign,
};

export default function ApprovalsPage() {
  const [summary, setSummary] = useState<ApprovalSummary | null>(null);
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [processingId, setProcessingId] = useState<number | null>(null);

  useEffect(() => {
    loadSummary();
    loadPendingItems();
  }, [selectedType]);

  async function loadSummary() {
    try {
      const response = await fetch(`${API_BASE}/api/bot-approvals/summary`);
      const data = await readJsonResponse(response);
      setSummary(data);
    } catch (error) {
      console.error("Failed to load summary:", error);
    }
  }

  async function loadPendingItems() {
    setLoading(true);
    try {
      const url = selectedType
        ? `${API_BASE}/api/bot-approvals/pending?approval_type=${selectedType}`
        : `${API_BASE}/api/bot-approvals/pending`;
      const response = await fetch(url);
      const data = await readJsonResponse(response);
      setItems(data);
    } catch (error) {
      console.error("Failed to load items:", error);
    } finally {
      setLoading(false);
    }
  }

  async function handleDecision(itemId: number, action: "approve" | "reject", reason?: string) {
    setProcessingId(itemId);
    try {
      const response = await fetch(`${API_BASE}/api/bot-approvals/${itemId}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, rejection_reason: reason }),
      });

      if (response.ok) {
        await loadSummary();
        await loadPendingItems();
      } else {
        const error = await response.json();
        alert(`Failed to ${action}: ${error.detail || "Unknown error"}`);
      }
    } catch (error) {
      console.error(`Failed to ${action}:`, error);
      alert(`Failed to ${action}: ${error}`);
    } finally {
      setProcessingId(null);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400 mb-2">
            Bot Approvals
          </h1>
          <p className="text-slate-400">Review and approve bot-submitted work</p>
        </div>

        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
            <Card className="bg-slate-900/50 border-slate-700">
              <CardContent className="p-4">
                <div className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-orange-400" />
                  <div>
                    <div className="text-2xl font-bold text-white">{summary.total_pending}</div>
                    <div className="text-xs text-slate-400">Total Pending</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {Object.entries({
              photo_pack: summary.pending_photo_packs,
              model_3d: summary.pending_models_3d,
              playbook: summary.pending_playbooks,
              prebuilt: summary.pending_prebuilts,
              pricing: summary.pending_pricing,
            }).map(([type, count]) => {
              const Icon = typeIcons[type];
              return (
                <Card
                  key={type}
                  className={`bg-slate-900/50 border-slate-700 cursor-pointer transition hover:border-cyan-500/50 ${
                    selectedType === type ? "border-cyan-500" : ""
                  }`}
                  onClick={() => setSelectedType(selectedType === type ? null : type)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2">
                      <Icon className="h-5 w-5 text-cyan-400" />
                      <div>
                        <div className="text-2xl font-bold text-white">{count}</div>
                        <div className="text-xs text-slate-400">{typeLabels[type]}</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        {selectedType && (
          <div className="mb-4">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedType(null)}
              className="border-slate-700 text-slate-300 hover:border-cyan-500"
            >
              Clear Filter
            </Button>
          </div>
        )}

        <div className="space-y-4">
          {loading ? (
            <Card className="bg-slate-900/50 border-slate-700">
              <CardContent className="p-8 text-center text-slate-400">Loading...</CardContent>
            </Card>
          ) : items.length === 0 ? (
            <Card className="bg-slate-900/50 border-slate-700">
              <CardContent className="p-8 text-center text-slate-400">
                No pending approvals {selectedType && `for ${typeLabels[selectedType]}`}
              </CardContent>
            </Card>
          ) : (
            items.map((item) => (
              <ApprovalCard
                key={item.id}
                item={item}
                onDecision={handleDecision}
                processing={processingId === item.id}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function ApprovalCard({
  item,
  onDecision,
  processing,
}: {
  item: ApprovalItem;
  onDecision: (id: number, action: "approve" | "reject", reason?: string) => Promise<void>;
  processing: boolean;
}) {
  const Icon = typeIcons[item.approval_type] || AlertCircle;

  return (
    <Card className="bg-slate-900/70 border-slate-700">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30">
              <Icon className="h-5 w-5 text-cyan-400" />
            </div>
            <div>
              <CardTitle className="text-white text-lg">{typeLabels[item.approval_type]}</CardTitle>
              <div className="text-sm text-slate-400 mt-1">
                {item.submitted_by} • {new Date(item.submitted_at).toLocaleString()}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => onDecision(item.id, "approve")}
              disabled={processing}
              className="bg-green-600 hover:bg-green-700 text-white"
            >
              <Check className="h-4 w-4 mr-1" />
              Approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                const reason = prompt("Rejection reason (optional):");
                if (reason !== null) {
                  onDecision(item.id, "reject", reason || undefined);
                }
              }}
              disabled={processing}
              className="border-red-500/50 text-red-400 hover:bg-red-500/10"
            >
              <X className="h-4 w-4 mr-1" />
              Reject
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-3">
          {item.subject_sku && (
            <div>
              <span className="text-slate-400 text-sm">SKU:</span>{" "}
              <span className="text-white font-mono">{item.subject_sku}</span>
              {item.subject_category && (
                <span className="ml-2 text-slate-400 text-sm">({item.subject_category})</span>
              )}
            </div>
          )}

          {item.playbook_id && (
            <div>
              <span className="text-slate-400 text-sm">Playbook ID:</span>{" "}
              <span className="text-white font-mono">{item.playbook_id}</span>
            </div>
          )}

          {(item.sell_price_gbp != null || item.total_cost_gbp != null || typeof item.est_margin_pct === "number") && (
            <div className="grid grid-cols-3 gap-4 p-3 rounded-lg bg-slate-800/50 border border-slate-700">
              {item.sell_price_gbp && (
                <div>
                  <div className="text-xs text-slate-400">Sell Price</div>
                  <div className="text-lg font-bold text-green-400">
                    {formatCurrency(item.sell_price_gbp)}
                  </div>
                </div>
              )}
              {item.total_cost_gbp && (
                <div>
                  <div className="text-xs text-slate-400">Total Cost</div>
                  <div className="text-lg font-bold text-orange-400">
                    {formatCurrency(item.total_cost_gbp)}
                  </div>
                </div>
              )}
              {typeof item.est_margin_pct === "number" && (
                <div>
                  <div className="text-xs text-slate-400">Margin</div>
                  <div className="text-lg font-bold text-cyan-400">
                    {item.est_margin_pct.toFixed(1)}%
                  </div>
                </div>
              )}
            </div>
          )}

          <ApprovalPayloadPreview type={item.approval_type} payload={item.payload} />
        </div>
      </CardContent>
    </Card>
  );
}

function ApprovalPayloadPreview({ type, payload }: { type: string; payload: Record<string, unknown> }) {
  if (type === "photo_pack") {
    const images = (payload.image_urls || []) as string[];
    return (
      <div>
        <div className="text-sm text-slate-400 mb-2">Reference Photos ({images.length}):</div>
        <div className="grid grid-cols-4 gap-2">
          {images.map((url, idx) => (
            <img
              key={idx}
              src={url}
              alt={`Photo ${idx + 1}`}
              className="w-full h-32 object-cover rounded border border-slate-700"
            />
          ))}
        </div>
      </div>
    );
  }

  if (type === "model_3d") {
    return (
      <div className="space-y-2">
        {payload.glb_url && (
          <div>
            <span className="text-slate-400 text-sm">GLB:</span>{" "}
            <a
              href={payload.glb_url as string}
              target="_blank"
              rel="noopener noreferrer"
              className="text-cyan-400 hover:underline font-mono text-sm"
            >
              {payload.glb_url as string}
            </a>
          </div>
        )}
        {payload.preview_image_url && (
          <img
            src={payload.preview_image_url as string}
            alt="Preview"
            className="w-64 h-64 object-cover rounded border border-slate-700"
          />
        )}
        {payload.poly_count && (
          <div className="text-sm text-slate-400">Poly count: {payload.poly_count}</div>
        )}
      </div>
    );
  }

  if (type === "playbook" || type === "prebuilt") {
    const components = (payload.core_components || payload.components || []) as Array<{
      sku: string;
      category: string;
      cost_gbp: number;
    }>;
    return (
      <div>
        <div className="text-sm text-slate-400 mb-2">Components ({components.length}):</div>
        <div className="space-y-1 max-h-64 overflow-y-auto">
          {components.map((comp, idx) => (
            <div key={idx} className="flex justify-between text-sm p-2 rounded bg-slate-800/30">
              <span className="text-white">
                {comp.category}: {comp.sku}
              </span>
              <span className="text-green-400">{formatCurrency(comp.cost_gbp)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (type === "pricing") {
    return (
      <div className="space-y-2 text-sm">
        {payload.pricing_rationale && (
          <div>
            <span className="text-slate-400">Rationale:</span>{" "}
            <span className="text-white">{payload.pricing_rationale as string}</span>
          </div>
        )}
        {payload.delivery_buffer_gbp && (
          <div>
            <span className="text-slate-400">Delivery Buffer:</span>{" "}
            <span className="text-white">{formatCurrency(payload.delivery_buffer_gbp as number)}</span>
          </div>
        )}
      </div>
    );
  }

  return null;
}
