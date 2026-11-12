"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import CommercialReviewWorkspace from '@/components/playbooks/CommercialReviewWorkspace';

const areas = new Set(["builds", "suppliers", "compatibility", "software", "workshop", "configurations"]);
function CommercialReadinessContent() {
  const query = useSearchParams();
  const requested = query.get("area") || "builds";
  const initialArea = areas.has(requested) ? requested as "builds" | "suppliers" | "compatibility" | "software" | "workshop" | "configurations" : "builds";
  return <CommercialReviewWorkspace key={initialArea} initialArea={initialArea} />;
}

export default function CommercialReadinessPage(){return <Suspense fallback={<p className="p-6 text-sm text-slate-400">Loading commercial reviews…</p>}><CommercialReadinessContent/></Suspense>;}
