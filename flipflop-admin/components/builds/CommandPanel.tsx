"use client";

import { Eye, Send, Trash2, Plus, RotateCcw, Loader2, Store, type LucideIcon } from "lucide-react";

interface ListingStatus {
  platform: string;
  isListed: boolean;
  listingId?: string;
  lastUpdated?: string;
  remoteStatus?: string;
}

interface CommandPanelProps {
  buildId: string;
  buildTitle: string;
  listingStatuses: ListingStatus[];
  onGenerateDescription?: () => void;
  onGenerateTitle?: () => void;
  onPreviewEbay?: () => void;
  onPublishEbay?: () => void;
  onUpdateEbay?: () => void;
  onDeleteEbay?: () => void;
  onPublishStorefront?: () => void;
  onCreateNew?: (platform: string) => void;
  isLoading?: boolean;
  isDeletingEbay?: boolean;
  isPublishingStorefront?: boolean;
}

type ActionAccent = "blue" | "amber" | "red" | "green";

const ACCENT_HOVER_CLASSES: Record<ActionAccent, string> = {
  blue: "hover:text-blue-300 hover:border-blue-500/50",
  amber: "hover:text-amber-300 hover:border-amber-500/50",
  red: "hover:text-red-300 hover:border-red-500/50",
  green: "hover:text-green-300 hover:border-green-500/50",
};

// One icon button in the vertical rail, with its label as a tooltip that
// pops out to the left (the rail itself is pinned to the right edge, so a
// label appearing on the right would run off-screen).
function RailButton({
  label,
  icon: Icon,
  onClick,
  disabled,
  isLoading,
  accent,
}: {
  label: string;
  icon: LucideIcon;
  onClick?: () => void;
  disabled?: boolean;
  isLoading?: boolean;
  accent: ActionAccent;
}) {
  return (
    <div className="group relative">
      <button
        onClick={onClick}
        disabled={disabled}
        title={label}
        className={`flex h-11 w-11 items-center justify-center rounded-xl border border-slate-600/50 bg-slate-800/60 backdrop-blur-sm text-slate-300 transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${ACCENT_HOVER_CLASSES[accent]}`}
      >
        {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Icon size={18} />}
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute right-full top-1/2 mr-2 -translate-y-1/2 whitespace-nowrap rounded-md border border-slate-600/50 bg-slate-800 px-2 py-1 text-xs text-slate-200 opacity-0 shadow-lg transition group-hover:opacity-100"
      >
        {label}
      </span>
    </div>
  );
}

// Floating side menu of build actions — fixed to the viewport (not the page
// content), positioned near the top-right and vertically centered from
// there, so it stays visible at a glance regardless of how far down the
// build detail page the user has scrolled. Replaces the previous bottom
// dock: same actions, vertical rail instead of a horizontal magnifying dock,
// since a dock's hover-magnification effect is a horizontal-mouse-x
// interaction that doesn't translate to a slim side rail.
export function CommandPanel({
  buildTitle,
  listingStatuses,
  onGenerateDescription,
  onGenerateTitle,
  onPreviewEbay,
  onPublishEbay,
  onUpdateEbay,
  onDeleteEbay,
  onPublishStorefront,
  isLoading = false,
  isDeletingEbay = false,
  isPublishingStorefront = false,
}: CommandPanelProps) {
  const ebayStatus = listingStatuses.find((s) => s.platform === "ebay");
  const storefrontStatus = listingStatuses.find((s) => s.platform === "storefront");

  return (
    <div className="fixed right-4 top-1/3 z-50 flex flex-col items-center gap-2">
      <div
        title={buildTitle}
        className="mb-1 flex w-11 flex-col items-center gap-1 rounded-xl border border-slate-600/50 bg-slate-800/60 backdrop-blur-sm px-1 py-2"
      >
        <span className="max-h-16 [writing-mode:vertical-rl] truncate text-[10px] font-mono text-slate-400">
          {buildTitle.slice(0, 20)}
        </span>
        {ebayStatus && (
          <span
            className={`h-2 w-2 rounded-full ${ebayStatus.isListed ? "bg-green-400" : "bg-slate-500"}`}
            title={ebayStatus.isListed ? "Active on eBay" : `eBay: ${(ebayStatus.remoteStatus || "not listed").replaceAll("_", " ")}`}
          />
        )}
      </div>

      <RailButton label="Generate title" icon={RotateCcw} onClick={onGenerateTitle} disabled={isLoading} isLoading={isLoading} accent="blue" />
      <RailButton label="Generate description" icon={RotateCcw} onClick={onGenerateDescription} disabled={isLoading} isLoading={isLoading} accent="blue" />
      <RailButton label="Preview eBay listing" icon={Eye} onClick={onPreviewEbay} disabled={isLoading || !onPreviewEbay} accent="blue" />

      {ebayStatus?.isListed ? (
        <>
          <RailButton label="Update eBay listing" icon={Send} onClick={onUpdateEbay} disabled={isLoading} isLoading={isLoading} accent="amber" />
          <RailButton label="End eBay listing" icon={Trash2} onClick={onDeleteEbay} disabled={isLoading || isDeletingEbay} isLoading={isDeletingEbay} accent="red" />
        </>
      ) : (
        <RailButton label="Create eBay listing" icon={Plus} onClick={onPublishEbay} disabled={isLoading} isLoading={isLoading} accent="green" />
      )}
      <RailButton
        label={storefrontStatus?.isListed ? "Update FlipFlop.shop listing" : "Publish to FlipFlop.shop"}
        icon={Store}
        onClick={onPublishStorefront}
        disabled={isLoading || isPublishingStorefront || !onPublishStorefront}
        isLoading={isPublishingStorefront}
        accent={storefrontStatus?.isListed ? "amber" : "green"}
      />
    </div>
  );
}
