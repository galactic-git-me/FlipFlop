"use client";

import { useEffect, useState } from "react";
import { Banknote, Loader2, ShieldCheck } from "lucide-react";

type Claim = { id: number; status: string; issue_summary: string; approved_cost_gbp: number; outcome?: string | null };
type Reserve = {
  id: number; order_id: number | null; manual_build_id: number | null;
  reserved_amount_gbp: number; allocated_claim_amount_gbp: number;
  available_amount_gbp: number; released_amount_gbp: number; reserve_pct: number;
  status: string; warranty_started_at: string; warranty_expires_at: string; claims: Claim[];
};

const money = (value: number) => new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(value);

export default function WarrantyReservesPage() {
  const [rows, setRows] = useState<Reserve[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const load = async () => {
    try {
      const response = await fetch("/api/admin/warranty-reserves", { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Could not load warranty reserves");
      setRows(payload);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load warranty reserves"); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const release = async (row: Reserve) => {
    const note = window.prompt("Release note (required):", "12-month warranty elapsed; no open claims.");
    if (!note) return;
    if (!window.confirm(`Release ${money(row.available_amount_gbp)} from reserve ${row.id}?`)) return;
    setBusy(row.id); setError("");
    try {
      const response = await fetch(`/api/admin/warranty-reserves/${row.id}/release`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm_release: true, note }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Reserve release failed");
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Reserve release failed"); }
    finally { setBusy(null); }
  };

  const updateClaim = async (claim: Claim) => {
    const status = window.prompt("Claim status: open, reviewing, approved, awaiting_customer_return, return_in_transit, received_for_inspection, repair_in_progress, waiting_for_parts, replacement_ordered, replacement_dispatched, resolved, rejected or closed", claim.status);
    if (!status) return;
    const costText = window.prompt("Approved warranty cost (£):", String(claim.approved_cost_gbp));
    if (costText == null) return;
    const approvedCost = Number(costText);
    if (!Number.isFinite(approvedCost) || approvedCost < 0) { setError("Approved cost must be zero or more"); return; }
    const outcome = window.prompt("Outcome or workshop note (optional):", claim.outcome || "");
    setBusy(claim.id); setError("");
    try {
      const response = await fetch(`/api/admin/warranty-claims/${claim.id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, approved_cost_gbp: approvedCost, outcome: outcome || null }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Claim update failed");
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Claim update failed"); }
    finally { setBusy(null); }
  };

  const held = rows.filter(row => row.status !== "released").reduce((sum, row) => sum + row.available_amount_gbp, 0);
  const eligible = rows.filter(row => row.status === "eligible_for_release").reduce((sum, row) => sum + row.available_amount_gbp, 0);
  return <main className="mx-auto max-w-7xl space-y-6 p-6 text-slate-100">
    <header><p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-300">Aftercare finance</p><h1 className="mt-2 flex items-center gap-3 text-3xl font-bold"><ShieldCheck className="h-7 w-7"/>Warranty reserves</h1><p className="mt-2 text-sm text-slate-400">Reserves become eligible after twelve months only when no claim remains open. Release always requires your confirmation.</p></header>
    {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
    <section className="grid gap-3 sm:grid-cols-3"><Summary label="Currently held" value={money(held)}/><Summary label="Eligible for review" value={money(eligible)}/><Summary label="Reserve records" value={String(rows.length)}/></section>
    {loading ? <Loader2 className="h-5 w-5 animate-spin"/> : rows.length === 0 ? <p className="rounded-xl border border-white/10 p-6 text-sm text-slate-400">No delivered sales have created a warranty reserve yet.</p> : <section className="space-y-3">{rows.map(row => <article key={row.id} className="rounded-xl border border-white/10 bg-white/[.03] p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="font-semibold">{row.order_id ? `Order #${row.order_id}` : `Ready-to-Ship build #${row.manual_build_id}`}</p><p className="mt-1 text-xs text-slate-400">{row.reserve_pct}% reserved · {new Date(row.warranty_started_at).toLocaleDateString("en-GB")} to {new Date(row.warranty_expires_at).toLocaleDateString("en-GB")}</p></div><span className="rounded-full border border-white/10 px-3 py-1 text-xs text-cyan-200">{row.status.replaceAll("_", " ")}</span></div><div className="mt-4 grid gap-2 text-sm sm:grid-cols-4"><Amount label="Reserved" value={row.reserved_amount_gbp}/><Amount label="Claims allocated" value={row.allocated_claim_amount_gbp}/><Amount label="Available" value={row.available_amount_gbp}/><Amount label="Released" value={row.released_amount_gbp}/></div>{row.claims.length > 0 && <div className="mt-4 space-y-2">{row.claims.map(claim => <div key={claim.id} className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-black/20 p-3 text-xs"><div><span className="font-semibold text-amber-200">Claim {claim.id} · {claim.status.replaceAll("_", " ")} · {money(claim.approved_cost_gbp)}</span><p className="mt-1 text-slate-300">{claim.issue_summary}</p>{claim.outcome && <p className="mt-1 text-slate-500">{claim.outcome}</p>}</div><button disabled={busy !== null} onClick={() => void updateClaim(claim)} className="rounded border border-white/10 px-2.5 py-1.5 font-semibold text-cyan-200 disabled:opacity-50">Review claim</button></div>)}</div>}{row.status === "eligible_for_release" && <button disabled={busy !== null} onClick={() => void release(row)} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-emerald-400 px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50">{busy === row.id ? <Loader2 className="h-4 w-4 animate-spin"/> : <Banknote className="h-4 w-4"/>}Review and release</button>}</article>)}</section>}
  </main>;
}

function Summary({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-white/10 bg-white/[.03] p-4"><p className="text-xs uppercase tracking-wider text-slate-500">{label}</p><p className="mt-2 text-2xl font-bold">{value}</p></div>; }
function Amount({ label, value }: { label: string; value: number }) { return <div className="rounded-lg bg-black/20 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 font-semibold">{money(value)}</p></div>; }
