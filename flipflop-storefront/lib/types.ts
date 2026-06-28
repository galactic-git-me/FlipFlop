// pc-flipper-customer/lib/types.ts

export interface PublicPlaybook {
  id: number;
  name: string;
  slots: PublicSlotSummary[];
}

export interface PublicSlotSummary {
  id: number;
  slot_type: SlotType;
  is_customer_visible: boolean;
  tier_names: TierNames;
}

export type SlotType = "cpu" | "gpu" | "ram" | "storage" | "cooling" | "os";
export type Tier = "budget" | "mid" | "high";

export interface TierNames {
  budget: string;
  mid: string;
  high: string;
}

export interface PublicSlotWithVariants {
  slot_id: number;
  slot_type: SlotType;
  tier_names: TierNames;
  variants_by_tier: Record<Tier, PublicVariant[]>;
}

export interface PublicVariant {
  id: number;
  title: string;
  display_price: number;
  gem_score: number;
}

export interface PublicCase {
  id: number;
  name: string;
  brand: string;
  form_factor: string;
  images: string[];
  rrp_gbp: number;
  is_transparent_panel: boolean;
  notes: string | null;
}

// The customer's current build state
export interface BuildState {
  // slot_type → chosen variant
  slots: Record<SlotType, PublicVariant | null>;
  case: PublicCase | null;
  chosenWeek: string | null; // ISO week "2026-W27"
}

// Available build week from /api/orders/slots (Subsystem 2)
export interface AvailableWeek {
  week: string;        // "2026-W27"
  week_start: string;  // "2026-06-29"
  available: number;
  capacity: number;
}
