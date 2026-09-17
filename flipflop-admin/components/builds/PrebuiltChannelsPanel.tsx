"use client";

import {
  CheckCircle2, ExternalLink, Store,
} from "lucide-react";
import type { ManualBuild } from "@/lib/api";

export function PrebuiltChannelsPanel({
  build,
  onOpenCrossListing,
}: {
  build: ManualBuild;
  onOpenCrossListing: () => void;
}) {
  return (
    <section className="mb-6 rounded-xl border border-cyan-400/20 bg-cyan-400/[0.03] p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-300">Canonical listing</p>
          <h2 className="mt-1 text-lg font-bold text-white">Listing submitted</h2>
          <p className="mt-1 max-w-2xl text-sm leading-5 text-slate-400">
            This build is now the source of truth for every future channel listing. Use Cross-listing to create, prepare and manage the individual marketplace listings.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1.5 text-xs font-bold uppercase tracking-wide text-emerald-300"><CheckCircle2 className="h-3.5 w-3.5" /> Ready to cross-list</span>
      </div>

      <div className="mt-4 flex flex-col gap-3 rounded-lg border border-white/[0.08] bg-black/20 px-3 py-3 text-xs leading-5 text-slate-400 sm:flex-row sm:items-center sm:justify-between">
        <span>Canonical title, description, price, photos, specifications and inventory identity are saved on Build {build.id}.</span>
        <button type="button" onClick={onOpenCrossListing} className="inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-lg bg-cyan-400 px-4 py-2.5 text-sm font-bold text-slate-950 transition-colors hover:bg-cyan-300">
          Open Cross-listing <ExternalLink className="h-3.5 w-3.5" />
        </button>
      </div>
    </section>
  );
}
