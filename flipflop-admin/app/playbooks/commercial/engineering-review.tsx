'use client';

import {useCallback,useEffect,useState} from 'react';
import {api} from '@/lib/api';
import type {MotherboardEngineeringSuggestion,ProductEngineeringSuggestion} from '@/lib/playbook-proposals';

function engineeringValue(value:ProductEngineeringSuggestion['suggested_specs'][string]){
  if(value==null)return 'Not recorded';
  if(Array.isArray(value))return value.join(', ');
  if(typeof value==='object')return Object.entries(value).map(([name,count])=>`${name}: ${count}`).join(', ');
  return String(value);
}

function SourceChanges({item,checked,onChange}:{item:ProductEngineeringSuggestion;checked:boolean;onChange:(checked:boolean)=>void}){
  if(item.conflicted_fields?.length)return <p role="alert" className="mt-3 text-sm text-amber-300">The current source gives contradictory values for {item.conflicted_fields.join(', ')}. These facts cannot be approved until the source conflict is resolved.</p>;
  const changes=Object.entries(item.reviewed_value_changes||{});
  if(!changes.length)return null;
  return <div className="mt-3 space-y-2 rounded border border-amber-700 p-3 text-sm">
    <p>The new capture differs from the previous review. Fit verification is blocked until these changes are reviewed.</p>
    <dl>{changes.map(([key,value])=><div key={key}><dt className="inline font-medium">{key.replaceAll('_',' ')}: </dt><dd className="inline">previously {engineeringValue(value.reviewed)}; captured {engineeringValue(value.captured)}</dd></div>)}</dl>
    <label className="flex items-start gap-2"><input type="checkbox" checked={checked} onChange={event=>onChange(event.target.checked)}/><span>I reviewed these differences and approve replacing the previous values.</span></label>
  </div>;
}

export function EngineeringReview({onApproved,listingIds,boardTitles}:{onApproved:()=>Promise<void>;listingIds?:number[];boardTitles?:string[]}){
  const [items,setItems]=useState<MotherboardEngineeringSuggestion[]>([]);
  const [productItems,setProductItems]=useState<ProductEngineeringSuggestion[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const [notice,setNotice]=useState<string|null>(null);
  const [replacementChecks,setReplacementChecks]=useState<Record<number,boolean>>({});
  const reviewReadyCount=productItems.filter(item=>item.status==='review_ready').length;
  const sourceResearchCount=productItems.filter(item=>item.status==='needs_source_facts').length;
  const captureNeededCount=productItems.filter(item=>item.status==='needs_product_capture').length;
  const listingKey=listingIds?.slice().sort((a,b)=>a-b).join(',');
  const boardKey=boardTitles?.join('|');
  const load=useCallback(async()=>{try{const [result,products]=await Promise.all([api.commercialReadiness.engineeringSuggestions(),api.commercialReadiness.productEngineeringSuggestions()]);const ids=listingKey===undefined?null:new Set(listingKey.split(',').filter(Boolean).map(Number));const titles=boardKey===undefined?null:boardKey.split('|').filter(Boolean).map(value=>value.toLowerCase().replace(/[^a-z0-9]/g,''));setItems(titles?result.items.filter(item=>titles.some(title=>title.includes(item.canonical_model.toLowerCase().replace(/[^a-z0-9]/g,'')))):result.items);setProductItems(ids?products.items.filter(item=>ids.has(item.listing_id)):products.items);setReplacementChecks({});}catch(reason){setError(reason instanceof Error?reason.message:'Could not load compatibility research');}},[listingKey,boardKey]);
  useEffect(()=>{void load();},[load]);
  const approve=async(item:MotherboardEngineeringSuggestion)=>{setBusy(true);setError(null);setNotice(null);try{await api.commercialReadiness.approveEngineeringSuggestion(item.id);await load();await onApproved();setNotice(`${item.canonical_model} reference reviewed. Proposals were recalculated from captured facts; no build was published.`);}catch(reason){setError(reason instanceof Error?reason.message:'Could not approve compatibility reference');}finally{setBusy(false);}};
  const approveProduct=async(item:ProductEngineeringSuggestion)=>{setBusy(true);setError(null);setNotice(null);try{const result=await (replacementChecks[item.listing_id]?api.commercialReadiness.approveProductEngineeringSuggestion(item,true):api.commercialReadiness.approveProductEngineeringSuggestion(item));await load();await onApproved();setNotice(`${result.role} source facts reviewed for ${item.source_title}. Proposals were recalculated from captured facts; nothing was published.`);}catch(reason){setError(reason instanceof Error?reason.message:'Could not approve source-backed specifications');}finally{setBusy(false);}};
  return <section aria-label="Compatibility research review" className="rounded border border-slate-700 p-4 lg:col-span-2">
    <div><h2 className="font-semibold">Compatibility evidence review</h2><p className="mt-1 max-w-3xl text-sm text-slate-400">The scheduled Playbook refresh captures exact catalogue and official manufacturer facts automatically. You only review source-backed suggestions here. AI identification and unsupported measurements stay unverified; approving evidence updates compatibility checks but never publishes a build.</p></div>
    {productItems.length>0&&<p className="mt-3 text-sm text-slate-300">{reviewReadyCount} products have source facts ready for your review · {sourceResearchCount} need manufacturer facts · {captureNeededCount} need a fresh product-page capture.</p>}
    {error&&<p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}{notice&&<p role="status" className="mt-3 text-sm text-emerald-300">{notice}</p>}
    <div className="mt-4 space-y-3">{productItems.map(item=><article key={`product:${item.listing_id}`} className="rounded border border-cyan-900 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs uppercase text-slate-500">{item.role} · exact catalogue product</p><h3 className="font-medium">{item.source_title}</h3><a className="text-xs text-cyan-300" href={item.source_url} target="_blank" rel="noopener noreferrer">Open exact product page</a><span className="ml-3 text-xs text-slate-500">{item.captured_at?`Captured ${new Date(item.captured_at).toLocaleString('en-GB')}`:'No current product-page capture'}</span></div>
      <button onClick={()=>void approveProduct(item)} disabled={busy||item.status!=='review_ready'||Boolean(item.conflicted_fields?.length)||(Object.keys(item.reviewed_value_changes||{}).length>0&&!replacementChecks[item.listing_id])} className="rounded border border-emerald-500/50 px-3 py-1.5 text-xs text-emerald-200 disabled:opacity-40">Review these source facts</button></div>
      {item.status==='needs_product_capture'&&<p className="mt-3 text-sm text-amber-200">Capture the current product page before these fit facts can be reviewed.</p>}
      {item.status==='needs_source_facts'&&<p className="mt-3 text-sm text-amber-200">The exact page was captured but exposed no usable fit facts. Research the manufacturer specifications before approval.</p>}
      {item.missing_fields.length>0&&<p className="mt-3 text-xs text-slate-400">Still needed for compatibility checks: {item.missing_fields.map(value=>value.replaceAll('_',' ')).join(', ')}.</p>}
      {Object.keys(item.suggested_specs).length>0?<dl className="mt-3 grid gap-2 text-xs text-slate-300 sm:grid-cols-3">{Object.entries(item.suggested_specs).map(([key,value])=><div key={key}><dt className="text-slate-500">{key.replaceAll('_',' ')}</dt><dd>{engineeringValue(value)}</dd></div>)}</dl>:<p className="mt-3 text-sm text-slate-500">No facts suggested. Nothing can be approved from this capture.</p>}
      <SourceChanges item={item} checked={replacementChecks[item.listing_id]===true} onChange={checked=>setReplacementChecks(current=>({...current,[item.listing_id]:checked}))}/>
      <details className="mt-3 text-xs"><summary>Show captured source fields</summary>{(['retailer','amazon_catalog'] as const).map(source=>{const fields=Object.entries(item.properties[source]||{});return <div key={source} className="mt-2"><h4 className="font-medium text-slate-400">{source==='retailer'?'Exact product page':'Amazon catalogue attributes'}</h4>{fields.length?<dl className="mt-1 grid gap-1 sm:grid-cols-2">{fields.map(([name,value])=><div key={name}><dt className="inline text-slate-500">{name}: </dt><dd className="inline">{String(value)}</dd></div>)}</dl>:<p className="text-slate-500">No technical properties exposed.</p>}</div>;})}</details>
      <p className="mt-3 text-xs text-slate-500">Suggestions use explicitly labelled properties or literal facts in this exact catalogue title. Review the source before approval. Unsupported values remain unknown.</p></article>)}{productItems.length===0&&<p className="text-sm text-slate-500">No component products are linked to the current proposals yet. Refresh catalogue sourcing to discover them.</p>}</div>
    <div className="mt-4 space-y-3">
      {items.map((item) => {
        const listingTitleEvidence = item.listing_title_facts_captured === true;
        const reviewable = item.manufacturer_facts_captured === true || listingTitleEvidence;
        return (
          <article key={item.id} className="rounded border border-slate-800 p-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="font-medium">{item.canonical_model}</h3>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                  {item.manufacturer_source_url ? (
                    <a className="text-cyan-300" href={item.manufacturer_source_url} target="_blank" rel="noopener noreferrer">
                      Official manufacturer spec: {item.manufacturer_source_title || "open source"}
                    </a>
                  ) : listingTitleEvidence ? (
                    <span className="text-amber-200">Facts captured literally from the linked catalogue listing title</span>
                  ) : (
                    <span className="text-amber-200">Official manufacturer page not captured yet</span>
                  )}
                  <a className="text-slate-400 underline" href={item.source_url} target="_blank" rel="noopener noreferrer">Open linked catalogue listing</a>
                </div>
                {item.manufacturer_source_captured_at && (
                  <p className="mt-1 text-xs text-slate-500">Manufacturer specs captured {new Date(item.manufacturer_source_captured_at).toLocaleString("en-GB")}</p>
                )}
              </div>
              <button onClick={() => void approve(item)} disabled={busy || !reviewable} className="rounded border border-emerald-500/50 px-3 py-1.5 text-xs text-emerald-200 disabled:opacity-40">
                Approve reviewed specs
              </button>
            </div>
            <dl className="mt-3 grid gap-2 text-xs text-slate-300 sm:grid-cols-3">
              {[["Socket", item.socket], ["Chipset", item.chipset], ["Memory", `${item.ram_type || "Unknown"} · ${item.ram_slots ?? "Unknown"} slots · ${item.max_ram_gb == null ? "capacity unknown" : `maximum ${item.max_ram_gb} GB`} `], ["Form factor", item.form_factor], ["M.2 slots", item.m2_slots], ["SATA ports", item.sata_ports]].map(([label, value]) => (
                <div key={label}><dt className="text-slate-500">{label}</dt><dd>{value || "Unknown"}</dd></div>
              ))}
            </dl>
            <p className="mt-3 text-xs text-slate-500">
              {listingTitleEvidence
                ? "Only literal facts in the linked catalogue title are included; unknown measurements stay unknown. Review the exact listing before approval. Approval updates compatibility evidence for this board and does not publish a build."
                : "Captured values remain proposals. Check the official source page above; approval makes this exact board reference usable for compatibility checks but does not publish a build."}
            </p>
          </article>
        );
      })}
      {items.length === 0 && <p className="text-sm text-slate-500">No unreviewed Playbook motherboard suggestions. Scheduled research will add exact-source candidates.</p>}
    </div>
  </section>;
}
