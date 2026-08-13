"use client";

import { Truck, Info } from "lucide-react";
import type { TabProps } from "./types";

// Rows 11-15, 43, 44: these are global eBay Business Policy settings — set
// once in Settings > Seller Policies, applied to every listing via the
// eBay Business Policies API, not re-entered per build. This tab shows what
// will apply to this listing; per-build overrides only exist for cases a
// specific build genuinely can't hit the global default.
const GLOBAL_DEFAULTS = [
  { label: "Handling time", value: "2 business days", row: "11, 12" },
  { label: "Returns", value: "30-day returns accepted, buyer pays return shipping", row: "13, 14" },
  { label: "Shipping", value: "Free, absorbed into price", row: "15, 35" },
  { label: "Local pickup", value: "Offered", row: "43" },
  { label: "Listing type", value: "Fixed Price (never auction)", row: "44" },
];

export function DispatchTab({}: TabProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <Truck className="w-3.5 h-3.5" /> Dispatch &amp; Delivery
        </p>
        <div className="space-y-2">
          {GLOBAL_DEFAULTS.map((d) => (
            <div key={d.label} className="flex items-center justify-between text-sm">
              <span className="text-slate-500">{d.label}</span>
              <span className="text-slate-200 text-right">{d.value}</span>
            </div>
          ))}
        </div>
        <div className="flex items-start gap-2 text-[11px] text-slate-600 bg-slate-900/40 rounded-lg p-3 mt-1">
          <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          These are configured once for the whole store in Settings &gt; Seller Policies and
          applied to every listing automatically — not re-entered per build. Override here
          only if this specific build genuinely can&apos;t hit the global default (e.g. unusually
          heavy/fragile, needing extra handling days).
        </div>
      </div>
    </div>
  );
}
