'use client';
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { ReconciliationHealth } from '@/lib/commercial-readiness';

export default function CommercialRunHealth({onComplete}:{onComplete:()=>void}) {
  const [health,setHealth]=useState<ReconciliationHealth|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const load=useCallback(async()=>{
    try {setHealth(await api.commercialReadiness.health());setError(null);}
    catch {setError('Could not load reconciliation history.');}
  },[]);
  useEffect(()=>{void load();},[load]);
  const run=async()=>{
    setBusy(true);setError(null);
    try {await api.commercialReadiness.reconcile();await load();onComplete();}
    catch {setError('Reconciliation did not complete. Reload history to inspect the recorded result.');}
    finally {setBusy(false);}
  };
  const latest=health?.runs[0];
  return <section aria-label="Commercial reconciliation" className="space-y-2 rounded border border-slate-700 p-4 text-sm">
    <h2 className="font-semibold">Background evidence refresh</h2>
    <p className="text-slate-400">Refreshes previously reviewed exact listings. Original capture times are preserved. Rules and checkout enablement require their own review.</p>
    {error&&<p role="alert" className="text-amber-300">{error}</p>}
    {health&&<p>Hourly scheduling: {health.scheduled_enabled?'enabled':'disabled'} · Last success: {health.last_success_at?new Date(health.last_success_at).toLocaleString():'No successful run recorded'}</p>}
    {latest&&<p>Latest run #{latest.id}: {latest.status} · imported {latest.result.imported??0} · reused {latest.result.reused??0} · needs review {latest.result.blocked?.length??0}{latest.result.error_type?` · ${latest.result.error_type}`:''}</p>}
    {!!latest?.result.blocked?.length&&<ul className="list-inside list-disc text-slate-400">{latest.result.blocked.slice(0,8).map((item,index)=><li key={`${item.part_key}:${index}`}>{item.part_key}: {item.reason}</li>)}</ul>}
    <div className="flex gap-3"><button type="button" disabled={busy} onClick={()=>void run()} className="rounded border border-cyan-700 px-3 py-2 disabled:opacity-40">{busy?'Refreshing evidence…':'Run evidence refresh'}</button>
      <button type="button" disabled={busy} onClick={()=>void load()} className="text-cyan-300 underline">Reload history</button></div>
  </section>;
}
