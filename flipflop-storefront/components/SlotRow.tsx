import type { SlotType, PublicVariant } from "@/lib/types";
import { formatPrice } from "@/lib/utils";

const SLOT_LABELS: Record<SlotType, string> = {
  cpu: "Processor",
  gpu: "Graphics Card",
  ram: "Memory",
  storage: "Storage",
  cooling: "Cooling",
  os: "Operating System",
};

interface Props {
  slotType: SlotType;
  selected: PublicVariant | null;
  onSwap: () => void;
}

export function SlotRow({ slotType, selected, onSwap }: Props) {
  return (
    <div
      className="flex items-center gap-4 py-3 px-4 rounded-lg"
      style={{
        background: "var(--color-bg-card)",
        border: "1px solid var(--color-border)",
      }}
    >
      <div className="w-24 shrink-0">
        <span className="text-xs font-bold uppercase tracking-wider text-muted">
          {SLOT_LABELS[slotType]}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        {selected ? (
          <>
            <p className="text-sm font-medium truncate">{selected.title}</p>
            <p className="text-xs text-muted mt-0.5">
              Gem score {selected.gem_score.toFixed(0)}
            </p>
          </>
        ) : (
          <p className="text-sm text-muted italic">No variants available</p>
        )}
      </div>
      {selected && (
        <p className="font-semibold text-sm shrink-0">
          {formatPrice(selected.display_price)}
        </p>
      )}
      {selected && (
        <button
          onClick={onSwap}
          className="text-xs shrink-0 px-3 py-1.5 rounded-md font-medium transition-colors"
          style={{
            background: "var(--color-border)",
            color: "var(--color-text-muted)",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.color = "var(--color-text)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.color = "var(--color-text-muted)")
          }
        >
          Swap
        </button>
      )}
    </div>
  );
}
