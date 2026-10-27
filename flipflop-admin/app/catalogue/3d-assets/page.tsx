"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import CataloguePhotoApproval from "@/components/playbooks/CataloguePhotoApproval";
const Workspace = dynamic(() => import("./workspace"));
const ModelInventory = dynamic(() => import("@/components/playbooks/ModelInventory"));
function CatalogueView() {
  const query = useSearchParams();
  const view = query.get("advanced") === "1" ? "advanced" : query.get("view") === "models" ? "models" : "photos";
  return view === "advanced" ? <Workspace /> : view === "models" ? <ModelInventory /> : <CataloguePhotoApproval />;
}

export default function Catalogue3DAssetsPage() {
  return <Suspense fallback={<p role="status" className="p-6">Loading catalogue…</p>}><CatalogueView /></Suspense>;
}
