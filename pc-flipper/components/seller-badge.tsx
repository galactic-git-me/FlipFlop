import { Listing } from "@/lib/types";

export const SELLER_TYPE_CONFIG = {
  shop:        { label: "Shop",    emoji: "🏪", color: "text-sky-400",    bg: "bg-sky-400/10 border-sky-400/25"       },
  refurb_shop: { label: "Refurb",  emoji: "🔧", color: "text-purple-400", bg: "bg-purple-400/10 border-purple-400/25" },
  flipper:     { label: "Flipper", emoji: "🔄", color: "text-yellow-400", bg: "bg-yellow-400/10 border-yellow-400/25" },
  private:     { label: "Private", emoji: "👤", color: "text-slate-400",  bg: "bg-slate-400/10 border-slate-400/25"   },
} as const;

export function SellerBadge({ listing: l }: { listing: Listing }) {
  if (!l.seller_type) return null;
  const cfg = SELLER_TYPE_CONFIG[l.seller_type as keyof typeof SELLER_TYPE_CONFIG];
  if (!cfg) return null;

  return (
    <div className="flex items-center gap-1 flex-wrap">
      <span
        className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold border ${cfg.bg} ${cfg.color}`}
      >
        <span>{cfg.emoji}</span>
        {cfg.label}
        {l.seller_has_shop && <span className="ml-0.5 opacity-60">·Shop</span>}
      </span>
      {l.seller_feedback_pct != null && (
        <span
          className={`text-[10px] font-medium ${
            l.seller_feedback_pct >= 99
              ? "text-[#00dc82]"
              : l.seller_feedback_pct >= 95
              ? "text-yellow-400"
              : "text-red-400"
          }`}
        >
          {l.seller_feedback_pct.toFixed(1)}%
          {l.seller_feedback_count != null && (
            <span className="text-slate-600 ml-0.5">
              (
              {l.seller_feedback_count >= 1000
                ? `${(l.seller_feedback_count / 1000).toFixed(1)}k`
                : l.seller_feedback_count}
              )
            </span>
          )}
        </span>
      )}
    </div>
  );
}
