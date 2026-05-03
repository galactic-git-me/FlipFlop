import { SCORE_TIER } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  score: number;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

export function FlippabilityScore({ score, size = "md", showLabel = true }: Props) {
  const tier = SCORE_TIER(score);
  const sizes = {
    sm: "w-8 h-8 text-sm",
    md: "w-11 h-11 text-base",
    lg: "w-14 h-14 text-xl",
  };
  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className={cn(
        "rounded-xl border flex items-center justify-center font-black ring-1",
        sizes[size],
        tier.bg,
        tier.color,
        tier.ring,
      )}>
        {tier.label}
      </div>
      {showLabel && (
        <div className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">{score.toFixed(0)}</div>
      )}
    </div>
  );
}
