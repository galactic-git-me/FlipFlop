"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { VENDOR_META } from "@/lib/vendors";

type Job = Awaited<ReturnType<typeof api.crossListing.browserJobs>>[number];

function ageLabel(value?: string | null) {
  if (!value) return "time unknown";
  const normalized = /(?:z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
  const minutes = Math.max(0, Math.floor((Date.now() - Date.parse(normalized)) / 60_000));
  if (!Number.isFinite(minutes)) return "time unknown";
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}

function queueIsStale(job: Job) {
  if (job.status !== "queued" || !job.created_at) return false;
  const normalized = /(?:z|[+-]\d{2}:?\d{2})$/i.test(job.created_at) ? job.created_at : `${job.created_at}Z`;
  const createdAt = Date.parse(normalized);
  return Number.isFinite(createdAt) && Date.now() - createdAt >= 15 * 60_000;
}

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
      } catch { if (!cancelled) setError("Could not load Codex Chrome jobs. Refresh to retry."); }
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
  const operatorChallenges = jobs.filter((job) => ["blocked", "needs_review"].includes(job.status) && /login|credential|captcha|challenge|verification|security check|arkose|bot check/i.test(job.message ?? ""));
  return (
    <section className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 p-4" aria-label="Codex Chrome listing jobs">
      <h2 className="text-sm font-semibold text-emerald-300">Codex Chrome jobs</h2>
      <p className="mt-1 text-xs text-slate-400">Publishing and auto-relisting use the saved seller pack. Security challenges need your action in Chrome; completing a challenge never counts as a published listing until the worker verifies it.</p>
      {!!operatorChallenges.length && <div role="alert" className="mt-3 rounded-lg border border-amber-400/50 bg-amber-950/30 p-3">
        <p className="text-sm font-semibold text-amber-100">Vendor sign-in or security check needs you</p>
        <p className="mt-1 text-xs text-amber-200">Bring the vendor Chrome window forward, sign in or complete its security check, then choose “Resume and reconcile”. The worker will inspect the account again before attempting any listing change.</p>
        <p className="mt-1 text-xs text-amber-100">{operatorChallenges.map((job) => `Build ${job.build_id} · ${VENDOR_META[job.channel]?.label ?? job.channel}`).join("; ")}</p>
      </div>}
      {error && <p role="alert" className="mt-3 text-xs text-red-300">{error}</p>}
      {!jobs.length && !error && <p className="py-5 text-center text-xs text-slate-500">No Chrome listing jobs yet.</p>}
      <div className="mt-3 space-y-2">
        {jobs.slice(0, 30).map((job) => (
          <div key={job.id} className="flex flex-wrap items-center gap-3 rounded border border-slate-800 p-3 text-xs">
            <span className="text-slate-300">Build {job.build_id} · {VENDOR_META[job.channel]?.label ?? job.channel}</span>
            {(() => {
              const age = ageLabel(job.created_at);
              const staleQueue = queueIsStale(job);
              const statusText = job.status === "queued"
                ? staleQueue ? `queued ${age} · worker not responding` : `queued ${age}`
                : job.status.replaceAll("_", " ");
              const message = job.status === "queued"
                ? staleQueue
                  ? `Not published. The desktop worker has not claimed this ${job.operation} job. Check that the “FlipFlop Codex Browser Listings” Windows task is running.`
                  : `Waiting for the desktop worker; this is not a live listing yet. ${job.message ?? ""}`
                : job.message;
              return <>
                <span className={job.status === "succeeded" ? "text-emerald-300" : job.status === "blocked" || job.status === "needs_review" || staleQueue ? "text-amber-300" : job.status === "cancelled" ? "text-slate-400" : "text-sky-300"}>{statusText}</span>
                <span className="min-w-0 flex-1 text-slate-400">{message}</span>
              </>;
            })()}
            <a href={`/proxy-api/cross-listing/browser-jobs/${job.id}/seller-pack`} download={`seller-pack-${job.id}.json`} className="text-sky-300 underline">Seller pack</a>
            {operatorChallenges.some((challenge) => challenge.id === job.id) && <span className="w-full text-xs font-semibold text-amber-200">Action required: complete sign-in or security check in the vendor Chrome window, then resume.</span>}
            {["blocked", "needs_review"].includes(job.status) && <button type="button" disabled={saving === job.id} onClick={() => void retry(job)} className="cursor-pointer rounded border border-yellow-400/30 px-2 py-1 text-yellow-200 disabled:opacity-50">{saving === job.id ? "Resuming…" : "Resume and reconcile"}</button>}
          </div>
        ))}
      </div>
    </section>
  );
}
