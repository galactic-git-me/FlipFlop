import { NextResponse } from "next/server";
import type { PublicSlotWithVariants } from "@/lib/types";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const _playbookId = parseInt(id);

  // Mock slots data - same for all playbooks
  const slots: PublicSlotWithVariants[] = [
    {
      slot_id: 1,
      slot_type: "cpu",
      tier_names: {
        budget: "Ryzen 5 7500F",
        mid: "Ryzen 7 7700",
        high: "Ryzen 9 7950X"
      },
      variants_by_tier: {
        budget: [
          {
            id: 101,
            title: "Ryzen 5 7500F",
            display_price: 12000,
            gem_score: 72,
          },
        ],
        mid: [
          {
            id: 102,
            title: "Ryzen 7 7700",
            display_price: 18000,
            gem_score: 80,
          },
        ],
        high: [
          {
            id: 103,
            title: "Ryzen 9 7950X",
            display_price: 28000,
            gem_score: 88,
          },
        ],
      },
    },
    {
      slot_id: 2,
      slot_type: "gpu",
      tier_names: {
        budget: "RTX 4070",
        mid: "RTX 4070 Ti",
        high: "RTX 4090"
      },
      variants_by_tier: {
        budget: [
          {
            id: 201,
            title: "RTX 4070",
            display_price: 22000,
            gem_score: 78,
          },
        ],
        mid: [
          {
            id: 202,
            title: "RTX 4070 Ti",
            display_price: 28000,
            gem_score: 85,
          },
        ],
        high: [
          {
            id: 203,
            title: "RTX 4090",
            display_price: 42000,
            gem_score: 94,
          },
        ],
      },
    },
  ];

  return NextResponse.json(slots);
}
