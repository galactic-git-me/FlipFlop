"use client";

import { useEffect, useState } from "react";
import { Check, X, Clock, Package, Image, Sparkles, DollarSign, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/utils";
import { readJsonResponse } from "@/lib/read-json-response";
import { Build3DViewer } from "@/components/builds/Build3DViewer";

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



function playbookMemoryGen(item: ApprovalItem): "DDR4" | "DDR5" | "LPDDR5X" | null {
  const comps = item.payload?.core_components;
  if (!Array.isArray(comps)) return null;
  const text = comps
    .filter((c) => {
      const cat = String((c as { category?: string })?.category || "").toLowerCase();
      return cat === "memory" || cat === "ram";
    })
    .map((c) => String((c as { title?: string; sku?: string })?.title || (c as { sku?: string })?.sku || ""))
    .join(" ");
  if (/LPDDR5X/i.test(text)) return "LPDDR5X";
  if (/DDR5/i.test(text)) return "DDR5";
  if (/DDR4/i.test(text)) return "DDR4";
  return null;
}


const SHIP_BY_CUSTOMER_TYPE: Record<string, string> = {
  "Great-value Gaming": "Reliant",
  "High-performance Gaming": "Defiant",
  "Student Hybrid": "Voyager",
  "Business & Office": "Excelsior",
  "Content Creation": "Galaxy",
  "AI Workstation": "Enterprise",
  "Software Development": "Titan",
  "Family & Home": "Stargazer",
};

function playbookPublicName(item: ApprovalItem): string | null {
  const fromPayload =
    (typeof item.payload?.display_name === "string" && item.payload.display_name) ||
    (typeof item.payload?.public_name === "string" && item.payload.public_name) ||
    null;
  if (fromPayload) return fromPayload;

  const ship =
    (typeof item.payload?.ship_name === "string" && item.payload.ship_name) ||
    SHIP_BY_CUSTOMER_TYPE[String(item.payload?.customer_type || "")] ||
    null;
  if (!ship) return null;

  const tier = String(item.payload?.budget_tier || "");
  if (tier === "Mid-range") return `${ship} Pro`;
  if (tier === "High-end") return `${ship} Ultra`;
  return ship; // Budget: no Base suffix
}

function playbookCost(item: ApprovalItem): number | null {
  if (typeof item.total_cost_gbp === "number") return item.total_cost_gbp;
  const comps = item.payload?.core_components;
  if (Array.isArray(comps)) {
    const sum = comps.reduce((acc: number, c: unknown) => {
      const cost = (c as { cost_gbp?: number })?.cost_gbp;
      return acc + (typeof cost === "number" ? cost : 0);
    }, 0);
    return sum > 0 ? sum : null;
  }
  return null;
}

function PlaybookProfitMatrix({ items }: { items: ApprovalItem[] }) {
  const playbooks = items.filter((i) => i.approval_type === "playbook");
  if (playbooks.length === 0) return null;

  const pricingByPlaybook = new Map<string, ApprovalItem>();
  for (const item of items) {
    if (item.approval_type !== "pricing") continue;
    const key = String(item.playbook_id || item.payload?.target_id || "");
    if (!key) continue;
    const prev = pricingByPlaybook.get(key);
    if (!prev || item.id > prev.id) pricingByPlaybook.set(key, item);
  }

  const tiers = ["Budget", "Mid-range", "High-end"] as const;
  const byType = new Map<string, ApprovalItem[]>();
  for (const item of playbooks) {
    const ct = String(item.payload?.customer_type || "Other");
    if (!byType.has(ct)) byType.set(ct, []);
    byType.get(ct)!.push(item);
  }

  const types = Array.from(byType.keys()).sort();

  return (
    <Card className="mb-6 bg-slate-900/60 border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-white text-lg">Playbook profit matrix</CardTitle>
        <p className="text-sm text-slate-400">
          Rows = customer type, columns = budget tier. Joins BuildBot playbooks with PricingBot proposals (provisional sells ok).
        </p>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left text-slate-400 border-b border-slate-700">
              <th className="py-2 pr-3 font-medium">Customer type</th>
              {tiers.map((tier) => (
                <th key={tier} className="py-2 px-2 font-medium min-w-[9rem]">
                  {tier}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {types.map((ct) => {
              const row = byType.get(ct) || [];
              return (
                <tr key={ct} className="border-b border-slate-800 align-top">
                  <td className="py-3 pr-3 text-white font-medium whitespace-nowrap">{ct}</td>
                  {tiers.map((tier) => {
                    const item = row.find((i) => String(i.payload?.budget_tier) === tier);
                    if (!item) {
                      return (
                        <td key={tier} className="py-3 px-2 text-slate-600">
                          —
                        </td>
                      );
                    }
                    const pricing = item.playbook_id
                      ? pricingByPlaybook.get(item.playbook_id)
                      : undefined;
                    const cost =
                      typeof pricing?.total_cost_gbp === "number"
                        ? pricing.total_cost_gbp
                        : playbookCost(item);
                    const sell =
                      typeof pricing?.sell_price_gbp === "number"
                        ? pricing.sell_price_gbp
                        : typeof item.sell_price_gbp === "number"
                          ? item.sell_price_gbp
                          : null;
                    const profit = sell != null && cost != null ? sell - cost : null;
                    const margin =
                      typeof pricing?.est_margin_pct === "number"
                        ? pricing.est_margin_pct
                        : typeof item.est_margin_pct === "number"
                          ? item.est_margin_pct
                          : profit != null && sell
                            ? (profit / sell) * 100
                            : null;
                    return (
                      <td key={tier} className="py-3 px-2">
                        <div className="rounded-md border border-slate-700 bg-slate-950/50 p-2 space-y-0.5">
                          <div className="text-xs font-semibold text-white">{playbookPublicName(item) || item.playbook_id}</div>
                          <div className="text-[10px] text-slate-500 font-mono">{item.playbook_id}</div>
                          {playbookMemoryGen(item) && (
                            <div className="text-[10px] font-semibold text-violet-300">{playbookMemoryGen(item)}</div>
                          )}
                          <div className="text-orange-300">
                            Cost {cost != null ? formatCurrency(cost) : "—"}
                          </div>
                          <div className="text-green-400">
                            Sell {sell != null ? formatCurrency(sell) : "—"}
                          </div>
                          <div className={profit != null ? "text-cyan-300 font-semibold" : "text-slate-500"}>
                            Profit {profit != null ? formatCurrency(profit) : "awaiting price"}
                            {margin != null ? ` (${margin.toFixed(0)}%)` : ""}
                          </div>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}


export default function ApprovalsPage() {
  const [summary, setSummary] = useState<ApprovalSummary | null>(null);
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkProcessing, setBulkProcessing] = useState(false);

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
        ? `${API_BASE}/api/bot-approvals/pending?approval_type=${selectedType}&limit=200`
        : `${API_BASE}/api/bot-approvals/pending?limit=200`;
      const response = await fetch(url);
      const data = await readJsonResponse(response);
      setItems(data);
      setSelectedIds([]);
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


  function toggleSelected(id: number) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  function toggleSelectAll() {
    if (selectedIds.length === items.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(items.map((i) => i.id));
    }
  }

  async function handleBulkDecision(action: "approve" | "reject") {
    if (selectedIds.length === 0) return;
    let reason: string | undefined;
    if (action === "reject") {
      const prompted = prompt(`Rejection reason for ${selectedIds.length} item(s) (optional):`);
      if (prompted === null) return;
      reason = prompted || undefined;
    } else if (
      !confirm(`Approve ${selectedIds.length} selected item(s)?`)
    ) {
      return;
    }

    setBulkProcessing(true);
    try {
      for (const id of selectedIds) {
        setProcessingId(id);
        const response = await fetch(`${API_BASE}/api/bot-approvals/${id}/decision`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, rejection_reason: reason }),
        });
        if (!response.ok) {
          const error = await response.json().catch(() => ({}));
          alert(`Failed to ${action} #${id}: ${error.detail || "Unknown error"}`);
          break;
        }
      }
      await loadSummary();
      await loadPendingItems();
    } catch (error) {
      console.error(`Bulk ${action} failed:`, error);
      alert(`Bulk ${action} failed: ${error}`);
    } finally {
      setProcessingId(null);
      setBulkProcessing(false);
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

        {items.length > 0 && (
          <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-slate-700 bg-slate-900/60 px-4 py-3">
            <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-600 bg-slate-950"
                checked={items.length > 0 && selectedIds.length === items.length}
                onChange={toggleSelectAll}
                disabled={bulkProcessing || loading}
              />
              Select all ({items.length})
            </label>
            <span className="text-xs text-slate-500">{selectedIds.length} selected</span>
            <div className="ml-auto flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={() => handleBulkDecision("approve")}
                disabled={selectedIds.length === 0 || bulkProcessing}
                className="bg-green-600 hover:bg-green-700 text-white"
              >
                <Check className="h-4 w-4 mr-1" />
                Approve ({selectedIds.length})
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleBulkDecision("reject")}
                disabled={selectedIds.length === 0 || bulkProcessing}
                className="border-red-500/50 text-red-400 hover:bg-red-500/10"
              >
                <X className="h-4 w-4 mr-1" />
                Reject ({selectedIds.length})
              </Button>
            </div>
          </div>
        )}

        <div className="space-y-4">
          {(!selectedType || selectedType === "playbook") && (
          <PlaybookProfitMatrix items={items} />
        )}

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
                processing={processingId === item.id || bulkProcessing}
                selected={selectedIds.includes(item.id)}
                onToggleSelect={() => toggleSelected(item.id)}
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
  selected,
  onToggleSelect,
}: {
  item: ApprovalItem;
  onDecision: (id: number, action: "approve" | "reject", reason?: string) => Promise<void>;
  processing: boolean;
  selected: boolean;
  onToggleSelect: () => void;
}) {
  const Icon = typeIcons[item.approval_type] || AlertCircle;

  return (
    <Card className={`bg-slate-900/70 border-slate-700 ${selected ? "border-cyan-500/70 ring-1 ring-cyan-500/30" : ""}`}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-600 bg-slate-950 mt-1"
              checked={selected}
              onChange={onToggleSelect}
              disabled={processing}
              aria-label={`Select approval ${item.id}`}
            />
            <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30">
              <Icon className="h-5 w-5 text-cyan-400" />
            </div>
            <div>
              <CardTitle className="text-white text-lg">
                {item.approval_type === "playbook" && playbookPublicName(item)
                  ? playbookPublicName(item)
                  : typeLabels[item.approval_type]}
              </CardTitle>
              <div className="text-sm text-slate-400 mt-1">
                {item.approval_type === "playbook" && playbookPublicName(item) ? (
                  <span>{typeLabels[item.approval_type]} · </span>
                ) : null}
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

          {(item.approval_type === "playbook" || item.approval_type === "prebuilt") && (
            <div className="flex flex-wrap gap-2">
              {item.payload?.customer_type ? (
                <span className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-2.5 py-0.5 text-xs text-cyan-200">
                  Customer: {String(item.payload.customer_type)}
                </span>
              ) : null}
              {item.payload?.budget_tier ? (
                <span className="rounded-full border border-orange-500/40 bg-orange-500/10 px-2.5 py-0.5 text-xs text-orange-200">
                  Budget: {String(item.payload.budget_tier)}
                </span>
              ) : null}
              {playbookMemoryGen(item) ? (
                <span className="rounded-full border border-violet-500/40 bg-violet-500/10 px-2.5 py-0.5 text-xs text-violet-200">
                  Memory: {playbookMemoryGen(item)}
                </span>
              ) : null}
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
              src={url?.startsWith("http") ? `/api/proxy-image?url=${encodeURIComponent(url)}` : url}
              alt={`Photo ${idx + 1}`}
              referrerPolicy="no-referrer"
              className="w-full h-32 object-cover rounded border border-slate-700 bg-slate-900"
            />
          ))}
        </div>
      </div>
    );
  }

  if (type === "model_3d") {
    const glbUrl = typeof payload.glb_url === "string" ? payload.glb_url : null;
    return (
      <div className="space-y-3">
        {glbUrl ? (
          <Build3DViewer url={glbUrl} />
        ) : (
          <div className="text-sm text-amber-400">No GLB URL on this submission</div>
        )}
        {glbUrl && (
          <div>
            <span className="text-slate-400 text-sm">GLB:</span>{" "}
            <a
              href={glbUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-cyan-400 hover:underline font-mono text-sm break-all"
            >
              {glbUrl}
            </a>
          </div>
        )}
        {payload.preview_image_url && (
          <img
            src={
              String(payload.preview_image_url).startsWith("http")
                ? `/api/proxy-image?url=${encodeURIComponent(String(payload.preview_image_url))}`
                : String(payload.preview_image_url)
            }
            alt="Preview"
            referrerPolicy="no-referrer"
            className="w-64 h-64 object-cover rounded border border-slate-700 bg-slate-900"
          />
        )}
        {payload.poly_count ? (
          <div className="text-sm text-slate-400">Poly count: {String(payload.poly_count)}</div>
        ) : null}
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
