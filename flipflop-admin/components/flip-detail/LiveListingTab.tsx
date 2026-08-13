"use client";

import { useState } from "react";
import { ExternalLink, Loader2, CalendarClock, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import type { Flip, TabProps } from "./types";

// Row 3: seller-consensus traffic-band default (Sun evening best, Mon
// strong, Tue-Thu evenings solid, Fri weakest) — re-weight from FlipFlop's
// own sold-listing timestamps once there's enough history (default
// proposed, confirm once).
const TRAFFIC_BANDS = [
  { value: "sunday_evening", label: "Sunday evening (best)" },
  { value: "monday", label: "Monday (strong)" },
  { value: "tuesday_evening", label: "Tuesday evening (solid)" },
  { value: "wednesday_evening", label: "Wednesday evening (solid)" },
  { value: "thursday_evening", label: "Thursday evening (solid)" },
  { value: "friday", label: "Friday (weakest)" },
  { value: "saturday", label: "Saturday (weekend, ~15-20% above weekday)" },
];

function fmt(d?: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

export function LiveListingTab({ flip, onFlipUpdated }: TabProps) {
  const [deferredAt, setDeferredAt] = useState(
    flip.deferred_publish_at ? flip.deferred_publish_at.slice(0, 16) : ""
  );
  const [trafficBand, setTrafficBand] = useState(flip.traffic_band ?? "sunday_evening");
  const [markdownOptIn, setMarkdownOptIn] = useState(flip.markdown_event_opt_in);
  const [saving, setSaving] = useState(false);

  async function saveScheduler() {
    setSaving(true);
    try {
      const updated = await api.flips.patch(flip.id, {
        deferred_publish_at: deferredAt ? new Date(deferredAt).toISOString() : null,
        traffic_band: trafficBand,
        markdown_event_opt_in: markdownOptIn,
      });
      onFlipUpdated(updated as Flip);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* eBay listing status */}
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-2">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">eBay listing</p>
        {flip.ebay_listing_url ? (
          <a
            href={flip.ebay_listing_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm text-cyan-400 hover:text-cyan-300 transition-colors w-fit"
          >
            View live listing <ExternalLink className="w-3.5 h-3.5" />
          </a>
        ) : (
          <p className="text-sm text-slate-500 italic">Not posted to eBay yet.</p>
        )}
        <p className="text-xs text-slate-600">Listed at: {fmt(flip.listed_at)}</p>
      </div>

      {/* Deferred-listing scheduler */}
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <CalendarClock className="w-3.5 h-3.5" /> Deferred-listing scheduler
        </p>
        <div className="flex flex-col gap-2">
          <label className="text-xs text-slate-500">Traffic band</label>
          <select
            value={trafficBand}
            onChange={(e) => setTrafficBand(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 outline-none focus:border-[#00dc82] transition-colors"
          >
            {TRAFFIC_BANDS.map((b) => (
              <option key={b.value} value={b.value}>{b.label}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs text-slate-500">Publish at (optional — leave blank to list immediately)</label>
          <input
            type="datetime-local"
            value={deferredAt}
            onChange={(e) => setDeferredAt(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 outline-none focus:border-[#00dc82] transition-colors"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={markdownOptIn}
            onChange={(e) => setMarkdownOptIn(e.target.checked)}
            className="accent-[#00dc82]"
          />
          Include in next scheduled markdown/sale event (row 46, after 2 recreate cycles unsold)
        </label>
        <button
          onClick={saveScheduler}
          disabled={saving}
          className="self-start px-3 py-1.5 text-xs bg-[#00dc82] text-[#04120d] rounded-md font-semibold hover:bg-[#00b86d] transition-colors disabled:opacity-40"
        >
          {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : "Save"}
        </button>
      </div>

      {/* Relist/recreate cycle */}
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-2">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <RotateCcw className="w-3.5 h-3.5" /> Relist/recreate cycle
        </p>
        <div className="grid grid-cols-3 gap-3 text-xs">
          <div>
            <p className="text-slate-600 uppercase tracking-wider text-[10px] mb-0.5">Cycles so far</p>
            <p className="font-mono text-slate-200 text-sm">{flip.recreate_cycle_count}</p>
          </div>
          <div>
            <p className="text-slate-600 uppercase tracking-wider text-[10px] mb-0.5">Last recreate</p>
            <p className="font-mono text-slate-200 text-sm">{fmt(flip.last_recreate_at)}</p>
          </div>
          <div>
            <p className="text-slate-600 uppercase tracking-wider text-[10px] mb-0.5">Next recreate</p>
            <p className="font-mono text-slate-200 text-sm">{fmt(flip.next_recreate_at)}</p>
          </div>
        </div>
        <p className="text-[11px] text-slate-600">
          Runs on a randomized ~7-day (±1 day) timer — reworded title, swapped main image,
          {" "}{(flip.recreate_price_step_pct * 100).toFixed(0)}% price step-down per cycle down to the
          pricing floor. Never the same clock time twice within the traffic band above.
        </p>
      </div>
    </div>
  );
}
