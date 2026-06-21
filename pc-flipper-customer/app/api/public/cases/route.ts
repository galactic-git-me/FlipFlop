import { NextResponse } from "next/server";
import type { PublicCase } from "@/lib/types";

export async function GET() {
  const cases: PublicCase[] = [
    {
      id: 1,
      name: "Lian Li Lancool 205M",
      price: 3000,
      gem_score: 70,
      form_factor: "Micro-ATX",
    },
    {
      id: 2,
      name: "Fractal Design Core 1000",
      price: 2500,
      gem_score: 68,
      form_factor: "ATX",
    },
    {
      id: 3,
      name: "Corsair 4000D Airflow",
      price: 4500,
      gem_score: 80,
      form_factor: "ATX",
    },
    {
      id: 4,
      name: "NZXT H510",
      price: 5000,
      gem_score: 78,
      form_factor: "Micro-ATX",
    },
  ];

  return NextResponse.json(cases);
}
