"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, Check, ChevronLeft, ChevronRight, Cpu, ExternalLink, ImageIcon, LayoutGrid, List, Loader2, Plus, RefreshCw, Save, Sparkles, Table2, X } from "lucide-react";
import type { ReactNode } from "react";

type ViewMode = "table" | "listings" | "grid";
type Tab = "segments" | "catalogue" | "playbook" | "inventory" | "assets" | "live";
type Component = { id: number; slot_type: string; title: string; price: number; status: string; last_seen_at?: string; image_url?: string | null; url?: string; curated_for_builds: boolean };
type BestsellerMatch = { category: string; rank: number; asin: string; cpk: string; title: string; url: string | null; image_url: string | null; price: number | null; marketplace_listing_id: string; marketplace_source: string; marketplace_title: string; marketplace_url: string | null; marketplace_image_url: string | null; marketplace_image_is_reference: boolean; marketplace_price: number; marketplace_condition: string | null; marketplace_seen_at: string; review_status: "pending" | "approved" | "rejected" };
type DraftBuild = { playbook_id: string; customer_type: string; budget_tier: string; name: string; status: string; est_component_cost_gbp: number; indicative_sell_gbp: number; note: string; core_components: { category: string; sku_name: string; cost_gbp: number }[]; upsells: { category: string; from_sku: string; to_sku: string; delta_cost_gbp: number; delta_sell_gbp: number | null }[] };
type Segment = { id: number; customer_type: string; budget_level: string; budget_min: number | null; budget_max: number | null; components: Record<string, number>; bestseller_components: Record<string, { category: string; cpk: string }>; component_details: Record<string, Component | null>; component_cost: number; selling_price?: number; proposed_selling_price?: number; availability_status: string; is_live: boolean; regeneration_status: string };
type Asset = { id: number; subject_type: string; subject_id: number | null; status: string; preview_image_ref?: string | null; glb_ref?: string | null; review_decision?: string | null; category?: string | null };
const TABS: { id: Tab; label: string }[] = [
  { id: "segments", label: "Customer Types + Budget Levels" }, { id: "catalogue", label: "Curated Catalogue" },
  { id: "playbook", label: "The Playbook" }, { id: "inventory", label: "Price and Inventory" },
  { id: "assets", label: "3D Assets" }, { id: "live", label: "Go Live" },
];
const SLOT_LABELS: Record<string, string> = { cpu: "CPU", gpu: "GPU", motherboard: "Motherboard", ram: "RAM", storage: "Storage", psu: "Power supply", cooling: "Cooling", case: "Case", os: "Operating system" };
const CATEGORY_LABELS: Record<string, string> = { cpu: "CPUs", gpu: "Graphics cards", motherboard: "Motherboards", ram: "Memory", storage: "Storage", psu: "Power supplies", cooler: "CPU coolers", case: "Cases", os: "Operating systems" };
const categoryForSlot = (slot: string) => slot === "cooling" ? "cooler" : slot;
const BUDGET_LEVELS = ["Budget", "Mid-range", "High-end"] as const;
const formatBudgetRange = (segment: Segment) => segment.budget_min == null ? "Range needed" : segment.budget_max == null ? `£${segment.budget_min.toLocaleString()}+` : `£${segment.budget_min.toLocaleString()}–£${(segment.budget_max - 1).toLocaleString()}`;

export default function CuratedBuildsPage() {
  const [tab, setTab] = useState<Tab>("segments");
  const [view, setView] = useState<ViewMode>("grid");
  const [segments, setSegments] = useState<Segment[]>([]);
  const [components, setComponents] = useState<Component[]>([]);
  const [bestsellerMatches, setBestsellerMatches] = useState<BestsellerMatch[]>([]);
  const [draftBuilds, setDraftBuilds] = useState<DraftBuild[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const [reviewFilter, setReviewFilter] = useState<"all" | BestsellerMatch["review_status"]>("pending");
  const [reviewMatchIndex, setReviewMatchIndex] = useState<number | null>(null);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const selected = segments.find(s => s.id === selectedId) ?? segments[0];

  const load = useCallback(async () => {
    setError("");
    try {
      const [data, assetResponse, bestsellerResponse, draftResponse] = await Promise.all([fetch("/api/curated-builds", { cache: "no-store" }), fetch("/api/assets-3d?subject_type=variant", { cache: "no-store" }), fetch("/api/curated-builds/bestseller-catalogue", { cache: "no-store" }), fetch("/api/curated-builds/draft-playbook", { cache: "no-store" })]);
      if (!data.ok) throw new Error((await data.json()).detail || "Could not load curated builds");
      const payload = await data.json();
      setSegments(payload.segments ?? []); setComponents(payload.components ?? []);
      if (bestsellerResponse.ok) {
        const matchPayload = await bestsellerResponse.json();
        setBestsellerMatches(matchPayload.items ?? []);
      }
      if (draftResponse.ok) setDraftBuilds((await draftResponse.json()).playbooks ?? []);
      if (assetResponse.ok) setAssets(await assetResponse.json());
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load curated builds"); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (!selectedId && segments.length) setSelectedId(segments[0].id); }, [selectedId, segments]);

  const saveSegment = async (segment: Partial<Segment> & { customer_type: string; budget_level: string }) => {
    setBusy(true); setMessage(""); setError("");
    try {
      const response = await fetch("/api/curated-builds/segments", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(segment) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not save segment");
      setMessage("Playbook segment saved"); await load(); setSelectedId(data.id);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save segment"); } finally { setBusy(false); }
  };
  const toggleCurated = async (item: Component) => {
    setBusy(true);
    try { const r = await fetch(`/api/curated-builds/variants/${item.id}/curated`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ curated_for_builds: !item.curated_for_builds }) }); if (!r.ok) throw new Error((await r.json()).detail || "Update failed"); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not update catalogue item"); } finally { setBusy(false); }
  };
  const reviewBestseller = async (item: BestsellerMatch, status: BestsellerMatch["review_status"]) => {
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/curated-builds/bestseller-catalogue/review", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: item.category, cpk: item.cpk, status }),
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Could not save review");
      setBestsellerMatches(old => old.map(candidate => candidate.category === item.category && candidate.cpk === item.cpk ? { ...candidate, review_status: status } : candidate));
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save review"); }
    finally { setBusy(false); }
  };
  const assignBestseller = async (segment: Segment, slot: string, cpk: string) => {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/curated-builds/segments/${segment.id}/bestseller-component`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slot, cpk: cpk || null }),
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Could not assign bestseller product");
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not assign bestseller product"); }
    finally { setBusy(false); }
  };
  const updateChoice = async (slot: string, value: string) => {
    if (!selected) return;
    const choices = { ...selected.components };
    if (value) choices[slot] = Number(value); else delete choices[slot];
    await saveSegment({ ...selected, components: choices });
  };
  const generate = async (segment: Segment) => {
    setBusy(true); setError(""); setMessage("");
    try { const r = await fetch(`/api/curated-builds/segments/${segment.id}/generate`, { method: "POST" }); const d = await r.json(); if (!r.ok) throw new Error(d.detail || "Generation request failed"); setMessage(`Hermes workflow queued · ${d.request_id}`); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not queue generation"); } finally { setBusy(false); }
  };
  const applyPrice = async (segment: Segment) => { const r = await fetch(`/api/curated-builds/segments/${segment.id}/apply-price`, { method: "POST" }); if (!r.ok) { setError((await r.json()).detail || "Could not apply proposed price"); return; } await load(); };
  const publish = async (segment: Segment) => { setBusy(true); setError(""); try { const r = await fetch(`/api/curated-builds/segments/${segment.id}/publish`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_live: !segment.is_live }) }); const data = await r.json(); if (!r.ok) throw new Error(data.detail || "Could not update publication"); setMessage(data.is_live ? "Segment published to the curated builds feed" : "Segment taken offline"); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Could not update publication"); } finally { setBusy(false); } };
  const catalogueCategories = [...new Set([...bestsellerMatches.map(c => c.category), ...components.map(c => categoryForSlot(c.slot_type))])].sort();
  const filteredComponents = useMemo(() => components.filter(c =>
    (categoryFilter === "all" || categoryForSlot(c.slot_type) === categoryFilter) &&
    `${c.title} ${c.slot_type}`.toLowerCase().includes(filter.toLowerCase())
  ), [components, filter, categoryFilter]);
  const filteredBestsellers = useMemo(() => bestsellerMatches.filter(c =>
    (reviewFilter === "all" || c.review_status === reviewFilter) &&
    (categoryFilter === "all" || c.category === categoryFilter) &&
    `${c.title} ${c.category} ${c.asin} ${c.marketplace_title}`.toLowerCase().includes(filter.toLowerCase())
  ), [bestsellerMatches, filter, reviewFilter, categoryFilter]);
  const reviewCandidates = useMemo(() => bestsellerMatches.filter(c =>
    (categoryFilter === "all" || c.category === categoryFilter) &&
    `${c.title} ${c.category} ${c.asin} ${c.marketplace_title}`.toLowerCase().includes(filter.toLowerCase())
  ), [bestsellerMatches, filter, categoryFilter]);
  const reviewMatch = reviewMatchIndex == null ? null : reviewCandidates[reviewMatchIndex] ?? null;
  useEffect(() => {
    if (reviewMatchIndex == null) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setReviewMatchIndex(null);
      if (event.key === "ArrowLeft") setReviewMatchIndex(index => index == null ? null : Math.max(0, index - 1));
      if (event.key === "ArrowRight") setReviewMatchIndex(index => index == null ? null : Math.min(reviewCandidates.length - 1, index + 1));
    };
    window.addEventListener("keydown", onKeyDown);
    return () => { document.body.style.overflow = previousOverflow; window.removeEventListener("keydown", onKeyDown); };
  }, [reviewMatchIndex, reviewCandidates.length]);
  const selectedAssets = assets.filter(a => a.subject_id != null && components.some(c => c.id === a.subject_id));
  const totalChecks = segments.length;
  const customerTypes = [...new Set(segments.map(s => s.customer_type))].sort();

  return <main className="min-h-screen bg-[#080d14] px-5 py-7 text-slate-100 md:px-8">
    <div className="mx-auto max-w-[1600px] space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[.22em] text-cyan-300">Build studio</p><h1 className="mt-2 text-3xl font-bold">Curated Builds</h1><p className="mt-1 text-sm text-slate-400">Manage the approved component catalogue, build playbooks, pricing, assets and launch readiness.</p></div><button onClick={() => void load()} className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-300 hover:bg-white/5"><RefreshCw className="h-4 w-4"/>Refresh</button></header>
      {(message || error) && <div role="status" className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm ${error ? "border-rose-400/30 bg-rose-400/10 text-rose-200" : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"}`}>{error ? <AlertCircle className="h-4 w-4"/> : <Check className="h-4 w-4"/>}{error || message}</div>}
      <nav className="flex gap-1 overflow-x-auto border-b border-white/10">{TABS.map(item => <button key={item.id} onClick={() => setTab(item.id)} className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition ${tab === item.id ? "border-cyan-400 text-cyan-200" : "border-transparent text-slate-400 hover:text-white"}`}>{item.label}</button>)}</nav>

      {tab === "segments" && <section className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">Customer types and budget levels</h2><p className="text-sm text-slate-400">Create one playbook build for each audience and budget combination.</p></div><button onClick={() => { const name = window.prompt("Customer type (e.g. Gaming)"); if (!name?.trim()) return; const budget = window.prompt("Budget level (e.g. Entry, Mid-range, Premium)"); if (budget?.trim()) void saveSegment({ customer_type: name.trim(), budget_level: budget.trim(), components: {} }); }} className="inline-flex items-center gap-2 rounded-lg bg-cyan-500 px-3 py-2 text-sm font-semibold text-slate-950"><Plus className="h-4 w-4"/>Add segment</button></div>
        {segments.length === 0 ? <Empty title="No customer segments yet" text="Add your first customer type and budget level to start the playbook."/> : <div className="space-y-5"><div className="hidden grid-cols-3 gap-3 pl-40 text-sm font-semibold text-slate-300 lg:grid">{BUDGET_LEVELS.map(level => <div key={level}>{level}</div>)}</div>{customerTypes.map(type => <div key={type} className="grid gap-3 lg:grid-cols-[148px_repeat(3,minmax(0,1fr))]"><h3 className="self-center text-sm font-semibold text-cyan-200">{type}</h3>{BUDGET_LEVELS.map(level => { const s = segments.find(item => item.customer_type === type && item.budget_level === level); if (!s) return <div key={level} className="rounded-xl border border-dashed border-white/10 p-4 text-xs text-slate-500">No {level} build</div>; const draft = draftBuilds.find(b => b.customer_type === type && b.budget_tier === level); const outOfRange = draft && s.budget_min != null && (draft.indicative_sell_gbp < s.budget_min || (s.budget_max != null && draft.indicative_sell_gbp >= s.budget_max)); return <button key={s.id} onClick={() => { setSelectedId(s.id); setTab("playbook"); }} className="rounded-xl border border-white/10 bg-[#101924] p-4 text-left hover:border-cyan-400/40"><div className="flex items-start justify-between gap-2"><div><p className="text-xs uppercase tracking-wide text-slate-400 lg:hidden">{level}</p><p className="font-semibold">{draft?.name ?? level}</p></div><Badge tone={s.is_live ? "green" : "amber"}>{s.is_live ? "Live" : "Draft"}</Badge></div><p className="mt-2 text-sm font-medium text-cyan-200">{formatBudgetRange(s)}</p><p className="mt-3 text-xs text-slate-400">Draft indicative sell: {draft ? `£${draft.indicative_sell_gbp.toLocaleString()}` : "pending"}</p>{outOfRange && <p className="mt-1 text-xs text-amber-300">Draft price falls outside this range; reprice or revise build</p>}<p className="mt-2 text-xs text-slate-500">{Object.keys(s.bestseller_components ?? {}).length} reviewed products linked</p></button>; })}</div>)}</div>}</section>}

      {tab === "catalogue" && <section className="space-y-4"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">Curated Catalogue</h2><p className="text-sm text-slate-400">Choose which catalogue products can be assigned to curated build segments.</p></div><input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Filter components…" className="w-full max-w-sm rounded-lg border border-white/10 bg-[#101924] px-3 py-2 text-sm outline-none focus:border-cyan-400"/></div><div className="flex items-center justify-end gap-2">{([ ["table", Table2, "Table"], ["listings", List, "Listings"], ["grid", LayoutGrid, "Grid"] ] as const).map(([v, Icon, label]) => <button key={v} onClick={() => setView(v)} aria-pressed={view === v} className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-xs ${view === v ? "bg-cyan-400 text-slate-950" : "bg-white/5 text-slate-400"}`}><Icon className="h-3.5 w-3.5"/>{label}</button>)}</div>
        <div role="tablist" aria-label="Product categories" className="flex gap-2 overflow-x-auto border-b border-white/10 pb-2">
          {(["all", ...catalogueCategories]).map(category => <button key={category} type="button" role="tab" aria-selected={categoryFilter === category} onClick={() => setCategoryFilter(category)} className={`shrink-0 rounded-lg px-3 py-2 text-sm font-medium ${categoryFilter === category ? "bg-cyan-400 text-slate-950" : "bg-white/5 text-slate-300 hover:bg-white/10"}`}>{category === "all" ? "All products" : CATEGORY_LABELS[category] ?? category}</button>)}
        </div>
        <div className="rounded-xl border border-white/10 bg-[#101924] p-4"><h3 className="font-semibold">Amazon bestseller matches</h3><p className="mt-1 text-xs text-slate-400">{bestsellerMatches.length} ranked products matched by canonical product key to marketplace listings. {matchesAwaitingImages > 0 && `${matchesAwaitingImages} more awaiting a marketplace picture. `}Prices and availability need review before approval.</p><div className="mt-3 flex flex-wrap gap-2"><select value={reviewFilter} onChange={e => setReviewFilter(e.target.value as typeof reviewFilter)} aria-label="Review status" className="rounded border border-white/10 bg-[#0b1119] px-3 py-2 text-xs"><option value="pending">Pending review</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="all">All statuses</option></select><span className="self-center text-xs text-slate-400">{filteredBestsellers.length} shown</span></div></div>
        {filteredBestsellers.length === 0 ? <Empty title="No matched bestseller products" text="No ranked Amazon products have a marketplace product match for this filter."/> : <div className="overflow-x-auto rounded-xl border border-white/10"><table className="w-full text-left text-xs"><thead className="bg-[#14202d] text-slate-400"><tr>{["Amazon rank", "Picture", "Bestseller product", "Amazon price", "Marketplace match", "Marketplace price", "Review"].map(h => <th key={h} className="px-3 py-3">{h}</th>)}</tr></thead><tbody>{filteredBestsellers.map(c => <tr key={`${c.category}-${c.cpk}`} className="border-t border-white/5 align-top"><td className="whitespace-nowrap px-3 py-3">{c.category} #{c.rank}</td><td className="px-3 py-3"><ProductThumbnail src={c.image_url} alt={c.title} /></td><td className="max-w-sm px-3 py-3"><a className="font-medium text-cyan-200 hover:underline" href={c.url ?? undefined} target="_blank" rel="noreferrer">{c.title}</a><p className="mt-1 text-slate-500">ASIN {c.asin}</p></td><td className="px-3 py-3">{c.price == null ? "—" : `£${c.price.toFixed(2)}`}</td><td className="max-w-sm px-3 py-3"><a className="text-cyan-200 hover:underline" href={c.marketplace_url ?? undefined} target="_blank" rel="noreferrer">{c.marketplace_title}</a><p className="mt-1 text-slate-500">{c.marketplace_source} · {c.marketplace_condition ?? "condition unknown"}</p></td><td className="whitespace-nowrap px-3 py-3">£{c.marketplace_price.toFixed(2)}</td><td className="min-w-48 px-3 py-3"><div className="flex items-center gap-2"><Badge tone={c.review_status === "approved" ? "green" : c.review_status === "rejected" ? "red" : "amber"}>{c.review_status}</Badge><button onClick={() => setReviewMatchIndex(reviewCandidates.findIndex(item => item.category === c.category && item.cpk === c.cpk))} className="rounded-md border border-cyan-400/30 px-2.5 py-1.5 font-semibold text-cyan-200 hover:bg-cyan-400/10">Compare images</button></div></td></tr>)}</tbody></table></div>}
        {components.length > 0 && <><h3 className="font-semibold">Approved catalogue variants</h3>{view === "table" ? <div className="overflow-x-auto rounded-xl border border-white/10"><table className="w-full text-left text-sm"><thead className="bg-[#14202d] text-xs text-slate-400"><tr>{["Product", "Type", "Price", "Availability", "Curated"].map(h => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead><tbody>{filteredComponents.map(c => <tr key={c.id} className="border-t border-white/5"><td className="max-w-xl px-4 py-3"><div className="flex items-center gap-3"><ProductThumbnail src={c.image_url} alt={c.title} /><span>{c.title}</span></div></td><td className="px-4 py-3">{SLOT_LABELS[c.slot_type] || c.slot_type}</td><td className="px-4 py-3">£{c.price?.toFixed(2)}</td><td className="px-4 py-3"><Badge tone={c.status === "active" ? "green" : "red"}>{c.status}</Badge></td><td className="px-4 py-3"><Toggle checked={c.curated_for_builds} onClick={() => void toggleCurated(c)}/></td></tr>)}</tbody></table></div> : <div className={view === "grid" ? "grid gap-4 sm:grid-cols-2 xl:grid-cols-4" : "space-y-3"}>{filteredComponents.map(c => <article key={c.id} className={`overflow-hidden rounded-xl border border-white/10 bg-[#101924] ${view === "listings" ? "flex items-center gap-4 p-3" : "p-3"}`}><div className={view === "grid" ? "mb-3" : ""}><ProductThumbnail src={c.image_url} alt={c.title} large={view === "grid"}/></div><div className="min-w-0 flex-1"><p className="line-clamp-2 text-sm font-medium">{c.title}</p><p className="mt-1 text-xs text-slate-400">{SLOT_LABELS[c.slot_type] || c.slot_type} · £{c.price?.toFixed(2)}</p><p className="mt-1 text-xs text-slate-500">Last seen {c.last_seen_at ? new Date(c.last_seen_at).toLocaleDateString() : "unknown"}</p></div><Toggle checked={c.curated_for_builds} onClick={() => void toggleCurated(c)}/></article>)}</div>}</>}</section>}

      {tab === "playbook" && selected && <DraftOverview build={draftBuilds.find(b => b.customer_type === selected.customer_type && b.budget_tier === selected.budget_level)} />}
      {tab === "playbook" && selected && <ReviewedBestsellerChoices segment={selected} matches={bestsellerMatches} busy={busy} onAssign={assignBestseller} />}
      {tab === "playbook" && <section className="space-y-5"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">The Playbook</h2><p className="text-sm text-slate-400">Review the draft specification above, then link approved catalogue products below.</p></div>{selected && <button disabled={busy} onClick={() => void generate(selected)} className="inline-flex items-center gap-2 rounded-lg bg-violet-500 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Sparkles className="h-4 w-4"/>{selected.regeneration_status === "queued" ? "Generation queued" : "Generate Build with Hermes"}</button>}</div>
        {segments.length === 0 ? <Empty title="Create a segment first" text="Customer type and budget segments appear here for component assignment."/> : <div className="grid gap-5 lg:grid-cols-[280px_1fr]"><aside className="space-y-2">{segments.map(s => <button key={s.id} onClick={() => setSelectedId(s.id)} className={`w-full rounded-lg border p-3 text-left ${selected?.id === s.id ? "border-cyan-400/50 bg-cyan-400/10" : "border-white/10 bg-[#101924]"}`}><span className="block font-medium">{s.customer_type}</span><span className="text-xs text-slate-400">{s.budget_level}</span></button>)}</aside>{selected && <div className="space-y-4 rounded-xl border border-white/10 bg-[#101924] p-5"><div><p className="text-lg font-semibold">{selected.customer_type} · {selected.budget_level}</p><p className="text-sm text-slate-400">Current component cost: £{selected.component_cost.toFixed(2)}</p></div><div className="grid gap-3 md:grid-cols-2">{Object.entries(SLOT_LABELS).filter(([slot]) => slot !== "os").map(([slot,label]) => <label key={slot} className="space-y-1.5 text-xs text-slate-400">{label}<select value={selected.components[slot] ?? ""} onChange={e => void updateChoice(slot,e.target.value)} className="w-full rounded-lg border border-white/10 bg-[#0b1119] px-3 py-2.5 text-sm text-white"><option value="">Choose a curated product…</option>{components.filter(c => c.curated_for_builds && c.slot_type === slot).map(c => <option key={c.id} value={c.id}>{c.title} · £{c.price.toFixed(2)}</option>)}</select></label>)}</div><div className="grid gap-3 md:grid-cols-3"><label className="text-xs text-slate-400">Minimum budget<input type="number" value={selected.budget_min ?? ""} onChange={e => setSegments(old => old.map(s => s.id === selected.id ? { ...s, budget_min: e.target.value === "" ? null : Number(e.target.value) } : s))} className="mt-1 w-full rounded border border-white/10 bg-[#0b1119] p-2 text-sm text-white"/></label><label className="text-xs text-slate-400">Maximum budget<input type="number" value={selected.budget_max ?? ""} onChange={e => setSegments(old => old.map(s => s.id === selected.id ? { ...s, budget_max: e.target.value === "" ? null : Number(e.target.value) } : s))} className="mt-1 w-full rounded border border-white/10 bg-[#0b1119] p-2 text-sm text-white"/></label><label className="text-xs text-slate-400">Selling price<input type="number" value={selected.selling_price ?? ""} onChange={e => setSegments(old => old.map(s => s.id === selected.id ? { ...s, selling_price: Number(e.target.value) } : s))} className="mt-1 w-full rounded border border-white/10 bg-[#0b1119] p-2 text-sm text-white"/></label></div><button onClick={() => void saveSegment(selected)} className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-white/5"><Save className="h-4 w-4"/>Save segment</button></div>}</div>}</section>}

      {tab === "inventory" && <section className="space-y-4"><div><h2 className="text-xl font-semibold">Price and Inventory</h2><p className="text-sm text-slate-400">Supplier listing price and last-seen status are used to flag component changes and unavailable builds.</p></div>{segments.length === 0 ? <Empty title="No playbook segments" text="Create playbook segments to see pricing and availability."/> : <div className="overflow-x-auto rounded-xl border border-white/10"><table className="w-full text-left text-sm"><thead className="bg-[#14202d] text-xs text-slate-400"><tr>{["Build segment", "Components", "Cost", "Selling price", "Availability", "State"].map(x=><th className="px-4 py-3" key={x}>{x}</th>)}</tr></thead><tbody>{segments.map(s=><tr key={s.id} className="border-t border-white/5"><td className="px-4 py-3 font-medium">{s.customer_type} · {s.budget_level}</td><td className="max-w-md px-4 py-3 text-xs text-slate-400">{Object.values(s.component_details).filter(Boolean).map(c=>c!.title).join(" · ") || "No components assigned"}</td><td className="px-4 py-3">£{s.component_cost.toFixed(2)}</td><td className="px-4 py-3">{s.proposed_selling_price != null ? <span>£{s.selling_price?.toFixed(2) ?? "—"} <span className="text-amber-300">→ £{s.proposed_selling_price.toFixed(2)}</span> <button onClick={()=>void applyPrice(s)} className="ml-2 text-cyan-300 underline">Apply</button></span> : s.selling_price == null ? "—" : `£${s.selling_price.toFixed(2)}`}</td><td className="px-4 py-3"><Badge tone={s.availability_status === "out_of_stock" ? "red" : "green"}>{s.availability_status === "out_of_stock" ? "Out of stock" : "Available"}</Badge></td><td className="px-4 py-3 text-xs">{s.is_live ? "Live" : "Draft"}</td></tr>)}</tbody></table></div>}</section>}

      {tab === "assets" && <section className="space-y-4"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">3D Assets</h2><p className="text-sm text-slate-400">Assets linked to curated catalogue variants. Review and approval remain in the existing 3D asset workflow.</p></div><a href="/components-3d-review?curatedOnly=1" className="rounded-lg border border-white/10 px-3 py-2 text-sm text-cyan-200 hover:bg-white/5">Review curated images and models</a></div>{selectedAssets.length === 0 ? <Empty title="No curated component assets found" text="When Hermes creates component image and model assets, they will appear here for review."/> : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{selectedAssets.map(a=>{const c=components.find(x=>x.id===a.subject_id);return <article key={a.id} className="overflow-hidden rounded-xl border border-white/10 bg-[#101924]">{a.preview_image_ref ? <img src={a.preview_image_ref} className="h-40 w-full object-contain bg-black/20" alt="Asset preview"/> : <div className="flex h-40 items-center justify-center bg-white/[.03] text-sm text-slate-600">No image preview</div>}<div className="p-3"><p className="line-clamp-2 text-sm font-medium">{c?.title ?? `Variant ${a.subject_id}`}</p><p className="mt-1 text-xs text-slate-400">{a.status.replaceAll("_"," ")}{a.glb_ref ? " · 3D model ready" : " · model pending"}</p>{a.review_decision && <p className="mt-2 text-xs text-emerald-300">Decision: {a.review_decision}</p>}</div></article>})}</div>}</section>}

      {tab === "live" && <section className="space-y-4"><div><h2 className="text-xl font-semibold">Go Live</h2><p className="text-sm text-slate-400">Final checks for publishing curated builds to the customer storefront.</p></div>{segments.length === 0 ? <Empty title="No builds ready for review" text="Add customer segments and assign curated components first."/> : <div className="space-y-3">{segments.map(s=>{const chosen=Object.values(s.component_details).filter(Boolean) as Component[];const required=["cpu","gpu","motherboard","ram","storage","psu","case"];const complete=required.every(slot=>s.component_details[slot] && s.component_details[slot]?.status === "active");const available=s.availability_status !== "out_of_stock";const priced=s.selling_price != null;const ready=complete&&available&&priced;return <article key={s.id} className="rounded-xl border border-white/10 bg-[#101924] p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-semibold">{s.customer_type} · {s.budget_level}</p><p className="mt-1 text-xs text-slate-400">{chosen.length} components assigned</p></div><Badge tone={ready ? "green" : "amber"}>{ready ? "Ready for go live" : "Checks required"}</Badge></div><div className="mt-4 grid gap-2 sm:grid-cols-3 text-xs"><CheckRow ok={complete} label="CPU, GPU, motherboard, RAM, storage, PSU and case assigned"/><CheckRow ok={available} label="All selected listings available"/><CheckRow ok={priced} label="Selling price set"/></div><button onClick={()=>void publish(s)} disabled={!ready && !s.is_live} className="mt-4 rounded-lg bg-cyan-500 px-3 py-2 text-xs font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">{s.is_live ? "Take offline" : "Publish segment"}</button></article>})}<p className="text-xs text-slate-500">{totalChecks} segment{totalChecks===1?"":"s"} · Live availability follows the latest captured supplier listing status.</p></div>}</section>}
      {reviewMatch && reviewMatchIndex != null && <MatchReviewModal
        match={reviewMatch} index={reviewMatchIndex} count={reviewCandidates.length}
        busy={busy} error={error} onClose={() => setReviewMatchIndex(null)}
        onPrevious={() => setReviewMatchIndex(index => index == null ? null : Math.max(0, index - 1))}
        onNext={() => setReviewMatchIndex(index => index == null ? null : Math.min(reviewCandidates.length - 1, index + 1))}
        onReview={status => void reviewBestseller(reviewMatch, status)}
      />}
      {busy && <div className="fixed bottom-5 right-5 flex items-center gap-2 rounded-lg border border-white/10 bg-[#14202d] px-3 py-2 text-xs"><Loader2 className="h-4 w-4 animate-spin"/>Saving…</div>}
    </div>
  </main>;
}

function MatchReviewModal({ match, index, count, busy, error, onClose, onPrevious, onNext, onReview }: {
  match: BestsellerMatch; index: number; count: number; busy: boolean; error: string;
  onClose: () => void; onPrevious: () => void; onNext: () => void;
  onReview: (status: BestsellerMatch["review_status"]) => void;
}) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-2 backdrop-blur-sm sm:p-5" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div role="dialog" aria-modal="true" aria-labelledby="match-review-title" className="flex h-[min(96vh,1100px)] w-full max-w-[1800px] flex-col overflow-hidden rounded-2xl border border-white/15 bg-[#0b1119] shadow-2xl">
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-white/10 px-4 py-3 sm:px-6">
        <div className="min-w-0"><p className="text-xs font-semibold uppercase tracking-widest text-cyan-300">Match review · {index + 1} of {count}</p><h2 id="match-review-title" className="truncate text-base font-semibold sm:text-xl">{CATEGORY_LABELS[match.category] ?? match.category} · Amazon rank #{match.rank}</h2></div>
        <div className="flex shrink-0 items-center gap-2"><Badge tone={match.review_status === "approved" ? "green" : match.review_status === "rejected" ? "red" : "amber"}>{match.review_status}</Badge><button type="button" onClick={onClose} aria-label="Close comparison" className="rounded-lg border border-white/10 p-2 text-slate-300 hover:bg-white/10"><X className="h-5 w-5" /></button></div>
      </header>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-px overflow-y-auto bg-white/10 md:grid-cols-2 md:overflow-hidden">
        <MatchImagePanel key={`amazon-${match.asin}`} label="Amazon bestseller" title={match.title} price={match.price} imageUrl={match.image_url} url={match.url} detail={`ASIN ${match.asin}`} />
        <MatchImagePanel key={`market-${match.marketplace_listing_id}`} label={match.marketplace_image_is_reference ? `${match.marketplace_source} · product reference photo` : `${match.marketplace_source} listing`} title={match.marketplace_title} price={match.marketplace_price} imageUrl={match.marketplace_image_url} url={match.marketplace_url} detail={match.marketplace_condition ?? "Condition unknown"} />
      </div>
      <footer className="shrink-0 border-t border-white/10 bg-[#0b1119] px-4 py-3 sm:px-6">
        {error && <p role="alert" className="mb-2 text-sm text-rose-300">{error}</p>}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex gap-2"><button type="button" onClick={onPrevious} disabled={index === 0} className="inline-flex items-center gap-1 rounded-lg border border-white/15 px-3 py-2 text-sm font-medium hover:bg-white/10 disabled:opacity-40"><ChevronLeft className="h-4 w-4" />Previous</button><button type="button" onClick={onNext} disabled={index === count - 1} className="inline-flex items-center gap-1 rounded-lg border border-white/15 px-3 py-2 text-sm font-medium hover:bg-white/10 disabled:opacity-40">Next<ChevronRight className="h-4 w-4" /></button></div>
          <div className="flex gap-2"><button type="button" disabled={busy} onClick={() => onReview("rejected")} className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-bold text-white hover:bg-rose-500 disabled:opacity-50"><X className="h-5 w-5" />Reject</button><button type="button" disabled={busy} onClick={() => onReview("approved")} className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-emerald-400 disabled:opacity-50"><Check className="h-5 w-5" />Approve</button></div>
        </div>
      </footer>
    </div>
  </div>;
}

function MatchImagePanel({ label, title, price, imageUrl, url, detail }: { label: string; title: string; price: number | null; imageUrl: string | null; url: string | null; detail: string }) {
  const [failed, setFailed] = useState(false);
  return <div className="relative flex min-h-[360px] flex-col overflow-hidden bg-white md:min-h-0">
    <div className="absolute left-4 top-4 z-10 rounded-full bg-slate-950/85 px-3 py-1.5 text-xs font-bold uppercase tracking-wide text-white shadow-lg">{label}</div>
    {imageUrl && !failed ? <img src={imageUrl} alt={title} onError={() => setFailed(true)} className="min-h-0 h-full w-full flex-1 object-contain p-4 pb-28" /> : <div className="flex flex-1 flex-col items-center justify-center gap-3 text-slate-500"><ImageIcon className="h-12 w-12" /><span className="text-sm">Picture unavailable</span></div>}
    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950 via-slate-950/95 to-transparent px-5 pb-5 pt-14 text-white sm:px-7">
      <p className="line-clamp-3 text-base font-semibold leading-snug sm:text-lg">{title}</p>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-2"><div><p className="text-2xl font-bold">{price == null ? "Price unavailable" : `£${price.toFixed(2)}`}</p><p className="text-xs text-slate-300">{detail}</p></div>{url && <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-md border border-white/20 bg-slate-900/80 px-2.5 py-1.5 text-xs font-semibold hover:bg-slate-800">Open listing<ExternalLink className="h-3.5 w-3.5" /></a>}</div>
    </div>
  </div>;
}

function Empty({title,text}:{title:string;text:string}) { return <div className="rounded-xl border border-dashed border-white/10 bg-white/[.02] px-6 py-12 text-center"><Cpu className="mx-auto h-8 w-8 text-slate-600"/><p className="mt-3 font-semibold text-slate-300">{title}</p><p className="mt-1 text-sm text-slate-500">{text}</p></div>; }
function ProductThumbnail({ src, alt, large = false }: { src?: string | null; alt: string; large?: boolean }) {
  const [failed, setFailed] = useState(false);
  const size = large ? "h-36 w-full" : "h-16 w-16";
  return <div className={`flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-white/10 bg-white ${size}`}>
    {src && !failed ? <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} className="h-full w-full object-contain" /> : <ImageIcon aria-label="Image unavailable" className="h-6 w-6 text-slate-400" />}
  </div>;
}
function Badge({children,tone}:{children:ReactNode;tone:"green"|"red"|"amber"}) { return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${tone==="green"?"border-emerald-400/20 bg-emerald-400/10 text-emerald-300":tone==="red"?"border-rose-400/20 bg-rose-400/10 text-rose-300":"border-amber-400/20 bg-amber-400/10 text-amber-300"}`}>{children}</span>; }
function Toggle({checked,onClick}:{checked:boolean;onClick:()=>void}) { return <button type="button" role="switch" aria-checked={checked} onClick={onClick} className={`relative h-6 w-11 rounded-full transition ${checked?"bg-cyan-400":"bg-slate-700"}`}><span className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${checked?"left-6":"left-1"}`}/></button>; }
function CheckRow({ok,label}:{ok:boolean;label:string}) { return <div className={`flex items-center gap-2 ${ok?"text-emerald-300":"text-amber-300"}`}>{ok?<Check className="h-4 w-4"/>:<AlertCircle className="h-4 w-4"/>}{label}</div>; }

function DraftOverview({ build }: { build?: DraftBuild }) {
  if (!build) return null;
  return <section className="rounded-xl border border-cyan-400/20 bg-[#101924] p-5">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs uppercase tracking-widest text-cyan-300">{build.playbook_id} · Planning draft</p><h2 className="mt-1 text-xl font-semibold">{build.name}</h2><p className="mt-1 max-w-3xl text-sm text-slate-400">{build.note}</p></div><div className="text-right text-sm"><p>Estimated components: £{build.est_component_cost_gbp.toLocaleString()}</p><p className="text-slate-400">Indicative sell: £{build.indicative_sell_gbp.toLocaleString()}</p></div></div>
    <p className="mt-4 text-xs text-amber-300">These specifications and prices are estimates. Product links, supplier availability, compatibility and selling prices still require review.</p>
    <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{build.core_components.filter(c => c.category !== "Case").map(c => <div key={c.category} className="rounded-lg border border-white/10 bg-[#0b1119] p-3"><p className="text-[11px] uppercase text-slate-500">{c.category}</p><p className="mt-1 text-sm font-medium">{c.sku_name}</p><p className="mt-1 text-xs text-slate-400">Estimated £{c.cost_gbp.toFixed(2)}</p></div>)}</div>
    <p className="mt-4 text-xs text-slate-400">Case: customer choice from compatible curated bestseller cases. The draft specified {build.core_components.find(c => c.category === "Case")?.sku_name} as a reference.</p>
    <details className="mt-4 text-sm"><summary className="cursor-pointer text-cyan-200">Draft upsells ({build.upsells.length})</summary><div className="mt-3 space-y-2">{build.upsells.length ? build.upsells.map((u, i) => <p key={i} className="rounded border border-white/10 p-2 text-xs">{u.category}: {u.from_sku} → {u.to_sku} · estimated cost +£{u.delta_cost_gbp.toFixed(2)} · selling price pending</p>) : <p className="text-xs text-amber-300">No upsells defined for this draft.</p>}</div></details>
  </section>;
}

function ReviewedBestsellerChoices({ segment, matches, busy, onAssign }: {
  segment: Segment; matches: BestsellerMatch[]; busy: boolean;
  onAssign: (segment: Segment, slot: string, cpk: string) => Promise<void>;
}) {
  const slotCategory: Record<string, string> = { cpu: "cpu", gpu: "gpu", motherboard: "motherboard", ram: "ram", storage: "storage", psu: "psu", cooling: "cooler", case: "case" };
  const choices = segment.bestseller_components ?? {};
  const selectedMatches = Object.values(choices).map(ref => matches.find(item => item.category === ref.category && item.cpk === ref.cpk)).filter((item): item is BestsellerMatch => Boolean(item));
  const observedTotal = selectedMatches.reduce((sum, item) => sum + item.marketplace_price, 0);
  return <section className="rounded-xl border border-emerald-400/20 bg-[#101924] p-5">
    <h2 className="text-lg font-semibold">Reviewed bestseller products</h2>
    <p className="mt-1 text-sm text-slate-400">Approve products in Curated Catalogue, then assign them here. A marketplace price is a comparison snapshot, not a supplier quote.</p>
    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">{Object.entries(slotCategory).map(([slot, category]) => {
      const options = matches.filter(item => item.category === category && item.review_status === "approved").sort((a, b) => a.rank - b.rank);
      const current = choices[slot]?.cpk ?? "";
      return <label key={slot} className="space-y-1.5 text-xs text-slate-400">{SLOT_LABELS[slot]}
        <select disabled={busy} value={current} onChange={event => void onAssign(segment, slot, event.target.value)} className="w-full rounded-lg border border-white/10 bg-[#0b1119] px-3 py-2.5 text-sm text-white disabled:opacity-50">
          <option value="">No reviewed product assigned</option>
          {options.map(item => <option key={item.cpk} value={item.cpk}>#{item.rank} {item.title.slice(0, 75)} · £{item.marketplace_price.toFixed(2)}</option>)}
        </select>
      </label>;
    })}</div>
    <p className="mt-4 text-xs text-amber-300">{selectedMatches.length}/8 hardware slots linked · marketplace comparison total £{observedTotal.toFixed(2)}. Compatibility, delivery, procurement cost and PricingBot selling price still need validation before launch.</p>
  </section>;
}
