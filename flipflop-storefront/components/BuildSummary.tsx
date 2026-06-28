"use client";

import type { BuildState, PublicSlotWithVariants, AvailableWeek } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { WeekPicker } from "@/components/WeekPicker";

const SLOT_LABELS: Record<string, string> = {
  cpu: "CPU", gpu: "GPU", ram: "RAM", storage: "Storage",
  cooling: "Cooling", os: "OS",
};

interface Props {
  build: BuildState;
  slots: PublicSlotWithVariants[];
  weeks: AvailableWeek[];
  onWeekSelect: (week: string) => void;
}

export function BuildSummary({ build, slots, weeks, onWeekSelect }: Props) {
  const lineItems = slots
    .map((s) => ({ label: SLOT_LABELS[s.slot_type] ?? s.slot_type, variant: build.slots[s.slot_type] }))
    .filter((item) => item.variant !== null && item.variant !== undefined);

  const caseItem = build.case;

  const total =
    lineItems.reduce((sum, item) => sum + (item.variant?.display_price ?? 0), 0) +
    (caseItem?.rrp_gbp ?? 0);

  const canOrder = build.chosenWeek !== null && total > 0;

  return (
    <div className="rounded-2xl p-5 flex flex-col gap-5"
      style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)" }}>
      <h3 className="font-bold text-sm uppercase tracking-wider">Your Build</h3>

      {/* Line items */}
      <div className="flex flex-col gap-1.5 text-sm">
        {lineItems.map(({ label, variant }) => (
          <div key={label} className="flex justify-between">
            <span className="text-muted">{label}</span>
            <span>{formatPrice(variant!.display_price)}</span>
          </div>
        ))}
        {caseItem && (
          <div className="flex justify-between">
            <span className="text-muted">Case</span>
            <span>{formatPrice(caseItem.rrp_gbp)}</span>
          </div>
        )}
        {lineItems.length === 0 && !caseItem && (
          <p className="text-muted text-xs italic">Select components above</p>
        )}
      </div>

      {/* Total */}
      {total > 0 && (
        <div className="flex justify-between font-bold text-base"
          style={{ borderTop: "1px solid var(--color-border)", paddingTop: "12px" }}>
          <span>Total</span>
          <span>{formatPrice(total)}</span>
        </div>
      )}

      {/* Week picker */}
      <div>
        <p className="text-xs font-bold uppercase tracking-wider text-muted mb-2">Build slot</p>
        <WeekPicker
          weeks={weeks}
          selected={build.chosenWeek}
          onSelect={onWeekSelect}
        />
      </div>

      {/* Checkout button — STUB until Subsystem 2 */}
      <div>
        <button
          disabled
          className="btn-accent w-full text-center py-3 rounded-xl text-sm"
          title="Checkout launching soon"
        >
          Order Now — Coming Soon
        </button>
        <p className="text-xs text-muted text-center mt-2">
          Checkout launching soon ·{" "}
          <a href="mailto:hello@flipflop.co.uk" className="underline hover:text-white">
            email us to order now
          </a>
        </p>
      </div>
    </div>
  );
}
