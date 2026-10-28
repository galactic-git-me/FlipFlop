"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { api } from "@/lib/api";
import { bookMoney } from "@/lib/playbook-book";
import { customerNeeds } from "@/lib/playbook-customer-needs";
import { inventoryHealth } from "@/lib/playbook-inventory-health";
import { modelHealth } from "@/lib/playbook-model-health";
import { playbookLiveStatus } from "@/lib/playbook-live-status";
import { heatmapValue, profitHeatmap } from "@/lib/playbook-profit-heatmap";
import type { HeatmapMetric } from "@/lib/playbook-profit-heatmap";
import type { BookCell, BookPage, PlaybookBook as BookData } from "@/lib/playbook-book";
import ComponentPaceOptions from "./ComponentPaceOptions";
import PlaybookOperatingRules from "./PlaybookOperatingRules";
const MediaDialog = dynamic(() => import("./PlaybookMediaDialog"), {ssr:false});
const Advanced = dynamic(() => import("./AdvancedPlaybookBook"));
type Props = {refreshKey?:number;onEdit:(id:number)=>void;renderTools?:(page:BookPage,cell:BookCell)=>ReactNode};
function humanTask(cell:BookCell) {
  const parts = cell.offer?.components.filter(part => !part.role.startsWith("os")) ?? [];
  if (parts.some(part => !part.photo_ready)) return "Photos & models";
  if (parts.some(part => !part.media_ready && part.model_generation_status === "DRAFT_CREATED")) return "View models";
  return null;
}
function live(cell:BookCell) { return cell.is_live && cell.checkout_enabled && cell.availability_status === "in_stock"; }
export default function PlaybookBook(props:Props) {
  const [book,setBook] = useState<BookData|null>(null);
  const [error,setError] = useState("");
  const [selected,setSelected] = useState<string|null>(null);
  const detailsRef=useRef<HTMLElement>(null);
  useEffect(()=>{if(selected) detailsRef.current?.scrollIntoView({block:"start",behavior:"smooth"});},[selected]);
  const [media,setMedia] = useState<BookCell|null>(null);
  const [advanced,setAdvanced] = useState(false);
  const [status,setStatus] = useState<Awaited<ReturnType<typeof api.commercialReadiness.automation>>|null>(null);
  const [needsMe,setNeedsMe] = useState(false);
  const [heatmapMetric,setHeatmapMetric] = useState<HeatmapMetric>("profit");
  const [pricingError,setPricingError] = useState("");
  const bookRequestInFlight=useRef(false);
  const load=useCallback(async () => {
    if(bookRequestInFlight.current) return;
    bookRequestInFlight.current=true;
    try {
      const next = await api.commercialReadiness.book(); setBook(next); setError("");
      if (next.cells.some(cell => cell.pricing_guidance?.market_advice.status === "pending")) {
        void api.commercialReadiness.refreshPricingGuidance().then(() => setPricingError("")).catch(() => setPricingError("Could not queue local market advice. Cost estimates remain available; refresh to retry."));
      }
    }
    catch(reason) { setError(reason instanceof Error ? reason.message : "Could not load the Playbook"); }
    finally { bookRequestInFlight.current=false; }
  },[]);
  useEffect(() => {
    void load();
    void api.commercialReadiness.automation().then(setStatus).catch(() => setStatus(null));
    const timer=window.setInterval(() => {
      void load(); void api.commercialReadiness.automation().then(setStatus).catch(() => setStatus(null));
    },30000);
    return () => window.clearInterval(timer);
  },[load,props.refreshKey]);
  const cells=book?.cells ?? [];
  const profits=cells.map(cell=>heatmapValue(cell,heatmapMetric)).filter((value):value is number=>value!==null);
  const minProfit=profits.length ? Math.min(...profits) : 0;
  const maxProfit=profits.length ? Math.max(...profits) : 0;
  const heatmapLabel=heatmapMetric === "profit" ? "Estimated profit per build (£)" : heatmapMetric === "price" ? "Recommended price (£)" : "Recorded matching complete-PC sold listings";
  const heatmapNumber=(value:number)=>heatmapMetric === "sales" ? new Intl.NumberFormat("en-GB",{maximumFractionDigits:1}).format(value) : bookMoney(value);
  const current=cells.find(cell => cell.cell_id===selected);
  const customers=[...new Set(cells.map(cell=>cell.customer_type))];
  const tiers=["Budget","Mid-range","High-end"];
  return <section aria-label="The Playbook" className="space-y-4 text-slate-100">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-2xl font-semibold">The Playbook</h2><p className="text-sm text-slate-400">Top-selling components, linked supplier costs and suggested prices for each segment.</p></div><button onClick={() => void load()} className="rounded border border-white/20 px-3 py-2 text-sm">Refresh</button></header>
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-white/10 p-3 text-sm">
      <span>{cells.filter(cell=>cell.pricing_guidance?.estimated_price_gbp).length}/{cells.length} priced suggestions · {cells.filter(live).length} live builds</span><Link href="/catalogue/3d-assets" className="text-cyan-300 underline">Approve catalogue photos in one grid</Link>
      <label className="flex items-center gap-2"><input type="checkbox" checked={needsMe} onChange={event=>setNeedsMe(event.target.checked)} />Show builds with media work</label>
      <span className="text-slate-400">{status ? status.enabled ? "Scheduled refresh on" : "Scheduled refresh off in this environment" : "Scheduler status unavailable"} · {cells.filter(cell=>cell.mvp_autonomy).length} cells enabled for automatic publication</span>
    </div>
    {status?.scheduled_latest?.status === "failed" && <p role="alert" className="text-amber-200">Automatic refresh failed: {status.scheduled_latest.error}. Existing evidence still controls customer availability.</p>}
    {pricingError && <p role="alert" className="text-amber-200">{pricingError}</p>}
    {error && <p role="alert" className="text-rose-200">{error}{book ? " Showing the last loaded snapshot." : ""}</p>}
    {!book && !error && <p role="status">Loading Playbook…</p>}
    {book && !cells.length && <p>No Playbook builds are configured.</p>}
    <div role="group" aria-label="Heatmap based on" className="flex flex-wrap items-center gap-2 text-xs"><span className="text-slate-400">Heatmap based on</span>{([["profit","Estimated profit"],["price","Recommended price"],["sales","Sales volume"]] as const).map(([metric,label])=><button key={metric} type="button" aria-pressed={heatmapMetric===metric} onClick={()=>setHeatmapMetric(metric)} className={`rounded border px-3 py-2 focus-visible:outline-2 focus-visible:outline-cyan-300 ${heatmapMetric===metric ? "border-cyan-400 bg-cyan-400/15 text-cyan-200" : "border-white/20 text-slate-300"}`}>{label}</button>)}</div>
    {!!profits.length && <div aria-label="Heatmap legend" className="max-w-xl space-y-1 text-xs text-slate-300"><p>{heatmapLabel} · {heatmapMetric === "profit" ? "faint green = lowest, strongest green = highest" : "red = lowest, amber = middle, green = highest"}</p><div aria-hidden="true" className={`h-2 rounded ${heatmapMetric === "profit" ? "" : "bg-gradient-to-r from-red-400 via-amber-400 to-emerald-400"}`} style={heatmapMetric === "profit" ? {background:"linear-gradient(to right, rgba(52,211,153,0.06), rgba(52,211,153,0.4))"} : undefined} /><div className="flex justify-between tabular-nums"><span>{heatmapNumber(minProfit)}</span><span>{heatmapNumber((minProfit+maxProfit)/2)}</span><span>{heatmapNumber(maxProfit)}</span></div><p className="text-slate-400">Relative to all Playbook builds · missing values are unshaded</p></div>}
    {heatmapMetric === "sales" && <p role="status" className="text-xs text-slate-400">{profits.length ? "Counts of distinct matching complete-PC sold listings captured in the last 90 days; not total market sales or component sales." : "No matching complete-PC sales volume is recorded for these builds. Cells remain unshaded."}</p>}
    {!!cells.length && <div className="overflow-x-auto rounded-lg border border-white/10"><table aria-label="Playbook build matrix" className="w-full min-w-[850px] table-fixed text-left">
      <thead className="bg-[#14202d]"><tr><th className="w-36 p-3">Customer type</th>{tiers.map(tier=><th scope="col" key={tier} className="p-3 text-cyan-200">{tier}</th>)}</tr></thead>
      <tbody>{customers.filter(customer=>!needsMe || cells.some(cell=>cell.customer_type===customer && humanTask(cell))).map(customer=><tr key={customer} className="border-t border-white/10"><th scope="row" className="p-3 align-top">{customer}</th>{tiers.map(tier=>{
        const cell=cells.find(item=>item.customer_type===customer && item.budget_tier===tier);
        if (!cell || (needsMe && !humanTask(cell))) return <td key={tier} className="border-l border-white/10 p-3 text-slate-500">—</td>;
        const isLive=live(cell); const offer=isLive ? cell.approved_offer : cell.offer;
        const standard=offer?.delivery_products.standard; const task=humanTask(cell);
        const guidance=cell.pricing_guidance;
        const estimateOnly=!isLive && standard?.recommended_price_gbp == null;
        const price=isLive ? cell.approved_price_gbp : guidance?.estimated_price_gbp ?? standard?.recommended_price_gbp;
        const priceLabel=isLive ? "Customer price" : price != null ? "Suggested price" : "Known parts cost";
        const profit=heatmapValue(cell,"profit");
        const heatValue=heatmapValue(cell,heatmapMetric);
        const inventory=inventoryHealth(cell,offer);
        const models=modelHealth(offer,inventory.total);
        const liveStatus=playbookLiveStatus(cell);
        return <td key={tier} style={profitHeatmap(heatValue,minProfit,maxProfit,heatmapMetric) ?? undefined} className="space-y-3 border-l border-white/10 p-3 align-top">
          <div><p className="font-semibold">{cell.name}</p><p className="mt-1 text-xs text-slate-300" title={liveStatus.reason} aria-label={`Build status: ${liveStatus.label}`}><span aria-hidden="true" className={`mr-2 inline-block h-2.5 w-2.5 rounded-full ${liveStatus.colour === "green" ? "bg-emerald-400" : liveStatus.colour === "amber" ? "bg-amber-400" : "bg-red-400"}`} />{liveStatus.label}</p></div>
          <details className="text-xs text-slate-300"><summary className="cursor-pointer" aria-label={`Inventory health: ${inventory.label}`}><span aria-hidden="true" className={`mr-2 inline-block h-2.5 w-2.5 rounded-full ${inventory.status === "green" ? "bg-emerald-400" : inventory.status === "amber" ? "bg-amber-400" : "bg-red-400"}`} />{inventory.label} · {inventory.available}/{inventory.total}</summary><p className="mt-2 text-slate-400">Supplier hardware stock recorded within 24 hours; not stock held in our workshop. Quantities must be confirmed when ordering.</p>{!!inventory.issues.length && <ul className="mt-1 space-y-1">{inventory.issues.map(issue=><li key={issue}>{issue}</li>)}</ul>}</details>
          <details className="text-xs text-slate-300"><summary className="cursor-pointer" aria-label={`3D model status: ${models.label}`}><span aria-hidden="true" className={`mr-2 inline-block h-2.5 w-2.5 rounded-full ${models.status === "green" ? "bg-emerald-400" : models.status === "amber" ? "bg-amber-400" : "bg-red-400"}`} />{models.label} · {models.ready}/{models.total}</summary><p className="mt-2 text-slate-400">Approved component models ready for this build.</p>{!!models.issues.length && <ul className="mt-1 space-y-1">{models.issues.map(issue=><li key={issue}>{issue}</li>)}</ul>}</details>
          <div className="text-xs text-slate-300"><p className="mb-1 font-medium text-cyan-200">Customer needs</p><p>{customerNeeds(cell)}</p></div>
          <ul className="space-y-1 text-xs text-slate-400">{offer?.components.filter(part=>["cpu","gpu","ram","storage"].includes(part.role)).map(part=><li key={part.role} className="truncate" title={part.title}><span className="uppercase text-cyan-300">{part.role}</span> · {(part.quantity ?? 1)>1 ? `${part.quantity} × ` : ""}{part.role === "gpu" ? part.title : part.performance_evidence?.model ?? part.title}</li>)}{!offer?.components.length && <li>The system is finding matching parts.</li>}</ul>
          <dl className="space-y-1 text-sm"><div className="flex justify-between gap-2" title="Selected component costs including recorded buying postage; unknown buying postage defaults to £0. Excludes build operating costs."><dt>Component cost</dt><dd className="tabular-nums">{bookMoney(guidance?.known_parts_subtotal_gbp)}</dd></div><div className="flex justify-between gap-2"><dt>{priceLabel}</dt><dd>{bookMoney(price ?? guidance?.known_parts_subtotal_gbp)}</dd></div><div className="flex justify-between gap-2"><dt>Estimated profit</dt><dd className="font-semibold tabular-nums">{bookMoney(profit)}</dd></div>{isLive && <div className="flex justify-between gap-2"><dt>Standard delivery</dt><dd>{standard?.delivery_working_days != null ? `${standard.delivery_working_days} working days` : "Not yet quoted"}</dd></div>}</dl>
          {estimateOnly && !guidance?.estimated_price_gbp && <p className="text-xs text-amber-200">Missing parts or item prices are listed in build details.</p>}
          {heatmapMetric === "sales" && <p className="text-xs text-slate-300">Recorded matching PC sales: <strong>{heatValue === null ? "Not recorded" : heatmapNumber(heatValue)}</strong></p>}
          <div className="flex flex-wrap gap-2"><button type="button" onClick={()=>setMedia(cell)} className="rounded border border-cyan-400/40 px-3 py-2 text-xs text-cyan-200">{task ?? "Photos & 3D models"}</button><button type="button" onClick={()=>setSelected(selected===cell.cell_id ? null : cell.cell_id)} className="rounded border border-white/15 px-3 py-2 text-xs">Build details</button></div>
        </td>;
      })}</tr>)}</tbody>
    </table></div>}
    {current && <section ref={detailsRef} aria-label="Selected build details" className="space-y-3 rounded-lg border border-white/15 p-4"><div className="flex justify-between"><h3 className="font-semibold">{current.name}</h3><button onClick={()=>setSelected(null)} className="text-sm underline">Close details</button></div><ul className="space-y-1 text-sm">{current.offer?.components.map(part=><li key={part.role}><span className="uppercase text-cyan-300">{part.role}</span> · <a href={part.suggested_supplier_offer?.url ?? part.source_url} target="_blank" rel="noopener noreferrer" className="text-cyan-200 underline">{(part.quantity ?? 1)>1 ? `${part.quantity} × ` : ""}{part.title}</a> · {bookMoney(part.suggested_supplier_offer?.item_gbp ?? part.listing_price_gbp)}<span className="text-slate-400"> · supplier postage {part.suggested_supplier_offer ? part.suggested_supplier_offer.delivery_gbp == null ? "£0.00 (default)" : bookMoney(part.suggested_supplier_offer.delivery_gbp) : part.supplier_postage_gbp == null ? "£0.00 (default)" : bookMoney(part.supplier_postage_gbp)}</span></li>)}</ul>{current.offer && <ComponentPaceOptions offer={current.offer} />}{current.pricing_guidance && <details className="rounded border border-white/10 p-3"><summary className="cursor-pointer text-sm text-cyan-200">Suggested price and stored sold evidence</summary><p className="mt-2 text-sm">{current.pricing_guidance.market_advice.summary}</p><p className="mt-2 text-xs text-amber-200">{current.pricing_guidance.profit_check?.basis ?? "Profit cannot be verified until the complete build is costed."}</p>{current.pricing_guidance.cost_allowances_gbp && <dl className="mt-2 grid grid-cols-2 gap-1 text-xs text-slate-400">{Object.entries(current.pricing_guidance.cost_allowances_gbp).map(([key,value])=><div key={key}><dt>{key.replaceAll("_"," ")} allowance</dt><dd>{bookMoney(value)}</dd></div>)}</dl>}{current.pricing_guidance.market_advice.model && <p className="text-xs text-slate-500">Local model: {current.pricing_guidance.market_advice.model}</p>}<ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-400">{[...current.pricing_guidance.gaps,...current.pricing_guidance.assumptions].map((gap,index)=><li key={index}>{gap}</li>)}</ul>{current.pricing_guidance.market_advice.comparisons?.map(row=><a key={row.id} href={row.url} target="_blank" rel="noopener noreferrer" className="mt-2 block text-xs text-cyan-200 underline">{row.title} · {bookMoney(row.total_gbp)} · {row.kind}</a>)}</details>}{current.offer?.compatibility_review && <details className="rounded border border-white/10 p-3"><summary className="cursor-pointer text-sm text-cyan-200">Automated LLM compatibility review · {current.offer.compatibility_review.status.replaceAll("_", " ")}</summary><p className="mt-2 text-xs text-slate-300">{current.offer.compatibility_review.summary}</p><ul className="mt-2 space-y-1 text-xs">{current.offer.compatibility_review.checks.map((row,index)=><li key={`${row.pair}-${index}`}><strong>{row.pair.replaceAll("_", " ↔ ")}</strong> · {row.verdict.replaceAll("_", " ")} · {row.explanation}{row.evidence.length ? <span className="text-slate-500"> · Evidence: {row.evidence.join(", ")}</span> : null}</li>)}</ul><p className="mt-2 text-xs text-amber-200">LLM assessment is advisory. Source-backed physical checks below determine whether this build can be published.</p>{current.offer.compatibility_review.model && <p className="mt-1 text-xs text-slate-500">{current.offer.compatibility_review.provider} · {current.offer.compatibility_review.model}</p>}</details>}{current.offer?.planning_compatibility && <details className="rounded border border-white/10 p-3"><summary className="cursor-pointer text-sm text-cyan-200">Compatibility for this planned build</summary><ul className="mt-2 space-y-1 text-xs">{current.offer.planning_compatibility.checks.map(row=><li key={row.check}>{row.status === "pass" ? "✓" : "Needs correction"} {row.check}: {row.detail}</li>)}</ul><p className="mt-3 text-xs text-slate-400">Assembly checks</p><ul className="mt-1 list-disc pl-5 text-xs text-slate-400">{current.offer.planning_compatibility.assembly_notes.map(note=><li key={note}>{note}</li>)}</ul></details>}{current.automation_reason && <p className="text-sm text-amber-200">{current.automation_reason}</p>}{Boolean(current.offer?.blockers.length) && <details><summary className="cursor-pointer text-sm text-amber-200">Checks before publishing</summary><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-400">{current.offer?.blockers.map(reason=><li key={reason}>{reason}</li>)}</ul></details>}<p className="text-xs text-slate-500">Last assessment: {current.proposal_observed_at ? new Date(current.proposal_observed_at).toLocaleString("en-GB") : "Not yet recorded"}</p></section>}
    <details onToggle={event=>setAdvanced(event.currentTarget.open)} className="rounded border border-white/10 p-3"><summary className="cursor-pointer text-sm text-slate-500">Advanced diagnostics</summary>{advanced && <><PlaybookOperatingRules onUpdated={()=>void load()} /><Advanced {...props} /></>}</details>
    {media && <MediaDialog cell={media} onClose={()=>{setMedia(null);void load();}} />}
  </section>;
}
