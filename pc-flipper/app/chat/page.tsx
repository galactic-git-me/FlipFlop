"use client";

import { Suspense, useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import {
  Wand2, Cpu, Trophy, ClipboardList,
  ChevronRight, ChevronLeft, RotateCcw, Search,
  AlertTriangle, Zap,
  CheckCircle2, Circle, Loader2, ExternalLink,
  Clock, Copy, Check,
} from "lucide-react";
import { api, WizardPlaybook, WizardBuild, RefinedIntent, PurchasePlan, PlanStep } from "@/lib/api";
import { cn } from "@/lib/utils";
import { BuildScatterGraph } from "@/components/build-scatter-graph";

// ─── Phase definitions ────────────────────────────────────────────────────────

type Phase = "playbook" | "intent" | "generating" | "builds" | "plan";

const PHASES: { id: Phase; label: string; icon: React.ElementType }[] = [
  { id: "playbook",    label: "Playbook",  icon: Wand2        },
  { id: "intent",      label: "Intent",    icon: Cpu          },
  { id: "generating",  label: "Agents",    icon: Zap          },
  { id: "builds",      label: "Builds",    icon: Trophy       },
  { id: "plan",        label: "Plan",      icon: ClipboardList },
];

// ─── Colour helpers ───────────────────────────────────────────────────────────

const RISK_STYLE = {
  low:    { badge: "bg-emerald-400/15 text-emerald-400 border-emerald-400/30", dot: "bg-emerald-400" },
  medium: { badge: "bg-yellow-400/15 text-yellow-400 border-yellow-400/30",   dot: "bg-yellow-400"  },
  high:   { badge: "bg-red-400/15 text-red-400 border-red-400/30",             dot: "bg-red-400"     },
};
const DEMAND_STYLE = {
  excellent: "text-cyan-400",
  good:      "text-emerald-400",
  moderate:  "text-yellow-400",
  poor:      "text-red-400",
};

// ─── Agent status while generating ───────────────────────────────────────────

interface AgentStatus {
  id: string;
  label: string;
  status: "waiting" | "running" | "done" | "retrying";
  detail?: string;
}

// ─── Phase 1: Playbook picker ─────────────────────────────────────────────────

function PlaybookPicker({
  playbooks, selected, onSelect,
}: {
  playbooks: WizardPlaybook[];
  selected: WizardPlaybook | null;
  onSelect: (p: WizardPlaybook) => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-100">Choose a Playbook</h2>
        <p className="text-sm text-slate-500 mt-1">
          Playbooks define your flip strategy — the type of PC you&apos;re building and who you&apos;re selling to.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {playbooks.map(p => {
          const isSelected = selected?.id === p.id;
          const target = (p.profit_strategy as Record<string, number | string | undefined>)?.target_profit_gbp;
          return (
            <button
              key={p.id}
              onClick={() => onSelect(p)}
              className={cn(
                "text-left p-4 rounded-xl border transition-all",
                isSelected
                  ? "border-[#00dc82]/60 bg-[#00dc82]/8 ring-1 ring-[#00dc82]/30"
                  : "border-[#1e2d45] bg-[#0d1320] hover:border-[#1e2d45]/80 hover:bg-[#0d1320]/80"
              )}
            >
              <div className="flex items-start gap-3">
                <span className="text-2xl leading-none mt-0.5">{p.emoji}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-200 text-sm">{p.name}</span>
                    {p.status === "candidate" && (
                      <span className="text-[9px] px-1.5 py-0.5 bg-yellow-400/15 text-yellow-400 border border-yellow-400/30 rounded font-mono">BETA</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">{p.description}</p>
                  {target && (
                    <div className="mt-2 text-xs text-[#00dc82] font-mono">
                      Target profit: £{String(target)}
                    </div>
                  )}
                </div>
                {isSelected && (
                  <CheckCircle2 className="w-4 h-4 text-[#00dc82] flex-shrink-0 mt-0.5" />
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Phase 2: Intent form ─────────────────────────────────────────────────────

const PRIORITY_OPTIONS = [
  "Maximum profit",
  "Minimum risk",
  "Quick turnaround",
  "Low upfront cost",
  "High demand builds",
];

const CONSTRAINT_OPTIONS = [
  "ATX cases only",
  "Must include PSU",
  "No untested listings",
  "Delivery only (no collection)",
  "GPU required",
];

function IntentForm({
  playbook, budget, setBudget,
  notes, setNotes,
  priorities, setPriorities,
  constraints, setConstraints,
}: {
  playbook: WizardPlaybook;
  budget: number; setBudget: (n: number) => void;
  notes: string; setNotes: (s: string) => void;
  priorities: string[]; setPriorities: (a: string[]) => void;
  constraints: string[]; setConstraints: (a: string[]) => void;
}) {
  const toggle = (arr: string[], val: string, set: (a: string[]) => void) =>
    set(arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]);

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-lg">{playbook.emoji}</span>
          <h2 className="text-xl font-bold text-slate-100">Refine Your Intent</h2>
        </div>
        <p className="text-sm text-slate-500">Tell the Wizard what you&apos;re optimising for.</p>
      </div>

      {/* Budget */}
      <div>
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Total Budget
        </label>
        <div className="mt-2 flex items-center gap-3">
          <span className="text-2xl font-black text-[#00dc82]">£{budget}</span>
          <input
            type="range" min={50} max={1000} step={25} value={budget}
            onChange={e => setBudget(Number(e.target.value))}
            className="flex-1 accent-[#00dc82]"
          />
        </div>
        <div className="flex justify-between text-xs text-slate-600 mt-1">
          <span>£50</span><span>£1,000</span>
        </div>
      </div>

      {/* Priorities */}
      <div>
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Priorities (pick any)
        </label>
        <div className="mt-2 flex flex-wrap gap-2">
          {PRIORITY_OPTIONS.map(p => (
            <button
              key={p}
              onClick={() => toggle(priorities, p, setPriorities)}
              className={cn(
                "px-3 py-1.5 rounded-lg border text-xs font-medium transition-all",
                priorities.includes(p)
                  ? "border-[#00dc82]/50 bg-[#00dc82]/10 text-[#00dc82]"
                  : "border-[#1e2d45] bg-[#0d1320] text-slate-500 hover:text-slate-400"
              )}
            >{p}</button>
          ))}
        </div>
      </div>

      {/* Constraints */}
      <div>
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Constraints (optional)
        </label>
        <div className="mt-2 flex flex-wrap gap-2">
          {CONSTRAINT_OPTIONS.map(c => (
            <button
              key={c}
              onClick={() => toggle(constraints, c, setConstraints)}
              className={cn(
                "px-3 py-1.5 rounded-lg border text-xs font-medium transition-all",
                constraints.includes(c)
                  ? "border-yellow-400/50 bg-yellow-400/10 text-yellow-400"
                  : "border-[#1e2d45] bg-[#0d1320] text-slate-500 hover:text-slate-400"
              )}
            >{c}</button>
          ))}
        </div>
      </div>

      {/* Notes */}
      <div>
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Additional Notes (optional)
        </label>
        <textarea
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="e.g. I have an RTX 3060 already. Prefer i7 base units. Want to flip within 2 weeks."
          rows={3}
          className="mt-2 w-full px-4 py-3 bg-[#0d1320] border border-[#1e2d45] rounded-xl text-sm text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50 resize-none transition-colors"
        />
      </div>
    </div>
  );
}

// ─── Phase 3: Agent activity ──────────────────────────────────────────────────

function AgentPipeline({ agents }: { agents: AgentStatus[] }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-100">Agents Working…</h2>
        <p className="text-sm text-slate-500 mt-1">The multi-agent pipeline is generating and validating your builds.</p>
      </div>
      <div className="space-y-3">
        {agents.map((agent) => (
          <div key={agent.id} className={cn(
            "flex items-start gap-4 p-4 rounded-xl border transition-all",
            agent.status === "running"  ? "border-[#00dc82]/40 bg-[#00dc82]/5"   : "",
            agent.status === "done"     ? "border-emerald-400/20 bg-emerald-400/3" : "",
            agent.status === "retrying" ? "border-yellow-400/40 bg-yellow-400/5"  : "",
            agent.status === "waiting"  ? "border-[#1e2d45]/50 bg-[#0d1320]/50 opacity-50" : "",
          )}>
            <div className={cn(
              "w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0",
              agent.status === "running"  ? "bg-[#00dc82]/20"     : "",
              agent.status === "done"     ? "bg-emerald-400/15"    : "",
              agent.status === "retrying" ? "bg-yellow-400/15"     : "",
              agent.status === "waiting"  ? "bg-[#1e2d45]"         : "",
            )}>
              {agent.status === "running"  && <Loader2 className="w-4 h-4 text-[#00dc82] animate-spin" />}
              {agent.status === "done"     && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
              {agent.status === "retrying" && <RotateCcw className="w-4 h-4 text-yellow-400 animate-spin" />}
              {agent.status === "waiting"  && <Circle className="w-4 h-4 text-slate-600" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={cn(
                  "text-sm font-semibold",
                  agent.status === "running"  ? "text-[#00dc82]"   : "",
                  agent.status === "done"     ? "text-emerald-400" : "",
                  agent.status === "retrying" ? "text-yellow-400"  : "",
                  agent.status === "waiting"  ? "text-slate-600"   : "",
                )}>{agent.label}</span>
                {agent.status === "retrying" && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-yellow-400/15 text-yellow-400 border border-yellow-400/30 rounded font-mono">RETRYING</span>
                )}
              </div>
              {agent.detail && (
                <p className="text-xs text-slate-500 mt-0.5">{agent.detail}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Phase 4: Build cards ─────────────────────────────────────────────────────

function BuildCard({
  build, selected, onSelect,
}: {
  build: WizardBuild;
  selected: boolean;
  onSelect: () => void;
}) {
  const risk = RISK_STYLE[build.risk] ?? RISK_STYLE.medium;
  const demandColor = DEMAND_STYLE[build.demand_fit] ?? DEMAND_STYLE.good;

  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full text-left p-5 rounded-xl border transition-all",
        selected
          ? "border-[#00dc82]/60 bg-[#00dc82]/6 ring-1 ring-[#00dc82]/25"
          : "border-[#1e2d45] bg-[#0d1320] hover:border-[#1e2d45]/80"
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-6 h-6 rounded-full border flex items-center justify-center text-xs font-black flex-shrink-0",
            build.rank === 1 ? "border-yellow-400/60 bg-yellow-400/15 text-yellow-400" : "border-[#1e2d45] text-slate-500"
          )}>
            {build.rank === 1 ? "★" : build.rank}
          </div>
          <span className="font-bold text-slate-200 text-sm">{build.name}</span>
        </div>
        <span className={cn("text-[10px] px-2 py-0.5 rounded border font-mono", risk.badge)}>
          {build.risk.toUpperCase()} RISK
        </span>
      </div>

      {/* Spec */}
      <p className="text-xs text-slate-500 mb-3 font-mono leading-relaxed">
        {build.base_spec}
      </p>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div className="bg-[#0a0f1a] rounded-lg p-2.5">
          <div className="text-[10px] text-slate-600 uppercase tracking-wider">Total Cost</div>
          <div className="text-sm font-bold text-slate-200 mt-0.5">£{build.total_cost.toFixed(0)}</div>
        </div>
        <div className="bg-[#0a0f1a] rounded-lg p-2.5">
          <div className="text-[10px] text-slate-600 uppercase tracking-wider">Profit</div>
          <div className="text-sm font-bold text-[#00dc82] mt-0.5">£{build.estimated_profit.toFixed(0)}</div>
        </div>
        <div className="bg-[#0a0f1a] rounded-lg p-2.5">
          <div className="text-[10px] text-slate-600 uppercase tracking-wider">Demand</div>
          <div className={cn("text-sm font-bold mt-0.5 capitalize", demandColor)}>{build.demand_fit}</div>
        </div>
      </div>

      {/* Upgrades chips */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {build.upgrades.map((u, i) => (
          <span key={i} className={cn(
            "text-[10px] px-2 py-0.5 rounded border font-mono",
            u.required
              ? "border-slate-600/40 bg-slate-800/50 text-slate-400"
              : "border-slate-700/30 bg-slate-900/50 text-slate-600"
          )}>
            {u.item} · £{u.cost_estimate.toFixed(0)}
          </span>
        ))}
      </div>

      {/* Why */}
      <p className="text-xs text-slate-500 italic leading-relaxed">&quot;{build.why}&quot;</p>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {build.playbook_name && (
          <span className="text-[10px] px-2 py-0.5 rounded border border-cyan-400/30 bg-cyan-400/10 text-cyan-300 font-mono">
            {build.playbook_name}
          </span>
        )}
        {build.sourcing_lane && (
          <span className="text-[10px] px-2 py-0.5 rounded border border-slate-600/40 bg-slate-800/50 text-slate-300 font-mono">
            {build.sourcing_lane.replaceAll("_", " ")}
          </span>
        )}
        {build.seller_label && (
          <span className="text-[10px] px-2 py-0.5 rounded border border-yellow-400/25 bg-yellow-400/10 text-yellow-300 font-mono">
            {build.seller_label.replaceAll("_", " ")}
          </span>
        )}
      </div>

      {/* Score bar */}
      <div className="mt-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] text-slate-600 uppercase tracking-wider">Validation score</span>
          <span className="text-[10px] font-mono text-slate-500">{build.validation_score.toFixed(0)}/100</span>
        </div>
        <div className="h-1 bg-[#1e2d45] rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-[#00dc82] to-cyan-400 rounded-full transition-all"
            style={{ width: `${Math.min(100, build.validation_score)}%` }}
          />
        </div>
      </div>
      {build.listing_url && (
        <div className="mt-2">
          <a
            href={build.listing_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[11px] text-cyan-300 hover:text-cyan-200"
            onClick={(e) => e.stopPropagation()}
          >
            View source listing <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      )}
    </button>
  );
}

// ─── Phase 5: Purchase plan ───────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button onClick={copy} className="p-1 rounded hover:bg-[#1e2d45] transition-colors">
      {copied ? <Check className="w-3 h-3 text-[#00dc82]" /> : <Copy className="w-3 h-3 text-slate-500" />}
    </button>
  );
}

function PurchasePlanView({ plan }: { plan: PurchasePlan; intent: RefinedIntent }) {
  const b = plan.build;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#00dc82]/15 border border-[#00dc82]/30 flex items-center justify-center">
          <ClipboardList className="w-5 h-5 text-[#00dc82]" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-slate-100">{b.name}</h2>
          <p className="text-sm text-slate-500">Your purchase plan · {plan.timeline_days}-day flip</p>
        </div>
      </div>

      {/* Budget summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Total Budget",    value: `£${plan.total_budget.toFixed(0)}`,          color: "text-slate-200"  },
          { label: "Expected Profit", value: `£${plan.expected_net_profit.toFixed(0)}`,   color: "text-[#00dc82]" },
          { label: "ROI",             value: `${plan.expected_roi_pct.toFixed(0)}%`,       color: "text-cyan-400"   },
          { label: "Contingency",     value: `£${plan.contingency_buffer.toFixed(0)}`,     color: "text-yellow-400" },
        ].map(m => (
          <div key={m.label} className="bg-[#0d1320] border border-[#1e2d45] rounded-xl p-3">
            <div className="text-[10px] text-slate-600 uppercase tracking-wider">{m.label}</div>
            <div className={cn("text-lg font-black mt-0.5", m.color)}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* Steps */}
      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Action Plan</h3>
        <div className="space-y-2">
          {plan.steps.map((step: PlanStep) => (
            <div key={step.step} className="flex gap-3 p-3 bg-[#0d1320] border border-[#1e2d45] rounded-xl">
              <div className="w-6 h-6 rounded-full bg-[#00dc82]/15 border border-[#00dc82]/30 flex items-center justify-center flex-shrink-0">
                <span className="text-[10px] font-black text-[#00dc82]">{step.step}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-200">{step.action}</span>
                  <span className="text-[10px] text-slate-600 flex-shrink-0 flex items-center gap-1">
                    <Clock className="w-3 h-3" />{step.estimated_time}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">{step.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </div>


      {/* Pro tips */}
      {plan.tips.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Pro Tips</h3>
          <div className="space-y-2">
            {plan.tips.map((tip, i) => (
              <div key={i} className="flex gap-2 p-3 bg-yellow-400/5 border border-yellow-400/20 rounded-xl">
                <Zap className="w-3.5 h-3.5 text-yellow-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-slate-300">{tip}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cost breakdown */}
      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Cost Breakdown</h3>
        <div className="bg-[#0d1320] border border-[#1e2d45] rounded-xl overflow-hidden">
          <div className="divide-y divide-[#1e2d45]">
            {/* Base PC row */}
            <div className="flex items-center gap-3 px-4 py-2.5 text-xs">
              {b.base_image_url ? (
                <img src={b.base_image_url} alt="Base PC" className="w-10 h-10 rounded object-cover flex-shrink-0 border border-[#1e2d45]" />
              ) : (
                <div className="w-10 h-10 rounded bg-[#1e2d45] flex-shrink-0 flex items-center justify-center text-slate-600 text-[9px]">IMG</div>
              )}
              <div className="flex-1 min-w-0">
                <a
                  href={b.base_listing_url || `https://www.ebay.co.uk/sch/i.html?_nkw=${encodeURIComponent(b.base_spec)}&LH_ItemCondition=3000`}
                  target="_blank" rel="noopener noreferrer"
                  className="text-slate-300 hover:text-[#00dc82] transition-colors flex items-center gap-1 group font-medium"
                >
                  <span className="truncate">{b.base_spec.slice(0, 55)}{b.base_spec.length > 55 ? "…" : ""}</span>
                  <ExternalLink className="w-2.5 h-2.5 flex-shrink-0 opacity-60 group-hover:opacity-100 transition-opacity" />
                </a>
                <div className="text-slate-600 mt-0.5">
                  Base PC {b.base_listing_url ? <span className="text-emerald-500">· verified listing</span> : <span className="text-slate-700">· search</span>}
                </div>
              </div>
              <span className="text-slate-300 font-mono flex-shrink-0">£{b.base_cost.toFixed(0)}</span>
            </div>
            {b.upgrades.map((u, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-2.5 text-xs">
                {u.image_url ? (
                  <img src={u.image_url} alt={u.item} className="w-10 h-10 rounded object-cover flex-shrink-0 border border-[#1e2d45]" />
                ) : (
                  <div className="w-10 h-10 rounded bg-[#1e2d45] flex-shrink-0 flex items-center justify-center text-slate-600 text-[9px]">IMG</div>
                )}
                <div className="flex-1 min-w-0">
                  <a
                    href={u.listing_url || `https://www.ebay.co.uk/sch/i.html?_nkw=${encodeURIComponent(u.item)}&LH_ItemCondition=3000`}
                    target="_blank" rel="noopener noreferrer"
                    className="text-slate-300 hover:text-[#00dc82] transition-colors flex items-center gap-1 group font-medium"
                  >
                    <span className="truncate">{u.item}</span>
                    <ExternalLink className="w-2.5 h-2.5 flex-shrink-0 opacity-60 group-hover:opacity-100 transition-opacity" />
                  </a>
                  <div className="text-slate-600 mt-0.5">
                    {u.source} {u.listing_url ? <span className="text-emerald-500">· verified listing</span> : <span className="text-slate-700">· search</span>}
                  </div>
                </div>
                <span className="text-slate-300 font-mono flex-shrink-0">£{u.cost_estimate.toFixed(0)}</span>
              </div>
            ))}
            <div className="flex justify-between px-4 py-2.5 text-xs border-t border-[#1e2d45]">
              <span className="text-slate-400">Contingency (10%)</span>
              <span className="text-yellow-400 font-mono">£{plan.contingency_buffer.toFixed(0)}</span>
            </div>
            <div className="flex justify-between px-4 py-2.5 text-sm font-bold bg-[#0a0f1a]">
              <span className="text-slate-200">Total Budget Required</span>
              <span className="text-[#00dc82] font-mono">£{plan.total_budget.toFixed(0)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Progress bar ─────────────────────────────────────────────────────────────

function WizardProgress({ phase }: { phase: Phase }) {
  const idx = PHASES.findIndex(p => p.id === phase);
  return (
    <div className="flex items-center gap-0 mb-8">
      {PHASES.map((p, i) => {
        const Icon = p.icon;
        const done    = i < idx;
        const current = i === idx;
        return (
          <div key={p.id} className="flex items-center flex-1">
            <div className={cn(
              "flex flex-col items-center gap-1 flex-shrink-0",
            )}>
              <div className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center border transition-all",
                done    ? "border-emerald-400/50 bg-emerald-400/15 text-emerald-400" : "",
                current ? "border-[#00dc82]/60 bg-[#00dc82]/15 text-[#00dc82] ring-2 ring-[#00dc82]/20" : "",
                !done && !current ? "border-[#1e2d45] bg-[#0d1320] text-slate-600" : "",
              )}>
                {done ? <CheckCircle2 className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
              </div>
              <span className={cn(
                "text-[9px] uppercase tracking-wider font-semibold",
                current ? "text-[#00dc82]" : done ? "text-emerald-400" : "text-slate-700",
              )}>{p.label}</span>
            </div>
            {i < PHASES.length - 1 && (
              <div className={cn(
                "flex-1 h-px mx-2 mb-4 transition-all",
                i < idx ? "bg-emerald-400/40" : "bg-[#1e2d45]",
              )} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Main wizard ──────────────────────────────────────────────────────────────

function BuildWizardPageContent() {
  const searchParams = useSearchParams();
  const prefillListingId = Number(searchParams.get("listing_id") || 0) || null;
  const prefillMarker = prefillListingId ? `[prefill listing #${prefillListingId}] Build around this purchased listing.` : "";

  const [phase, setPhase] = useState<Phase>(prefillListingId ? "intent" : "playbook");

  // Playbooks
  const [playbooks, setPlaybooks]     = useState<WizardPlaybook[]>([]);
  const [loadingPbs, setLoadingPbs]   = useState(true);
  const [selectedPb, setSelectedPb]   = useState<WizardPlaybook | null>(null);

  // Intent form
  const [budget, setBudget]           = useState(300);
  const [notes, setNotes]             = useState(prefillMarker);
  const [priorities, setPriorities]   = useState<string[]>(["Maximum profit"]);
  const [constraints, setConstraints] = useState<string[]>([]);

  // Generation
  const [agents, setAgents]           = useState<AgentStatus[]>([]);
  const [genError, setGenError]       = useState<string | null>(null);

  // Results
  const [result, setResult]           = useState<import("@/lib/api").GenerateResult | null>(null);
  const [intent, setIntent]           = useState<RefinedIntent | null>(null);
  const [selectedBuild, setSelectedBuild] = useState<WizardBuild | null>(null);
  const [plan, setPlan]               = useState<PurchasePlan | null>(null);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const autoStartedForListingRef = useRef<number | null>(null);

  // Load playbooks on mount
  useEffect(() => {
    api.buildWizard.playbooks()
      .then((pbs) => {
        setPlaybooks(pbs);
        setSelectedPb((prev) => prev ?? pbs[0] ?? null);
      })
      .catch(() => setPlaybooks([]))
      .finally(() => setLoadingPbs(false));
  }, []);

  // ── Run generation ──────────────────────────────────────────────────────────
  const runGeneration = useCallback(async () => {
    setPhase("generating");
    setGenError(null);
    setResult(null);

    const AGENTS: AgentStatus[] = [
      { id: "wizard",    label: "Wizard Agent",    status: "waiting", detail: "Extracting intent from your inputs" },
      { id: "composer",  label: "Composer Agent",  status: "waiting", detail: "Generating 5 candidate builds" },
      { id: "validator", label: "Validator Agent", status: "waiting", detail: "Checking compatibility & feasibility" },
      { id: "ranker",    label: "Ranker Agent",    status: "waiting", detail: "Sorting by profit · demand · risk" },
    ];
    setAgents(AGENTS);

    const update = (id: string, patch: Partial<AgentStatus>) =>
      setAgents(prev => prev.map(a => a.id === id ? { ...a, ...patch } : a));

    try {
      update("wizard", { status: "running" });
      await new Promise(r => setTimeout(r, 600));
      update("wizard", { status: "done" });

      update("composer", { status: "running", detail: "Building Gem × Playbook recommendations" });
      await new Promise(r => setTimeout(r, 400));

      const data = await api.buildWizard.generateGemMatrix({
        budget,
        user_notes: notes,
        priorities,
        constraints,
        gem_limit: 5,
        playbook_limit: 6,
        listing_id: prefillListingId ?? undefined,
      });

      if (data.attempts > 1) {
        update("composer", { status: "retrying", detail: `Retried ${data.attempts}× to find valid builds` });
        await new Promise(r => setTimeout(r, 500));
      }
      update("composer", { status: "done", detail: `Generated ${(data.builds.length + data.rejected_count)} candidates` });

      update("validator", { status: "running" });
      await new Promise(r => setTimeout(r, 500));
      update("validator", {
        status: "done",
        detail: `${data.builds.length} valid · ${data.rejected_count} rejected`,
      });

      update("ranker", { status: "running" });
      await new Promise(r => setTimeout(r, 300));
      update("ranker", { status: "done", detail: `Ranked ${data.builds.length} builds` });

      setResult(data);
      setIntent(data.intent);
      await new Promise(r => setTimeout(r, 600));
      setPhase("builds");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setGenError(msg || "Generation failed — is the backend running?");
      setPhase("intent");
    }
  }, [budget, notes, priorities, constraints, prefillListingId]);

  useEffect(() => {
    if (!prefillListingId) return;
    if (loadingPbs) return;
    if (phase !== "intent") return;
    if (autoStartedForListingRef.current === prefillListingId) return;
    autoStartedForListingRef.current = prefillListingId;
    void runGeneration();
  }, [prefillListingId, loadingPbs, phase, runGeneration]);

  // ── Generate plan ───────────────────────────────────────────────────────────
  const generatePlan = useCallback(async () => {
    if (!selectedBuild || !intent) return;
    setLoadingPlan(true);
    try {
      const planData = await api.buildWizard.plan({ build: selectedBuild, intent });
      setPlan(planData);
      setPhase("plan");
    } catch {
      alert("Failed to generate plan — check backend");
    } finally {
      setLoadingPlan(false);
    }
  }, [selectedBuild, intent]);

  const reset = () => {
    setPhase("playbook");
    setSelectedPb(null);
    setResult(null);
    setIntent(null);
    setSelectedBuild(null);
    setPlan(null);
    setGenError(null);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="p-6">
      <div className="max-w-5xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 border border-[var(--nf-border)] bg-[rgba(164,230,255,0.08)] flex items-center justify-center">
              <Wand2 className="w-5 h-5 text-[var(--nf-primary)]" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase">Build_Wizard</h1>
              <p className="text-xs text-[var(--nf-text-muted)] font-mono">Multi-agent · Wizard · Composer · Validator · Planner</p>
            </div>
          </div>
          {phase !== "playbook" && phase !== "generating" && (
            <button
              onClick={reset}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0d1320] border border-[#1e2d45] hover:border-slate-600 rounded-lg text-xs text-slate-500 hover:text-slate-400 transition-colors"
            >
              <RotateCcw className="w-3 h-3" /> Start over
            </button>
          )}
        </div>

        {/* Progress */}
        {phase !== "generating" && <WizardProgress phase={phase} />}

        {/* Error banner */}
        {genError && (
          <div className="mb-4 flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-xl">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-red-300">{genError}</p>
          </div>
        )}

        {/* Phase content */}
        <div className="glass-card rounded-md p-6">
          {/* ── Phase 1: Playbook ── */}
          {phase === "playbook" && (
            <>
              {loadingPbs ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-5 h-5 text-[#00dc82] animate-spin" />
                </div>
              ) : (
                <PlaybookPicker playbooks={playbooks} selected={selectedPb} onSelect={setSelectedPb} />
              )}
            </>
          )}

          {/* ── Phase 2: Intent ── */}
          {phase === "intent" && selectedPb && (
            <IntentForm
              playbook={selectedPb}
              budget={budget} setBudget={setBudget}
              notes={notes} setNotes={setNotes}
              priorities={priorities} setPriorities={setPriorities}
              constraints={constraints} setConstraints={setConstraints}
            />
          )}

          {/* ── Phase 3: Generating ── */}
          {phase === "generating" && <AgentPipeline agents={agents} />}

          {/* ── Phase 4: Builds ── */}
          {phase === "builds" && result && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-slate-100">
                    {result.builds.length} Validated Builds
                  </h2>
                  <p className="text-sm text-slate-500 mt-0.5">
                    {result.matrix_meta
                      ? `${result.matrix_meta.gem_count} gems × ${result.matrix_meta.playbook_count} playbooks · ranked by profit`
                      : "Ranked by profit · demand · risk"}
                  </p>
                </div>
                <span className="text-xs text-slate-600 font-mono">
                  Budget: £{budget}
                </span>
              </div>

              {/* Scatter Graph */}
              {result.builds.length > 0 && (
                <div className="bg-[#0d1320] border border-[#1e2d45] rounded-xl p-4">
                  <BuildScatterGraph
                    builds={result.builds}
                    selectedBuild={selectedBuild ?? undefined}
                    onSelectBuild={setSelectedBuild}
                  />
                </div>
              )}

              <div className="space-y-3">
                {result.builds.map(b => (
                  <BuildCard
                    key={b.id}
                    build={b}
                    selected={selectedBuild?.id === b.id}
                    onSelect={() => setSelectedBuild(b)}
                  />
                ))}
              </div>
              {result.builds.length === 0 && (
                <div className="py-8 text-center">
                  <AlertTriangle className="w-8 h-8 text-yellow-400 mx-auto mb-2" />
                  <p className="text-sm text-slate-400">No valid builds found for this budget and playbook.</p>
                  <p className="text-xs text-slate-600 mt-1">Try increasing the budget or choosing a different playbook.</p>
                </div>
              )}
            </div>
          )}

          {/* ── Phase 5: Plan ── */}
          {phase === "plan" && plan && intent && (
            <PurchasePlanView plan={plan} intent={intent} />
          )}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between mt-4">
          <div>
            {phase === "intent" && (
              <button
                onClick={() => setPhase("playbook")}
                className="flex items-center gap-1.5 px-4 py-2.5 bg-[#0d1320] border border-[#1e2d45] hover:border-slate-600 rounded-xl text-sm text-slate-400 hover:text-slate-300 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" /> Back
              </button>
            )}
            {phase === "builds" && (
              <button
                onClick={() => setPhase("intent")}
                className="flex items-center gap-1.5 px-4 py-2.5 bg-[#0d1320] border border-[#1e2d45] hover:border-slate-600 rounded-xl text-sm text-slate-400 hover:text-slate-300 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" /> Change intent
              </button>
            )}
            {phase === "plan" && (
              <button
                onClick={() => setPhase("builds")}
                className="flex items-center gap-1.5 px-4 py-2.5 bg-[#0d1320] border border-[#1e2d45] hover:border-slate-600 rounded-xl text-sm text-slate-400 hover:text-slate-300 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" /> Back to builds
              </button>
            )}
          </div>

          <div>
            {phase === "playbook" && (
              <button
                onClick={() => setPhase("intent")}
                className="flex items-center gap-1.5 px-5 py-2.5 bg-[#00dc82] hover:bg-[#00dc82]/90 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-sm font-bold text-[#0a0f1a] transition-all"
              >
                Next <ChevronRight className="w-4 h-4" />
              </button>
            )}
            {phase === "intent" && (
              <button
                onClick={runGeneration}
                className="flex items-center gap-1.5 px-5 py-2.5 bg-[#00dc82] hover:bg-[#00dc82]/90 rounded-xl text-sm font-bold text-[#0a0f1a] transition-all"
              >
                <Zap className="w-4 h-4" /> Generate Builds
              </button>
            )}
            {phase === "builds" && (
              <button
                onClick={generatePlan}
                disabled={!selectedBuild || loadingPlan}
                className="flex items-center gap-1.5 px-5 py-2.5 bg-[#00dc82] hover:bg-[#00dc82]/90 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-sm font-bold text-[#0a0f1a] transition-all"
              >
                {loadingPlan ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Generating plan…</>
                ) : (
                  <><ClipboardList className="w-4 h-4" /> Get Purchase Plan</>
                )}
              </button>
            )}
          </div>
        </div>

        {/* Footer hint */}
        <p className="text-[10px] text-slate-700 text-center mt-4">
          Wizard · Composer · Validator · Ranker · Planner — 5 agents · powered by Hermes AI
        </p>
      </div>
    </div>
  );
}

export default function BuildWizardPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-slate-400">Loading Build Wizard...</div>}>
      <BuildWizardPageContent />
    </Suspense>
  );
}
