"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { VENDOR_META } from "@/lib/vendors";

type Job = Awaited<ReturnType<typeof api.crossListing.browserJobs>>[number];

export default function BrowserListingJobs({ onChanged }: { onChanged: () => Promise<void> }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<number | null>(null);
  const previous = useRef("");
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const rows = await api.crossListing.browserJobs();
        if (cancelled) return;
        const signature = rows.map((job) => `${job.id}:${job.status}`).join(",");
        if (previous.current && previous.current !== signature) void onChanged();
        previous.current = signature;
        setJobs(rows);
        setError(null);
      } catch { if (!cancelled) setError("Could not load channel synchronisation jobs. Refresh to retry."); }
    };
    void load();
    const interval = window.setInterval(() => void load(), 10000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [onChanged]);
  const retry = async (job: Job) => {
    setSaving(job.id);
    try {
      await api.crossListing.retryBrowserJob(job.id);
      setJobs(await api.crossListing.browserJobs());
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not resume the job."); }
    finally { setSaving(null); }
  };
  return (
    <section className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 p-4" aria-label="Channel synchronisation jobs">
      <h2 className="text-sm font-semibold text-emerald-300">Channel synchronisation</h2>
      <p className="mt-1 text-xs text-slate-400">Listings, updates, sale checks and withdrawals are tracked here. Browser channels need the desktop worker; queued work waits until it is available.</p>
      {error && <p role="alert" className="mt-3 text-xs text-red-300">{error}</p>}
      {!jobs.length && !error && <p className="py-5 text-center text-xs text-slate-500">No channel jobs yet.</p>}
      <div className="mt-3 space-y-2">
        {jobs.slice(0, 30).map((job) => (
          <div key={job.id} className="flex flex-wrap items-center gap-3 rounded border border-slate-800 p-3 text-xs">
            <span className="text-slate-300">Build {job.build_id} · {VENDOR_META[job.channel]?.label ?? job.channel} � {job.operation.replaceAll("_", " ")}</span>
            <span className={job.status === "succeeded" ? "text-emerald-300" : job.status === "blocked" || job.status === "needs_review" ? "text-yellow-300" : "text-sky-300"}>{job.status.replaceAll("_", " ")}</span>
            <span className="min-w-0 flex-1 text-slate-400">{job.message}</span>
            <a href={`/proxy-api/cross-listing/browser-jobs/${job.id}/seller-pack`} download={`seller-pack-${job.id}.json`} className="text-sky-300 underline">Seller pack</a>
            {["blocked", "needs_review"].includes(job.status) && <button type="button" disabled={saving === job.id} onClick={() => void retry(job)} className="cursor-pointer rounded border border-yellow-400/30 px-2 py-1 text-yellow-200 disabled:opacity-50">{saving === job.id ? "Resuming…" : "Resume and reconcile"}</button>}
          </div>
        ))}
      </div>
    </section>
  );
}
