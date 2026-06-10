"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BookOpen, Plus, CheckCircle, XCircle, Clock, ChevronRight,
  TrendingUp, Zap, Target, Search, AlertTriangle, RefreshCw,
  BarChart2, Pencil, Trash2, ChevronDown, ChevronUp, Tag,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  Playbook, PlaybookProposal,
  PLAYBOOK_STATUS_CONFIG, PROPOSAL_ACTION_CONFIG, USE_CASE_CONFIG,
  PlaybookStatus,
} from "@/lib/types";
import { SeasonalityChart } from "@/components/playbooks/SeasonalityChart";
import { ScoreBadges } from "@/components/playbooks/ScoreBadges";
import { IdealBuildPanel } from "@/components/playbooks/IdealBuildPanel";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function relTime(iso: string) {
  const d = new Date(iso);
  const secs = Math.floor((Date.now() - d.getTime()) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

function StatusBadge({ status }: { status: PlaybookStatus }) {
  const cfg = PLAYBOOK_STATUS_CONFIG[status];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full border ${cfg.bg} ${cfg.color}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

// ─── Create / Edit modal ───────────────────────────────────────────────────────

interface PlaybookFormData {
  name: string;
  description: string;
  emoji: string;
  target_use_case: string;
  req_cpu: string;
  req_ram: string;
  req_gpu: boolean;
  req_psu: boolean;
  search_keywords: string;
  price_min: string;
  price_max: string;
  upgrade_required: string;
  upgrade_optional: string;
  target_profit: string;
  target_margin: string;
  flip_structure: string;
  profit_notes: string;
}

const BLANK_FORM: PlaybookFormData = {
  name: "", description: "", emoji: "🖥️", target_use_case: "gaming",
  req_cpu: "i5", req_ram: "8", req_gpu: false, req_psu: true,
  search_keywords: "", price_min: "50", price_max: "300",
  upgrade_required: "", upgrade_optional: "",
  target_profit: "100", target_margin: "40",
  flip_structure: "buy_upgrade_sell", profit_notes: "",
};

function formToPlaybook(f: PlaybookFormData): Record<string, unknown> {
  return {
    name: f.name.trim(),
    description: f.description.trim() || null,
    emoji: f.emoji || "🖥️",
    target_use_case: f.target_use_case,
    requirements: {
      cpu_min_tier: f.req_cpu,
      ram_min_gb: parseInt(f.req_ram) || 8,
      gpu_required: f.req_gpu,
      psu_required: f.req_psu,
    },
    search_strategy: {
      keywords: f.search_keywords.split("\n").map(k => k.trim()).filter(Boolean),
      price_min: parseFloat(f.price_min) || 50,
      price_max: parseFloat(f.price_max) || 300,
      listing_types: ["buy_it_now", "auction"],
    },
    upgrade_strategy: {
      required: f.upgrade_required.split("\n").map(l => l.trim()).filter(Boolean).map(l => {
        const parts = l.split("|").map(s => s.trim());
        return { component: parts[0] || "", target: parts[1] || "", max_cost: parseFloat(parts[2] || "0") };
      }),
      optional: f.upgrade_optional.split("\n").map(l => l.trim()).filter(Boolean).map(l => {
        const parts = l.split("|").map(s => s.trim());
        return { component: parts[0] || "", target: parts[1] || "", max_cost: parseFloat(parts[2] || "0") };
      }),
    },
    profit_strategy: {
      target_profit_gbp: parseFloat(f.target_profit) || 100,
      target_margin_pct: parseFloat(f.target_margin) || 40,
      sell_platform: "eBay",
      flip_structure: f.flip_structure,
      notes: f.profit_notes.trim() || null,
    },
  };
}

function playbookToForm(pb: Playbook): PlaybookFormData {
  const req = pb.requirements || {};
  const ss = pb.search_strategy || {};
  const us = pb.upgrade_strategy || {};
  const ps = pb.profit_strategy || {};
  return {
    name: pb.name,
    description: pb.description || "",
    emoji: pb.emoji || "🖥️",
    target_use_case: pb.target_use_case || "gaming",
    req_cpu: req.cpu_min_tier || "i5",
    req_ram: String(req.ram_min_gb || 8),
    req_gpu: req.gpu_required || false,
    req_psu: req.psu_required !== false,
    search_keywords: (ss.keywords || []).join("\n"),
    price_min: String(ss.price_min || 50),
    price_max: String(ss.price_max || 300),
    upgrade_required: (us.required || []).map((u: { component: string; target: string; max_cost: number }) => `${u.component} | ${u.target} | ${u.max_cost}`).join("\n"),
    upgrade_optional: (us.optional || []).map((u: { component: string; target: string; max_cost: number }) => `${u.component} | ${u.target} | ${u.max_cost}`).join("\n"),
    target_profit: String(ps.target_profit_gbp || 100),
    target_margin: String(ps.target_margin_pct || 40),
    flip_structure: ps.flip_structure || "buy_upgrade_sell",
    profit_notes: ps.notes || "",
  };
}

function PlaybookFormModal({
  open, onClose, onSave, initialData, title,
}: {
  open: boolean;
  onClose: () => void;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  initialData?: PlaybookFormData;
  title: string;
}) {
  const [form, setForm] = useState<PlaybookFormData>(initialData || BLANK_FORM);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    const id = setTimeout(() => setForm(initialData || BLANK_FORM), 0);
    return () => clearTimeout(id);
  }, [open, initialData]);

  const set = (k: keyof PlaybookFormData, v: string | boolean) =>
    setForm(prev => ({ ...prev, [k]: v }));

  if (!open) return null;

  const handleSave = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try { await onSave(formToPlaybook(form)); onClose(); }
    catch { /* ignore */ }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-[#0d1726] border border-[#1e2d45] rounded-2xl shadow-2xl">
        <div className="sticky top-0 bg-[#0d1726] border-b border-[#1e2d45] px-6 py-4 flex items-center justify-between">
          <h2 className="text-slate-100 font-semibold">{title}</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200 text-xl leading-none">✕</button>
        </div>
        <div className="p-6 space-y-5">

          {/* Identity */}
          <section>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">Identity</h3>
            <div className="grid grid-cols-[64px_1fr] gap-3 mb-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Emoji</label>
                <input value={form.emoji} onChange={e => set("emoji", e.target.value)}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-2 py-2 text-xl text-center text-slate-100 focus:border-[#00dc82]/50 focus:outline-none" />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Name *</label>
                <input value={form.name} onChange={e => set("name", e.target.value)}
                  placeholder="e.g. Budget Gaming PC"
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Description</label>
                <textarea value={form.description} onChange={e => set("description", e.target.value)}
                  rows={2} placeholder="What this playbook targets…"
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none resize-none" />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Use Case</label>
                <select value={form.target_use_case} onChange={e => set("target_use_case", e.target.value)}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 focus:border-[#00dc82]/50 focus:outline-none">
                  {Object.entries(USE_CASE_CONFIG).map(([k, v]) => (
                    <option key={k} value={k}>{v.emoji} {v.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          {/* Requirements */}
          <section>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">Hardware Requirements</h3>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Min CPU tier</label>
                <select value={form.req_cpu} onChange={e => set("req_cpu", e.target.value)}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 focus:border-[#00dc82]/50 focus:outline-none">
                  {["i3","i5","i7","i9","Xeon","Ryzen 5","Ryzen 7","Ryzen 9","Threadripper"].map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Min RAM (GB)</label>
                <input type="number" value={form.req_ram} onChange={e => set("req_ram", e.target.value)}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 focus:border-[#00dc82]/50 focus:outline-none" />
              </div>
            </div>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-300">
                <input type="checkbox" checked={form.req_gpu} onChange={e => set("req_gpu", e.target.checked)}
                  className="accent-[#00dc82] w-4 h-4" />
                GPU required
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-300">
                <input type="checkbox" checked={form.req_psu} onChange={e => set("req_psu", e.target.checked)}
                  className="accent-[#00dc82] w-4 h-4" />
                PSU required
              </label>
            </div>
          </section>

          {/* Search */}
          <section>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">Search Strategy</h3>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Price min (£)</label>
                <input type="number" value={form.price_min} onChange={e => set("price_min", e.target.value)}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 focus:border-[#00dc82]/50 focus:outline-none" />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Price max (£)</label>
                <input type="number" value={form.price_max} onChange={e => set("price_max", e.target.value)}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 focus:border-[#00dc82]/50 focus:outline-none" />
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Search keywords (one per line)</label>
              <textarea value={form.search_keywords} onChange={e => set("search_keywords", e.target.value)}
                rows={5} placeholder={"gaming pc no gpu\npc tower no graphics\ni7 desktop"}
                className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none resize-y font-mono" />
            </div>
          </section>

          {/* Upgrades */}
          <section>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-1">Upgrade Strategy</h3>
            <p className="text-xs text-slate-500 mb-3">Format per line: <code className="text-slate-400 bg-white/5 px-1 rounded">Component | Target | MaxCost</code></p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Required upgrades</label>
                <textarea value={form.upgrade_required} onChange={e => set("upgrade_required", e.target.value)}
                  rows={3} placeholder={"GPU | RTX 3060 / RX 6600 | 100"}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none resize-none font-mono" />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Optional upgrades</label>
                <textarea value={form.upgrade_optional} onChange={e => set("upgrade_optional", e.target.value)}
                  rows={3} placeholder={"SSD | 500GB NVMe | 25\nRAM | 16GB DDR4 | 20"}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none resize-none font-mono" />
              </div>
            </div>
          </section>

          {/* Profit */}
          <section>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">Profit Strategy</h3>
            <div className="grid grid-cols-3 gap-3 mb-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Target profit (£)</label>
                <input type="number" value={form.target_profit} onChange={e => set("target_profit", e.target.value)}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 focus:border-[#00dc82]/50 focus:outline-none" />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Target margin (%)</label>
                <input type="number" value={form.target_margin} onChange={e => set("target_margin", e.target.value)}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 focus:border-[#00dc82]/50 focus:outline-none" />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Flip structure</label>
                <select value={form.flip_structure} onChange={e => set("flip_structure", e.target.value)}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 focus:border-[#00dc82]/50 focus:outline-none">
                  <option value="buy_upgrade_sell">Buy → Upgrade → Sell</option>
                  <option value="buy_clean_sell">Buy → Clean → Sell</option>
                  <option value="bulk_lot">Bulk Lot</option>
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Notes</label>
              <textarea value={form.profit_notes} onChange={e => set("profit_notes", e.target.value)}
                rows={2} placeholder="Listing tips, pricing guidance…"
                className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none resize-none" />
            </div>
          </section>

        </div>
        <div className="sticky bottom-0 bg-[#0d1726] border-t border-[#1e2d45] px-6 py-4 flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose} className="text-slate-400">Cancel</Button>
          <Button onClick={handleSave} disabled={saving || !form.name.trim()}
            className="bg-[#00dc82] text-black hover:bg-[#00dc82]/90 font-semibold">
            {saving ? "Saving…" : "Save Playbook"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Proposal card ─────────────────────────────────────────────────────────────

function ProposalCard({
  proposal, onApprove, onReject,
}: {
  proposal: PlaybookProposal;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const actionCfg = PROPOSAL_ACTION_CONFIG[proposal.action];

  return (
    <div className="bg-[#0d1726] border border-[#1e2d45] rounded-xl p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`text-xs font-semibold ${actionCfg.color}`}>{actionCfg.label}</span>
            {proposal.playbook_name && (
              <>
                <ChevronRight className="w-3 h-3 text-slate-600" />
                <span className="text-xs text-slate-300 truncate">{proposal.playbook_name}</span>
              </>
            )}
            {proposal.action === "CREATE" && proposal.proposed_data?.name && (
              <>
                <ChevronRight className="w-3 h-3 text-slate-600" />
                <span className="text-xs text-slate-300">{String(proposal.proposed_data.name)}</span>
              </>
            )}
          </div>
          {proposal.reason && (
            <p className="text-sm text-slate-400 leading-snug">{proposal.reason}</p>
          )}
          {Object.keys(proposal.demand_signals || {}).length > 0 && (
            <div className="flex gap-2 mt-2 flex-wrap">
              {Object.entries(proposal.demand_signals).map(([k, v]) => (
                <span key={k} className="text-xs bg-[#111c2e] border border-[#1e2d45] text-slate-400 px-2 py-0.5 rounded-full">
                  {k}: {String(v)}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-slate-600">{relTime(proposal.proposed_at)}</span>
          {proposal.status === "pending" && (
            <>
              <button onClick={() => onApprove(proposal.id)}
                className="flex items-center gap-1 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs px-2.5 py-1 rounded-lg hover:bg-emerald-500/20 transition-colors">
                <CheckCircle className="w-3 h-3" /> Approve
              </button>
              <button onClick={() => onReject(proposal.id)}
                className="flex items-center gap-1 bg-red-500/10 border border-red-500/30 text-red-400 text-xs px-2.5 py-1 rounded-lg hover:bg-red-500/20 transition-colors">
                <XCircle className="w-3 h-3" /> Reject
              </button>
            </>
          )}
          {proposal.status !== "pending" && (
            <span className={`text-xs font-medium ${proposal.status === "approved" ? "text-emerald-400" : "text-red-400"}`}>
              {proposal.status === "approved" ? "✓ Approved" : "✕ Rejected"}
            </span>
          )}
        </div>
      </div>

      {proposal.action !== "RETIRE" && Object.keys(proposal.proposed_data || {}).length > 0 && (
        <button onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-400 mt-2 transition-colors">
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {expanded ? "Hide" : "Show"} proposed changes
        </button>
      )}

      {expanded && (
        <pre className="mt-2 text-xs text-slate-400 bg-[#080c14] border border-[#1e2d45] rounded-lg p-3 overflow-x-auto max-h-48">
          {JSON.stringify(proposal.proposed_data, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ─── Playbook card ─────────────────────────────────────────────────────────────

function PlaybookCard({
  playbook, onEdit, onDelete, onActivate, onRetire, onRollback,
}: {
  playbook: Playbook;
  onEdit: (pb: Playbook) => void;
  onDelete: (id: number) => void;
  onActivate: (id: number) => void;
  onRetire: (id: number) => void;
  onRollback: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [tab, setTab] = useState<"scores" | "build" | "season">("scores");
  const ss = playbook.search_strategy || {};
  const us = playbook.upgrade_strategy || {};
  const ps = playbook.profit_strategy || {};
  const useCase = USE_CASE_CONFIG[playbook.target_use_case as keyof typeof USE_CASE_CONFIG];

  return (
    <div className="bg-[#0d1726] border border-[#1e2d45] hover:border-[#2a3d5c] rounded-xl transition-colors">
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-2xl flex-shrink-0">{playbook.emoji || "🖥️"}</span>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-slate-100 truncate">{playbook.name}</span>
                <StatusBadge status={playbook.status} />
                {useCase && (
                  <span className="text-xs text-slate-500 bg-[#111c2e] border border-[#1e2d45] px-2 py-0.5 rounded-full">
                    {useCase.emoji} {useCase.label}
                  </span>
                )}
              </div>
              {playbook.description && (
                <p className="text-sm text-slate-500 mt-0.5 leading-snug">{playbook.description}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {playbook.status === "candidate" && (
              <button onClick={() => onActivate(playbook.id)}
                className="text-xs bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-2 py-1 rounded-lg hover:bg-emerald-500/20 transition-colors flex items-center gap-1">
                <Zap className="w-3 h-3" /> Activate
              </button>
            )}
            {playbook.status === "active" && (
              <button onClick={() => onRetire(playbook.id)}
                className="text-xs bg-slate-500/10 border border-slate-500/20 text-slate-500 px-2 py-1 rounded-lg hover:bg-slate-500/20 transition-colors">
                Retire
              </button>
            )}
            {playbook.status === "active" && (
              <button onClick={() => onRollback(playbook.id)}
                className="text-xs bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 px-2 py-1 rounded-lg hover:bg-cyan-500/20 transition-colors">
                Rollback Proposal
              </button>
            )}
            <button onClick={() => onEdit(playbook)}
              className="p-1.5 text-slate-500 hover:text-slate-300 hover:bg-white/5 rounded-lg transition-colors">
              <Pencil className="w-3.5 h-3.5" />
            </button>
            {playbook.status !== "active" && (
              <button onClick={() => onDelete(playbook.id)}
                className="p-1.5 text-slate-600 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Profit/cost summary */}
        {(() => {
          const pm = playbook.profit_model ?? {};
          const pricing = playbook.pricing_model ?? {};
          const hasProfit = (pm.expected_profit ?? 0) > 0;
          const hasBuildCost = (pricing.expected_build_cost ?? 0) > 0;
          if (!hasProfit && !hasBuildCost) return null;
          return (
            <div className="flex items-center gap-4 px-4 py-2 bg-[#0a1220] border-b border-[#1e2d45] text-sm -mx-4 mt-3">
              {hasBuildCost && (
                <div>
                  <div className="text-[11px] text-slate-500">Build cost</div>
                  <div className="font-bold text-slate-300">£{pricing.minimum_build_cost ?? "?"}–£{pricing.maximum_build_cost ?? "?"}</div>
                </div>
              )}
              {hasProfit && (
                <div>
                  <div className="text-[11px] text-slate-500">Profit range</div>
                  <div className="font-bold text-[#00dc82]">£{pm.minimum_profit ?? "?"}–£{pm.maximum_profit ?? "?"}</div>
                </div>
              )}
              {(pm.expected_roi_pct ?? 0) > 0 && (
                <div>
                  <div className="text-[11px] text-slate-500">ROI</div>
                  <div className="font-bold text-blue-400">{pm.expected_roi_pct?.toFixed(0)}%</div>
                </div>
              )}
              {playbook.avg_days_to_sell != null && (
                <div className="ml-auto">
                  <div className="text-[11px] text-slate-500">Avg sell</div>
                  <div className="font-bold text-slate-300">{playbook.avg_days_to_sell.toFixed(0)}d</div>
                </div>
              )}
            </div>
          );
        })()}

        {/* Metrics row */}
        {(playbook.flip_count > 0 || playbook.avg_profit_gbp != null) && (
          <div className="flex gap-4 mt-3 pt-3 border-t border-[#1e2d45]">
            <div className="text-center">
              <div className="text-base font-bold text-[#00dc82]">{playbook.flip_count}</div>
              <div className="text-xs text-slate-600">Flips</div>
            </div>
            {playbook.avg_profit_gbp != null && (
              <div className="text-center">
                <div className="text-base font-bold text-emerald-400">£{playbook.avg_profit_gbp.toFixed(0)}</div>
                <div className="text-xs text-slate-600">Avg profit</div>
              </div>
            )}
            {playbook.avg_days_to_sell != null && (
              <div className="text-center">
                <div className="text-base font-bold text-slate-200">{playbook.avg_days_to_sell.toFixed(1)}d</div>
                <div className="text-xs text-slate-600">Avg sell time</div>
              </div>
            )}
            {playbook.conversion_rate != null && (
              <div className="text-center">
                <div className="text-base font-bold text-slate-200">{(playbook.conversion_rate * 100).toFixed(0)}%</div>
                <div className="text-xs text-slate-600">Conversion</div>
              </div>
            )}
          </div>
        )}

        {/* Quick stats */}
        <div className="flex gap-3 mt-3 flex-wrap">
          {ss.price_min != null && ss.price_max != null && (
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Tag className="w-3 h-3" />
              £{ss.price_min}–£{ss.price_max}
            </span>
          )}
          {(ss.keywords || []).length > 0 && (
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Search className="w-3 h-3" />
              {(ss.keywords || []).length} keywords
            </span>
          )}
          {ps.target_profit_gbp != null && (
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Target className="w-3 h-3" />
              £{ps.target_profit_gbp} target
            </span>
          )}
          {ps.target_margin_pct != null && (
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <BarChart2 className="w-3 h-3" />
              {ps.target_margin_pct}% margin
            </span>
          )}
        </div>

        <button onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-400 mt-2 transition-colors">
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {expanded ? "Less" : "More"} detail
        </button>
      </div>

      {expanded && (
        <div className="px-4 pb-4 pt-0 border-t border-[#1e2d45] space-y-3">
          {(us.required || []).length > 0 && (
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-1">Required upgrades</div>
              <div className="space-y-1">
                {(us.required || []).map((u: { component: string; target: string; max_cost: number }, i: number) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-slate-300">{u.component}</span>
                    <span className="text-slate-500">{u.target}</span>
                    <span className="text-[#00dc82]">≤£{u.max_cost}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {(us.optional || []).length > 0 && (
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-1">Optional upgrades</div>
              <div className="space-y-1">
                {(us.optional || []).map((u: { component: string; target: string; max_cost: number }, i: number) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">{u.component}</span>
                    <span className="text-slate-500">{u.target}</span>
                    <span className="text-slate-400">≤£{u.max_cost}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {ps.notes && (
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-1">Notes</div>
              <p className="text-xs text-slate-400 leading-relaxed">{ps.notes}</p>
            </div>
          )}
          {(ss.keywords || []).length > 0 && (
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-1">Keywords ({(ss.keywords || []).length})</div>
              <div className="flex flex-wrap gap-1">
                {(ss.keywords || []).slice(0, 20).map((kw: string) => (
                  <span key={kw} className="text-xs bg-[#111c2e] border border-[#1e2d45] text-slate-400 px-1.5 py-0.5 rounded font-mono">{kw}</span>
                ))}
                {(ss.keywords || []).length > 20 && (
                  <span className="text-xs text-slate-600">+{(ss.keywords || []).length - 20} more</span>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab navigation */}
      <div className="flex border-t border-[#1e2d45]">
        {(["scores", "build", "season"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-2 text-xs font-medium transition-colors ${
              tab === t ? "text-[#00dc82] bg-[#00dc82]/5" : "text-slate-500 hover:text-slate-300"
            }`}>
            {t === "scores" ? "📊 Scores" : t === "build" ? "🔧 Ideal Build" : "📅 Seasonality"}
          </button>
        ))}
      </div>
      {/* Tab content */}
      <div className="p-4 border-t border-[#1e2d45]">
        {tab === "scores" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ScoreBadges playbook={playbook} />
            <div>
              {playbook.what_they_use_it_for && (
                <div className="mb-3">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest mb-1">What they use it for</div>
                  <p className="text-xs text-slate-400">{playbook.what_they_use_it_for}</p>
                </div>
              )}
              {(playbook.critical_success_factors ?? []).length > 0 && (
                <div>
                  <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest mb-1">Success factors</div>
                  <ul className="space-y-0.5">
                    {(playbook.critical_success_factors ?? []).map(f => (
                      <li key={f} className="text-xs text-slate-300 flex items-center gap-1.5">
                        <span className="w-1 h-1 bg-[#00dc82] rounded-full flex-shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
        {tab === "build" && (
          <IdealBuildPanel idealBuild={playbook.ideal_build ?? {}} />
        )}
        {tab === "season" && (
          <SeasonalityChart seasonality={playbook.seasonality ?? {}} />
        )}
      </div>
      {playbook.last_reviewed && (
        <div className="px-4 py-2 border-t border-[#1e2d45]">
          <span className="text-[11px] text-slate-600">Last reviewed {relTime(playbook.last_reviewed)}</span>
        </div>
      )}
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

type Tab = "active" | "candidates" | "retired" | "proposals";

export default function PlaybooksPage() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [proposals, setProposals] = useState<PlaybookProposal[]>([]);
  const [experimentSummary, setExperimentSummary] = useState<Record<string, { total: number; pending: number; approved: number; rejected: number; approval_rate: number }>>({});
  const [experimentAttribution, setExperimentAttribution] = useState<Record<string, { proposal_windows: number; attributed_flips: number; avg_profit: number; avg_roi_pct: number; sample_quality: "low" | "medium" | "high" }>>({});
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("active");
  const [showCreate, setShowCreate] = useState(false);
  const [editTarget, setEditTarget] = useState<Playbook | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pbs, props] = await Promise.all([
        api.playbooks.list(),
        api.playbooks.proposals.list(),
      ]);
      setPlaybooks(pbs);
      setProposals(props);
      try {
        const [exp, attrib] = await Promise.all([
          api.playbooks.experimentSummary(),
          api.playbooks.experimentAttribution(14),
        ]);
        setExperimentSummary(exp.variants || {});
        setExperimentAttribution(attrib.variants || {});
      } catch {
        setExperimentSummary({});
        setExperimentAttribution({});
      }
    } catch {
      setPlaybooks([]); setProposals([]);
      setExperimentSummary({});
      setExperimentAttribution({});
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(() => { void load(); }, 0);
    return () => clearTimeout(id);
  }, [load]);

  const handleCreate = async (data: Record<string, unknown>) => {
    await api.playbooks.create(data);
    await load();
  };

  const handleEdit = async (data: Record<string, unknown>) => {
    if (!editTarget) return;
    await api.playbooks.update(editTarget.id, data);
    setEditTarget(null);
    await load();
  };

  const handleDelete = async (id: number) => {
    await api.playbooks.delete(id);
    await load();
  };

  const handleActivate = async (id: number) => {
    await api.playbooks.update(id, { status: "active", activated_at: new Date().toISOString() });
    await load();
  };

  const handleRetire = async (id: number) => {
    // Create a proposal rather than retiring directly
    await api.playbooks.proposals.create({
      action: "RETIRE",
      playbook_id: id,
      reason: "Manually retired by user",
    });
    await load();
    setTab("proposals");
  };

  const handleApprove = async (proposalId: number) => {
    await api.playbooks.proposals.approve(proposalId);
    await load();
  };

  const handleReject = async (proposalId: number) => {
    await api.playbooks.proposals.reject(proposalId, "Rejected by user");
    await load();
  };

  const handleRollback = async (id: number) => {
    await api.playbooks.rollbackLastUpdate(id);
    await load();
    setTab("proposals");
  };

  const active = playbooks.filter(p => p.status === "active");
  const candidates = playbooks.filter(p => p.status === "candidate");
  const retired = playbooks.filter(p => p.status === "deprecated");
  const pending = proposals.filter(p => p.status === "pending");

  const tabList: { key: Tab; label: string; count: number; icon: React.ReactNode }[] = [
    { key: "active",     label: "Active",     count: active.length,     icon: <Zap className="w-3.5 h-3.5" /> },
    { key: "candidates", label: "Candidates", count: candidates.length, icon: <Clock className="w-3.5 h-3.5" /> },
    { key: "proposals",  label: "Proposals",  count: pending.length,    icon: <AlertTriangle className="w-3.5 h-3.5" /> },
    { key: "retired",    label: "Retired",    count: retired.length,    icon: <CheckCircle className="w-3.5 h-3.5" /> },
  ];

  const displayedPlaybooks =
    tab === "active" ? active :
    tab === "candidates" ? candidates :
    tab === "retired" ? retired : [];

  const displayedProposals =
    tab === "proposals" ? proposals : [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2.5">
            <span className="w-8 h-8 border border-[var(--nf-border)] bg-[rgba(164,230,255,0.08)] flex items-center justify-center">
              <BookOpen className="w-4 h-4 text-[var(--nf-primary)]" />
            </span>
            Strategy_Library
          </h1>
          <p className="text-[var(--nf-text-muted)] text-sm mt-1 font-mono">
            Strategy templates that drive search, filtering, and evaluation.
            All status changes require approval.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load}
            className="p-2 text-slate-500 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-colors">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <Button
            onClick={async () => {
              await api.playbooks.seed();
              await load();
            }}
            variant="outline"
            className="border-[#1e2d45] text-slate-400 hover:text-slate-200 text-sm"
          >
            Seed Playbooks
          </Button>
          <Button onClick={() => setShowCreate(true)}
            className="bg-[#00dc82] text-black hover:bg-[#00dc82]/90 font-semibold flex items-center gap-1.5">
            <Plus className="w-4 h-4" /> New Playbook
          </Button>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Active strategies", value: active.length, color: "text-[#00dc82]", icon: <TrendingUp className="w-4 h-4" /> },
          { label: "Candidates", value: candidates.length, color: "text-yellow-400", icon: <Clock className="w-4 h-4" /> },
          { label: "Pending approvals", value: pending.length, color: "text-orange-400", icon: <AlertTriangle className="w-4 h-4" /> },
          { label: "Total keywords", value: active.reduce((s, p) => s + (p.search_strategy?.keywords?.length || 0), 0), color: "text-slate-200", icon: <Search className="w-4 h-4" /> },
        ].map(item => (
          <Card key={item.label} className="glass-card">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-slate-500 mb-1">
                {item.icon}
                <span className="text-xs">{item.label}</span>
              </div>
              <div className={`text-2xl font-bold ${item.color}`}>{item.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="glass-card">
        <CardContent className="p-4">
          <div className="text-xs uppercase tracking-widest text-slate-500 mb-3">Evolution Experiments</div>
          {Object.keys(experimentSummary).length === 0 ? (
            <p className="text-xs text-slate-600">No A/B experiment proposals yet.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {Object.entries(experimentSummary).map(([variant, v]) => (
                <div key={variant} className="rounded-lg border border-[#1e2d45] bg-[#111c2e] p-3">
                  <div className="text-sm text-slate-200 font-semibold">Variant {variant}</div>
                  <div className="text-xs text-slate-500 mt-1">
                    {v.total} total · {v.approved} approved · {v.rejected} rejected · {v.pending} pending
                  </div>
                  <div className="text-xs text-cyan-300 mt-1">Approval rate: {v.approval_rate.toFixed(1)}%</div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      <Card className="glass-card">
        <CardContent className="p-4">
          <div className="text-xs uppercase tracking-widest text-slate-500 mb-3">Experiment Attribution (14d)</div>
          {Object.keys(experimentAttribution).length === 0 ? (
            <p className="text-xs text-slate-600">No attributed sold outcomes yet.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {Object.entries(experimentAttribution).map(([variant, v]) => (
                <div key={variant} className="rounded-lg border border-[#1e2d45] bg-[#111c2e] p-3">
                  <div className="text-sm text-slate-200 font-semibold">Variant {variant}</div>
                  <div className="text-xs text-slate-500 mt-1">
                    windows {v.proposal_windows} · flips {v.attributed_flips}
                  </div>
                  <div className="text-xs text-emerald-300 mt-1">
                    avg profit £{v.avg_profit.toFixed(0)} · ROI {v.avg_roi_pct.toFixed(1)}%
                  </div>
                  <div className={`text-[11px] mt-1 ${
                    v.sample_quality === "high" ? "text-emerald-300"
                      : v.sample_quality === "medium" ? "text-yellow-300"
                        : "text-slate-500"
                  }`}>
                    sample quality: {v.sample_quality}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pending approval banner */}
      {pending.length > 0 && tab !== "proposals" && (
        <div
          className="flex items-center gap-3 bg-orange-500/10 border border-orange-500/30 rounded-xl px-4 py-3 cursor-pointer hover:bg-orange-500/15 transition-colors"
          onClick={() => setTab("proposals")}
        >
          <AlertTriangle className="w-4 h-4 text-orange-400 flex-shrink-0" />
          <p className="text-sm text-orange-300">
            <span className="font-semibold">{pending.length} proposal{pending.length > 1 ? "s" : ""} awaiting approval.</span>
            {" "}Review and approve to apply strategy changes.
          </p>
          <ChevronRight className="w-4 h-4 text-orange-400 ml-auto flex-shrink-0" />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-[rgba(15,18,24,0.78)] border border-[var(--nf-border)] rounded-md p-1 w-fit">
        {tabList.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              tab === t.key
                ? "bg-[#00dc82]/10 text-[#00dc82] border border-[#00dc82]/20"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {t.icon}
            {t.label}
            {t.count > 0 && (
              <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                tab === t.key ? "bg-[#00dc82]/20 text-[#00dc82]" : "bg-[#1e2d45] text-slate-500"
              }`}>
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map(i => (
            <div key={i} className="h-24 bg-[#0d1726] border border-[#1e2d45] rounded-xl animate-pulse" />
          ))}
        </div>
      ) : tab === "proposals" ? (
        <div className="space-y-3">
          {displayedProposals.length === 0 ? (
            <div className="text-center py-16 text-slate-500">
              <CheckCircle className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p>No proposals</p>
            </div>
          ) : (
            displayedProposals.map(p => (
              <ProposalCard
                key={p.id}
                proposal={p}
                onApprove={handleApprove}
                onReject={handleReject}
              />
            ))
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {displayedPlaybooks.length === 0 ? (
            <div className="text-center py-16 text-slate-500">
              <BookOpen className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p>No {tab} playbooks</p>
              {tab === "active" && (
                <p className="text-sm mt-1">Create a playbook or promote a candidate to get started.</p>
              )}
            </div>
          ) : (
            displayedPlaybooks.map(pb => (
              <PlaybookCard
                key={pb.id}
                playbook={pb}
                onEdit={setEditTarget}
                onDelete={handleDelete}
                onActivate={handleActivate}
                onRetire={handleRetire}
                onRollback={handleRollback}
              />
            ))
          )}
        </div>
      )}

      {/* Create modal */}
      <PlaybookFormModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSave={handleCreate}
        title="New Playbook"
      />

      {/* Edit modal */}
      <PlaybookFormModal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        onSave={handleEdit}
        initialData={editTarget ? playbookToForm(editTarget) : undefined}
        title={`Edit: ${editTarget?.name || ""}`}
      />
    </div>
  );
}
