"use client";

import type { PublicCase } from "@/lib/types";
import { formatPrice } from "@/lib/utils";

interface Props {
  cases: PublicCase[];
  selected: PublicCase | null;
  onSelect: (c: PublicCase) => void;
}

export function CasePicker({ cases, selected, onSelect }: Props) {
  if (cases.length === 0) {
    return <p className="text-sm text-muted italic">No cases available right now.</p>;
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {cases.map((c) => {
        const isSelected = c.id === selected?.id;
        return (
          <button
            key={c.id}
            onClick={() => onSelect(c)}
            className="text-left rounded-xl p-4 transition-all"
            style={{
              border: `2px solid ${isSelected ? "var(--color-accent)" : "var(--color-border)"}`,
              background: isSelected
                ? "color-mix(in srgb, var(--color-accent) 6%, transparent)"
                : "var(--color-bg-card)",
            }}
          >
            {c.images[0] && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={c.images[0]}
                alt={c.name}
                className="w-full h-28 object-contain mb-3 rounded-lg"
                style={{ background: "var(--color-border)" }}
              />
            )}
            <p className="font-semibold text-sm truncate">{c.name}</p>
            <p className="text-xs text-muted mt-0.5">
              {c.brand} · {c.form_factor.toUpperCase()}
              {c.is_transparent_panel ? " · Glass panel" : ""}
            </p>
            <p className="text-sm font-bold mt-2">{formatPrice(c.rrp_gbp)}</p>
          </button>
        );
      })}
    </div>
  );
}
