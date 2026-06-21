import { NextResponse } from "next/server";
import type { PublicSlotWithVariants } from "@/lib/types";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const playbookId = parseInt(id);

  // Mock slots data - same for all playbooks
  const slots: PublicSlotWithVariants[] = [
    {
      id: 1,
      name: "CPU",
      tier: "Budget",
      spec: "Ryzen 5 7500F",
      variant_count: 5,
      price: 12000,
      gem_score: 72,
      variants: [
        {
          id: 101,
          name: "Ryzen 5 7500F",
          spec: "6C/12T, 3.7-5.1GHz",
          price: 12000,
          gem_score: 72,
        },
        {
          id: 102,
          name: "Ryzen 7 7700",
          spec: "8C/16T, 3.8-5.4GHz",
          price: 18000,
          gem_score: 80,
        },
      ],
    },
    {
      id: 2,
      name: "GPU",
      tier: "Budget",
      spec: "RTX 4070",
      variant_count: 5,
      price: 22000,
      gem_score: 78,
      variants: [
        {
          id: 201,
          name: "RTX 4070",
          spec: "12GB, 2475 MHz",
          price: 22000,
          gem_score: 78,
        },
        {
          id: 202,
          name: "RTX 4070 Ti",
          spec: "12GB, 2610 MHz",
          price: 28000,
          gem_score: 85,
        },
      ],
    },
    {
      id: 3,
      name: "RAM",
      tier: "Budget",
      spec: "32GB DDR5",
      variant_count: 5,
      price: 8000,
      gem_score: 70,
      variants: [
        {
          id: 301,
          name: "32GB DDR5 5600MHz",
          spec: "Crucial Ballistix",
          price: 8000,
          gem_score: 70,
        },
      ],
    },
  ];

  return NextResponse.json(slots);
}
