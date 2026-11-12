"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowUpRight, CheckCheck, RefreshCw } from "lucide-react";
import { getApprovalSnapshot, type ApprovalSnapshot, type ApprovalTab } from "@/lib/approvals";

const tabs: Array<{ id: "all" | ApprovalTab; label: string }> = [
  { id: "all", label: "All approvals" },
  { id: "images", label: "Images" },
  { id: "models", label: "3D models" },
  { id: "pricing", label: "Pricing" },
  { id: "playbook", label: "Playbook & catalogue" },
  { id: "marketing", label: "Marketing" },
];

function ApprovalCentre() {
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]["id"]>("all");
  const [snapshot, setSnapshot] = useState<ApprovalSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (force = false) => {
    setLoading(true);
    setError("");
    try { setSnapshot(await getApprovalSnapshot(force)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load approval queues"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    const requested = searchParams.get("tab");
    if (tabs.some(tab => tab.id === requested)) setActiveTab(requested as (typeof tabs)[number]["id"]);
  }, [searchParams]);
  useEffect(() => { void load(); }, [load]);

  const queues = useMemo(() => (snapshot?.queues ?? []).filter(queue => activeTab === "all" || queue.tab === activeTab), [snapshot, activeTab]);
  const total = (snapshot?.queues ?? []).reduce((sum, queue) => sum + queue.count, 0);
  const tabCount = (tab: (typeof tabs)[number]["id"]) => (snapshot?.queues ?? []).filter(queue => tab === "all" || queue.tab === tab).reduce((sum, queue) => sum + queue.count, 0);

  return <main className="mx-auto max-w-7xl space-y-6 p-5 text-slate-100 sm:p-7">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="font-mono text-[10px] uppercase tracking-[.24em] text-rose-300">Admin work queue</p><h1 className="mt-1 text-3xl font-semibold">Approvals</h1><p className="mt-2 max-w-3xl text-sm text-slate-400">One place to find reviews and decisions waiting across catalogue images, 3D assets, Playbook pricing, technical evidence, customer configurations, and marketing.</p></div>
      <button type="button" onClick={() => void load(true)} disabled={loading} className="inline-flex items-center gap-2 rounded-lg border border-white/15 px-3 py-2 text-sm text-slate-200 hover:bg-white/5 disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh queues</button>
    </header>

    {error && <p role="alert" className="rounded-lg border border-rose-400/30 bg-rose-950/30 px-4 py-3 text-sm text-rose-100">{error}</p>}
    {snapshot?.unavailable.length ? <div role="status" className="rounded-lg border border-amber-400/25 bg-amber-950/20 px-4 py-3 text-sm text-amber-100">Some queues could not be checked ({snapshot.unavailable.join(", ")}). Their counts are omitted until the connection recovers.</div> : null}

    <section className="rounded-2xl border border-white/10 bg-slate-950/70 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="text-sm text-slate-400">Approvals and reviews waiting</p><p className="mt-1 text-4xl font-semibold tabular-nums">{loading && !snapshot ? "…" : total}</p></div>
        <p className="text-xs text-slate-500">{snapshot ? `Updated ${new Date(snapshot.observedAt).toLocaleTimeString()}` : "Loading live queues"}</p>
      </div>
      <nav aria-label="Approval types" className="mt-5 flex flex-wrap gap-2 border-t border-white/10 pt-4">
        {tabs.map(tab => <button key={tab.id} type="button" aria-pressed={activeTab === tab.id} onClick={() => setActiveTab(tab.id)} className={`rounded-lg border px-3 py-2 text-sm transition ${activeTab === tab.id ? "border-rose-300/50 bg-rose-400/10 text-rose-100" : "border-white/10 text-slate-300 hover:bg-white/5"}`}>
          {tab.label}<span className={`ml-2 rounded-full px-1.5 py-0.5 text-xs tabular-nums ${tabCount(tab.id) > 0 ? "bg-rose-500/20 text-rose-200" : "bg-white/5 text-slate-400"}`}>{tabCount(tab.id)}</span>
        </button>)}
      </nav>
    </section>

    {queues.length === 0 ? <section className="grid min-h-64 place-items-center rounded-2xl border border-dashed border-white/15 bg-slate-950/40 p-8 text-center">
      <div><CheckCheck className="mx-auto h-8 w-8 text-emerald-300" /><h2 className="mt-3 text-lg font-semibold">{loading ? "Checking approval queues" : "No approvals in this tab"}</h2><p className="mt-1 text-sm text-slate-400">{loading ? "Queue counts are loading." : "Nothing is waiting for review in this category."}</p></div>
    </section> : <section aria-label="Approval queues" className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {queues.map(queue => <Link key={queue.id} href={queue.href} className="group rounded-xl border border-white/10 bg-[#101924] p-4 transition hover:border-rose-300/40 hover:bg-[#14202e] focus-visible:outline focus-visible:outline-2 focus-visible:outline-rose-300">
        <div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold text-white">{queue.title}</h2><p className="mt-2 text-sm leading-5 text-slate-400">{queue.description}</p></div><span className={`min-w-9 rounded-full px-2 py-1 text-center text-sm font-bold tabular-nums ${queue.count ? "bg-rose-500/20 text-rose-200" : "bg-white/5 text-slate-400"}`}>{queue.count}</span></div>
        <span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-cyan-200">Open review queue <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" /></span>
      </Link>)}
    </section>}
    <p className="text-xs text-slate-500">Counts show items currently awaiting a human decision. A failed source is marked unavailable instead of being treated as an empty queue.</p>
  </main>;
}

export default function ApprovalsPage() {
  return <Suspense fallback={<main className="p-6 text-sm text-slate-400">Loading approvals…</main>}><ApprovalCentre /></Suspense>;
}
