'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { request, getAssets, labels, money, options, selected, type Chassis, type Configuration, type Evaluation, type Product, type Slot } from '@/lib/studio';
import type { ResolvedAsset } from '@/lib/asset-api';
import { addCartItem } from '@/lib/cart';
import '../studio/studio.css';

const Scene = dynamic(() => import('../studio/StudioScene'), { ssr: false });
type Definition = { id: string; name: string; segment: string; tier: string; description: string; playbook_id: number | null; components: Record<string,string> };
type Choice = Product & { choice_label?: string; customer_option?: { interface?: string; capacity_gb?: number } };
type CuratedSlot = Slot & { default_variant_id?: number };
const colours = ['#ff7426','#6d9dff','#b18aff','#48e0c1','#f0e8d9'];

export default function CuratedBuild({ buildId }: { buildId: string }) {
  const [definition, setDefinition] = useState<Definition|null>(null);
  const [slots, setSlots] = useState<CuratedSlot[]>([]);
  const [cases, setCases] = useState<Chassis[]>([]);
  const [config, setConfig] = useState<Configuration>({ selections: {}, caseId: null });
  const [assets, setAssets] = useState<Record<string,ResolvedAsset|null>>({});
  const [accent, setAccent] = useState(colours[0]);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [quote, setQuote] = useState<Evaluation|null>(null);
  const [quoteKey, setQuoteKey] = useState('');
  const [notice, setNotice] = useState('');
  const [adding, setAdding] = useState(false);
  const signature = JSON.stringify({ playbook_id: definition?.playbook_id, selections: config.selections, case_id: config.caseId, build_mode: 'curated', curated_build_id: buildId });
  const fresh = signature === quoteKey;
  useEffect(() => {
    const controller = new AbortController();
    request<Definition[]>('curated-builds',controller.signal).then(async rows => {
      const build = rows.find(b => b.id === buildId);
      if (!build) throw new Error('This curated build could not be found.');
      setDefinition(build);
      if (!build.playbook_id) { setLoaded(true); return; }
      const [s,c] = await Promise.all([request<CuratedSlot[]>(`playbooks/${build.playbook_id}/curated-slots?build_id=${encodeURIComponent(buildId)}`,controller.signal),request<Chassis[]>('cases',controller.signal)]);
      setSlots(s); setCases(c);
      setConfig({selections: Object.fromEntries(s.flatMap(slot => slot.default_variant_id ? [[slot.slot_id,slot.default_variant_id]] : [])),caseId:c[0]?.id??null});
      setLoaded(true);
    }).catch(e => { if(e.name!=='AbortError') { setError(e.message); setLoaded(true); } });
    return () => controller.abort();
  },[buildId]);
  useEffect(() => {
    if (!loaded || !definition?.playbook_id) return;
    const controller = new AbortController();
    request<Evaluation>('studio/evaluate',controller.signal,JSON.parse(signature)).then(q => {setQuote(q);setQuoteKey(signature);}).catch(e => {if(e.name!=='AbortError') setError(e.message);});
    getAssets(slots,config,controller.signal).then(setAssets).catch(() => { if (!controller.signal.aborted) setAssets({}); });
    return () => controller.abort();
  },[signature,loaded,definition?.playbook_id,slots,config]);
  const chassis = cases.find(c => c.id===config.caseId);
  const parts = [...(chassis?[{category:'case',id:chassis.id,title:chassis.name,asset:assets['case:'+chassis.id]}]:[]),...slots.flatMap(s=>{const p=selected(s,config);return p?[{category:s.slot_type,id:p.id,title:p.title,asset:assets['variant:'+p.id]}]:[];})];
  const memory = slots.find(s=>s.slot_type==='ram');
  const storage = slots.find(s=>s.slot_type==='storage');
  const drives = storage ? options(storage) as Choice[] : [];
  const drive = storage ? selected(storage,config) as Choice|undefined : undefined;
  const interfaces = Array.from(new Set(drives.map(v=>v.customer_option?.interface).filter(Boolean)));
  const choose = (slot: Slot, id: number) => { if(options(slot).some(v=>v.id===id)) setConfig(c=>({...c,selections:{...c.selections,[slot.slot_id]:id}})); };
  const add = async () => {
    setAdding(true); setNotice('');
    try {
      const q = await request<Evaluation>('studio/evaluate',undefined,JSON.parse(signature));
      if(!q.can_checkout || !q.price || !definition?.playbook_id) { setNotice('This configuration needs a stock or compatibility review before ordering.'); return; }
      addCartItem({kind:'configured',validationMode:'curated',curatedBuildId:buildId,title:definition.name,playbookName:definition.name,playbookId:definition.playbook_id,slotSelections:config.selections,caseId:config.caseId,chosenWeek:null,displayTotal:q.price.total,componentSummary:parts.map(p=>p.title)});
      setNotice('Added to your cart.');
    } catch(e) {setNotice(e instanceof Error?e.message:'Could not add this build.');} finally {setAdding(false);}
  };
  const selectStyle = 'mt-2 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-3';
  return <main className="mx-auto max-w-6xl px-5 py-12">
    <Link href="/products" className="text-sm text-secondary">← Curated builds</Link>
    {error && <p role="alert" className="mt-5">{error}</p>}
    {!loaded ? <p className="py-20">Loading your build…</p> : definition && <div className="mt-7 grid gap-10 lg:grid-cols-2">
      <section aria-label="Your PC preview">
        <div className="curated-preview relative aspect-square overflow-hidden rounded-3xl bg-[#101722]">
          {parts.length ? <Scene parts={parts} active="case" onSelect={()=>{}} mode="assembled" open={false} accent={accent} rotating={false} resetKey={0} reducedMotion={true}/> : <div className="flex h-full items-center justify-center p-10 text-center text-secondary">Product preview will appear when its catalogue components are available.</div>}
        </div>
        <div className="mt-4 flex items-center justify-between gap-3"><span className="text-xs text-secondary">Drag to look around · Scroll to zoom</span><div className="flex gap-2" aria-label="Preview fan lighting">{colours.map((c,i)=><button key={c} aria-label={['Ember','Ice','Violet','Mint','Pearl'][i]+' fan lighting'} aria-pressed={accent===c} onClick={()=>setAccent(c)} className="h-5 w-5 rounded-full" style={{background:c,outline:accent===c?'2px solid white':'none',outlineOffset:3}}/>)}</div></div>
        <p className="mt-3 text-xs text-secondary">3D layout preview. Product appearance follows the available model.</p>
      </section>
      <section><p className="text-sm text-secondary">{definition.segment} · {definition.tier}</p><h1 className="mt-2 text-4xl font-bold">{definition.name}</h1><p className="mt-4 text-secondary">{definition.description}</p>
        <p className="mt-6 text-sm">Your core build is chosen. Make room for what you need.</p>
        <fieldset disabled={adding} className="mt-5 space-y-5">
          {memory && <label className="block text-sm">RAM capacity<select className={selectStyle} value={config.selections[memory.slot_id]??''} onChange={e=>choose(memory,Number(e.target.value))}><option disabled value="">Awaiting catalogue availability</option>{(options(memory) as Choice[]).map(v=><option key={v.id} value={v.id}>{v.choice_label??'Included RAM'}</option>)}</select></label>}
          {storage && <div className="grid grid-cols-2 gap-3"><label className="block text-sm">SSD type<select className={selectStyle} value={drive?.customer_option?.interface??''} onChange={e=>{const v=drives.find(d=>d.customer_option?.interface===e.target.value&&d.customer_option?.capacity_gb===drive?.customer_option?.capacity_gb)??drives.find(d=>d.customer_option?.interface===e.target.value);if(v)choose(storage,v.id);}}><option disabled value="">Included SSD</option>{interfaces.map(i=><option key={i} value={i}>{i}</option>)}</select></label><label className="block text-sm">SSD capacity<select className={selectStyle} value={config.selections[storage.slot_id]??''} onChange={e=>choose(storage,Number(e.target.value))}><option disabled value="">Unavailable</option>{drives.filter(v=>v.customer_option?.interface===drive?.customer_option?.interface).map(v=><option key={v.id} value={v.id}>{v.customer_option?.capacity_gb?`${v.customer_option.capacity_gb} GB`:'Included capacity'}</option>)}</select></label></div>}
          <label className="block text-sm">PC case<select className={selectStyle} value={config.caseId??''} onChange={e=>setConfig(c=>({...c,caseId:Number(e.target.value)}))}><option disabled value="">Choose a case</option>{cases.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        </fieldset>
        <details className="mt-7 border-y border-[var(--color-border)] py-4"><summary className="cursor-pointer text-sm">What’s inside</summary><dl className="mt-4 space-y-3 text-sm">{Object.entries(definition.components).filter(([c])=>!['ram','storage','case'].includes(c)).map(([c,t])=><div key={c}><dt className="text-secondary">{labels[c]??c}</dt><dd>{t}</dd></div>)}</dl></details>
        <div className="mt-7"><p className="text-3xl font-semibold">{fresh&&quote?.price?money(quote.price.total):'Price pending'}</p><p className="mt-1 text-xs text-secondary">Assembly included · Current catalogue pricing</p></div>
        <button disabled={!fresh||!quote?.can_checkout||adding} onClick={add} className="mt-5 w-full rounded-xl bg-[#ff7426] px-5 py-4 font-semibold text-black disabled:opacity-40">{adding?'Checking availability…':'Add to cart'}</button>
        {loaded&&(!fresh||!quote?.can_checkout)&&<p className="mt-3 text-sm text-secondary">{!fresh&&definition.playbook_id?'Checking this configuration…':'We’re confirming stock and compatibility for this build.'}</p>}
        {notice&&<p role="status" className="mt-3 text-sm">{notice} <Link href="/cart">View cart →</Link></p>}
      </section>
    </div>}
  </main>;
}
