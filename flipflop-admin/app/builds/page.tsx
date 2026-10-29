"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Package, Plus, Trash2, ArrowRight, Layers, Sparkles } from "lucide-react";
import { api, ManualBuildSummary } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { VendorLogo } from "@/components/VendorLogo";

type ChannelListingSummary = {
  build_id: number;
  channel: string;
  status: string;
  external_listing_id?: string | null;
};

const CHANNEL_LABELS: Record<string, string> = {
  ebay: "eBay UK",
  ebay_uk: "eBay UK",
  amazon: "Amazon",
  storefront: "FlipFlop.shop",
  flipflop_shop: "FlipFlop.shop",
  facebook_marketplace: "Facebook Marketplace",
  facebook_catalog: "Facebook catalog",
  vinted: "Vinted",
  onbuy: "OnBuy",
};

function vendorKeyForChannel(channel: string): string {
  if (channel === "ebay") return "ebay_uk";
  if (channel === "storefront") return "flipflop_shop";
  return channel;
}

function listedStatus(status: string): boolean {
  return ["published", "scheduled", "withdrawn", "ended", "sold"].includes(status.toLowerCase());
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

const STATUS_LABEL: Record<string, string> = {
  in_progress: "In Progress",
  built: "Built",
  listed: "Listed",
  sold: "Sold",
};

const STATUS_COLOR: Record<string, string> = {
  in_progress: "text-amber-400 border-amber-400/30 bg-amber-400/5",
  built: "text-cyan-400 border-cyan-400/30 bg-cyan-400/5",
  listed: "text-[#00dc82] border-[#00dc82]/30 bg-[#00dc82]/5",
  sold: "text-slate-400 border-slate-400/30 bg-slate-400/5",
};

export default function BuildsPage() {
  return (
    <Suspense fallback={null}>
      <BuildsPageInner />
    </Suspense>
  );
}

function BuildsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const highlightId = searchParams.get("new") ? Number(searchParams.get("new")) : null;

  const [builds, setBuilds] = useState<ManualBuildSummary[]>([]);
  const [channelListings, setChannelListings] = useState<ChannelListingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    Promise.allSettled([api.manualBuilds.list(), api.crossListing.schedules()]).then(async ([buildResult, listingResult]) => {
      if (buildResult.status !== "fulfilled") {
        console.error("Could not load builds:", buildResult.reason);
        return;
      }
      const summaries = buildResult.value;
      setBuilds(summaries);
      const channelRows: ChannelListingSummary[] = listingResult.status === "fulfilled" ? listingResult.value : [];
      if (listingResult.status === "rejected") console.error("Could not load channel listings:", listingResult.reason);

      // Older eBay and storefront listings are stored on the build itself;
      // newer cross-listings are represented by channel_listings records.
      const legacyBuilds = summaries.filter((build) => build.status === "listed" || build.status === "sold");
      const details = await Promise.allSettled(legacyBuilds.map((build) => api.manualBuilds.get(build.id)));
      details.forEach((result) => {
        if (result.status !== "fulfilled") return;
        const build = result.value;
        if (build.ebay_listing_id) channelRows.push({
          build_id: build.id,
          channel: "ebay_uk",
          status: build.ebay_listing_status === "active" ? "published" : build.ebay_listing_status ?? "ended",
          external_listing_id: build.ebay_listing_id,
        });
        if (build.storefront_product_id) channelRows.push({
          build_id: build.id,
          channel: "flipflop_shop",
          status: build.storefront_live === false ? "withdrawn" : "published",
          external_listing_id: String(build.storefront_product_id),
        });
      });
      const byBuildAndChannel = new Map<string, ChannelListingSummary>();
      for (const listing of channelRows) {
        const normalizedChannel = vendorKeyForChannel(listing.channel);
        byBuildAndChannel.set(`${listing.build_id}:${normalizedChannel}`, { ...listing, channel: normalizedChannel });
      }
      setChannelListings([...byBuildAndChannel.values()]);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this build?")) return;
    setDeletingId(id);
    try {
      await api.manualBuilds.delete(id);
      setBuilds((prev) => prev.filter((b) => b.id !== id));
    } catch (error) {
      console.error("Error deleting build:", error);
      alert("Failed to delete build. Please check the console for details.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#060d18] text-slate-100 px-4 py-6 md:px-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Package className="w-5 h-5 text-[#00dc82]" />
          <h1 className="text-xl font-black">Pre-Built</h1>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => router.push("/add-build")} className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold border border-cyan-400/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-200 rounded-lg transition-colors">
            <Plus className="w-3.5 h-3.5" /> Manual build
          </button>
          <button onClick={() => router.push("/add-build/ai")} className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold bg-[#00dc82] hover:bg-[#18e991] text-black rounded-lg transition-colors">
            <Sparkles className="w-3.5 h-3.5" /> AI-created
          </button>
        </div>
      </div>

      {/* Summary row */}
      {builds.length > 0 && (
        <div className="flex gap-4 mb-6">
          <div className="flex-1 rounded-xl p-4 border border-white/[0.07] bg-white/[0.02]">
            <p className="text-xs text-slate-500 mb-1">Total builds</p>
            <p className="text-2xl font-black">{builds.length}</p>
          </div>
          <div className="flex-1 rounded-xl p-4 border border-white/[0.07] bg-white/[0.02]">
            <p className="text-xs text-slate-500 mb-1">Total paid</p>
            <p className="text-2xl font-black text-[#00dc82]">
              {formatCurrency(builds.reduce((s, b) => s + (b.total_cost ?? 0), 0))}
            </p>
          </div>
        </div>
      )}

      {/* Build list */}
      {loading ? (
        <div className="flex items-center justify-center py-24 text-slate-500 text-sm">Loading…</div>
      ) : builds.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-slate-500">
          <Package className="w-10 h-10 opacity-20" />
          <p className="text-sm">No builds yet.</p>
          <div className="flex gap-2">
            <button onClick={() => router.push("/add-build")} className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold border border-cyan-400/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-200 rounded-lg transition-colors"><Plus className="w-3.5 h-3.5" /> Manual build</button>
            <button onClick={() => router.push("/add-build/ai")} className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold bg-[#00dc82] hover:bg-[#18e991] text-black rounded-lg transition-colors"><Sparkles className="w-3.5 h-3.5" /> AI-created</button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {builds.map((b) => (
            <BuildCard
              key={b.id}
              build={b}
              channels={channelListings.filter((listing) => listing.build_id === b.id && listedStatus(listing.status))}
              highlighted={b.id === highlightId}
              deleting={deletingId === b.id}
              onDelete={(e) => handleDelete(b.id, e)}
              onClick={() => router.push(`/builds/${b.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function BuildCard({
  build,
  channels,
  highlighted,
  deleting,
  onDelete,
  onClick,
}: {
  build: ManualBuildSummary;
  channels: ChannelListingSummary[];
  highlighted: boolean;
  deleting: boolean;
  onDelete: (e: React.MouseEvent) => void;
  onClick: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onClick()}
      className={`w-full flex items-center gap-4 p-4 rounded-xl border transition-all text-left cursor-pointer ${
        highlighted
          ? "border-[#00dc82]/50 bg-[#00dc82]/[0.06]"
          : "border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/[0.14]"
      }`}
    >
      <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
        <Layers className="w-4 h-4 text-slate-500" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <p className="text-sm font-semibold text-slate-100 truncate">{build.name}</p>
          <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${build.creation_method === "ai" || build.creation_method === "gem_spotlight" ? "border-[#00dc82]/30 bg-[#00dc82]/10 text-[#00dc82]" : "border-slate-500/30 bg-slate-500/10 text-slate-400"}`}>{build.creation_method === "ai" ? "AI-built" : build.creation_method === "gem_spotlight" ? "Gem spotlight" : "Manual"}</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-0.5">
          {build.component_count} component{build.component_count === 1 ? "" : "s"} · updated {formatDate(build.updated_at)}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-1.5" aria-label="Listing channels">
          {channels.length === 0 ? (
            <span className="text-[10px] text-slate-500">Not listed on any channel</span>
          ) : channels.map((listing) => {
            const channelLabel = CHANNEL_LABELS[listing.channel] ?? listing.channel.replaceAll("_", " ");
            const state = listing.status.toLowerCase();
            const active = state === "published" || state === "scheduled";
            const description = `${channelLabel}: ${state}${listing.external_listing_id ? ` · listing ${listing.external_listing_id}` : ""}`;
            return (
              <span key={`${listing.channel}-${listing.build_id}`} title={description} aria-label={description} className={`inline-flex items-center gap-1.5 rounded-md border px-1.5 py-1 ${active ? "border-emerald-400/25 bg-emerald-400/[.06]" : "border-slate-600/40 bg-slate-800/40 opacity-60"}`}>
                <VendorLogo vendor={vendorKeyForChannel(listing.channel)} />
                <span className="text-[10px] font-medium text-slate-300">{channelLabel}</span>
              </span>
            );
          })}
        </div>
      </div>

      <div className={`px-2 py-1 rounded-lg border text-[10px] font-bold uppercase tracking-wider shrink-0 ${STATUS_COLOR[build.status] ?? STATUS_COLOR.in_progress}`}>
        {STATUS_LABEL[build.status] ?? build.status}
      </div>

      <div className="grid grid-cols-3 gap-4 text-right shrink-0">
        <div>
          <p className="text-xs text-slate-500">Total paid</p>
          <p className="text-sm font-semibold">{(build.creation_method === "ai" || build.creation_method === "gem_spotlight") && build.total_cost === 0 ? "—" : build.total_cost != null ? formatCurrency(build.total_cost) : "—"}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Listing price</p>
          <p className="text-sm font-semibold text-emerald-300">{build.ebay_price != null ? formatCurrency(build.ebay_price) : "—"}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Est. profit</p>
          <p className={`text-sm font-semibold ${build.ebay_price != null && build.total_cost != null ? build.ebay_price - build.total_cost >= 0 ? "text-emerald-300" : "text-red-300" : "text-slate-500"}`}>
            {build.ebay_price != null && build.total_cost != null
              ? formatCurrency(build.ebay_price - build.total_cost)
              : "—"}
          </p>
        </div>
      </div>

      <button
        onClick={onDelete}
        disabled={deleting}
        className="p-2 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-400/10 transition-colors shrink-0 disabled:opacity-40"
        title="Delete build"
      >
        <Trash2 className="w-4 h-4" />
      </button>

      <ArrowRight className="w-4 h-4 text-slate-600 shrink-0" />
    </div>
  );
}
