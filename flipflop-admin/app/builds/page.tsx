"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Package, Plus, Trash2, ArrowRight, Layers } from "lucide-react";
import { api, ManualBuildSummary } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

const STATUS_LABEL: Record<string, string> = {
  in_progress: "In Progress",
  built: "Built",
  listed: "Listed",
  sold: "Sold",
};

const STATUS_COLOR: Record<string, string> = {
  in_progress: "text-amber-400 border-amber-400/30 bg-amber-400/5",
  built: "text-cyan-400 border-cyan-400/30 bg-cyan-400/5",
  listed: "text-[#00dc82] border-[#00dc82]/30 bg-[#00dc82]/5",
  sold: "text-slate-400 border-slate-400/30 bg-slate-400/5",
};

export default function BuildsPage() {
  return (
    <Suspense fallback={null}>
      <BuildsPageInner />
    </Suspense>
  );
}

function BuildsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const highlightId = searchParams.get("new") ? Number(searchParams.get("new")) : null;

  const [builds, setBuilds] = useState<ManualBuildSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    api.manualBuilds
      .list()
      .then(setBuilds)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this build?")) return;
    setDeletingId(id);
    try {
      await api.manualBuilds.delete(id);
      setBuilds((prev) => prev.filter((b) => b.id !== id));
    } catch (error) {
      console.error("Error deleting build:", error);
      alert("Failed to delete build. Please check the console for details.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#060d18] text-slate-100 px-4 py-6 md:px-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Package className="w-5 h-5 text-[#00dc82]" />
          <h1 className="text-xl font-black">Pre-Built</h1>
        </div>
        <button
          onClick={() => router.push("/add-build")}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 text-black rounded-lg transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          Create Pre-Built
        </button>
      </div>

      {/* Summary row */}
      {builds.length > 0 && (
        <div className="flex gap-4 mb-6">
          <div className="flex-1 rounded-xl p-4 border border-white/[0.07] bg-white/[0.02]">
            <p className="text-xs text-slate-500 mb-1">Total builds</p>
            <p className="text-2xl font-black">{builds.length}</p>
          </div>
          <div className="flex-1 rounded-xl p-4 border border-white/[0.07] bg-white/[0.02]">
            <p className="text-xs text-slate-500 mb-1">Total invested</p>
            <p className="text-2xl font-black text-[#00dc82]">
              {formatCurrency(builds.reduce((s, b) => s + (b.total_cost ?? 0), 0))}
            </p>
          </div>
        </div>
      )}

      {/* Build list */}
      {loading ? (
        <div className="flex items-center justify-center py-24 text-slate-500 text-sm">Loading…</div>
      ) : builds.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-slate-500">
          <Package className="w-10 h-10 opacity-20" />
          <p className="text-sm">No builds yet.</p>
          <button
            onClick={() => router.push("/add-build")}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 text-black rounded-lg transition-colors"
          >
            <Plus className="w-3.5 h-3.5" /> Create Your First Pre-Built
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {builds.map((b) => (
            <BuildCard
              key={b.id}
              build={b}
              highlighted={b.id === highlightId}
              deleting={deletingId === b.id}
              onDelete={(e) => handleDelete(b.id, e)}
              onClick={() => router.push(`/builds/${b.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function BuildCard({
  build,
  highlighted,
  deleting,
  onDelete,
  onClick,
}: {
  build: ManualBuildSummary;
  highlighted: boolean;
  deleting: boolean;
  onDelete: (e: React.MouseEvent) => void;
  onClick: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onClick()}
      className={`w-full flex items-center gap-4 p-4 rounded-xl border transition-all text-left cursor-pointer ${
        highlighted
          ? "border-[#00dc82]/50 bg-[#00dc82]/[0.06]"
          : "border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/[0.14]"
      }`}
    >
      <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
        <Layers className="w-4 h-4 text-slate-500" />
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-100 truncate">{build.name}</p>
        <p className="text-[11px] text-slate-500 mt-0.5">
          {build.component_count} component{build.component_count === 1 ? "" : "s"} · updated {formatDate(build.updated_at)}
        </p>
      </div>

      <div className={`px-2 py-1 rounded-lg border text-[10px] font-bold uppercase tracking-wider shrink-0 ${STATUS_COLOR[build.status] ?? STATUS_COLOR.in_progress}`}>
        {STATUS_LABEL[build.status] ?? build.status}
      </div>

      <div className="text-right shrink-0">
        <p className="text-xs text-slate-500">Total paid</p>
        <p className="text-sm font-semibold">{build.total_cost != null ? formatCurrency(build.total_cost) : "—"}</p>
      </div>

      <button
        onClick={onDelete}
        disabled={deleting}
        className="p-2 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-400/10 transition-colors shrink-0 disabled:opacity-40"
        title="Delete build"
      >
        <Trash2 className="w-4 h-4" />
      </button>

      <ArrowRight className="w-4 h-4 text-slate-600 shrink-0" />
    </div>
  );
}
