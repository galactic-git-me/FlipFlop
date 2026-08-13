"use client";

import { useState } from "react";
import { Loader2, Zap } from "lucide-react";
import { api } from "@/lib/api";
import type { TabProps } from "./types";

// Row 4/24: title generation is prompt-level (item + key specs first, filler
// last, sourced from the build's own parts list, cross-checked against
// buyer search terms) — see app/services/selling_toolkit.py / ai_service.

export function ListingContentTab({ flip, onFlipUpdated }: TabProps) {
  const [generating, setGenerating] = useState(false);
  const [title, setTitle] = useState<string | null>(flip.generated_title ?? null);
  const [description, setDescription] = useState<string | null>(flip.generated_description ?? null);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const result = await api.flips.generateListing(flip.id);
      setTitle(result.titles[0] ?? null);
      setDescription(result.description ?? null);
      const updated = await api.flips.get(flip.id);
      onFlipUpdated(updated as import("./types").Flip);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Title &amp; Description
          </p>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#00dc82] text-[#04120d] rounded-md font-semibold hover:bg-[#00b86d] transition-colors disabled:opacity-40"
          >
            {generating ? (
              <><Loader2 className="w-3 h-3 animate-spin" /> Generating…</>
            ) : (
              <><Zap className="w-3 h-3" /> {title ? "Regenerate" : "Generate Listing"}</>
            )}
          </button>
        </div>

        <p className="text-[11px] text-slate-600 leading-relaxed">
          Row 4: front-loads item + key specs before any filler, using the full ~80-char
          title budget. Row 24: pulled from real buyer search terms via the keyword
          research tool in the admin Performance dashboard, not generic keyword tools.
        </p>

        {title && (
          <div className="space-y-2">
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Title</p>
              <p className="text-sm text-slate-200 font-medium bg-slate-800/50 rounded p-2">{title}</p>
            </div>
            {description && (
              <div>
                <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Description preview</p>
                <div
                  className="text-xs text-slate-400 bg-slate-800/50 rounded p-2 max-h-40 overflow-y-auto leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: description }}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
