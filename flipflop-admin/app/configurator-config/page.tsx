"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { AlertCircle, Check, Cpu, LayoutGrid, List, Loader2, RefreshCw, Table2 } from "lucide-react";

type ViewMode = "table" | "listings" | "grid";
type Tab = "catalogue" | "inventory" | "assets" | "live";
type Item = { id: number; listing_id: number; slot_type: string; title: string; image_url?: string | null; source_price: number; price: number; proposed_price?: number | null; custom_cost_snapshot?: number | null; custom_for_builds: boolean; sale_status: string; listing_status: string; catalogue_status: string; last_seen_at?: string | null; url?: string };
type Asset = { id: number; subject_type: string; subject_id: number | null; status: string; preview_image_ref?: string | null; glb_ref?: string | null; review_decision?: string | null };
const TABS: { id: Tab; label: string }[] = [{ id: "catalogue", label: "Custom Catalogue" }, { id: "inventory", label: "Price and Inventory" }, { id: "assets", label: "3D Assets" }, { id: "live", label: "Go Live" }];
const SLOT_LABELS: Record<string, string> = { cpu: "CPU", gpu: "GPU", motherboard: "Motherboard", ram: "RAM", storage: "Storage", psu: "Power supply", cooling: "Cooling", case: "PC case", os: "Operating system" };
const REQUIRED = ["cpu", "gpu", "motherboard", "ram", "storage", "psu", "case"];

export default function CustomBuildsPage() {
  const [tab, setTab] = useState<Tab>("catalogue");
  const [view, setView] = useState<ViewMode>("grid");
  const [items, setItems] = useState<Item[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [isLive, setIsLive] = useState(false);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [catalogueResponse, assetsResponse] = await Promise.all([
        fetch("/api/custom-builds", { cache: "no-store" }),
        fetch("/api/assets-3d?subject_type=variant&custom_only=true", { cache: "no-store" }),
      ]);
      const data = await catalogueResponse.json();
      if (!catalogueResponse.ok) throw new Error(data.detail || "Could not load the custom catalogue");
      setItems(data.items ?? []); setIsLive(Boolean(data.is_live));
      if (assetsResponse.ok) setAssets(await assetsResponse.json());
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load Custom Builds"); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const toggleMembership = async (item: Item) => {
    setBusy(true); setError("");
    try {
      const r = await fetch(`/api/custom-builds/variants/${item.id}/catalogue`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ custom_for_builds: !item.custom_for_builds }) });
      const data = await r.json(); if (!r.ok) throw new Error(data.detail || "Could not update custom catalogue");
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update custom catalogue"); }
    finally { setBusy(false); }
  };
  const approvePrice = async (item: Item) => {
    setBusy(true); setError(""); setMessage("");
    try {
      const r = await fetch(`/api/custom-builds/variants/${item.id}/approve-price`, { method: "POST" });
      const data = await r.json(); if (!r.ok) throw new Error(data.detail || "Could not approve proposed price");
      setMessage(`Approved ${item.title} at £${Number(data.price).toFixed(2)}`); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not approve price"); }
    finally { setBusy(false); }
  };
  const dismissPrice = async (item: Item) => {
    setBusy(true); setError("");
    try { const r = await fetch(`/api/custom-builds/variants/${item.id}/dismiss-price`, { method: "POST" }); const data = await r.json(); if (!r.ok) throw new Error(data.detail || "Could not dismiss proposed price"); setMessage(`Dismissed price proposal for ${item.title}`); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not dismiss proposed price"); }
    finally { setBusy(false); }
  };
  const toggleLive = async () => {
    setBusy(true); setError(""); setMessage("");
    try {
      const r = await fetch("/api/custom-builds/go-live", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_live: !isLive }) });
      const data = await r.json(); if (!r.ok) throw new Error(data.detail || "Go-live checks did not pass");
      setIsLive(data.is_live); setMessage(data.is_live ? "Custom catalogue is live" : "Custom catalogue is offline"); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update custom catalogue publication"); }
    finally { setBusy(false); }
  };

  const filtered = useMemo(() => items.filter(i => `${i.title} ${i.slot_type}`.toLowerCase().includes(filter.toLowerCase())), [items, filter]);
  const customItems = items.filter(i => i.custom_for_builds);
  const proposed = customItems.filter(i => i.proposed_price != null);
  const onSale = customItems.filter(i => i.sale_status === "on_sale");
  const missingSlots = REQUIRED.filter(slot => !onSale.some(i => i.slot_type === slot));
  const assetsForCustom = assets.filter(a => customItems.some(i => i.id === a.subject_id));

  return <main className="min-h-screen bg-[#080d14] px-5 py-7 text-slate-100 md:px-8"><div className="mx-auto max-w-[1600px] space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[.22em] text-cyan-300">Build studio</p><h1 className="mt-2 text-3xl font-bold">Custom Builds</h1><p className="mt-1 text-sm text-slate-400">Manage the components and cases customers can choose from when building a PC.</p></div><button onClick={() => void load()} className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-300 hover:bg-white/5"><RefreshCw className="h-4 w-4"/>Refresh</button></header>
    {(message || error) && <div role="status" className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm ${error ? "border-rose-400/30 bg-rose-400/10 text-rose-200" : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"}`}>{error ? <AlertCircle className="h-4 w-4"/> : <Check className="h-4 w-4"/>}{error || message}</div>}
    <nav className="flex gap-1 overflow-x-auto border-b border-white/10">{TABS.map(t => <button key={t.id} onClick={() => setTab(t.id)} className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium ${tab === t.id ? "border-cyan-400 text-cyan-200" : "border-transparent text-slate-400 hover:text-white"}`}>{t.label}</button>)}</nav>

    {tab === "catalogue" && <section className="space-y-4"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">Custom Catalogue</h2><p className="text-sm text-slate-400">Select products from the catalogue that customers may choose for custom PCs.</p></div><input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Filter components…" className="w-full max-w-sm rounded-lg border border-white/10 bg-[#101924] px-3 py-2 text-sm outline-none focus:border-cyan-400"/></div>
      <div className="flex items-center justify-end gap-2">{([ ["table", Table2, "Table"], ["listings", List, "Listings"], ["grid", LayoutGrid, "Grid"] ] as const).map(([v, Icon, label]) => <button key={v} onClick={() => setView(v)} aria-pressed={view === v} className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-xs ${view === v ? "bg-cyan-400 text-slate-950" : "bg-white/5 text-slate-400"}`}><Icon className="h-3.5 w-3.5"/>{label}</button>)}</div>
      {view === "table" ? <div className="overflow-x-auto rounded-xl border border-white/10"><table className="w-full text-left text-sm"><thead className="bg-[#14202d] text-xs text-slate-400"><tr>{["Component", "Type", "Customer price", "Availability", "Custom catalogue"].map(x=><th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody>{filtered.map(i=><tr key={i.id} className="border-t border-white/5"><td className="max-w-xl px-4 py-3">{i.title}</td><td className="px-4 py-3">{SLOT_LABELS[i.slot_type] || i.slot_type}</td><td className="px-4 py-3">£{i.price.toFixed(2)}</td><td className="px-4 py-3"><Badge tone={i.sale_status === "on_sale" ? "green" : "red"}>{i.sale_status === "on_sale" ? "On sale" : "Out of stock"}</Badge></td><td className="px-4 py-3"><Toggle checked={i.custom_for_builds} onClick={() => void toggleMembership(i)}/></td></tr>)}</tbody></table></div> : <div className={view === "grid" ? "grid gap-4 sm:grid-cols-2 xl:grid-cols-4" : "space-y-3"}>{filtered.map(i=><article key={i.id} className={`overflow-hidden rounded-xl border border-white/10 bg-[#101924] ${view === "listings" ? "flex items-center gap-4 p-3" : "p-3"}`}>{i.image_url && <img src={i.image_url} alt="" className={view === "listings" ? "h-20 w-24 rounded object-contain" : "mb-3 h-36 w-full rounded bg-black/20 object-contain"}/>}<div className="min-w-0 flex-1"><p className="line-clamp-2 text-sm font-medium">{i.title}</p><p className="mt-1 text-xs text-slate-400">{SLOT_LABELS[i.slot_type] || i.slot_type} · £{i.price.toFixed(2)}</p><p className="mt-1 text-xs text-slate-500">{i.sale_status === "on_sale" ? "Available" : "Out of stock"} · last seen {i.last_seen_at ? new Date(i.last_seen_at).toLocaleDateString() : "unknown"}</p></div><Toggle checked={i.custom_for_builds} onClick={() => void toggleMembership(i)}/></article>)}</div>}
      {filtered.length === 0 && <Empty title="No catalogue matches" text="Try another search or refresh the current catalogue."/>}</section>}

    {tab === "inventory" && <section className="space-y-4"><div><h2 className="text-xl font-semibold">Price and Inventory</h2><p className="text-sm text-slate-400">Listing price changes create a reviewable custom-build price proposal. Availability automatically follows catalogue listing status.</p></div>{customItems.length === 0 ? <Empty title="Custom Catalogue is empty" text="Add components in the Custom Catalogue tab to see price and availability here."/> : <div className="overflow-x-auto rounded-xl border border-white/10"><table className="w-full text-left text-sm"><thead className="bg-[#14202d] text-xs text-slate-400"><tr>{["Component type", "Product", "Source cost", "Current price", "Proposed price", "Availability", "Approval"].map(x=><th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody>{customItems.map(i=><tr key={i.id} className="border-t border-white/5"><td className="px-4 py-3">{SLOT_LABELS[i.slot_type] || i.slot_type}</td><td className="max-w-sm px-4 py-3">{i.title}</td><td className="px-4 py-3">£{i.source_price.toFixed(2)}</td><td className="px-4 py-3">£{i.price.toFixed(2)}</td><td className="px-4 py-3">{i.proposed_price == null ? "—" : <span className="font-semibold text-amber-300">£{i.proposed_price.toFixed(2)}</span>}</td><td className="px-4 py-3"><Badge tone={i.sale_status === "on_sale" ? "green" : "red"}>{i.sale_status === "on_sale" ? "On sale" : "Out of stock"}</Badge></td><td className="px-4 py-3">{i.proposed_price == null ? <span className="text-xs text-slate-500">No change</span> : <div className="flex gap-2"><button onClick={() => void approvePrice(i)} className="rounded-md bg-amber-400 px-2.5 py-1.5 text-xs font-semibold text-slate-950">Approve £{i.proposed_price.toFixed(2)}</button><button onClick={() => void dismissPrice(i)} className="rounded-md border border-white/10 px-2 py-1.5 text-xs text-slate-300">Dismiss</button></div>}</td></tr>)}</tbody></table></div>}</section>}

    {tab === "assets" && <section className="space-y-4"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">3D Assets</h2><p className="text-sm text-slate-400">Images and models for Custom Catalogue items, with approval in the existing asset review flow.</p></div><a href="/components-3d-review?customOnly=1" className="rounded-lg border border-white/10 px-3 py-2 text-sm text-cyan-200 hover:bg-white/5">Review custom images and models</a></div>{assetsForCustom.length === 0 ? <Empty title="No custom component assets found" text="Assets for Custom Catalogue items will appear here when available."/> : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{assetsForCustom.map(a=>{const i=customItems.find(x=>x.id===a.subject_id);return <article key={a.id} className="overflow-hidden rounded-xl border border-white/10 bg-[#101924]">{a.preview_image_ref ? <img src={a.preview_image_ref} alt="Asset preview" className="h-40 w-full bg-black/20 object-contain"/> : <div className="flex h-40 items-center justify-center text-sm text-slate-600">No image preview</div>}<div className="p-3"><p className="line-clamp-2 text-sm font-medium">{i?.title || `Component ${a.subject_id}`}</p><p className="mt-1 text-xs text-slate-400">{a.status.replaceAll("_", " ")} · {a.glb_ref ? "3D model ready" : "model pending"}</p>{a.review_decision && <p className="mt-2 text-xs text-emerald-300">Decision: {a.review_decision}</p>}</div></article>})}</div>}</section>}

    {tab === "live" && <section className="space-y-4"><div><h2 className="text-xl font-semibold">Go Live</h2><p className="text-sm text-slate-400">Check catalogue coverage and pending prices before making custom components available to customers.</p></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Summary label="Custom products" value={customItems.length}/><Summary label="On sale" value={onSale.length}/><Summary label="Price approvals" value={proposed.length}/><Summary label="3D assets" value={assetsForCustom.length}/></div><div className="space-y-2 rounded-xl border border-white/10 bg-[#101924] p-4"><CheckRow ok={customItems.length > 0} label="At least one component is in the Custom Catalogue"/><CheckRow ok={missingSlots.length === 0} label={missingSlots.length ? `Available coverage: missing ${missingSlots.map(s=>SLOT_LABELS[s]).join(", ")}` : "CPU, GPU, motherboard, RAM, storage, PSU and case are available"}/><CheckRow ok={proposed.length === 0} label={proposed.length ? `${proposed.length} proposed component price${proposed.length === 1 ? "" : "s"} need approval` : "No proposed price changes awaiting approval"}/><CheckRow ok={customItems.every(i => i.sale_status === "on_sale" || i.sale_status === "out_of_stock")} label="Availability status is current for all selected products"/></div><button onClick={() => void toggleLive()} disabled={busy || (!isLive && (customItems.length === 0 || missingSlots.length > 0 || proposed.length > 0))} className="rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">{isLive ? "Take custom catalogue offline" : "Publish custom catalogue"}</button><p className="text-xs text-slate-500">Current state: {isLive ? "Live" : "Draft"}. Components are automatically removed from the public feed while unavailable and returned when the source listing is active again.</p></section>}
    {busy && <div className="fixed bottom-5 right-5 flex items-center gap-2 rounded-lg border border-white/10 bg-[#14202d] px-3 py-2 text-xs"><Loader2 className="h-4 w-4 animate-spin"/>Saving…</div>}
  </div></main>;
}

function Empty({title,text}:{title:string;text:string}) { return <div className="rounded-xl border border-dashed border-white/10 bg-white/[.02] px-6 py-12 text-center"><Cpu className="mx-auto h-8 w-8 text-slate-600"/><p className="mt-3 font-semibold text-slate-300">{title}</p><p className="mt-1 text-sm text-slate-500">{text}</p></div>; }
function Badge({children,tone}:{children:ReactNode;tone:"green"|"red"}) { return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${tone === "green" ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300" : "border-rose-400/20 bg-rose-400/10 text-rose-300"}`}>{children}</span>; }
function Toggle({checked,onClick}:{checked:boolean;onClick:()=>void}) { return <button type="button" role="switch" aria-checked={checked} onClick={onClick} className={`relative h-6 w-11 shrink-0 rounded-full transition ${checked ? "bg-cyan-400" : "bg-slate-700"}`}><span className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${checked ? "left-6" : "left-1"}`}/></button>; }
function CheckRow({ok,label}:{ok:boolean;label:string}) { return <div className={`flex items-center gap-2 text-sm ${ok ? "text-emerald-300" : "text-amber-300"}`}>{ok ? <Check className="h-4 w-4"/> : <AlertCircle className="h-4 w-4"/>}{label}</div>; }
function Summary({label,value}:{label:string;value:number}) { return <div className="rounded-xl border border-white/10 bg-[#101924] p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold">{value}</p></div>; }
