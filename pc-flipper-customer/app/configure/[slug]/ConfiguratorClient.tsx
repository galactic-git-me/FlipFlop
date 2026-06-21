"use client";

import { useState, useCallback } from "react";
import type {
  PublicPlaybook,
  PublicSlotWithVariants,
  PublicCase,
  AvailableWeek,
  Tier,
  SlotType,
  BuildState,
  PublicVariant,
} from "@/lib/types";
import { bestVariantForTier } from "@/lib/utils";
import { SlotRow } from "@/components/SlotRow";
import { SwapModal } from "@/components/SwapModal";
import { CasePicker } from "@/components/CasePicker";
import { BuildSummary } from "@/components/BuildSummary";

interface Props {
  playbook: PublicPlaybook;
  slots: PublicSlotWithVariants[];
  cases: PublicCase[];
  weeks: AvailableWeek[];
  initialTier: Tier;
}

function buildInitialState(
  slots: PublicSlotWithVariants[],
  cases: PublicCase[],
  tier: Tier
): BuildState {
  const slotState: Record<string, PublicVariant | null> = {};
  for (const slot of slots) {
    slotState[slot.slot_type] = bestVariantForTier(
      slot.variants_by_tier,
      tier
    );
  }
  return {
    slots: slotState as BuildState["slots"],
    case: cases[0] ?? null,
    chosenWeek: null,
  };
}

export function ConfiguratorClient({
  playbook,
  slots,
  cases,
  weeks,
  initialTier,
}: Props) {
  const [tier, setTier] = useState<Tier>(initialTier);
  const [build, setBuild] = useState<BuildState>(() =>
    buildInitialState(slots, cases, initialTier)
  );
  const [swapTarget, setSwapTarget] = useState<PublicSlotWithVariants | null>(
    null
  );

  const switchTier = useCallback(
    (newTier: Tier) => {
      setTier(newTier);
      const newSlots: Record<string, PublicVariant | null> = {};
      for (const slot of slots) {
        newSlots[slot.slot_type] = bestVariantForTier(
          slot.variants_by_tier,
          newTier
        );
      }
      setBuild((prev) => ({
        ...prev,
        slots: newSlots as BuildState["slots"],
      }));
    },
    [slots]
  );

  const applySwap = useCallback((slotType: SlotType, variant: PublicVariant) => {
    setBuild((prev) => ({
      ...prev,
      slots: { ...prev.slots, [slotType]: variant },
    }));
    setSwapTarget(null);
  }, []);

  // Tier names come from the first slot (all slots share the same tier_names per playbook)
  const tierNames = slots[0]?.tier_names ?? {
    budget: "Budget",
    mid: "Mid",
    high: "High",
  };

  return (
    <div className="flex flex-col lg:flex-row gap-8">
      {/* Left panel */}
      <div className="flex-1 min-w-0">
        {/* Tier picker */}
        <div className="mb-6">
          <p className="text-xs font-bold uppercase tracking-wider text-muted mb-3">
            Starting point
          </p>
          <div className="flex gap-3">
            {(["budget", "mid", "high"] as Tier[]).map((t) => (
              <button
                key={t}
                onClick={() => switchTier(t)}
                className="flex-1 py-3 px-4 rounded-xl text-sm font-semibold transition-all"
                style={{
                  border:
                    tier === t
                      ? "2px solid var(--color-accent)"
                      : "2px solid var(--color-border)",
                  background:
                    tier === t
                      ? "color-mix(in srgb, var(--color-accent) 8%, transparent)"
                      : "var(--color-bg-card)",
                  color:
                    tier === t
                      ? "var(--color-accent)"
                      : "var(--color-text-muted)",
                }}
              >
                {tierNames[t]}
              </button>
            ))}
          </div>
        </div>

        {/* Slot list */}
        <div className="mb-6">
          <p className="text-xs font-bold uppercase tracking-wider text-muted mb-3">
            Components
          </p>
          <div className="flex flex-col gap-2">
            {slots.map((slot) => (
              <SlotRow
                key={slot.slot_id}
                slotType={slot.slot_type}
                selected={build.slots[slot.slot_type] ?? null}
                onSwap={() => setSwapTarget(slot)}
              />
            ))}
          </div>
        </div>

        {/* Case picker */}
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-muted mb-3">
            Case
          </p>
          <CasePicker
            cases={cases}
            selected={build.case}
            onSelect={(c: PublicCase) =>
              setBuild((prev) => ({ ...prev, case: c }))
            }
          />
        </div>
      </div>

      {/* Right panel — sticky summary */}
      <div className="lg:w-72 shrink-0">
        <div className="sticky top-20">
          <BuildSummary
            build={build}
            slots={slots}
            weeks={weeks}
            onWeekSelect={(w: string) =>
              setBuild((prev) => ({ ...prev, chosenWeek: w }))
            }
          />
        </div>
      </div>

      {/* Swap modal */}
      {swapTarget && (
        <SwapModal
          slot={swapTarget}
          currentVariant={build.slots[swapTarget.slot_type] ?? null}
          onSelect={(v: PublicVariant) =>
            applySwap(swapTarget.slot_type, v)
          }
          onClose={() => setSwapTarget(null)}
        />
      )}
    </div>
  );
}
