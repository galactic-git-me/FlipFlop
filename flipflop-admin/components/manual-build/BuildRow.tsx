// pc-flipper/components/manual-build/BuildRow.tsx
"use client";

import { X } from "lucide-react";
import { BuildComponent } from "@/lib/api";

const SLOT_COLOURS: Record<string, string> = {
  "Base PC": "#a855f7",
  CPU:       "#3b82f6",
  GPU:       "#22d3ee",
  RAM:       "#f59e0b",
  Storage:   "#10b981",
  PSU:       "#ef4444",
  Case:      "#6366f1",
  Motherboard: "#14b8a6",
  Cooling:   "#38bdf8",
};

function slotColour(slot: string): string {
  return SLOT_COLOURS[slot] ?? "#94a3b8";
}

interface FilledRowProps {
  component: BuildComponent;
  onPriceChange: (price: number) => void;
  onRemove: () => void;
}

function FilledRow({ component, onPriceChange, onRemove }: FilledRowProps) {
  const colour = slotColour(component.slot);
  return (
    <div
      className="flex items-center gap-3 rounded-md px-3 py-2 border"
      style={{ borderColor: colour + "55", background: "#0d1a2a" }}
    >
      <span
        className="text-xs font-mono uppercase min-w-[80px] font-semibold"
        style={{ color: colour }}
      >
        {component.slot}
      </span>
      <span className="flex-1 text-sm text-slate-200 truncate">{component.name}</span>
      {component.image_url && (
        <img
          src={component.image_url}
          alt=""
          className="w-8 h-8 rounded object-cover opacity-80"
        />
      )}
      <span className="text-xs text-slate-400 mr-1">£</span>
      <input
        type="number"
        value={component.price_paid}
        onChange={(e) => onPriceChange(parseFloat(e.target.value) || 0)}
        className="w-20 text-sm text-right bg-transparent border-b border-slate-600 focus:border-[#00dc82] outline-none text-[#00dc82] font-mono"
        min={0}
        step={0.01}
      />
      {component.listing_url && (
        <a
          href={component.listing_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[10px] text-cyan-500 hover:text-cyan-300 ml-1"
        >
          ↗
        </a>
      )}
      <button
        onClick={onRemove}
        className="text-slate-500 hover:text-red-400 transition-colors ml-1"
        title="Remove"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

interface EmptyRowProps {
  slot: string;
  onClick: () => void;
}

function EmptyRow({ slot, onClick }: EmptyRowProps) {
  const colour = slotColour(slot);
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 rounded-md px-3 py-2 border border-dashed opacity-40 hover:opacity-70 transition-opacity text-left"
      style={{ borderColor: "#374151" }}
    >
      <span
        className="text-xs font-mono uppercase min-w-[80px] font-semibold"
        style={{ color: colour }}
      >
        {slot}
      </span>
      <span className="flex-1 text-xs text-slate-500">Click to add…</span>
    </button>
  );
}

export interface BuildRowProps {
  slot: string;
  component: BuildComponent | null;
  onAdd: (slot: string) => void;
  onPriceChange: (slot: string, price: number) => void;
  onRemove: (slot: string) => void;
}

export function BuildRow({ slot, component, onAdd, onPriceChange, onRemove }: BuildRowProps) {
  if (component) {
    return (
      <FilledRow
        component={component}
        onPriceChange={(price) => onPriceChange(slot, price)}
        onRemove={() => onRemove(slot)}
      />
    );
  }
  return <EmptyRow slot={slot} onClick={() => onAdd(slot)} />;
}
