"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Boxes, Download, Loader2, RefreshCw, Save, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import { toast, Toaster } from "sonner";

import { api, type BuildComponent } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

type Forecast = Awaited<ReturnType<typeof api.inventory.forecast>>;
type Opportunity = Awaited<ReturnType<typeof api.inventory.buildOpportunities>>[number];
type ReorderRule = Awaited<ReturnType<typeof api.inventory.reorderRules>>[number];

const DEFAULT_TYPES = ["cpu", "gpu", "motherboard", "ram", "ssd", "psu", "case", "cooler"];

export default function InventoryIntelligencePage() {
  const router = useRouter();
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [rules, setRules] = useState<Record<string, ReorderRule>>({});
  const [adjustments, setAdjustments] = useState<Awaited<ReturnType<typeof api.inventory.sourcingAdjustments>>>([]);
  const [loading, setLoading] = useState(true);
  const [savingRule, setSavingRule] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [horizon, setHorizon] = useState(30);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [forecastData, opportunityData, ruleData, adjustmentData] = await Promise.all([
        api.inventory.forecast(horizon), api.inventory.buildOpportunities(),
        api.inventory.reorderRules(), api.inventory.sourcingAdjustments(),
      ]);
      setForecast(forecastData);
      setOpportunities(opportunityData);
      setRules(Object.fromEntries(ruleData.map(rule => [rule.component_type, rule])));
      setAdjustments(adjustmentData);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not load inventory intelligence");
    } finally {
      setLoading(false);
    }
  }, [horizon]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const updateRule = (componentType: string, field: "minimum_free" | "target_free" | "maximum_free", value: number) => {
    setRules(previous => ({
      ...previous,
      [componentType]: {
        id: previous[componentType]?.id ?? 0,
        component_type: componentType,
        minimum_free: previous[componentType]?.minimum_free ?? 0,
        target_free: previous[componentType]?.target_free ?? 1,
        maximum_free: previous[componentType]?.maximum_free ?? 3,
        notes: previous[componentType]?.notes ?? null,
        [field]: value,
      },
    }));
  };

  const saveRule = async (componentType: string) => {
    const rule = rules[componentType];
    if (!rule) return;
    setSavingRule(componentType);
    try {
      await api.inventory.saveReorderRule(componentType, rule);
      toast.success(`${componentType.toUpperCase()} stock targets saved`);
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save stock target");
    } finally {
      setSavingRule(null);
    }
  };

  const createOwnedBuild = async (opportunity: Opportunity) => {
    if (!opportunity.ready) return;
    setCreating(true);
    try {
      const draft = await api.manualBuilds.create("Inventory-optimised build");
      const labels: Record<string, string> = { cpu: "CPU", gpu: "GPU", motherboard: "Motherboard", ram: "RAM", ssd: "Storage", psu: "PSU", case: "PC Case", cooler: "CPU Cooler" };
      const components: BuildComponent[] = opportunity.components.map(component => ({
        slot: labels[component.component_type] ?? component.component_type,
        name: component.name,
        price_paid: component.cost,
        source: "manual",
        purchased: true,
        inventory_item_id: component.inventory_item_id,
      }));
      await api.manualBuilds.patch(draft.id, { components });
      await api.inventoryAllocations.assignToManualBuild(draft.id, opportunity.components.map(component => component.inventory_item_id));
      router.push(`/builds/${draft.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create inventory build");
      setCreating(false);
    }
  };

  const types = Array.from(new Set([...DEFAULT_TYPES, ...Object.keys(rules), ...(forecast?.rows.map(row => row.component_type) ?? [])]));

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <Toaster theme="dark" position="top-right" />
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div><Link href="/inventory" className="mb-2 inline-flex cursor-pointer items-center gap-1 text-xs text-slate-500 hover:text-cyan-300"><ArrowLeft className="h-3.5 w-3.5" /> Inventory</Link><h1 className="flex items-center gap-2 text-2xl font-bold text-slate-100"><Boxes className="h-5 w-5 text-cyan-300" /> Inventory Intelligence</h1><p className="mt-1 text-sm text-slate-500">Forecast stock, build from what you own and control purchasing targets.</p></div>
        <div className="flex gap-2"><button type="button" onClick={() => void load()} className="flex cursor-pointer items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-300 hover:border-cyan-300/30"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</button><a href={api.inventory.accountingExportUrl()} className="flex cursor-pointer items-center gap-2 rounded-lg bg-emerald-400 px-3 py-2 text-sm font-bold text-slate-950 hover:bg-emerald-300"><Download className="h-4 w-4" /> Accounting CSV</a></div>
      </header>

      <section className="grid gap-3 sm:grid-cols-3">
        <Metric label="Forecast capital required" value={formatCurrency(forecast?.capital_required ?? 0)} />
        <Metric label="Categories to buy" value={String(forecast?.rows.filter(row => row.recommendation === "buy").length ?? 0)} tone="text-amber-300" />
        <Metric label="Buildable from stock" value={opportunities.some(item => item.ready) ? "Yes" : "Not yet"} tone={opportunities.some(item => item.ready) ? "text-emerald-300" : "text-slate-400"} />
      </section>

      <section className="rounded-xl border border-white/10 bg-[#07101c] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-slate-100">Stock forecast</h2><p className="text-xs text-slate-500">Uses recorded consumption and sales velocity; recommendations respect your targets.</p></div><label className="text-xs text-slate-400">Horizon <select value={horizon} onChange={event => setHorizon(Number(event.target.value))} className="ml-2 cursor-pointer rounded border border-white/10 bg-slate-950 px-2 py-1.5 text-slate-200"><option value={30}>30 days</option><option value={60}>60 days</option><option value={90}>90 days</option></select></label></div>
        <div className="mt-4 overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b border-white/10 text-left text-xs text-slate-500"><th className="p-2">Type</th><th className="p-2 text-right">Free now</th><th className="p-2 text-right">Monthly use</th><th className="p-2 text-right">Projected</th><th className="p-2">Action</th><th className="p-2 text-right">Units</th></tr></thead><tbody>{forecast?.rows.map(row => <tr key={row.component_type} className="border-b border-white/5"><td className="p-2 font-semibold uppercase text-slate-300">{row.component_type}</td><td className="p-2 text-right">{row.free_now}</td><td className="p-2 text-right text-slate-400">{row.monthly_usage}</td><td className="p-2 text-right text-slate-300">{row.projected_free}</td><td className="p-2"><span className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-semibold ${row.recommendation === "buy" ? "bg-amber-300/10 text-amber-300" : row.recommendation === "liquidate" ? "bg-rose-300/10 text-rose-300" : "bg-emerald-300/10 text-emerald-300"}`}>{row.recommendation === "buy" ? <TrendingUp className="h-3 w-3" /> : row.recommendation === "liquidate" ? <TrendingDown className="h-3 w-3" /> : null}{row.recommendation}</span></td><td className="p-2 text-right">{row.units}</td></tr>)}</tbody></table></div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-[#07101c] p-4"><h2 className="flex items-center gap-2 font-semibold text-slate-100"><Sparkles className="h-4 w-4 text-violet-300" /> What can I build now?</h2>{opportunities.map(opportunity => <div key={opportunity.name} className="mt-4 rounded-lg border border-white/8 bg-black/20 p-4"><div className="flex justify-between"><div><p className="font-semibold text-slate-200">{opportunity.name}</p><p className="text-xs text-slate-500">{opportunity.completion_pct}% complete from stock</p></div><p className="font-bold text-cyan-300">{formatCurrency(opportunity.owned_cost)}</p></div><div className="mt-3 h-2 overflow-hidden rounded bg-slate-800"><div className="h-full bg-cyan-300" style={{ width: `${opportunity.completion_pct}%` }} /></div><p className="mt-3 text-xs text-slate-400">{opportunity.ready ? "All required component categories are available and compatibility checks passed." : `Still needed: ${opportunity.missing.join(", ")}`}</p><button type="button" disabled={!opportunity.ready || creating} onClick={() => void createOwnedBuild(opportunity)} className="mt-3 flex cursor-pointer items-center gap-2 rounded-md bg-violet-400 px-3 py-2 text-xs font-bold text-slate-950 hover:bg-violet-300 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500">{creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />} Create draft from stock</button></div>)}</div>
        <div className="rounded-xl border border-white/10 bg-[#07101c] p-4"><h2 className="font-semibold text-slate-100">Sourcing score adjustments</h2><p className="mt-1 text-xs text-slate-500">Applied as inventory context alongside the normal deal score.</p><div className="mt-3 space-y-2">{adjustments.map(item => <div key={item.component_type} className="flex items-center justify-between rounded-lg bg-black/20 p-3"><div><p className="text-xs font-semibold uppercase text-slate-300">{item.component_type}</p><p className="text-xs text-slate-500">{item.reason}</p></div><span className={`font-mono text-sm font-bold ${item.deal_score_adjustment > 0 ? "text-emerald-300" : item.deal_score_adjustment < 0 ? "text-rose-300" : "text-slate-500"}`}>{item.deal_score_adjustment > 0 ? "+" : ""}{item.deal_score_adjustment}</span></div>)}</div></div>
      </section>

      <section className="rounded-xl border border-white/10 bg-[#07101c] p-4"><h2 className="font-semibold text-slate-100">Reorder targets</h2><p className="mt-1 text-xs text-slate-500">Set minimum, preferred and maximum free-stock levels by component type.</p><div className="mt-4 grid gap-2 lg:grid-cols-2">{types.map(componentType => { const rule = rules[componentType] ?? { id: 0, component_type: componentType, minimum_free: 0, target_free: 1, maximum_free: 3, notes: null }; return <div key={componentType} className="grid grid-cols-[1fr_repeat(3,70px)_40px] items-end gap-2 rounded-lg border border-white/5 p-3"><p className="self-center text-xs font-semibold uppercase text-slate-300">{componentType}</p>{(["minimum_free", "target_free", "maximum_free"] as const).map(field => <label key={field} className="text-[10px] text-slate-500">{field.split("_")[0]}<input type="number" min={0} value={rule[field]} onChange={event => updateRule(componentType, field, Number(event.target.value))} className="mt-1 w-full rounded border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-slate-200" /></label>)}<button type="button" onClick={() => void saveRule(componentType)} disabled={savingRule === componentType} className="flex h-9 cursor-pointer items-center justify-center rounded border border-cyan-300/20 text-cyan-300 hover:bg-cyan-300/10"><Save className="h-4 w-4" /></button></div>; })}</div></section>
    </div>
  );
}

function Metric({ label, value, tone = "text-cyan-300" }: { label: string; value: string; tone?: string }) {
  return <div className="rounded-xl border border-white/10 bg-[#07101c] p-4"><p className="text-xs text-slate-500">{label}</p><p className={`mt-1 text-2xl font-bold ${tone}`}>{value}</p></div>;
}
