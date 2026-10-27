"use client";

import { useState } from "react";
import Link from "next/link";

type Answers = {
  primary_use: string;
  secondary_uses: string[];
  budget_gbp: number;
  budget_policy: "firm" | "small_stretch" | "best_value";
  resolution: "1080p" | "1440p" | "4k" | null;
  refresh_rate_hz: number | null;
  gaming_priority: "competitive" | "visuals" | "balanced" | null;
  docker_or_vms: boolean;
  heavy_compilation: boolean;
  local_ai: boolean;
  ai_workload: "experimentation" | "regular" | "large_models" | null;
  creation_workload: "photo" | "video" | "3d" | "audio" | "mixed" | null;
  quiet: boolean;
  storage_gb: number | null;
  useful_life_years: number | null;
  condition_policy: "NEW_ONLY" | "NEW_OR_REFURBISHED" | "USED_ALLOWED";
};

type Requirements = Record<string, number | boolean>;
type PerformanceOption = {
  id: "save" | "recommended" | "stretch";
  label: string;
  summary: string;
  hard_minimums: Requirements;
  targets: Requirements;
  stretch_allowed: boolean;
};
type CatalogueBomCandidate = {
  role: string;
  catalogue_variant_id: number | null;
  slot_id: number | null;
  title: string | null;
};
type Envelope = {
  recommendation_session_id: number;
  envelope_version: string;
  playbook_version: string;
  segment: string;
  hard_minimums: Requirements;
  preferred_targets: Requirements;
  performance_options: PerformanceOption[];
  catalogue_bom_candidates: Array<{
    option_id: string;
    status: "candidate" | "suppressed";
    reason_code: string | null;
    bom?: { parts: CatalogueBomCandidate[] } | null;
    availability?: "not_checked";
    price?: "not_checked";
  }>;
  ready_to_ship_matches: Array<{
    product_id: number;
    title: string | null;
    hero_photo_url: string | null;
    href: string;
    capabilities: Record<string, number | null>;
  }>;
  budget_strategy: string[];
  status: string;
};

const uses = [
  ["gaming", "Gaming"], ["software_development", "Software development"],
  ["ai", "Local AI"], ["content_creation", "Content creation"],
  ["study", "Study"], ["business", "Business & office"], ["family", "Family & home"],
] as const;

const initial: Answers = {
  primary_use: "", secondary_uses: [], budget_gbp: 1100, budget_policy: "firm", resolution: null,
  refresh_rate_hz: null, gaming_priority: null, docker_or_vms: false, heavy_compilation: false,
  local_ai: false, ai_workload: null, creation_workload: null, quiet: false, storage_gb: null,
  useful_life_years: null, condition_policy: "NEW_ONLY",
};

const labels: Record<string, string> = {
  cpu_cores: "Processor cores", ram_gb: "Memory", storage_gb: "Storage",
  gpu_vram_gb: "Graphics memory", gpu_required: "Dedicated graphics required",
};

function formatRequirement(key: string, value: number | boolean) {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (key === "ram_gb" || key === "gpu_vram_gb") return `${value}GB`;
  if (key === "storage_gb") return `${value >= 1000 ? `${value / 1000}TB` : `${value}GB`}`;
  return String(value);
}

export default function FindMyPcJourney() {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Answers>(initial);
  const [result, setResult] = useState<Envelope | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const update = (patch: Partial<Answers>) => setAnswers((current) => ({ ...current, ...patch }));
  const toggleSecondaryUse = (value: string) => update({
    secondary_uses: answers.secondary_uses.includes(value)
      ? answers.secondary_uses.filter((item) => item !== value)
      : [...answers.secondary_uses, value],
  });

  async function recommend() {
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/recommendations/envelope", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(answers),
      });
      if (!response.ok) throw new Error("We could not calculate your starting point. Please try again.");
      setResult(await response.json());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Please try again.");
    } finally {
      setPending(false);
    }
  }

  const reset = () => { setResult(null); setStep(0); setError(""); };

  return (
    <main className="mx-auto max-w-4xl px-5 py-20 text-white">
      <p className="mb-4 text-sm uppercase tracking-[0.3em] text-orange-400">Find My PC</p>
      <h1 className="text-4xl font-bold sm:text-6xl" style={{ fontFamily: "var(--font-heading)" }}>The right PC. Without the homework.</h1>
      <p className="mt-5 max-w-2xl text-lg text-slate-300">Tell us what you want to do. We will explain the performance that matters before choosing parts.</p>
      {result ? (
        <section className="mt-12 rounded-3xl border border-blue-500/30 bg-slate-950/80 p-6 sm:p-10" aria-live="polite">
          <p className="text-sm uppercase tracking-widest text-blue-300">Your starting point</p>
          <h2 className="mt-3 text-3xl font-semibold">{result.segment}</h2>
          <p className="mt-4 text-slate-300">These are performance plans based on what you told us, not priced or purchasable builds. We will only show exact parts, prices or delivery choices after stock, compatibility, cost and market checks.</p>
          <h3 className="mt-8 text-xl font-semibold">Plans worth considering</h3>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {result.performance_options.map((option) => (
              <article key={option.id} className={`rounded-2xl border p-5 ${option.id === "recommended" ? "border-orange-400/60 bg-orange-500/10" : "border-white/15 bg-white/[0.03]"}`}>
                <h4 className="text-lg font-semibold">{option.label}</h4>
                <p className="mt-2 text-sm text-slate-300">{option.summary}</p>
                {Object.keys(option.targets).length > 0 && <dl className="mt-4 space-y-2 text-sm">{Object.entries(option.targets).map(([key, value]) => <div key={key} className="flex justify-between gap-3"><dt className="text-slate-400">{labels[key] ?? key}</dt><dd className="font-medium">{formatRequirement(key, value)}</dd></div>)}</dl>}
                {(() => {
                  const candidate = result.catalogue_bom_candidates.find((item) => item.option_id === option.id);
                  return candidate?.status === "candidate" && candidate.bom ? <div className="mt-5 border-t border-white/10 pt-4"><p className="text-sm font-medium text-emerald-300">Compatibility checked catalogue candidate</p><ul className="mt-2 space-y-1 text-xs text-slate-300">{candidate.bom.parts.map((part) => <li key={`${part.role}-${part.catalogue_variant_id}`}>{labels[part.role] ?? part.role}: {part.title}</li>)}</ul><p className="mt-2 text-xs text-slate-400">Supplier stock, current price and delivery have not been checked.</p></div> : <p className="mt-4 border-t border-white/10 pt-3 text-xs text-slate-400">No complete catalogue build passed the required compatibility and evidence checks for this plan.</p>;
                })()}
                {option.id === "stretch" && <p className="mt-3 text-xs text-slate-400">Your answers allow us to consider a stretch, but we will show it only if the improvement is worthwhile.</p>}
              </article>
            ))}
          {result.ready_to_ship_matches.length > 0 && <section className="mt-8"><h3 className="text-xl font-semibold">Ready to ship and suitable for your needs</h3><div className="mt-4 grid gap-3 sm:grid-cols-2">{result.ready_to_ship_matches.map((match) => <Link key={match.product_id} href={match.href} className="rounded-xl border border-emerald-400/30 bg-emerald-500/5 p-4 transition-colors hover:border-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-400"><span className="font-medium">{match.title}</span><span className="mt-2 block text-xs text-emerald-200">Listed prebuilt · capability evidence meets your minimums</span></Link>)}</div></section>}
          </div>
          <h3 className="mt-8 text-xl font-semibold">Why we would spend your money this way</h3>
          <ul className="mt-4 space-y-3 text-slate-200">{result.budget_strategy.map((reason) => <li key={reason}>• {reason}</li>)}</ul>
          <details className="mt-8 rounded-xl border border-white/20 p-4"><summary className="cursor-pointer font-medium">Show me the nerdy stuff</summary>
            <p className="mt-4 text-xs text-slate-400">Playbook {result.playbook_version} · envelope rules {result.envelope_version}</p>
            <dl className="mt-4 grid gap-3 sm:grid-cols-2">{Object.entries(result.hard_minimums).map(([key, value]) => <div key={key}><dt className="text-sm text-slate-400">{labels[key] ?? key.replaceAll("_", " ")}</dt><dd>{formatRequirement(key, value)}</dd></div>)}</dl>
          </details>
          <div className="mt-8 flex flex-wrap gap-3"><Link href="/ready-to-ship" className="rounded-full bg-orange-500 px-6 py-3 font-semibold text-black">See what is ready now</Link><button type="button" onClick={reset} className="rounded-full border border-white/30 px-6 py-3">Change answers</button></div>
        </section>
      ) : (
        <section className="mt-12 rounded-3xl border border-white/15 bg-slate-950/80 p-6 sm:p-10">
          <div className="mb-8 flex items-center justify-between gap-4 text-sm text-slate-300"><span>Step {step + 1} of 5</span><progress value={step + 1} max={5} aria-label="Journey progress" className="w-40 accent-orange-500" /></div>
          {step === 0 && <fieldset><legend className="text-2xl font-semibold">What will you mainly use your PC for?</legend><p className="mt-2 text-sm text-slate-400">Choose the closest fit. You can add another use too.</p><div className="mt-6 grid gap-3 sm:grid-cols-2">{uses.map(([value, label]) => <label key={value} className={`cursor-pointer rounded-xl border p-4 transition-colors focus-within:ring-2 focus-within:ring-orange-400 ${answers.primary_use === value ? "border-orange-400 bg-orange-500/10" : "border-white/20"}`}><input className="mr-3 accent-orange-500" type="radio" name="primary-use" checked={answers.primary_use === value} onChange={() => update({ primary_use: value })} />{label}</label>)}</div><fieldset className="mt-7"><legend className="mb-3 font-medium">Anything else you will use it for?</legend>{uses.filter(([value]) => value !== answers.primary_use).map(([value, label]) => <label key={value} className="mr-5 inline-block py-2 text-slate-300"><input type="checkbox" className="mr-2 accent-orange-500" checked={answers.secondary_uses.includes(value)} onChange={() => toggleSecondaryUse(value)} />{label}</label>)}</fieldset><p className="mt-5 text-xs text-slate-400">Why we ask: your main use sets the minimum performance; other demanding tasks can raise it.</p></fieldset>}
          {step === 1 && <div><label htmlFor="budget" className="block text-2xl font-semibold">What would you like to spend?</label><p className="mt-2 text-sm text-slate-400">Why we ask: it helps us focus on useful performance within your comfort zone.</p><div className="mt-6 flex items-center gap-3"><span>£</span><input id="budget" type="number" min={300} max={20000} value={answers.budget_gbp} onChange={(event) => update({ budget_gbp: Number(event.target.value) })} className="w-40 rounded-xl border border-white/30 bg-slate-900 p-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-400" /></div><fieldset className="mt-7"><legend className="mb-3 font-medium">Is that a firm ceiling?</legend>{[["firm", "Firm maximum"], ["small_stretch", "A small stretch is OK"], ["best_value", "Show me the best-value point"]].map(([value, label]) => <label key={value} className="mb-3 block"><input type="radio" name="budget-policy" className="mr-3 accent-orange-500" checked={answers.budget_policy === value} onChange={() => update({ budget_policy: value as Answers["budget_policy"] })} />{label}</label>)}</fieldset></div>}
          {step === 2 && <div><h2 className="text-2xl font-semibold">What does your work or play look like?</h2><p className="mt-2 text-sm text-slate-400">Skip anything you are unsure about. We will not assume specialist needs.</p>
            {(answers.primary_use === "gaming" || answers.secondary_uses.includes("gaming")) && <fieldset className="mt-6 rounded-xl border border-white/10 p-4"><legend className="px-2 font-medium">For gaming</legend><label className="block">Resolution<div className="mt-2 flex flex-wrap gap-4">{[[null, "I'm not sure"], ["1080p", "1080p"], ["1440p", "1440p"], ["4k", "4K"]].map(([value, label]) => <label key={label}><input type="radio" name="resolution" className="mr-2 accent-orange-500" checked={answers.resolution === value} onChange={() => update({ resolution: value as Answers["resolution"] })} />{label}</label>)}</div></label><label className="mt-4 block">Monitor refresh rate<select value={answers.refresh_rate_hz ?? ""} onChange={(event) => update({ refresh_rate_hz: event.target.value ? Number(event.target.value) : null })} className="ml-3 rounded-lg border border-white/20 bg-slate-900 p-2"><option value="">I'm not sure</option><option value="60">60Hz</option><option value="120">120Hz</option><option value="144">144Hz</option><option value="165">165Hz</option><option value="240">240Hz or higher</option></select></label><fieldset className="mt-4"><legend>What matters more?</legend>{[["balanced", "A balance"], ["competitive", "Fast, responsive play"], ["visuals", "Visual detail"]].map(([value, label]) => <label key={value} className="mr-4 inline-block py-2"><input type="radio" name="gaming-priority" className="mr-2 accent-orange-500" checked={answers.gaming_priority === value} onChange={() => update({ gaming_priority: value as Answers["gaming_priority"] })} />{label}</label>)}</fieldset></fieldset>}
            {(answers.primary_use === "software_development" || answers.secondary_uses.includes("software_development")) && <fieldset className="mt-6 rounded-xl border border-white/10 p-4"><legend className="px-2 font-medium">For software development</legend><label className="block py-2"><input type="checkbox" className="mr-3 accent-orange-500" checked={answers.docker_or_vms} onChange={(event) => update({ docker_or_vms: event.target.checked })} />I use Docker or virtual machines</label><label className="block py-2"><input type="checkbox" className="mr-3 accent-orange-500" checked={answers.heavy_compilation} onChange={(event) => update({ heavy_compilation: event.target.checked })} />I regularly compile large projects</label></fieldset>}
            {(answers.primary_use === "ai" || answers.secondary_uses.includes("ai")) && <fieldset className="mt-6 rounded-xl border border-white/10 p-4"><legend className="px-2 font-medium">For local AI</legend><p className="text-sm text-slate-400">Model size and software affect what fits in graphics memory.</p><div className="mt-3 space-y-2">{[["experimentation", "Experimenting"], ["regular", "Regular use"], ["large_models", "Larger models, where supported"]].map(([value, label]) => <label key={value} className="block"><input type="radio" name="ai-workload" className="mr-3 accent-orange-500" checked={answers.ai_workload === value} onChange={() => update({ local_ai: true, ai_workload: value as Answers["ai_workload"] })} />{label}</label>)}</div></fieldset>}
            {(answers.primary_use === "content_creation" || answers.secondary_uses.includes("content_creation")) && <fieldset className="mt-6 rounded-xl border border-white/10 p-4"><legend className="px-2 font-medium">For content creation</legend><div className="flex flex-wrap gap-4">{[["photo", "Photo"], ["video", "Video"], ["3d", "3D"], ["audio", "Audio"], ["mixed", "A mix"]].map(([value, label]) => <label key={value}><input type="radio" name="creation-workload" className="mr-2 accent-orange-500" checked={answers.creation_workload === value} onChange={() => update({ creation_workload: value as Answers["creation_workload"] })} />{label}</label>)}</div></fieldset>}
            {!(["gaming", "software_development", "ai", "content_creation"].includes(answers.primary_use) || answers.secondary_uses.some((item) => ["gaming", "software_development", "ai", "content_creation"].includes(item))) && <p className="mt-6 rounded-xl bg-white/5 p-4 text-slate-300">No specialist workload questions needed for this choice. Continue when ready.</p>}
          </div>}
          {step === 3 && <div><h2 className="text-2xl font-semibold">Any practical preferences?</h2><p className="mt-2 text-sm text-slate-400">Why we ask: these can change case, cooling and storage choices later.</p><label className="mt-6 block"><input type="checkbox" className="mr-3 accent-orange-500" checked={answers.quiet} onChange={(event) => update({ quiet: event.target.checked })} />A quiet machine matters to me</label><label className="mt-6 block">Minimum storage<select value={answers.storage_gb ?? ""} onChange={(event) => update({ storage_gb: event.target.value ? Number(event.target.value) : null })} className="ml-3 rounded-lg border border-white/20 bg-slate-900 p-2"><option value="">I'm not sure</option><option value="500">At least 500GB</option><option value="1000">At least 1TB</option><option value="2000">At least 2TB</option><option value="4000">At least 4TB</option></select></label><label className="mt-6 block">How long would you like to keep it?<select value={answers.useful_life_years ?? ""} onChange={(event) => update({ useful_life_years: event.target.value ? Number(event.target.value) : null })} className="ml-3 rounded-lg border border-white/20 bg-slate-900 p-2"><option value="">I'm not sure</option><option value="3">Around 3 years</option><option value="5">Around 5 years</option><option value="7">7 years or more</option></select></label></div>}
          {step === 4 && <fieldset><legend className="text-2xl font-semibold">How should we approach component condition?</legend><p className="mt-3 text-slate-300">New parts are the default. Refurbished or used parts need your explicit agreement and clear warranty information.</p><p className="mt-2 text-sm text-slate-400">Why we ask: condition affects sourcing, warranty and value.</p><div className="mt-6 space-y-4">{[["NEW_ONLY", "New only"], ["NEW_OR_REFURBISHED", "New or approved refurbished"], ["USED_ALLOWED", "Include approved used opportunities"]].map(([value, label]) => <label key={value} className="block rounded-xl border border-white/20 p-4"><input type="radio" name="condition" className="mr-3 accent-orange-500" checked={answers.condition_policy === value} onChange={() => update({ condition_policy: value as Answers["condition_policy"] })} />{label}</label>)}</div></fieldset>}
          {error && <p role="alert" className="mt-5 text-red-300">{error}</p>}
          <div className="mt-9 flex justify-between gap-3"><button type="button" disabled={step === 0} onClick={() => setStep((current) => current - 1)} className="rounded-full border border-white/30 px-6 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-400 disabled:opacity-40">Back</button>{step < 4 ? <button type="button" disabled={step === 0 && !answers.primary_use || step === 1 && (answers.budget_gbp < 300 || answers.budget_gbp > 20000)} onClick={() => setStep((current) => current + 1)} className="rounded-full bg-orange-500 px-6 py-3 font-semibold text-black focus-visible:outline focus-visible:outline-2 focus-visible:outline-white disabled:opacity-40">Continue</button> : <button type="button" disabled={pending} onClick={recommend} className="rounded-full bg-orange-500 px-6 py-3 font-semibold text-black focus-visible:outline focus-visible:outline-2 focus-visible:outline-white disabled:opacity-40">{pending ? "Working it out…" : "See my starting point"}</button>}</div>
        </section>
      )}
    </main>
  );
}
