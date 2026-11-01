'use client';
import { CommercialDraft, costFields, modes } from '@/lib/commercial-readiness';

function NumberField({label,value,kind='money',onChange,disabled}:{label:string;value:string|number|null;
  kind?:'money'|'rate'|'integer';onChange:(value:string|number|null)=>void;disabled:boolean}) {
  const displayed=value===null?'':kind==='rate'?Number((Number(value)*100).toFixed(4)):value;
  return <label className="grid gap-1 text-xs text-slate-400">{label}
    <input aria-label={label} type="number" min="0" step={kind==='integer'?'1':'0.01'} value={displayed} disabled={disabled}
      className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-100"
      onChange={event=>onChange(event.target.value===''?null:kind==='integer'?Number(event.target.value):
        kind==='rate'?String(Number((Number(event.target.value)/100).toFixed(6))):event.target.value)} />
  </label>;
}

export default function CommercialPolicyEditor({draft,onChange,disabled}:{draft:CommercialDraft;
  onChange:(draft:CommercialDraft)=>void;disabled:boolean}) {
  const update=(path:string[],value:unknown)=>{
    const next=structuredClone(draft);
    let node=next as unknown as Record<string,unknown>;
    for(const key of path.slice(0,-1)) node=node[key] as Record<string,unknown>;
    node[path[path.length-1]]=value;
    onChange(next);
  };
  const textClass='w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-100';
  const localDate=draft.market.observed_at?new Date(draft.market.observed_at):null;
  const dateValue=localDate&&Number.isFinite(localDate.getTime())?
    new Date(localDate.getTime()-localDate.getTimezoneOffset()*60000).toISOString().slice(0,16):'';
  return <div className="space-y-5">
    <section aria-label="Fees and reserve rules" className="space-y-3">
      <h3 className="font-semibold">Fees and reserves</h3>
      <p className="text-sm text-slate-400">Enter reviewed values. Blank means unknown; use zero only where you have confirmed there is no cost.</p>
      <p className="text-sm text-slate-400">Pilot defaults: not VAT registered; owner labour £0 for now; packaging £10 and separate insurance £15 per build. Each value is editable below. Card processing allowance: 3.15% + £0.20, based on published Stripe GBP card rates; review custom pricing, currency conversion or other payment methods separately. Courier costs must cover home collection, tracking and signature.</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {([['vat_rate','Output VAT (%)'],['payment_rate','Payment fee (%)'],['warranty_rate','Warranty reserve (%)'],
          ['returns_rate','Returns reserve (%)'],['market_tolerance_fraction','Market price tolerance (%)']] as const).map(([key,label])=>
          <NumberField key={key} label={label} value={draft[key]} kind="rate" disabled={disabled} onChange={value=>update([key],value)}/>)}
      </div>
    </section>
    <section aria-label="Delivery mode rules" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Profit, delivery and operating costs</h3>
        <button type="button" disabled={disabled} className="text-sm text-cyan-300 underline" onClick={()=>{
          const next=structuredClone(draft);
          next.modes.fast_track.costs={...draft.modes.standard.costs};
          next.modes.flexible.costs={...draft.modes.standard.costs};
          onChange(next);
        }}>Copy Standard costs to other modes</button>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">{modes.map(mode=><fieldset key={mode.id} className="space-y-3 rounded-lg border border-slate-700 p-3">
        <legend className="px-2 font-semibold">{mode.label}</legend>{mode.id === 'flexible' && <p className="text-xs text-slate-400">No promised delivery date. Workshop and courier times are internal planning inputs.</p>}
        <NumberField label={`${mode.label} minimum contribution (£)`} value={draft.modes[mode.id].minimum_contribution_gbp} disabled={disabled} onChange={value=>update(['modes',mode.id,'minimum_contribution_gbp'],value)}/>
        <NumberField label={`${mode.label} minimum margin (%)`} value={draft.modes[mode.id].minimum_margin_fraction} kind="rate" disabled={disabled} onChange={value=>update(['modes',mode.id,'minimum_margin_fraction'],value)}/>
        <NumberField label={`${mode.label} premium (£)`} value={draft.modes[mode.id].premium_gbp} disabled={disabled} onChange={value=>update(['modes',mode.id,'premium_gbp'],value)}/>
        {([['workshop_working_days','Queue, build and QA days'],['courier_working_days','Courier days'],['maximum_delivery_working_days','Maximum delivery days']] as const).filter(([key])=>mode.id !== 'flexible' || key !== 'maximum_delivery_working_days').map(([key,label])=>
          <NumberField key={key} label={`${mode.label} ${label}`} value={draft.modes[mode.id][key]} kind="integer" disabled={disabled} onChange={value=>update(['modes',mode.id,key],value)}/>)}
        <div className="border-t border-slate-700 pt-3 text-xs text-slate-400">Operating costs (£), excluding supplier parts</div>
        {costFields.map(([key,label])=><NumberField key={key} label={`${mode.label} ${label} (£)`} value={draft.modes[mode.id].costs[key]} disabled={disabled} onChange={value=>update(['modes',mode.id,'costs',key],value)}/>)}
      </fieldset>)}</div>
    </section>
    <details className="space-y-3 rounded-lg border border-slate-700 p-3"><summary className="cursor-pointer font-semibold">Optional comparable-PC price check</summary>
      <p className="text-sm text-slate-400">Component prices come from catalogue listings. Leave this optional check blank to calculate from those costs and your margin rules. If you choose to add a market ceiling, use comparable complete systems of the same condition.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <NumberField label="Sold median (£)" value={draft.market.sold_median_gbp} disabled={disabled} onChange={value=>update(['market','sold_median_gbp'],value)}/>
        <NumberField label="Comparable sold sample size" value={draft.market.sold_sample_size} kind="integer" disabled={disabled} onChange={value=>update(['market','sold_sample_size'],value)}/>
        <label className="grid gap-1 text-xs text-slate-400">Evidence observed (local time)<input className={textClass} type="datetime-local" value={dateValue} disabled={disabled} onChange={event=>update(['market','observed_at'],event.target.value?new Date(event.target.value).toISOString():null)}/></label>
        {(['evidence_source','evidence_ref'] as const).map(key=><label key={key} className="grid gap-1 text-xs text-slate-400">{key==='evidence_source'?'Sold evidence source':'Sold evidence reference'}<input className={textClass} value={draft.market[key]??''} disabled={disabled} onChange={event=>update(['market',key],event.target.value||null)}/></label>)}
      </div>
    </details>
  </div>;
}
