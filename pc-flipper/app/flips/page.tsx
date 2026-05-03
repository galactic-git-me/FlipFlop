"use client";

import { useEffect, useState } from "react";
import { Zap, Gem, Package, Box, ChevronRight, CheckCircle, ExternalLink, Plus, RefreshCw, Sparkles, ImageIcon, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ClassificationBadge } from "@/components/classification-badge";
import { FlippabilityScore } from "@/components/flippability-score";
import { SourceBadge } from "@/components/source-badge";
import { EmptyState } from "@/components/empty-state";
import { Listing, Part, Flip, FlipStage } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

type Stage = 1 | 2 | 3;

const FLIP_STAGES: { stage: FlipStage; label: string; icon: React.ReactNode }[] = [
  { stage: "selected", label: "Selected", icon: <Zap className="w-3.5 h-3.5" /> },
  { stage: "building", label: "Building", icon: <Package className="w-3.5 h-3.5" /> },
  { stage: "ready_for_sale", label: "Ready", icon: <CheckCircle className="w-3.5 h-3.5" /> },
  { stage: "sold", label: "Sold", icon: <Zap className="w-3.5 h-3.5" /> },
];

export default function FlipsPage() {
  // Builder state (3-stage wizard for new flips)
  const [builderStage, setBuilderStage] = useState<Stage>(1);
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const [selectedUpgrades, setSelectedUpgrades] = useState<Part[]>([]);
  const [selectedCase, setSelectedCase] = useState<Part | null>(null);

  // Data
  const [flips, setFlips] = useState<Flip[]>([]);
  const [listings, setListings] = useState<Listing[]>([]);
  const [parts, setParts] = useState<Part[]>([]);
  const [cases, setCases] = useState<Part[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        const [f, l, p, c] = await Promise.all([
          api.flips.list() as Promise<Flip[]>,
          api.listings.list({ sort_by: "gem_score", sort_desc: "true", limit: "30", status: "active", classification: "amazing_gem" }) as Promise<Listing[]>,
          api.parts.list() as Promise<Part[]>,
          api.parts.cases({}) as Promise<Part[]>,
        ]);
        // Also grab gems
        const gems = await api.listings.list({ sort_by: "gem_score", sort_desc: "true", limit: "30", status: "active" }) as Listing[];
        setFlips(f);
        setListings(gems.filter(l => l.classification === "amazing_gem" || l.classification === "gem"));
        setParts(p.filter(p => p.category !== "case"));
        setCases(c);
      } catch { /* show empty state */ }
      setLoading(false);
    };
    init();
  }, []);

  const upgradeCost = selectedUpgrades.reduce((s, p) => s + (p.price_used ?? p.price_refurb ?? p.price ?? 0), 0);
  const caseCost = selectedCase ? (selectedCase.price_new ?? selectedCase.price ?? 0) : 0;
  const totalCost = (selectedListing?.price ?? 0) + upgradeCost + caseCost;
  const estimatedResale = (selectedListing?.estimated_resale ?? 0) + selectedUpgrades.reduce((s, p) => s + p.resale_value_add, 0);
  const fees = estimatedResale * 0.127;
  const estimatedProfit = estimatedResale - totalCost - fees;

  const toggleUpgrade = (part: Part) => {
    setSelectedUpgrades(prev =>
      prev.find(p => p.id === part.id) ? prev.filter(p => p.id !== part.id) : [...prev, part]
    );
  };

  const startFlip = async () => {
    if (!selectedListing) return;
    await api.flips.create({ listing_id: selectedListing.id });
    const updated = await api.flips.list() as Flip[];
    setFlips(updated);
    setBuilderStage(1);
    setSelectedListing(null);
    setSelectedUpgrades([]);
    setSelectedCase(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-3 text-slate-500 text-sm">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading…
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <Zap className="w-5 h-5 text-yellow-400" /> Flip Builder
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">3 stages: pick a base unit → add upgrades → choose a case</p>
      </div>

      {/* 3-Stage Wizard */}
      <Card className="border-[#1e3a5a]">
        {/* Stage progress bar */}
        <div className="flex items-center px-5 pt-5 pb-0 gap-2">
          {([1, 2, 3] as Stage[]).map((s, i) => {
            const labels = ["1. Base Unit", "2. Upgrades", "3. Case"];
            const done = builderStage > s;
            const active = builderStage === s;
            return (
              <div key={s} className="flex items-center gap-2 flex-1">
                <button
                  onClick={() => s < builderStage && setBuilderStage(s)}
                  className={`flex items-center gap-2 flex-1 py-2 px-3 rounded-xl border transition-all text-xs font-semibold ${
                    active ? "bg-[#00dc82]/10 border-[#00dc82]/40 text-[#00dc82]"
                    : done ? "bg-emerald-400/8 border-emerald-400/25 text-emerald-400"
                    : "border-[#1e2d45] text-slate-600"
                  }`}
                >
                  {done ? <CheckCircle className="w-3.5 h-3.5" /> : <span className="w-3.5 h-3.5 rounded-full border-2 border-current flex-shrink-0" />}
                  {labels[i]}
                </button>
                {i < 2 && <ChevronRight className="w-4 h-4 text-slate-700 flex-shrink-0" />}
              </div>
            );
          })}
        </div>

        {/* Stage 1 — Pick base unit */}
        {builderStage === 1 && (
          <CardContent className="pt-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
              <Gem className="w-4 h-4 text-[#00dc82]" /> Select a gem to flip
            </h3>
            {listings.length === 0 ? (
              <EmptyState icon={Gem} title="No gems available" description="Run a scan on the Opportunities page first to populate gems." />
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {listings.map(l => (
                  <button
                    key={l.id}
                    onClick={() => setSelectedListing(l)}
                    className={`w-full flex items-center gap-3 p-3 rounded-xl border text-left transition-all ${
                      selectedListing?.id === l.id ? "border-[#00dc82]/50 bg-[#00dc82]/8" : "border-[#1e2d45] bg-[#0a1119] hover:border-slate-600"
                    }`}
                  >
                    <FlippabilityScore score={l.gem_score} size="sm" />
                    {l.image_urls[0] && <img src={l.image_urls[0]} alt="" className="w-10 h-10 rounded-lg object-cover flex-shrink-0" />}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-slate-200 line-clamp-1">{l.title}</p>
                      <p className="text-[10px] text-slate-500 mt-0.5 font-mono">{[l.cpu, l.ram_gb ? `${l.ram_gb}GB` : null, l.gpu ?? "No GPU"].filter(Boolean).join(" · ")}</p>
                    </div>
                    <SourceBadge sourceName={l.source_name} url={l.url} />
                    <ClassificationBadge classification={l.classification} />
                    <div className="text-right flex-shrink-0">
                      <div className="text-sm font-bold text-slate-200">{formatCurrency(l.price)}</div>
                      <div className="text-xs text-[#00dc82]">+{formatCurrency(l.estimated_profit ?? 0)}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
            <div className="mt-4 flex justify-end">
              <Button variant="primary" disabled={!selectedListing} onClick={() => setBuilderStage(2)}>
                Next: Choose Upgrades <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        )}

        {/* Stage 2 — Upgrades */}
        {builderStage === 2 && (
          <CardContent className="pt-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
              <Package className="w-4 h-4 text-blue-400" /> Select upgrade parts (optional)
            </h3>
            <p className="text-xs text-slate-500 mb-3">Click parts to add them to your build. Prices are used/refurb market rates.</p>
            {parts.length === 0 ? (
              <EmptyState icon={Package} title="No parts tracked" description="Run the parts swarm from the Parts page first." />
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {parts.map(p => {
                  const chosen = selectedUpgrades.some(u => u.id === p.id);
                  const price = p.price_used ?? p.price_refurb ?? p.price ?? 0;
                  return (
                    <button
                      key={p.id}
                      onClick={() => toggleUpgrade(p)}
                      className={`w-full flex items-center gap-3 p-3 rounded-xl border text-left transition-all ${
                        chosen ? "border-blue-400/40 bg-blue-400/8" : "border-[#1e2d45] bg-[#0a1119] hover:border-slate-600"
                      }`}
                    >
                      {chosen ? <CheckCircle className="w-4 h-4 text-blue-400 flex-shrink-0" /> : <Plus className="w-4 h-4 text-slate-600 flex-shrink-0" />}
                      <div className="flex-1 min-w-0">
                        <span className="text-xs font-semibold text-slate-300">{p.name}</span>
                        {p.specs && <span className="text-[10px] text-slate-500 ml-2 font-mono">{p.specs}</span>}
                      </div>
                      <SourceBadge sourceName={p.source_site ?? "eBay"} url={p.source_url} />
                      <span className={`text-sm font-bold ${chosen ? "text-blue-400" : "text-slate-300"}`}>{formatCurrency(price)}</span>
                    </button>
                  );
                })}
              </div>
            )}
            <div className="mt-4 flex justify-between">
              <Button variant="ghost" size="sm" onClick={() => setBuilderStage(1)}>← Back</Button>
              <Button variant="primary" onClick={() => setBuilderStage(3)}>
                Next: Choose Case <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        )}

        {/* Stage 3 — Case */}
        {builderStage === 3 && (
          <CardContent className="pt-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
              <Box className="w-4 h-4 text-purple-400" /> Choose a themed case (optional)
            </h3>
            {cases.length === 0 ? (
              <EmptyState icon={Box} title="No cases catalogued" description="Run the cases swarm from the Cases page to scan for sci-fi themed cases." />
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3 max-h-80 overflow-y-auto">
                {/* No case option */}
                <button
                  onClick={() => setSelectedCase(null)}
                  className={`flex flex-col items-center justify-center p-4 rounded-xl border text-center transition-all ${
                    !selectedCase ? "border-slate-500 bg-slate-700/20 text-slate-300" : "border-[#1e2d45] bg-[#0a1119] text-slate-600 hover:border-slate-600"
                  }`}
                >
                  <Box className="w-6 h-6 mb-2 opacity-40" />
                  <span className="text-xs font-medium">No case</span>
                  <span className="text-[10px] text-slate-600 mt-0.5">Use existing</span>
                </button>
                {cases.slice(0, 11).map(c => (
                  <button
                    key={c.id}
                    onClick={() => setSelectedCase(selectedCase?.id === c.id ? null : c)}
                    className={`flex flex-col items-start p-3 rounded-xl border text-left transition-all ${
                      selectedCase?.id === c.id ? "border-purple-400/50 bg-purple-400/8" : "border-[#1e2d45] bg-[#0a1119] hover:border-slate-600"
                    }`}
                  >
                    {c.image_url && <img src={c.image_url} alt="" className="w-full h-20 object-cover rounded-lg mb-2" />}
                    <span className="text-[10px] font-semibold text-purple-300">{c.theme}</span>
                    <span className="text-xs text-slate-300 line-clamp-2 leading-snug mt-0.5">{c.name}</span>
                    <SourceBadge sourceName={c.source_site ?? ""} url={c.source_url} className="mt-1.5" />
                    <span className="text-sm font-bold text-slate-200 mt-1">{formatCurrency(c.price_new ?? c.price ?? 0)}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Cost summary */}
            <div className="mt-4 p-4 bg-[#0a1119] rounded-xl border border-[#1e2d45] space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Flip Summary</h4>
              <div className="space-y-1.5 text-xs">
                <CostRow label={`Base unit — ${selectedListing?.title.slice(0, 40)}…`} value={selectedListing?.price ?? 0} />
                {selectedUpgrades.map(u => (
                  <CostRow key={u.id} label={u.name} value={u.price_used ?? u.price_refurb ?? u.price ?? 0} />
                ))}
                {selectedCase && <CostRow label={`Case — ${selectedCase.name.slice(0, 35)}…`} value={caseCost} />}
                <CostRow label="eBay fees (~12.7%)" value={fees} dimmed />
                <div className="border-t border-[#1e2d45] pt-2 flex justify-between font-semibold text-slate-200">
                  <span>Total Cost</span><span>{formatCurrency(totalCost)}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Est. Resale</span><span>{formatCurrency(estimatedResale)}</span>
                </div>
                <div className={`flex justify-between text-base font-black pt-1 ${estimatedProfit > 0 ? "text-[#00dc82]" : "text-red-400"}`}>
                  <span>Est. Profit</span>
                  <span>{estimatedProfit > 0 ? "+" : ""}{formatCurrency(estimatedProfit)}</span>
                </div>
              </div>
            </div>

            <div className="mt-4 flex justify-between">
              <Button variant="ghost" size="sm" onClick={() => setBuilderStage(2)}>← Back</Button>
              <Button variant="primary" disabled={!selectedListing} onClick={startFlip}>
                <Zap className="w-4 h-4" /> Start This Flip
              </Button>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Active flips list */}
      {flips.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Active Flips ({flips.length})</h2>
          <div className="space-y-3">
            {flips.map(flip => <ActiveFlipRow key={flip.id} flip={flip} />)}
          </div>
        </div>
      )}
    </div>
  );
}

function ActiveFlipRow({ flip }: { flip: Flip }) {
  const stageIdx = FLIP_STAGES.findIndex(s => s.stage === flip.stage);
  const profit = flip.current_estimated_profit ?? 0;
  const [generatingImages, setGeneratingImages] = useState(false);
  const [generatedImages, setGeneratedImages] = useState<string[]>([]);
  const [refImages, setRefImages] = useState<string[]>([]);
  const [showImages, setShowImages] = useState(false);
  const [caseTheme, setCaseTheme] = useState("");

  const handleGenerateImages = async () => {
    setGeneratingImages(true);
    setShowImages(true);
    try {
      const res = await fetch(`http://localhost:8000/api/flips/${flip.id}/generate-images`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_theme: caseTheme || null }),
      });
      const data = await res.json();
      setGeneratedImages(data.images ?? []);
      setRefImages(data.reference_images ?? []);
    } catch {
      setGeneratedImages([]);
    } finally {
      setGeneratingImages(false);
    }
  };

  const listing = flip.listing;
  const thumbUrl = listing?.image_urls?.[0];

  return (
    <Card>
      <CardContent className="pt-4 space-y-3">
        {/* Main row */}
        <div className="flex items-center gap-4">
          {/* Thumbnail */}
          <div className="w-14 h-14 rounded-xl overflow-hidden bg-[#080f1a] flex-shrink-0">
            {thumbUrl ? (
              <img src={thumbUrl} alt="" className="w-full h-full object-contain" />
            ) : (
              <div className="w-full h-full flex items-center justify-center opacity-20">
                <Gem className="w-5 h-5 text-slate-400" />
              </div>
            )}
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-200 line-clamp-1">{listing?.title ?? `Flip #${flip.id}`}</p>
            <div className="flex items-center gap-2 mt-1.5">
              {FLIP_STAGES.map((s, i) => (
                <div key={s.stage} className="flex items-center gap-1">
                  <div className={`w-2 h-2 rounded-full ${i <= stageIdx ? "bg-[#00dc82]" : "bg-[#1e2d45]"}`} />
                  <span className={`text-[10px] ${i === stageIdx ? "text-[#00dc82] font-semibold" : "text-slate-600"}`}>{s.label}</span>
                  {i < FLIP_STAGES.length - 1 && <span className="text-slate-700 text-[10px]">›</span>}
                </div>
              ))}
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <div className="text-xs text-slate-500">Total Cost</div>
            <div className="text-sm font-bold text-slate-200">{formatCurrency(flip.total_cost)}</div>
          </div>
          <div className="text-right flex-shrink-0">
            <div className="text-xs text-slate-500">Est. Profit</div>
            <div className={`text-sm font-bold ${profit > 100 ? "text-[#00dc82]" : profit > 0 ? "text-amber-400" : "text-red-400"}`}>
              {profit > 0 ? "+" : ""}{formatCurrency(profit)}
            </div>
          </div>
        </div>

        {/* Generate images section */}
        <div className="border-t border-white/[0.05] pt-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Sparkles className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
            <span className="text-[11px] text-slate-500 font-medium">AI Marketing Images</span>
            <input
              type="text"
              placeholder="Case theme (e.g. cyberpunk, stealth, white)"
              value={caseTheme}
              onChange={e => setCaseTheme(e.target.value)}
              className="flex-1 min-w-32 bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-300 placeholder:text-slate-600 focus:outline-none focus:border-purple-400/40"
            />
            <Button
              variant="ghost" size="sm"
              onClick={handleGenerateImages}
              disabled={generatingImages}
              className="text-purple-400 hover:text-purple-300 hover:bg-purple-400/10 border border-purple-400/20"
            >
              {generatingImages
                ? <><RefreshCw className="w-3 h-3 animate-spin" /> Generating…</>
                : <><ImageIcon className="w-3 h-3" /> Generate 6 shots</>
              }
            </Button>
            {generatedImages.length > 0 && (
              <button onClick={() => setShowImages(v => !v)} className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors">
                {showImages ? "hide" : "show"} images
              </button>
            )}
          </div>

          {/* Image gallery */}
          {showImages && (
            <div className="mt-3 space-y-3">
              {/* Reference images from original listing */}
              {refImages.length > 0 && (
                <div>
                  <p className="text-[10px] text-slate-600 mb-1.5 uppercase tracking-wider">Original listing photos</p>
                  <div className="flex gap-2 overflow-x-auto pb-1">
                    {refImages.map((url, i) => (
                      <img key={i} src={url} alt="" className="h-20 w-auto rounded-lg object-contain bg-[#080f1a] flex-shrink-0 border border-white/[0.05]" />
                    ))}
                  </div>
                </div>
              )}
              {/* Generated images */}
              {generatingImages ? (
                <div className="flex items-center gap-2 text-xs text-slate-500 py-4">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-purple-400" />
                  Generating 6 AI shots — this takes ~15 seconds…
                </div>
              ) : generatedImages.length > 0 ? (
                <div>
                  <p className="text-[10px] text-slate-600 mb-1.5 uppercase tracking-wider">AI-generated marketing shots</p>
                  <div className="grid grid-cols-3 gap-2">
                    {generatedImages.map((url, i) => (
                      <div key={i} className="relative group">
                        <img
                          src={url}
                          alt={`AI shot ${i + 1}`}
                          className="w-full rounded-lg object-cover aspect-video bg-[#080f1a] border border-white/[0.05]"
                          loading="lazy"
                        />
                        <a
                          href={url}
                          download={`pc-flip-${flip.id}-shot-${i + 1}.jpg`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg text-[10px] text-white font-medium"
                        >
                          Download
                        </a>
                      </div>
                    ))}
                  </div>
                  <p className="text-[9px] text-slate-700 mt-2">
                    Generated by Pollinations.ai — free to use for marketing. Download and upload directly to eBay/Facebook.
                  </p>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function CostRow({ label, value, dimmed }: { label: string; value: number; dimmed?: boolean }) {
  return (
    <div className={`flex justify-between ${dimmed ? "text-slate-600" : "text-slate-400"}`}>
      <span className="truncate max-w-xs">{label}</span>
      <span className="flex-shrink-0 ml-4">{formatCurrency(value)}</span>
    </div>
  );
}
