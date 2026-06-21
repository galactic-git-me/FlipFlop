import { NextResponse } from "next/server";
import type { PublicPlaybook } from "@/lib/types";

export async function GET() {
  const playbooks: PublicPlaybook[] = [
    {
      id: 1,
      name: "Productivity",
      slots: [
        {
          id: 1,
          slot_type: "cpu",
          is_customer_visible: true,
          tier_names: {
            budget: "Ryzen 5 7500F",
            mid: "Ryzen 7 7700",
            high: "Ryzen 9 7950X"
          }
        },
        {
          id: 2,
          slot_type: "gpu",
          is_customer_visible: true,
          tier_names: {
            budget: "RTX 4070",
            mid: "RTX 4070 Ti",
            high: "RTX 4090"
          }
        }
      ]
    },
    {
      id: 2,
      name: "Gaming",
      slots: [
        {
          id: 3,
          slot_type: "cpu",
          is_customer_visible: true,
          tier_names: {
            budget: "Ryzen 5 7600X",
            mid: "Ryzen 7 7700X",
            high: "Ryzen 9 7950X3D"
          }
        },
        {
          id: 4,
          slot_type: "gpu",
          is_customer_visible: true,
          tier_names: {
            budget: "RTX 4070",
            mid: "RTX 4080",
            high: "RTX 4090"
          }
        }
      ]
    },
    {
      id: 3,
      name: "Creator",
      slots: [
        {
          id: 5,
          slot_type: "cpu",
          is_customer_visible: true,
          tier_names: {
            budget: "Ryzen 7 7700X",
            mid: "Ryzen 9 7950X",
            high: "Ryzen 9 7950X3D"
          }
        },
        {
          id: 6,
          slot_type: "gpu",
          is_customer_visible: true,
          tier_names: {
            budget: "RTX 4080",
            mid: "RTX 6000 Ada",
            high: "RTX 6000 Ada"
          }
        }
      ]
    }
  ];

  return NextResponse.json(playbooks);
}
