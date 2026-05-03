import { Classification, CLASSIFICATION_CONFIG } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ClassificationBadge({ classification }: { classification: Classification }) {
  const cfg = CLASSIFICATION_CONFIG[classification];
  return (
    <span className={cn(
      "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium border",
      cfg.bg,
      cfg.color
    )}>
      <span>{cfg.emoji}</span>
      <span>{cfg.label}</span>
    </span>
  );
}
