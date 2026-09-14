"use client";

import { Check, ExternalLink, Loader2, Store, ShoppingBag, Users, Package, X } from "lucide-react";

export type PrebuiltChannel = "flipflop_shop" | "ebay_uk" | "facebook_marketplace" | "vinted" | "amazon";

const CHANNELS: Array<{
  id: PrebuiltChannel;
  label: string;
  description: string;
  mode: "api" | "manual" | "approval";
  icon: typeof Store;
}> = [
  { id: "flipflop_shop", label: "FlipFlop.shop", description: "Publish to your own storefront", mode: "api", icon: Store },
  { id: "ebay_uk", label: "eBay UK", description: "Publish through your connected seller account", mode: "api", icon: ShoppingBag },
  { id: "facebook_marketplace", label: "Facebook Marketplace", description: "Download a listing pack for manual posting", mode: "manual", icon: Users },
  { id: "vinted", label: "Vinted", description: "Download a listing pack for manual posting", mode: "manual", icon: Package },
  { id: "amazon", label: "Amazon", description: "Download a listing pack; seller approval is required", mode: "approval", icon: ShoppingBag },
];

const MODE_LABEL: Record<typeof CHANNELS[number]["mode"], string> = {
  api: "Live publish",
  manual: "Manual pack",
  approval: "Needs approval",
};

export function PrebuiltChannelPicker({
  selected,
  onChange,
  onClose,
  onConfirm,
  submitting,
}: {
  selected: PrebuiltChannel[];
  onChange: (channel: PrebuiltChannel) => void;
  onClose: () => void;
  onConfirm: () => void;
  submitting: boolean;
}) {
  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/75 px-4 backdrop-blur-sm" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !submitting) onClose();
    }}>
      <div role="dialog" aria-modal="true" aria-labelledby="prebuilt-channel-title" className="w-full max-w-xl rounded-2xl border border-slate-700 bg-[#0b1422] p-5 shadow-2xl shadow-black/50">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-300">Pre-built listing</p>
            <h2 id="prebuilt-channel-title" className="mt-1 text-xl font-bold text-white">Where should this build be listed?</h2>
            <p className="mt-2 text-sm leading-5 text-slate-400">Choose one or more channels. You can publish to connected channels now and get ready-to-use packs for the others.</p>
          </div>
          <button type="button" aria-label="Close channel picker" onClick={onClose} disabled={submitting} className="cursor-pointer rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/[0.06] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"><X className="h-5 w-5" /></button>
        </div>

        <div className="mt-5 space-y-2">
          {CHANNELS.map(({ id, label, description, mode, icon: Icon }) => {
            const isSelected = selected.includes(id);
            return (
              <button key={id} type="button" onClick={() => onChange(id)} disabled={submitting} aria-pressed={isSelected} className={`flex w-full cursor-pointer items-center gap-3 rounded-xl border p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${isSelected ? "border-cyan-400/70 bg-cyan-400/[0.08]" : "border-slate-700 bg-slate-900/50 hover:border-slate-500"}`}>
                <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${isSelected ? "bg-cyan-400/15 text-cyan-300" : "bg-slate-800 text-slate-400"}`}><Icon className="h-4 w-4" /></span>
                <span className="min-w-0 flex-1"><span className="block text-sm font-semibold text-white">{label}</span><span className="mt-0.5 block text-xs text-slate-400">{description}</span></span>
                <span className={`hidden rounded-full border px-2 py-1 text-[10px] font-bold uppercase tracking-wide sm:inline-flex ${mode === "api" ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300" : mode === "approval" ? "border-amber-400/30 bg-amber-400/10 text-amber-300" : "border-slate-600 bg-slate-800 text-slate-300"}`}>{MODE_LABEL[mode]}</span>
                <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${isSelected ? "border-cyan-300 bg-cyan-300 text-slate-950" : "border-slate-600"}`}>{isSelected && <Check className="h-3.5 w-3.5" />}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-4 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2.5 text-xs leading-5 text-amber-100/80">
          Amazon, Facebook Marketplace, and Vinted are not posted automatically. FlipFlop will create a manual listing pack and explain any approval steps.
        </div>

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-xs text-slate-500">{selected.length} channel{selected.length === 1 ? "" : "s"} selected</span>
          <div className="flex gap-2 sm:justify-end"><button type="button" onClick={onClose} disabled={submitting} className="cursor-pointer rounded-lg border border-slate-600 px-4 py-2.5 text-sm font-semibold text-slate-300 transition-colors hover:border-slate-400 disabled:opacity-50">Cancel</button><button type="button" onClick={onConfirm} disabled={!selected.length || submitting} className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-cyan-400 px-4 py-2.5 text-sm font-bold text-slate-950 transition-colors hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40">{submitting && <Loader2 className="h-4 w-4 animate-spin" />} {submitting ? "Preparing listings…" : "Continue with selected channels"}<ExternalLink className="h-3.5 w-3.5" /></button></div>
        </div>
      </div>
    </div>
  );
}
