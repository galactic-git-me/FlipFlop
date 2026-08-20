"use client";

import { useEffect, useState } from "react";
import { getAllPlaybooks, getPlaybook, getBuildProfile, PlaybookTier, Playbook, ComponentType } from "@/lib/playbooks";
import { ChevronRight, Save, AlertCircle, X, Edit2, Sparkles } from "lucide-react";

type TabType = "design" | "build" | "sell" | "madetoorder";
type DesignSubTab = "playbook" | "draft" | "previous" | "custom" | "ai";

// Fixed slot order backing customComponents' index-based state — the Custom
// Build tab renders these split across two columns flanking the 3D preview,
// but the underlying array position must stay consistent regardless of
// which visual column a given type is drawn in.
const CUSTOM_COMPONENT_TYPES: ComponentType[] = [
  "CPU",
  "Motherboard",
  "RAM",
  "PSU",
  "SSD",
  "GPU",
  "Cooler",
  "Case",
];

interface ScoredListing {
  id: number;
  listing_id: string;
  title: string;
  seller?: string;
  image_url?: string | null;
  actual_price: number;
  delivered_price: number;
  market_new_price?: number;
  market_used_price?: number;
  classification: string;
  deal_score: number;
  scored_at: string;
}

interface SelectedComponent {
  type: ComponentType;
  listing: ScoredListing | null;
  customPrice?: number;
}

interface SavedBuild {
  id: number;
  name: string;
  playbook_id: string;
  playbook_tier: string;
  status: string;
  components: any;
  estimated_total_cost: number;
  estimated_market_new_price?: number;
  estimated_market_used_price?: number;
  estimated_profit?: number;
  created_at: string;
  updated_at: string;
}

// Cooler and Motherboard are checked before CPU deliberately — a "Liquid
// CPU Cooler" or "AM4 Motherboard" title also matches the generic "cpu"
// keyword, and since classifyComponent() returns on the first category
// match, whichever category is checked first wins that tie. "am4"/"am5" are
// deliberately NOT used as keywords at all — they're socket types shared by
// both CPUs and motherboards, so they can't distinguish between them
// (verified against 648 real listings: removing them costs zero genuine CPU
// matches, since every real bare-CPU listing already contains "processor"/
// "cpu"/"ryzen"/"intel core" too).
const COMPONENT_KEYWORDS: Record<ComponentType, string[]> = {
  Cooler: ["cooler", "tower cooler", "aio", "liquid cooling"],
  Motherboard: ["motherboard", "mobo", "lga"],
  CPU: ["processor", "cpu", "ryzen", "intel core"],
  RAM: ["ram", "memory", "ddr4", "ddr5", "udimm"],
  PSU: ["psu", "power supply", "watt"],
  SSD: ["ssd", "nvme", "nand", "storage"],
  GPU: ["gpu", "graphics card", "rtx", "gtx"],
  Case: ["case", "chassis", "pc case"],
  Fan: ["fan", "rgb fan", "cooling fan"],
};

// Word-boundary match, not substring — a plain `.includes("ram")` also
// matches "Rambler", "framework", "diagram", etc. Multi-word keywords like
// "power supply" still match as a literal phrase via the same regex.
function _hasKeyword(title: string, keyword: string): boolean {
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`\\b${escaped}\\b`, "i").test(title);
}

// Titles scraped before the extractor fix (src/content/ebay-extractor.ts)
// still have eBay's "New listing"/"Opens in a new window or tab"
// accessibility text glued directly onto the real title with no separating
// space — e.g. "...DDR4 MotherboardOpens in a new window or tab". That
// breaks \b word-boundary matching on whatever word it's glued to. Strip
// both patterns here too so existing data classifies correctly without
// needing a re-scan.
function _stripScrapeArtifacts(title: string): string {
  return title.replace(/^New listing/i, "").replace(/Opens in a new window or tab$/i, "").trim();
}

function classifyComponent(rawTitle: string): ComponentType | null {
  const title = _stripScrapeArtifacts(rawTitle);
  for (const [component, keywords] of Object.entries(COMPONENT_KEYWORDS)) {
    if (keywords.some((kw) => _hasKeyword(title, kw))) {
      return component as ComponentType;
    }
  }
  return null;
}

function findBestComponentForType(type: ComponentType, listings: ScoredListing[]): ScoredListing | null {
  const matching = listings.filter((l) => classifyComponent(l.title) === type);
  if (!matching.length) return null;

  const superGems = matching.filter((l) => l.classification === "SUPER_GEM").sort((a, b) => b.deal_score - a.deal_score);
  if (superGems.length) return superGems[0];

  const gems = matching.filter((l) => l.classification === "GEM").sort((a, b) => b.deal_score - a.deal_score);
  if (gems.length) return gems[0];

  return matching.sort((a, b) => b.deal_score - a.deal_score)[0];
}

// Backend-computed AI-generated build (app/services/ai_build_generator.py).
// Unlike the other tabs, this is not derived client-side from `listings` —
// it's a cached result of a scheduled job that cross-checks Super Gem
// combinations against live eBay sold/BIN data for the finished build.
interface AIBuildComponent {
  id: number;
  listing_id: string;
  category: string;
  title: string;
  seller?: string;
  image_url?: string | null;
  delivered_price: number;
  market_new_price?: number | null;
  market_used_price?: number | null;
  classification: string;
  estimated_profit: number;
  url: string;
}

interface AIBuildMarket {
  query: string;
  sold: { available: boolean; count: number; average_price: number | null; unavailable_reason: string | null };
  bin: { available: boolean; count: number; min_price: number | null; max_price: number | null; average_price: number | null };
}

interface AIBuild {
  rank: number;
  components: AIBuildComponent[];
  compatibility_confidence: "matched" | "unknown";
  build_cost: number;
  market: AIBuildMarket;
  resale_estimate: number;
  resale_source: "sold_average" | "bin_average" | "component_estimate";
  estimated_profit: number;
}

interface AIBuildsResponse {
  generated_at: string | null;
  builds: AIBuild[];
  unavailable_reason?: string;
  candidates_evaluated?: number;
  total_compatible_combinations?: number;
}

const AI_REQUIRED_SUPER_GEM_CATEGORIES = new Set(["cpu", "motherboard", "gpu", "ram"]);

const RESALE_SOURCE_LABEL: Record<AIBuild["resale_source"], string> = {
  sold_average: "Avg sold price",
  bin_average: "Avg BIN price (no sold comps)",
  component_estimate: "Component estimate (no eBay comps)",
};

function AIBuildCard({ build }: { build: AIBuild }) {
  return (
    <div className="p-4 bg-slate-800 border border-purple-500/30 rounded-lg space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-purple-400" />
          <h3 className="font-bold text-white">Build #{build.rank}</h3>
        </div>
        <span
          className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border ${
            build.compatibility_confidence === "matched"
              ? "bg-purple-500/20 text-purple-300 border-purple-500/40"
              : "bg-slate-600/30 text-slate-300 border-slate-500/40"
          }`}
          title={
            build.compatibility_confidence === "matched"
              ? "CPU socket and RAM generation both confirmed compatible from listing titles"
              : "Socket/RAM generation could not be fully confirmed from listing titles — verify before buying"
          }
        >
          {build.compatibility_confidence === "matched" ? "Compatibility Confirmed" : "Compatibility Unverified"}
        </span>
      </div>

      <div className="space-y-1">
        {build.components.map((c) => (
          <div key={c.id} className="flex justify-between text-xs">
            <span className="text-slate-400 truncate pr-2 capitalize">
              {c.category}
              {AI_REQUIRED_SUPER_GEM_CATEGORIES.has(c.category) && <span className="ml-1 text-purple-400">★</span>}
            </span>
            <span className="text-slate-200 text-right truncate max-w-[60%]">£{c.delivered_price.toFixed(2)}</span>
          </div>
        ))}
      </div>

      <div className="border-t border-slate-700 pt-2 space-y-1.5">
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">Build Cost</span>
          <span className="text-amber-400 font-semibold">£{build.build_cost.toFixed(2)}</span>
        </div>

        <div className="bg-slate-900/50 rounded p-2 space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Avg Sold (similar build)</span>
            <span className="text-slate-200">
              {build.market.sold.available ? `£${build.market.sold.average_price!.toFixed(2)}` : "No comps found"}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">BIN Range</span>
            <span className="text-slate-200">
              {build.market.bin.available
                ? `£${build.market.bin.min_price!.toFixed(2)} – £${build.market.bin.max_price!.toFixed(2)}`
                : "No listings found"}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Avg BIN Price</span>
            <span className="text-slate-200">
              {build.market.bin.available ? `£${build.market.bin.average_price!.toFixed(2)}` : "—"}
            </span>
          </div>
        </div>

        <div className="flex justify-between font-bold">
          <span className="text-slate-200">Est. Profit</span>
          <span className={build.estimated_profit >= 0 ? "text-green-400" : "text-red-400"}>
            £{build.estimated_profit.toFixed(2)}
          </span>
        </div>
        <p className="text-[10px] text-slate-500">via {RESALE_SOURCE_LABEL[build.resale_source]}</p>
      </div>
    </div>
  );
}

// Real CSS 3D transforms (perspective + preserve-3d + per-face rotateY),
// not an image — no external .glb/.gltf asset dependency, no new 3D library.
// Each side panel lights up once its component type has a selection, so the
// model reflects build progress rather than being pure decoration.
const TOWER_FACES: { rotate: number; label: string; types: ComponentType[] }[] = [
  { rotate: 0, label: "front", types: ["GPU", "Case"] },
  { rotate: 90, label: "right", types: ["Motherboard", "RAM"] },
  { rotate: 180, label: "back", types: ["PSU", "Fan"] },
  { rotate: 270, label: "left", types: ["CPU", "Cooler"] },
];

function RotatingPCTower({ selectedTypes }: { selectedTypes: Set<ComponentType> }) {
  const WIDTH = 160;
  const DEPTH = 160;
  const HEIGHT = 220;

  return (
    <div className="flex flex-col items-center justify-center py-6">
      <div
        style={{ perspective: 900 }}
        className="relative"
      >
        <div
          className="tower-spin relative"
          style={{
            width: WIDTH,
            height: HEIGHT,
            transformStyle: "preserve-3d",
          }}
        >
          {TOWER_FACES.map((face) => {
            const isLit = face.types.some((t) => selectedTypes.has(t));
            return (
              <div
                key={face.label}
                className="absolute inset-0 border rounded-md backdrop-blur-sm transition-colors duration-500"
                style={{
                  transform: `rotateY(${face.rotate}deg) translateZ(${DEPTH / 2}px)`,
                  background: isLit
                    ? "linear-gradient(160deg, rgba(0,220,130,0.18), rgba(0,184,255,0.10))"
                    : "linear-gradient(160deg, rgba(148,163,184,0.08), rgba(30,41,59,0.35))",
                  borderColor: isLit ? "rgba(0,220,130,0.55)" : "rgba(100,116,139,0.35)",
                  boxShadow: isLit ? "0 0 24px rgba(0,220,130,0.25) inset" : "none",
                }}
              >
                <div className="absolute top-3 left-3 right-3 h-1.5 rounded-full bg-gradient-to-r from-cyan-400/70 via-blue-400/70 to-emerald-400/70 opacity-70" />
                <div className="absolute inset-x-3 top-8 bottom-3 flex flex-col gap-2 justify-center">
                  {face.types.map((t) => (
                    <div
                      key={t}
                      className={`h-2 rounded-full transition-colors duration-500 ${
                        selectedTypes.has(t) ? "bg-emerald-400/80" : "bg-slate-600/50"
                      }`}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <p className="text-[11px] text-slate-500 mt-3 tracking-wide uppercase">Live build preview</p>
      <style jsx>{`
        .tower-spin {
          animation: tower-rotate 14s linear infinite;
        }
        @keyframes tower-rotate {
          from {
            transform: rotateY(0deg);
          }
          to {
            transform: rotateY(360deg);
          }
        }
      `}</style>
    </div>
  );
}

function ComponentSelector({
  listings,
  type,
  selected,
  onSelect,
  customPrice,
  onPriceChange,
}: {
  listings: ScoredListing[];
  type: ComponentType;
  selected: ScoredListing | null;
  onSelect: (listing: ScoredListing) => void;
  customPrice?: number;
  onPriceChange?: (price: number) => void;
}) {
  const matching = listings.filter((l) => classifyComponent(l.title) === type);

  return (
    <div className="space-y-2">
      <label className="block text-sm font-semibold text-slate-200">{type}</label>
      <select
        value={selected?.id || ""}
        onChange={(e) => {
          const listing = matching.find((l) => l.id === parseInt(e.target.value));
          if (listing) onSelect(listing);
        }}
        className="w-full px-3 py-2 bg-slate-700 border border-slate-600 text-white rounded text-sm"
      >
        <option value="">-- Select {type} --</option>
        {matching.map((item) => (
          <option key={item.id} value={item.id}>
            {item.title.substring(0, 60)} - £{item.delivered_price.toFixed(2)}
          </option>
        ))}
      </select>

      {selected && (
        <div className="mt-2 p-2 bg-slate-800/50 rounded text-xs space-y-1">
          {selected.image_url && (
            // eslint-disable-next-line @next/next/no-img-element -- external eBay-hosted thumbnail
            <img
              src={selected.image_url}
              alt={selected.title}
              width={48}
              height={48}
              className="rounded object-cover bg-slate-700 mb-1"
              style={{ width: 48, height: 48 }}
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          )}
          <div className="text-slate-300">
            <span className="font-semibold">Seller:</span> {selected.seller || "Unknown"}
          </div>
          <div className="text-slate-300">
            <span className="font-semibold">Market New:</span> £{selected.market_new_price?.toFixed(2) || "—"}
          </div>
          <div className="text-slate-300">
            <span className="font-semibold">Market Used:</span> £{selected.market_used_price?.toFixed(2) || "—"}
          </div>

          <label className="block mt-2">
            <span className="text-slate-400">Override Price (£):</span>
            <input
              type="number"
              step="0.01"
              value={customPrice || selected.delivered_price}
              onChange={(e) => onPriceChange?.(parseFloat(e.target.value) || 0)}
              className="w-full mt-1 px-2 py-1 bg-slate-700 border border-slate-600 text-white rounded text-xs"
            />
          </label>
        </div>
      )}
    </div>
  );
}

function CostBreakdown({ components }: { components: SelectedComponent[] }) {
  const componentCosts = components.map((c) => ({
    type: c.type,
    price: c.customPrice || c.listing?.delivered_price || 0,
  }));

  const totalCost = componentCosts.reduce((sum, c) => sum + c.price, 0);
  const avgResalePrice =
    components.reduce(
      (sum, c) => sum + ((c.listing?.market_new_price || 0) + (c.listing?.market_used_price || 0)) / 2,
      0
    ) / Math.max(components.length, 1);
  const estimatedProfit = avgResalePrice * components.length - totalCost;

  return (
    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
      <h3 className="font-bold text-white mb-4">Cost Breakdown</h3>

      <div className="space-y-2 mb-4">
        {componentCosts.map((item, idx) => (
          <div key={idx} className="flex justify-between text-sm">
            <span className="text-slate-300">{item.type}</span>
            <span className="text-white font-semibold">£{item.price.toFixed(2)}</span>
          </div>
        ))}
        <div className="border-t border-slate-600 pt-2 mt-2 flex justify-between font-bold">
          <span className="text-white">Total Build Cost</span>
          <span className="text-amber-400">£{totalCost.toFixed(2)}</span>
        </div>
      </div>

      <div className="space-y-2 bg-slate-900/50 p-3 rounded">
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">Avg Resale Price</span>
          <span className="text-blue-400">£{avgResalePrice.toFixed(2)}</span>
        </div>
        <div className="flex justify-between font-bold">
          <span className="text-slate-200">Estimated Profit</span>
          <span className={estimatedProfit >= 0 ? "text-green-400" : "text-red-400"}>
            £{estimatedProfit.toFixed(2)}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function PCBuilderPage() {
  const [playbooks] = useState<Playbook[]>(getAllPlaybooks());
  const [tab, setTab] = useState<TabType>("design");
  const [designSubTab, setDesignSubTab] = useState<DesignSubTab>("playbook");
  const [listings, setListings] = useState<ScoredListing[]>([]);
  const [draftBuilds, setDraftBuilds] = useState<SavedBuild[]>([]);
  const [completedBuilds, setCompletedBuilds] = useState<SavedBuild[]>([]);
  const [buildStageBuilds, setBuildStageBuilds] = useState<SavedBuild[]>([]);
  const [sellStageBuilds, setSellStageBuilds] = useState<SavedBuild[]>([]);

  const [selectedPlaybook, setSelectedPlaybook] = useState<string | null>(null);
  const [selectedTier, setSelectedTier] = useState<PlaybookTier | null>(null);
  const [playbookComponents, setPlaybookComponents] = useState<SelectedComponent[]>([]);
  const [buildName, setBuildName] = useState("");

  const [customComponents, setCustomComponents] = useState<SelectedComponent[]>([]);
  const [customBuildName, setCustomBuildName] = useState("");

  const [aiBuildsData, setAiBuildsData] = useState<AIBuildsResponse | null>(null);
  const [aiRefreshing, setAiRefreshing] = useState(false);

  const [selectedBuildId, setSelectedBuildId] = useState<number | null>(null);
  const [buildSubTab, setBuildSubTab] = useState<"inventory" | "software" | "3d" | "pictures" | "tests" | "plate">("inventory");
  const [unallocatedInventory, setUnallocatedInventory] = useState<Record<string, any[]>>({});

  const fetchAIBuilds = async () => {
    try {
      const res = await fetch("/api/pc-builder/ai-generated-builds");
      if (res.ok) setAiBuildsData(await res.json());
    } catch (error) {
      console.error("Error fetching AI-generated builds:", error);
    }
  };

  const handleSelectBuildForInventory = async (buildId: number) => {
    setSelectedBuildId(buildId);
    setBuildSubTab("inventory");
    try {
      const res = await fetch(`/inventory-allocations/builds/${buildId}/unallocated-by-type`);
      if (res.ok) {
        setUnallocatedInventory(await res.json());
      }
    } catch (error) {
      console.error("Error fetching unallocated inventory:", error);
    }
  };

  const handleAllocateInventory = async (inventoryItemId: number, quantity: number) => {
    if (!selectedBuildId) return;
    try {
      const res = await fetch("/inventory-allocations/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          inventory_item_id: inventoryItemId,
          build_id: selectedBuildId,
          quantity_allocated: quantity,
        }),
      });
      if (res.ok) {
        alert("Inventory allocated successfully!");
        handleSelectBuildForInventory(selectedBuildId);
      }
    } catch (error) {
      console.error("Error allocating inventory:", error);
      alert("Failed to allocate inventory");
    }
  };

  const handleRefreshAIBuilds = async () => {
    setAiRefreshing(true);
    try {
      const res = await fetch("/api/pc-builder/ai-generated-builds/refresh", { method: "POST" });
      if (res.ok) setAiBuildsData(await res.json());
    } catch (error) {
      console.error("Error refreshing AI-generated builds:", error);
    } finally {
      setAiRefreshing(false);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [listingsRes, draftRes, completedRes, allBuildsRes] = await Promise.all([
          fetch("/api/gem-radar/scored-listings"),
          fetch("/api/pc-builder/builds?status=draft"),
          fetch("/api/pc-builder/builds?status=completed"),
          fetch("/api/pc-builder/builds"),
        ]);

        if (listingsRes.ok) setListings(await listingsRes.json());
        if (draftRes.ok) setDraftBuilds(await draftRes.json());
        if (completedRes.ok) setCompletedBuilds(await completedRes.json());

        if (allBuildsRes.ok) {
          const allBuilds = await allBuildsRes.json();
          setBuildStageBuilds(allBuilds.filter((b: any) => b.stage === "build"));
          setSellStageBuilds(allBuilds.filter((b: any) => b.stage === "sell"));
        }
      } catch (error) {
        console.error("Error fetching data:", error);
      }
    };

    fetchData();
    fetchAIBuilds();
  }, []);

  const handlePlaybookBuildSelect = (tier: PlaybookTier) => {
    if (!selectedPlaybook) return;
    setSelectedTier(tier);
    const profile = getBuildProfile(selectedPlaybook, tier);
    if (!profile) return;
    const components: SelectedComponent[] = profile.components.map((spec) => ({
      type: spec.type,
      listing: findBestComponentForType(spec.type, listings),
    }));
    setPlaybookComponents(components);
  };

  const handleSavePlaybookBuild = async () => {
    if (!buildName.trim() || !selectedPlaybook || !selectedTier) return;

    const totalCost = playbookComponents.reduce((sum, c) => sum + (c.customPrice || c.listing?.delivered_price || 0), 0);
    const profit = playbookComponents.reduce((sum, c) => sum + ((c.listing?.market_new_price || 0) + (c.listing?.market_used_price || 0)) / 2, 0) - totalCost;

    try {
      await fetch("/api/pc-builder/builds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: buildName,
          playbook_id: selectedPlaybook,
          playbook_tier: selectedTier,
          components: { components: playbookComponents.map((c) => ({ type: c.type, listing_id: c.listing?.listing_id })) },
          estimated_total_cost: totalCost,
          estimated_profit: profit,
        }),
      });
      alert("Build saved!");
      setBuildName("");
    } catch (error) {
      alert("Failed to save build");
    }
  };

  const handleSaveCustomBuild = async () => {
    if (!customBuildName.trim()) return;

    const totalCost = customComponents.reduce((sum, c) => sum + (c.customPrice || c.listing?.delivered_price || 0), 0);
    const profit = customComponents.reduce((sum, c) => sum + ((c.listing?.market_new_price || 0) + (c.listing?.market_used_price || 0)) / 2, 0) - totalCost;

    try {
      await fetch("/api/pc-builder/builds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: customBuildName,
          playbook_id: "custom",
          playbook_tier: "custom",
          components: { components: customComponents.map((c) => ({ type: c.type, listing_id: c.listing?.listing_id })) },
          estimated_total_cost: totalCost,
          estimated_profit: profit,
        }),
      });
      alert("Curated build saved!");
      setCustomBuildName("");
      setCustomComponents([]);
    } catch (error) {
      alert("Failed to save build");
    }
  };

  return (
    <div className="flex flex-col h-full gap-4 p-6 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="mb-4">
        <h1 className="text-3xl font-bold text-white">Curated Builds</h1>
        <p className="text-slate-400 text-sm mt-1">Shape proven playbooks into ready-to-sell PC configurations</p>
      </div>

      {/* Main Tabs */}
      <div className="flex gap-2 border-b border-slate-700 pb-4">
        {[
          { id: "design" as TabType, label: "DESIGN" },
          { id: "build" as TabType, label: `BUILD (${buildStageBuilds.length})` },
          { id: "sell" as TabType, label: `SELL (${sellStageBuilds.length})` },
          { id: "madetoorder" as TabType, label: "MADE TO ORDER" },
        ].map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-4 py-2 rounded font-semibold transition ${
              tab === id ? "bg-blue-600 text-white" : "bg-slate-700 text-slate-300 hover:bg-slate-600"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Design Sub-Tabs */}
      {tab === "design" && (
        <div className="flex gap-2 border-b border-slate-600 pb-3">
          {[
            { id: "playbook" as DesignSubTab, label: "By Playbook" },
            { id: "draft" as DesignSubTab, label: `Draft Builds (${draftBuilds.length})` },
            { id: "previous" as DesignSubTab, label: `Previous Builds (${completedBuilds.length})` },
            { id: "custom" as DesignSubTab, label: "Manual Configuration" },
            { id: "ai" as DesignSubTab, label: "AI-Generated" },
          ].map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setDesignSubTab(id)}
              className={`px-3 py-2 text-sm rounded font-semibold transition ${
                designSubTab === id ? "bg-amber-600 text-white" : "bg-slate-700 text-slate-300 hover:bg-slate-600"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-auto">
        {/* DESIGN TAB */}
        {tab === "design" && (
          <div className="space-y-6">
            {designSubTab === "playbook" && (
              <div>
                {!selectedPlaybook ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {playbooks.map((playbook) => (
                      <button
                        key={playbook.id}
                        onClick={() => setSelectedPlaybook(playbook.id)}
                        className="group p-6 rounded-lg bg-slate-800 border border-slate-700 hover:border-blue-500 transition text-left"
                      >
                        <div className="text-4xl mb-3">{playbook.icon}</div>
                        <h2 className="text-xl font-bold text-white mb-2">{playbook.name}</h2>
                        <p className="text-sm text-slate-400 mb-4">{playbook.description}</p>
                        <div className="flex items-center gap-2 text-blue-400 group-hover:gap-3 transition">
                          <span className="text-sm font-semibold">View builds</span>
                          <ChevronRight className="w-4 h-4" />
                        </div>
                      </button>
                    ))}
                  </div>
                ) : !selectedTier ? (
                  <div>
                    <button onClick={() => setSelectedPlaybook(null)} className="mb-4 text-blue-400 hover:text-blue-300">
                      ← Back to Playbooks
                    </button>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {(["budget", "midrange", "highend"] as PlaybookTier[]).map((tier) => {
                        const profile = getBuildProfile(selectedPlaybook, tier);
                        if (!profile) return null;
                        return (
                          <button
                            key={tier}
                            onClick={() => handlePlaybookBuildSelect(tier)}
                            className="p-6 rounded-lg bg-slate-800 border border-slate-700 hover:border-amber-500 transition text-left"
                          >
                            <h2 className="text-2xl font-bold text-white mb-2">
                              {tier === "budget" ? "Budget" : tier === "midrange" ? "Mid-Range" : "High-End"}
                            </h2>
                            <p className="text-3xl font-bold text-amber-400 mb-2">${profile.budgetUSD}</p>
                            <p className="text-sm text-slate-400">{profile.description}</p>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-3 gap-6">
                    <div className="col-span-2 space-y-4">
                      <button onClick={() => setSelectedTier(null)} className="text-blue-400 hover:text-blue-300">
                        ← Change Tier
                      </button>
                      <div className="space-y-3">
                        {playbookComponents.map((comp, idx) => (
                          <ComponentSelector
                            key={idx}
                            listings={listings}
                            type={comp.type}
                            selected={comp.listing}
                            onSelect={(listing) => {
                              const newComps = [...playbookComponents];
                              newComps[idx].listing = listing;
                              setPlaybookComponents(newComps);
                            }}
                            customPrice={comp.customPrice}
                            onPriceChange={(price) => {
                              const newComps = [...playbookComponents];
                              newComps[idx].customPrice = price;
                              setPlaybookComponents(newComps);
                            }}
                          />
                        ))}
                      </div>
                    </div>

                    <div className="space-y-4">
                      <CostBreakdown components={playbookComponents} />

                      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700 space-y-3">
                        <input
                          type="text"
                          placeholder="Build name..."
                          value={buildName}
                          onChange={(e) => setBuildName(e.target.value)}
                          className="w-full px-3 py-2 bg-slate-700 border border-slate-600 text-white rounded text-sm"
                        />
                        <button
                          onClick={handleSavePlaybookBuild}
                          disabled={!buildName.trim()}
                          className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white rounded font-semibold transition flex items-center justify-center gap-2"
                        >
                          <Save className="w-4 h-4" /> Save Build
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {designSubTab === "draft" && (
              <div>
                {draftBuilds.length === 0 ? (
                  <p className="text-slate-400">No draft builds yet. Create one using the "By Playbook" or "Manual Configuration" tabs.</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {draftBuilds.map((build) => (
                      <div key={build.id} className="p-4 bg-slate-800 border border-slate-700 rounded-lg">
                        <h3 className="font-bold text-white">{build.name}</h3>
                        <p className="text-sm text-slate-400 mt-1">{build.playbook_id} • {build.playbook_tier}</p>
                        <p className="text-lg font-bold text-amber-400 mt-2">£{build.estimated_total_cost.toFixed(2)}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {designSubTab === "previous" && (
              <div>
                {completedBuilds.length === 0 ? (
                  <p className="text-slate-400">No completed builds yet.</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {completedBuilds.map((build) => (
                      <div key={build.id} className="p-4 bg-slate-800 border border-slate-700 rounded-lg">
                        <h3 className="font-bold text-white">{build.name}</h3>
                        <p className="text-sm text-slate-400 mt-1">{build.playbook_id} • {build.playbook_tier}</p>
                        <p className="text-lg font-bold text-emerald-400 mt-2">£{build.estimated_profit?.toFixed(2) || "—"} profit</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {designSubTab === "custom" && (
              <div className="space-y-6">
                <div className="grid grid-cols-[1fr_auto_1fr] gap-6 items-start">
                  <div className="space-y-3">
                    {(["CPU", "Motherboard", "RAM", "PSU"] as ComponentType[]).map((type) => {
                      const idx = CUSTOM_COMPONENT_TYPES.indexOf(type);
                      return (
                        <ComponentSelector
                          key={type}
                          listings={listings}
                          type={type}
                          selected={customComponents[idx]?.listing || null}
                          onSelect={(listing) => {
                            const newComps = [...customComponents];
                            if (!newComps[idx]) newComps[idx] = { type, listing: null };
                            newComps[idx].listing = listing;
                            setCustomComponents(newComps);
                          }}
                          customPrice={customComponents[idx]?.customPrice}
                          onPriceChange={(price) => {
                            const newComps = [...customComponents];
                            if (!newComps[idx]) newComps[idx] = { type, listing: null };
                            newComps[idx].customPrice = price;
                            setCustomComponents(newComps);
                          }}
                        />
                      );
                    })}
                  </div>

                  <RotatingPCTower
                    selectedTypes={
                      new Set(customComponents.filter((c) => c.listing).map((c) => c.type))
                    }
                  />

                  <div className="space-y-3">
                    {(["SSD", "GPU", "Cooler", "Case"] as ComponentType[]).map((type) => {
                      const idx = CUSTOM_COMPONENT_TYPES.indexOf(type);
                      return (
                        <ComponentSelector
                          key={type}
                          listings={listings}
                          type={type}
                          selected={customComponents[idx]?.listing || null}
                          onSelect={(listing) => {
                            const newComps = [...customComponents];
                            if (!newComps[idx]) newComps[idx] = { type, listing: null };
                            newComps[idx].listing = listing;
                            setCustomComponents(newComps);
                          }}
                          customPrice={customComponents[idx]?.customPrice}
                          onPriceChange={(price) => {
                            const newComps = [...customComponents];
                            if (!newComps[idx]) newComps[idx] = { type, listing: null };
                            newComps[idx].customPrice = price;
                            setCustomComponents(newComps);
                          }}
                        />
                      );
                    })}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-6 max-w-2xl mx-auto">
                  <CostBreakdown components={customComponents.filter((c) => c.listing)} />

                  <div className="bg-slate-800 rounded-lg p-4 border border-slate-700 space-y-3">
                    <input
                      type="text"
                        placeholder="Curated build name..."
                      value={customBuildName}
                      onChange={(e) => setCustomBuildName(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 text-white rounded text-sm"
                    />
                    <button
                      onClick={handleSaveCustomBuild}
                      disabled={!customBuildName.trim()}
                      className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white rounded font-semibold transition flex items-center justify-center gap-2"
                    >
                      <Save className="w-4 h-4" /> Save Build
                    </button>
                  </div>
                </div>
              </div>
            )}

            {designSubTab === "ai" && (
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <p className="text-slate-400 text-sm max-w-2xl">
                    CPU, Motherboard, GPU, and RAM (★) are sourced exclusively from socket/RAM-compatible Super Gem
                    combinations. Ranked by estimated profit, validated against live eBay sold and BIN prices for
                    similar finished builds. Refreshed automatically every few hours.
                  </p>
                  <div className="flex items-center gap-3">
                    {aiBuildsData?.generated_at && (
                      <span className="text-xs text-slate-500 whitespace-nowrap">
                        Updated {new Date(aiBuildsData.generated_at).toLocaleString()}
                      </span>
                    )}
                    <button
                      onClick={handleRefreshAIBuilds}
                      disabled={aiRefreshing}
                      className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600 text-white rounded text-sm font-semibold transition flex items-center gap-2 whitespace-nowrap"
                    >
                      <Sparkles className="w-4 h-4" /> {aiRefreshing ? "Generating…" : "Regenerate"}
                    </button>
                  </div>
                </div>

                {!aiBuildsData ? (
                  <p className="text-slate-400">Loading…</p>
                ) : aiBuildsData.builds.length === 0 ? (
                  <p className="text-slate-400">
                    {aiBuildsData.unavailable_reason ||
                      "Not enough Super Gem listings yet across CPU, Motherboard, GPU, and RAM to generate a build."}
                  </p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {aiBuildsData.builds.map((build) => (
                      <AIBuildCard key={build.rank} build={build} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* BUILD TAB */}
        {tab === "build" && (
          <div className="space-y-4">
            {buildStageBuilds.length === 0 ? (
              <p className="text-slate-400">No builds in BUILD stage yet. Start a build from the DESIGN tab to see it here.</p>
            ) : !selectedBuildId ? (
              <div className="space-y-4">
                {buildStageBuilds.map((build) => (
                  <button
                    key={build.id}
                    onClick={() => handleSelectBuildForInventory(build.id)}
                    className="w-full p-4 bg-slate-800 border border-slate-700 rounded-lg hover:border-blue-500 transition text-left"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="font-bold text-white">{build.name}</h3>
                        <p className="text-sm text-slate-400 mt-1">{build.playbook_id} • {build.playbook_tier}</p>
                        <p className="text-sm text-amber-400 font-semibold mt-2">£{build.estimated_total_cost?.toFixed(2) || "0.00"}</p>
                      </div>
                      <span className="px-3 py-1 bg-blue-600/30 text-blue-300 rounded text-xs font-semibold">BUILD</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="space-y-4">
                <button
                  onClick={() => setSelectedBuildId(null)}
                  className="text-blue-400 hover:text-blue-300 text-sm"
                >
                  ← Back to Builds
                </button>

                <div className="flex gap-2 border-b border-slate-600 pb-3">
                  {[
                    { id: "inventory" as const, label: "Inventory" },
                    { id: "software" as const, label: "Software" },
                    { id: "3d" as const, label: "3D Model" },
                    { id: "pictures" as const, label: "Pictures" },
                    { id: "tests" as const, label: "Performance Tests" },
                    { id: "plate" as const, label: "Registration Plate" },
                  ].map(({ id, label }) => (
                    <button
                      key={id}
                      onClick={() => setBuildSubTab(id)}
                      className={`px-3 py-2 text-sm rounded font-semibold transition ${
                        buildSubTab === id ? "bg-blue-600 text-white" : "bg-slate-700 text-slate-300 hover:bg-slate-600"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {buildSubTab === "inventory" && (
                  <div className="space-y-6">
                    {Object.keys(unallocatedInventory).length === 0 ? (
                      <p className="text-slate-400">All inventory allocated or no available items.</p>
                    ) : (
                      Object.entries(unallocatedInventory).map(([componentType, items]) => (
                        <div key={componentType} className="border border-slate-700 rounded-lg p-4">
                          <h3 className="text-lg font-bold text-white mb-3 capitalize">{componentType}</h3>
                          <div className="space-y-3">
                            {(items as any[]).map((item) => (
                              <div key={item.id} className="flex items-start justify-between p-3 bg-slate-900 rounded border border-slate-700">
                                <div className="flex-1">
                                  <p className="font-semibold text-white">{item.component_name}</p>
                                  <p className="text-xs text-slate-400 mt-1">
                                    Total: {item.quantity} | Allocated: {item.allocated_quantity} | Unallocated: {item.unallocated_quantity}
                                  </p>
                                  <p className="text-sm text-amber-400 font-semibold mt-1">£{item.actual_cost.toFixed(2)}</p>
                                  {item.source && <p className="text-xs text-slate-500">From: {item.source}</p>}
                                </div>
                                <button
                                  onClick={() => handleAllocateInventory(item.id, item.unallocated_quantity)}
                                  className="ml-4 px-3 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-semibold whitespace-nowrap transition"
                                >
                                  Allocate All
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {buildSubTab !== "inventory" && (
                  <p className="text-slate-400 text-sm">Sub-tab content coming soon...</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* SELL TAB */}
        {tab === "sell" && (
          <div className="space-y-4">
            {sellStageBuilds.length === 0 ? (
              <p className="text-slate-400">No builds in SELL stage yet. Complete the BUILD stage to move a build here.</p>
            ) : (
              <div className="space-y-4">
                {sellStageBuilds.map((build) => (
                  <div key={build.id} className="p-4 bg-slate-800 border border-slate-700 rounded-lg">
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="font-bold text-white">{build.name}</h3>
                        <p className="text-sm text-slate-400 mt-1">{build.playbook_id} • {build.playbook_tier}</p>
                        <p className="text-sm text-emerald-400 font-semibold mt-2">£{build.estimated_total_cost?.toFixed(2) || "0.00"} → £{build.estimated_market_new_price?.toFixed(2) || "—"}</p>
                      </div>
                      <span className="px-3 py-1 bg-emerald-600/30 text-emerald-300 rounded text-xs font-semibold">READY TO SELL</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-2">Sub-tabs coming soon: Selling Profiles, Platforms, GO LIVE</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* MADE TO ORDER TAB */}
        {tab === "madetoorder" && (
          <div className="space-y-4">
            <p className="text-slate-400 text-sm">Made-to-Order sales from customers will appear here. Phase 4 integration pending.</p>
            <div className="p-4 bg-slate-800 border border-slate-700 rounded-lg">
              <p className="text-slate-500 text-sm">No Made-to-Order builds yet. When customers purchase custom builds from the storefront, they'll appear here for fulfillment.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
