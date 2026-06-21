import { NextResponse } from "next/server";
import type { PublicPlaybook } from "@/lib/types";

export async function GET() {
  const playbooks: PublicPlaybook[] = [
    {
      id: 1,
      name: "Productivity",
      description: "Perfect for everyday computing, office work, and streaming",
      color: "blue",
      gem_score: 75,
      budget_total: 45000,
      tier_count: 3,
    },
    {
      id: 2,
      name: "Gaming",
      description: "High performance for AAA games at 1440p 144Hz+",
      color: "red",
      gem_score: 88,
      budget_total: 72000,
      tier_count: 3,
    },
    {
      id: 3,
      name: "Creator",
      description: "Video editing, 3D rendering, streaming, and more",
      color: "purple",
      gem_score: 92,
      budget_total: 95000,
      tier_count: 3,
    },
  ];

  return NextResponse.json(playbooks);
}
