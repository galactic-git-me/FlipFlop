'use client';
import { useState } from 'react';
import { supplierArrivalEstimate, supplierDisplayLabel, type ImportEntry, type ReadinessPart } from '@/lib/commercial-readiness';

type Review={selected:boolean;fees:string;risk:string;confidence:string;stock:''|'yes'|'no'};
const blank=():Review=>({selected:false,fees:'',risk:'',confidence:'',stock:''});
function safeLink(value:string) {
  try {const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password?url.href:null;} catch{return null;}
}
function deliveryEstimate(part:ReadinessPart) {
  const estimate=supplierArrivalEstimate(part.source ?? {url:part.listing_url ?? undefined});
  return estimate ? `${estimate.days} working days · ${estimate.label}` : 'No supplier-specific arrival default available';
}

export default function CommercialEvidenceReview({parts,busy,onImport}:{parts:ReadinessPart[];busy:boolean;
  onImport:(entries:ImportEntry[])=>void}) {
  const signature=JSON.stringify(parts.map(part=>[part.part_key,part.source?.fingerprint]));
  const [state,setState]=useState<{signature:string;reviews:Record<string,Review>}>({signature:'',reviews:{}});
  const reviews=state.signature===signature?state.reviews:{};
  const change=(key:string,value:Partial<Review>)=>setState(current=>({signature,reviews:{
    ...(current.signature===signature?current.reviews:{}),[key]:{...blank(),...reviews[key],...value},
  }}));
  const isFreeSoftware=(part:ReadinessPart)=>part.source?.evidence_kind==='official_free_software';
  const selected=parts.filter(part=>part.part_key&&part.source
    &&(isFreeSoftware(part)||reviews[part.part_key]?.selected));
  const ready=selected.length>0&&selected.every(part=>isFreeSoftware(part)||(()=>{const review=reviews[part.part_key!];
    return [review.fees,review.risk,review.confidence,review.stock].every(value=>value!=='');})());
  return <section aria-label="Review collected supplier evidence" className="space-y-3">
    <h3 className="font-semibold">Review collected supplier evidence</h3>
    <p className="text-sm text-slate-400">Confirm physical supplier stock and review fees, risk and confidence before importing. Official free software downloads are verified separately and carry no physical stock or postage.</p>
    <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-slate-700 text-slate-400">
      {['Import','Reviewed product','Collector evidence','Fees (£)','Risk (£)','Confidence (0–1)','Stock'].map(title=><th key={title} className="p-2">{title}</th>)}
    </tr></thead><tbody>{parts.map((part,index)=>{
      const source=part.source,key=part.part_key??`missing:${index}`,review=reviews[key]??blank(),url=source?safeLink(source.url):null,freeSoftware=isFreeSoftware(part);
      return <tr key={`${part.role}:${part.slot_id??part.case_id??index}`} className="border-b border-slate-800 align-top">
        <td className="p-2"><input type="checkbox" aria-label={`Import ${part.role}`} checked={freeSoftware||review.selected} disabled={busy||!source||!part.part_key||freeSoftware} onChange={event=>change(key,{selected:event.target.checked})}/></td>
        <td className="min-w-48 p-2"><strong>{part.role}</strong><div>{part.title}</div><div className="text-xs text-slate-500">{part.part_key??'Mapping missing'}</div></td>
        <td className="min-w-56 p-2">{source?<><div>{supplierDisplayLabel(source)} · {source.condition} · £{source.item_gbp}{freeSoftware?' licence cost · no postage':` + ${source.postage_verified?`£${source.delivery_gbp}`:'£0.00 (cost fallback)'} postage`}</div>
          <div className="text-xs text-slate-400">{new Date(source.observed_at).toLocaleString()} · {source.fresh?'Current':'Stale'} · {source.active_listing?'Active listing':'Inactive listing'}</div>
          <div className="text-xs text-slate-400">{freeSoftware?'Official download availability; not physical stock':deliveryEstimate(part)}</div>
          {url&&<a href={url} target="_blank" rel="noreferrer" className="text-cyan-300 underline">Open source listing</a>}</>:<span className="text-amber-300">No exact collector observation linked</span>}</td>
        {(['fees','risk','confidence'] as const).map(field=><td key={field} className="p-2"><input aria-label={`${part.role} ${field}`} type="number" min="0" max={field==='confidence'?1:undefined} step="0.01"
          className="w-24 rounded border border-slate-700 bg-slate-950 p-2" value={freeSoftware?(field==='confidence'?'1':'0'):review[field]} disabled={busy||!source||freeSoftware} onChange={event=>change(key,{[field]:event.target.value})}/></td>)}
        <td className="p-2">{freeSoftware?<span className="text-xs text-emerald-300">Official download verified; no physical stock</span>:<select aria-label={`${part.role} stock review`} value={review.stock} disabled={busy||!source} className="rounded border border-slate-700 bg-slate-950 p-2" onChange={event=>change(key,{stock:event.target.value as Review['stock']})}>
          <option value="">Review stock</option><option value="no">Not confirmed</option><option value="yes" disabled={!source?.fresh||!source.active_listing}>Confirmed available</option>
        </select>}</td>
      </tr>;
    })}</tbody></table></div>
    <button type="button" disabled={busy||!ready} className="rounded bg-cyan-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-40" onClick={()=>onImport(selected.map(part=>{
      const review=reviews[part.part_key!];return {part_key:part.part_key!,observation_id:part.source!.observation_id,
        source_fingerprint:part.source!.fingerprint,fees_gbp:isFreeSoftware(part)?'0':review.fees,
        risk_gbp:isFreeSoftware(part)?'0':review.risk,
        supplier_confidence:isFreeSoftware(part)?'1':review.confidence,
        stock_confirmed:isFreeSoftware(part)||review.stock==='yes'};
    }))}>Import reviewed observations ({selected.length})</button>
  </section>;
}
