"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";

type Evidence = { id: string; filename: string; content_type: string; size_bytes: number; sha256: string; uploaded_at: string };
type RepairTracking = { purpose: "customer_return" | "replacement"; carrier: string; tracking_number: string; tracking_url: string; events?: Array<{status_code: string; description: string; occurred_at: string; location?: string | null; tracking_url?: string | null}> };
type RepairShipment = { id: number; purpose: "customer_return" | "replacement"; carrier: string; tracking_number: string; tracking_url: string | null; provider_reference?: string | null; events: Array<{status_code: string; description: string; occurred_at: string}> };
type Problem = { id: number; order_id: number | null; manual_build_id?: number | null; category: string; description: string; status: string; created_at: string; evidence: Evidence[]; repair_tracking?: RepairTracking | null; repair_tracking_provider_reference?: string | null; repair_shipments?: RepairShipment[] };
const supportStatuses = ["received", "reviewing", "claim_opened", "resolved", "closed"];
const warrantyStatuses = ["received", "reviewing", "claim_opened", "approved", "awaiting_customer_return", "return_in_transit", "received_for_inspection", "repair_in_progress", "waiting_for_parts", "replacement_ordered", "replacement_dispatched", "resolved", "rejected", "closed"];
const warrantyCategories = new Set(["warranty", "warranty_claim", "repair", "technical_fault"]);

export default function ProblemsPage() {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<number | null>(null);
  const [trackingDrafts, setTrackingDrafts] = useState<Record<number, {carrier: string; tracking_number: string; tracking_url: string; provider_reference: string}>>({});

  const load = async () => {
    try {
      const response = await fetch("/api/admin/customer-problems", { cache: "no-store" });
      if (!response.ok) throw new Error(`Could not load problem reports (${response.status})`);
      const items: Problem[] = await response.json();
      setProblems(items);
      setTrackingDrafts((current) => Object.fromEntries(items.map((item) => {
        const purpose = item.repair_tracking?.purpose || (item.status === "replacement_dispatched" ? "replacement" : "customer_return");
        const shipment = item.repair_shipments?.find((candidate) => candidate.purpose === purpose);
        return [item.id, current[item.id] ?? {
          carrier: shipment?.carrier || item.repair_tracking?.carrier || "",
          tracking_number: shipment?.tracking_number || item.repair_tracking?.tracking_number || "",
          tracking_url: shipment?.tracking_url || item.repair_tracking?.tracking_url || "",
          provider_reference: shipment?.provider_reference || item.repair_tracking_provider_reference || "",
        }];
      })) as Record<number, {carrier: string; tracking_number: string; tracking_url: string; provider_reference: string}>);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load problem reports"); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const updateStatus = async (id: number, status: string) => {
    setSaving(id);
    try {
      const response = await fetch(`/api/admin/customer-problems/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) });
      if (!response.ok) throw new Error(`Could not update report (${response.status})`);
      const updated = await response.json();
      setProblems((current) => current.map((item) => item.id === id ? updated : item));
      const purpose = status === "return_in_transit" ? "customer_return" : status === "replacement_dispatched" ? "replacement" : null;
      if (purpose) {
        const shipment = (updated.repair_shipments || []).find((item: RepairShipment) => item.purpose === purpose);
        setTrackingDrafts((current) => ({ ...current, [id]: {
          carrier: shipment?.carrier || "",
          tracking_number: shipment?.tracking_number || "",
          tracking_url: shipment?.tracking_url || "",
          provider_reference: shipment?.provider_reference || "",
        } }));
      }
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update problem report"); }
    finally { setSaving(null); }
  };

  const saveRepairTracking = async (problem: Problem) => {
    const draft = trackingDrafts[problem.id];
    if (!draft?.carrier.trim() || !draft.tracking_number.trim() || !draft.tracking_url.trim()) {
      setError("Enter the carrier, tracking number and tracking link.");
      return;
    }
    if (!draft.tracking_url.trim().startsWith("https://")) {
      setError("Repair tracking links must use HTTPS.");
      return;
    }
    const note = window.prompt("Record how you verified this repair shipment tracking (at least 12 characters).")?.trim();
    if (!note || note.length < 12) return;
    setSaving(problem.id);
    try {
      const response = await fetch(`/api/admin/customer-problems/${problem.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: problem.status,
          repair_tracking_purpose: problem.status === "return_in_transit" ? "customer_return" : "replacement",
          repair_carrier: draft.carrier.trim(),
          repair_tracking_number: draft.tracking_number.trim(),
          repair_tracking_url: draft.tracking_url.trim(),
          repair_tracking_provider_reference: draft.provider_reference.trim() || null,
          repair_tracking_note: note,
        }),
      });
      if (!response.ok) throw new Error(`Could not save repair tracking (${response.status})`);
      const updated: Problem = await response.json();
      setProblems((current) => current.map((item) => item.id === problem.id ? updated : item));
      setError(null);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save repair tracking"); }
    finally { setSaving(null); }
  };

  return <main className="mx-auto max-w-6xl p-6 text-slate-100">
    <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-3"><AlertTriangle className="h-6 w-6 text-amber-300" /><div><h1 className="text-2xl font-bold">Customer problems</h1><p className="text-sm text-slate-400">Delivery, warranty and support reports submitted from customer portals.</p></div></div>
      <Link href="/warranty-reserves" className="rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-sm font-semibold text-cyan-200">Review warranty reserves</Link>
    </div>
    {error && <p role="alert" className="mb-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
    {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : problems.length === 0 ? <p className="rounded border border-white/10 p-6 text-sm text-slate-400">No customer problem reports have been submitted.</p> : <div className="space-y-4">
      {problems.map((problem) => {
        const isWarranty = warrantyCategories.has(problem.category.trim().toLowerCase());
        const statuses = isWarranty ? warrantyStatuses : supportStatuses;
        return <article key={problem.id} className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><p className="text-xs uppercase tracking-wider text-amber-200">{problem.category.replace(/_/g, " ")} · {problem.order_id ? `Order #${problem.order_id}` : `Build #${problem.manual_build_id ?? "unknown"}`}</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-200">{problem.description}</p><p className="mt-3 text-xs text-slate-500">Received {new Date(problem.created_at).toLocaleString("en-GB")}</p></div>
            <select aria-label={`Status for problem ${problem.id}`} value={problem.status} disabled={saving === problem.id} onChange={(event) => void updateStatus(problem.id, event.target.value)} className="rounded border border-white/10 bg-slate-900 px-3 py-2 text-xs text-slate-100">{statuses.map((status) => <option key={status} value={status}>{status.replace(/_/g, " ")}</option>)}</select>
          </div>
          {isWarranty && <div className="mt-4 rounded-lg border border-cyan-400/20 bg-cyan-400/[0.04] p-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-cyan-200">Repair shipment tracking</p>
            {(problem.repair_shipments || []).map((shipment) => <div key={shipment.id} className="mt-2 rounded border border-white/10 p-2 text-xs"><p className="font-semibold text-slate-200">{shipment.purpose === "customer_return" ? "Customer return to FlipFlop" : "Repaired or replacement PC to customer"}</p><p className="mt-1 text-slate-300">{shipment.carrier} · {shipment.tracking_number}{shipment.provider_reference ? ` · Parcel2Go ${shipment.provider_reference}` : ""}</p><p className="mt-1 text-slate-400">{shipment.events?.[0]?.description || "Waiting for courier updates"}</p></div>)}
            {problem.repair_tracking && <><p className="mt-2 text-xs text-slate-300">{problem.repair_tracking.purpose === "replacement" ? "Replacement" : "Customer return"}: {problem.repair_tracking.carrier} · {problem.repair_tracking.tracking_number} · <a href={problem.repair_tracking.tracking_url} target="_blank" rel="noreferrer" className="text-cyan-200 underline">Track parcel</a></p>{problem.repair_tracking.events?.[0] && <p className="mt-1 text-xs text-slate-400">Latest courier update: {problem.repair_tracking.events[0].description}</p>}</>}
            {(problem.status === "return_in_transit" || problem.status === "replacement_dispatched") && <>
            <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
              <input aria-label={`Repair carrier for problem ${problem.id}`} value={trackingDrafts[problem.id]?.carrier || ""} onChange={(event) => setTrackingDrafts((current) => ({ ...current, [problem.id]: {carrier: event.target.value, tracking_number: current[problem.id]?.tracking_number || "", tracking_url: current[problem.id]?.tracking_url || "", provider_reference: current[problem.id]?.provider_reference || ""} }))} placeholder="Carrier" className="rounded border border-white/10 bg-slate-900 px-3 py-2 text-xs" />
              <input aria-label={`Repair tracking number for problem ${problem.id}`} value={trackingDrafts[problem.id]?.tracking_number || ""} onChange={(event) => setTrackingDrafts((current) => ({ ...current, [problem.id]: {carrier: current[problem.id]?.carrier || "", tracking_number: event.target.value, tracking_url: current[problem.id]?.tracking_url || "", provider_reference: current[problem.id]?.provider_reference || ""} }))} placeholder="Tracking number" className="rounded border border-white/10 bg-slate-900 px-3 py-2 text-xs" />
              <input aria-label={`Repair tracking URL for problem ${problem.id}`} value={trackingDrafts[problem.id]?.tracking_url || ""} onChange={(event) => setTrackingDrafts((current) => ({ ...current, [problem.id]: {carrier: current[problem.id]?.carrier || "", tracking_number: current[problem.id]?.tracking_number || "", tracking_url: event.target.value, provider_reference: current[problem.id]?.provider_reference || ""} }))} placeholder="https://carrier.example/track/..." className="rounded border border-white/10 bg-slate-900 px-3 py-2 text-xs" />
              <input aria-label={`Parcel2Go OrderLineId for problem ${problem.id}`} value={trackingDrafts[problem.id]?.provider_reference || ""} onChange={(event) => setTrackingDrafts((current) => ({ ...current, [problem.id]: {carrier: current[problem.id]?.carrier || "", tracking_number: current[problem.id]?.tracking_number || "", tracking_url: current[problem.id]?.tracking_url || "", provider_reference: event.target.value} }))} placeholder="Parcel2Go OrderLineId (optional)" className="rounded border border-white/10 bg-slate-900 px-3 py-2 text-xs" />
            </div>
            <button type="button" disabled={saving === problem.id} onClick={() => void saveRepairTracking(problem)} className="mt-3 rounded border border-cyan-300/40 px-3 py-2 text-xs font-semibold text-cyan-100 disabled:opacity-50">Save tracking details</button>
            <p className="mt-2 text-[10px] text-slate-500">Each purpose is retained as its own shipment leg. Add that parcel’s Parcel2Go OrderLineId to sync its courier stages; only a delivered customer return advances the case to inspection.</p>
            </>}
          </div>}
          {problem.evidence?.length > 0 && <div className="mt-4 rounded-lg border border-cyan-400/20 bg-cyan-400/[0.04] p-3"><p className="text-xs font-semibold uppercase tracking-wider text-cyan-200">Customer evidence ({problem.evidence.length})</p><ul className="mt-2 space-y-1">{problem.evidence.map((item) => <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 text-xs"><span className="text-slate-300">{item.filename} · {Math.ceil(item.size_bytes / 1024)} KB · {new Date(item.uploaded_at).toLocaleString("en-GB")}</span><a href={`/api/admin/customer-problems/${problem.id}/evidence/${item.id}`} className="text-cyan-200 underline" target="_blank" rel="noreferrer">Download</a></li>)}</ul></div>}
          {problem.status === "resolved" && <p className="mt-4 flex items-center gap-2 text-xs text-emerald-300"><CheckCircle2 className="h-4 w-4" /> Resolved</p>}
        </article>;
      })}
    </div>}
  </main>;
}
