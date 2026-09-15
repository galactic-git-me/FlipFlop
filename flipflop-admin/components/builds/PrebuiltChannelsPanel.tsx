"use client";

import {
  Check, CheckCircle2, Download, ExternalLink, Loader2,
  Package, ShoppingBag, Store, Users,
} from "lucide-react";
import type { ManualBuild } from "@/lib/api";
import type { PrebuiltChannel } from "./PrebuiltChannelPicker";

const CHANNELS: Array<{
  id: PrebuiltChannel;
  label: string;
  description: string;
  icon: typeof Store;
  live: (build: ManualBuild) => boolean;
  mode: "live" | "manual" | "approval";
}> = [
  { id: "flipflop_shop", label: "FlipFlop.shop", description: "Your direct storefront", icon: Store, live: (build) => !!build.storefront_live, mode: "live" },
  { id: "ebay_uk", label: "eBay UK", description: "Connected seller account", icon: ShoppingBag, live: (build) => !!build.ebay_live, mode: "live" },
  { id: "amazon", label: "Amazon", description: "Manual pack until Seller Central approval is connected", icon: Package, live: () => false, mode: "approval" },
  { id: "vinted", label: "Vinted", description: "Manual listing pack for your Vinted account", icon: Package, live: () => false, mode: "manual" },
  { id: "facebook_marketplace", label: "Facebook Marketplace", description: "Manual listing pack for Facebook Marketplace", icon: Users, live: () => false, mode: "manual" },
];

const MODE_LABEL = { live: "Live publish", manual: "Manual pack", approval: "Needs approval" } as const;

export function PrebuiltChannelsPanel({
  build,
  enabled,
  onToggle,
  onListSelected,
  onDownloadPack,
  submitting,
  canPublish,
  price,
}: {
  build: ManualBuild;
  enabled: PrebuiltChannel[];
  onToggle: (channel: PrebuiltChannel) => void;
  onListSelected: () => void;
  onDownloadPack: (channel: PrebuiltChannel) => void;
  submitting: boolean;
  canPublish: boolean;
  price: string;
}) {
  const selectedCount = enabled.length;
  const hasPrice = Number(price) > 0 || Number(build.ebay_price) > 0;

  return (
    <section className="mb-6 rounded-xl border border-cyan-400/20 bg-cyan-400/[0.03] p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-300">Pre-built distribution</p>
          <h2 className="mt-1 text-lg font-bold text-white">Channels</h2>
          <p className="mt-1 max-w-2xl text-sm leading-5 text-slate-400">
            Enable the destinations you want for this build. FlipFlop.shop and eBay can publish from here; the other channels download a ready-to-post listing pack.
          </p>
        </div>
        <div className="rounded-lg border border-white/[0.08] bg-black/20 px-3 py-2 text-right">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">Enabled</p>
          <p className="text-lg font-bold text-white">{selectedCount}<span className="text-sm font-normal text-slate-500"> / 5</span></p>
        </div>
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-2">
        {CHANNELS.map(({ id, label, description, icon: Icon, live, mode }) => {
          const selected = enabled.includes(id);
          const isLive = live(build);
          return (
            <div key={id} className={`rounded-xl border p-3 transition-colors ${selected ? "border-cyan-400/50 bg-cyan-400/[0.06]" : "border-white/[0.07] bg-black/10"}`}>
              <div className="flex items-start gap-3">
                <button
                  type="button"
                  aria-pressed={selected}
                  aria-label={`${selected ? "Disable" : "Enable"} ${label}`}
                  onClick={() => onToggle(id)}
                  className={`mt-0.5 flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg border transition-colors ${selected ? "border-cyan-300 bg-cyan-300 text-slate-950" : "border-slate-600 text-transparent hover:border-slate-400"}`}
                >
                  <Check className="h-4 w-4" />
                </button>
                <Icon className={`mt-1 h-4 w-4 shrink-0 ${selected ? "text-cyan-300" : "text-slate-500"}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-white">{label}</span>
                    {isLive && <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-emerald-300"><CheckCircle2 className="h-3 w-3" /> Live</span>}
                    {!isLive && <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${mode === "approval" ? "border-amber-400/30 text-amber-300" : "border-slate-600 text-slate-400"}`}>{MODE_LABEL[mode]}</span>}
                  </div>
                  <p className="mt-1 text-xs leading-4 text-slate-500">{description}</p>
                </div>
                {!isLive && selected && mode !== "approval" && (
                  <button type="button" onClick={() => onDownloadPack(id)} className="inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-md border border-slate-600 px-2 py-1.5 text-[10px] font-bold text-slate-300 transition-colors hover:border-cyan-400/50 hover:text-cyan-300" title={`Download ${label} listing pack`}>
                    <Download className="h-3 w-3" /> Pack
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-col gap-3 rounded-lg border border-amber-400/20 bg-amber-400/[0.05] px-3 py-2.5 text-xs leading-5 text-amber-100/80 sm:flex-row sm:items-center sm:justify-between">
        <span>Amazon, Vinted and Facebook Marketplace require manual account steps here. Selecting them downloads the listing information for quick posting.</span>
        <span className="inline-flex shrink-0 items-center gap-1 text-slate-400"><ExternalLink className="h-3 w-3" /> Your accounts stay in control</span>
      </div>

      <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-slate-500">{canPublish && hasPrice ? "Ready to publish or prepare" : "Finish the build, listing copy, media, specifics and price first"}</p>
        <button type="button" onClick={onListSelected} disabled={!selectedCount || !canPublish || !hasPrice || submitting} className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-cyan-400 px-4 py-2.5 text-sm font-bold text-slate-950 transition-colors hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40">
          {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
          {submitting ? "Preparing channels…" : `List ${selectedCount || "selected"} channel${selectedCount === 1 ? "" : "s"}`}
        </button>
      </div>
    </section>
  );
}
