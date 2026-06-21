import { NextResponse } from "next/server";
import type { PublicCase } from "@/lib/types";

export async function GET() {
  const cases: PublicCase[] = [
    {
      id: 1,
      name: "Lian Li Lancool 205M",
      brand: "Lian Li",
      form_factor: "Micro-ATX",
      images: [],
      rrp_gbp: 3000,
      is_transparent_panel: false,
      notes: null,
    },
    {
      id: 2,
      name: "Fractal Design Core 1000",
      brand: "Fractal Design",
      form_factor: "ATX",
      images: [],
      rrp_gbp: 2500,
      is_transparent_panel: false,
      notes: null,
    },
    {
      id: 3,
      name: "Corsair 4000D Airflow",
      brand: "Corsair",
      form_factor: "ATX",
      images: [],
      rrp_gbp: 4500,
      is_transparent_panel: true,
      notes: null,
    },
    {
      id: 4,
      name: "NZXT H510",
      brand: "NZXT",
      form_factor: "Micro-ATX",
      images: [],
      rrp_gbp: 5000,
      is_transparent_panel: false,
      notes: null,
    },
  ];

  return NextResponse.json(cases);
}
