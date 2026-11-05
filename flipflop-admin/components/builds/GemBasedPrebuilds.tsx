"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ExternalLink, Loader2, Save, X } from "lucide-react";
import { api } from "@/lib/api";

interface GemData {
  id: number;
  title: string;
  price: number;
  seller?: string;
  condition?: string | null;
  source?: string | null;
  url: string;
  image_url?: string | null;
  cpu?: string | null;
  category?: string;
  classification?: "SUPER_GEM" | "GEM";
  deal_score?: number;
  market_reference?: number | null;
  market_median_price?: number | null;
  expected_profit?: number | null;
  performance_percentile?: number | null;
  desirability_score?: number | null;
  liquidity_score?: number | null;
  watch_count?: number | null;
  bid_count?: number | null;
}

type GemBuildConceptKey = "best" | "cheapest" | "highest_end" | "most_profitable" | "most_popular";

interface GemBuildConcept {
  title: string;
  gems: Record<string, GemData | null>;
  metrics: {
    parts_total?: number;
    component_profit_signal?: number;
    component_profit_evidence_count?: number;
    market_reference_total?: number | null;
    popularity_signal?: number;
    listing_watch_count?: number;
    listing_bid_count?: number;
    performance_percentile?: number;
  };
}

interface GemSpotlightData {
  builds: Record<GemBuildConceptKey, GemBuildConcept>;
}

const componentOrder = ["motherboard", "cpu", "cooler", "ram", "gpu", "ssd", "psu", "case"];
const componentLabels: Record<string, string> = {
  motherboard: "Motherboard",
  cpu: "CPU",
  cooler: "CPU cooler",
  ram: "Memory",
  gpu: "GPU",
  ssd: "Storage",
  psu: "Power supply",
  case: "PC case",
};

const concepts: { key: GemBuildConceptKey; title: string; description: string; signal: string }[] = [
  { key: "best", title: "Top Deal Score Concept", description: "Selected from the available Gems by their overall deal scores.", signal: "Overall Gem deal score" },
  { key: "cheapest", title: "Lowest Parts Cost Concept", description: "The available Gem set with the lowest combined asking price.", signal: "Lowest parts total" },
  { key: "highest_end", title: "Highest Benchmark Tier Concept", description: "Highest known CPU/GPU benchmark tier, with component specs considered where benchmark data is unavailable.", signal: "CPU/GPU benchmark percentile" },
  { key: "most_profitable", title: "Combined Profit Signal Concept", description: "Selected by summed per-listing expected profit estimates. Component estimates do not guarantee whole-PC profit.", signal: "Combined component profit signal" },
  { key: "most_popular", title: "Top Demand Signal Concept", description: "Selected by combined desirability, liquidity, watch and bid signals from the chosen listings.", signal: "Observed demand signals" },
];

const accents = {
  cyan: { label: "text-cyan-300", price: "text-cyan-200", border: "ring-cyan-400/30" },
  purple: { label: "text-purple-300", price: "text-purple-200", border: "ring-purple-400/30" },
  emerald: { label: "text-emerald-300", price: "text-emerald-200", border: "ring-emerald-400/30" },
  blue: { label: "text-blue-300", price: "text-blue-200", border: "ring-blue-400/30" },
  orange: { label: "text-orange-300", price: "text-orange-200", border: "ring-orange-400/30" },
} as const;

function GemCard({ gem, label, accent, details, onSelect }: { gem: GemData | null; label: string; accent: keyof typeof accents; details?: string; onSelect: (gem: GemData) => void }) {
  const colors = accents[accent];
  if (!gem) return <div className="flex aspect-square min-w-0 flex-col justify-between rounded-xl border border-white/10 bg-white/[0.03] p-3"><span className="truncate text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</span><p className="text-xs text-slate-500">No compatible Gem</p></div>;
  const medianDifference = gem.market_median_price != null && gem.market_median_price > 0
    ? gem.price - gem.market_median_price
    : null;
  return <button type="button" onClick={() => onSelect(gem)} aria-haspopup="dialog" aria-label={`View ${label} details: ${gem.title}`} className={`group relative block aspect-square min-w-0 overflow-hidden rounded-xl text-left ring-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white ${colors.border}`}>
    {gem.image_url ? <img src={gem.image_url} alt={gem.title} className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" onError={event => { event.currentTarget.style.display = "none"; }} /> : <div className="absolute inset-0 bg-slate-800" />}
    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-black/40" />
    <span className={`absolute left-2 top-2 max-w-[calc(100%-1rem)] truncate rounded-full bg-black/50 px-2 py-1 text-[9px] font-semibold uppercase tracking-wide ${colors.label}`}>{label}</span>
    <div className="absolute inset-x-0 bottom-0 min-w-0 border-t border-white/10 bg-black/35 p-2 backdrop-blur-sm">
      <p className="truncate text-xs font-medium text-white">{gem.title}</p>
      {gem.cpu && <p className="truncate text-[10px] text-white/70">{gem.cpu}</p>}
      <div className="mt-0.5 flex items-baseline gap-1.5 whitespace-nowrap">
        <span className={`text-base font-bold ${colors.price}`}>£{gem.price.toFixed(2)}</span>
        {medianDifference != null && gem.market_median_price != null && (
          <span className="text-[10px] font-semibold text-red-300" title={`${Math.abs(medianDifference).toFixed(0)} pounds ${medianDifference > 0 ? "above" : "below"} market median`}>
            {medianDifference > 0 ? "↑" : medianDifference < 0 ? "↓" : "↔"} £{Math.abs(medianDifference).toFixed(0)} · {Math.abs((medianDifference / gem.market_median_price) * 100).toFixed(0)}%
          </span>
        )}
      </div>
      {details && <p className="truncate text-[9px] text-white/60">{details}</p>}
    </div>
  </button>;
}

export default function GemBasedPrebuilds() {
  const router = useRouter();
  const [data, setData] = useState<GemSpotlightData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState<GemBuildConceptKey | null>(null);
  const [draftError, setDraftError] = useState("");
  const [selectedGem, setSelectedGem] = useState<GemData | null>(null);

  useEffect(() => {
    if (!selectedGem) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedGem(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [selectedGem]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        let result: GemSpotlightData | null = null;
        let failure: Error | null = null;
        for (let attempt = 0; attempt < 2 && !result; attempt += 1) {
          try {
            const response = await fetch("/proxy-api/gem-radar/gem-build-concepts", { cache: "no-store", signal: AbortSignal.timeout(240_000) });
            if (!response.ok) throw new Error(`Gem build selection returned ${response.status}.`);
            result = await response.json() as GemSpotlightData;
          } catch (error) {
            failure = error instanceof Error ? error : new Error("Could not load Gem build concepts.");
            if (attempt === 0) await new Promise(resolve => setTimeout(resolve, 1500));
          }
        }
        if (!result) throw failure ?? new Error("Could not load Gem build concepts.");
        if (active) { setData(result); setLoadError(""); }
      } catch (error) {
        if (active) setLoadError(error instanceof Error ? error.message : "Could not load Gem build concepts.");
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    const interval = setInterval(load, 5 * 60_000);
    return () => { active = false; clearInterval(interval); };
  }, []);

  const money = (value: number) => new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(value);

  const createDraft = async (key: GemBuildConceptKey, concept: GemBuildConcept) => {
    const selected = componentOrder.map(category => concept.gems[category] ?? null);
    if (selected.some(gem => !gem) || saving) return;
    setSaving(key);
    setDraftError("");
    try {
      const draft = await api.manualBuilds.createGemSpotlightDraft({
        listing_ids: selected.map(gem => gem!.id),
        build_name: concept.title,
        concept: key,
      });
      router.push(`/builds?new=${draft.id}`);
    } catch (error) {
      setDraftError(error instanceof Error ? error.message : "Could not create the build draft.");
      setSaving(null);
    }
  };

  return <div className="mx-auto w-full max-w-[1600px] space-y-6 p-4 sm:p-6 lg:p-8">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <a href="/ready-to-ship" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white"><ArrowLeft className="h-4 w-4" /> Ready-to-Ship workflows</a>
        <p className="mt-5 text-xs font-semibold uppercase tracking-[.22em] text-cyan-300">Ready-to-Ship</p>
        <h1 className="mt-2 text-3xl font-bold text-white">Gem-based pre-builds</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">Five eight-part build concepts assembled from active Gem listings. Drafts remain unpaid sourcing candidates.</p>
      </div>
      <a href="/builds" className="rounded-lg border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-white/[0.06]">View current builds</a>
    </header>

    {loading && <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-5 text-sm text-slate-300"><Loader2 className="h-5 w-5 animate-spin text-cyan-300" /> Checking Gem candidates and compatibility…</div>}
    {!loading && loadError && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-950/30 p-4 text-sm text-red-200">{loadError}</div>}
    {draftError && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-950/30 p-4 text-sm text-red-200">{draftError}</div>}

    <section aria-label="Top Gems from the Best Gem Build" className="grid w-full min-w-0 grid-cols-8 gap-2">
      {componentOrder.map(category => <GemCard key={category} gem={data?.builds?.best?.gems?.[category] ?? null}
        label={componentLabels[category]} accent={category === "motherboard" || category === "ram" ? "emerald" : category === "cpu" ? "cyan" : category === "gpu" ? "purple" : category === "ssd" ? "blue" : "orange"} onSelect={setSelectedGem} />)}
    </section>

    {concepts.map(({ key, title, description, signal }) => {
      const concept = data?.builds?.[key];
      if (!concept) return null;
      const selected = componentOrder.map(category => ({ category, gem: concept.gems[category] ?? null }));
      const complete = selected.every(item => item.gem && ["GEM", "SUPER_GEM"].includes(item.gem.classification ?? ""));
      const partsTotal = concept.metrics.parts_total ?? selected.reduce((sum, item) => sum + (item.gem?.price ?? 0), 0);
      const fixedCosts = partsTotal + partsTotal * 0.10 + 20 + 15 + 6 + 0.20;
      const sellingPrice = concept.metrics.market_reference_total ?? null;
      const estimatedProfit = sellingPrice === null ? null : sellingPrice - fixedCosts - Math.ceil(sellingPrice * 0.1015 * 100) / 100;
      return <article key={key} className="rounded-2xl border border-white/10 bg-white/[0.035] p-5 shadow-lg shadow-black/20">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div><p className="text-xs font-bold uppercase tracking-wider text-emerald-300">Pre-built concept · {signal}</p><h2 className="mt-1 text-xl font-semibold text-white">{title}</h2><p className="mt-1 max-w-3xl text-sm text-slate-400">{description}</p></div>
        </div>

        <div className="mb-4 grid gap-3 rounded-xl border border-emerald-400/15 bg-emerald-400/[0.04] p-4 sm:grid-cols-3">
          <div className="rounded-lg border border-sky-300/15 bg-sky-300/[0.04] p-3">
            <p className="text-xs font-semibold text-sky-200">Estimated resale value</p>
            <p className="mt-1 text-xl font-bold text-white">{sellingPrice === null ? "Insufficient data" : money(sellingPrice)}</p>
            <p className="mt-1 text-[11px] leading-4 text-slate-400">Sum of the parts’ available market references. This is not a confirmed whole-PC sale price.</p>
          </div>
          <div className="rounded-lg border border-amber-300/15 bg-amber-300/[0.04] p-3">
            <p className="text-xs font-semibold text-amber-200">Estimated parts cost</p>
            <p className="mt-1 text-xl font-bold text-white">{money(partsTotal)}</p>
            <p className="mt-1 text-[11px] leading-4 text-slate-400">Sum of current listing asking prices; not confirmed paid cost. Buying postage is not included.</p>
          </div>
          <div className="rounded-lg border border-emerald-300/15 bg-emerald-300/[0.04] p-3">
            <p className="text-xs font-semibold text-emerald-200">Estimated profit</p>
            <p className={`mt-1 text-xl font-bold ${estimatedProfit !== null && estimatedProfit >= 0 ? "text-emerald-200" : "text-slate-400"}`}>{estimatedProfit === null ? "Insufficient data" : money(estimatedProfit)}</p>
            <p className="mt-1 text-[11px] leading-4 text-slate-400">Deducts parts asking prices, 10% parts overhead, £20 delivery, £15 insurance, £6 packaging, £0.20 fixed payment fee and a 10.15% selling fee. No separate warranty or returns reserve is included.</p>
          </div>
          {key === "most_profitable" && <p className="text-[11px] leading-4 text-slate-400 sm:col-span-3">Separate component profit signal: {concept.metrics.component_profit_signal == null ? "—" : money(concept.metrics.component_profit_signal)}. This sums individual listing-level estimates; it is not the whole-build profit shown above.</p>}
          {key === "most_popular" && <p className="text-[11px] leading-4 text-slate-400 sm:col-span-3">Demand signals for these selected listings: {concept.metrics.listing_watch_count ?? 0} watches · {concept.metrics.listing_bid_count ?? 0} bids. These are not total product demand.</p>}
          {key === "highest_end" && <p className="text-[11px] leading-4 text-slate-400 sm:col-span-3">Average matched CPU/GPU benchmark percentile: {concept.metrics.performance_percentile == null ? "unavailable" : `${concept.metrics.performance_percentile}th`}.</p>}
        </div>

        <div className="grid w-full min-w-0 grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">{selected.map(({ category, gem }) => {
          const meta = componentLabels[category];
          const details = gem
            ? `Market: ${gem.market_reference == null ? "unknown" : money(gem.market_reference)} · Profit: ${gem.expected_profit == null ? "unknown" : money(gem.expected_profit)}`
            : undefined;
          const accent = category === "motherboard" ? "emerald" : category === "cpu" ? "cyan" : category === "gpu" ? "purple" : category === "ssd" ? "blue" : "orange";
          return <GemCard key={category} gem={gem} label={meta} accent={accent} details={details} onSelect={setSelectedGem} />;
        })}</div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] pt-4">
          <p className="max-w-2xl text-xs text-slate-500">{complete ? "Creates an unpaid sourcing draft from these eight listings. It does not buy parts or publish an offer." : "An active Gem is required for each of the eight component types."}</p>
          <button type="button" onClick={() => void createDraft(key, concept)} disabled={!complete || saving !== null} className="inline-flex items-center gap-2 rounded-lg bg-emerald-400 px-4 py-2.5 text-sm font-bold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-50">
            {saving === key ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{saving === key ? "Creating draft…" : `Create ${title} draft`}
          </button>
        </div>
      </article>;
    })}
    {selectedGem && <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm" onClick={event => { if (event.target === event.currentTarget) setSelectedGem(null); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="gem-detail-title" className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/15 bg-[#0b1422] shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-white/10 p-5">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wider text-cyan-300">{componentLabels[selectedGem.category ?? ""] ?? selectedGem.category ?? "Gem component"} · {selectedGem.classification?.replaceAll("_", " ") ?? "Listing details"}</p>
            <h2 id="gem-detail-title" className="mt-1 text-lg font-bold text-white">{selectedGem.title}</h2>
          </div>
          <button type="button" autoFocus onClick={() => setSelectedGem(null)} aria-label="Close component details" className="shrink-0 rounded-md p-2 text-slate-400 hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"><X className="h-5 w-5" /></button>
        </div>
        <div className="grid gap-5 p-5 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <div className="overflow-hidden rounded-xl border border-white/10 bg-slate-900">
            {selectedGem.image_url ? <img src={selectedGem.image_url} alt={selectedGem.title} className="aspect-square w-full object-contain" /> : <div className="grid aspect-square place-items-center text-sm text-slate-500">No listing image</div>}
          </div>
          <dl className="grid content-start grid-cols-2 gap-2 text-sm">
            {[
              ["Listing price", money(selectedGem.price)],
              ["Condition", selectedGem.condition ?? "Unknown"],
              ["Seller", selectedGem.seller ?? "Unknown"],
              ["Source", selectedGem.source ?? "Unknown"],
              ["Market median", selectedGem.market_median_price == null ? "Unavailable" : money(selectedGem.market_median_price)],
              ["Market reference", selectedGem.market_reference == null ? "Unavailable" : money(selectedGem.market_reference)],
              ["Expected profit signal", selectedGem.expected_profit == null ? "Unavailable" : money(selectedGem.expected_profit)],
              ["Deal score", selectedGem.deal_score == null ? "Unavailable" : selectedGem.deal_score.toFixed(1)],
              ["CPU/GPU benchmark", selectedGem.performance_percentile == null ? "Unavailable" : `${selectedGem.performance_percentile.toFixed(1)}th percentile`],
              ["Watches · bids", `${selectedGem.watch_count ?? "—"} · ${selectedGem.bid_count ?? "—"}`],
              ["Demand scores", `Desirability ${selectedGem.desirability_score == null ? "—" : selectedGem.desirability_score.toFixed(0)} · liquidity ${selectedGem.liquidity_score == null ? "—" : selectedGem.liquidity_score.toFixed(0)}`],
            ].map(([label, value]) => <div key={label} className="rounded-lg border border-white/[0.07] bg-white/[0.03] p-3">
              <dt className="text-[11px] text-slate-500">{label}</dt><dd className="mt-1 break-words font-semibold text-slate-100">{value}</dd>
            </div>)}
          </dl>
        </div>
        {selectedGem.url && <div className="flex justify-end border-t border-white/10 p-4">
          <a href={selectedGem.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-200 hover:bg-cyan-400/10">View original listing <ExternalLink className="h-4 w-4" /></a>
        </div>}
      </div>
    </div>}
  </div>;
}
