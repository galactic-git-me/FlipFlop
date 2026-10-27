"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ExternalLink, Loader2, RefreshCw, Save, Sparkles } from "lucide-react";
import { api, AiReadyToShipProposal } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export default function AiBuildPage() {
  const router = useRouter();
  const [proposal, setProposal] = useState<AiReadyToShipProposal | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [buildName, setBuildName] = useState("");

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.manualBuilds.generateAi();
      setProposal(result);
      setBuildName(result.build_name);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The AI build could not be generated.");
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    if (!proposal) return;
    setSaving(true);
    setError(null);
    try {
      const build = await api.manualBuilds.createAi({
        component_ids: proposal.components.map((component) => component.id),
        playbook_id: proposal.playbook_recommendation.playbook_id,
        curated_build_id: proposal.playbook_recommendation.id,
        build_name: buildName.trim() || proposal.build_name,
        rationale: proposal.rationale,
        playbook_rationale: proposal.playbook_recommendation.rationale,
      });
      router.push(`/builds?new=${build.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The AI build could not be saved.");
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#060d18] px-4 py-6 text-slate-100 md:px-8">
      <div className="mx-auto max-w-5xl">
        <button onClick={() => router.push("/builds")} className="mb-5 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white"><ArrowLeft className="h-4 w-4" /> Back to Pre-Built</button>
        <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-[#00dc82]"><Sparkles className="h-4 w-4" /> Gem Radar AI</p>
            <h1 className="text-2xl font-bold">Create an AI-sourced build</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">The model will assemble a build from active SUPER_GEM and GEM listings and recommend a Playbook segment. Review the parts and live listings before saving.</p>
          </div>
          <button onClick={generate} disabled={loading || saving} className="inline-flex items-center gap-2 rounded-lg bg-[#00dc82] px-4 py-2.5 text-sm font-bold text-black transition hover:bg-[#18e991] disabled:opacity-50">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : proposal ? <RefreshCw className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
            {loading ? "Building recommendation…" : proposal ? "Generate another" : "Generate build"}
          </button>
        </header>

        {error && <div role="alert" className="mb-5 rounded-lg border border-red-400/30 bg-red-400/10 px-4 py-3 text-sm text-red-200">{error}</div>}

        {!proposal && !loading && <section className="rounded-2xl border border-white/10 bg-white/[0.025] p-8 text-center">
          <Sparkles className="mx-auto mb-3 h-8 w-8 text-[#00dc82]" />
          <h2 className="font-semibold">Ready to find the strongest live parts</h2>
          <p className="mt-2 text-sm text-slate-400">The recommendation uses current active buy-it-now Gem Radar listings. It does not buy or publish anything.</p>
        </section>}

        {loading && <div className="flex items-center justify-center gap-3 py-20 text-sm text-slate-400"><Loader2 className="h-5 w-5 animate-spin text-[#00dc82]" /> Comparing active GEM listings and Playbook segments…</div>}

        {proposal && <div className="space-y-5">
          <section className="rounded-2xl border border-white/10 bg-white/[0.025] p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
              <div><p className="text-xs uppercase tracking-wider text-slate-500">AI recommendation</p><h2 className="mt-1 text-lg font-bold">{proposal.build_name}</h2></div>
              <div className="text-right"><p className="text-xs text-slate-500">Estimated sourcing cost</p><p className="text-xl font-bold text-[#00dc82]">{formatCurrency(proposal.estimated_parts_cost)}</p></div>
            </div>
            <p className="text-sm leading-6 text-slate-300">{proposal.rationale || "Build assembled from the best available GEM and SUPER_GEM candidates."}</p>
            <div className="mt-4 rounded-xl border border-cyan-300/20 bg-cyan-300/[0.05] p-4">
              <p className="text-xs font-bold uppercase tracking-wider text-cyan-200">Recommended Playbook segment</p>
              <p className="mt-1 font-semibold">{proposal.playbook_recommendation.segment} · {proposal.playbook_recommendation.tier} — {proposal.playbook_recommendation.name}</p>
              <p className="mt-1 text-sm text-slate-400">{proposal.playbook_recommendation.rationale || proposal.playbook_recommendation.use}</p>
            </div>
          </section>

          <section className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.025]">
            <div className="border-b border-white/[0.07] px-5 py-4"><h2 className="font-semibold">Selected Gem Radar candidates</h2><p className="mt-1 text-xs text-slate-500">Live asking prices; these are not purchases or paid costs.</p></div>
            <div className="divide-y divide-white/[0.06]">
              {proposal.components.map((component) => <article key={component.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                {component.image_url ? <img src={component.image_url} alt="" className="h-12 w-12 rounded-lg bg-slate-800 object-contain" /> : <div className="h-12 w-12 rounded-lg bg-slate-800" />}
                <div className="min-w-0 flex-1"><p className="text-xs font-bold uppercase tracking-wide text-slate-500">{component.slot}</p><p className="truncate text-sm font-medium text-slate-100">{component.name}</p><p className="mt-1 text-[11px] text-slate-500">{component.classification.replace("_", " ")} · Deal score {component.deal_score.toFixed(0)}</p></div>
                <p className="font-semibold">{formatCurrency(component.price)}</p>
                <a href={component.listing_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2.5 py-2 text-xs text-cyan-200 hover:bg-white/[0.05]">View listing <ExternalLink className="h-3 w-3" /></a>
              </article>)}
            </div>
          </section>

          {proposal.compatibility_notes.length > 0 && <section className="rounded-xl border border-amber-300/20 bg-amber-300/[0.04] p-4"><p className="text-xs font-bold uppercase tracking-wide text-amber-200">Compatibility notes to review</p><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-100/80">{proposal.compatibility_notes.map((note, index) => <li key={index}>{note}</li>)}</ul></section>}

          <section className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.025] p-5">
            <label className="min-w-[240px] flex-1 text-xs font-semibold text-slate-400">Build name<input value={buildName} onChange={(event) => setBuildName(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1422] px-3 py-2 text-sm text-white outline-none focus:border-[#00dc82]/50" /></label>
            <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-cyan-300 px-4 py-2.5 text-sm font-bold text-slate-950 transition hover:bg-cyan-200 disabled:opacity-50">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{saving ? "Saving…" : "Save AI-created draft"}</button>
          </section>
          <p className="text-xs text-slate-500">Saving records an in-progress build with unpaid sourcing candidates. No listing is purchased, and Total paid stays at £0 until you record confirmed purchases.</p>
        </div>}
      </div>
    </main>
  );
}
