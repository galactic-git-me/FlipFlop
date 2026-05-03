"use client";

import { useEffect, useState } from "react";
import { Tag, Copy, RefreshCw, CheckCircle, Sparkles, DollarSign, FileText, Image as ImageIcon, ExternalLink, PackageCheck, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FlippabilityScore } from "@/components/flippability-score";
import { SourceBadge } from "@/components/source-badge";
import { EmptyState } from "@/components/empty-state";
import { Flip } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const PLATFORM_FEES: Record<string, number> = { ebay: 0.127, facebook: 0, gumtree: 0.02 };
const PLATFORMS = ["ebay", "facebook", "gumtree"] as const;

export default function SellingPage() {
  const [flips, setFlips] = useState<Flip[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Flip | null>(null);
  const [platform, setPlatform] = useState<"ebay" | "facebook" | "gumtree">("ebay");
  const [titles, setTitles] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [selectedTitleIdx, setSelectedTitleIdx] = useState(0);
  const [generatingContent, setGeneratingContent] = useState(false);
  const [generatingImages, setGeneratingImages] = useState(false);
  const [images, setImages] = useState<string[]>([]);
  const [copied, setCopied] = useState<"title" | "desc" | null>(null);
  const [markingSold, setMarkingSold] = useState(false);
  const [salePrice, setSalePrice] = useState("");
  const [showSoldModal, setShowSoldModal] = useState(false);

  useEffect(() => {
    api.flips.list().then(data => {
      const activeFlips = (data as Flip[]).filter(f => f.stage !== "sold");
      setFlips(activeFlips);
      if (activeFlips.length > 0 && !selected) {
        setSelected(activeFlips[0]);
      }
    }).catch(() => setFlips([])).finally(() => setLoading(false));
  }, []);

  const generateContent = async () => {
    if (!selected) return;
    setGeneratingContent(true);
    setTitles([]);
    setDescription("");
    try {
      const result = await api.flips.generateListing(selected.id);
      setTitles(result.titles ?? []);
      setDescription(result.description ?? "");
      setSelectedTitleIdx(0);
    } catch {
      setTitles(["Error generating — check Hermes is online"]);
    } finally {
      setGeneratingContent(false);
    }
  };

  const generateImages = async () => {
    if (!selected) return;
    setGeneratingImages(true);
    setImages([]);
    try {
      const result = await api.flips.generateImages(selected.id);
      setImages(result.images ?? []);
    } catch {
      setImages([]);
    } finally {
      setGeneratingImages(false);
    }
  };

  const markSold = async () => {
    if (!selected || !salePrice) return;
    setMarkingSold(true);
    try {
      await api.flips.markSold(selected.id, {
        actual_sale_price: parseFloat(salePrice),
        sale_platform: platform,
      });
      setFlips(prev => prev.filter(f => f.id !== selected.id));
      setSelected(flips.find(f => f.id !== selected.id) ?? null);
      setShowSoldModal(false);
      setSalePrice("");
    } finally {
      setMarkingSold(false);
    }
  };

  const copyText = (text: string, type: "title" | "desc") => {
    navigator.clipboard.writeText(text);
    setCopied(type);
    setTimeout(() => setCopied(null), 2000);
  };

  const resale = selected?.current_estimated_resale ?? 0;
  const totalCost = selected?.total_cost ?? 0;
  const suggestedPrice = Math.round(resale * 1.05);
  const fee = suggestedPrice * PLATFORM_FEES[platform];
  const netProfit = suggestedPrice - fee - totalCost;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
        <RefreshCw className="w-4 h-4 animate-spin" /> Loading flips…
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <Tag className="w-5 h-5 text-yellow-400" /> Selling Toolkit
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">AI-generated listings · product image generation · profit tracking</p>
      </div>

      {flips.length === 0 ? (
        <EmptyState
          icon={Tag}
          title="No active flips ready to list"
          description='Complete Stage 3 of the Flip Wizard to move a flip here for listing.'
          action={{ label: "Go to Flips", onClick: () => window.location.href = "/flips" }}
        />
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Flip selector */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Select Flip to List</h3>
            {flips.map(flip => {
              const isActive = selected?.id === flip.id;
              return (
                <Card
                  key={flip.id}
                  hover
                  className={isActive ? "border-[#00dc82]/40" : ""}
                  onClick={() => {
                    setSelected(flip);
                    setTitles([]);
                    setDescription("");
                    setImages([]);
                  }}
                >
                  <CardContent className="pt-3">
                    <div className="flex items-center gap-3">
                      <FlippabilityScore score={(flip as unknown as { gem_score?: number }).gem_score ?? 0} size="sm" showLabel={false} />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-slate-200 line-clamp-2">
                          {(flip as unknown as { listing?: { title?: string } }).listing?.title ?? `Flip #${flip.id}`}
                        </p>
                        <p className="text-[10px] text-slate-500 mt-0.5">
                          Cost: {formatCurrency(flip.total_cost)} · Stage: {flip.stage.replace("_", " ")}
                        </p>
                      </div>
                      <div className="text-xs font-bold text-[#00dc82]">
                        {formatCurrency(flip.current_estimated_profit ?? 0)}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Content generation */}
          {selected && (
            <div className="xl:col-span-2 space-y-5">
              {/* Pricing */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <DollarSign className="w-3.5 h-3.5 text-[#00dc82]" /> Pricing Strategy
                    </CardTitle>
                    <Button variant="danger" size="sm" onClick={() => setShowSoldModal(true)}>
                      <PackageCheck className="w-3.5 h-3.5" /> Mark as Sold
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4 pt-0">
                  <div className="flex gap-2">
                    {PLATFORMS.map(p => (
                      <button
                        key={p}
                        onClick={() => setPlatform(p)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border capitalize transition-all ${
                          platform === p
                            ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30"
                            : "bg-[#0a1119] text-slate-500 border-[#1e2d45] hover:border-slate-600"
                        }`}
                      >
                        {p === "ebay" ? "eBay" : p.charAt(0).toUpperCase() + p.slice(1)}
                      </button>
                    ))}
                  </div>
                  <div className="grid grid-cols-4 gap-3">
                    {[
                      { label: "Total Cost", value: formatCurrency(totalCost), color: "text-slate-200" },
                      { label: "Suggested Price", value: formatCurrency(suggestedPrice), color: "text-slate-200" },
                      { label: "Platform Fee", value: `-${formatCurrency(Math.round(fee))}`, color: "text-red-400", sub: `${(PLATFORM_FEES[platform] * 100).toFixed(1)}%` },
                      { label: "Est. Net Profit", value: `+${formatCurrency(Math.round(netProfit))}`, color: "text-[#00dc82]" },
                    ].map(({ label, value, color, sub }) => (
                      <div key={label} className="p-3 bg-[#0a1119] rounded-xl border border-[#1e2d45] text-center">
                        <div className="text-xs text-slate-500">{label}</div>
                        <div className={`text-lg font-bold mt-1 ${color}`}>{value}</div>
                        {sub && <div className="text-[10px] text-slate-600">{sub}</div>}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* AI Images */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <ImageIcon className="w-3.5 h-3.5 text-pink-400" /> AI Product Images
                    </CardTitle>
                    <Button variant="secondary" size="sm" onClick={generateImages} disabled={generatingImages}>
                      <Sparkles className={`w-3.5 h-3.5 ${generatingImages ? "animate-spin" : ""}`} />
                      {generatingImages ? "Generating…" : images.length > 0 ? "Regenerate" : "Generate Images"}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  {images.length === 0 && !generatingImages && (
                    <div className="py-8 text-center text-slate-600 text-sm">
                      <ImageIcon className="w-8 h-8 mx-auto mb-2 opacity-30" />
                      Generate AI product photos — hero shots from multiple angles, spec callouts, studio lighting.
                      <br />
                      <span className="text-xs text-slate-700">Uses Stable Diffusion via Pollinations.ai (free)</span>
                    </div>
                  )}
                  {generatingImages && (
                    <div className="grid grid-cols-3 gap-3">
                      {[0, 1, 2].map(i => (
                        <div key={i} className="h-32 rounded-xl bg-[#0a1119] border border-[#1e2d45] animate-pulse" />
                      ))}
                    </div>
                  )}
                  {images.length > 0 && (
                    <div className="grid grid-cols-3 gap-3">
                      {images.map((url, i) => (
                        <div key={i} className="relative group">
                          <img src={url} alt={`Product shot ${i + 1}`} className="w-full h-32 object-cover rounded-xl border border-[#1e2d45]" />
                          <a
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <ExternalLink className="w-5 h-5 text-white" />
                          </a>
                          <div className="absolute bottom-1.5 left-2 text-[10px] text-white/70 font-medium">
                            {["Hero Shot", "Side View", "Detail"][i] ?? `View ${i + 1}`}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Generated Titles */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <Sparkles className="w-3.5 h-3.5 text-yellow-400" /> AI-Generated Listing Content
                    </CardTitle>
                    <Button variant="secondary" size="sm" onClick={generateContent} disabled={generatingContent}>
                      <Zap className={`w-3.5 h-3.5 ${generatingContent ? "animate-spin" : ""}`} />
                      {generatingContent ? "Generating…" : titles.length > 0 ? "Regenerate" : "Generate with Hermes"}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4 pt-0">
                  {titles.length === 0 && !generatingContent && (
                    <div className="py-6 text-center text-slate-600 text-sm">
                      Click "Generate with Hermes" to create optimised listing titles and description using the PC specs.
                    </div>
                  )}
                  {titles.length > 0 && (
                    <>
                      <div className="space-y-2">
                        <label className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Titles — click to select</label>
                        {titles.map((title, i) => (
                          <button
                            key={i}
                            onClick={() => setSelectedTitleIdx(i)}
                            className={`w-full text-left p-3 rounded-xl border text-sm transition-all ${
                              selectedTitleIdx === i
                                ? "border-[#00dc82]/40 bg-[#00dc82]/5 text-slate-200"
                                : "border-[#1e2d45] bg-[#0a1119] text-slate-400 hover:border-slate-600 hover:text-slate-300"
                            }`}
                          >
                            {selectedTitleIdx === i && <CheckCircle className="w-3 h-3 text-[#00dc82] inline mr-2" />}
                            {title}
                          </button>
                        ))}
                        <Button variant="secondary" size="sm" onClick={() => copyText(titles[selectedTitleIdx], "title")}>
                          {copied === "title" ? <><CheckCircle className="w-3.5 h-3.5 text-[#00dc82]" /> Copied!</> : <><Copy className="w-3.5 h-3.5" /> Copy Title</>}
                        </Button>
                      </div>

                      <div className="space-y-2 pt-2">
                        <label className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Description</label>
                        <pre className="text-xs text-slate-400 whitespace-pre-wrap font-mono bg-[#0a1119] rounded-xl p-4 border border-[#1e2d45] leading-relaxed max-h-64 overflow-y-auto">
                          {description}
                        </pre>
                        <Button variant="secondary" size="sm" onClick={() => copyText(description, "desc")}>
                          {copied === "desc" ? <><CheckCircle className="w-3.5 h-3.5 text-[#00dc82]" /> Copied!</> : <><Copy className="w-3.5 h-3.5" /> Copy Description</>}
                        </Button>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* Mark Sold Modal */}
      {showSoldModal && selected && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-sm border-[#00dc82]/30">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PackageCheck className="w-4 h-4 text-[#00dc82]" /> Mark as Sold
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-0">
              <p className="text-sm text-slate-400">
                Record the actual sale to track real profit and train the intelligence engine.
              </p>
              <div>
                <label className="text-xs text-slate-500 mb-1.5 block">Actual Sale Price (£)</label>
                <input
                  type="number"
                  value={salePrice}
                  onChange={e => setSalePrice(e.target.value)}
                  placeholder="e.g. 220"
                  className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 outline-none focus:border-[#00dc82]/50"
                  autoFocus
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-2 block">Platform Sold On</label>
                <div className="flex gap-2">
                  {PLATFORMS.map(p => (
                    <button
                      key={p}
                      onClick={() => setPlatform(p)}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium border capitalize transition-all ${
                        platform === p
                          ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30"
                          : "bg-[#0a1119] text-slate-500 border-[#1e2d45]"
                      }`}
                    >
                      {p === "ebay" ? "eBay" : p.charAt(0).toUpperCase() + p.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
              {salePrice && (
                <div className="p-3 bg-[#00dc82]/8 rounded-xl border border-[#00dc82]/20 text-center">
                  <div className="text-xs text-slate-500">Actual profit</div>
                  <div className="text-xl font-black text-[#00dc82]">
                    +{formatCurrency(parseFloat(salePrice) - (parseFloat(salePrice) * PLATFORM_FEES[platform]) - (selected.total_cost ?? 0))}
                  </div>
                </div>
              )}
              <div className="flex gap-2">
                <Button variant="primary" className="flex-1" onClick={markSold} disabled={markingSold || !salePrice}>
                  {markingSold ? "Saving…" : "Confirm Sale"}
                </Button>
                <Button variant="ghost" className="flex-1" onClick={() => setShowSoldModal(false)}>Cancel</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
