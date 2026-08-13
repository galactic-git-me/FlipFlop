"use client";

import { CheckCircle2, AlertTriangle } from "lucide-react";
import type { TabProps } from "./types";

// Row 25: every relevant eBay item specific auto-populated from the build's
// own parts list (cpu/gpu/ram/storage), so nothing ships blank — a blank
// item specific excludes the listing from filtered search entirely.

function SpecRow({ label, value }: { label: string; value?: string | number | null }) {
  const filled = value !== undefined && value !== null && value !== "";
  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-800 last:border-b-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className={`text-sm font-mono flex items-center gap-1.5 ${filled ? "text-slate-200" : "text-amber-400"}`}>
        {filled ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <AlertTriangle className="w-3.5 h-3.5" />}
        {filled ? value : "Not set — will be excluded from filtered search"}
      </span>
    </div>
  );
}

export function ItemSpecificsTab({ flip }: TabProps) {
  const listing = flip.listing;

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-1">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          Auto-populated Item Specifics
        </p>
        <SpecRow label="Brand" value="Custom Build" />
        <SpecRow label="Processor" value={listing?.cpu} />
        <SpecRow label="Graphics Processing Type" value={listing?.gpu ?? (listing?.cpu ? "Integrated" : undefined)} />
        <SpecRow
          label="RAM Size"
          value={listing?.ram_gb ? `${listing.ram_gb}GB ${listing.ram_type ?? ""}`.trim() : undefined}
        />
        <SpecRow
          label="SSD/Storage Capacity"
          value={listing?.storage_gb ? `${listing.storage_gb}GB ${listing.storage_type ?? ""}`.trim() : undefined}
        />
        <SpecRow label="Condition" value="Used" />
        <SpecRow label="Compatible Operating System" value="Windows 11" />
      </div>
      <p className="text-[11px] text-slate-600 leading-relaxed">
        Sourced from the build&apos;s parts list in Build Overview above — swap a part there
        and these update automatically. Amber rows will exclude this listing from any
        buyer search filtered on that specific.
      </p>
    </div>
  );
}
