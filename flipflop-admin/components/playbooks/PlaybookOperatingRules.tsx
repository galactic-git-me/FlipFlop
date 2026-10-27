"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
export type MvpRules = { cells: {cell_id:string;name:string;enabled:boolean;budget_ceiling:number|null}[]; approved_suppliers:string[]; max_price_change_fraction:number };
export default function PlaybookOperatingRules({ onUpdated }: {onUpdated:()=>void}) {
  const [rules, setRules] = useState<MvpRules|null>(null);
  const [budgets, setBudgets] = useState<Record<string, string>>({});
  const [movement, setMovement] = useState("10");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.commercialReadiness.mvpRules().then(data => {
    setRules(data); setBudgets(Object.fromEntries(data.cells.map(cell => [cell.cell_id,cell.budget_ceiling == null ? "" : String(cell.budget_ceiling)])));
    setMovement(String(data.max_price_change_fraction * 100));
  }).catch(reason => setError(reason instanceof Error ? reason.message : "Could not load operating rules")); }, []);
  const save = async (enabled: boolean) => {
    setBusy(true); setError(""); setNotice("");
    try {
      const budget_ceilings = Object.fromEntries(Object.entries(budgets).filter(([,value]) => value.trim()).map(([id,value]) => [id,Number(value)]));
      if (Object.values(budget_ceilings).some(value => !Number.isFinite(value) || value <= 0)) throw new Error("Budget ceilings must be positive amounts");
      if (!Number.isFinite(Number(movement)) || Number(movement) <= 0 || Number(movement) > 25) throw new Error("Choose a price movement between 0 and 25 percent");
      await api.commercialReadiness.saveMvpRules({enabled,budget_ceilings,max_price_change_fraction:Number(movement)/100});
      setRules(current => current && ({...current,cells:current.cells.map(cell => ({...cell,enabled}))}));
      setNotice(enabled ? "Automatic maintenance enabled. A local proposal rebuild is queued. Cells without a budget ceiling remain paused." : "Automatic publication paused. Existing valid customer offers are unchanged.");
      onUpdated();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save operating rules"); }
    finally { setBusy(false); }
  };
  return <details className="rounded-lg border border-white/15 p-3"><summary className="cursor-pointer text-sm text-slate-300">Operating rules · one-time setup</summary>
    <div className="mt-3 space-y-3 text-sm">
      <p>Automatic publication requires current supplier evidence, verified fit, approved product photos, the existing profit floors and a budget ceiling. The MVP offers one base build and Standard delivery. Model approval always stays with you.</p>
      {rules && <>
        <p className="text-slate-400">Approved suppliers: {rules.approved_suppliers.join(", ")}. Existing profit floors: Budget £60 / 10%, Mid-range £100 / 12%, High-end £175 / 15%.</p>
        <label className="block">Maximum price movement from the approved baseline (%) <input type="number" min="0.1" max="25" step="0.1" value={movement} onChange={event => setMovement(event.target.value)} className="ml-2 w-20 rounded border border-white/20 bg-slate-900 p-2" /></label>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{rules.cells.map(cell => <label key={cell.cell_id} className="text-xs">{cell.name} · maximum £<input aria-label={`${cell.name} budget ceiling`} type="number" min="1" step="0.01" value={budgets[cell.cell_id] ?? ""} onChange={event => setBudgets(current => ({...current,[cell.cell_id]:event.target.value}))} className="mt-1 w-full rounded border border-white/20 bg-slate-900 p-2" /></label>)}</div>
        <p className="text-xs text-slate-400">Blank budgets keep those cells paused. Saving resets price baselines to the current published offers. Unknown facts never become approved facts.</p>
        <div className="flex gap-2"><button disabled={busy} onClick={() => void save(true)} className="rounded bg-cyan-400 px-3 py-2 text-slate-950 disabled:opacity-40">Save rules & enable automatic maintenance</button><button disabled={busy} onClick={() => void save(false)} className="rounded border border-white/20 px-3 py-2 disabled:opacity-40">Pause automatic publication</button></div>
      </>}
      {error && <p role="alert" className="text-rose-200">{error}</p>}{notice && <p role="status" className="text-emerald-200">{notice}</p>}
    </div>
  </details>;
}
