"use client";

import { Send, Trash2, Plus, RotateCcw, Loader2 } from "lucide-react";
import { Dock, DockItem, DockLabel, DockIcon } from "@/components/ui/dock";

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
    <div className="fixed bottom-0 left-0 right-0 z-50 flex justify-center pb-4">
      <Dock
        panelHeight={48}
        magnification={90}
        distance={150}
        className="bg-slate-800/60 border border-slate-600/50 backdrop-blur-sm"
      >
        {/* Title Generation */}
        <DockItem>
          <DockLabel>Title</DockLabel>
          <DockIcon>
            <button
              onClick={onGenerateTitle}
              disabled={isLoading}
              title="Generate eBay title with AI"
              className="w-full h-full flex items-center justify-center hover:text-blue-300 disabled:opacity-50 transition cursor-pointer"
            >
              {isLoading ? <Loader2 size={16} className="animate-spin" /> : <RotateCcw size={16} />}
            </button>
          </DockIcon>
        </DockItem>

        {/* Description Generation */}
        <DockItem>
          <DockLabel>Description</DockLabel>
          <DockIcon>
            <button
              onClick={onGenerateDescription}
              disabled={isLoading}
              title="Generate eBay description with AI"
              className="w-full h-full flex items-center justify-center hover:text-blue-300 disabled:opacity-50 transition cursor-pointer"
            >
              {isLoading ? <Loader2 size={16} className="animate-spin" /> : <RotateCcw size={16} />}
            </button>
          </DockIcon>
        </DockItem>

        {/* eBay Buttons */}
        {ebayStatus?.isListed ? (
          <>
            {/* Update eBay */}
            <DockItem>
              <DockLabel>Update</DockLabel>
              <DockIcon>
                <button
                  onClick={onUpdateEbay}
                  disabled={isLoading}
                  title="Update eBay listing with changes"
                  className="w-full h-full flex items-center justify-center hover:text-amber-300 disabled:opacity-50 transition cursor-pointer"
                >
                  {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                </button>
              </DockIcon>
            </DockItem>

            {/* Delete */}
            <DockItem>
              <DockLabel>Delete</DockLabel>
              <DockIcon>
                <button
                  onClick={onDeleteEbay}
                  disabled={isLoading}
                  title="Delete eBay listing"
                  className="w-full h-full flex items-center justify-center hover:text-red-300 disabled:opacity-50 transition cursor-pointer"
                >
                  {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                </button>
              </DockIcon>
            </DockItem>
          </>
        ) : (
          /* Create eBay */
          <DockItem>
            <DockLabel>Create</DockLabel>
            <DockIcon>
              <button
                onClick={onPublishEbay}
                disabled={isLoading}
                title="Create new eBay listing"
                className="w-full h-full flex items-center justify-center hover:text-green-300 disabled:opacity-50 transition cursor-pointer"
              >
                {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
              </button>
            </DockIcon>
          </DockItem>
        )}

        {/* Status */}
        <DockItem>
          <DockLabel>Status</DockLabel>
          <DockIcon>
            <div className="flex items-center gap-2 px-3 h-full text-xs text-slate-400">
              <span className="font-mono text-slate-300 whitespace-nowrap">{buildTitle.slice(0, 15)}</span>
              {ebayStatus && (
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                  ebayStatus.isListed
                    ? "bg-green-900/30 text-green-300"
                    : "bg-slate-700 text-slate-400"
                }`}>
                  {ebayStatus.isListed ? "✓ Listed" : "Not Listed"}
                </span>
              )}
            </div>
          </DockIcon>
        </DockItem>
      </Dock>
    </div>
  );
}
