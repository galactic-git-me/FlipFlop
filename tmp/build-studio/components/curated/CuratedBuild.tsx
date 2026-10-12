'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { request, getAssets, labels, money, options, selected, shortCaseName, type Chassis, type Configuration, type Evaluation, type Product, type Slot } from '@/lib/studio';
import type { ResolvedAsset } from '@/lib/asset-api';
import { addCartItem } from '@/lib/cart';
import '../studio/studio.css';
import CaseGalleryModal from './CaseGalleryModal';
import ProductDetailsModal from './ProductDetailsModal';

const Scene = dynamic(() => import('../studio/StudioScene'), { ssr: false });
type Definition = { id: string; name: string; segment: string; tier: string; description: string; use?: string; playbook_id: number | null; components: Record<string,string> };
type Choice = Product & { choice_label?: string; automatic_upsell?: boolean; market_median_price?: number; baseline_market_median_price?: number; playbook_upgrade_only?: boolean; approved_upgrade?: { candidate_index: number; from_sku: string; to_sku: string; performance_evidence?: { metric: string; baseline_score: number; candidate_score: number } | null }; customer_option?: { interface?: string; capacity_gb?: number; memory_type?: string } };
type CuratedSlot = Slot & { default_variant_id?: number; upgrade_budget_ceiling?: number | null };
type ComponentStep = { category: string; slot?: CuratedSlot };
type PerformanceReport = { parts: { slot: string; title: string; specifications: Record<string, unknown>; customer_option: Record<string, unknown> }[]; component_benchmarks: Record<string, { model: string; overall_score: number | null; gaming_score: number | null; workstation_score: number | null; source: string; source_url: string | null; confidence: number; refreshed_at: string | null } | null>; notice: string };
type BuildPanel = 'photos' | 'performance' | 'specifications';
const colours = ['#ff7426','#6d9dff','#b18aff','#48e0c1','#f0e8d9'];
const escapeHtml = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]!));

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
  const [panel, setPanel] = useState<BuildPanel>('photos');
  const [galleryPhotoIndex, setGalleryPhotoIndex] = useState(0);
  const [performanceReport, setPerformanceReport] = useState<PerformanceReport|null>(null);
  const [performanceError, setPerformanceError] = useState('');
  const [activeStep, setActiveStep] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(true);
  const [caseGalleryOpen, setCaseGalleryOpen] = useState(false);
  const [detail, setDetail] = useState<{ product?: Product; caseItem?: Chassis; baselineVariantId?: number; curatedBuildId?: string; candidateIndex?: number } | null>(null);
  const closeDetail = useCallback(() => setDetail(null), []);
  const closeCaseGallery = useCallback(() => setCaseGalleryOpen(false), []);
  const signature = JSON.stringify({ playbook_id: definition?.playbook_id, selections: config.selections, case_id: config.caseId, build_mode: 'curated', curated_build_id: buildId });
  const fresh = signature === quoteKey;
  const chassis = cases.find(c => c.id===config.caseId);
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
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(preference.matches);
    update();
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  },[]);
  useEffect(() => {
    if (!loaded || !definition?.playbook_id) return;
    const controller = new AbortController();
    request<Evaluation>('studio/evaluate',controller.signal,JSON.parse(signature)).then(q => {setQuote(q);setQuoteKey(signature);}).catch(e => {if(e.name!=='AbortError') setError(e.message);});
    setPerformanceReport(null); setPerformanceError('');
    request<PerformanceReport>('studio/performance',controller.signal,JSON.parse(signature)).then(setPerformanceReport).catch(e => {if(e.name!=='AbortError') setPerformanceError(e.message);});
    getAssets(slots,config,controller.signal,chassis?.asset_subject_id).then(setAssets).catch(() => { if (!controller.signal.aborted) setAssets({}); });
    setGalleryPhotoIndex(0);
    return () => controller.abort();
  },[signature,loaded,definition?.playbook_id,slots,config,chassis?.asset_subject_id]);
  const parts = [...(chassis?[{category:'case',id:chassis.id,title:chassis.name,asset:assets['case:'+chassis.id]}]:[]),...slots.flatMap(s=>{const p=selected(s,config);return p?[{category:s.slot_type,id:p.id,title:p.title,asset:assets['variant:'+p.id]}]:[];})];
  const componentSteps = useMemo<ComponentStep[]>(() => [
    ...slots.filter(slot=>slot.slot_type!=='case'&&options(slot).length>0)
      .sort((a,b)=>['cpu','motherboard','ram','gpu','storage','cooling','psu','fan','os'].indexOf(a.slot_type)-['cpu','motherboard','ram','gpu','storage','cooling','psu','fan','os'].indexOf(b.slot_type))
      .map(slot=>({category:slot.slot_type,slot})),
    ...(cases.length ? [{category:'case'}] : []),
  ],[slots,cases.length]);
  const currentStep = componentSteps[activeStep] ?? componentSteps[0] ?? {category:'case'};
  const allCurrentOptions: Choice[] = currentStep?.category==='case'
    ? cases.map(item=>({id:item.id,title:item.name,display_price:item.rrp_gbp,images:item.images,specifications:{brand:item.brand,form_factor:item.form_factor,width_mm:item.width_mm,height_mm:item.height_mm,depth_mm:item.depth_mm}}))
    : currentStep?.slot ? options(currentStep.slot) as Choice[] : [];
  const currentDefaultId = currentStep?.category==='case' ? cases[0]?.id : currentStep?.slot?.default_variant_id;
  const currentChoice = allCurrentOptions.find(item=>item.id===(currentStep?.category==='case'?config.caseId:currentStep?.slot?config.selections[currentStep.slot.slot_id]:undefined));
  const currentOptions = allCurrentOptions.filter(choice=>{
    if(!choice.automatic_upsell) return true;
    if(currentStep?.slot && choice.id===config.selections[currentStep.slot.slot_id]) return true;
    const slot = currentStep?.slot;
    if(!slot || !fresh || !quote?.price || !currentChoice || !slot.upgrade_budget_ceiling) return false;
    const verdict = quote.verdicts.find(item=>item.slot_id===slot.slot_id)?.variants.find(item=>item.variant_id===choice.id);
    const projectedTotal = quote.price.total + (choice.display_price-currentChoice.display_price)*1.1;
    return verdict?.is_compatible === true && projectedTotal <= slot.upgrade_budget_ceiling;
  });
  const recommendedChoice = currentOptions.find(item=>item.id===currentDefaultId);
  const adviceUse = definition?.use ?? `${definition?.segment ?? 'this build'} workload`;
  const chooseStepOption = (id:number) => {
    if(currentStep?.category==='case') setCaseGalleryOpen(true);
    else if(currentStep?.slot) choose(currentStep.slot,id);
  };
  const chooseCase = useCallback((item:Chassis) => {
    setConfig(value=>({...value,caseId:item.id}));
    setCaseGalleryOpen(false);
  },[]);
  const openChoiceDetails = (choice:Choice) => setDetail({
    product: choice,
    baselineVariantId: choice.id!==currentDefaultId ? currentDefaultId : undefined,
    curatedBuildId: choice.approved_upgrade ? buildId : undefined,
    candidateIndex: choice.approved_upgrade?.candidate_index,
  });
  const changeStep = (delta:number) => setActiveStep(index=>Math.max(0,Math.min(componentSteps.length-1,index+delta)));
  const choiceAdvice = (choice:Choice) => {
    const baseline = recommendedChoice;
    if(!baseline || choice.id===baseline.id) return `Recommended starting point for ${adviceUse}.`;
    const upgrade = choice.approved_upgrade;
    const evidence = upgrade?.performance_evidence;
    const gain = evidence && evidence.baseline_score>0 ? Math.round((evidence.candidate_score/evidence.baseline_score-1)*100) : null;
    const category = currentStep?.category;
    const capacity = choice.customer_option?.capacity_gb;
    const baselineCapacity = baseline.customer_option?.capacity_gb;
    if(category==='case') return 'Changes the case appearance and features. The compatibility check will be re-run with your selected components before checkout.';
    if(category==='gpu'&&/(office|business|student|family|home)/i.test(`${definition?.segment} ${adviceUse}`)) return `This Playbook is aimed at ${adviceUse}, where a dedicated graphics upgrade may do little for everyday tasks unless you also game, edit video, use 3D tools or run GPU-heavy AI. Consider another component upgrade or keep the total lower. You can still choose this GPU.`;
    if(category==='ram'&&capacity&&baselineCapacity&&capacity>baselineCapacity&&/(gaming|esports)/i.test(adviceUse)&&baselineCapacity>=32) return `For ${adviceUse}, the recommended ${baselineCapacity} GB already gives most games room to run. More memory mainly helps if you run unusually heavy games, creative apps or many demanding tasks together; if not, another component or keeping the money may be better value.`;
    if(category==='ram'&&capacity&&baselineCapacity&&capacity>baselineCapacity) return `More memory headroom for ${adviceUse}, especially with several demanding apps or large projects open. More RAM helps most when your current workload is running short of memory.`;
    if(category==='storage'&&capacity&&baselineCapacity&&capacity>baselineCapacity) { const added=capacity-baselineCapacity; const amount=added>=1024?`${(added/1024).toLocaleString()} TB`:`${added.toLocaleString()} GB`; return `Adds ${amount} of space over the recommended drive, so you can keep more games, apps and files installed.`; }
    if(gain!==null) return `The reviewed ${evidence.metric.replaceAll('_',' ')} score is ${gain}% higher than the recommended ${baseline.title}. That can provide more ${category==='gpu'?'graphics':'processing'} headroom for ${adviceUse}; it is not a frame-rate or whole-PC guarantee.`;
    if(choice.automatic_upsell) return `This available option has a higher market median than the recommended ${baseline.title}. It passed the system compatibility and Playbook budget checks; open the product details to compare its features.`;
    if(category==='cooling') return `Offers more cooling headroom for sustained workloads such as ${adviceUse}. Actual temperatures and noise depend on the complete build and testing.`;
    return `An alternative to the recommended ${baseline.title} for ${adviceUse}. Check the listed specifications and live price to decide whether its extra features are useful to you.`;
  };
  const galleryPhotos = useMemo(() => [
    ...(chassis?.images ?? []).map((url,index)=>({url,label:`${shortCaseName(chassis.name,chassis.brand)} photo ${index+1}`,category:'Case'})),
    ...slots.flatMap(slot => {
      const product = selected(slot,config);
      return (product?.images ?? []).map((url,index)=>({url,label:`${labels[slot.slot_type] ?? slot.slot_type} photo ${index+1}`,category:labels[slot.slot_type] ?? slot.slot_type}));
    }),
  ],[chassis,slots,config]);
  const specParts = useMemo(() => [
    ...(chassis ? [{category:'Case',title:chassis.name,specifications:{brand:chassis.brand,form_factor:chassis.form_factor,width_mm:chassis.width_mm,height_mm:chassis.height_mm,depth_mm:chassis.depth_mm,max_gpu_length_mm:chassis.max_gpu_length_mm,max_cooler_height_mm:chassis.max_cooler_height_mm,...(chassis.engineering ?? {})}}] : []),
    ...slots.flatMap(slot => { const product=selected(slot,config) as Choice|undefined; return product ? [{category:labels[slot.slot_type] ?? slot.slot_type,title:product.title,specifications:{...(product.specifications ?? {}),...(product.customer_option ?? {})}}] : []; }),
  ],[chassis,slots,config]);
  const reportHtml = useMemo(() => {
    const selectedTitle = (category: string) => { const slot=slots.find(item=>item.slot_type===category); return slot ? selected(slot,config)?.title ?? 'No selected component' : 'No selected component'; };
    const benchmarkRows = (['cpu','gpu'] as const).map(category => {
      const item=performanceReport?.component_benchmarks?.[category];
      return `<tr><th>${category.toUpperCase()}</th><td>${escapeHtml(item?.model ?? selectedTitle(category))}</td><td>${item?.overall_score ?? 'No matching benchmark'}</td><td>${escapeHtml(item?.source ?? '—')}</td></tr>`;
    }).join('');
    const partsRows = specParts.map(part => `<tr><th>${escapeHtml(part.category)}</th><td>${escapeHtml(part.title)}</td></tr>`).join('');
    return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${escapeHtml(definition?.name ?? 'Curated build')} performance</title><style>body{font:16px system-ui;background:#07111b;color:#e7f1ff;margin:0;padding:32px}main{max-width:900px;margin:auto}h1{color:#b7ff42}section{background:#101b28;border:1px solid #26394d;border-radius:16px;padding:22px;margin:18px 0}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #26394d}small{color:#9aacc0}.notice{color:#ffd88a}</style><main><h1>${escapeHtml(definition?.name ?? 'Curated build')}</h1><p>${escapeHtml(definition?.segment ?? '')} · ${escapeHtml(definition?.tier ?? '')}</p><section><h2>Selected components</h2><table>${partsRows}</table></section><section><h2>Component benchmark references</h2><table><thead><tr><th>Part</th><th>Model</th><th>Overall score</th><th>Source</th></tr></thead><tbody>${benchmarkRows}</tbody></table><p class="notice">${escapeHtml(performanceReport?.notice ?? 'Benchmark lookup is loading.')}</p><small>These component scores are not measured results for this assembled PC and do not predict in-game frame rates.</small></section></main></html>`;
  },[definition,performanceReport,slots,config,specParts]);
  const performanceHtmlUrl = `data:text/html;charset=utf-8,${encodeURIComponent(reportHtml)}`;
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
  return <main className="mx-auto w-full max-w-[1800px] px-4 py-6 text-primary sm:px-6 xl:px-10">
    <Link href="/products" className="text-sm text-secondary transition-colors hover:text-primary">← Curated builds</Link>
    {error && <p role="alert" className="mt-5">{error}</p>}
    {!loaded ? <p className="py-20">Loading your build…</p> : definition && <>
      <header className="mb-5 mt-5 flex flex-wrap items-end justify-between gap-4 lg:mb-2">
        <div><p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-200">{definition.segment} · {definition.tier}</p><h1 className="mt-1 text-3xl font-semibold tracking-tight md:text-4xl">{definition.name}</h1><p className="mt-1 text-sm text-secondary">{definition.description}</p></div>
        <p className="max-w-md text-sm text-secondary lg:text-right">Make it yours, one component at a time. Your live 3D build updates as you choose.</p>
      </header>
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.7fr)_minmax(360px,.76fr)] lg:gap-8 xl:gap-12">
      <section aria-label="Live 3D build and product information" className="min-w-0">
        <div className="curated-preview relative h-[58vh] min-h-[420px] overflow-hidden md:h-[min(78vh,920px)] md:min-h-[620px]">
          {parts.length ? <Scene parts={parts} active={currentStep?.category??'case'} onSelect={category=>{const index=componentSteps.findIndex(step=>step.category===category);if(index>=0)setActiveStep(index);}} mode="assembled" open={false} accent={accent} rotating={!reducedMotion} resetKey={activeStep} reducedMotion={reducedMotion}/> : <div className="flex h-full items-center justify-center p-10 text-center text-secondary">Product preview will appear when its catalogue components are available.</div>}
          <div className="absolute bottom-4 left-4 right-4 flex items-end justify-between gap-4 pointer-events-none"><span className="rounded-full bg-slate-950/45 px-3 py-2 text-xs text-white/80 backdrop-blur-sm">Drag to orbit · Scroll or pinch to zoom</span><div className="pointer-events-auto flex items-center gap-3 rounded-full bg-slate-950/45 px-4 py-2 backdrop-blur-sm" aria-label="Preview fan lighting">{colours.map((c,i)=><button key={c} type="button" aria-label={['Ember','Ice','Violet','Mint','Pearl'][i]+' fan lighting'} aria-pressed={accent===c} onClick={()=>setAccent(c)} className="h-4 w-4 cursor-pointer rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white" style={{background:c,boxShadow:accent===c?'0 0 0 2px white':''}}/>)}</div></div>
        </div>
        <p className="-mt-1 text-center text-xs text-secondary">The preview responds to your selected components. Models appear where approved catalogue assets are available.</p>
        <div role="tablist" aria-label="Build details" className="mt-8 flex flex-wrap gap-6 border-b border-white/10">
          {([['photos','Product photos'],['performance','Performance'],['specifications','Specifications']] as const).map(([id,label])=><button key={id} type="button" role="tab" aria-selected={panel===id} onClick={()=>setPanel(id)} className={`relative cursor-pointer py-3 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300 ${panel===id?'text-cyan-200 after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-cyan-300':'text-secondary hover:text-primary'}`}>{label}</button>)}
        </div>
        {panel==='photos' && <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="text-xs text-secondary">Photos for the components currently selected. Changing a part updates this gallery.</p>
          {galleryPhotos.length ? <><div className="mt-3 flex aspect-square items-center justify-center overflow-hidden rounded-xl bg-white"><img src={galleryPhotos[Math.min(galleryPhotoIndex,galleryPhotos.length-1)].url} alt={galleryPhotos[Math.min(galleryPhotoIndex,galleryPhotos.length-1)].label} className="h-full w-full object-contain"/></div><p className="mt-2 text-xs text-secondary">{galleryPhotos[Math.min(galleryPhotoIndex,galleryPhotos.length-1)].category} · {galleryPhotoIndex+1} of {galleryPhotos.length}</p><div className="mt-3 grid grid-cols-4 gap-2">{galleryPhotos.map((photo,index)=><button key={`${photo.url}-${index}`} type="button" aria-label={`Show ${photo.label}`} aria-pressed={galleryPhotoIndex===index} onClick={()=>setGalleryPhotoIndex(index)} className={`aspect-square cursor-pointer overflow-hidden rounded-lg border bg-white ${galleryPhotoIndex===index?'border-cyan-300 ring-2 ring-cyan-400/40':'border-[var(--color-border)]'}`}><img src={photo.url} alt="" className="h-full w-full object-contain" loading="lazy"/></button>)}</div></> : <div className="flex aspect-square items-center justify-center rounded-xl bg-[var(--color-surface-alt)] p-8 text-center text-sm text-secondary">No product photos are available for the current selections.</div>}
          <p className="mt-3 text-[11px] text-secondary">These are component product photos; they are not photographs of this exact assembled PC.</p>
        </div>}
        {panel==='performance' && <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">Performance for this configuration</h2><p className="mt-1 text-xs text-secondary">Updates when you change any selected component.</p></div><a href={performanceHtmlUrl} target="_blank" rel="noreferrer" className="rounded-lg border border-cyan-400/40 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-400/10">Open performance HTML</a></div>
          {performanceError && <p role="alert" className="mt-4 rounded-lg border border-rose-400/30 bg-rose-400/10 p-3 text-sm">{performanceError}</p>}
          {!performanceReport ? <p className="mt-5 text-sm text-secondary">Loading benchmark evidence for your selected processor and graphics card…</p> : <><div className="mt-5 grid gap-3 sm:grid-cols-2">{(['cpu','gpu'] as const).map(category=>{const item=performanceReport.component_benchmarks?.[category];const slot=slots.find(candidate=>candidate.slot_type===category);return <article key={category} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-4"><p className="text-xs uppercase tracking-wider text-secondary">{category==='cpu'?'Processor':'Graphics card'}</p><h3 className="mt-1 font-semibold">{item?.model ?? (slot ? selected(slot,config)?.title : undefined) ?? 'Not selected'}</h3><p className="mt-3 text-2xl font-bold text-cyan-200">{item?.overall_score ?? '—'}</p><p className="text-xs text-secondary">{item ? `${item.source} component benchmark` : 'No matching benchmark currently available'}</p>{item?.source_url&&<a href={item.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-cyan-300 underline">Benchmark source</a>}</article>})}</div><p className="mt-4 rounded-lg border border-amber-400/25 bg-amber-400/5 p-3 text-xs text-amber-100">{performanceReport.notice} No game FPS estimate is available for this configuration yet.</p></>}
        </div>}
        {panel==='specifications' && <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">Selected build specifications</h2><p className="mt-1 text-xs text-secondary">This sheet follows your current RAM, SSD, case and component choices.</p></div><a href={`data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html><html><meta charset="utf-8"><title>${escapeHtml(definition?.name ?? 'Build')} specifications</title><style>body{font:16px system-ui;background:#07111b;color:#e7f1ff;padding:32px}main{max-width:900px;margin:auto}h1{color:#b7ff42}article{background:#101b28;border:1px solid #26394d;border-radius:12px;padding:16px;margin:10px 0}dt{color:#9aacc0;text-transform:capitalize}dd{margin:3px 0 12px}</style><main><h1>${escapeHtml(definition?.name ?? 'Curated build')}</h1>${specParts.map(part=>`<article><h2>${escapeHtml(part.category)}: ${escapeHtml(part.title)}</h2><dl>${Object.entries(part.specifications).filter(([,value])=>value!==null&&value!==undefined&&value!=='').map(([key,value])=>`<dt>${escapeHtml(key.replaceAll('_',' '))}</dt><dd>${escapeHtml(typeof value==='object'?JSON.stringify(value):value)}</dd>`).join('')}</dl></article>`).join('')}</main></html>`)}`} target="_blank" rel="noreferrer" className="rounded-lg border border-cyan-400/40 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-400/10">Open specifications HTML</a></div><div className="mt-4 space-y-3">{specParts.map(part=><article key={`${part.category}-${part.title}`} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-4"><h3 className="font-semibold">{part.category} · {part.title}</h3>{Object.entries(part.specifications).filter(([,value])=>value!==null&&value!==undefined&&value!=='').length>0?<dl className="mt-3 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2">{Object.entries(part.specifications).filter(([,value])=>value!==null&&value!==undefined&&value!=='').map(([key,value])=><div key={key}><dt className="text-xs capitalize text-secondary">{key.replaceAll('_',' ')}</dt><dd>{typeof value==='object'?JSON.stringify(value):String(value)}</dd></div>)}</dl>:<p className="mt-2 text-xs text-secondary">Technical specifications have not been supplied in the catalogue.</p>}</article>)}</div></div>}
      </section>
      <section className="min-w-0 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:pr-2">
        <p className="text-sm leading-6 text-secondary">{adviceUse}. The recommended starting build is already selected. Choose a component to see compatible options and what each change means.</p>
        {componentSteps.length>0 && <section aria-label="Guided component choices" className="mt-5">
          <div className="flex items-end justify-between gap-3"><div><p className="text-xs uppercase tracking-wider text-secondary">Step {activeStep+1} of {componentSteps.length}</p><h2 className="mt-1 text-2xl font-semibold">Choose your {labels[currentStep.category]??currentStep.category}</h2></div><span className="pb-1 text-xs text-secondary">{currentOptions.length} options</span></div>
          <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-cyan-300 transition-all duration-300" style={{width:`${((activeStep+1)/componentSteps.length)*100}%`}}/></div>
          <nav aria-label="Component steps" className="mt-3 flex flex-wrap gap-x-4 gap-y-1">{componentSteps.map((step,index)=><button key={step.category} type="button" aria-current={activeStep===index?'step':undefined} onClick={()=>setActiveStep(index)} className={`cursor-pointer py-1 text-xs transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300 ${activeStep===index?'font-semibold text-cyan-200':'text-secondary hover:text-primary'}`}>{labels[step.category]??step.category}</button>)}</nav>
          <div className="mt-4 space-y-3" role="group" aria-label={`${labels[currentStep.category]??currentStep.category} options`}>
            {currentStep.category==='case' ? <div className="py-4">
              <p className="text-xs uppercase tracking-wider text-cyan-200">Current case · {chassis?.form_factor?.toUpperCase()}</p><h3 className="mt-1 text-lg font-semibold">{chassis?shortCaseName(chassis.name,chassis.brand):'Choose your case'}</h3><p className="mt-1 text-sm text-secondary">{chassis?money(chassis.rrp_gbp):'Compare the available cases for this build.'}</p><button type="button" onClick={()=>chassis&&setDetail({caseItem:chassis})} disabled={!chassis} className="mt-2 cursor-pointer text-sm text-cyan-200 underline underline-offset-4 disabled:opacity-40">View case details</button>
              <button type="button" onClick={()=>setCaseGalleryOpen(true)} className="mt-4 flex w-full cursor-pointer items-center justify-between gap-3 bg-cyan-300/[.06] px-4 py-4 text-left text-sm transition-colors hover:bg-cyan-300/[.12] focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"><span><span className="block font-semibold">Explore all {cases.length} cases</span><span className="mt-1 block text-xs text-secondary">Filter by size, compare similar designs and browse the 3D gallery.</span></span><span aria-hidden="true" className="text-2xl text-cyan-200">→</span></button>
            </div> : currentOptions.map(choice=>{
              const isSelected=currentChoice?.id===choice.id;
              const isRecommended=choice.id===currentDefaultId;
              const delta=choice.display_price-(recommendedChoice?.display_price??choice.display_price);
              const hasReviewedOffer=Boolean(choice.automatic_upsell||choice.playbook_upgrade_only||choice.approved_upgrade);
              const badge=isRecommended?'Playbook recommendation':choice.automatic_upsell?'Eligible upgrade':hasReviewedOffer?'Reviewed upgrade':'Available option';
              return <article key={choice.id} className={`border-b border-white/10 py-4 transition-colors ${isSelected?'bg-cyan-300/[.07] shadow-[-3px_0_0_0_#67e8f9]':''}`}>
                <button type="button" aria-pressed={isSelected} disabled={adding} onClick={()=>chooseStepOption(choice.id)} className="block w-full cursor-pointer text-left">
                  <span className="flex flex-wrap items-start justify-between gap-2"><span className="font-semibold">{choice.choice_label??choice.title}</span><span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${isRecommended?'bg-emerald-400/10 text-emerald-200':hasReviewedOffer?'bg-violet-400/10 text-violet-200':'bg-slate-400/10 text-secondary'}`}>{badge}</span></span>
                  <span className="mt-2 block text-xs font-medium text-cyan-100">{delta===0?'Included in the recommended build':`${delta>0?'+':''}${money(delta)} vs Playbook recommendation`}</span>
                  {choice.automatic_upsell&&choice.market_median_price!=null&&<span className="mt-1 block text-xs text-secondary">Market median {money(choice.market_median_price)} · above the recommended part</span>}
                  <span className="mt-2 block text-xs leading-5 text-secondary">{choiceAdvice(choice)}</span>
                </button>
                <button type="button" onClick={()=>openChoiceDetails(choice)} className="mt-3 text-xs font-semibold text-cyan-200 underline underline-offset-4 hover:text-white">View product details</button>
                {currentChoice&&currentChoice.id===choice.id&&delta!==0&&<p className="mt-3 border-t border-amber-300/15 pt-3 text-xs leading-5 text-amber-50">This choice {delta>0?`adds ${money(delta)}`:`saves ${money(Math.abs(delta))}`} compared with the Playbook recommendation. If you do not expect to use the extra capability for {adviceUse}, you could keep that money for another component or reduce your total. Your choices remain yours.</p>}
              </article>;
            })}
            {currentStep.category!=='case'&&!currentOptions.length&&<p className="rounded-xl border border-amber-400/20 p-4 text-sm text-secondary">No compatible upgrade with a higher market median is available within this Playbook segment’s budget. The recommended component remains selected.</p>}
          </div>
          <div className="mt-4 flex justify-between gap-3"><button type="button" disabled={activeStep===0} onClick={()=>changeStep(-1)} className="cursor-pointer py-2 text-sm text-secondary hover:text-primary disabled:opacity-40">← Previous</button><button type="button" disabled={activeStep>=componentSteps.length-1} onClick={()=>changeStep(1)} className="cursor-pointer py-2 text-sm font-semibold text-cyan-200 hover:text-white disabled:opacity-40">Next component →</button></div>
        </section>}
        <details className="mt-6 border-y border-[var(--color-border)] py-4"><summary className="cursor-pointer text-sm">Review selected components</summary><dl className="mt-4 space-y-3 text-sm">{parts.map(part=><div key={`${part.category}-${part.id}`}><dt className="text-secondary">{labels[part.category]??part.category}</dt><dd><button type="button" onClick={()=>part.category==='case'&&chassis?setDetail({caseItem:chassis}):setDetail({product:selected(slots.find(slot=>slot.slot_type===part.category)!,config)})} className="text-left font-medium text-cyan-200 underline underline-offset-4 hover:text-white">{part.title}</button></dd></div>)}</dl></details>
        <div className="mt-6 border-t border-white/15 pt-5"><p className="text-xs uppercase tracking-wider text-secondary">Your current build</p><p className="mt-1 text-3xl font-semibold tabular-nums">{fresh&&quote?.price?money(quote.price.total):'Price pending'}</p><p className="mt-1 text-xs text-secondary">Assembly included · Live catalogue pricing</p></div>
        <button disabled={!fresh||!quote?.can_checkout||adding} onClick={add} className="mt-4 w-full cursor-pointer rounded-md bg-[#ff7426] px-5 py-4 font-semibold text-black transition-colors hover:bg-orange-300 disabled:opacity-40">{adding?'Checking availability…':'Continue with this build →'}</button>
        {loaded&&(!fresh||!quote?.can_checkout)&&<p className="mt-3 text-sm text-secondary">{!fresh&&definition.playbook_id?'Checking this configuration…':'We’re confirming stock and compatibility for this build.'}</p>}
        {notice&&<p role="status" className="mt-3 text-sm">{notice} <Link href="/cart">View cart →</Link></p>}
      </section>
    </div></>}
    {caseGalleryOpen&&<CaseGalleryModal cases={cases} selectedId={config.caseId} onClose={closeCaseGallery} onChoose={chooseCase} onDetails={item=>setDetail({caseItem:item})}/>}
    <ProductDetailsModal detail={detail} onClose={closeDetail}/>
  </main>;
}
