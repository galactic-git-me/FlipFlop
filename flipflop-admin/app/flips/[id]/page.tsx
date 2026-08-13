"use client";

import { useEffect, useState, use, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ExternalLink,
  Loader2,
  ChevronRight,
  Check,
  Cpu,
  MemoryStick,
  HardDrive,
  Monitor,
  Search,
  X,
  PackagePlus,
  FileText,
  Camera,
  ListChecks,
  Banknote,
  Truck,
  CalendarClock,
  MoreHorizontal,
} from "lucide-react";
import { api } from "@/lib/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { Flip, Listing } from "@/components/flip-detail/types";
import { ListingContentTab } from "@/components/flip-detail/ListingContentTab";
import { ItemSpecificsTab } from "@/components/flip-detail/ItemSpecificsTab";
import { PhotosTab } from "@/components/flip-detail/PhotosTab";
import { PricingTab } from "@/components/flip-detail/PricingTab";
import { DispatchTab } from "@/components/flip-detail/DispatchTab";
import { LiveListingTab } from "@/components/flip-detail/LiveListingTab";
import { OtherTab } from "@/components/flip-detail/OtherTab";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type FlipStage = "selected" | "building" | "ready_for_sale" | "sold";

// ── Playbook + Upgrade Section (Build Overview — pre-listing build process,
// stays above the eBay-listing tabs; see docs/build-details-automation-plan.md) ──

interface Playbook {
  id: number;
  name: string;
  emoji: string;
  description: string;
  target_use_case: string;
  upgrade_strategy?: {
    required?: { component: string; target: string; max_cost: number }[];
    optional?: { component: string; target: string; max_cost: number }[];
  };
}

interface Part {
  id: number;
  name: string;
  category: string;
  price: number;
  source_site: string;
  model?: string;
  specs?: string;
  source_url?: string;
}

const COMPONENT_TO_CATEGORY: Record<string, string> = {
  GPU: "gpu", RAM: "ram", SSD: "ssd", CPU: "cpu",
  PSU: "psu", Motherboard: "motherboard", Cooling: "cooling",
  Storage: "ssd", Memory: "ram",
};

const GOOD_SOURCES = ["eBay UK", "Gumtree", "Amazon"];

function autoSelectPlaybook(playbooks: Playbook[], listing?: { cpu?: string; gpu?: string } | null): number | null {
  if (!listing || playbooks.length === 0) return null;
  const hasGpu = !!listing.gpu;
  const cpu = (listing.cpu ?? "").toLowerCase();
  const isHighEnd = /i9|ryzen 9|threadripper/.test(cpu);
  const isMidRange = /i7|ryzen 7/.test(cpu);

  for (const pb of playbooks) {
    const uc = pb.target_use_case?.toLowerCase() ?? "";
    if (isHighEnd && uc.includes("workstation")) return pb.id;
    if (!hasGpu && uc.includes("gaming")) return pb.id;
    if (hasGpu && isMidRange && uc.includes("content")) return pb.id;
  }
  return playbooks[0]?.id ?? null;
}

function UpgradeSection({
  flip, listing, onFlipUpdated,
}: {
  flip: Flip;
  listing?: { cpu?: string; gpu?: string; title?: string; url?: string } | null;
  onFlipUpdated: (f: Flip) => void;
}) {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [selectedPbId, setSelectedPbId] = useState<number | null>(null);
  const [loadingPbs, setLoadingPbs] = useState(true);

  // Part picker state
  const [openSlot, setOpenSlot] = useState<string | null>(null);
  const [partQuery, setPartQuery] = useState("");
  const [allParts, setAllParts] = useState<Part[]>([]);
  const [loadingParts, setLoadingParts] = useState(false);
  const [savingSlot, setSavingSlot] = useState<string | null>(null);

  // Fetch playbooks once
  useEffect(() => {
    fetch(`${API_BASE}/api/build-wizard/playbooks`)
      .then((r) => r.json())
      .then((data: Playbook[]) => {
        setPlaybooks(data);
        const autoId = autoSelectPlaybook(data, listing);
        setSelectedPbId(autoId);
      })
      .catch(console.error)
      .finally(() => setLoadingPbs(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const openPickerFor = useCallback(async (component: string) => {
    const cat = COMPONENT_TO_CATEGORY[component] ?? component.toLowerCase();
    setOpenSlot(component);
    setPartQuery("");
    setLoadingParts(true);
    try {
      const res = await fetch(`${API_BASE}/api/parts/?category=${cat}&limit=200`);
      const data = await res.json();
      const items: Part[] = Array.isArray(data) ? data : data.items ?? [];
      const filtered = items.filter(
        (p) => GOOD_SOURCES.includes(p.source_site) && (p.price ?? 0) > 10
      );
      setAllParts(filtered);
    } finally {
      setLoadingParts(false);
    }
  }, []);

  async function selectPart(component: string, part: Part) {
    setSavingSlot(component);
    try {
      const updated = await api.flips.patch(flip.id, {
        selected_upgrade_ids: {
          ...(flip.selected_upgrade_ids ?? {}),
          [component]: part.id,
        },
      });
      onFlipUpdated(updated as Flip);
      setOpenSlot(null);
    } finally {
      setSavingSlot(null);
    }
  }

  async function clearSlot(component: string) {
    const ids = { ...(flip.selected_upgrade_ids ?? {}) };
    delete ids[component];
    const updated = await api.flips.patch(flip.id, { selected_upgrade_ids: ids });
    onFlipUpdated(updated as Flip);
  }

  const selectedPb = playbooks.find((p) => p.id === selectedPbId);
  const upgrades = [
    ...(selectedPb?.upgrade_strategy?.required ?? []),
    ...(selectedPb?.upgrade_strategy?.optional ?? []),
  ];

  const filteredParts = allParts.filter((p) =>
    partQuery.length < 2 ||
    p.name.toLowerCase().includes(partQuery.toLowerCase()) ||
    (p.model ?? "").toLowerCase().includes(partQuery.toLowerCase())
  ).slice(0, 30);

  if (loadingPbs) return null;

  return (
    <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-4">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
        <PackagePlus className="w-3.5 h-3.5" /> Playbook &amp; Upgrades
      </p>

      {/* Playbook selector */}
      <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
        {playbooks.map((pb) => (
          <button
            key={pb.id}
            onClick={() => setSelectedPbId(pb.id)}
            className={`flex-shrink-0 flex flex-col items-start gap-0.5 px-3 py-2 rounded-lg border text-left transition-all ${
              pb.id === selectedPbId
                ? "border-[#00dc82] bg-[#00dc82]/10 text-[#00dc82]"
                : "border-slate-700 text-slate-400 hover:border-slate-600"
            }`}
          >
            <span className="text-base leading-none">{pb.emoji}</span>
            <span className="text-[10px] font-bold whitespace-nowrap">{pb.name}</span>
          </button>
        ))}
      </div>

      {/* Upgrade slots */}
      {upgrades.length === 0 && (
        <p className="text-xs text-slate-600 italic">Select a playbook to see upgrade recommendations.</p>
      )}

      {upgrades.map((u) => {
        const selectedId = (flip.selected_upgrade_ids ?? {})[u.component] as number | undefined;
        const isOpen = openSlot === u.component;
        const isSaving = savingSlot === u.component;

        return (
          <div key={u.component} className="flex flex-col gap-2">
            <div className="flex items-center gap-3 p-3 rounded-lg border border-slate-800 bg-slate-900/40">
              {/* Slot label */}
              <div className="w-16 flex-shrink-0">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{u.component}</p>
                <p className="text-[10px] text-slate-600 mt-0.5">max £{u.max_cost}</p>
              </div>

              {/* Target */}
              <div className="flex-1 min-w-0">
                <p className="text-xs text-slate-400 truncate">{u.target}</p>
                {selectedId && (
                  <p className="text-[10px] text-[#00dc82] mt-0.5 flex items-center gap-1">
                    <Check className="w-2.5 h-2.5" /> Part selected
                  </p>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1.5 flex-shrink-0">
                {selectedId && (
                  <button
                    onClick={() => clearSlot(u.component)}
                    className="p-1 text-slate-600 hover:text-red-400 transition-colors"
                    title="Remove"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
                <button
                  onClick={() => isOpen ? setOpenSlot(null) : openPickerFor(u.component)}
                  disabled={isSaving}
                  className={`flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-semibold rounded-md transition-colors ${
                    selectedId
                      ? "border border-slate-700 text-slate-400 hover:border-slate-500"
                      : "bg-[#00dc82]/90 text-[#04120d] hover:bg-[#00dc82]"
                  }`}
                >
                  {isSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
                  {selectedId ? "Swap" : "Pick"}
                </button>
              </div>
            </div>

            {/* Inline part picker */}
            {isOpen && (
              <div className="border border-slate-700 rounded-lg bg-[#080f1a] p-3 flex flex-col gap-2">
                <input
                  autoFocus
                  type="text"
                  value={partQuery}
                  onChange={(e) => setPartQuery(e.target.value)}
                  placeholder={`Search ${u.component} parts…`}
                  className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 outline-none focus:border-[#00dc82] transition-colors placeholder-slate-600"
                />
                {loadingParts ? (
                  <div className="flex items-center gap-2 text-sm text-slate-500 py-2">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading parts…
                  </div>
                ) : filteredParts.length === 0 ? (
                  <p className="text-xs text-slate-600 py-2">
                    No parts found. Try a shorter search term.
                  </p>
                ) : (
                  <div className="flex flex-col gap-1 max-h-52 overflow-y-auto">
                    {filteredParts.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => selectPart(u.component, p)}
                        className="flex items-center gap-3 px-2 py-1.5 rounded-md hover:bg-slate-800 text-left transition-colors"
                      >
                        <span className="text-xs font-mono text-[#00dc82] w-12 flex-shrink-0 text-right">
                          £{p.price.toFixed(0)}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-slate-300 truncate">{p.name}</p>
                          {p.specs && (
                            <p className="text-[10px] text-slate-600 truncate">{p.specs}</p>
                          )}
                        </div>
                        <span className="text-[10px] text-slate-600 flex-shrink-0">{p.source_site}</span>
                      </button>
                    ))}
                  </div>
                )}
                {!loadingParts && allParts.length === 0 && (
                  <a
                    href={`https://www.ebay.co.uk/sch/i.html?_nkw=${encodeURIComponent(u.target)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
                  >
                    <ExternalLink className="w-3 h-3" /> Search eBay for "{u.target}"
                  </a>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const STAGES: { key: FlipStage; label: string }[] = [
  { key: "selected", label: "Selected" },
  { key: "building", label: "Building" },
  { key: "ready_for_sale", label: "Ready for Sale" },
  { key: "sold", label: "Sold" },
];

const STAGE_NEXT: Record<FlipStage, FlipStage | null> = {
  selected: "building",
  building: "ready_for_sale",
  ready_for_sale: "sold",
  sold: null,
};

const STAGE_NEXT_LABEL: Record<FlipStage, string> = {
  selected: "Mark as Building",
  building: "Mark Ready for Sale",
  ready_for_sale: "Mark as Sold",
  sold: "",
};

function SpecPill({ icon, value }: { icon: React.ReactNode; value?: string | number | null }) {
  if (!value) return null;
  return (
    <span className="flex items-center gap-1 px-2 py-0.5 bg-slate-800 rounded text-xs text-slate-300">
      {icon}
      {value}
    </span>
  );
}

const TABS = [
  { key: "listing-content", label: "Listing Content", icon: FileText },
  { key: "photos", label: "Photos", icon: Camera },
  { key: "item-specifics", label: "Item Specifics", icon: ListChecks },
  { key: "pricing", label: "Pricing", icon: Banknote },
  { key: "dispatch", label: "Dispatch & Delivery", icon: Truck },
  { key: "live-listing", label: "Live Listing Management", icon: CalendarClock },
  { key: "other", label: "Other", icon: MoreHorizontal },
] as const;

export default function FlipDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [flip, setFlip] = useState<Flip | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Purchase plan
  type PurchaseItem = {
    category: string;
    label: string;
    name: string;
    specs: string;
    price: number;
    url: string;
    source: string;
    part_id: number | null;
  };
  type PurchasePlan = { flip_id: number; items: PurchaseItem[]; total: number };
  const [purchasePlan, setPurchasePlan] = useState<PurchasePlan | null>(null);
  const [purchased, setPurchased] = useState<Set<string>>(new Set());
  const [loadingPlan, setLoadingPlan] = useState(false);

  // Compatibility check
  type CompatResult = {
    compatible: boolean | null;
    confidence: "high" | "medium" | "low";
    issues: string[];
    warnings: string[];
    summary: string;
    model_used: string;
  };
  const [compatResult, setCompatResult] = useState<CompatResult | null>(null);
  const [checkingCompat, setCheckingCompat] = useState(false);
  const [compatChecked, setCompatChecked] = useState(false);

  // Sold form
  const [showSoldForm, setShowSoldForm] = useState(false);
  const [salePrice, setSalePrice] = useState("");
  const [salePlatform, setSalePlatform] = useState("eBay");
  const [markingSold, setMarkingSold] = useState(false);

  useEffect(() => {
    api.flips
      .get(Number(id))
      .then((raw) => {
        setFlip(raw as Flip);
      })
      .catch(() => router.push("/flips"))
      .finally(() => setLoading(false));
  }, [id, router]);

  async function loadPurchasePlan(flipId: number) {
    setLoadingPlan(true);
    try {
      const plan = await api.flips.purchasePlan(flipId);
      setPurchasePlan(plan as PurchasePlan);
      setPurchased(new Set());
    } finally {
      setLoadingPlan(false);
    }
  }

  async function runCompatibilityCheck() {
    if (!flip) return;
    setCheckingCompat(true);
    try {
      const result = await api.flips.compatibilityCheck(flip.id);
      setCompatResult(result);
      setCompatChecked(true);
      // Load purchase plan alongside compat result so user can act immediately
      if (result.compatible !== false) {
        await loadPurchasePlan(flip.id);
      }
    } finally {
      setCheckingCompat(false);
    }
  }

  const allPurchased =
    purchasePlan !== null &&
    purchasePlan.items.length > 0 &&
    purchasePlan.items.every((item) => purchased.has(item.category));

  async function advanceStage() {
    if (!flip) return;
    const next = STAGE_NEXT[flip.stage];
    if (!next) return;
    if (next === "sold") {
      setShowSoldForm(true);
      return;
    }
    // Gate 1: run compat check first
    if (next === "ready_for_sale" && !compatChecked) {
      await runCompatibilityCheck();
      return;
    }
    // Gate 2: all purchases must be confirmed
    if (next === "ready_for_sale" && !allPurchased) {
      return;
    }
    setSaving(true);
    try {
      const updated = await api.flips.patch(flip.id, { stage: next });
      setFlip(updated as Flip);
      setCompatChecked(false);
      setCompatResult(null);
      setPurchasePlan(null);
      setPurchased(new Set());
      // After confirming all purchases and marking ready for sale, go straight to selling hub
      if (next === "ready_for_sale") {
        router.push("/selling");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleMarkSold() {
    if (!flip || !salePrice) return;
    setMarkingSold(true);
    try {
      await api.flips.markSold(flip.id, {
        actual_sale_price: parseFloat(salePrice),
        sale_platform: salePlatform,
      });
      const updated = (await api.flips.get(flip.id)) as Flip;
      setFlip(updated);
      setShowSoldForm(false);
    } finally {
      setMarkingSold(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading flip…
      </div>
    );
  }

  if (!flip) return null;

  const listing: Listing | undefined = flip.listing;
  const stageIdx = STAGES.findIndex((s) => s.key === flip.stage);
  const nextStage = STAGE_NEXT[flip.stage];

  return (
    <div className="flex flex-col h-full min-h-0 p-6 gap-5 max-w-3xl mx-auto w-full">
      {/* ══════════════════ Build Overview (page-level, pre-listing build process) ══════════════════ */}

      {/* ── Header ── */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push("/selling")}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back
        </button>
        <span className="text-slate-700">/</span>
        <span className="text-sm font-semibold text-slate-300">Flip #{flip.id}</span>
        <span
          className={`ml-auto px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
            flip.stage === "sold"
              ? "bg-emerald-500/20 text-emerald-400"
              : flip.stage === "ready_for_sale"
              ? "bg-blue-500/20 text-blue-400"
              : flip.stage === "building"
              ? "bg-amber-500/20 text-amber-400"
              : "bg-slate-700 text-slate-400"
          }`}
        >
          {flip.stage.replace(/_/g, " ")}
        </span>
      </div>

      {/* ── Stage progress bar ── */}
      <div className="flex items-center gap-0">
        {STAGES.map((s, i) => {
          const done = i < stageIdx;
          const active = i === stageIdx;
          return (
            <div key={s.key} className="flex items-center flex-1">
              <div
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium flex-1 justify-center ${
                  done
                    ? "bg-emerald-500/15 text-emerald-400"
                    : active
                    ? "bg-[#00dc82]/15 text-[#00dc82] ring-1 ring-[#00dc82]/40"
                    : "text-slate-600"
                }`}
              >
                {done && <Check className="w-3 h-3" />}
                {s.label}
              </div>
              {i < STAGES.length - 1 && (
                <ChevronRight className="w-3.5 h-3.5 text-slate-700 flex-shrink-0" />
              )}
            </div>
          );
        })}
      </div>

      {/* ── Listing card ── */}
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-semibold text-slate-200 leading-snug line-clamp-2">
            {listing?.title ?? `Listing #${flip.listing_id}`}
          </p>
          {listing?.url && (
            <a
              href={listing.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-shrink-0 text-slate-600 hover:text-slate-400 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>

        {listing && (
          <div className="flex flex-wrap gap-1.5">
            <SpecPill icon={<Cpu className="w-3 h-3" />} value={listing.cpu} />
            <SpecPill icon={<Monitor className="w-3 h-3" />} value={listing.gpu} />
            <SpecPill
              icon={<MemoryStick className="w-3 h-3" />}
              value={listing.ram_gb ? `${listing.ram_gb}GB ${listing.ram_type ?? ""}`.trim() : null}
            />
            <SpecPill
              icon={<HardDrive className="w-3 h-3" />}
              value={
                listing.storage_gb
                  ? `${listing.storage_gb}GB ${listing.storage_type ?? ""}`.trim()
                  : null
              }
            />
          </div>
        )}

        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="capitalize">{listing?.source_name}</span>
          <span>·</span>
          <span className="text-slate-400 font-mono">Paid £{flip.base_cost.toFixed(0)}</span>
        </div>
      </div>

      {/* ── Playbook + Upgrade Slots ── */}
      {flip.stage !== "sold" && (
        <UpgradeSection flip={flip} listing={listing} onFlipUpdated={setFlip} />
      )}

      {/* ── Sold form modal ── */}
      {showSoldForm && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0b1220] border border-slate-700 rounded-xl p-6 w-full max-w-sm flex flex-col gap-4">
            <p className="text-base font-semibold text-slate-200">Mark as Sold</p>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs text-slate-500">Sale price (£)</label>
              <input
                type="number"
                value={salePrice}
                onChange={(e) => setSalePrice(e.target.value)}
                placeholder="e.g. 350"
                className="bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 outline-none focus:border-[#00dc82] transition-colors"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs text-slate-500">Platform</label>
              <select
                value={salePlatform}
                onChange={(e) => setSalePlatform(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 outline-none focus:border-[#00dc82] transition-colors"
              >
                <option>eBay</option>
                <option>Facebook Marketplace</option>
                <option>Gumtree</option>
                <option>Preloved</option>
                <option>Other</option>
              </select>
            </div>

            {salePrice && (
              <div className="bg-slate-800/50 rounded-lg p-3 text-xs space-y-1">
                <div className="flex justify-between text-slate-500">
                  <span>Sale price</span>
                  <span>£{parseFloat(salePrice).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-slate-500">
                  <span>Platform fees</span>
                  <span>−£{(parseFloat(salePrice) * flip.platform_fee_pct).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-slate-500">
                  <span>Total cost</span>
                  <span>−£{flip.total_cost.toFixed(2)}</span>
                </div>
                <div className="flex justify-between font-semibold border-t border-slate-700 pt-1 mt-1">
                  <span className="text-slate-300">Profit</span>
                  <span
                    className={
                      parseFloat(salePrice) - flip.total_cost - parseFloat(salePrice) * flip.platform_fee_pct >= 0
                        ? "text-emerald-400"
                        : "text-red-400"
                    }
                  >
                    £
                    {(
                      parseFloat(salePrice) -
                      flip.total_cost -
                      parseFloat(salePrice) * flip.platform_fee_pct
                    ).toFixed(2)}
                  </span>
                </div>
              </div>
            )}

            <div className="flex gap-2 pt-1">
              <button
                onClick={() => setShowSoldForm(false)}
                className="flex-1 px-4 py-2 text-sm border border-slate-700 text-slate-400 rounded-md hover:border-slate-500 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleMarkSold}
                disabled={!salePrice || markingSold}
                className="flex-1 px-4 py-2 text-sm bg-emerald-500 text-white rounded-md font-semibold hover:bg-emerald-600 transition-colors disabled:opacity-40"
              >
                {markingSold ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Confirm Sale"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Compatibility check result ── */}
      {compatResult && (
        <div
          className={`rounded-xl border p-4 flex flex-col gap-3 ${
            compatResult.compatible === false
              ? "border-red-500/40 bg-red-500/5"
              : compatResult.compatible === true
              ? "border-emerald-500/40 bg-emerald-500/5"
              : "border-amber-500/40 bg-amber-500/5"
          }`}
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Compatibility Check
            </p>
            <span
              className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                compatResult.compatible === false
                  ? "bg-red-500/20 text-red-400"
                  : compatResult.compatible === true
                  ? "bg-emerald-500/20 text-emerald-400"
                  : "bg-amber-500/20 text-amber-400"
              }`}
            >
              {compatResult.compatible === false
                ? "Issues Found"
                : compatResult.compatible === true
                ? "Compatible"
                : "Check Incomplete"}
            </span>
          </div>

          <p className="text-sm text-slate-300">{compatResult.summary}</p>

          {compatResult.issues.length > 0 && (
            <div>
              <p className="text-[10px] text-red-400 uppercase tracking-wider mb-1 font-semibold">Incompatibilities</p>
              <ul className="space-y-1">
                {compatResult.issues.map((issue, i) => (
                  <li key={i} className="text-xs text-red-300 flex gap-2">
                    <span className="text-red-500 flex-shrink-0">✗</span>
                    {issue}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {compatResult.warnings.length > 0 && (
            <div>
              <p className="text-[10px] text-amber-400 uppercase tracking-wider mb-1 font-semibold">Warnings</p>
              <ul className="space-y-1">
                {compatResult.warnings.map((w, i) => (
                  <li key={i} className="text-xs text-amber-300 flex gap-2">
                    <span className="text-amber-500 flex-shrink-0">⚠</span>
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-[10px] text-slate-600">
            Evaluated by {compatResult.model_used} · Confidence: {compatResult.confidence}
          </p>
        </div>
      )}

      {/* ── Purchase plan ── */}
      {(purchasePlan || loadingPlan) && flip.stage === "building" && (
        <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Purchase Plan
            </p>
            {allPurchased && (
              <span className="text-xs font-bold text-emerald-400 flex items-center gap-1">
                <Check className="w-3 h-3" /> All purchased
              </span>
            )}
          </div>

          {loadingPlan && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading items…
            </div>
          )}

          {purchasePlan && (
            <div className="space-y-2">
              {purchasePlan.items.map((item) => {
                const done = purchased.has(item.category);
                return (
                  <div
                    key={item.category}
                    className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${
                      done
                        ? "border-emerald-500/30 bg-emerald-500/5"
                        : "border-slate-800 bg-slate-900/40"
                    }`}
                  >
                    <button
                      onClick={() =>
                        setPurchased((prev) => {
                          const next = new Set(prev);
                          done ? next.delete(item.category) : next.add(item.category);
                          return next;
                        })
                      }
                      className={`mt-0.5 w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center transition-colors ${
                        done
                          ? "bg-emerald-500 border-emerald-500"
                          : "border-slate-600 hover:border-slate-400"
                      }`}
                    >
                      {done && <Check className="w-2.5 h-2.5 text-white" />}
                    </button>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2">
                        <span className="text-[10px] text-slate-600 uppercase tracking-wider font-semibold">
                          {item.label}
                        </span>
                        <span className="text-xs font-mono text-slate-400">
                          £{item.price.toFixed(0)}
                        </span>
                      </div>
                      <p className={`text-sm font-medium mt-0.5 ${done ? "text-slate-500 line-through" : "text-slate-200"}`}>
                        {item.name}
                      </p>
                      {item.specs && (
                        <p className="text-[11px] text-slate-600 mt-0.5 line-clamp-1">{item.specs}</p>
                      )}
                    </div>

                    {item.url && (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-shrink-0 flex items-center gap-1 px-2.5 py-1 text-[11px] border border-slate-700 text-slate-400 rounded-md hover:border-slate-500 hover:text-slate-200 transition-colors"
                      >
                        Buy <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    )}
                  </div>
                );
              })}

              <div className="flex justify-between items-center pt-2 border-t border-slate-800">
                <span className="text-xs text-slate-500">Total spend</span>
                <span className="text-sm font-mono font-bold text-slate-200">
                  £{purchasePlan.total.toFixed(0)}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Advance stage button ── */}
      {nextStage && (
        <div className="flex items-center justify-end gap-3 pt-1">
          {/* Re-run check button once a result exists */}
          {compatChecked && flip.stage === "building" && (
            <button
              onClick={runCompatibilityCheck}
              disabled={checkingCompat}
              className="flex items-center gap-1.5 px-3 py-2 text-xs border border-slate-700 text-slate-400 rounded-lg hover:border-slate-500 transition-colors disabled:opacity-40"
            >
              {checkingCompat ? <Loader2 className="w-3 h-3 animate-spin" /> : "Re-check"}
            </button>
          )}
          <button
            onClick={advanceStage}
            disabled={
              saving ||
              checkingCompat ||
              (compatChecked && compatResult?.compatible === false) ||
              (compatChecked && flip.stage === "building" && !allPurchased)
            }
            className={`flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-lg transition-colors disabled:opacity-40 ${
              nextStage === "sold"
                ? "bg-emerald-500 text-white hover:bg-emerald-600"
                : "bg-[#00dc82] text-[#04120d] hover:bg-[#00b86d]"
            }`}
          >
            {checkingCompat ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Checking compatibility…</>
            ) : saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : compatChecked && flip.stage === "building" && !allPurchased ? (
              <>Tick all purchases to continue</>
            ) : compatChecked && flip.stage === "building" && allPurchased ? (
              <>Ready for Sale — Go to Selling Hub <ChevronRight className="w-4 h-4" /></>
            ) : (
              <>{STAGE_NEXT_LABEL[flip.stage]} <ChevronRight className="w-4 h-4" /></>
            )}
          </button>
        </div>
      )}

      {/* ══════════════════ eBay-listing tabs ══════════════════ */}
      <Tabs defaultValue="listing-content" className="flex flex-col gap-0">
        <TabsList>
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <TabsTrigger key={t.key} value={t.key}>
                <Icon className="w-3.5 h-3.5" /> {t.label}
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent value="listing-content">
          <ListingContentTab flip={flip} onFlipUpdated={setFlip} />
        </TabsContent>
        <TabsContent value="photos">
          <PhotosTab flip={flip} onFlipUpdated={setFlip} />
        </TabsContent>
        <TabsContent value="item-specifics">
          <ItemSpecificsTab flip={flip} onFlipUpdated={setFlip} />
        </TabsContent>
        <TabsContent value="pricing">
          <PricingTab flip={flip} onFlipUpdated={setFlip} />
        </TabsContent>
        <TabsContent value="dispatch">
          <DispatchTab flip={flip} onFlipUpdated={setFlip} />
        </TabsContent>
        <TabsContent value="live-listing">
          <LiveListingTab flip={flip} onFlipUpdated={setFlip} />
        </TabsContent>
        <TabsContent value="other">
          <OtherTab flip={flip} onFlipUpdated={setFlip} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
