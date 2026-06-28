import Link from "next/link";
import type { PublicPlaybook, PublicSlotWithVariants, PublicCase } from "@/lib/types";
import { getPlaybookMeta } from "@/lib/playbook-config";
import { computeBudgetTotal, formatPrice } from "@/lib/utils";

interface Props {
  playbook: PublicPlaybook;
  slots: PublicSlotWithVariants[];
  cases: PublicCase[];
}

export function PlaybookCard({ playbook, slots, cases }: Props) {
  const meta = getPlaybookMeta(playbook.name);
  const budgetTotal = computeBudgetTotal(slots, cases);

  // Tier names from the first slot that has them (all slots share the same tier_names per playbook)
  const tierNames = slots[0]?.tier_names ?? { budget: "Budget", mid: "Mid", high: "High" };

  return (
    <Link href={`/configure/${meta.slug}`} className="card block p-6 hover:border-[var(--color-accent)] transition-colors group">
      <div className="text-3xl mb-3">{meta.emoji}</div>
      <h2 className="font-bold text-lg mb-1" style={{ fontFamily: "var(--font-heading)" }}>
        {playbook.name}
      </h2>
      <p className="text-sm text-muted mb-4 leading-relaxed">{meta.description}</p>

      <div className="flex gap-2 mb-5">
        {(["budget", "mid", "high"] as const).map((tier) => (
          <span key={tier} className="text-xs px-2.5 py-1 rounded-full"
            style={{ background: "var(--color-border)", color: "var(--color-text-muted)" }}>
            {tierNames[tier]}
          </span>
        ))}
      </div>

      {budgetTotal > 0 && (
        <p className="text-sm text-muted">
          from <span className="font-bold text-white">{formatPrice(budgetTotal)}</span>
        </p>
      )}

      <div className="mt-4 text-sm font-semibold text-[var(--color-accent)] group-hover:underline">
        Configure your build →
      </div>
    </Link>
  );
}
