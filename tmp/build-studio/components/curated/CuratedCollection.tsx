'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { request, money } from '@/lib/studio';
type Build = {id:string;name:string;segment:string;tier:string;description:string;price_gbp:number|null};
export default function CuratedCollection() {
  const [builds,setBuilds]=useState<Build[]>([]);
  const [error,setError]=useState('');
  const [loaded,setLoaded]=useState(false);
  useEffect(()=>{const c=new AbortController();request<Build[]>('curated-builds',c.signal).then(b=>{setBuilds(b);setLoaded(true);}).catch(e=>{if(e.name!=='AbortError'){setError(e.message);setLoaded(true);}});return()=>c.abort();},[]);
  return <main className="mx-auto max-w-6xl px-5 py-14"><p className="text-sm text-secondary">BUILT AROUND YOU</p><h1 className="mt-3 text-4xl font-bold">Find your kind of PC.</h1><p className="mt-4 max-w-2xl text-lg text-secondary">Choose a build for what you do. We’ve chosen the core; you choose RAM capacity, SATA or NVMe SSD and capacity, and your case.</p>
    {error&&<p role="alert" className="mt-8">{error}</p>}{!loaded&&<p className="mt-8">Loading the collection…</p>}
    {Array.from(new Set(builds.map(b=>b.segment))).map(segment=><section className="mt-12" key={segment}><h2 className="text-2xl font-semibold">{segment}</h2><div className="mt-5 grid gap-4 md:grid-cols-3">{builds.filter(b=>b.segment===segment).map(b=><Link href={'/curated/'+b.id} key={b.id} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-6 transition-colors hover:border-[#ff7426]"><p className="text-xs text-secondary">{b.tier}</p><h3 className="mt-2 text-xl font-semibold">{b.name}</h3><p className="mt-3 min-h-16 text-sm text-secondary">{b.description}</p><p className="mt-6 font-semibold">{b.price_gbp===null?'Price pending':`From ${money(b.price_gbp)}`}</p><p className="mt-3 text-sm text-[#ff7426]">Explore build →</p></Link>)}</div></section>)}
    <div className="mt-12 flex flex-wrap gap-6 text-sm"><Link href="/studio">Choose every component → Custom builds</Link><Link href="/ready-to-ship">Already built and tested → Pre-builts</Link></div>
  </main>;
}
