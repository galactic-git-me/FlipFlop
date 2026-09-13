'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowUpRight, ArrowLeft, Check, ChevronRight, CircleHelp, Cpu, Expand, Eye, Layers3, LoaderCircle, Maximize2, Monitor, Package, Pause, Play, RotateCcw, Search, ShieldCheck, SlidersHorizontal, Trash2, Undo2, X, Box, Share2, Download, AlertTriangle } from 'lucide-react';
import { assetURL, changePart, defaults, getAssets, labels, money, options, order, request, selected, type Chassis, type Configuration, type Evaluation, type Product, type Slot } from '@/lib/studio';
import type { ResolvedAsset } from '@/lib/asset-api';
import { addCartItem } from '@/lib/cart';
import type { ScenePart } from './StudioScene';
import './studio.css';

const Scene = dynamic(() => import('./StudioScene'), { ssr: false, loading: () => <div className="studio-loading"><LoaderCircle className="studio-spin" size={26} /><span>Preparing your private showroom</span></div> });
type Playbook = { id: number; name: string };
const EMPTY: Configuration = { selections: {}, caseId: null };
const accents = ['#ff7426','#6d9dff','#b18aff','#48e0c1','#f0e8d9'];
const cleanName = (title: string) => title.replace(/\s+/g,' ').trim();

function ProductImage({ src, alt, large = false }: { src?: string; alt: string; large?: boolean }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  return <div className={large ? 'studio-product-image large' : 'studio-product-image'}>{src && !failed ? <img src={assetURL(src) || undefined} alt={alt} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} /> : <Box size={large ? 44 : 22} strokeWidth={1} />}</div>;
}

export default function Studio() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [playbook, setPlaybook] = useState(0);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [cases, setCases] = useState<Chassis[]>([]);
  const [config, setConfig] = useState<Configuration>(EMPTY);
  const [history, setHistory] = useState<Configuration[]>([]);
  const [active, setActive] = useState('case');
  const [tab, setTab] = useState<'parts'|'details'|'checks'>('parts');
  const [choosing, setChoosing] = useState(false);
  const [search, setSearch] = useState('');
  const [mode, setMode] = useState<'assembled'|'exploded'|'xray'>('assembled');
  const [open, setOpen] = useState(true);
  const [accent, setAccent] = useState(accents[0]);
  const [rotating, setRotating] = useState(true);
  const [resetKey, setResetKey] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [evaluation, setEvaluation] = useState<Evaluation|null>(null);
  const [evaluatedKey, setEvaluatedKey] = useState('');
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState('');
  const [assets, setAssets] = useState<Record<string,ResolvedAsset|null>>({});
  const [assetError, setAssetError] = useState(false);
  const [notice, setNotice] = useState('');
  const [lastSync, setLastSync] = useState('');
  const stage = useRef<HTMLDivElement>(null);
  const initialized = useRef(0);
  const configRef = useRef(config); configRef.current = config;
  const signature = JSON.stringify({ playbook_id: playbook, selections: config.selections, case_id: config.caseId });
  const fresh = signature === evaluatedKey && !checking && !loading && !error && !checkError;
  const chassis = cases.find(c => c.id === config.caseId);
  const activeSlot = slots.find(s => s.slot_type === active);
  const product = activeSlot ? selected(activeSlot,config) : undefined;
  const title = active === 'case' ? chassis?.name : product?.title;
  const price = active === 'case' ? chassis?.rrp_gbp : product?.display_price;
  const issues = fresh ? evaluation?.checks.filter(c => c.severity !== 'pass') ?? [] : [];
  const failures = issues.filter(c => c.severity === 'error');
  const pending = issues.filter(c => c.severity === 'unknown');
  const priceEstimate = slots.reduce((sum,s) => sum+(selected(s,config)?.display_price ?? 0),0)+(chassis?.rrp_gbp ?? 0);
  const total = fresh && evaluation?.price ? evaluation.price.total : null;
  const playbookName = playbooks.find(p => p.id === playbook)?.name ?? 'Custom build';
  const sceneParts = useMemo<ScenePart[]>(() => [
    ...(chassis ? [{ category:'case', id:chassis.id, title:chassis.name, asset:assets['case:'+chassis.id] }] : []),
    ...slots.flatMap(s => { const p=selected(s,config); return p ? [{ category:s.slot_type,id:p.id,title:p.title,asset:assets['variant:'+p.id] }] : []; })
  ], [slots,config,chassis,assets]);
  const exactCount = sceneParts.filter(p => p.asset?.fallback_level === 'exact' && p.asset.scale_validated).length;

  useEffect(() => {
    const media = matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(media.matches); update(); media.addEventListener('change',update);
    return () => media.removeEventListener('change',update);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    request<Playbook[]>('playbooks',controller.signal).then(data => {
      setPlaybooks(data);
      const requested = Number(new URLSearchParams(location.search).get('playbook'));
      setPlaybook(current => data.some(p => p.id===current) ? current : data.some(p => p.id===requested) ? requested : data[0]?.id ?? 0);
      if (!data.length) { setError('No curated builds are currently published. Please check back shortly.'); setLoading(false); }
    }).catch(e => { if (e.name !== 'AbortError') { setError(e.message); setLoading(false); } });
    return () => controller.abort();
  }, [refresh]);
  useEffect(() => {
    if (!playbook) return;
    const controller = new AbortController(); setLoading(true); setError('');
    Promise.all([request<Slot[]>('playbooks/'+playbook+'/custom-slots',controller.signal),request<Chassis[]>('cases',controller.signal)]).then(([s,c]) => {
      setSlots(s.sort((a,b) => order.indexOf(a.slot_type)-order.indexOf(b.slot_type))); setCases(c);
      if (initialized.current !== playbook) {
        const next = defaults(s,c);
        const query = new URLSearchParams(location.search);
        if (Number(query.get('playbook')) === playbook) {
          try { const saved = JSON.parse(query.get('parts') || '{}'); for (const slot of s) if (options(slot).some(p => p.id === saved[slot.slot_id])) next.selections[slot.slot_id] = saved[slot.slot_id]; } catch { /* Ignore malformed shared selections. */ }
          const caseId = Number(query.get('case')); if (c.some(row => row.id===caseId)) next.caseId=caseId;
        }
        setConfig(next); setHistory([]); initialized.current=playbook;
      }
      setLastSync(new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'})); setLoading(false);
    }).catch(e => { if(e.name !== 'AbortError') { setError(e.message); setLoading(false); } });
    return () => controller.abort();
  }, [playbook,refresh]);
  useEffect(() => {
    const update = () => { if (document.visibilityState==='visible') setRefresh(n=>n+1); };
    const timer=setInterval(update,120000); document.addEventListener('visibilitychange',update);
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange',update); };
  }, []);
  useEffect(() => {
    if(!playbook || loading || error) return;
    const controller=new AbortController(); setChecking(true); setCheckError('');
    const timer=setTimeout(() => {
      request<Evaluation>('studio/evaluate',controller.signal,JSON.parse(signature)).then(result => { setEvaluation(result); setEvaluatedKey(signature); setChecking(false); }).catch(e => { if(e.name!=='AbortError') { setCheckError(e.message); setChecking(false); } });
    },180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [playbook,signature,loading,error,refresh]);
  useEffect(() => {
    if(!slots.length || loading) return;
    const controller=new AbortController(); setAssets({}); setAssetError(false);
    getAssets(slots,config,controller.signal).then(setAssets).catch(e => { if(e.name!=='AbortError') setAssetError(true); });
    return () => controller.abort();
  }, [slots,config,loading]);
  useEffect(() => { if (!notice) return; const timer=setTimeout(()=>setNotice(''),4500); return ()=>clearTimeout(timer); },[notice]);

  const commit = useCallback((next: Configuration) => { setHistory(h => [...h.slice(-29),configRef.current]); setConfig(next); },[]);
  const pick = (category: string) => { setActive(category); setTab('details'); setChoosing(false); setResetKey(n=>n+1); };
  const replace = (category: string) => { setActive(category); setTab('parts'); setChoosing(true); setSearch(''); };
  const remove = () => { commit(active==='case' ? {...config,caseId:null} : activeSlot ? changePart(config,activeSlot.slot_id,null) : config); setNotice((labels[active] || active)+' removed. Other selections preserved.'); };
  const undo = () => { const previous=history.at(-1); if(previous) {setConfig(previous);setHistory(h=>h.slice(0,-1));} };
  const share = async () => { const url=new URL('/studio',location.origin); url.searchParams.set('playbook',String(playbook));url.searchParams.set('parts',JSON.stringify(config.selections));if(config.caseId)url.searchParams.set('case',String(config.caseId));try { await navigator.clipboard.writeText(url.href);setNotice('Build link copied. Prices refresh when the link is opened.'); } catch {setNotice('Sharing is unavailable in this browser. Use Export build to save your selections.');} };
  const download = () => { const build={playbook_id:playbook,playbook_name:playbookName,selections:config.selections,case_id:config.caseId,components:sceneParts.map(p=>({category:p.category,id:p.id,title:p.title})),quoted_at:new Date().toISOString(),total_gbp:total,checks:fresh ? evaluation?.checks : [],engineering_status:fresh&&evaluation?.can_checkout?'verified':'requires_verification'}; const url=URL.createObjectURL(new Blob([JSON.stringify(build,null,2)],{type:'application/json'})); const a=document.createElement('a');a.href=url;a.download='flipflop-build.json';a.click();URL.revokeObjectURL(url);setNotice('Build exported with product IDs and verification status.'); };
  const cart = async () => {
    if(!fresh || !evaluation?.can_checkout || total===null) return;
    setChecking(true);
    try {
      const verified=await request<Evaluation>('studio/evaluate',undefined,JSON.parse(signature));
      if(signature!==JSON.stringify({playbook_id:playbook,selections:configRef.current.selections,case_id:configRef.current.caseId})) return;
      setEvaluation(verified);setEvaluatedKey(signature);
      if(!verified.can_checkout || !verified.price) {setNotice('This build needs attention before checkout.');setTab('checks');return;}
      addCartItem({kind:'configured',validationMode:'studio',title:playbookName,playbookId:playbook,playbookName,slotSelections:config.selections,caseId:config.caseId,chosenWeek:null,displayTotal:verified.price.total,componentSummary:sceneParts.map(p=>p.title)});
      setNotice('Build added to your cart.');
    } catch(e) {setCheckError(e instanceof Error ? e.message : 'Could not verify the build.');} finally {setChecking(false);}
  };
  const list = active==='case' ? cases.map(c => ({id:c.id,title:c.name,display_price:c.rrp_gbp,images:c.images,specifications:{},description:c.brand})) : activeSlot ? options(activeSlot) : [];
  const visible = list.filter(p => p.title.toLowerCase().includes(search.toLowerCase()));
  const specs = active==='case' && chassis ? {form_factor:chassis.form_factor,width_mm:chassis.width_mm,height_mm:chassis.height_mm,depth_mm:chassis.depth_mm,max_gpu_length_mm:chassis.max_gpu_length_mm,max_cooler_height_mm:chassis.max_cooler_height_mm} : product?.specifications ?? {};
  const specRows=Object.entries(specs).filter(([k,v])=>v!=null && !['reviewed','source_url'].includes(k));

  return <div className="ff-studio" style={{'--studio-accent':accent} as React.CSSProperties}>
    <header className="studio-header"><div><Link href="/start" className="studio-back"><ArrowLeft size={13}/> BUILD OPTIONS</Link><h1>Custom Build Studio<span>01 / YOUR MACHINE</span></h1></div><div className="studio-header-right"><span className="studio-live"><i/> FlipFlop catalogue</span><button onClick={share} disabled={!playbook} title="Copy build link"><Share2 size={16}/><span>Share build</span></button><Link href="/cart">View cart <ArrowUpRight size={15}/></Link></div></header>
    <div className="studio-layout">
      <section className="studio-stage" ref={stage} aria-label="PC showroom">
        <div className="studio-stage-top"><div className="studio-eyebrow"><span/> ENGINEERED FOR YOUR NEXT LEVEL</div><div className="studio-stage-title"><h2>Your vision.<br/><em>Every detail.</em></h2><p>Explore it. Make it yours.</p></div><div className="studio-edition">FF<span>STUDIO / 3D</span></div></div>
        {!error && sceneParts.length>0 ? <Scene parts={sceneParts} active={active} onSelect={pick} mode={mode} open={open} accent={accent} rotating={rotating} resetKey={resetKey} reducedMotion={reducedMotion}/> : <div className="studio-loading">{loading ? <><LoaderCircle className="studio-spin"/><span>Connecting to your catalogue</span></> : <><Package size={38}/><span>{error || 'Choose components to start your build.'}</span><button onClick={()=>setRefresh(n=>n+1)}>Retry catalogue</button></>}</div>}
        <div className="studio-view-tools" role="group" aria-label="3D view mode">{([{value:'assembled',label:'Assembled',Icon:Box},{value:'exploded',label:'Exploded',Icon:Expand},{value:'xray',label:'X-ray',Icon:Eye}] as const).map(({value,label,Icon})=><button key={value} aria-pressed={mode===value} className={mode===value?'active':''} onClick={()=>setMode(value)}><Icon size={15}/>{label}</button>)}</div>
        <div className="studio-stage-bottom"><div className="studio-swatch-box"><span>LIGHT SIGNATURE</span><div>{accents.map((c,i)=><button key={c} style={{background:c}} aria-label={['Ember lighting','Ice lighting','Violet lighting','Mint lighting','Pearl lighting'][i]} aria-pressed={accent===c} onClick={()=>setAccent(c)}>{accent===c&&<Check size={12} color="#111"/>}</button>)}</div><small>Preview lighting</small></div><div className="studio-stage-actions"><button onClick={()=>setOpen(v=>!v)} aria-pressed={open} title="Open or close illustrative side panel"><Layers3 size={17}/><span>{open?'Close panel':'Open panel'}</span></button><button onClick={()=>setRotating(v=>!v)} aria-label={rotating?'Pause idle rotation':'Enable idle rotation'} aria-pressed={rotating}>{rotating?<Pause size={17}/>:<Play size={17}/>}</button><button onClick={()=>{setActive('case');setResetKey(n=>n+1);}} aria-label="Reset camera"><RotateCcw size={17}/></button><button onClick={()=>{if(document.fullscreenElement) void document.exitFullscreen();else void stage.current?.requestFullscreen().catch(()=>setNotice('Fullscreen is unavailable on this device.'));}} aria-label="Fullscreen viewer"><Maximize2 size={17}/></button></div></div>
        <div className="studio-stage-caption"><span>DRAG TO ORBIT <b>·</b> PINCH TO ZOOM <b>·</b> SELECT TO INSPECT</span><span>{exactCount>0?`${exactCount} registered product assets`:'Illustrative geometry'} <CircleHelp size={12}/></span></div>
      </section>
      <aside className="studio-builder" aria-label="Build configuration">
        <div className="studio-builder-top"><div className="studio-eyebrow">THE FOUNDATION</div><label htmlFor="studio-playbook" className="sr-only">Curated build</label><select id="studio-playbook" value={playbook} onChange={e=>{setPlaybook(Number(e.target.value));setChoosing(false);setActive('case');}} disabled={loading}>{playbooks.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><p>A curated starting point. Your finishing touch.</p></div>
        <div className="studio-tabs" role="tablist" aria-label="Build information">{(['parts','details','checks'] as const).map(t=><button role="tab" aria-selected={tab===t} aria-controls={'studio-panel-'+t} id={'studio-tab-'+t} key={t} onClick={()=>setTab(t)}>{t==='parts'?'Components':t==='details'?'Inspect':'Compatibility'}{t==='checks'&&issues.length>0&&<span>{issues.length}</span>}</button>)}</div>
        <div className="studio-panel" role="tabpanel" id={'studio-panel-'+tab} aria-labelledby={'studio-tab-'+tab}>
          {tab==='parts' && (choosing ? <div className="studio-picker"><button className="studio-text-button" onClick={()=>setChoosing(false)}><ArrowLeft size={14}/> All components</button><h3>Choose {labels[active]?.toLowerCase() || active}</h3><label className="studio-search"><Search size={16}/><input aria-label="Search components" placeholder="Search the catalogue" value={search} onChange={e=>setSearch(e.target.value)}/></label><p className="studio-subtle">{visible.length} catalogue options · other selections stay in place</p><div className="studio-options">{visible.map(p=>{const isSelected=active==='case'?config.caseId===p.id:activeSlot&&config.selections[activeSlot.slot_id]===p.id;const verdict=fresh?evaluation?.verdicts.find(v=>v.slot_id===activeSlot?.slot_id)?.variants.find(v=>v.variant_id===p.id):null;return <button key={p.id} className={'studio-option'+(isSelected?' selected':'')} onClick={()=>{commit(active==='case'?{...config,caseId:p.id}:activeSlot?changePart(config,activeSlot.slot_id,p.id):config);setChoosing(false);setNotice(labels[active]+' updated. Checking your build…');}}><ProductImage src={p.images?.[0]} alt=""/><span><strong>{cleanName(p.title)}</strong><small>{money(p.display_price)}</small>{verdict?.is_compatible===false&&<em>{verdict.reason || 'Incompatible with this build'}</em>}</span>{isSelected?<Check size={16}/>:<ChevronRight size={16}/>}</button>;})}{!visible.length&&<p>No matching products are published for this slot.</p>}</div></div> : <div className="studio-components">{['case',...slots.map(s=>s.slot_type)].map((category,i)=>{const s=slots.find(s=>s.slot_type===category);const p=s?selected(s,config):null;const name=category==='case'?chassis?.name:p?.title;const amount=category==='case'?chassis?.rrp_gbp:p?.display_price;return <div className={'studio-component'+(active===category?' selected':'')} key={category}><span className="studio-number">{String(i+1).padStart(2,'0')}</span><button className="studio-component-main" onClick={()=>pick(category)}><small>{labels[category] || category}</small><strong>{name?cleanName(name):'Select a component'}</strong><span>{amount!==undefined?money(amount):'Required'}</span></button><button className="studio-swap" aria-label={'Replace '+(labels[category]||category)} onClick={()=>replace(category)}><SlidersHorizontal size={15}/></button></div>;})}<div className="studio-build-actions"><button onClick={undo} disabled={!history.length}><Undo2 size={14}/> Undo</button><button onClick={()=>commit(defaults(slots,cases))} disabled={!slots.length}><RotateCcw size={14}/> Reset build</button><button onClick={download} disabled={!slots.length} aria-label="Export build"><Download size={14}/></button></div></div>)}
          {tab==='details'&&<div className="studio-details"><div className="studio-eyebrow">{labels[active] || active} / INSPECT</div><ProductImage large src={active==='case'?chassis?.images?.[0]:product?.images?.[0]} alt={title||'No component selected'}/><h3>{title||'Nothing selected yet'}</h3><div className="studio-detail-price">{price!==undefined?money(price):'—'}<small>Catalogue component price</small></div><div className="studio-detail-actions"><button className="studio-primary" onClick={()=>replace(active)}>Replace <SlidersHorizontal size={14}/></button><button onClick={remove} disabled={!title}><Trash2 size={14}/> Remove</button></div><p>{product?.description || (active==='case'&&chassis ? `${chassis.brand} ${chassis.form_factor} chassis. Select a different case to update your build and fit checks.` : 'Additional product description has not yet been supplied in the catalogue.')}</p><h4>Technical specifications</h4>{specRows.length ? <dl>{specRows.map(([k,v])=><div key={k}><dt>{k.replaceAll('_',' ')}</dt><dd>{typeof v==='object'?JSON.stringify(v):String(v)}</dd></div>)}</dl> : <p className="studio-subtle">Verified dimensions and technical specifications are awaiting catalogue enrichment.</p>}<h4>Compatibility</h4>{!fresh?<p>Checking this configuration…</p>:evaluation?.checks.filter(c=>c.affected.includes(active)).map(c=><p className={'studio-detail-check '+c.severity} key={c.code}>{c.severity==='pass'?<Check size={14}/>:<CircleHelp size={14}/>} {c.message}</p>)}<p className="studio-disclosure">{assetError?'Product asset service unavailable. ':''}Illustrative models show component layout, not an exact product replica. Physical fit is validated from reviewed specifications, never from this preview.</p></div>}
          {tab==='checks'&&<div className="studio-checks"><ShieldCheck size={29}/><h3>{!fresh?'Checking your build':failures.length?'A few things to resolve':pending.length?'Engineering review needed':'Your build checks out'}</h3><p>{!fresh?'Retrieving catalogue availability, price and fit checks.':pending.length?'Some exact measurements are missing. Explore freely; checkout unlocks when all required checks are verified.':'Every change is checked against the current configuration.'}</p>{checkError&&<div className="studio-error">{checkError}<button onClick={()=>setRefresh(n=>n+1)}>Retry checks</button></div>}{fresh&&evaluation?.checks.map(c=><div className={'studio-check '+c.severity} key={c.code}>{c.severity==='pass'?<Check size={16}/>:c.severity==='error'?<X size={16}/>:c.severity==='unknown'?<CircleHelp size={16}/>:<AlertTriangle size={16}/>}<div><strong>{c.code.replaceAll('_',' ').toLowerCase()}</strong><p>{c.message}</p></div></div>)}</div>}
        </div>
        <div className="studio-checkout"><button className={'studio-status '+(failures.length?'error':pending.length?'unknown':'')} onClick={()=>setTab('checks')}><span>{!fresh?<LoaderCircle size={15} className={checking?'studio-spin':''}/>:failures.length?<AlertTriangle size={15}/>:pending.length?<CircleHelp size={15}/>:<ShieldCheck size={15}/>} {!fresh?(checkError?'Verification unavailable':'Checking configuration'):failures.length?`${failures.length} ${failures.length===1?'issue':'issues'} to resolve`:pending.length?`${pending.length} checks need verification`:'Compatibility verified'}</span><ChevronRight size={14}/></button><div className="studio-total"><div><small>{total!==null?'YOUR BUILD TOTAL':'SELECTED PARTS'}</small><strong>{money(total??priceEstimate)}</strong></div><span>{total!==null?'Assembly & overhead included':'Assembly quoted after validation'}</span></div><button className="studio-cart" onClick={cart} disabled={!fresh||!evaluation?.can_checkout}>Add build to cart <ArrowUpRight size={19}/></button><div className="studio-checkout-foot"><span><i/> {lastSync?'Catalogue synced '+lastSync:'Connecting'}</span><button onClick={download}>Export build</button></div></div>
      </aside>
    </div>
    <div className="studio-footer"><div><Monitor size={19}/><span><strong>See the whole picture.</strong> Inspect each part. Explore every angle.</span></div><div><ShieldCheck size={19}/><span><strong>Built on real catalogue data.</strong> Prices refresh as you configure.</span></div><div><Cpu size={19}/><span><strong>Your build, considered.</strong> Clear fit checks before checkout.</span></div></div>
    {notice&&<div className="studio-toast" role="status"><Check size={17}/>{notice}<button aria-label="Dismiss notification" onClick={()=>setNotice('')}><X size={15}/></button></div>}
  </div>;
}
