'use client';
import { useEffect, useState, type FormEvent } from 'react';
import { API_BASE_URL } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

type Details = { tradingName: string; legalName: string; address: string; phone: string; email: string; vatNumber: string | null; weeeRegistration: string | null; weeeTakebackRoute: 'unconfirmed'|'direct'|'dts'; returnsAddress: string | null };
export default function BusinessDetailsSettings() {
  const [details,setDetails]=useState<Details|null>(null);
  const [error,setError]=useState('');
  const [saving,setSaving]=useState(false);
  const [saved,setSaved]=useState(false);
  useEffect(()=>{
    const controller=new AbortController();
    fetch(`${API_BASE_URL}/settings/business-details`,{credentials:'include',signal:controller.signal})
      .then(async response=>{if(!response.ok)throw new Error('Could not load public business settings.');return response.json() as Promise<Details>;})
      .then(data=>{if(!controller.signal.aborted)setDetails(data);})
      .catch(reason=>{if(!controller.signal.aborted)setError(reason.message);});
    return ()=>controller.abort();
  },[]);
  async function save(event:FormEvent) {
    event.preventDefault();setSaving(true);setError('');setSaved(false);
    try {
      const response=await fetch(`${API_BASE_URL}/settings/business-details`,{method:'PUT',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify(details)});
      if(!response.ok)throw new Error(response.status===422?'Check the public contact details and selected take-back route.':'Could not save business settings. Please try again.');
      setDetails(await response.json());setSaved(true);
    } catch(reason){setError(reason instanceof Error?reason.message:'Could not save business settings.');}
    finally{setSaving(false);}
  }
  const update=(key:keyof Details,value:string)=>{setDetails(current=>current?{...current,[key]:value}:current);setSaved(false);};
  const inputClass='mt-2 w-full rounded-lg border border-[#1e2d45] bg-[#0a1119] px-3 py-2 text-sm text-slate-100';
  return <Card><CardHeader><CardTitle>Public business details &amp; recycling</CardTitle><p className="text-sm text-slate-400">These settings appear on storefront policy pages. Enter business contact details intended for public display. The legal proprietor and trading name are separate.</p></CardHeader><CardContent>
    {error&&<p role="alert" className="mb-4 text-sm text-red-300">{error}</p>}
    {!details&&!error&&<p role="status">Loading business details…</p>}
    {details&&<form onSubmit={save}><fieldset disabled={saving} className="grid gap-5 md:grid-cols-2">
      {([['legalName','Sole trader’s full legal name'],['tradingName','Trading name'],['phone','Public business telephone'],['email','Public contact email']] as const).map(([key,label])=><label key={key} className="text-sm text-slate-300">{label}<input required type={key==='email'?'email':key==='phone'?'tel':'text'} value={details[key]} onChange={event=>update(key,event.target.value)} className={inputClass}/></label>)}
      <label className="text-sm text-slate-300">Geographic business address<textarea required rows={5} value={details.address} onChange={event=>update('address',event.target.value)} className={inputClass}/></label>
      <label className="text-sm text-slate-300">Returns address, if different<textarea rows={5} value={details.returnsAddress??''} onChange={event=>update('returnsAddress',event.target.value)} className={inputClass}/><span className="mt-2 block text-xs text-slate-400">Leave blank if the return route must be confirmed with support. This does not authorise unsolicited equipment returns.</span></label>
      <label className="text-sm text-slate-300">VAT number, if registered<input value={details.vatNumber??''} onChange={event=>update('vatNumber',event.target.value)} className={inputClass}/></label>
      <label className="text-sm text-slate-300">WEEE producer registration, if applicable<input value={details.weeeRegistration??''} onChange={event=>update('weeeRegistration',event.target.value)} className={inputClass}/></label>
      <label className="text-sm text-slate-300 md:col-span-2">Electrical-waste take-back route<select value={details.weeeTakebackRoute} onChange={event=>update('weeeTakebackRoute',event.target.value)} className={inputClass}><option value="unconfirmed">Not yet confirmed</option><option value="direct">Direct free like-for-like take-back</option><option value="dts">Distributor Takeback Scheme membership</option></select></label>
      <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 p-4 text-sm text-slate-300 md:col-span-2"><p>WEEE means waste electrical and electronic equipment. When selling household electrical equipment, you need a qualifying recycling take-back arrangement: provide an eligible route for equivalent old equipment, or join the Distributor Takeback Scheme if eligible. Take-back and producer-registration obligations are separate.</p><p className="mt-2">Select a route only after the arrangement or membership is confirmed. “Not yet confirmed” keeps the public recycling page’s warning visible.</p><a className="mt-2 inline-block text-sky-300 underline" href="https://www.gov.uk/electricalwaste-producer-supplier-responsibilities" target="_blank" rel="noreferrer">Read the official take-back guidance ↗</a></div>
      <button type="submit" className="rounded-lg bg-emerald-400 px-5 py-3 font-semibold text-black disabled:opacity-50">{saving?'Saving…':'Save public business details'}</button>
    </fieldset>{saved&&<p role="status" className="mt-4 text-sm text-emerald-300">Saved. The storefront uses these details on the next policy-page request.</p>}</form>}
  </CardContent></Card>;
}
