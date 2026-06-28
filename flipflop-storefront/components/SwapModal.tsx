"use client";

import { useEffect } from "react";
import type { PublicSlotWithVariants, PublicVariant } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { X } from "lucide-react";

const SLOT_LABELS: Record<string, string> = {
  cpu: "Processor", gpu: "Graphics Card", ram: "Memory",
  storage: "Storage", cooling: "Cooling", os: "Operating System",
};

interface Props {
  slot: PublicSlotWithVariants;
  currentVariant: PublicVariant | null;
  onSelect: (v: PublicVariant) => void;
  onClose: () => void;
}

const TIER_LABELS: Record<string, string> = {
  budget: "Budget", mid: "Mid-Range", high: "High End",
};
const TIER_COLOURS: Record<string, string> = {
  budget: "#60a5fa", mid: "#fbbf24", high: "#22c55e",
};

export function SwapModal({ slot, currentVariant, onSelect, onClose }: Props) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Flatten all variants sorted by gem_score desc
  const allVariants: (PublicVariant & { tier: string })[] = (
    ["high", "mid", "budget"] as const
  ).flatMap((tier) =>
    slot.variants_by_tier[tier].map((v) => ({ ...v, tier }))
  ).sort((a, b) => b.gem_score - a.gem_score);

  const priceDelta = (v: PublicVariant) =>
    currentVariant ? v.display_price - currentVariant.display_price : 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-lg rounded-2xl overflow-hidden"
        style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: "1px solid var(--color-border)" }}>
          <div>
            <h2 className="font-bold text-base">
              Choose {SLOT_LABELS[slot.slot_type] ?? slot.slot_type}
            </h2>
            <p className="text-xs text-muted mt-0.5">
              {allVariants.length} option{allVariants.length !== 1 ? "s" : ""} available
            </p>
          </div>
          <button onClick={onClose} className="text-muted hover:text-white transition-colors p-1">
            <X size={18} />
          </button>
        </div>

        {/* Variant list */}
        <div className="overflow-y-auto max-h-[60vh] p-4 flex flex-col gap-3">
          {allVariants.length === 0 && (
            <p className="text-center text-muted text-sm py-8">No variants available for this slot.</p>
          )}
          {allVariants.map((v) => {
            const isCurrent = v.id === currentVariant?.id;
            const delta = priceDelta(v);
            return (
              <button
                key={v.id}
                onClick={() => onSelect(v)}
                className="w-full text-left rounded-xl p-4 transition-all"
                style={{
                  border: `2px solid ${isCurrent ? "var(--color-accent)" : "var(--color-border)"}`,
                  background: isCurrent
                    ? "color-mix(in srgb, var(--color-accent) 6%, transparent)"
                    : "transparent",
                }}
                onMouseEnter={e => {
                  if (!isCurrent) (e.currentTarget as HTMLElement).style.borderColor = "#555";
                }}
                onMouseLeave={e => {
                  if (!isCurrent) (e.currentTarget as HTMLElement).style.borderColor = "var(--color-border)";
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm truncate">{v.title}</span>
                      {isCurrent && (
                        <span className="text-xs px-2 py-0.5 rounded-full font-bold"
                          style={{ background: "var(--color-accent)", color: "#000" }}>
                          Current
                        </span>
                      )}
                      <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                        style={{ color: TIER_COLOURS[v.tier], background: `color-mix(in srgb, ${TIER_COLOURS[v.tier]} 12%, transparent)` }}>
                        {TIER_LABELS[v.tier] ?? v.tier}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-2">
                      <span className="text-xs text-muted">
                        Gem score <span className="font-bold text-white">{v.gem_score.toFixed(0)}</span>
                      </span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-bold text-sm">{formatPrice(v.display_price)}</p>
                    {!isCurrent && delta !== 0 && (
                      <p className="text-xs mt-0.5"
                        style={{ color: delta > 0 ? "#fbbf24" : "var(--color-accent)" }}>
                        {delta > 0 ? `+${formatPrice(delta)}` : formatPrice(delta)}
                      </p>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="px-5 py-3 text-xs text-muted text-center"
          style={{ borderTop: "1px solid var(--color-border)" }}>
          Prices update hourly · availability confirmed at checkout
        </div>
      </div>
    </div>
  );
}
