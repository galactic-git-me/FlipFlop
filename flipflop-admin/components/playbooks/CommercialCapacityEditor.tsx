'use client';
import { useState } from 'react';
import { api } from '@/lib/api';

export default function CommercialCapacityEditor({onComplete}:{onComplete:()=>void}) {
  const [week,setWeek]=useState('');
  const [count,setCount]=useState('');
  const [basis,setBasis]=useState('');
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState<string|null>(null);
  const [error,setError]=useState<string|null>(null);
  const valid=!!week&&count!==''&&Number.isInteger(Number(count))&&Number(count)>=0&&!!basis.trim();
  const save=async()=>{
    if(!valid)return;
    setBusy(true);setError(null);setMessage(null);
    try {
      const result=await api.commercialReadiness.saveCapacity({build_week:week,available_builds:Number(count),
        observed_at:new Date().toISOString(),evidence_source:'operator_workshop_review',evidence_ref:basis.trim()});
      setMessage(`Saved ${result.available_builds} builds for ${result.build_week}. Evidence #${result.id}.`);
      onComplete();
    } catch(error) {setError(error instanceof Error?error.message:'Could not save capacity');}
    finally {setBusy(false);}
  };
  const style='rounded border border-slate-700 bg-slate-950 p-2 text-slate-100';
  return <details className="rounded border border-slate-700 p-4 text-sm">
    <summary className="cursor-pointer font-semibold">Configure workshop capacity</summary>
    <p className="mt-3 text-slate-400">Enter capacity after existing committed work. Do not subtract live quote holds: the engine handles those. Zero pauses new offers for this week; reducing capacity may release active quote holds. Review daily; evidence expires after 24 hours.</p>
    <div className="mt-3 grid gap-3 sm:grid-cols-3">
      <label className="grid gap-1">Build week<input type="week" value={week} disabled={busy} className={style} onChange={e=>setWeek(e.target.value)}/></label>
      <label className="grid gap-1">Available builds<input type="number" min="0" step="1" value={count} disabled={busy} className={style} onChange={e=>setCount(e.target.value)}/></label>
      <label className="grid gap-1">Basis for this capacity<input value={basis} maxLength={500} disabled={busy} className={style} placeholder="Available hours, committed work and QA limits" onChange={e=>setBasis(e.target.value)}/></label>
    </div>
    {error&&<p role="alert" className="mt-2 text-amber-300">{error}</p>}
    {message&&<p role="status" className="mt-2 text-cyan-300">{message}</p>}
    <button type="button" disabled={busy||!valid} className="mt-3 rounded border border-cyan-700 px-3 py-2 disabled:opacity-40" onClick={()=>void save()}>{busy?'Saving…':'Save reviewed capacity'}</button>
  </details>;
}
