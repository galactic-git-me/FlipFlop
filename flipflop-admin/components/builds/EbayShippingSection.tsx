"use client";

import { ManualBuild, FulfillmentPolicy, CourierQuote, api } from "@/lib/api";
import { Truck, AlertCircle, Globe2, Package, Zap } from "lucide-react";
import { useEffect, useState, useRef } from "react";

interface Props {
  build: ManualBuild;
  onUpdate: (config: Partial<ManualBuild>) => Promise<void>;
  saving?: boolean;
  askingPrice?: number;
  onAskingPriceUpdate?: (price: number) => void;
}

const SHIPPING_METHODS = [
  { value: "tracked", label: "Tracked Delivery (Royal Mail/Courier)" },
  { value: "untracked", label: "Untracked Delivery" },
  { value: "local_pickup", label: "Local Pickup Only" },
];

export function EbayShippingSection({ build, onUpdate, saving, askingPrice, onAskingPriceUpdate }: Props) {
  const [shippingMethod, setShippingMethod] = useState(build.shipping_method ?? "tracked");
  const [shippingCost, setShippingCost] = useState((build.shipping_cost ?? 0).toString());
  const [handlingDays, setHandlingDays] = useState((build.handling_time_days ?? 1).toString());
  const [damageCoverConfirmed, setDamageCoverConfirmed] = useState(build.shipping_damage_cover_confirmed ?? false);
  const [fulfillmentPolicyId, setFulfillmentPolicyId] = useState(build.fulfillment_policy_id ?? "");
  const [weightKg, setWeightKg] = useState((build.package_weight_kg ?? "").toString());
  const [lengthCm, setLengthCm] = useState((build.package_length_cm ?? "").toString());
  const [widthCm, setWidthCm] = useState((build.package_width_cm ?? "").toString());
  const [heightCm, setHeightCm] = useState((build.package_height_cm ?? "").toString());

  const [quotes, setQuotes] = useState<CourierQuote[]>([]);
  const [selectedQuoteIndex, setSelectedQuoteIndex] = useState(0);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [loadingQuote, setLoadingQuote] = useState(false);
  const quote = quotes[selectedQuoteIndex] ?? null;
  const [autoSavingDimensions, setAutoSavingDimensions] = useState(false);
  const dimensionsSaveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastSavedDimensionsRef = useRef<{ w: string; l: string; wd: string; h: string }>({
    w: (build.package_weight_kg ?? "").toString(),
    l: (build.package_length_cm ?? "").toString(),
    wd: (build.package_width_cm ?? "").toString(),
    h: (build.package_height_cm ?? "").toString(),
  });

  const hasPackageDimensions = Boolean(weightKg && lengthCm && widthCm && heightCm);
  const dimensionsChanged =
    hasPackageDimensions &&
    (parseFloat(weightKg) !== (build.package_weight_kg ?? undefined) ||
      parseFloat(lengthCm) !== (build.package_length_cm ?? undefined) ||
      parseFloat(widthCm) !== (build.package_width_cm ?? undefined) ||
      parseFloat(heightCm) !== (build.package_height_cm ?? undefined));

  const handleGetQuote = async () => {
    setLoadingQuote(true);
    setQuoteError(null);
    setQuotes([]);
    setSelectedQuoteIndex(0);
    try {
      // Wait briefly to ensure auto-save has completed if dimensions were just entered
      if (autoSavingDimensions) {
        await new Promise(resolve => setTimeout(resolve, 1500));
      }

      const result = await api.manualBuilds.getCourierQuote(build.id);
      setQuotes(result);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "Failed to get courier quote";
      console.error("[handleGetQuote] Error:", errorMsg);
      setQuoteError(errorMsg);
    } finally {
      setLoadingQuote(false);
    }
  };

  const applyQuoteAsChargedShipping = () => {
    if (quote) setShippingCost(quote.price_gbp.toFixed(2));
  };

  // Folds the real courier cost into the asking price and zeroes the
  // shipping line — matches the free-delivery pricing recommendation
  // (Cassini gives free-shipping listings a small ranking boost, and
  // buyers strongly prefer the "free" framing even at the same total
  // cost). Persists ebay_price directly since that field lives in a
  // sibling component, not local state here.
  const applyQuoteToAskingPrice = async () => {
    if (!quote) return;
    setShippingCost("0");
    // Fold onto the asking price actually shown on screen (askingPrice prop),
    // not build.ebay_price — that field is only ever written from here and
    // is never the source of truth the seller is looking at.
    const currentAskingPrice = askingPrice ?? build.ebay_price ?? 0;
    const newAskingPrice = currentAskingPrice + quote.price_gbp;
    await onUpdate({
      ebay_price: newAskingPrice,
      shipping_cost: 0,
    });
    onAskingPriceUpdate?.(newAskingPrice);
  };

  // Real shipping-destination options, fetched live from the seller's own
  // eBay account rather than a hardcoded UK-only/international toggle —
  // that old toggle never actually controlled what the real eBay listing
  // shipped to (destinations are owned by eBay's own fulfillment policies),
  // so it was quietly doing nothing.
  const [policies, setPolicies] = useState<FulfillmentPolicy[] | null>(null);
  const [policiesError, setPoliciesError] = useState<string | null>(null);
  const [loadingPolicies, setLoadingPolicies] = useState(true);

  // Sync the last-saved ref when build data updates (e.g., after successful auto-save)
  useEffect(() => {
    lastSavedDimensionsRef.current = {
      w: (build.package_weight_kg ?? "").toString(),
      l: (build.package_length_cm ?? "").toString(),
      wd: (build.package_width_cm ?? "").toString(),
      h: (build.package_height_cm ?? "").toString(),
    };
  }, [build.package_weight_kg, build.package_length_cm, build.package_width_cm, build.package_height_cm]);

  // Auto-save package dimensions with 1s debounce via direct API call
  useEffect(() => {
    if (!hasPackageDimensions) return;

    const valuesChanged =
      weightKg !== lastSavedDimensionsRef.current.w ||
      lengthCm !== lastSavedDimensionsRef.current.l ||
      widthCm !== lastSavedDimensionsRef.current.wd ||
      heightCm !== lastSavedDimensionsRef.current.h;

    if (!valuesChanged) return;

    if (dimensionsSaveTimeoutRef.current) {
      clearTimeout(dimensionsSaveTimeoutRef.current);
    }

    dimensionsSaveTimeoutRef.current = setTimeout(async () => {
      try {
        const w = parseFloat(weightKg);
        const l = parseFloat(lengthCm);
        const wd = parseFloat(widthCm);
        const h = parseFloat(heightCm);

        console.log("[EbayShippingSection] Auto-saving dimensions:", { w, l, wd, h });

        // Call API directly to save dimensions
        await api.manualBuilds.updateEbayConfig(build.id, {
          package_weight_kg: w,
          package_length_cm: l,
          package_width_cm: wd,
          package_height_cm: h,
        });

        lastSavedDimensionsRef.current = { w: weightKg, l: lengthCm, wd: widthCm, h: heightCm };
        console.log("[EbayShippingSection] ✓ Dimensions auto-saved");
      } catch (error) {
        console.error("[EbayShippingSection] ✗ Failed to auto-save dimensions:", error);
      }
    }, 1000);

    return () => {
      if (dimensionsSaveTimeoutRef.current) {
        clearTimeout(dimensionsSaveTimeoutRef.current);
      }
    };
  }, [weightKg, lengthCm, widthCm, heightCm, hasPackageDimensions, build.id]);

  useEffect(() => {
    let cancelled = false;
    setLoadingPolicies(true);
    api.manualBuilds
      .getFulfillmentPolicies()
      .then((result) => {
        if (!cancelled) {
          setPolicies(result);
          setPoliciesError(null);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setPoliciesError(error instanceof Error ? error.message : "Failed to load shipping destinations");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingPolicies(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSave = async () => {
    const update: Parameters<typeof onUpdate>[0] = {
      shipping_method: shippingMethod,
      shipping_cost: parseFloat(shippingCost) || 0,
      handling_time_days: parseInt(handlingDays, 10),
      fulfillment_policy_id: fulfillmentPolicyId || null,
      shipping_damage_cover_confirmed: damageCoverConfirmed,
    };
    if (hasPackageDimensions) {
      update.package_weight_kg = parseFloat(weightKg);
      update.package_length_cm = parseFloat(lengthCm);
      update.package_width_cm = parseFloat(widthCm);
      update.package_height_cm = parseFloat(heightCm);
    }
    await onUpdate(update);
  };

  const hasChanges =
    dimensionsChanged ||
    shippingMethod !== (build.shipping_method ?? "tracked") ||
    parseFloat(shippingCost) !== (build.shipping_cost ?? 0) ||
    parseInt(handlingDays, 10) !== (build.handling_time_days ?? 1) ||
    damageCoverConfirmed !== (build.shipping_damage_cover_confirmed ?? false) ||
    fulfillmentPolicyId !== (build.fulfillment_policy_id ?? "");

  const selectedPolicy = policies?.find((p) => p.policy_id === fulfillmentPolicyId);

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800 p-4 space-y-4">
      <div className="flex items-center gap-2 mb-4">
        <Truck className="w-5 h-5 text-emerald-400" />
        <h3 className="text-sm font-semibold text-slate-100">Shipping & Delivery</h3>
      </div>

      {/* Shipping Method */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300">Shipping Method</label>
        <select
          value={shippingMethod}
          onChange={(e) => setShippingMethod(e.target.value)}
          className="w-full rounded bg-slate-700 px-3 py-2 text-sm text-slate-100 border border-slate-600 focus:border-blue-500 focus:outline-none"
        >
          {SHIPPING_METHODS.map((method) => (
            <option key={method.value} value={method.value}>
              {method.label}
            </option>
          ))}
        </select>
      </div>

      {/* Shipping Cost */}
      {shippingMethod !== "local_pickup" && (
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300">Shipping Cost (£)</label>
          <input
            type="number"
            step="0.01"
            min="0"
            value={shippingCost}
            onChange={(e) => setShippingCost(e.target.value)}
            className="w-full rounded bg-slate-700 px-3 py-2 text-sm text-slate-100 border border-slate-600 focus:border-blue-500 focus:outline-none"
          />
          <p className="text-xs text-slate-500">
            Flat rate shipping cost for buyers. Use 0 for free shipping.
          </p>
        </div>
      )}

      {/* Handling Time */}
      {shippingMethod !== "local_pickup" && (
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300">Handling Time (Days)</label>
          <select
            value={handlingDays}
            onChange={(e) => setHandlingDays(e.target.value)}
            className="w-full rounded bg-slate-700 px-3 py-2 text-sm text-slate-100 border border-slate-600 focus:border-blue-500 focus:outline-none"
          >
            <option value="0">Same Day</option>
            <option value="1">1 Day</option>
            <option value="2">2 Days</option>
            <option value="3">3 Days</option>
          </select>
          <p className="text-xs text-slate-500">How long after purchase before item ships</p>
        </div>
      )}

      {/* Package Dimensions + real courier quote */}
      {shippingMethod !== "local_pickup" && (
        <div className="space-y-2">
          <label className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
            <Package className="w-3.5 h-3.5 text-slate-500" />
            Package Dimensions
            {autoSavingDimensions && (
              <span className="text-[10px] text-amber-400 animate-pulse">saving…</span>
            )}
            {!autoSavingDimensions && hasPackageDimensions && weightKg === lastSavedDimensionsRef.current.w && (
              <span className="text-[10px] text-emerald-400">✓ saved</span>
            )}
          </label>
          <p className="text-xs text-slate-500">
            Dimensions auto-save as you enter them — used for real courier quotes.
          </p>
          <div className="grid grid-cols-4 gap-2">
            <div>
              <label className="text-[10px] text-slate-500">Weight (kg)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                value={weightKg}
                onChange={(e) => setWeightKg(e.target.value)}
                className="w-full rounded bg-slate-700 px-2 py-1.5 text-sm text-slate-100 border border-slate-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] text-slate-500">Length (cm)</label>
              <input
                type="number"
                step="1"
                min="0"
                value={lengthCm}
                onChange={(e) => setLengthCm(e.target.value)}
                className="w-full rounded bg-slate-700 px-2 py-1.5 text-sm text-slate-100 border border-slate-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] text-slate-500">Width (cm)</label>
              <input
                type="number"
                step="1"
                min="0"
                value={widthCm}
                onChange={(e) => setWidthCm(e.target.value)}
                className="w-full rounded bg-slate-700 px-2 py-1.5 text-sm text-slate-100 border border-slate-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] text-slate-500">Height (cm)</label>
              <input
                type="number"
                step="1"
                min="0"
                value={heightCm}
                onChange={(e) => setHeightCm(e.target.value)}
                className="w-full rounded bg-slate-700 px-2 py-1.5 text-sm text-slate-100 border border-slate-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={async () => {
                if (hasPackageDimensions) {
                  setAutoSavingDimensions(true);
                  try {
                    await onUpdate({
                      package_weight_kg: parseFloat(weightKg),
                      package_length_cm: parseFloat(lengthCm),
                      package_width_cm: parseFloat(widthCm),
                      package_height_cm: parseFloat(heightCm),
                    });
                    lastSavedDimensionsRef.current = { w: weightKg, l: lengthCm, wd: widthCm, h: heightCm };
                  } catch (error) {
                    console.error("Failed to save dimensions:", error);
                  } finally {
                    setAutoSavingDimensions(false);
                  }
                }
              }}
              disabled={!hasPackageDimensions || autoSavingDimensions}
              className="flex-1 flex items-center justify-center gap-1.5 rounded bg-emerald-700 hover:bg-emerald-600 disabled:bg-slate-800 disabled:text-slate-600 disabled:cursor-not-allowed px-3 py-2 text-xs font-semibold text-white transition"
            >
              {autoSavingDimensions ? "Saving..." : "Save Dimensions"}
            </button>
            <button
              onClick={handleGetQuote}
              disabled={!hasPackageDimensions || loadingQuote}
              className="flex-1 flex items-center justify-center gap-1.5 rounded bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 disabled:cursor-not-allowed px-3 py-2 text-xs font-semibold text-slate-200 transition"
            >
              <Zap className="w-3.5 h-3.5" />
              {loadingQuote ? "Getting estimate…" : "Get Shipping Estimate"}
            </button>
          </div>

          {quoteError && (
            <div className="flex items-start gap-2 p-2 rounded bg-red-900/20 border border-red-700/40">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              <p className="text-xs text-red-300">{quoteError}</p>
            </div>
          )}

          {quote && (
            <div className="space-y-2 p-2 rounded bg-amber-950/30 border border-amber-600/40">
              <div className="flex items-start gap-2 rounded border border-cyan-400/20 bg-cyan-400/5 p-2 text-xs text-cyan-100">
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <p><strong>Estimate only.</strong> This does not book or reserve delivery. After the item sells, get a fresh quote using the buyer&apos;s real address and choose the service before paying.</p>
              </div>
              {quotes.length > 1 && (
                <label className="block text-xs text-slate-300">
                  <span className="mb-1 block font-semibold">Estimated courier service</span>
                  <select
                    value={selectedQuoteIndex}
                    onChange={(event) => setSelectedQuoteIndex(Number(event.target.value))}
                    className="w-full rounded border border-white/10 bg-slate-900 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-400"
                  >
                    {quotes.map((option, index) => (
                      <option key={`${option.service_slug}-${index}`} value={index}>
                        {index === 0 ? "Cheapest · " : ""}{option.courier_name} — {option.service_name} — £{option.price_gbp.toFixed(2)}{option.estimated_days != null ? ` · ${option.estimated_days} day est.` : ""}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <div className="text-xs">
                <p className="font-semibold text-emerald-100">
                  {quote.courier_name} — {quote.service_name}
                </p>
                <p className="text-emerald-300">
                  £{quote.price_gbp.toFixed(2)} tracked
                  {quote.estimated_days != null && ` · ${quote.estimated_days} day est.`}
                </p>
                <p className="mt-2 flex items-start gap-1.5 text-amber-200">
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  {quote.protection_warning}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={applyQuoteToAskingPrice}
                  className="flex-1 rounded bg-emerald-700 hover:bg-emerald-600 px-2 py-1.5 text-[10px] font-semibold text-white transition"
                  title="Recommended: folds this cost into the asking price and offers free postage — better search ranking, buyers prefer 'free'"
                >
                  Add to price (free delivery)
                </button>
                <button
                  onClick={applyQuoteAsChargedShipping}
                  className="flex-1 rounded bg-slate-700 hover:bg-slate-600 px-2 py-1.5 text-[10px] font-semibold text-slate-200 transition"
                >
                  Charge as shipping
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Shipping Destination — real eBay fulfillment policies */}
      <div className="rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-3">
        <label className="flex cursor-pointer items-start gap-3">
          <input type="checkbox" checked={damageCoverConfirmed} onChange={(event) => setDamageCoverConfirmed(event.target.checked)} className="mt-1 h-4 w-4 accent-cyan-400" />
          <span>
            <span className="block text-xs font-semibold text-amber-200">Full-value transit protection requirements confirmed</span>
            <span className="mt-1 block text-xs leading-5 text-slate-500">
              Only tick after the insurer has confirmed this assembled PC and its packaging are eligible for loss and accidental-damage cover up to the exact invoice value. For a glass-sided case, obtain written packaging approval before dispatch. Use tracked, signature-required delivery and retain photos of the components, serial numbers, packaging and sealed carton. Parcel2Go carrier protection for computers is loss-only.
            </span>
            <span className="mt-2 block text-xs leading-5 text-slate-400">
              Check the current{' '}
              <a href="https://www.secursus.com/en-gb/terms-and-conditions/" target="_blank" rel="noreferrer" className="text-cyan-300 underline hover:text-cyan-200">Secursus terms</a>
              {' '}and get written confirmation rather than relying on this checkbox as proof of cover.
            </span>
          </span>
        </label>
      </div>

      {/* Shipping Destination — real eBay fulfillment policies */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300">Shipping Destination</label>

        {loadingPolicies && <p className="text-xs text-slate-500">Loading your eBay shipping policies…</p>}

        {!loadingPolicies && policiesError && (
          <div className="flex items-start gap-2 p-2 rounded bg-red-900/20 border border-red-700/40">
            <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <p className="text-xs text-red-300">{policiesError}</p>
          </div>
        )}

        {!loadingPolicies && !policiesError && policies && policies.length === 0 && (
          <p className="text-xs text-amber-300">
            No fulfillment policies found on your eBay account. Create at least one in eBay's Seller Hub
            (Account → Shipping preferences → Business policies) before listing.
          </p>
        )}

        {!loadingPolicies && !policiesError && policies && policies.length > 0 && (
          <>
            <select
              value={fulfillmentPolicyId}
              onChange={(e) => setFulfillmentPolicyId(e.target.value)}
              className="w-full rounded bg-slate-700 px-3 py-2 text-sm text-slate-100 border border-slate-600 focus:border-blue-500 focus:outline-none"
            >
              <option value="">Account default</option>
              {policies.map((policy) => (
                <option key={policy.policy_id} value={policy.policy_id}>
                  {policy.name} — {policy.ship_to_regions.join(", ")}
                </option>
              ))}
            </select>
            {selectedPolicy && (
              <p className="flex items-start gap-1.5 text-xs text-slate-500">
                <Globe2 className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                Ships to: {selectedPolicy.ship_to_regions.join(", ")}
              </p>
            )}
          </>
        )}
      </div>

      {/* Save Button */}
      {hasChanges && (
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full rounded bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed px-4 py-2 text-sm font-semibold text-white transition"
        >
          {saving ? "Saving..." : "Save Shipping"}
        </button>
      )}
    </div>
  );
}
