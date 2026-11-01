"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

type Generation = { status?: string; progress?: number; task_id?: string | null; error?: string | null; updated_at?: string };
type QueueItem = {
  variant_id: number; listing_id: number; title: string; category: string; media_family_key?: string;
  asset_media_review?: { generation?: Generation } | null;
  asset?: { id: number; status?: string; review_decision?: string | null; glb_ref?: string | null; review_batch_id?: string | null } | null;
};
const running = new Set(["QUEUED", "PREPARING", "STARTING", "RESUMING", "SUBMITTED", "PENDING", "IN_PROGRESS", "PUBLISHING", "SUCCEEDED"]);
const failed = (status: string) => ["FAILED", "TIMED_OUT", "CANCELED", "SOURCE_IMAGES_INVALID", "CONFIGURATION_ERROR", "SUBMIT_FAILED"].includes(status) || status.startsWith("SUBMIT_REJECTED_");
const finished = (item: QueueItem) => {
  const status = item.asset_media_review?.generation?.status || "";
  return status === "DRAFT_CREATED" || failed(status);
};
const modelReviewed = (item: QueueItem) => item.asset?.review_decision === "approved" || item.asset?.review_decision === "rejected";
const queueEntryVersion = (item: QueueItem) => {
  const generation = item.asset_media_review?.generation;
  return JSON.stringify([item.variant_id, generation?.task_id, generation?.status, generation?.updated_at, generation?.error]);
};
const labels: Record<string, string> = {
  QUEUED: "Queued by app", PREPARING: "Preparing approved photo", STARTING: "Submitting to Meshy",
  RESUMING: "Resuming existing task", SUBMITTED: "Submitted to Meshy", PENDING: "Waiting in Meshy queue",
  IN_PROGRESS: "Generating", SUCCEEDED: "Generated · preparing download", PUBLISHING: "Saving textured GLB",
  DRAFT_CREATED: "Ready for approval", FAILED: "Failed", TIMED_OUT: "Polling timed out", CANCELED: "Cancelled",
};

export default function MeshyGenerationQueue({ refreshKey }: { refreshKey: number }) {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastChecked, setLastChecked] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [retrying, setRetrying] = useState<Set<number>>(new Set());
  const [retryMessages, setRetryMessages] = useState<Record<number, { error: boolean; text: string }>>({});
  const retryLocks = useRef(new Set<number>());
  const inFlight = useRef(false);
  const dismissedEntries = useRef(new Set<string>());
  const clearFinishedOnRefresh = useRef(false);
  const mounted = useRef(false);
  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const response = await fetch("/api/assets-3d/catalogue/generation-queue", { cache: "no-store", signal: AbortSignal.timeout(20000) });
      const rows = await response.json();
      if (!response.ok || !Array.isArray(rows)) throw new Error(rows.detail || "Could not refresh the model queue");
      const unique = new Map<string, QueueItem>();
      for (const item of rows as QueueItem[]) {
        const generation = item.asset_media_review?.generation;
        if (!generation?.status) continue;
        const key = generation.task_id || `${item.category}:${item.media_family_key || item.listing_id}`;
        if (!unique.has(key)) unique.set(key, item);
      }
      if (mounted.current) {
        if (clearFinishedOnRefresh.current) {
          for (const item of unique.values()) if (finished(item)) dismissedEntries.current.add(queueEntryVersion(item));
          clearFinishedOnRefresh.current = false;
        }
        setItems([...unique.values()].filter(item => !modelReviewed(item) && (!finished(item) || !dismissedEntries.current.has(queueEntryVersion(item)))).sort((a, b) => Number(running.has(b.asset_media_review?.generation?.status || "")) - Number(running.has(a.asset_media_review?.generation?.status || "")) || a.title.localeCompare(b.title)));
        setLastChecked(new Date().toLocaleTimeString()); setError("");
      }
    } catch (reason) {
      if (mounted.current) setError(reason instanceof Error ? reason.message : "Could not refresh the model queue");
    } finally {
      inFlight.current = false;
      if (mounted.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => { mounted.current = false; window.clearInterval(timer); };
  }, [refresh]);
  useEffect(() => { void refresh(); }, [refreshKey, refresh]);
  const refreshAndClear = () => {
    clearFinishedOnRefresh.current = true;
    for (const item of items) if (finished(item)) dismissedEntries.current.add(queueEntryVersion(item));
    setItems(current => current.filter(item => !finished(item)));
    setRetryMessages({});
    void refresh();
  };
  const retry = async (item: QueueItem) => {
    if (retryLocks.current.has(item.variant_id)) return;
    retryLocks.current.add(item.variant_id);
    setRetrying(current => new Set(current).add(item.variant_id));
    setRetryMessages(current => { const next = { ...current }; delete next[item.variant_id]; return next; });
    const generation = item.asset_media_review?.generation;
    const resumeSave = generation?.status === "FAILED" && generation.task_id
      && generation.error?.startsWith("Model generated but could not be saved:");
    try {
      const response = await fetch(`/api/assets-3d/variants/${item.variant_id}/${resumeSave ? "generate" : "auto-prepare"}`, {
        method: "POST", headers: { "content-type": "application/json" }, body: "{}", signal: AbortSignal.timeout(30000),
      });
      const result = await response.json().catch(() => ({ detail: `Retry failed (${response.status})` }));
      if (!response.ok) throw new Error(result.detail || "Could not retry model generation");
      if (mounted.current) {
        setItems(current => current.map(row => row.variant_id === item.variant_id ? {
          ...row, asset_media_review: { ...row.asset_media_review, generation: {
            ...generation, status: resumeSave || (generation?.status === "TIMED_OUT" && generation.task_id) ? "RESUMING" : "PREPARING", error: null,
          } },
        } : row));
        setRetryMessages(current => ({ ...current, [item.variant_id]: { error: false, text: "Retry accepted. Progress will update here." } }));
        await refresh();
      }
    } catch (reason) {
      if (mounted.current) setRetryMessages(current => ({ ...current, [item.variant_id]: {
        error: true, text: reason instanceof Error ? reason.message : "Could not retry model generation",
      } }));
    } finally {
      retryLocks.current.delete(item.variant_id);
      if (mounted.current) setRetrying(current => { const next = new Set(current); next.delete(item.variant_id); return next; });
    }
  };
  const activeCount = items.filter(item => running.has(item.asset_media_review?.generation?.status || "")).length;
  const completedCount = items.filter(item => item.asset_media_review?.generation?.status === "DRAFT_CREATED" && item.asset?.review_decision == null).length;
  return <section aria-label="Meshy model queue" className="shrink-0 overflow-hidden rounded-lg border border-cyan-400/30 bg-slate-950/95 text-sm text-slate-100">
    <header className="flex flex-wrap items-center gap-3 px-4 py-2">
      <button type="button" aria-expanded={expanded} aria-controls="meshy-generation-progress" onClick={() => setExpanded(value => !value)} className="rounded border border-cyan-400/40 px-3 py-2 font-semibold text-cyan-200 hover:bg-cyan-400/10">{expanded ? "▾ Hide progress" : "▸ Show progress"}</button>
      <span className="font-semibold text-cyan-200">Meshy model queue</span>
      <span>{activeCount} active · {completedCount} ready for approval</span>
      <span className="text-xs text-slate-400">Catalogue jobs submitted by this app</span>
      <span className="text-xs text-slate-400">Updates every 5 seconds{lastChecked ? ` · checked ${lastChecked}` : ""}</span>
      <button type="button" onClick={refreshAndClear} title="Refresh active jobs and clear completed or failed entries from this view" className="ml-auto rounded border border-slate-600 px-2 py-1">Refresh queue</button>
    </header>
    {expanded && <div id="meshy-generation-progress" className="max-h-56 overflow-auto border-t border-slate-700">
      {error && <p role="alert" className="px-4 py-2 text-rose-200">Queue update failed: {error}. Last known statuses are retained.</p>}
      {loading ? <p role="status" className="px-4 py-3">Loading submitted model jobs…</p> : !items.length ? <p className="px-4 py-3 text-slate-400">No model jobs to show. Completed and failed jobs can be cleared with Refresh queue.</p> : <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-slate-900"><tr><th className="px-4 py-2">Model</th><th className="px-3 py-2">Status</th><th className="min-w-40 px-3 py-2">Complete</th><th className="px-3 py-2">Details</th></tr></thead>
        <tbody>{items.map(item => {
          const generation = item.asset_media_review!.generation!;
          const status = generation.status || "UNKNOWN";
          const progress = status === "DRAFT_CREATED" ? 100 : Math.max(0, Math.min(100, Number(generation.progress) || 0));
          return <tr key={`${item.category}:${item.variant_id}`} className="border-t border-slate-800 align-top">
            <td className="max-w-64 px-4 py-2"><p className="line-clamp-2 font-medium" title={item.title}>{item.title}</p><p className="text-slate-400">{item.category}</p></td>
            <td className="px-3 py-2">{labels[status] || status.replaceAll("_", " ").toLowerCase()}</td>
            <td className="px-3 py-2"><span>{progress}%</span><progress aria-label={`${item.title} generation progress`} className="mt-1 block h-2 w-full accent-cyan-400" value={progress} max={100} /></td>
            <td className="max-w-80 px-3 py-2">{generation.error && <p className="break-words text-rose-200">{generation.error}</p>}
              {failed(status) && !item.asset?.glb_ref && <button type="button" disabled={retrying.has(item.variant_id)} onClick={() => void retry(item)} aria-label={`Retry 3D model generation for ${item.title}`} title="Retry this model. A new generation uses Meshy credits; recoverable existing tasks are resumed." className="my-1 rounded border border-cyan-400/50 bg-cyan-400/10 px-3 py-1 font-semibold text-cyan-200 hover:bg-cyan-400/20 disabled:opacity-40">{retrying.has(item.variant_id) ? "Retrying…" : "Retry"}</button>}
              {retryMessages[item.variant_id] && <p role={retryMessages[item.variant_id].error ? "alert" : "status"} className={retryMessages[item.variant_id].error ? "text-rose-200" : "text-emerald-200"}>{retryMessages[item.variant_id].text}</p>}
              {item.asset?.glb_ref && status === "DRAFT_CREATED" && <Link className="text-cyan-200 underline" href={`/components-3d-review?${item.asset.review_batch_id ? `batch=${encodeURIComponent(item.asset.review_batch_id)}&` : ""}asset_id=${item.asset.id}`}>Review model</Link>}<p className="text-slate-500">{generation.updated_at ? `Updated ${new Date(generation.updated_at).toLocaleTimeString()}` : "Awaiting first update"}</p></td>
          </tr>;
        })}</tbody>
      </table>}
    </div>}
  </section>;
}
