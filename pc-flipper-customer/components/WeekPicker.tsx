"use client";

import type { AvailableWeek } from "@/lib/types";
import { formatWeek } from "@/lib/utils";

interface Props {
  weeks: AvailableWeek[];
  selected: string | null;
  onSelect: (week: string) => void;
}

export function WeekPicker({ weeks, selected, onSelect }: Props) {
  if (weeks.length === 0) {
    return <p className="text-xs text-muted">No build slots available right now.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {weeks.map((w) => {
        const isSelected = w.week === selected;
        return (
          <button
            key={w.week}
            onClick={() => onSelect(w.week)}
            className="flex items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-all"
            style={{
              border: `1px solid ${isSelected ? "var(--color-accent)" : "var(--color-border)"}`,
              background: isSelected
                ? "color-mix(in srgb, var(--color-accent) 8%, transparent)"
                : "var(--color-bg)",
              color: isSelected ? "var(--color-accent)" : "var(--color-text)",
            }}
          >
            <span className="font-medium">{formatWeek(w.week_start)}</span>
            <span className="text-xs text-muted">{w.available} slot{w.available !== 1 ? "s" : ""}</span>
          </button>
        );
      })}
    </div>
  );
}
