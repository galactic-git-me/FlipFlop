"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Sparkles, DollarSign, TrendingUp, AlertCircle, Check, Zap, Package, Send, Upload, Copy, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, BuildComponent, ManualBuild } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { BuildListingTemplate } from "@/components/build-listing-template";

interface ComponentEntry {
  slot: string;
  name: string;
  price_paid: number;
  source: string;
  condition: "new" | "used" | "refurb";
  notes: string;
  part_id?: number;
  market_price?: number;
  market_status?: "checking" | "found" | "not_found" | "idle";
}

interface ComponentPricing {
  component_name: string;
  market_price_low: number;
  market_price_high: number;
  market_price_avg: number;
  source: string;
  fair_price: number;
  deal_score: number;
}

const COMPONENT_SLOTS = [
  { slot: "cpu", label: "CPU / Processor", icon: "🖥️", required: true },
  { slot: "motherboard", label: "Motherboard", icon: "🔌", required: true },
  { slot: "ram", label: "RAM / Memory", icon: "💾", required: true },
  { slot: "ssd", label: "Storage (SSD/HDD)", icon: "💿", required: true },
  { slot: "psu", label: "Power Supply", icon: "⚡", required: true },
  { slot: "gpu", label: "Graphics Card (GPU)", icon: "🎮", required: false },
  { slot: "cooler", label: "CPU Cooler", icon: "❄️", required: false },
  { slot: "case", label: "PC Case", icon: "📦", required: false },
];

export default function AddBuildPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [buildName, setBuildName] = useState("");
  const [components, setComponents] = useState<ComponentEntry[]>([
    { slot: "cpu", name: "", price_paid: 0, source: "eBay", condition: "used", notes: "" },
    { slot: "motherboard", name: "", price_paid: 0, source: "eBay", condition: "used", notes: "" },
    { slot: "ram", name: "", price_paid: 0, source: "eBay", condition: "used", notes: "" },
    { slot: "ssd", name: "", price_paid: 0, source: "eBay", condition: "used", notes: "" },
    { slot: "psu", name: "", price_paid: 0, source: "eBay", condition: "used", notes: "" },
  ]);
  const [saving, setSaving] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [evaluation, setEvaluation] = useState<any>(null);
  const [showEval, setShowEval] = useState(false);
  const [pricingLookups, setPricingLookups] = useState<Record<number, ComponentPricing | null>>({});
  const [showJsonModal, setShowJsonModal] = useState(false);
  const [jsonCopied, setJsonCopied] = useState(false);

  const JSON_EXAMPLE = {
    buildName: "Gaming PC #1",
    components: [
      { slot: "cpu", name: "Intel Core i7-10700K", price_paid: 250, source: "eBay", condition: "used", notes: "" },
      { slot: "motherboard", name: "ASUS ROG STRIX Z490-E", price_paid: 180, source: "eBay", condition: "refurb", notes: "" },
      { slot: "ram", name: "Corsair Vengeance 32GB DDR4 3600MHz", price_paid: 120, source: "Amazon", condition: "new", notes: "" },
      { slot: "ssd", name: "Samsung 970 EVO Plus 1TB", price_paid: 90, source: "eBay", condition: "used", notes: "" },
      { slot: "psu", name: "Corsair RM850x 850W Gold", price_paid: 100, source: "eBay", condition: "used", notes: "" },
      { slot: "gpu", name: "NVIDIA RTX 3070 8GB", price_paid: 350, source: "eBay", condition: "used", notes: "slight cosmetic wear" }
    ]
  };

  const handleJsonFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const data = JSON.parse(text);

      if (!data.buildName || !data.components || !Array.isArray(data.components)) {
        alert("Invalid JSON format. Please check the example and try again.");
        return;
      }

      setBuildName(data.buildName);
      const importedComponents = data.components
        .filter((c: any) => c.slot && c.name)
        .map((c: any) => ({
          slot: c.slot,
          name: c.name || "",
          price_paid: parseFloat(c.price_paid) || 0,
          source: c.source || "eBay",
          condition: (c.condition || "used") as "new" | "used" | "refurb",
          notes: c.notes || "",
          part_id: c.part_id,
        }));

      if (importedComponents.length > 0) {
        setComponents(importedComponents);
        setShowJsonModal(false);
      } else {
        alert("No valid components found in the JSON file.");
      }
    } catch (error) {
      alert("Error parsing JSON file. Please check the format and try again.");
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const copyJsonExample = () => {
    navigator.clipboard.writeText(JSON.stringify(JSON_EXAMPLE, null, 2));
    setJsonCopied(true);
    setTimeout(() => setJsonCopied(false), 2000);
  };

  const totalCost = components.reduce((sum, c) => sum + (c.price_paid || 0), 0);

  const checkMarketPrice = async (index: number, componentName: string) => {
    if (!componentName.trim()) return;

    updateComponent(index, "market_status", "checking");
    try {
      const listings = await api.listings.list({ q: componentName }) as any[];
      if (listings && listings.length > 0) {
        const prices = listings
          .filter((l: any) => l.price && l.price > 0)
          .slice(0, 10)
          .map((l: any) => l.price);

        if (prices.length > 0) {
          const low = Math.min(...prices);
          const high = Math.max(...prices);
          const avg = prices.reduce((a, b) => a + b) / prices.length;

          setPricingLookups(prev => ({
            ...prev,
            [index]: {
              component_name: componentName,
              market_price_low: low,
              market_price_high: high,
              market_price_avg: avg,
              source: "ebay",
              fair_price: avg,
              deal_score: components[index].price_paid > avg ? -25 : (avg - components[index].price_paid) / avg * 100,
            }
          }));
          updateComponent(index, "market_status", "found");
          updateComponent(index, "market_price", avg);
        } else {
          updateComponent(index, "market_status", "not_found");
        }
      } else {
        updateComponent(index, "market_status", "not_found");
      }
    } catch {
      updateComponent(index, "market_status", "not_found");
    }
  };

  const addComponent = () => {
    const unused = COMPONENT_SLOTS.find(
      s => !components.find(c => c.slot === s.slot)
    );
    if (unused) {
      setComponents([
        ...components,
        {
          slot: unused.slot,
          name: "",
          price_paid: 0,
          source: "eBay",
          condition: "used",
          notes: "",
        },
      ]);
    }
  };

  const updateComponent = (index: number, field: keyof ComponentEntry, value: any) => {
    const updated = [...components];
    updated[index] = { ...updated[index], [field]: value };
    setComponents(updated);
  };

  const removeComponent = (index: number) => {
    setComponents(components.filter((_, i) => i !== index));
  };

  const getSlotLabel = (slot: string) => {
    return COMPONENT_SLOTS.find(s => s.slot === slot)?.label || slot;
  };

  const getSlotEmoji = (slot: string) => {
    return COMPONENT_SLOTS.find(s => s.slot === slot)?.icon || "📌";
  };

  const isComplete = () => {
    const required = COMPONENT_SLOTS.filter(s => s.required).map(s => s.slot);
    return (
      buildName.trim() &&
      required.every(slot => components.find(c => c.slot === slot && c.name.trim()))
    );
  };

  const saveBuild = async () => {
    if (!isComplete()) return;
    setSaving(true);
    try {
      const buildComponents: BuildComponent[] = components
        .filter(c => c.name.trim())
        .map(c => ({
          slot: c.slot,
          name: c.name,
          price_paid: c.price_paid,
          source: c.part_id ? "catalogue" : "manual",
          part_id: c.part_id,
        }));

      const build = await api.manualBuilds.create(buildName);
      await api.manualBuilds.patch(build.id, { components: buildComponents });

      // Auto-evaluate (non-blocking - if it fails, still continue)
      setEvaluating(true);
      try {
        const eval_result = await api.manualBuilds.evaluate(build.id);
        setEvaluation(eval_result);
        setShowEval(true);
      } catch (evalError) {
        console.warn("Build evaluation failed (non-blocking):", evalError);
        // Don't show error - build was saved successfully
      } finally {
        setEvaluating(false);
      }

      // Return to the Pre-Built workspace after the evaluation preview.
      setTimeout(() => {
        router.push(`/builds?new=${build.id}`);
      }, 2000);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : JSON.stringify(error);
      console.error("Error saving build:", errorMsg, error);
      alert(`Error saving build: ${errorMsg || 'Unknown error'}. Please check the console for details.`);
      setSaving(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold font-mono tracking-wider uppercase flex items-center gap-2 bg-gradient-to-r from-cyan-400 via-[#00dc82] to-orange-400 bg-clip-text text-transparent">
          <Package className="w-5 h-5 text-[var(--nf-primary)]" /> Create Pre-Built
        </h1>
        <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
          Enter all components to calculate profit and resale potential
        </p>
      </div>

      <div className="grid grid-cols-1 2xl:grid-cols-[1fr_1.2fr] gap-6">
        {/* Build Form */}
        <div className="space-y-5 max-h-[calc(100vh-200px)] overflow-y-auto">
          {/* JSON Import */}
          <Card className="border-[#00dc82]/30 bg-[#00dc82]/5">
            <CardHeader>
              <CardTitle className="text-sm">Quick Import from JSON</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-xs text-slate-400">
                Have a JSON file with your build details? Upload it to auto-fill the entire form.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="flex-1 px-4 py-2.5 bg-[#00dc82]/10 border border-[#00dc82]/30 rounded-lg text-sm font-medium text-[#00dc82] hover:border-[#00dc82]/50 transition-colors flex items-center justify-center gap-2"
                >
                  <Upload className="w-4 h-4" />
                  Upload JSON File
                </button>
                <button
                  onClick={() => setShowJsonModal(true)}
                  className="flex-1 px-4 py-2.5 bg-slate-700/30 border border-slate-600 rounded-lg text-sm font-medium text-slate-400 hover:border-slate-500 transition-colors"
                >
                  See Format
                </button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                onChange={handleJsonFileUpload}
                className="hidden"
              />
            </CardContent>
          </Card>

          {/* Build Name */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Build Name</CardTitle>
            </CardHeader>
            <CardContent>
              <input
                type="text"
                value={buildName}
                onChange={e => setBuildName(e.target.value)}
                placeholder="e.g., Gaming PC #1, Office Workstation, Budget Build"
                className="w-full px-4 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 outline-none focus:border-[#00dc82]/50 placeholder-slate-600"
              />
            </CardContent>
          </Card>

          {/* Components */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">Components</CardTitle>
                <span className="text-xs text-slate-500">
                  {components.filter(c => c.name.trim()).length} added
                </span>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {components.map((comp, idx) => (
                <div key={idx} className="p-4 bg-[#0a1119] rounded-lg border border-[#1e2d45] space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-400 uppercase">
                      {getSlotEmoji(comp.slot)} {getSlotLabel(comp.slot)}
                    </label>
                    {components.length > 5 && (
                      <button
                        onClick={() => removeComponent(idx)}
                        className="p-1 text-slate-600 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="col-span-2 flex gap-2">
                      <input
                        type="text"
                        value={comp.name}
                        onChange={e => updateComponent(idx, "name", e.target.value)}
                        placeholder={`e.g., Intel Core i7-10700K, RTX 3070, 16GB DDR4`}
                        className="flex-1 px-3 py-1.5 bg-[#141d2d] border border-[#1e2d45] rounded text-xs text-slate-300 outline-none focus:border-[#00dc82]/50"
                      />
                      <button
                        onClick={() => comp.name.trim() && checkMarketPrice(idx, comp.name)}
                        disabled={!comp.name.trim() || comp.market_status === "checking"}
                        className="px-2 py-1.5 text-[10px] font-semibold bg-[#00dc82]/10 text-[#00dc82] border border-[#00dc82]/20 rounded hover:border-[#00dc82]/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {comp.market_status === "checking" ? "🔍" : "Check Price"}
                      </button>
                    </div>
                    {pricingLookups[idx] && (
                      <div className="col-span-2 p-2 bg-[#00dc82]/5 rounded border border-[#00dc82]/20 text-[10px]">
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-slate-500">Market Range:</span>
                          <span className="font-bold text-[#00dc82]">
                            £{formatCurrency(pricingLookups[idx]!.market_price_low)} - £{formatCurrency(pricingLookups[idx]!.market_price_high)}
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-500">Fair Price:</span>
                          <span className="font-bold text-slate-300">£{formatCurrency(pricingLookups[idx]!.fair_price)}</span>
                        </div>
                        <div className="flex justify-between items-center mt-1 pt-1 border-t border-[#1e2d45]">
                          <span className="text-slate-600">Deal Score:</span>
                          <span className={pricingLookups[idx]!.deal_score > 0 ? "text-[#00dc82]" : "text-orange-400"}>
                            {pricingLookups[idx]!.deal_score > 0 ? "+" : ""}{Math.round(pricingLookups[idx]!.deal_score)}%
                          </span>
                        </div>
                      </div>
                    )}

                    <div>
                      <label className="text-[10px] text-slate-500 uppercase">Price (£)</label>
                      <input
                        type="number"
                        value={comp.price_paid || ""}
                        onChange={e => updateComponent(idx, "price_paid", parseFloat(e.target.value) || 0)}
                        placeholder="0"
                        className="w-full px-3 py-1.5 bg-[#141d2d] border border-[#1e2d45] rounded text-xs text-slate-300 outline-none focus:border-[#00dc82]/50"
                      />
                    </div>

                    <div>
                      <label className="text-[10px] text-slate-500 uppercase">Condition</label>
                      <select
                        value={comp.condition}
                        onChange={e => updateComponent(idx, "condition", e.target.value as any)}
                        className="w-full px-3 py-1.5 bg-[#141d2d] border border-[#1e2d45] rounded text-xs text-slate-300 outline-none focus:border-[#00dc82]/50"
                      >
                        <option value="new">New</option>
                        <option value="refurb">Refurb</option>
                        <option value="used">Used</option>
                      </select>
                    </div>

                    <div>
                      <label className="text-[10px] text-slate-500 uppercase">Source</label>
                      <input
                        type="text"
                        value={comp.source}
                        onChange={e => updateComponent(idx, "source", e.target.value)}
                        placeholder="eBay, Amazon, etc."
                        className="w-full px-3 py-1.5 bg-[#141d2d] border border-[#1e2d45] rounded text-xs text-slate-300 outline-none focus:border-[#00dc82]/50"
                      />
                    </div>

                    <div className="col-span-2">
                      <label className="text-[10px] text-slate-500 uppercase">Notes (optional)</label>
                      <input
                        type="text"
                        value={comp.notes}
                        onChange={e => updateComponent(idx, "notes", e.target.value)}
                        placeholder="e.g., slight cosmetic damage, includes box"
                        className="w-full px-3 py-1.5 bg-[#141d2d] border border-[#1e2d45] rounded text-xs text-slate-300 outline-none focus:border-[#00dc82]/50"
                      />
                    </div>
                  </div>
                </div>
              ))}

              <Button variant="secondary" size="sm" onClick={addComponent} className="w-full">
                <Plus className="w-3.5 h-3.5" /> Add Optional Component
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar Summary */}
        <div className="space-y-4">
          {/* Cost Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <DollarSign className="w-3.5 h-3.5 text-[#00dc82]" /> Build Cost
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="text-center">
                <div className="text-xs text-slate-500 mb-1">Total Invested</div>
                <div className="text-3xl font-black text-[#00dc82]">
                  {formatCurrency(totalCost)}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                {components.filter(c => c.name.trim()).length > 0 && (
                  <>
                    <div className="p-2 bg-[#0a1119] rounded text-center">
                      <div className="text-slate-500 text-[9px]">Items</div>
                      <div className="font-bold text-slate-300">
                        {components.filter(c => c.name.trim()).length}
                      </div>
                    </div>
                    <div className="p-2 bg-[#0a1119] rounded text-center">
                      <div className="text-slate-500 text-[9px]">Avg/Item</div>
                      <div className="font-bold text-slate-300">
                        {formatCurrency(totalCost / components.filter(c => c.name.trim()).length)}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Evaluation Result */}
          {evaluation && (
            <>
              <Card className="bg-gradient-to-br from-[#00dc82]/10 to-transparent border-[#00dc82]/30">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Sparkles className="w-3.5 h-3.5 text-[#00dc82]" /> AI Market Assessment
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 text-xs">
                  {/* Price Range */}
                  <div className="space-y-2">
                    <div className="flex justify-between mb-2">
                      <span className="text-slate-500">Market Price Range (Today)</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div className="p-2 bg-[#0a1119] rounded border border-orange-400/30">
                        <div className="text-[9px] text-slate-600">Conservative</div>
                        <div className="font-bold text-orange-400">{formatCurrency(evaluation.low)}</div>
                      </div>
                      <div className="p-2 bg-[#0a1119] rounded border border-[#00dc82]/30">
                        <div className="text-[9px] text-slate-600">Fair Market</div>
                        <div className="font-bold text-[#00dc82]">{formatCurrency(evaluation.mid)}</div>
                      </div>
                      <div className="p-2 bg-[#0a1119] rounded border border-cyan-400/30">
                        <div className="text-[9px] text-slate-600">Optimistic</div>
                        <div className="font-bold text-cyan-400">{formatCurrency(evaluation.high)}</div>
                      </div>
                    </div>
                  </div>

                  {/* Profit Analysis */}
                  <div className="p-3 bg-[#00dc82]/10 rounded border border-[#00dc82]/20 space-y-1">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Investment Cost</span>
                      <span className="font-bold text-slate-300">{formatCurrency(totalCost)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Expected Resale (Fair Market)</span>
                      <span className="font-bold text-[#00dc82]">{formatCurrency(evaluation.mid)}</span>
                    </div>
                    <div className="pt-2 border-t border-[#00dc82]/20 flex justify-between">
                      <span className="font-semibold text-slate-400">Expected Profit</span>
                      <span className="text-lg font-black text-[#00dc82]">
                        +{formatCurrency(evaluation.mid - totalCost)}
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-500 flex justify-between">
                      <span>ROI & Margin</span>
                      <span>
                        {Math.round(((evaluation.mid - totalCost) / totalCost) * 100)}% ·{" "}
                        {Math.round((1 - totalCost / evaluation.mid) * 100)}% margin
                      </span>
                    </div>
                  </div>

                  {/* Components Breakdown */}
                  {components.filter(c => c.name.trim()).length > 0 && (
                    <div className="space-y-2">
                      <div className="text-[10px] font-semibold text-slate-500 uppercase">Component Analysis</div>
                      <div className="space-y-1.5 max-h-40 overflow-y-auto">
                        {components
                          .filter(c => c.name.trim())
                          .map((comp, idx) => {
                            const pricing = pricingLookups[idx];
                            const percentOfTotal = ((comp.price_paid / totalCost) * 100).toFixed(0);
                            return (
                              <div key={idx} className="p-2 bg-[#0a1119] rounded border border-[#1e2d45] text-[10px]">
                                <div className="flex justify-between items-start mb-1">
                                  <span className="font-semibold text-slate-300">{comp.name}</span>
                                  <span className="text-[9px] text-slate-500">{percentOfTotal}% of build</span>
                                </div>
                                <div className="flex justify-between text-[9px]">
                                  <span className="text-slate-600">Paid: {formatCurrency(comp.price_paid)}</span>
                                  {pricing ? (
                                    <span className={pricing.deal_score >= 0 ? "text-[#00dc82]" : "text-orange-400"}>
                                      Market avg: {formatCurrency(pricing.fair_price)}
                                      {pricing.deal_score > 0 ? " ✓ Good deal" : " ⚠ Pricey"}
                                    </span>
                                  ) : (
                                    <span className="text-slate-500">Check market price →</span>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  )}

                  {/* LLM Narrative Assessment */}
                  {evaluation.narrative && (
                    <div className="p-3 bg-[#0a1119] rounded border border-[#1e2d45] text-slate-400 text-[11px] leading-relaxed space-y-1.5">
                      <div className="font-semibold text-slate-300">💡 AI Assessment</div>
                      <div>{evaluation.narrative}</div>
                    </div>
                  )}

                  {/* Upgrade Suggestions */}
                  {evaluation.suggestions && evaluation.suggestions.length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-[10px] font-semibold text-slate-500 uppercase">Enhancement Ideas</div>
                      {evaluation.suggestions.slice(0, 3).map((s: any, i: number) => (
                        <div key={i} className="p-2 bg-[#0a1119] rounded border border-[#1e2d45] text-[10px] text-slate-400 flex gap-2">
                          <span className="text-[#00dc82] flex-shrink-0">→</span>
                          <span>
                            {s.text}
                            {s.uplift && <span className="text-[#00dc82] ml-1">(+£{formatCurrency(s.uplift)} profit)</span>}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Ready to Sell Card */}
              <Card className="bg-[#00dc82]/5 border-[#00dc82]/30">
                <CardContent className="pt-6 space-y-3">
                  <div className="text-center">
                    <div className="text-xs text-slate-500 mb-1">Build is Ready to List</div>
                    <div className="flex items-center justify-center gap-2">
                      <Check className="w-5 h-5 text-[#00dc82]" />
                      <span className="text-sm font-bold text-[#00dc82]">AI Approved</span>
                    </div>
                  </div>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => router.push("/selling")}
                    className="w-full justify-center"
                  >
                    <Send className="w-3.5 h-3.5" /> Go to Selling
                  </Button>
                </CardContent>
              </Card>
            </>
          )}

          {/* Validation */}
          <Card>
            <CardContent className="pt-6 space-y-2">
              {!buildName.trim() && (
                <div className="flex items-start gap-2 text-xs text-yellow-400">
                  <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>Enter a build name</span>
                </div>
              )}
              {COMPONENT_SLOTS.filter(s => s.required)
                .filter(s => !components.find(c => c.slot === s.slot && c.name.trim()))
                .map(s => (
                  <div key={s.slot} className="flex items-start gap-2 text-xs text-yellow-400">
                    <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <span>Add {s.label}</span>
                  </div>
                ))}
              {isComplete() && (
                <div className="flex items-start gap-2 text-xs text-[#00dc82]">
                  <Check className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>Ready to save</span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Save Button */}
          <Button
            variant="primary"
            size="sm"
            onClick={saveBuild}
            disabled={!isComplete() || saving || evaluating}
            className="w-full justify-center"
          >
            {saving || evaluating ? (
              <>
                <Zap className="w-3.5 h-3.5 animate-spin" />
                {evaluating ? "Evaluating..." : "Saving..."}
              </>
            ) : (
              <>
                <Check className="w-3.5 h-3.5" />
                Save & Evaluate Build
              </>
            )}
          </Button>

          {evaluation && (
            <Button variant="secondary" size="sm" onClick={() => router.push("/selling")} className="w-full">
              Go to Selling
            </Button>
          )}
        </div>

        {/* Live Preview */}
        <div className="hidden 2xl:block sticky top-6 h-fit">
          <div className="border border-cyan-400/30 bg-cyan-400/5 rounded-lg p-4 mb-4">
            <h2 className="text-sm font-bold text-cyan-400 mb-2">📋 Live Listing Preview</h2>
            <p className="text-xs text-slate-400">This is how your build will look to buyers</p>
          </div>

          <div className="bg-white rounded-lg overflow-hidden shadow-2xl border border-slate-200">
            <BuildListingTemplate
              buildName={buildName || "Your Build Name"}
              totalCost={totalCost}
              components={components.filter(c => c.name.trim())}
              totalMarketValue={evaluation?.mid || 0}
              profitPotential={evaluation ? (evaluation.mid - totalCost) : 0}
              dealScore={evaluation?.deal_score || 0}
              description={`A carefully curated build featuring ${components.filter(c => c.name.trim()).length} premium components. Expertly selected for compatibility and performance.`}
            />
          </div>
        </div>
      </div>

      {/* JSON Format Modal */}
      {showJsonModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-2xl border-[#00dc82]/30 bg-[#0a1119]">
            <CardHeader className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Upload className="w-4 h-4 text-[#00dc82]" /> JSON Format Guide
              </CardTitle>
              <button
                onClick={() => setShowJsonModal(false)}
                className="p-1 hover:bg-slate-700/30 rounded transition-colors"
              >
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </CardHeader>
            <CardContent className="space-y-4 text-xs">
              <div className="space-y-2">
                <label className="font-semibold text-slate-400 uppercase">Required JSON Structure:</label>
                <div className="p-3 bg-[#141d2d] rounded border border-[#1e2d45] font-mono text-[11px] text-slate-300 overflow-x-auto">
                  {`{
  "buildName": "Your Build Name Here",
  "components": [
    {
      "slot": "cpu",
      "name": "Component Name",
      "price_paid": 250,
      "source": "eBay",
      "condition": "used",
      "notes": "optional notes"
    }
  ]
}`}
                </div>
              </div>

              <div className="space-y-2">
                <label className="font-semibold text-slate-400 uppercase">Example (Ready to Copy):</label>
                <div className="p-3 bg-[#141d2d] rounded border border-[#1e2d45] font-mono text-[10px] text-slate-300 overflow-x-auto max-h-64 overflow-y-auto">
                  <pre>{JSON.stringify(JSON_EXAMPLE, null, 2)}</pre>
                </div>
              </div>

              <div className="space-y-2">
                <label className="font-semibold text-slate-400 uppercase">Component Slots (use these values):</label>
                <div className="grid grid-cols-2 gap-2 text-[10px]">
                  {COMPONENT_SLOTS.map(slot => (
                    <div key={slot.slot} className="p-2 bg-[#141d2d] rounded border border-[#1e2d45]">
                      <code className="text-cyan-400">"{slot.slot}"</code>
                      <div className="text-slate-500 mt-1">{slot.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="font-semibold text-slate-400 uppercase">Condition Values:</label>
                <div className="flex gap-2 text-[10px]">
                  {["new", "refurb", "used"].map(cond => (
                    <div key={cond} className="px-2 py-1 bg-[#141d2d] rounded border border-[#1e2d45]">
                      <code className="text-orange-400">"{cond}"</code>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-[#1e2d45] flex gap-2">
                <button
                  onClick={copyJsonExample}
                  className="flex-1 px-3 py-2 bg-[#00dc82]/10 border border-[#00dc82]/30 rounded text-[#00dc82] font-medium text-xs hover:border-[#00dc82]/50 transition-colors flex items-center justify-center gap-2"
                >
                  <Copy className="w-3.5 h-3.5" />
                  {jsonCopied ? "Copied!" : "Copy Example"}
                </button>
                <button
                  onClick={() => setShowJsonModal(false)}
                  className="flex-1 px-3 py-2 bg-slate-700/30 border border-slate-600 rounded text-slate-300 font-medium text-xs hover:border-slate-500 transition-colors"
                >
                  Close
                </button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
