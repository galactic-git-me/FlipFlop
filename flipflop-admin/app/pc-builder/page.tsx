"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, Check, ChevronLeft, ChevronRight, Cpu, ExternalLink, ImageIcon, LayoutGrid, List, Loader2, Plus, RefreshCw, Save, Sparkles, Table2, X } from "lucide-react";
import type { ReactNode } from "react";
import Shared3DAssetGrid from "@/components/catalogue/Shared3DAssetGrid";
import { api } from "@/lib/api";

type ViewMode = "table" | "listings" | "grid";
type Tab = "segments" | "catalogue" | "images" | "playbook" | "inventory" | "assets" | "live";
type Component = { id: number; slot_type: string; title: string; price: number; status: string; last_seen_at?: string; image_url?: string | null; url?: string; curated_for_builds: boolean };
type CurationCandidate = Component & { segment_label: string; reference_image_url: string | null };
type BestsellerMatch = { category: string; rank: number; asin: string; cpk: string; title: string; url: string | null; image_url: string | null; price: number | null; marketplace_listing_id: string; marketplace_source: string; marketplace_title: string; marketplace_url: string | null; marketplace_image_url: string | null; marketplace_image_is_reference: boolean; marketplace_is_self_capture: boolean; marketplace_price: number | null; marketplace_condition: string | null; marketplace_seen_at: string; review_status: "pending" | "approved" | "rejected" };
type DraftBuild = { playbook_id: string; customer_type: string; budget_tier: string; name: string; status: string; est_component_cost_gbp: number; indicative_sell_gbp: number; note: string; core_components: { category: string; sku_name: string; cost_gbp: number }[]; upsells: { category: string; from_sku: string; to_sku: string; delta_cost_gbp: number; delta_sell_gbp: number | null }[] };
type ApprovedUpgrade = { candidate_index: number; category: string; from_sku: string; to_sku: string; delta_cost_gbp: number; slot_id: number; target_variant_id: number; target_title: string; target_display_price: number; popularity_evidence: { source: string; category: string; cpk: string; rank: number; observed_price_gbp: number; title: string; url: string | null; captured_at: string | null } };
type Segment = { id: number; customer_type: string; budget_level: string; budget_min: number | null; budget_max: number | null; components: Record<string, number>; bestseller_components: Record<string, { category: string; cpk: string }>; approved_upgrades?: ApprovedUpgrade[]; allow_flip_component_sources: boolean; software_profile?: { recommended_package_ids?: string[]; rationale?: string } | null; effective_software_profile?: { recommended_package_ids?: string[]; rationale?: string } | null; component_details: Record<string, Component | null>; component_cost: number; selling_price?: number; proposed_selling_price?: number; availability_status: "not_configured" | "in_stock" | "out_of_stock"; is_live: boolean; regeneration_status: string };
type SoftwareApp = { package_id: string; name: string; category: string; estimated_minutes_saved: number; license_note: string };
type Asset = { id: number; subject_type: string; subject_id: number | null; status: string; version?: number; preview_image_ref?: string | null; glb_ref?: string | null; review_decision?: string | null; category?: string | null };
const TABS: { id: Tab; label: string }[] = [
  { id: "segments", label: "Customer Types + Budget Levels" }, { id: "catalogue", label: "Curated Catalogue" },
  { id: "images", label: "Listing Images" }, { id: "playbook", label: "The Playbook" }, { id: "inventory", label: "Price and Inventory" },
  { id: "assets", label: "3D Assets" }, { id: "live", label: "Go Live" },
];
const SLOT_LABELS: Record<string, string> = { cpu: "CPU", gpu: "GPU", motherboard: "Motherboard", ram: "RAM", storage: "Storage", psu: "Power supply", cooling: "Cooling", case: "Case", os: "Operating system" };
const CATEGORY_LABELS: Record<string, string> = { cpu: "CPUs", gpu: "Graphics cards", motherboard: "Motherboards", ram: "Memory", storage: "Storage", psu: "Power supplies", cooler: "CPU coolers", case: "Cases", os: "Operating systems" };
const categoryForSlot = (slot: string) => slot === "cooling" ? "cooler" : slot;
const DRAFT_CATEGORY_SLOT: Record<string, string> = {
  "CPU / APU": "cpu", Motherboard: "motherboard", Memory: "ram", Graphics: "gpu",
  "Primary storage": "storage", "Power supply": "psu", "CPU cooling": "cooling",
  Case: "case", "Operating system": "os",
};
const normalizeModel = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, "");
const BUDGET_LEVELS = ["Budget", "Mid-range", "High-end"] as const;
const formatBudgetRange = (segment: Segment) => segment.budget_min == null ? "Range needed" : segment.budget_max == null ? `£${segment.budget_min.toLocaleString()}+` : `£${segment.budget_min.toLocaleString()}–£${(segment.budget_max - 1).toLocaleString()}`;

function collectCurationCandidates(segments: Segment[], matches: BestsellerMatch[]): CurationCandidate[] {
  const seen = new Set<number>();
  return segments.flatMap(segment => Object.entries(segment.component_details ?? {}).flatMap(([slot, component]) => {
    if (!component || component.curated_for_builds || component.status !== "active" || seen.has(component.id)) return [];
    seen.add(component.id);
    const identity = segment.bestseller_components?.[slot];
    const referenceImage = identity
      ? matches.find(match => match.category === identity.category && match.cpk === identity.cpk)?.image_url ?? null
      : null;
    return [{ ...component, segment_label: `${segment.customer_type} · ${segment.budget_level}`, reference_image_url: referenceImage }];
  }));
}

export default function CuratedBuildsPage() {
  const [tab, setTab] = useState<Tab>("segments");
  const [view, setView] = useState<ViewMode>("grid");
  const [segments, setSegments] = useState<Segment[]>([]);
  const [components, setComponents] = useState<Component[]>([]);
  const [bestsellerMatches, setBestsellerMatches] = useState<BestsellerMatch[]>([]);
  const [draftBuilds, setDraftBuilds] = useState<DraftBuild[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [softwareApps, setSoftwareApps] = useState<SoftwareApp[]>([]);
  const [softwareDraft, setSoftwareDraft] = useState<string[]>([]);
  const [softwareRationale, setSoftwareRationale] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const [reviewFilter, setReviewFilter] = useState<"all" | BestsellerMatch["review_status"]>("pending");
  const [selectedImageMatches, setSelectedImageMatches] = useState<Set<string>>(new Set());
  const [reviewMatchIndex, setReviewMatchIndex] = useState<number | null>(null);
  const [curationQueue, setCurationQueue] = useState<CurationCandidate[] | null>(null);
  const [curationQueueIndex, setCurationQueueIndex] = useState(0);
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
      try { setSoftwareApps((await api.dispatch.softwareCatalogue()).items); }
      catch { setSoftwareApps([]); }
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load curated builds"); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    setSoftwareDraft(selected?.effective_software_profile?.recommended_package_ids ?? selected?.software_profile?.recommended_package_ids ?? []);
    setSoftwareRationale(selected?.effective_software_profile?.rationale ?? selected?.software_profile?.rationale ?? "");
  }, [selected?.id, selected?.software_profile, selected?.effective_software_profile]);
  useEffect(() => {
    if (tab !== "playbook" || selectedId === null) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setSelectedId(null); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [tab, selectedId]);

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
      const result = await response.json();
      setBestsellerMatches(old => old.map(candidate => candidate.category === item.category && candidate.cpk === item.cpk ? { ...candidate, review_status: status } : candidate));
      setSelectedImageMatches(current => { const next = new Set(current); next.delete(imageMatchKey(item)); return next; });
      if (result.invalidated_cells) setMessage(`${result.invalidated_cells} Playbook cell(s) were unpublished and their reviewed component offers removed because popularity evidence is no longer approved.`);
      if (result.invalidated_cells) await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save review"); }
    finally { setBusy(false); }
  };
  const imageMatchKey = (item: Pick<BestsellerMatch, "category" | "cpk">) => `${item.category}\u0000${item.cpk}`;
  const imageReviewCandidates = useMemo(() => bestsellerMatches.filter(item =>
    (reviewFilter === "all" || item.review_status === reviewFilter) &&
    Boolean(item.marketplace_image_url || item.image_url)
  ), [bestsellerMatches, reviewFilter]);
  const actionableImageCandidates = imageReviewCandidates.filter(item => item.review_status !== "approved");
  const allImageCandidatesSelected = actionableImageCandidates.length > 0 && actionableImageCandidates.every(item => selectedImageMatches.has(imageMatchKey(item)));
  const toggleAllImageMatches = () => setSelectedImageMatches(current => {
    const next = new Set(current);
    if (allImageCandidatesSelected) actionableImageCandidates.forEach(item => next.delete(imageMatchKey(item)));
    else actionableImageCandidates.forEach(item => next.add(imageMatchKey(item)));
    return next;
  });
  const bulkApproveImageMatches = async () => {
    const items = actionableImageCandidates.filter(item => selectedImageMatches.has(imageMatchKey(item)));
    if (!items.length) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch("/api/curated-builds/bestseller-catalogue/review/bulk", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: items.map(({ category, cpk }) => ({ category, cpk })) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not approve selected matches");
      const approvedKeys = new Set(items.filter(item => !result.failed.some((failure: { category: string; cpk: string }) => failure.category === item.category && failure.cpk === item.cpk)).map(imageMatchKey));
      setBestsellerMatches(current => current.map(item => approvedKeys.has(imageMatchKey(item)) ? { ...item, review_status: "approved" } : item));
      setSelectedImageMatches(new Set((result.failed ?? []).map((item: { category: string; cpk: string }) => imageMatchKey(item))));
      setMessage(`Approved ${result.approved} match${result.approved === 1 ? "" : "es"}.${result.failed?.length ? ` ${result.failed.length} could not be approved; they remain selected.` : ""}`);
      if (result.failed?.length) setError(result.failed.map((item: { category: string; cpk: string; detail: string }) => `${item.category} · ${item.cpk}: ${item.detail}`).join("; "));
    } catch (e) { setError(e instanceof Error ? e.message : "Could not approve selected matches"); }
    finally { setBusy(false); }
  };
  const autoLinkBestsellerComponents = async () => {
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch("/api/curated-builds/auto-link-bestseller-components", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not auto-link Playbook products");
      setMessage(`Linked ${data.linked} active supplier listing${data.linked === 1 ? "" : "s"} by Amazon ASIN/CPK. ${data.linked_needs_curation} need Curated Catalogue approval before publishing; ${data.unmatched} have no exact active supplier match.`);
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not auto-link Playbook products"); }
    finally { setBusy(false); }
  };
  const approveCurationCandidate = async () => {
    const item = curationQueue?.[curationQueueIndex];
    if (!item) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/curated-builds/variants/${item.id}/curated`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ curated_for_builds: true }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not approve supplier listing");
      setMessage(`Approved ${item.title} for the Curated Catalogue.`);
      if (curationQueueIndex + 1 >= curationQueue.length) setCurationQueue(null);
      else setCurationQueueIndex(index => index + 1);
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not approve supplier listing"); }
    finally { setBusy(false); }
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
  const pendingCurationCandidates = useMemo(() => collectCurationCandidates(segments, bestsellerMatches), [segments, bestsellerMatches]);
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
  const curatedComponents = components.filter(component => component.curated_for_builds);
  const recordUploadedAsset = (asset: Asset) => setAssets(current => [asset, ...current.filter(existing => existing.id !== asset.id)]);
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
        <div className="rounded-xl border border-white/10 bg-[#101924] p-4"><h3 className="font-semibold">Amazon bestseller matches</h3><p className="mt-1 text-xs text-slate-400">{bestsellerMatches.length} captured Amazon bestsellers. Each ASIN has an Amazon match; independent marketplace sightings appear when available. Prices and availability need review before approval.</p><div className="mt-3 flex flex-wrap gap-2"><select value={reviewFilter} onChange={e => setReviewFilter(e.target.value as typeof reviewFilter)} aria-label="Review status" className="rounded border border-white/10 bg-[#0b1119] px-3 py-2 text-xs"><option value="pending">Pending review</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="all">All statuses</option></select><span className="self-center text-xs text-slate-400">{filteredBestsellers.length} shown</span></div></div>
        {filteredBestsellers.length === 0 ? <Empty title="No matched bestseller products" text="No Amazon bestseller products match this filter."/> : <div className="overflow-x-auto rounded-xl border border-white/10"><table className="w-full text-left text-xs"><thead className="bg-[#14202d] text-slate-400"><tr>{["Amazon rank", "Picture", "Bestseller product", "Amazon price", "Marketplace match", "Marketplace price", "Review"].map(h => <th key={h} className="px-3 py-3">{h}</th>)}</tr></thead><tbody>{filteredBestsellers.map(c => <tr key={`${c.category}-${c.asin}`} className="border-t border-white/5 align-top"><td className="whitespace-nowrap px-3 py-3">{c.category} #{c.rank}</td><td className="px-3 py-3"><ProductThumbnail src={c.image_url} alt={c.title} /></td><td className="max-w-sm px-3 py-3"><a className="font-medium text-cyan-200 hover:underline" href={c.url ?? undefined} target="_blank" rel="noreferrer">{c.title}</a><p className="mt-1 text-slate-500">ASIN {c.asin}</p></td><td className="px-3 py-3">{c.price == null ? "—" : `£${c.price.toFixed(2)}`}</td><td className="max-w-sm px-3 py-3"><a className="text-cyan-200 hover:underline" href={c.marketplace_url ?? undefined} target="_blank" rel="noreferrer">{c.marketplace_title}</a><p className="mt-1 text-slate-500">{c.marketplace_source} · {c.marketplace_condition ?? "condition unknown"}</p></td><td className="whitespace-nowrap px-3 py-3">{c.marketplace_price == null ? "—" : `£${c.marketplace_price.toFixed(2)}`}</td><td className="min-w-48 px-3 py-3"><div className="flex items-center gap-2"><Badge tone={c.review_status === "approved" ? "green" : c.review_status === "rejected" ? "red" : "amber"}>{c.review_status}</Badge><button onClick={() => setReviewMatchIndex(reviewCandidates.findIndex(item => item.category === c.category && item.asin === c.asin))} className="rounded-md border border-cyan-400/30 px-2.5 py-1.5 font-semibold text-cyan-200 hover:bg-cyan-400/10">Compare images</button></div></td></tr>)}</tbody></table></div>}
        {components.length > 0 && <><h3 className="font-semibold">Approved catalogue variants</h3>{view === "table" ? <div className="overflow-x-auto rounded-xl border border-white/10"><table className="w-full text-left text-sm"><thead className="bg-[#14202d] text-xs text-slate-400"><tr>{["Product", "Type", "Price", "Availability", "Curated"].map(h => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead><tbody>{filteredComponents.map(c => <tr key={c.id} className="border-t border-white/5"><td className="max-w-xl px-4 py-3"><div className="flex items-center gap-3"><ProductThumbnail src={c.image_url} alt={c.title} /><span>{c.title}</span></div></td><td className="px-4 py-3">{SLOT_LABELS[c.slot_type] || c.slot_type}</td><td className="px-4 py-3">£{c.price?.toFixed(2)}</td><td className="px-4 py-3"><Badge tone={c.status === "active" ? "green" : "red"}>{c.status}</Badge></td><td className="px-4 py-3"><Toggle checked={c.curated_for_builds} onClick={() => void toggleCurated(c)}/></td></tr>)}</tbody></table></div> : <div className={view === "grid" ? "grid gap-4 sm:grid-cols-2 xl:grid-cols-4" : "space-y-3"}>{filteredComponents.map(c => <article key={c.id} className={`overflow-hidden rounded-xl border border-white/10 bg-[#101924] ${view === "listings" ? "flex items-center gap-4 p-3" : "p-3"}`}><div className={view === "grid" ? "mb-3" : ""}><ProductThumbnail src={c.image_url} alt={c.title} large={view === "grid"}/></div><div className="min-w-0 flex-1"><p className="line-clamp-2 text-sm font-medium">{c.title}</p><p className="mt-1 text-xs text-slate-400">{SLOT_LABELS[c.slot_type] || c.slot_type} · £{c.price?.toFixed(2)}</p><p className="mt-1 text-xs text-slate-500">Last seen {c.last_seen_at ? new Date(c.last_seen_at).toLocaleDateString() : "unknown"}</p></div><Toggle checked={c.curated_for_builds} onClick={() => void toggleCurated(c)}/></article>)}</div>}</>}</section>}

      {tab === "images" && <section className="space-y-5"><header><p className="font-mono text-[10px] uppercase tracking-[.2em] text-cyan-300">Curated builds · image review</p><h2 className="mt-1 text-xl font-semibold">Listing Images</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">Review the captured product photo beside its scraped marketplace listing image. Approving a match makes all captured listing photos and any available videos eligible for curated-build galleries. Approve only exact product matches with suitable media.</p></header><div className="flex flex-wrap items-center gap-2"><select value={reviewFilter} onChange={event => { setReviewFilter(event.target.value as typeof reviewFilter); setSelectedImageMatches(new Set()); }} aria-label="Listing image approval status" className="rounded border border-white/10 bg-[#0b1119] px-3 py-2 text-xs"><option value="pending">Awaiting approval</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="all">All statuses</option></select><span className="text-xs text-slate-400">{imageReviewCandidates.length} image matches</span><label className="ml-auto flex cursor-pointer items-center gap-2 rounded border border-white/10 px-3 py-2 text-xs text-slate-300"><input type="checkbox" checked={allImageCandidatesSelected} disabled={actionableImageCandidates.length === 0 || busy} onChange={toggleAllImageMatches} />Select all {actionableImageCandidates.length ? `(${actionableImageCandidates.length})` : ""}</label><button type="button" disabled={busy || selectedImageMatches.size === 0} onClick={() => void bulkApproveImageMatches()} className="rounded bg-emerald-400 px-3 py-2 text-xs font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50">{busy ? "Approving…" : `Approve selected (${selectedImageMatches.size})`}</button></div>{imageReviewCandidates.length === 0 ? <Empty title="No listing images in this review state" text="Captured bestseller and marketplace images will appear here when available."/> : <div className="grid gap-4 xl:grid-cols-2">{imageReviewCandidates.map(item => <article key={JSON.stringify([item.category, item.asin, item.marketplace_listing_id])} className="overflow-hidden rounded-xl border border-white/10 bg-[#101924]"><div className="grid grid-cols-2 gap-px bg-white/10">{[[item.image_url, "Amazon reference", item.url], [item.marketplace_image_url, `${item.marketplace_source} listing`, item.marketplace_url]].map(([src, label, href]) => <div key={label} className="relative grid min-h-44 place-items-center bg-[#0b1119] p-3"><span className="absolute left-3 top-3 rounded bg-black/70 px-2 py-1 text-[10px] text-slate-300">{label}</span>{src ? <a href={href ?? undefined} target="_blank" rel="noreferrer"><img src={src} alt={`${item.title} · ${label}`} className="h-40 w-full object-contain"/></a> : <span className="text-xs text-slate-500">No captured image</span>}</div>)}</div><div className="flex flex-wrap items-start justify-between gap-3 p-4"><div className="min-w-0"><p className="text-xs uppercase tracking-wide text-slate-500">{item.category} · rank #{item.rank} · {item.marketplace_condition ?? "condition unknown"}</p><p className="mt-1 line-clamp-2 text-sm font-medium text-white">{item.marketplace_title}</p><p className="mt-1 text-xs text-slate-400">{item.marketplace_source} · CPK {item.cpk}</p></div><div className="flex shrink-0 flex-wrap items-center gap-2"><label className="flex items-center gap-1.5 text-xs text-slate-300"><input type="checkbox" aria-label={`Select ${item.marketplace_title}`} checked={selectedImageMatches.has(imageMatchKey(item))} disabled={busy || item.review_status === "approved"} onChange={event => setSelectedImageMatches(current => { const next = new Set(current); if (event.target.checked) next.add(imageMatchKey(item)); else next.delete(imageMatchKey(item)); return next; })}/>{item.review_status === "approved" ? "Approved" : "Select"}</label><Badge tone={item.review_status === "approved" ? "green" : item.review_status === "rejected" ? "red" : "amber"}>{item.review_status}</Badge>{item.review_status !== "approved" && <button disabled={busy} onClick={() => void reviewBestseller(item, "approved")} className="rounded-md bg-emerald-400 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50">Approve</button>}{item.review_status !== "rejected" && <button disabled={busy} onClick={() => void reviewBestseller(item, "rejected")} className="rounded-md border border-rose-400/30 px-3 py-2 text-xs text-rose-200 disabled:opacity-50">Reject</button>}</div></div></article>)}</div>}</section>}
      {tab === "playbook" && <PlaybookGrid builds={draftBuilds} segments={segments} matches={bestsellerMatches} selectedId={selectedId} onSelect={setSelectedId} />}
      {tab === "playbook" && selectedId !== null && selected && <div role="dialog" aria-modal="true" aria-label={`${selected.customer_type} ${selected.budget_level} build`} className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-3 sm:p-6" onClick={() => setSelectedId(null)}><div className="max-h-[94vh] w-full max-w-6xl overflow-y-auto rounded-2xl border border-white/15 bg-[#0b1119] p-4 shadow-2xl sm:p-6" onClick={event => event.stopPropagation()}><div className="mb-4 flex items-start justify-between gap-4"><div><p className="text-xs uppercase tracking-widest text-cyan-300">Playbook build</p><h2 className="mt-1 text-2xl font-semibold">{draftBuilds.find(build => build.customer_type === selected.customer_type && build.budget_tier === selected.budget_level)?.name ?? selected.customer_type}</h2><p className="mt-1 text-sm text-slate-400">{selected.customer_type} · {selected.budget_level} · customer budget {formatBudgetRange(selected)}</p></div><button type="button" onClick={() => setSelectedId(null)} aria-label="Close build details" className="rounded-lg border border-white/10 p-2 text-slate-300 hover:bg-white/10"><X className="h-5 w-5"/></button></div><section className="mb-4 rounded-xl border border-white/10 bg-[#101924] p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">Recommended software for this Playbook cell</h3><p className="mt-1 text-xs text-slate-400">Choose the recommended free applications for this customer type and budget. Customers can add or remove available apps before setup.</p></div><div className="flex gap-2"><button type="button" disabled={busy} onClick={() => void saveSegment({ ...selected, software_profile: null })} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 disabled:opacity-50">Restore inherited default</button><button type="button" disabled={busy} onClick={() => void saveSegment({ ...selected, software_profile: { recommended_package_ids: softwareDraft, rationale: softwareRationale } })} className="rounded-lg bg-cyan-400 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50">Save software recommendations</button></div></div><label className="mt-3 block text-xs text-slate-400">Why these apps suit the segment</label><textarea value={softwareRationale} maxLength={2000} onChange={event => setSoftwareRationale(event.target.value)} rows={2} className="mt-1 w-full rounded-lg border border-white/10 bg-[#0b1119] p-2 text-sm"/><div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{softwareApps.map(app => <label key={app.package_id} className="flex items-start gap-2 rounded-lg border border-white/5 p-2 text-xs"><input type="checkbox" checked={softwareDraft.includes(app.package_id)} onChange={event => setSoftwareDraft(current => event.target.checked ? [...current, app.package_id] : current.filter(id => id !== app.package_id))}/><span><span className="font-medium">{app.name}</span><span className="block text-slate-500">{app.category} · indicative {app.estimated_minutes_saved} min saved</span></span></label>)}</div>{softwareApps.length === 0 && <p className="mt-3 text-xs text-amber-300">Reviewed software catalogue unavailable; recommendations cannot be edited.</p>}</section><label className="mb-4 flex items-start gap-3 rounded-lg border border-white/10 bg-white/[.03] p-3 text-sm"><input type="checkbox" className="mt-1" checked={selected.allow_flip_component_sources} disabled={busy} onChange={event => void saveSegment({ ...selected, allow_flip_component_sources: event.target.checked })}/><span><span className="font-medium">Allow components recovered from potential flips</span><span className="mt-1 block text-xs text-slate-400">Candidates must meet or exceed this cell&apos;s benchmarks. Sources are for Flexible delivery or Ready-to-Ship builds.</span></span></label><FlipMatchPanel segment={selected}/><ReviewedBestsellerChoices segment={selected} build={draftBuilds.find(b => b.customer_type === selected.customer_type && b.budget_tier === selected.budget_level)} matches={bestsellerMatches} components={components} onSave={saveSegment} /><div className="mt-4 flex justify-end"><button disabled={busy} onClick={() => void generate(selected)} className="inline-flex items-center gap-2 rounded-lg bg-violet-500 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Sparkles className="h-4 w-4"/>{selected.regeneration_status === "queued" ? "Generation queued" : "Generate Build with Hermes"}</button></div></div></div>}

      {tab === "inventory" && <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
          <h2 className="text-xl font-semibold">Price and Inventory</h2>
          <p className="text-sm text-slate-400">Supplier listings are matched automatically to the Playbook’s Amazon ASIN/CPK identities. Only active Curated Catalogue listings are eligible.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={busy} onClick={() => { setCurationQueue(pendingCurationCandidates); setCurationQueueIndex(0); }} className="inline-flex items-center gap-2 rounded-lg border border-emerald-400/30 px-3 py-2 text-sm font-semibold text-emerald-200 disabled:opacity-50">Review linked matches ({pendingCurationCandidates.length})</button>
            <button type="button" disabled={busy} onClick={() => void autoLinkBestsellerComponents()} className="inline-flex items-center gap-2 rounded-lg bg-cyan-400 px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`}/>Auto-link by ASIN / CPK</button>
          </div>
        </div>
        {segments.length === 0 ? <Empty title="No playbook segments" text="Create playbook segments to see pricing and availability."/> : <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-[#14202d] text-xs text-slate-400"><tr>{["Build segment", "Components", "Supplier cost", "Selling price", "Availability", "State"].map(x=><th className="px-4 py-3" key={x}>{x}</th>)}</tr></thead>
            <tbody>{segments.map(segment => {
              const build = draftBuilds.find(item => item.customer_type === segment.customer_type && item.budget_tier === segment.budget_level);
              const linkedCount = Object.values(segment.component_details ?? {}).filter(Boolean).length;
              const stockTrackedCount = build?.core_components.filter(part => DRAFT_CATEGORY_SLOT[part.category] !== "os").length ?? 0;
              return <tr key={segment.id} className="border-t border-white/5">
                <td className="px-4 py-3 font-medium">{segment.customer_type} · {segment.budget_level}</td>
                <td className="max-w-md px-4 py-3 text-xs text-slate-400">
                  <PlannedPartsDisclosure segment={segment} build={build} matches={bestsellerMatches}/>
                </td>
                <td className="px-4 py-3">{linkedCount > 0 ? `£${segment.component_cost.toFixed(2)}` : "—"}</td>
                <td className="px-4 py-3">{segment.proposed_selling_price != null ? <span>£{segment.selling_price?.toFixed(2) ?? "—"} <span className="text-amber-300">→ £{segment.proposed_selling_price.toFixed(2)}</span> <button onClick={() => void applyPrice(segment)} className="ml-2 text-cyan-300 underline">Apply</button></span> : segment.selling_price == null ? "—" : `£${segment.selling_price.toFixed(2)}`}</td>
                <td className="px-4 py-3"><AvailabilityBadge segment={segment} plannedCount={stockTrackedCount}/></td>
                <td className="px-4 py-3 text-xs">{segment.is_live ? "Live" : "Draft"}</td>
              </tr>;
            })}</tbody>
          </table>
        </div>}
      </section>}

      {tab === "assets" && <section className="space-y-4"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">Shared 3D Assets</h2><p className="text-sm text-slate-400">Every Curated Catalogue component appears here, including products still waiting for a model. Assets are shared with the Custom Catalogue for the same product.</p></div><a href="/components-3d-review?curatedOnly=1" className="rounded-lg border border-white/10 px-3 py-2 text-sm text-cyan-200 hover:bg-white/5">Review curated images and models</a></div><Shared3DAssetGrid items={curatedComponents} assets={assets} onUploaded={recordUploadedAsset} onMessage={setMessage} onError={setError}/></section>}

      {tab === "live" && <section className="space-y-4"><div><h2 className="text-xl font-semibold">Go Live</h2><p className="text-sm text-slate-400">Final checks for publishing curated builds to the customer storefront.</p></div>{segments.length === 0 ? <Empty title="No builds ready for review" text="Add customer segments and assign curated components first."/> : <div className="space-y-3">{segments.map(s=>{const chosen=Object.values(s.component_details).filter(Boolean) as Component[];const required=["cpu","gpu","motherboard","ram","storage","psu","case"];const complete=required.every(slot=>s.component_details[slot] && s.component_details[slot]?.status === "active");const available=s.availability_status !== "out_of_stock";const priced=s.selling_price != null;const ready=complete&&available&&priced;return <article key={s.id} className="rounded-xl border border-white/10 bg-[#101924] p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-semibold">{s.customer_type} · {s.budget_level}</p><p className="mt-1 text-xs text-slate-400">{chosen.length} components assigned</p></div><Badge tone={ready ? "green" : "amber"}>{ready ? "Ready for go live" : "Checks required"}</Badge></div><div className="mt-4 grid gap-2 sm:grid-cols-3 text-xs"><CheckRow ok={complete} label="CPU, GPU, motherboard, RAM, storage, PSU and case assigned"/><CheckRow ok={available} label="All selected listings available"/><CheckRow ok={priced} label="Selling price set"/></div><button onClick={()=>void publish(s)} disabled={!ready && !s.is_live} className="mt-4 rounded-lg bg-cyan-500 px-3 py-2 text-xs font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">{s.is_live ? "Take offline" : "Publish segment"}</button></article>})}<p className="text-xs text-slate-500">{totalChecks} segment{totalChecks===1?"":"s"} · Live availability follows the latest captured supplier listing status.</p></div>}</section>}
      {curationQueue?.[curationQueueIndex] && <SupplierCurationModal item={curationQueue[curationQueueIndex]} index={curationQueueIndex} count={curationQueue.length} busy={busy} onClose={() => setCurationQueue(null)} onApprove={() => void approveCurationCandidate()} onNext={() => setCurationQueueIndex(index => index + 1)} />}
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

function SupplierCurationModal({ item, index, count, busy, onClose, onApprove, onNext }: {
  item: CurationCandidate; index: number; count: number; busy: boolean;
  onClose: () => void; onApprove: () => void; onNext: () => void;
}) {
  return <div role="dialog" aria-modal="true" aria-labelledby="supplier-curation-title" className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/80 p-4">
    <section className="max-h-[90dvh] w-full max-w-xl overflow-y-auto rounded-2xl border border-white/15 bg-[#0b1119] shadow-2xl">
      <header className="border-b border-white/10 px-5 py-4"><p className="text-xs font-semibold uppercase tracking-widest text-cyan-300">Supplier match review · {index + 1} of {count}</p><h2 id="supplier-curation-title" className="mt-1 text-lg font-semibold">{item.segment_label} · {SLOT_LABELS[item.slot_type] ?? item.slot_type}</h2></header>
      <div className="space-y-4 p-5"><div><ProductThumbnail src={item.image_url} fallbackSrc={item.reference_image_url} alt={item.title} large/><p className="mt-1 text-[11px] text-slate-500">{item.image_url && item.reference_image_url ? "Supplier listing photo · Amazon product reference fallback" : item.image_url ? "Supplier listing photo" : item.reference_image_url ? "Amazon product reference · supplier photo unavailable" : "No product image available"}</p></div><div className="min-w-0"><p className="font-semibold">{item.title}</p><p className="mt-2 text-sm text-slate-300">£{item.price.toFixed(2)} · {item.status}</p><p className="mt-1 text-xs text-slate-500">Last seen {item.last_seen_at ? new Date(item.last_seen_at).toLocaleDateString("en-GB") : "unknown"}</p>{item.url && <a href={item.url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-sm text-cyan-200 hover:underline">Open supplier listing <ExternalLink className="h-3.5 w-3.5"/></a>}<p className="mt-3 text-xs text-slate-400">Approving adds this supplier listing to the Curated Catalogue and allows it to be used in curated builds.</p></div></div>
      <footer className="flex justify-between gap-2 border-t border-white/10 px-5 py-4"><button type="button" disabled={busy} onClick={onClose} className="rounded-lg border border-white/15 px-3 py-2 text-sm text-slate-300 disabled:opacity-50">Close</button><div className="flex gap-2"><button type="button" disabled={busy || index >= count - 1} onClick={onNext} className="rounded-lg border border-white/15 px-3 py-2 text-sm text-slate-300 disabled:opacity-40">Skip</button><button type="button" disabled={busy} onClick={onApprove} className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-bold text-slate-950 disabled:opacity-50"><Check className="h-4 w-4"/>{index < count - 1 ? "Approve & next" : "Approve"}</button></div></footer>
    </section>
  </div>;
}

function MatchReviewModal({ match, index, count, busy, error, onClose, onPrevious, onNext, onReview }: {
  match: BestsellerMatch; index: number; count: number; busy: boolean; error: string;
  onClose: () => void; onPrevious: () => void; onNext: () => void;
  onReview: (status: BestsellerMatch["review_status"]) => void;
}) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/85 p-2 backdrop-blur-sm sm:p-5" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div role="dialog" aria-modal="true" aria-labelledby="match-review-title" className="flex h-[min(96dvh,1100px)] w-[min(96vw,1800px)] min-w-0 flex-col overflow-hidden rounded-2xl border border-white/15 bg-[#0b1119] shadow-2xl">
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-white/10 px-4 py-3 sm:px-6">
        <div className="min-w-0"><p className="text-xs font-semibold uppercase tracking-widest text-cyan-300">Match review · {index + 1} of {count}</p><h2 id="match-review-title" className="truncate text-base font-semibold sm:text-xl">{CATEGORY_LABELS[match.category] ?? match.category} · Amazon rank #{match.rank}</h2></div>
        <div className="flex shrink-0 items-center gap-2"><Badge tone={match.review_status === "approved" ? "green" : match.review_status === "rejected" ? "red" : "amber"}>{match.review_status}</Badge><button type="button" onClick={onClose} aria-label="Close comparison" className="rounded-lg border border-white/10 p-2 text-slate-300 hover:bg-white/10"><X className="h-5 w-5" /></button></div>
      </header>
      <div className="grid min-h-0 min-w-0 flex-1 grid-cols-1 gap-px overflow-y-auto bg-white/10 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:overflow-hidden">
        <MatchImagePanel key={`amazon-${match.asin}`} label="Amazon bestseller" title={match.title} price={match.price} imageUrl={match.image_url} url={match.url} detail={`ASIN ${match.asin}`} />
        <MatchImagePanel key={`market-${match.marketplace_listing_id}`} label={match.marketplace_image_is_reference ? `${match.marketplace_source} · product reference photo` : match.marketplace_is_self_capture ? "Amazon bestseller capture · ASIN self-match" : `${match.marketplace_source} listing`} title={match.marketplace_title} price={match.marketplace_price} imageUrl={match.marketplace_image_url} url={match.marketplace_url} detail={match.marketplace_condition ?? "Condition unknown"} />
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
  return <div className="relative flex min-h-[360px] min-w-0 flex-col overflow-hidden bg-white md:min-h-0">
    <div className="absolute left-4 top-4 z-10 rounded-full bg-slate-950/85 px-3 py-1.5 text-xs font-bold uppercase tracking-wide text-white shadow-lg">{label}</div>
    {imageUrl && !failed ? <img src={imageUrl} alt={title} onError={() => setFailed(true)} className="min-h-0 h-full w-full flex-1 object-contain p-4 pb-28" /> : <div className="flex flex-1 flex-col items-center justify-center gap-3 text-slate-500"><ImageIcon className="h-12 w-12" /><span className="text-sm">Picture unavailable</span></div>}
    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950 via-slate-950/95 to-transparent px-5 pb-5 pt-14 text-white sm:px-7">
      <p className="line-clamp-3 text-base font-semibold leading-snug sm:text-lg">{title}</p>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-2"><div><p className="text-2xl font-bold">{price == null ? "Price unavailable" : `£${price.toFixed(2)}`}</p><p className="text-xs text-slate-300">{detail}</p></div>{url && <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-md border border-white/20 bg-slate-900/80 px-2.5 py-1.5 text-xs font-semibold hover:bg-slate-800">Open listing<ExternalLink className="h-3.5 w-3.5" /></a>}</div>
    </div>
  </div>;
}

function Empty({title,text}:{title:string;text:string}) { return <div className="rounded-xl border border-dashed border-white/10 bg-white/[.02] px-6 py-12 text-center"><Cpu className="mx-auto h-8 w-8 text-slate-600"/><p className="mt-3 font-semibold text-slate-300">{title}</p><p className="mt-1 text-sm text-slate-500">{text}</p></div>; }
function ProductThumbnail({ src, alt, large = false, fallbackSrc }: { src?: string | null; alt: string; large?: boolean; fallbackSrc?: string | null }) {
  const [failed, setFailed] = useState(false);
  const [fallbackFailed, setFallbackFailed] = useState(false);
  useEffect(() => { setFailed(false); setFallbackFailed(false); }, [src, fallbackSrc]);
  const size = large ? "h-36 w-full" : "h-16 w-16";
  const imageSrc = failed ? fallbackSrc : src ?? fallbackSrc;
  const imageFailed = fallbackFailed && (failed || !src);
  return <div className={`flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-white/10 bg-white ${size}`}>
    {imageSrc && !imageFailed ? <img src={imageSrc} alt={alt} loading="lazy" onError={() => { if (!failed && src && fallbackSrc && fallbackSrc !== src) setFailed(true); else setFallbackFailed(true); }} className="h-full w-full object-contain" /> : <ImageIcon aria-label="Image unavailable" className="h-6 w-6 text-slate-400" />}
  </div>;
}
function Badge({children,tone,title}:{children:ReactNode;tone:"green"|"red"|"amber";title?:string}) { return <span title={title} aria-label={title} tabIndex={title ? 0 : undefined} className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${tone==="green"?"border-emerald-400/20 bg-emerald-400/10 text-emerald-300":tone==="red"?"border-rose-400/20 bg-rose-400/10 text-rose-300":"border-amber-400/20 bg-amber-400/10 text-amber-300"}`}>{children}</span>; }
function AvailabilityBadge({segment,plannedCount}:{segment:Segment;plannedCount:number}) {
  const assigned = Object.entries(segment.components ?? {});
  const resolvedCount = assigned.filter(([slot]) => Boolean(segment.component_details?.[slot])).length;
  const unavailable = assigned.filter(([slot]) => segment.component_details?.[slot]?.status !== "active");
  if (segment.availability_status === "not_configured" || assigned.length === 0) {
    return plannedCount > 0
      ? <Badge tone="amber" title={`The Playbook has ${plannedCount} planned parts, but none are linked to supplier catalogue listings yet. Stock is unknown.`}>Not sourced</Badge>
      : <Badge tone="amber" title="No planned parts or supplier listings are assigned to this build segment.">Not configured</Badge>;
  }
  if (assigned.length !== plannedCount || resolvedCount !== assigned.length) {
    const unknownCount = Math.max(0, plannedCount - resolvedCount);
    return <Badge tone="amber" title={`${resolvedCount} of ${plannedCount} stock-tracked parts have resolved catalogue listings. Stock for the remaining parts is unknown.`}>Partially sourced</Badge>;
  }
  if (segment.availability_status === "out_of_stock") {
    const details = unavailable.map(([slot]) => {
      const component = segment.component_details?.[slot];
      return `${SLOT_LABELS[slot] ?? slot}: ${component?.title ?? "selected listing unavailable"} (${component?.status ?? "not found"})`;
    });
    const title = details.length ? `Unavailable components: ${details.join("; ")}` : "One or more selected component listings are unavailable.";
    return <Badge tone="red" title={title}>Out of stock</Badge>;
  }
  return <Badge tone="green">In stock</Badge>;
}
function PlannedPartsDisclosure({segment,build,matches}:{
  segment:Segment;
  build?:DraftBuild;
  matches:BestsellerMatch[];
}) {
  const planned = build?.core_components ?? [];
  const linked = Object.values(segment.component_details ?? {}).filter((component): component is Component => Boolean(component));
  const assignedCount = Object.keys(segment.components ?? {}).length;
  if (planned.length === 0 && linked.length === 0 && assignedCount === 0) return <span>No components assigned</span>;
  const summary = planned.length > 0
    ? `${planned.length} planned · ${linked.length} linked`
    : `${assignedCount} assigned component${assignedCount === 1 ? "" : "s"}`;
  return <details className="text-xs">
    <summary className="cursor-pointer text-cyan-200 hover:text-cyan-100">{summary}</summary>
    {planned.length > 0 && <div className="mt-2 space-y-3"><p className="font-medium text-slate-300">Playbook plan · indicative costs</p>{planned.map((part, index) => {
      const slot = DRAFT_CATEGORY_SLOT[part.category];
      const partKey = `${part.category}-${part.sku_name}-${index}`;
      if (slot === "os") return <div key={partKey} className="rounded-md border border-white/5 bg-white/[.02] p-2"><p className="text-slate-300">{part.category}: {part.sku_name}</p><p className="mt-1 text-[11px] text-slate-500">Software choice is managed in The Playbook tab; it is not supplier stock.</p></div>;
      const selectedListing = slot ? segment.component_details?.[slot] : undefined;
      const identity = slot ? segment.bestseller_components?.[slot] : undefined;
      const amazonProduct = identity ? matches.find(match => match.category === identity.category && match.cpk === identity.cpk) : undefined;
      return <div key={partKey} className="rounded-md border border-white/5 bg-white/[.02] p-2">
        <p className="text-slate-300">{part.category}: {part.sku_name} <span className="text-slate-500">· indicative £{part.cost_gbp.toLocaleString("en-GB")}</span></p>
        {!slot ? <p className="mt-1 text-amber-300">No catalogue slot mapping exists for this draft category.</p> : slot === "os" ? null : <p className="mt-1 text-[11px] text-slate-500">Amazon ASIN: {amazonProduct?.asin ?? "not found"} · CPK: {identity?.cpk ?? "not assigned"}</p>}
        {selectedListing ? <p className={`mt-1 text-[11px] ${selectedListing.status === "active" ? "text-emerald-300" : "text-amber-300"}`}>
          Matched supplier listing: {selectedListing.title} · £{selectedListing.price.toFixed(2)} · {selectedListing.status}{selectedListing.curated_for_builds ? " · curated" : " · needs Curated approval before publishing"}
        </p> : slot !== "os" && <p className="mt-1 text-[11px] text-amber-300">No active curated supplier listing matched this Amazon identity yet.</p>}
      </div>;
    })}</div>}
    {linked.length > 0 && <div className="mt-2"><p className="font-medium text-slate-300">Linked supplier listings</p><ul className="mt-1 space-y-1 text-slate-400">{linked.map(component => <li key={component.id}>{component.title} · {component.status}</li>)}</ul></div>}
    {assignedCount > linked.length && <p className="mt-2 text-amber-300">{assignedCount - linked.length} assigned listing link{assignedCount - linked.length === 1 ? "" : "s"} could not be found in the catalogue.</p>}
  </details>;
}
function Toggle({checked,onClick}:{checked:boolean;onClick:()=>void}) { return <button type="button" role="switch" aria-checked={checked} onClick={onClick} className={`relative h-6 w-11 rounded-full transition ${checked?"bg-cyan-400":"bg-slate-700"}`}><span className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${checked?"left-6":"left-1"}`}/></button>; }
function CheckRow({ok,label}:{ok:boolean;label:string}) { return <div className={`flex items-center gap-2 ${ok?"text-emerald-300":"text-amber-300"}`}>{ok?<Check className="h-4 w-4"/>:<AlertCircle className="h-4 w-4"/>}{label}</div>; }

function compactPart(title: string | undefined, slot: "cpu" | "gpu" | "ram" | "storage"): string {
  if (!title) return "Pending";
  if (slot === "cpu") return title.match(/\b(?:\d{4,5}(?:X3D|X|G|WX)?|(?:250|270)K Plus)\b/i)?.[0] ?? title.slice(0, 24);
  if (slot === "gpu") return title.match(/\b(?:RTX\s*\d{4}(?:\s*Ti)?|RX\s*\d{4}(?:\s*XT)?|Arc\s*B580|R9700)\b/i)?.[0] ?? title.slice(0, 24);
  if (slot === "ram") return `${title.match(/\b(?:16|32|64|96|128|256)GB\b/i)?.[0] ?? "RAM"} ${title.match(/\b(?:LPDDR[345]X?|DDR[345])\b/i)?.[0] ?? ""}`.trim();
  return title.match(/\b(?:512GB|1TB|2TB|4TB|8TB)\b/i)?.[0] ?? title.slice(0, 20);
}

function PlaybookGrid({ builds, segments, matches, selectedId, onSelect }: { builds: DraftBuild[]; segments: Segment[]; matches: BestsellerMatch[]; selectedId: number | null; onSelect: (id: number) => void }) {
  const types = [...new Set(builds.map(build => build.customer_type))];
  const tiers = ["Budget", "Mid-range", "High-end"];
  const byProduct = new Map(matches.map(match => [`${match.category}:${match.cpk}`, match]));
  return <section aria-label="Playbook build grid">
    <div className="mb-3 flex flex-wrap items-end justify-between gap-2"><div><h2 className="text-xl font-semibold">The Playbook</h2><p className="text-xs text-slate-400">{types.length} customer types · 24 bestseller based builds · select a cell for all components</p></div><p className="text-[11px] text-slate-500">Prices shown are Amazon component snapshots, not selling prices.</p></div>
    {builds.length === 0 ? <Empty title="No playbook builds loaded" text="The playbook could not be loaded." /> : <div className="overflow-x-auto rounded-xl border border-white/10 bg-[#101924]">
      <div className="min-w-[1050px]"><div className="grid grid-cols-[155px_repeat(3,minmax(0,1fr))] bg-[#14202d] text-xs font-semibold uppercase tracking-wide text-slate-300"><div className="px-3 py-2">Customer type</div>{tiers.map(tier => <div key={tier} className="border-l border-white/10 px-3 py-2">{tier}</div>)}</div>
        {types.map(type => <div key={type} className="grid grid-cols-[155px_repeat(3,minmax(0,1fr))] border-t border-white/10"><h3 className="flex items-center px-3 text-xs font-semibold text-cyan-200">{type}</h3>{tiers.map(tier => {
          const build = builds.find(item => item.customer_type === type && item.budget_tier === tier);
          const segment = segments.find(item => item.customer_type === type && item.budget_level === tier);
          if (!build) return <div key={tier} className="border-l border-white/10 px-3 py-2 text-xs text-slate-500">No build</div>;
          const refs = segment?.bestseller_components ?? {};
          const product = (slot: string) => { const ref = refs[slot]; return ref ? byProduct.get(`${ref.category}:${ref.cpk}`) : undefined; };
          const integrated = /integrated/i.test(build.core_components.find(item => item.category === "Graphics")?.sku_name ?? "");
          const memorySpec = build.core_components.find(item => item.category === "Memory")?.sku_name;
          const memoryLabel = compactPart(memorySpec ?? product("ram")?.title, "ram");
          const selected = Object.keys(refs).length;
          const subtotal = Object.values(refs).reduce((sum, ref) => sum + (byProduct.get(`${ref.category}:${ref.cpk}`)?.price ?? 0), 0);
          const unpriced = Object.values(refs).some(ref => byProduct.get(`${ref.category}:${ref.cpk}`)?.price == null);
          return <button key={tier} type="button" onClick={() => segment && onSelect(segment.id)} disabled={!segment} aria-label={`${build.name}, ${type}, ${tier}, ${memoryLabel} memory, ${selected} products selected; open build details`} className={`min-h-[76px] border-l border-white/10 px-3 py-2 text-left transition hover:bg-white/[.06] disabled:cursor-default ${selectedId === segment?.id ? "bg-cyan-400/[.08]" : ""}`}>
            <div className="flex items-baseline justify-between gap-2"><span className="text-sm font-semibold text-white">{build.name}</span><span className="whitespace-nowrap text-xs font-semibold text-cyan-200">{selected ? `£${Math.round(subtotal).toLocaleString()}${unpriced ? "+" : ""}` : "—"}</span></div>
            <p className="mt-1 truncate text-[11px] text-slate-300">CPU {compactPart(product("cpu")?.title, "cpu")} · GPU {integrated ? "integrated" : compactPart(product("gpu")?.title, "gpu")}</p>
            <p className="truncate text-[11px] text-slate-400"><span className="font-semibold text-cyan-200">RAM {memoryLabel}</span> · SSD {compactPart(product("storage")?.title, "storage")} <span className="text-emerald-300">· {selected}/{integrated ? 7 : 8}</span></p>
          </button>;
        })}</div>)}</div></div>}
  </section>;
}

function ReviewedBestsellerChoices({ segment, build, matches, components, onSave }: {
  segment: Segment; build?: DraftBuild; matches: BestsellerMatch[]; components: Component[];
  onSave: (segment: Partial<Segment> & { customer_type: string; budget_level: string }) => Promise<void>;
}) {
  const slotCategory: Record<string, string> = { cpu: "cpu", gpu: "gpu", motherboard: "motherboard", ram: "ram", storage: "storage", psu: "psu", cooling: "cooler", case: "case" };
  const draftCategorySlot = DRAFT_CATEGORY_SLOT;
  const choices = segment.bestseller_components ?? {};
  const integratedGraphics = /integrated/i.test(build?.core_components.find(item => item.category === "Graphics")?.sku_name ?? "");
  const selectedMatches = Object.values(choices).map(ref => matches.find(item => item.category === ref.category && item.cpk === ref.cpk)).filter((item): item is BestsellerMatch => Boolean(item));
  const observedTotal = selectedMatches.reduce((sum, item) => sum + (item.marketplace_price ?? 0), 0);
  const upgradeCandidates = build?.upsells ?? [];
  const [upgradeSelections, setUpgradeSelections] = useState<Record<number, { cpk: string; category: string; targetVariantId: string }>>({});
  const [upgradeSuggestion, setUpgradeSuggestion] = useState("");
  useEffect(() => {
    setUpgradeSelections(Object.fromEntries((segment.approved_upgrades ?? []).map(item => [item.candidate_index, {
      cpk: item.popularity_evidence.cpk, category: item.popularity_evidence.category,
      targetVariantId: String(item.target_variant_id),
    }])));
  }, [segment.id, segment.approved_upgrades]);
  const suggestComponentOffers = () => {
    const budgetAnchor = Math.max(segment.budget_min ?? 1, 1);
    const eligible = upgradeCandidates.flatMap((item, index) => {
      const slot = draftCategorySlot[item.category];
      const category = categoryForSlot(slot ?? "");
      if (!slot || item.category === "Case") return [];
      const model = normalizeModel(item.to_sku);
      const evidence = matches.find(candidate => candidate.category === category
        && candidate.review_status === "approved"
        && candidate.rank > 0
        && normalizeModel(candidate.title).includes(model));
      const target = components.find(part => part.curated_for_builds && part.status === "active"
        && categoryForSlot(part.slot_type) === category
        && normalizeModel(part.title).includes(model));
      if (!evidence || !target) return [];
      const basePrice = segment.component_details[slot]?.price;
      const priceIncrease = Math.max(0, target.price - (basePrice ?? target.price));
      const popularityScore = 1 / (1 + Math.log10(evidence.rank));
      const pricePointScore = 1 / (1 + priceIncrease / budgetAnchor);
      return [{
        index,
        category,
        cpk: evidence.cpk,
        targetVariantId: String(target.id),
        rank: evidence.rank,
        priceIncrease,
        score: (popularityScore + pricePointScore) / 2,
        label: `${item.category}: ${item.to_sku}`,
      }];
    }).sort((left, right) => right.score - left.score || left.index - right.index);
    if (!eligible.length) {
      setUpgradeSuggestion("No component upgrade currently has both approved exact-model popularity evidence and an active curated target.");
      return;
    }
    setUpgradeSelections(Object.fromEntries(eligible.map(candidate => [candidate.index, {
      cpk: candidate.cpk,
      category: candidate.category,
      targetVariantId: candidate.targetVariantId,
    }])));
    setUpgradeSuggestion(`Found ${eligible.length} component offer(s): ${eligible.map(candidate => `${candidate.label} (Amazon #${candidate.rank}, about £${candidate.priceIncrease.toFixed(2)} above the current catalogue default)`).join("; ")}. Review each evidence match and catalogue target before saving.`);
  };
  return <section className="rounded-xl border border-emerald-400/20 bg-[#101924] p-5">
    <h2 className="text-lg font-semibold">Playbook defaults and cell upgrades</h2>
    <p className="mt-1 text-sm text-slate-400">Choose reviewed offers by component. Customers will see the Playbook default alongside every offer approved here; offers require an approved exact-model bestseller match and an active curated catalogue target.</p>
    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">{Object.entries(slotCategory).map(([slot, category]) => {
      if (slot === "gpu" && integratedGraphics) return <div key={slot} className="space-y-1.5 text-xs text-slate-400">GPU<div className="rounded-lg border border-white/10 bg-[#0b1119] px-3 py-2.5 text-sm text-emerald-200">Integrated with CPU</div></div>;
      const ref = choices[slot];
      const current = ref ? matches.find(item => item.category === ref.category && item.cpk === ref.cpk) : undefined;
      const core = build?.core_components.find(item => draftCategorySlot[item.category] === slot);
      return <div key={slot} className="space-y-1.5 text-xs text-slate-400"><h3 className="font-medium">{SLOT_LABELS[slot]}</h3>
        <div className="rounded-lg border border-cyan-400/20 bg-[#0b1119] p-3"><p className="text-[10px] font-semibold uppercase tracking-wider text-cyan-300">Default</p><p className="mt-1 line-clamp-2 text-sm font-medium text-white">{current?.title ?? core?.sku_name ?? "No default assigned"}</p><p className="mt-1 text-xs text-slate-400">{current ? `Amazon match · ${current.marketplace_price == null ? "price unavailable" : `£${current.marketplace_price.toFixed(2)}`}` : "Marketplace match pending"}</p></div>
      </div>;
    })}</div>
    <div className="mt-4 rounded-lg border border-violet-400/20 bg-violet-400/[.04] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="font-semibold text-violet-200">Component offer review</h3><span className="text-xs text-slate-400">{upgradeCandidates.length} draft possibilities · {Object.keys(upgradeSelections).length} selected</span></div><button type="button" onClick={suggestComponentOffers} disabled={!upgradeCandidates.length} className="rounded border border-violet-300/40 px-3 py-1.5 text-xs text-violet-200 disabled:opacity-40">Find available offers</button></div>
      <p className="mt-2 text-[11px] leading-5 text-slate-400">This selects every draft possibility with an approved exact-model bestseller match and an active curated target. The selection is not saved or published until you review and save it below.</p>
      {upgradeSuggestion && <p role="status" className="mt-2 rounded border border-violet-300/20 bg-violet-300/5 p-2 text-xs text-violet-100">{upgradeSuggestion}</p>}
      {upgradeCandidates.length ? <div className="mt-3 space-y-2">{upgradeCandidates.map((item, index) => {
        const category = categoryForSlot(draftCategorySlot[item.category] ?? "");
        const targets = item.category === "Case" ? [] : components.filter(part => part.curated_for_builds && part.status === "active" && categoryForSlot(part.slot_type) === category && normalizeModel(part.title).includes(normalizeModel(item.to_sku)));
        const match = matches.filter(candidate => candidate.category === category && candidate.review_status === "approved")
          .find(candidate => normalizeModel(candidate.title).includes(normalizeModel(item.to_sku)));
        const picked = upgradeSelections[index];
        return <label key={`${item.category}-${item.to_sku}-${index}`} className="block rounded-md border border-white/10 bg-[#0b1119] p-3 text-sm"><span className="flex items-start gap-2"><input type="checkbox" disabled={item.category === "Case"} checked={Boolean(picked)} onChange={event => setUpgradeSelections(current => {
          const next = { ...current };
          if (event.target.checked) next[index] = { cpk: match?.cpk ?? "", category, targetVariantId: String(targets[0]?.id ?? "") };
          else delete next[index];
          return next;
        })}/><span><span className="font-medium text-white">{item.category}: {item.from_sku} → {item.to_sku}</span><span className="mt-1 block text-xs text-slate-400">Estimated component cost Δ £{item.delta_cost_gbp.toFixed(0)} · choose a verified popularity match and an active curated catalogue target.</span></span></span>
          {picked && <span className="mt-2 grid gap-2 sm:grid-cols-2"><select aria-label={`${item.to_sku} curated target component`} value={picked.targetVariantId} onChange={event => setUpgradeSelections(current => ({ ...current, [index]: { ...current[index], targetVariantId: event.target.value } }))} className="rounded border border-white/10 bg-[#111a26] p-2 text-xs"><option value="">Choose active curated catalogue target</option>{targets.map(target => <option key={target.id} value={target.id}>{target.title} · £{target.price.toFixed(2)}</option>)}</select><select aria-label={`${item.to_sku} bestseller evidence`} value={picked.cpk} onChange={event => setUpgradeSelections(current => ({ ...current, [index]: { ...current[index], cpk: event.target.value } }))} className="rounded border border-white/10 bg-[#111a26] p-2 text-xs"><option value="">Choose approved exact-model bestseller</option>{matches.filter(candidate => candidate.category === category && candidate.review_status === "approved" && normalizeModel(candidate.title).includes(normalizeModel(item.to_sku))).map(candidate => <option key={candidate.cpk} value={candidate.cpk}>#{candidate.rank} · {candidate.title} · {candidate.marketplace_price == null ? "price unavailable" : `£${candidate.marketplace_price.toFixed(2)}`}</option>)}</select></span>}
        </label>;
      })}</div> : <p className="mt-2 text-sm text-slate-400">No upgrade possibilities are present in this draft.</p>}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-slate-400">Save the reviewed component offers. Publishing requires an approved offer for each component category with a drafted upgrade. Checkout validates the selected active catalogue item and uses its current price.{segment.is_live ? " Unpublish this cell before removing saved offers." : ""}</p><div className="flex gap-2"><button type="button" disabled={segment.is_live || !segment.approved_upgrades?.length} onClick={() => void onSave({ ...segment, approved_upgrades: [] })} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 disabled:opacity-50">Remove saved offers</button><button type="button" disabled={!Object.keys(upgradeSelections).length || Object.values(upgradeSelections).some(item => !item.cpk || !item.targetVariantId)} onClick={() => void onSave({ ...segment, approved_upgrades: Object.entries(upgradeSelections).map(([candidate_index, item]) => ({ candidate_index: Number(candidate_index), popularity_cpk: item.cpk, evidence_category: item.category, target_variant_id: Number(item.targetVariantId) })) as unknown as ApprovedUpgrade[] })} className="rounded-lg bg-violet-400 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50">Save reviewed offers</button></div></div>
    </div>
    <p className="mt-4 text-xs text-amber-300">{selectedMatches.length}/{integratedGraphics ? 7 : 8} hardware defaults selected · marketplace comparison total £{observedTotal.toFixed(2)}. Compatibility, delivery, procurement cost and PricingBot selling price still need validation before launch.</p>
  </section>;
}


function FlipMatchPanel({ segment }: { segment: Segment }) {
  const [deliveryMode, setDeliveryMode] = useState<"flexible" | "ready_to_ship">("flexible");
  const [matches, setMatches] = useState<Array<{ flip_id: number; title: string; url: string; stage: string; meets_measured_requirements: boolean; checks: Array<{ slot: string; status: string; target_score?: number; candidate_score?: number }> }>>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const findMatches = async (mode: "flexible" | "ready_to_ship") => {
    setDeliveryMode(mode); setBusy(true); setError("");
    try {
      const response = await fetch(`/api/curated-builds/segments/${segment.id}/flip-matches?delivery_mode=${mode}`, { cache: "no-store" });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not match potential flips");
      setMatches(data.matches ?? []);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not match potential flips"); }
    finally { setBusy(false); }
  };
  return <section className="mb-4 rounded-lg border border-amber-300/20 bg-amber-300/[.03] p-3">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-sm font-semibold">Potential flip sourcing</h3><p className="mt-1 text-xs text-slate-400">Benchmark and budget fit is a sourcing suggestion; check remaining components before allocating inventory.</p></div>
      <div className="flex gap-2"><button type="button" disabled={busy || !segment.allow_flip_component_sources} onClick={() => void findMatches("flexible")} className={`rounded border px-3 py-1.5 text-xs ${deliveryMode === "flexible" ? "border-cyan-300/50 text-cyan-100" : "border-white/10 text-slate-300"}`}>Flexible</button><button type="button" disabled={busy || !segment.allow_flip_component_sources} onClick={() => void findMatches("ready_to_ship")} className={`rounded border px-3 py-1.5 text-xs ${deliveryMode === "ready_to_ship" ? "border-cyan-300/50 text-cyan-100" : "border-white/10 text-slate-300"}`}>Ready-to-Ship</button></div>
    </div>
    {!segment.allow_flip_component_sources && <p className="mt-2 text-xs text-slate-500">Enable flip sources above to run the matcher.</p>}
    {busy && <p className="mt-2 text-xs text-cyan-200">Checking benchmark and budget fit…</p>}{error && <p role="alert" className="mt-2 text-xs text-red-300">{error}</p>}
    {matches.length > 0 && <div className="mt-3 space-y-2">{matches.map(match => <article key={match.flip_id} className="rounded border border-white/10 bg-black/20 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><a className="text-sm font-medium text-cyan-200 underline" href={match.url} target="_blank" rel="noreferrer">{match.title}</a><span className={`text-xs ${match.meets_measured_requirements ? "text-emerald-300" : "text-amber-300"}`}>{match.meets_measured_requirements ? "Performance + budget fit" : "Review required"}</span></div><p className="mt-2 text-xs text-slate-400">Flip #{match.flip_id} · {match.stage.replaceAll("_", " ")} · {match.checks.map(check => `${check.slot}: ${check.status}${check.candidate_score != null && check.target_score != null ? ` (${check.candidate_score} / ${check.target_score})` : ""}`).join(" · ")}</p></article>)}</div>}
    {!busy && !error && matches.length === 0 && segment.allow_flip_component_sources && <p className="mt-2 text-xs text-slate-500">Run the matcher to see potential flip candidates.</p>}
  </section>;
}
