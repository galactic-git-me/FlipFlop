"use client";

import { useEffect, useState, use } from "react";
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
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";

type FlipStage = "selected" | "building" | "ready_for_sale" | "sold";

interface Listing {
  id: number;
  title: string;
  price: number;
  url: string;
  source_name: string;
  cpu?: string;
  gpu?: string;
  ram_gb?: number;
  ram_type?: string;
  storage_gb?: number;
  storage_type?: string;
  image_urls: string[];
  gem_score: number;
  estimated_resale?: number;
  estimated_profit?: number;
}

interface Flip {
  id: number;
  listing_id: number;
  listing?: Listing;
  stage: FlipStage;
  base_cost: number;
  upgrade_cost: number;
  total_cost: number;
  platform_fee_pct: number;
  initial_estimated_resale?: number;
  current_estimated_resale?: number;
  initial_estimated_profit?: number;
  current_estimated_profit?: number;
  actual_sale_price?: number;
  actual_profit?: number;
  sale_platform?: string;
  generated_title?: string;
  notes?: string;
  created_at: string;
  sold_at?: string;
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

export default function FlipDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [flip, setFlip] = useState<Flip | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notes, setNotes] = useState("");
  const [generatingListing, setGeneratingListing] = useState(false);
  const [generatedTitle, setGeneratedTitle] = useState<string | null>(null);
  const [generatedDescription, setGeneratedDescription] = useState<string | null>(null);

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
        const f = raw as Flip;
        setFlip(f);
        setNotes(f.notes ?? "");
        setGeneratedTitle(f.generated_title ?? null);
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

  async function saveNotes() {
    if (!flip) return;
    setSaving(true);
    try {
      await api.flips.patch(flip.id, { notes });
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

  async function handleGenerateListing() {
    if (!flip) return;
    setGeneratingListing(true);
    try {
      const result = await api.flips.generateListing(flip.id);
      setGeneratedTitle(result.titles[0] ?? null);
      setGeneratedDescription(result.description ?? null);
      const updated = await api.flips.get(flip.id);
      setFlip(updated as Flip);
    } finally {
      setGeneratingListing(false);
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

  const listing = flip.listing;
  const stageIdx = STAGES.findIndex((s) => s.key === flip.stage);
  const nextStage = STAGE_NEXT[flip.stage];
  const fees = flip.current_estimated_resale
    ? flip.current_estimated_resale * flip.platform_fee_pct
    : 0;

  return (
    <div className="flex flex-col h-full min-h-0 p-6 gap-5 max-w-3xl mx-auto w-full">
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

        {/* ── Financials ── */}
        <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Financials</p>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-500">Base cost</span>
              <span className="font-mono text-slate-300">£{flip.base_cost.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Upgrade cost</span>
              <span className="font-mono text-slate-300">£{flip.upgrade_cost.toFixed(2)}</span>
            </div>
            <div className="flex justify-between border-t border-slate-800 pt-2">
              <span className="text-slate-400 font-medium">Total in</span>
              <span className="font-mono text-slate-200 font-semibold">£{flip.total_cost.toFixed(2)}</span>
            </div>

            {flip.stage !== "sold" && flip.current_estimated_resale && (
              <>
                <div className="flex justify-between text-xs text-slate-600 pt-1">
                  <span>Est. resale</span>
                  <span className="font-mono">£{flip.current_estimated_resale.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-xs text-slate-600">
                  <span>eBay fees (~{(flip.platform_fee_pct * 100).toFixed(1)}%)</span>
                  <span className="font-mono">−£{fees.toFixed(2)}</span>
                </div>
                <div className="flex justify-between border-t border-slate-800 pt-2">
                  <span className="text-[#00dc82] font-medium">Est. profit</span>
                  <span className="font-mono text-[#00dc82] font-bold">
                    £{(flip.current_estimated_profit ?? 0).toFixed(2)}
                  </span>
                </div>
              </>
            )}

            {flip.stage === "sold" && (
              <>
                <div className="flex justify-between border-t border-slate-800 pt-2">
                  <span className="text-slate-400">Sold for</span>
                  <span className="font-mono text-slate-200">£{flip.actual_sale_price?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-emerald-400 font-medium">Actual profit</span>
                  <span
                    className={`font-mono font-bold ${
                      (flip.actual_profit ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    £{flip.actual_profit?.toFixed(2)}
                  </span>
                </div>
                <div className="text-xs text-slate-600">via {flip.sale_platform}</div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── Listing generator (shown when ready_for_sale) ── */}
      {(flip.stage === "ready_for_sale" || flip.stage === "building") && (
        <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">eBay Listing</p>
            <button
              onClick={handleGenerateListing}
              disabled={generatingListing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#00dc82] text-[#04120d] rounded-md font-semibold hover:bg-[#00b86d] transition-colors disabled:opacity-40"
            >
              {generatingListing ? (
                <><Loader2 className="w-3 h-3 animate-spin" /> Generating…</>
              ) : (
                <><Zap className="w-3 h-3" /> {generatedTitle ? "Regenerate" : "Generate Listing"}</>
              )}
            </button>
          </div>

          {generatedTitle && (
            <div className="space-y-2">
              <div>
                <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Title</p>
                <p className="text-sm text-slate-200 font-medium bg-slate-800/50 rounded p-2">
                  {generatedTitle}
                </p>
              </div>
              {generatedDescription && (
                <div>
                  <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Description preview</p>
                  <div
                    className="text-xs text-slate-400 bg-slate-800/50 rounded p-2 max-h-32 overflow-y-auto leading-relaxed"
                    dangerouslySetInnerHTML={{ __html: generatedDescription }}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Notes ── */}
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-2">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Notes</p>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={saveNotes}
          placeholder="Add notes about this flip…"
          rows={3}
          className="w-full bg-transparent text-sm text-slate-300 placeholder-slate-700 resize-none outline-none focus:text-slate-200 transition-colors"
        />
      </div>

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
    </div>
  );
}
