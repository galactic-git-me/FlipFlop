// pc-flipper-customer/lib/utils.ts
import type { PublicSlotWithVariants, PublicCase, Tier } from "./types";

export function formatPrice(p: number): string {
  return `£${Math.round(p)}`;
}

export function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

/** Sum of cheapest budget variant per customer-visible slot + lowest case RRP */
export function computeBudgetTotal(
  slots: PublicSlotWithVariants[],
  cases: PublicCase[]
): number {
  const slotTotal = slots.reduce((sum, s) => {
    const budgetVariants = s.variants_by_tier.budget;
    if (!budgetVariants.length) return sum;
    const cheapest = budgetVariants.reduce((a, b) => a.display_price < b.display_price ? a : b);
    return sum + cheapest.display_price;
  }, 0);

  const caseRrp = cases.length
    ? Math.min(...cases.map(c => c.rrp_gbp))
    : 0;

  return slotTotal + caseRrp;
}

/** Pick highest gem-score variant for a given tier. Falls back to mid, then budget. */
export function bestVariantForTier(
  variants_by_tier: Record<Tier, { id: number; title: string; display_price: number; gem_score: number }[]>,
  tier: Tier
): { id: number; title: string; display_price: number; gem_score: number } | null {
  const candidates = variants_by_tier[tier];
  if (candidates.length) {
    return candidates.reduce((a, b) => a.gem_score > b.gem_score ? a : b);
  }
  // Fallback to adjacent tiers
  const fallbackOrder: Tier[] = tier === "high" ? ["mid", "budget"] : tier === "budget" ? ["mid", "high"] : ["budget", "high"];
  for (const t of fallbackOrder) {
    const fb = variants_by_tier[t];
    if (fb.length) return fb.reduce((a, b) => a.gem_score > b.gem_score ? a : b);
  }
  return null;
}

export function formatWeek(weekStart: string): string {
  const d = new Date(weekStart);
  return `w/c ${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`;
}
