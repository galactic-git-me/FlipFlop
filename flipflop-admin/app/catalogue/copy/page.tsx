'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';

type Status = { total: number; ready: number; remaining: number };

export default function CatalogueCopyPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [lastBatch, setLastBatch] = useState<{ generated: number; failed: { task_key: string; error: string }[] } | null>(null);
  const refresh = useCallback(async () => setStatus(await api.marketingCopy.status()), []);
  useEffect(() => { void refresh().catch(cause => setError(cause instanceof Error ? cause.message : 'Could not load catalogue copy status.')); }, [refresh]);
  const run = async () => {
    setRunning(true); setError(''); setLastBatch(null);
    try {
      let current = status ?? await api.marketingCopy.status();
      setStatus(current);
      while (current.remaining > 0) {
        const batch = await api.marketingCopy.generateBatch(4);
        setStatus(batch); setLastBatch({ generated: batch.generated, failed: batch.failed });
        if (batch.failed.length || batch.attempted === 0) break;
        current = batch;
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The catalogue copy sweep stopped. Resume it to continue.');
    } finally {
      setRunning(false);
      try { setStatus(await api.marketingCopy.status()); } catch { /* Keep the last confirmed progress visible. */ }
    }
  };
  const percent = status?.total ? Math.round(status.ready / status.total * 100) : 0;
  return <main className="mx-auto max-w-5xl p-6 text-slate-100">
    <Link href="/catalogue" className="text-sm text-cyan-300 hover:underline">← Catalogue</Link>
    <header className="mt-7"><p className="font-mono text-[10px] uppercase tracking-[.24em] text-cyan-400">Customer experience · product storytelling</p><h1 className="mt-2 text-3xl font-bold">Catalogue product guides</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">Create short, evidence-based descriptions for curated/custom components and PC cases. The copy is saved against each catalogue item and reused when customers open its product guide.</p></header>
    <section className="mt-7 rounded-2xl border border-white/10 bg-[#0b1119] p-5 sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="text-lg font-semibold">Initial catalogue sweep</h2><p className="mt-1 max-w-2xl text-xs leading-5 text-slate-400">Products are sent to the configured local/free LLM in small batches. Each prompt includes the scraped vendor title, description and available specifications. Progress is saved after each batch, so you can resume later.</p></div><span className="rounded-full border border-emerald-300/20 bg-emerald-300/[.06] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-200">Free/local only</span></div>
      {status ? <><div className="mt-7 grid gap-3 sm:grid-cols-3">{[['Guides ready',status.ready],['Remaining',status.remaining],['Catalogue total',status.total]].map(([label,value])=><article key={label} className="rounded-xl border border-white/10 bg-white/[.025] p-4"><p className="text-xs text-slate-400">{label}</p><p className="mt-1 text-2xl font-bold">{value}</p></article>)}</div><div className="mt-5"><div className="flex justify-between text-xs"><span className="text-slate-400">Sweep progress</span><span className="font-semibold text-cyan-200">{percent}%</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-lime-300 transition-all" style={{ width: `${percent}%` }} /></div></div></> : <p className="mt-6 text-sm text-slate-400">Loading catalogue coverage…</p>}
      {error && <p role="alert" className="mt-4 rounded-lg border border-rose-300/20 bg-rose-300/[.06] p-3 text-sm text-rose-200">{error}</p>}
      {lastBatch?.failed.length ? <div className="mt-4 rounded-lg border border-amber-300/20 bg-amber-300/[.05] p-3"><p className="text-sm font-semibold text-amber-100">Some items need another attempt</p><ul className="mt-2 space-y-1 text-xs text-amber-100/75">{lastBatch.failed.map(item=><li key={item.task_key}>{item.task_key}: {item.error}</li>)}</ul></div> : null}
      <div className="mt-6 flex flex-wrap items-center gap-3"><button type="button" onClick={() => void run()} disabled={running||!status?.remaining} className="rounded-xl bg-lime-300 px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-lime-200 disabled:cursor-not-allowed disabled:opacity-40">{running?'Generating small batches…':status?.remaining?'Start or resume sweep':'All current guides are ready'}</button><button type="button" onClick={() => void refresh().catch(cause => setError(cause instanceof Error ? cause.message : 'Refresh failed.'))} disabled={running} className="rounded-xl border border-white/15 px-4 py-3 text-sm text-slate-200 hover:bg-white/5 disabled:opacity-40">Refresh progress</button><p className="text-[11px] text-slate-500">A customer opening a product guide generates missing copy on demand, also using local/free tiers only.</p></div>
    </section>
    <section className="mt-5 grid gap-3 md:grid-cols-3">{[['A guided case gallery','Customers can filter by case size, compare similar designs and explore approved 3D models alongside large product photos.'],['Product-first details','Product names open a modal with a clean image, short benefit-led copy and exact sourced details.'],['Two types of copy','Upgrade descriptions compare against the actual starting part where the catalogue records that relationship.']].map(([title,body])=><article key={title} className="rounded-xl border border-white/10 bg-[#0b1119] p-4"><h3 className="font-semibold text-white">{title}</h3><p className="mt-2 text-xs leading-5 text-slate-400">{body}</p></article>)}</section>
  </main>;
}
