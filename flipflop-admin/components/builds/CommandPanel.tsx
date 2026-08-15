"use client";

import { Send, Trash2, Plus, RotateCcw, Loader2 } from "lucide-react";

interface ListingStatus {
  platform: string;
  isListed: boolean;
  listingId?: string;
  lastUpdated?: string;
}

interface CommandPanelProps {
  buildId: string;
  buildTitle: string;
  listingStatuses: ListingStatus[];
  onGenerateDescription?: () => void;
  onGenerateTitle?: () => void;
  onPublishEbay?: () => void;
  onUpdateEbay?: () => void;
  onDeleteEbay?: () => void;
  onCreateNew?: (platform: string) => void;
  isLoading?: boolean;
}

export function CommandPanel({
  buildId,
  buildTitle,
  listingStatuses,
  onGenerateDescription,
  onGenerateTitle,
  onPublishEbay,
  onUpdateEbay,
  onDeleteEbay,
  onCreateNew,
  isLoading = false,
}: CommandPanelProps) {
  const ebayStatus = listingStatuses.find((s) => s.platform === "ebay");

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-slate-800/95 backdrop-blur border-t border-slate-600 shadow-2xl z-50">
      <div className="max-w-5xl mx-auto px-4 py-3">
        {/* Dock buttons container */}
        <div className="flex items-center justify-center gap-2 flex-wrap">
          {/* AI Generation Buttons */}
          <button
            onClick={onGenerateTitle}
            disabled={isLoading}
            title="Generate eBay title with AI"
            className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold rounded transition whitespace-nowrap"
          >
            {isLoading ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
            Title
          </button>

          <button
            onClick={onGenerateDescription}
            disabled={isLoading}
            title="Generate eBay description with AI"
            className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold rounded transition whitespace-nowrap"
          >
            {isLoading ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
            Description
          </button>

          {/* Divider */}
          <div className="w-px h-6 bg-slate-600" />

          {/* eBay Buttons */}
          {ebayStatus?.isListed ? (
            <>
              <button
                onClick={onUpdateEbay}
                disabled={isLoading}
                title="Update eBay listing with changes"
                className="flex items-center gap-2 px-3 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-semibold rounded transition whitespace-nowrap"
              >
                {isLoading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                Update eBay
              </button>

              <button
                onClick={onDeleteEbay}
                disabled={isLoading}
                title="Delete eBay listing"
                className="flex items-center gap-2 px-3 py-2 bg-red-600/20 hover:bg-red-600/30 border border-red-500/30 disabled:opacity-50 text-red-300 text-xs font-semibold rounded transition whitespace-nowrap"
              >
                {isLoading ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                Delete
              </button>
            </>
          ) : (
            <button
              onClick={onPublishEbay}
              disabled={isLoading}
              title="Create new eBay listing"
              className="flex items-center gap-2 px-3 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-xs font-semibold rounded transition whitespace-nowrap"
            >
              {isLoading ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
              Create eBay
            </button>
          )}

          {/* Divider */}
          <div className="w-px h-6 bg-slate-600" />

          {/* Status */}
          <div className="flex items-center gap-2 px-3 py-2 text-xs text-slate-400">
            <span className="font-mono text-slate-300">{buildTitle.slice(0, 20)}</span>
            {ebayStatus && (
              <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                ebayStatus.isListed
                  ? "bg-green-900/30 text-green-300"
                  : "bg-slate-700 text-slate-400"
              }`}>
                {ebayStatus.isListed ? "✓ Listed" : "Not Listed"}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
