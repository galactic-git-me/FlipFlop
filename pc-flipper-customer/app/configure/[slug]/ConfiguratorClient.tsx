"use client";
import type { PublicPlaybook, PublicSlotWithVariants, PublicCase, AvailableWeek, Tier } from "@/lib/types";

interface Props {
  playbook: PublicPlaybook;
  slots: PublicSlotWithVariants[];
  cases: PublicCase[];
  weeks: AvailableWeek[];
  initialTier: Tier;
}

export function ConfiguratorClient({ playbook, slots }: Props) {
  return (
    <div className="text-muted text-sm">
      Configurator loading… ({slots.length} slots for {playbook.name})
    </div>
  );
}
