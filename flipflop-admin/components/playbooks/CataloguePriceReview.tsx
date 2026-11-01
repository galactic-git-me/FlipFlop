'use client';
import Link from 'next/link';
import type { ReadinessPart } from '@/lib/commercial-readiness';

function money(value:string|null|undefined) {return value==null?'Not recorded':new Intl.NumberFormat('en-GB',{style:'currency',currency:'GBP'}).format(Number(value));}
function sourceURL(value:string|null|undefined) {try {const url=new URL(value??'');return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?url.href:null;}catch{return null;}}
export default function CataloguePriceReview({parts,total,blockers=[]}:{parts:ReadinessPart[];total?:string|null;blockers?:string[]}) {
  return <section aria-label="Prices from catalogue listings" className="space-y-3">
    <h3 className="text-lg font-semibold">1. Check the parts and their listing prices</h3>
    <p className="text-sm text-slate-400">These amounts come from the selected catalogue listings. You do not type component prices here. Supplier postage is separate from delivery of the completed PC to your customer.</p>
    <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-slate-700 text-slate-400">{['Part','Selected catalogue product','Listing price','Supplier postage','Last collected'].map(label=><th key={label} className="p-3">{label}</th>)}</tr></thead><tbody>{parts.map((part,index)=>{
      const url=sourceURL(part.listing_url??part.source?.url);
      const capturedPostage=part.source?.postage_verified===true;
      const postage=part.supplier_postage_gbp??(capturedPostage?part.source?.delivery_gbp:'0.00');
      return <tr key={`${part.role}:${part.slot_id??part.case_id??index}`} className="border-b border-slate-800"><th scope="row" className="p-3 uppercase">{part.role}</th><td className="max-w-lg p-3"><strong>{part.title}</strong>{!part.part_key&&<p className="mt-1 text-amber-300">Product selection or case link needed</p>}{url&&<a href={url} target="_blank" rel="noreferrer" className="mt-1 block text-cyan-300 underline">View supplier listing</a>}</td><td className="p-3">{money(part.listed_item_gbp??part.source?.item_gbp)}</td><td className="p-3">{capturedPostage?money(postage):<span title="Postage was not captured; £0.00 is used for component costing.">£0.00 (cost fallback)</span>}</td><td className="p-3 text-slate-400">{part.price_observed_at?new Date(part.price_observed_at).toLocaleString('en-GB'):'Not collected'}</td></tr>;
    })}</tbody></table></div>
    <p className="text-sm"><strong>Parts and supplier postage: {total?money(total):'Not yet complete'}</strong>{!total&&<span className="ml-2 text-slate-400">A full total appears when every selected listing has an item price. Missing buying postage is costed at £0.00; customer delivery is priced separately.</span>}</p>
    {!!blockers.length&&<div className="rounded border border-amber-800 bg-amber-950/20 p-3"><p className="font-semibold">Before there is a price to approve</p><ul className="mt-2 list-inside list-disc text-sm text-amber-200">{blockers.map(blocker=><li key={blocker}>{blocker}</li>)}</ul></div>}
    <Link href="/pc-builder" className="inline-block text-sm text-cyan-300 underline">Choose or change products in the curated catalogue →</Link>
  </section>;
}
