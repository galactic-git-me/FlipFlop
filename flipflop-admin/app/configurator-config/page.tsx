"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Eye, EyeOff, GripVertical, Loader } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:4311").trim();

interface Playbook {
  id: number;
  name: string;
}

interface Slot {
  id: number;
  slot_type: string;
  tier_names: Record<string, string>;
}

interface Variant {
  id: number;
  listing_id: number;
  title: string;
  display_price: number;
  tier: "budget" | "mid" | "high";
  status: string;
  is_visible?: boolean;
  display_order?: number;
}

interface SlotWithVariants extends Slot {
  variants: Variant[];
}

interface VisibilityRecord {
  catalogue_variant_id: number;
  is_publicly_visible: boolean;
  display_order: number;
}

export default function ConfiguratorConfigPage() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [selectedPlaybook, setSelectedPlaybook] = useState<Playbook | null>(null);
  const [slots, setSlots] = useState<SlotWithVariants[]>([]);
  const [expandedSlots, setExpandedSlots] = useState<Set<number>>(new Set());
  const [marketPrice, setMarketPrice] = useState<string>("");
  const [marketPriceReasoning, setMarketPriceReasoning] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [researchingPrice, setResearchingPrice] = useState(false);

  // Load playbooks on mount
  useEffect(() => {
    const loadPlaybooks = async () => {
      try {
        const res = await fetch(`${API_URL}/api/playbooks`);
        if (!res.ok) throw new Error("Failed to load playbooks");
        const data = await res.json();
        setPlaybooks(data);
        if (data.length > 0) {
          setSelectedPlaybook(data[0]);
        }
      } catch (err) {
        console.error("Error loading playbooks:", err);
      }
    };
    loadPlaybooks();
  }, []);

  // Load slots when playbook changes
  useEffect(() => {
    if (!selectedPlaybook) return;

    const loadSlots = async () => {
      setLoading(true);
      try {
        const res = await fetch(
          `${API_URL}/api/configurator/playbooks/${selectedPlaybook.id}/slots-with-variants`
        );
        if (!res.ok) {
          const errorData = await res.json();
          if (errorData.detail?.includes("no slots")) {
            setSlots([]);
            return;
          }
          throw new Error("Failed to load slots");
        }
        const data = await res.json();
        setSlots(data);

        // Load visibility info
        const visRes = await fetch(
          `${API_URL}/api/configurator/visibility/${selectedPlaybook.id}`
        );
        if (visRes.ok) {
          const visData = await visRes.json() as Array<{ catalogue_variant_id: number; is_publicly_visible: boolean; display_order: number }>;
          const visMap = new Map(visData.map((v) => [v.catalogue_variant_id, v]));

          setSlots(prev => prev.map(slot => ({
            ...slot,
            variants: slot.variants.map(v => ({
              ...v,
              is_visible: visMap.get(v.id)?.is_publicly_visible ?? false,
              display_order: visMap.get(v.id)?.display_order ?? 0,
            })),
          })));
        }

        // Reset market price when playbook changes
        setMarketPrice("");
        setMarketPriceReasoning("");
      } catch (err) {
        console.error("Error loading slots:", err);
      } finally {
        setLoading(false);
      }
    };

    loadSlots();
  }, [selectedPlaybook]);

  // Research market price using LLM
  const researchMarketPrice = async () => {
    if (!selectedPlaybook || slots.length === 0) return;

    setResearchingPrice(true);
    try {
      // Build spec summary from selected variants
      const specs = slots
        .map(slot => {
          const visibleVariants = slot.variants.filter(v => v.is_visible);
          if (visibleVariants.length === 0) return null;
          return `${slot.slot_type}: ${visibleVariants.map(v => v.title).join(" / ")}`;
        })
        .filter(Boolean)
        .join("\n");

      // Call LLM-based market research endpoint
      const res = await fetch(`${API_URL}/api/configurator/research-market-price`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playbook_id: selectedPlaybook.id,
          playbook_name: selectedPlaybook.name,
          specs,
        }),
      });

      if (!res.ok) throw new Error("Failed to research market price");
      const data = await res.json();
      setMarketPrice(data.suggested_price?.toString() ?? "");
      setMarketPriceReasoning(data.reasoning ?? "");
    } catch (err) {
      console.error("Error researching market price:", err);
      alert("Failed to research market price. Check console for details.");
    } finally {
      setResearchingPrice(false);
    }
  };

  // Toggle variant visibility
  const toggleVariantVisibility = async (slotId: number, variantId: number) => {
    try {
      const slot = slots.find(s => s.id === slotId);
      const variant = slot?.variants.find(v => v.id === variantId);
      if (!variant) return;

      const newVisibility = !variant.is_visible;

      // Optimistic update
      setSlots(prev => prev.map(s =>
        s.id === slotId
          ? {
              ...s,
              variants: s.variants.map(v =>
                v.id === variantId ? { ...v, is_visible: newVisibility } : v
              ),
            }
          : s
      ));

      // Save to backend
      const res = await fetch(`${API_URL}/api/configurator/visibility`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playbook_slot_id: slotId,
          catalogue_variant_id: variantId,
          is_publicly_visible: newVisibility,
          display_order: variant.display_order ?? 0,
        }),
      });

      if (!res.ok) throw new Error("Failed to save visibility");
    } catch (err) {
      console.error("Error toggling visibility:", err);
      window.location.reload();
    }
  };

  // Toggle slot expansion
  const toggleSlot = (slotId: number) => {
    const newExpanded = new Set(expandedSlots);
    if (newExpanded.has(slotId)) {
      newExpanded.delete(slotId);
    } else {
      newExpanded.add(slotId);
    }
    setExpandedSlots(newExpanded);
  };

  const minMargin = 150;
  const marketPriceNum = parseFloat(marketPrice) || 0;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Custom Builds</h1>
        <p className="text-muted">Shape the component choices customers can use to create a custom PC</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Playbook selector */}
        <Card>
          <CardContent className="pt-6">
            <h3 className="font-semibold mb-3">Playbooks</h3>
            <div className="space-y-2">
              {playbooks.map(pb => (
                <button
                  key={pb.id}
                  onClick={() => setSelectedPlaybook(pb)}
                  className={`w-full text-left px-3 py-2 rounded transition ${
                    selectedPlaybook?.id === pb.id
                      ? "bg-primary text-white"
                      : "bg-secondary hover:bg-secondary/80"
                  }`}
                >
                  {pb.name}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Market Price Research */}
        <Card>
          <CardContent className="pt-6">
            <h3 className="font-semibold mb-4">Market Price</h3>
            <div className="space-y-4">
              <button
                onClick={researchMarketPrice}
                disabled={!selectedPlaybook || loading || researchingPrice}
                className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded font-medium text-sm transition flex items-center justify-center gap-2"
              >
                {researchingPrice ? (
                  <>
                    <Loader className="h-4 w-4 animate-spin" />
                    Researching...
                  </>
                ) : (
                  <>
                    🔍 Research Market Price
                  </>
                )}
              </button>

              <div className="text-xs text-muted">
                <p className="mb-2 font-medium">System will:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Search eBay for similar specs</li>
                  <li>Analyze new/used pricing</li>
                  <li>Use LLM for market opinion</li>
                  <li>Suggest price + reasoning</li>
                </ul>
              </div>

              {marketPrice && (
                <div className="pt-2 border-t border-border space-y-2">
                  <div className="text-sm">
                    <div className="flex justify-between mb-1">
                      <span className="text-muted">Suggested Price:</span>
                      <span className="font-mono font-semibold text-blue-400">£{parseFloat(marketPrice).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-muted">Min Margin:</span>
                      <span className="font-mono text-yellow-400">£{minMargin}</span>
                    </div>
                  </div>
                  {marketPriceReasoning && (
                    <div className="text-xs text-muted bg-secondary/50 p-2 rounded">
                      <p className="font-medium mb-1">Why this price:</p>
                      <p>{marketPriceReasoning}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Info */}
        <Card>
          <CardContent className="pt-6">
            <h3 className="font-semibold mb-4">About This</h3>
            <div className="space-y-3 text-xs text-muted">
              <p>
                <strong>Visibility Toggle:</strong> Choose which component variants customers can select
              </p>
              <p>
                <strong>Market Price:</strong> LLM researches eBay for similar builds and suggests a price
              </p>
              <p>
                <strong>Margin:</strong> System ensures £150+ margin. Price components proportionally.
              </p>
              <p>
                <strong>Customer View:</strong> They see deltas ("+£50" for upgrades), not unit costs
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Slots */}
      {selectedPlaybook && (
        <div className="mt-8">
          <h2 className="text-xl font-bold mb-4">Components</h2>
          <div className="space-y-4">
            {slots.map(slot => (
              <Card key={slot.id}>
                <div
                  onClick={() => toggleSlot(slot.id)}
                  className="flex items-center justify-between p-4 cursor-pointer hover:bg-secondary/50 transition"
                >
                  <div>
                    <h3 className="font-semibold capitalize">{slot.slot_type}</h3>
                    <p className="text-sm text-muted">{slot.variants.filter(v => v.is_visible).length} visible options</p>
                  </div>
                  {expandedSlots.has(slot.id) ? <ChevronUp /> : <ChevronDown />}
                </div>

                {expandedSlots.has(slot.id) && (
                  <CardContent className="pt-0 pb-4">
                    <div className="space-y-3">
                      {["budget", "mid", "high"].map(tier => (
                        <div key={tier}>
                          <h4 className="text-xs font-bold text-muted uppercase mb-2">
                            {slot.tier_names[tier] || tier}
                          </h4>
                          <div className="space-y-2">
                            {slot.variants
                              .filter(v => v.tier === tier)
                              .map(variant => (
                                <div
                                  key={variant.id}
                                  className="flex items-center gap-3 p-3 bg-secondary rounded hover:bg-secondary/80 transition"
                                >
                                  <GripVertical className="h-4 w-4 text-muted flex-shrink-0" />

                                  <button
                                    onClick={() => toggleVariantVisibility(slot.id, variant.id)}
                                    className="flex-shrink-0"
                                  >
                                    {variant.is_visible ? (
                                      <Eye className="h-4 w-4 text-green-400" />
                                    ) : (
                                      <EyeOff className="h-4 w-4 text-muted" />
                                    )}
                                  </button>

                                  <div className="flex-1 min-w-0">
                                    <p className="text-sm truncate">{variant.title}</p>
                                    <p className="text-xs text-muted">Listing #{variant.listing_id}</p>
                                  </div>

                                  <div className="text-right flex-shrink-0">
                                    <p className="text-sm font-mono font-semibold">£{variant.display_price.toFixed(2)}</p>
                                    <p className="text-xs text-muted">{variant.status}</p>
                                  </div>
                                </div>
                              ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
