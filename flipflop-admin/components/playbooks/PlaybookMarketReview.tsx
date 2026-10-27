"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { bookMoney, type BookCell } from "@/lib/playbook-book";

export type MarketReview = {
  batch_id: number | null;
  stale: boolean;
  decision: string | null;
  components: Record<string, string>;
  approved: { sold_median_gbp: string; sold_sample_size: number; active_median_gbp: string | null } | null;
  batch: {
    observed_at: string;
    errors: string[];
    candidates: { id: string; kind: string; title: string; url: string | null;
      condition: string; total_gbp: string | null; sold_at: string | null; blockers: string[] }[];
  } | null;
};

export default function PlaybookMarketReview({ cell, onUpdated }: {cell: BookCell; onUpdated: () => void}) {
  const [review, setReview] = useState<MarketReview | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const load = useCallback(async () => {
    if (!cell.playbook_id) return;
    try { setReview(await api.commercialReadiness.market(cell.playbook_id, cell.cell_id)); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load market evidence"); }
  }, [cell.playbook_id, cell.cell_id]);
  useEffect(() => { void load(); }, [load]);
  async function act(decision: "collect" | "approve" | "reject") {
    if (!cell.playbook_id) return;
    setBusy(true); setError(null);
    try {
      const result = decision === "collect"
        ? await api.commercialReadiness.collectMarket(cell.playbook_id, cell.cell_id)
        : await api.commercialReadiness.reviewMarket(cell.playbook_id, cell.cell_id, {
          batch_id: review!.batch_id!, decision, candidate_ids: selected, exact_build_confirmed: confirmed,
        });
      setReview(result); setSelected([]); setConfirmed(false); onUpdated();
    } catch(e) { setError(e instanceof Error ? e.message : "Market action failed"); }
    finally { setBusy(false); }
  }
  const soldCount = selected.filter(id => id.startsWith("sold:")).length;
  async function recalculate() {
    setBusy(true); setError(null);
    try {
      const job = await api.commercialReadiness.rebuildProposals();
      setMessage(job.started ? "Recalculation started. Review the refreshed prices when the rebuild finishes in Automation health." : "A rebuild or refresh is already running. Check Automation health before reviewing new prices.");
    } catch(e) { setError(e instanceof Error ? e.message : "Could not recalculate proposals"); }
    finally { setBusy(false); }
  }
  return <section className="space-y-3 rounded border border-white/15 p-4" aria-label="Exact build market review">
    <h4 className="font-semibold">Exact build market review</h4>
    <p className="text-sm text-slate-400">Collect new complete PCs for this selected build. Open each source and compare every component below. Select only matching complete builds; asking prices remain separate from sold prices.</p>
    {error && <p role="alert" className="text-amber-200">{error}</p>}
    {message && <p role="status" className="text-cyan-200">{message}</p>}
    <button type="button" disabled={busy || !cell.playbook_id} onClick={() => void act("collect")} className="rounded border border-cyan-400/40 px-3 py-2 disabled:opacity-50">{busy ? "Working…" : "Collect market comparisons"}</button>
    {review && <>
      <details><summary>Selected build specifications</summary><dl className="text-sm">{Object.entries(review.components).map(([role,title]) => <div key={role}><dt className="inline text-slate-400">{role}: </dt><dd className="inline">{title}</dd></div>)}</dl></details>
      {!review.batch && <p className="text-sm text-slate-400">No comparisons collected for this cell yet.</p>}
      {review.stale && <p className="text-amber-200">The build changed or these observations expired. Collect again before reviewing.</p>}
      {review.decision && <p className="text-sm">Collection decision: {review.decision.replace("market_", "")}. Collect again to submit another review.</p>}
      {review.approved && <button type="button" disabled={busy} onClick={() => void recalculate()} className="rounded border border-cyan-400/40 px-3 py-2 disabled:opacity-50">Recalculate proposals with approved market evidence</button>}
      {review.batch && <>
        <p className="text-xs text-slate-400">Collected {new Date(review.batch.observed_at).toLocaleString("en-GB")}. Prices include delivery.</p>
        {review.batch.errors.map(message => <p className="text-sm text-amber-200" key={message}>{message}</p>)}
        {review.batch.candidates.length === 0 && <p>No provider comparisons available. No market price has been invented.</p>}
        <div className="max-h-96 space-y-2 overflow-y-auto">{review.batch.candidates.map(row => <label key={row.id} className="flex gap-3 rounded border border-white/10 p-3 text-sm">
          <input type="checkbox" aria-label={`Confirm comparable: ${row.title}`} checked={selected.includes(row.id)} disabled={busy || review.stale || !!review.decision || row.blockers.length > 0} onChange={e => setSelected(ids => e.target.checked ? [...ids,row.id] : ids.filter(id => id !== row.id))}/>
          <span className="min-w-0"><span className="block">{row.kind === "sold" ? "Sold" : "Current asking price"} · {bookMoney(row.total_gbp)} · {row.condition}</span>
            {row.url ? <a href={row.url} target="_blank" rel="noreferrer" className="text-cyan-200 underline">{row.title}</a> : row.title}
            {row.sold_at && <span className="block text-slate-400">Sold: {row.sold_at}</span>}
            {row.blockers.map(reason => <span className="block text-amber-200" key={reason}>{reason}</span>)}
          </span>
        </label>)}</div>
        {!review.decision && <>
          <label className="flex gap-2 text-sm"><input type="checkbox" checked={confirmed} disabled={busy || review.stale} onChange={e => setConfirmed(e.target.checked)}/>I checked the source listings: each selected item is a complete new PC matching every selected build component, including software, and each sold price is the actual completed sale price.</label>
          <p className="text-xs text-slate-400">{soldCount} sold comparisons selected; at least 3 required. Approval records market evidence for the next calculated proposal. Final build publication still requires its existing checks and approval.</p>
          <div className="flex gap-3"><button type="button" disabled={busy || review.stale || !confirmed || soldCount < 3} onClick={() => void act("approve")} className="rounded border border-cyan-400/40 px-3 py-2 disabled:opacity-50">Approve selected market evidence</button>
          <button type="button" disabled={busy || review.stale} onClick={() => void act("reject")} className="rounded border border-white/20 px-3 py-2 disabled:opacity-50">Reject this collection</button></div>
        </>}
      </>}
    </>}
  </section>;
}
