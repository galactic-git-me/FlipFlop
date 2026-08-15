"use client";

import { X, Send, Trash2, Plus, Copy, RotateCcw } from "lucide-react";

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
    <div className="fixed right-4 top-20 w-72 max-h-[calc(100vh-120px)] overflow-y-auto bg-slate-800 rounded-lg border border-slate-600 shadow-xl z-40">
      {/* Header */}
      <div className="sticky top-0 bg-slate-800 border-b border-slate-600 p-4">
        <h2 className="text-sm font-semibold text-slate-100">Commands</h2>
        <p className="text-xs text-slate-400 mt-1 truncate">{buildTitle}</p>
      </div>

      {/* Content */}
      <div className="p-4 space-y-6">
        {/* AI Generation Section */}
        <div>
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wide mb-3">
            AI Generation
          </h3>
          <div className="space-y-2">
            <button
              onClick={onGenerateTitle}
              disabled={isLoading}
              className="w-full flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm rounded transition"
            >
              <RotateCcw size={16} />
              Generate Title
            </button>
            <button
              onClick={onGenerateDescription}
              disabled={isLoading}
              className="w-full flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm rounded transition"
            >
              <RotateCcw size={16} />
              Generate Description
            </button>
          </div>
        </div>

        {/* eBay Section */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wide">
              eBay
            </h3>
            {ebayStatus && (
              <span className={`text-xs px-2 py-1 rounded ${
                ebayStatus.isListed
                  ? "bg-green-900/30 text-green-300"
                  : "bg-slate-700 text-slate-400"
              }`}>
                {ebayStatus.isListed ? "Listed" : "Not Listed"}
              </span>
            )}
          </div>

          <div className="space-y-2">
            {ebayStatus?.isListed ? (
              <>
                <button
                  onClick={onUpdateEbay}
                  disabled={isLoading}
                  className="w-full flex items-center gap-2 px-3 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm rounded transition"
                >
                  <Send size={16} />
                  Update Listing
                </button>
                <button
                  onClick={onDeleteEbay}
                  disabled={isLoading}
                  className="w-full flex items-center gap-2 px-3 py-2 bg-red-600/20 hover:bg-red-600/30 border border-red-500/30 disabled:opacity-50 text-red-300 text-sm rounded transition"
                >
                  <Trash2 size={16} />
                  Delete Listing
                </button>
              </>
            ) : (
              <button
                onClick={onPublishEbay}
                disabled={isLoading}
                className="w-full flex items-center gap-2 px-3 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm rounded transition"
              >
                <Plus size={16} />
                Create Listing
              </button>
            )}
          </div>
        </div>

        {/* Build Info Section */}
        <div className="bg-slate-750 rounded p-3 border border-slate-600">
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wide mb-2">
            Build Info
          </h3>
          <div className="space-y-2 text-xs text-slate-400">
            <div className="flex justify-between">
              <span>ID:</span>
              <span className="font-mono text-slate-300">{buildId.slice(0, 8)}...</span>
            </div>
            {ebayStatus?.listingId && (
              <div className="flex justify-between">
                <span>eBay ID:</span>
                <span className="font-mono text-slate-300">{ebayStatus.listingId}</span>
              </div>
            )}
            {ebayStatus?.lastUpdated && (
              <div className="flex justify-between">
                <span>Last Updated:</span>
                <span className="text-slate-300">
                  {new Date(ebayStatus.lastUpdated).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
