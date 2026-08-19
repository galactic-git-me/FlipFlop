"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

type Problem = { id: number; order_id: number; category: string; description: string; status: string; created_at: string };
const statuses = ["received", "reviewing", "claim_opened", "resolved", "closed"];

export default function ProblemsPage() {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<number | null>(null);

  const load = async () => {
    try { const response = await fetch("/api/admin/customer-problems"); if (!response.ok) throw new Error(`Could not load problem reports (${response.status})`); setProblems(await response.json()); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not load problem reports"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const updateStatus = async (id: number, status: string) => {
    setSaving(id);
    try { const response = await fetch(`/api/admin/customer-problems/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) }); if (!response.ok) throw new Error(`Could not update report (${response.status})`); const updated = await response.json(); setProblems((current) => current.map((item) => item.id === id ? updated : item)); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not update problem report"); }
    finally { setSaving(null); }
  };

  return <main className="mx-auto max-w-6xl p-6 text-slate-100"><div className="mb-8 flex items-center gap-3"><AlertTriangle className="h-6 w-6 text-amber-300" /><div><h1 className="text-2xl font-bold">Customer problems</h1><p className="text-sm text-slate-400">Delivery, warranty and support reports submitted from customer portals.</p></div></div>{error && <p role="alert" className="mb-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}{loading ? <Loader2 className="h-5 w-5 animate-spin" /> : problems.length === 0 ? <p className="rounded border border-white/10 p-6 text-sm text-slate-400">No customer problem reports have been submitted.</p> : <div className="space-y-4">{problems.map((problem) => <article key={problem.id} className="rounded-xl border border-white/10 bg-white/[0.03] p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-wider text-amber-200">{problem.category.replace(/_/g, " ")} · Order #{problem.order_id}</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-200">{problem.description}</p><p className="mt-3 text-xs text-slate-500">Received {new Date(problem.created_at).toLocaleString("en-GB")}</p></div><select aria-label={`Status for problem ${problem.id}`} value={problem.status} disabled={saving === problem.id} onChange={(event) => updateStatus(problem.id, event.target.value)} className="rounded border border-white/10 bg-slate-900 px-3 py-2 text-xs text-slate-100">{statuses.map((status) => <option key={status} value={status}>{status.replace(/_/g, " ")}</option>)}</select></div>{problem.status === "resolved" && <p className="mt-4 flex items-center gap-2 text-xs text-emerald-300"><CheckCircle2 className="h-4 w-4" /> Resolved</p>}</article>)}</div>}</main>;
}
