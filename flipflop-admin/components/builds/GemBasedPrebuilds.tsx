"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Box, CircuitBoard, Cpu, Fan, Gem, HardDrive, Loader2, MemoryStick, Save, Zap } from "lucide-react";
import { api } from "@/lib/api";

interface GemData {
  id: number;
  title: string;
  price: number;
  seller?: string;
  condition: string;
  url: string;
  image_url?: string | null;
  cpu?: string | null;
  category?: string;
  classification?: "SUPER_GEM" | "GEM";
  deal_score?: number;
  market_reference?: number | null;
  expected_profit?: number | null;
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
const componentLabels: Record<string, { label: string; icon: typeof Cpu }> = {
  motherboard: { label: "Motherboard", icon: CircuitBoard },
  cpu: { label: "CPU", icon: Cpu },
  cooler: { label: "CPU cooler", icon: Fan },
  ram: { label: "Memory", icon: MemoryStick },
  gpu: { label: "GPU", icon: CircuitBoard },
  ssd: { label: "Storage", icon: HardDrive },
  psu: { label: "Power supply", icon: Zap },
  case: { label: "PC case", icon: Box },
};

const concepts: { key: GemBuildConceptKey; title: string; description: string; signal: string }[] = [
  { key: "best", title: "The Best Gem Build", description: "Highest-ranked overall Gem set by deal score.", signal: "Overall Gem deal score" },
  { key: "cheapest", title: "The Cheapest Gem Build", description: "Lowest total asking price among available Gem listings.", signal: "Lowest parts total" },
  { key: "highest_end", title: "The Highest-end Gem Build", description: "Highest known CPU/GPU benchmark tier, with component specs considered where benchmark data is unavailable.", signal: "CPU/GPU benchmark percentile" },
  { key: "most_profitable", title: "The Most Profitable Gem Build", description: "Highest combined per-listing expected profit from available Gem market evidence.", signal: "Combined component profit signal" },
  { key: "most_popular", title: "The Most Popular Gem Build", description: "Highest combined desirability, liquidity, watch and bid signals from the selected listings.", signal: "Observed demand signals" },
];

const accents = {
  cyan: { label: "text-cyan-300", price: "text-cyan-200", border: "ring-cyan-400/30" },
  purple: { label: "text-purple-300", price: "text-purple-200", border: "ring-purple-400/30" },
  emerald: { label: "text-emerald-300", price: "text-emerald-200", border: "ring-emerald-400/30" },
  blue: { label: "text-blue-300", price: "text-blue-200", border: "ring-blue-400/30" },
  orange: { label: "text-orange-300", price: "text-orange-200", border: "ring-orange-400/30" },
} as const;

function GemCard({ gem, label, accent }: { gem: GemData | null; label: string; accent: keyof typeof accents }) {
  const colors = accents[accent];
  if (!gem) return <div className="flex aspect-square min-w-0 flex-col justify-between rounded-xl border border-white/10 bg-white/[0.03] p-3"><span className="truncate text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</span><p className="text-xs text-slate-500">No compatible Gem</p></div>;
  return <a href={gem.url} target="_blank" rel="noopener noreferrer" className={`group relative block aspect-square min-w-0 overflow-hidden rounded-xl ring-1 ${colors.border}`}>
    {gem.image_url ? <img src={gem.image_url} alt={gem.title} className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" onError={event => { event.currentTarget.style.display = "none"; }} /> : <div className="absolute inset-0 bg-slate-800" />}
    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-black/40" />
    <span className={`absolute left-2 top-2 max-w-[calc(100%-1rem)] truncate rounded-full bg-black/50 px-2 py-1 text-[9px] font-semibold uppercase tracking-wide ${colors.label}`}>{label}</span>
    <div className="absolute inset-x-0 bottom-0 min-w-0 border-t border-white/10 bg-black/35 p-2 backdrop-blur-sm">
      <p className="truncate text-xs font-medium text-white">{gem.title}</p>
      {gem.cpu && <p className="truncate text-[10px] text-white/70">{gem.cpu}</p>}
      <p className={`mt-0.5 text-base font-bold ${colors.price}`}>£{gem.price.toFixed(2)}</p>
    </div>
  </a>;
}

export default function GemBasedPrebuilds() {
  const router = useRouter();
  const [data, setData] = useState<GemSpotlightData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState<GemBuildConceptKey | null>(null);
  const [draftError, setDraftError] = useState("");

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
        label={componentLabels[category].label} accent={category === "motherboard" ? "emerald" : category === "cpu" ? "cyan" : category === "gpu" ? "purple" : category === "ssd" ? "blue" : "orange"} />)}
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
          <div className="text-right"><p className="text-xs text-slate-400">Estimated parts total</p><p className="text-xl font-bold text-emerald-200">{money(partsTotal)}</p><p className="text-[11px] text-slate-500">Asking prices · not paid cost</p></div>
        </div>

        <div className="mb-4 grid gap-3 rounded-xl border border-emerald-400/15 bg-emerald-400/[0.04] p-4 sm:grid-cols-2">
          <div><p className="text-xs text-slate-400">Estimated resale value from component evidence</p><p className="text-lg font-bold text-white">{sellingPrice === null ? "Insufficient listing data" : money(sellingPrice)}</p></div>
          <div><p className="text-xs text-slate-400">Estimated profit after costs and reserves</p><p className={`text-lg font-bold ${estimatedProfit !== null && estimatedProfit >= 0 ? "text-emerald-200" : "text-slate-500"}`}>{estimatedProfit === null ? "Insufficient listing data" : money(estimatedProfit)}</p></div>
          {key === "most_profitable" && <p className="text-[11px] text-slate-500 sm:col-span-2">Combined Gem market profit signal: {concept.metrics.component_profit_signal == null ? "—" : money(concept.metrics.component_profit_signal)} · listing-level estimate, not guaranteed whole-PC profit.</p>}
          {key === "most_popular" && <p className="text-[11px] text-slate-500 sm:col-span-2">Listing signals: {concept.metrics.listing_watch_count ?? 0} watches · {concept.metrics.listing_bid_count ?? 0} bids. These reflect the selected listings, not total product demand.</p>}
          {key === "highest_end" && <p className="text-[11px] text-slate-500 sm:col-span-2">Average matched CPU/GPU benchmark percentile: {concept.metrics.performance_percentile == null ? "unavailable" : `${concept.metrics.performance_percentile}th`}.</p>}
          <p className="text-[11px] leading-relaxed text-slate-500 sm:col-span-2">Resale value sums each listing’s available market reference; it is not a confirmed whole-PC selling price. Profit estimate subtracts asking costs, 10% parts overhead, £20 outbound delivery, £15 insurance, £6 packaging, £0 labour, £0.20 fixed payment cost, and payment, warranty and returns reserves. Buying postage is not confirmed.</p>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">{selected.map(({ category, gem }) => {
          const meta = componentLabels[category];
          const Icon = meta.icon;
          return <div key={category} className="flex min-w-0 items-center gap-3 rounded-xl border border-white/[0.07] bg-black/20 p-3">
            {gem?.image_url ? <img src={gem.image_url} alt="" className="h-12 w-12 shrink-0 rounded-lg bg-slate-800 object-contain" /> : <div className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-slate-800 text-slate-500"><Icon size={20} /></div>}
            <div className="min-w-0 flex-1"><p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{meta.label}</p><p className="truncate text-sm text-slate-200">{gem?.title ?? "No active Gem available"}</p>{gem && <p className="mt-0.5 truncate text-[10px] text-slate-500">Market: {gem.market_reference == null ? "unknown" : money(gem.market_reference)} · Profit signal: {gem.expected_profit == null ? "unknown" : money(gem.expected_profit)}</p>}</div>
            {gem && <span className="shrink-0 text-sm font-semibold text-emerald-200">{money(gem.price)}</span>}
          </div>;
        })}</div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] pt-4">
          <p className="max-w-2xl text-xs text-slate-500">{complete ? "Creates an unpaid sourcing draft from these eight listings. It does not buy parts or publish an offer." : "An active Gem is required for each of the eight component types."}</p>
          <button type="button" onClick={() => void createDraft(key, concept)} disabled={!complete || saving !== null} className="inline-flex items-center gap-2 rounded-lg bg-emerald-400 px-4 py-2.5 text-sm font-bold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-50">
            {saving === key ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{saving === key ? "Creating draft…" : `Create ${title} draft`}
          </button>
        </div>
      </article>;
    })}
  </div>;
}
