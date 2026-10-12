'use client';

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { request, money, shortCaseName, type Chassis } from '@/lib/studio';
import { normalizeAnchorManifest, type ResolvedAsset } from '@/lib/asset-api';

const Scene = dynamic(() => import('../studio/StudioScene'), { ssr: false });
type CaseAsset = { asset_id: number; glb_ref: string; anchor_manifest: unknown; scale_validated: boolean };
const accents = ['#5ce1ce', '#6d9dff', '#b18aff', '#ff7426'];

export default function CaseGalleryModal({ cases, selectedId, onClose, onChoose, onDetails }:
  { cases: Chassis[]; selectedId: number | null; onClose: () => void; onChoose: (item: Chassis) => void; onDetails: (item: Chassis) => void }) {
  const [index, setIndex] = useState(() => Math.max(0, cases.findIndex(item => item.id === selectedId)));
  const [formFactor, setFormFactor] = useState('all');
  const [similarOnly, setSimilarOnly] = useState(false);
  const [playing, setPlaying] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(true);
  const [assets, setAssets] = useState<Record<number, ResolvedAsset | null>>({});
  const [assetsLoading, setAssetsLoading] = useState(false);
  const [accentIndex, setAccentIndex] = useState(0);
  const selectedCase = cases.find(item => item.id === selectedId) ?? cases[0];
  const formFactors = useMemo(() => [...new Set(cases.map(item => (item.form_factor || 'Other').toUpperCase()))].sort(), [cases]);
  const visible = useMemo(() => cases.filter(item => {
    if (formFactor !== 'all' && (item.form_factor || '').toUpperCase() !== formFactor) return false;
    if (similarOnly && selectedCase && item.id !== selectedCase.id) {
      const matchingSize = (item.form_factor || '').toLowerCase() === (selectedCase.form_factor || '').toLowerCase();
      const tags = new Set(selectedCase.style_tags ?? []);
      const matchingStyle = (item.style_tags ?? []).some(tag => tags.has(tag));
      if (!matchingSize && !matchingStyle) return false;
    }
    return true;
  }), [cases, formFactor, similarOnly, selectedCase]);
  const activeIndex = Math.min(index, Math.max(0, visible.length - 1));
  const item = visible[activeIndex];
  const activeAsset = item ? assets[item.asset_subject_id ?? -1] : null;
  const asset = activeAsset ? { ...activeAsset, anchor_manifest: normalizeAnchorManifest(activeAsset.anchor_manifest) } : null;

  const go = useCallback((delta: number) => {
    if (!visible.length) return;
    setIndex(current => (current + delta + visible.length) % visible.length);
  }, [visible.length]);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(preference.matches);
    update(); preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'ArrowRight') go(1);
      if (event.key === 'ArrowLeft') go(-1);
    };
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = oldOverflow; };
  }, [go, onClose]);
  useEffect(() => {
    if (!playing || reducedMotion || visible.length < 2) return;
    const timer = window.setInterval(() => go(1), 5200);
    return () => window.clearInterval(timer);
  }, [playing, reducedMotion, visible.length, go]);
  useEffect(() => {
    if (!visible.length) return;
    setIndex(current => Math.min(current, visible.length - 1));
  }, [visible.length]);
  useEffect(() => {
    let cancelled = false;
    const unresolved = cases.filter(item => item.asset_subject_id && !(item.asset_subject_id in assets));
    if (!unresolved.length) return;
    setAssetsLoading(true);
    (async () => {
      const results: Record<number, ResolvedAsset | null> = {};
      for (const item of unresolved) results[item.asset_subject_id!] = null;
      for (let start = 0; start < unresolved.length; start += 50) {
        const subjects = unresolved.slice(start, start + 50).map(item => ({ subject_type: 'case', subject_id: item.asset_subject_id!, category: 'case' }));
        try {
          const response = await request<{ results: { query: { subject_id: number }; asset: ResolvedAsset | null }[] }>('assets/resolve', undefined, { subjects });
          for (const row of response.results) results[row.query.subject_id] = row.asset;
        } catch { /* Keep the photo gallery available when 3D resolution is offline. */ }
      }
      if (!cancelled) setAssets(current => ({ ...current, ...results }));
      if (!cancelled) setAssetsLoading(false);
    })();
    return () => { cancelled = true; };
  }, [cases, assets]);
  if (!item) return <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/85 p-4" role="dialog" aria-modal="true"><section className="rounded-2xl bg-[#0b1521] p-8 text-white"><p>No cases match these filters.</p><button className="mt-4" onClick={onClose}>Close gallery</button></section></div>;

  return <div className="fixed inset-0 z-[90] overflow-y-auto bg-[#050a10]/95 p-2 backdrop-blur-xl sm:p-5" role="presentation">
    <section role="dialog" aria-modal="true" aria-labelledby="case-gallery-title" className="mx-auto flex min-h-[94vh] max-w-[1500px] flex-col overflow-hidden rounded-[28px] border border-cyan-200/15 bg-[radial-gradient(ellipse_at_38%_35%,rgba(19,70,88,.43),transparent_55%),linear-gradient(140deg,#0b1521,#071018_65%,#101424)] text-white shadow-[0_25px_120px_rgba(0,0,0,.7)]">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4 sm:px-7"><div><p className="text-[10px] font-semibold uppercase tracking-[.25em] text-cyan-300">The case gallery · {cases.length} available</p><h2 id="case-gallery-title" className="mt-1 text-xl font-bold sm:text-2xl">Find the right home for your build</h2></div><div className="flex gap-2"><button type="button" aria-pressed={playing&&!reducedMotion} onClick={() => setPlaying(value => !value)} className="rounded-xl border border-white/15 px-3 py-2 text-xs text-slate-200 hover:bg-white/10">{playing&&!reducedMotion?'Pause gallery':'Play gallery'}</button><button type="button" onClick={onClose} className="rounded-xl border border-white/15 px-3 py-2 text-sm hover:bg-white/10">Close</button></div></header>
      <div className="grid flex-1 lg:grid-cols-[minmax(0,1fr)_330px]">
        <div className="flex min-h-[430px] flex-col p-4 sm:p-6 lg:min-h-0">
          <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap gap-2"><label className="sr-only" htmlFor="case-form-factor">Case size</label><select id="case-form-factor" value={formFactor} onChange={event => { setFormFactor(event.target.value); setIndex(0); }} className="rounded-xl border border-white/15 bg-[#101c29] px-3 py-2 text-sm"><option value="all">All case sizes</option>{formFactors.map(value => <option key={value} value={value}>{value} cases</option>)}</select><button type="button" aria-pressed={similarOnly} onClick={() => { setSimilarOnly(value => !value); setIndex(0); }} disabled={!selectedCase} className={`rounded-xl border px-3 py-2 text-sm ${similarOnly?'border-cyan-300/60 bg-cyan-300/10 text-cyan-100':'border-white/15 text-slate-200'} disabled:opacity-40`}>Similar to your case</button></div><span className="text-xs text-slate-400">{visible.length} cases in this view · {reducedMotion?'motion reduced':playing?'auto-advancing':'paused'}</span></div>
          <div className="relative mt-4 flex min-h-[340px] flex-1 items-center justify-center overflow-hidden rounded-[24px] border border-white/10 bg-[radial-gradient(ellipse_at_50%_80%,rgba(31,117,144,.27),transparent_48%),linear-gradient(145deg,#111e2b,#08111b)] sm:min-h-[470px]">
            <div className="absolute inset-x-1/4 bottom-[7%] h-10 rounded-[50%] bg-cyan-400/10 blur-2xl" />
            {asset?.glb_ref ? <div className="absolute inset-0"><Scene parts={[{ category: 'case', id: item.id, title: item.name, asset }]} active="case" onSelect={() => {}} mode="assembled" open={false} accent={accents[accentIndex]} rotating={!reducedMotion&&playing} resetKey={item.id} reducedMotion={reducedMotion} /></div>
              : item.images?.[0] ? <img key={item.id} src={item.images[0]} alt={shortCaseName(item.name, item.brand)} className="relative max-h-[70vh] w-full animate-[case-reveal_.45s_ease-out] object-contain drop-shadow-[0_30px_55px_rgba(0,0,0,.55)]" />
              : <div className="relative flex h-72 w-64 items-center justify-center rounded-3xl border border-white/20 bg-gradient-to-br from-slate-700 to-slate-950 text-center text-sm text-slate-400">Case image coming soon</div>}
            <button type="button" aria-label="Previous case" onClick={() => go(-1)} className="absolute left-3 top-1/2 z-10 -translate-y-1/2 rounded-full border border-white/20 bg-slate-950/70 p-3 text-white backdrop-blur hover:bg-cyan-900/80">‹</button><button type="button" aria-label="Next case" onClick={() => go(1)} className="absolute right-3 top-1/2 z-10 -translate-y-1/2 rounded-full border border-white/20 bg-slate-950/70 p-3 text-white backdrop-blur hover:bg-cyan-900/80">›</button>
            <div className="absolute bottom-4 left-4 right-4 z-10 flex flex-wrap items-end justify-between gap-3"><div className="rounded-xl border border-white/10 bg-slate-950/75 px-4 py-3 backdrop-blur"><p className="text-[10px] uppercase tracking-[.18em] text-cyan-200">{item.form_factor?.toUpperCase()} chassis {item.is_preferred?' · Recommended':''}</p><h3 className="mt-1 text-xl font-bold sm:text-2xl">{shortCaseName(item.name,item.brand)}</h3><p className="mt-1 text-sm text-slate-300">{money(item.rrp_gbp)}{asset?.glb_ref?' · Interactive 3D view':' · Product gallery view'}</p></div><button type="button" onClick={() => onDetails(item)} className="rounded-xl border border-white/20 bg-slate-950/75 px-4 py-3 text-sm font-semibold text-white backdrop-blur hover:border-cyan-300/50">Explore details</button></div>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2" aria-label="Case gallery lighting"><span className="mr-1 text-xs text-slate-400">Lighting</span>{accents.map((color,i)=><button key={color} aria-label={`Set gallery lighting ${i+1}`} aria-pressed={accentIndex===i} onClick={() => setAccentIndex(i)} className="h-4 w-4 rounded-full" style={{background:color,outline:accentIndex===i?'2px solid white':'none',outlineOffset:2}} />)}</div><span className="text-[11px] text-slate-500">{assetsLoading?'Checking for 3D case models…':asset?.glb_ref?'Drag to rotate · scroll to zoom':'Use the arrows, filter by size, or choose similar cases'}</span></div>
          <div className="mt-4 flex gap-2 overflow-x-auto pb-2" aria-label="Choose a case to preview">{visible.map((candidate,candidateIndex)=><button type="button" key={candidate.id} aria-current={candidateIndex===activeIndex?'true':undefined} onClick={() => setIndex(candidateIndex)} className={`w-28 shrink-0 overflow-hidden rounded-xl border text-left transition ${candidateIndex===activeIndex?'border-cyan-300 ring-2 ring-cyan-300/25':'border-white/10 opacity-70 hover:opacity-100'}`}><div className="flex h-20 items-center justify-center bg-white">{candidate.images?.[0]&&<img src={candidate.images[0]} alt="" className="h-full w-full object-contain" loading="lazy"/>}</div><span className="block truncate px-2 py-1.5 text-[10px]">{shortCaseName(candidate.name,candidate.brand)}</span></button>)}</div>
        </div>
        <aside className="flex flex-col border-t border-white/10 bg-black/15 p-5 lg:border-l lg:border-t-0 lg:p-6"><p className="text-[10px] font-semibold uppercase tracking-[.2em] text-lime-300">A case is part of the experience</p><h3 className="mt-2 text-xl font-bold">Pick the look and size that suit you.</h3><p className="mt-2 text-sm leading-6 text-slate-300">Compare the outside, explore the available 3D model and filter cases by form factor. We’ll recheck clearances against your chosen parts before checkout.</p>
          <div className="mt-5 space-y-2">{[['Form factor',item.form_factor?.toUpperCase()||'Not specified'],['Colour',item.colour||'See product image'],['Glass panel',item.is_transparent_panel?'Yes':'Not listed'],['GPU clearance',item.max_gpu_length_mm?`${item.max_gpu_length_mm} mm`:'Check details'],['Radiator support',item.engineering?.radiator_support?'Listed':'Check details']].map(([label,value])=><div key={label} className="flex justify-between gap-3 border-b border-white/10 py-2 text-xs"><span className="text-slate-400">{label}</span><span className="text-right text-slate-200">{value}</span></div>)}</div>
          {item.style_tags?.length ? <div className="mt-4 flex flex-wrap gap-1.5">{item.style_tags.slice(0,6).map(tag=><span key={tag} className="rounded-full border border-cyan-200/15 bg-cyan-200/[.06] px-2.5 py-1 text-[10px] text-cyan-100">{tag}</span>)}</div>:null}
          <div className="mt-auto pt-7"><p className="text-2xl font-bold">{money(item.rrp_gbp)}</p><p className="mt-1 text-xs text-slate-400">Case price · build total updates with your choice</p><button type="button" onClick={() => onChoose(item)} className="mt-4 w-full rounded-xl bg-lime-300 px-5 py-4 text-sm font-bold text-slate-950 shadow-[0_0_35px_rgba(190,255,69,.16)] transition hover:bg-lime-200">Choose this case</button><button type="button" onClick={() => { setSimilarOnly(true); setIndex(0); }} className="mt-2 w-full rounded-xl border border-white/15 px-4 py-3 text-sm text-slate-200 hover:border-cyan-300/40">Show similar cases</button></div>
        </aside>
      </div>
    </section>
    <style jsx>{`@keyframes case-reveal { from {opacity:.4; transform:translateY(10px) scale(.98)} to {opacity:1; transform:translateY(0) scale(1)} }`}</style>
  </div>;
}
