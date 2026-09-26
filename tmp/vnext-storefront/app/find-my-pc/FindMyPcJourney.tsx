"use client";

import { useState } from "react";
import Link from "next/link";

type Answers = {
  primary_use: string;
  budget_gbp: number;
  budget_policy: string;
  resolution: string | null;
  docker_or_vms: boolean;
  local_ai: boolean;
  quiet: boolean;
  condition_policy: string;
};

type Envelope = {
  recommendation_session_id: number;
  segment: string;
  hard_minimums: Record<string, number | boolean>;
  budget_strategy: string[];
  status: string;
};

const uses = [
  ["gaming", "Gaming"], ["software_development", "Software development"],
  ["ai", "Local AI"], ["content_creation", "Content creation"],
  ["study", "Study"], ["business", "Business & office"],
  ["family", "Family & home"],
] as const;

const initial: Answers = {
  primary_use: "", budget_gbp: 1100, budget_policy: "firm", resolution: null,
  docker_or_vms: false, local_ai: false, quiet: false, condition_policy: "NEW_ONLY",
};

export default function FindMyPcJourney() {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Answers>(initial);
  const [result, setResult] = useState<Envelope | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const update = (patch: Partial<Answers>) => setAnswers((current) => ({ ...current, ...patch }));
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

  return (
    <main className="mx-auto max-w-4xl px-5 py-20 text-white">
      <p className="mb-4 text-sm uppercase tracking-[0.3em] text-orange-400">Find My PC</p>
      <h1 className="text-4xl font-bold sm:text-6xl" style={{ fontFamily: "var(--font-heading)" }}>The right PC. Without the homework.</h1>
      <p className="mt-5 max-w-2xl text-lg text-slate-300">Tell us what you want to do. We will explain the performance that matters before choosing parts.</p>
      {result ? (
        <section className="mt-12 rounded-3xl border border-blue-500/30 bg-slate-950/80 p-6 sm:p-10" aria-live="polite">
          <p className="text-sm uppercase tracking-widest text-blue-300">Your starting point</p>
          <h2 className="mt-3 text-3xl font-semibold">{result.segment}</h2>
          <p className="mt-4 text-slate-300">We have set performance minimums for your needs. This is an assessment, not a priced offer; exact parts and delivery depend on live sourcing and checks.</p>
          <h3 className="mt-8 text-xl font-semibold">Why we would spend your money this way</h3>
          <ul className="mt-4 space-y-3 text-slate-200">{result.budget_strategy.map((reason) => <li key={reason}>• {reason}</li>)}</ul>
          <details className="mt-8 rounded-xl border border-white/20 p-4"><summary className="cursor-pointer font-medium">Show me the nerdy stuff</summary>
            <dl className="mt-5 grid gap-3 sm:grid-cols-2">{Object.entries(result.hard_minimums).map(([key, value]) => <div key={key}><dt className="text-sm text-slate-400">{key.replaceAll("_", " ")}</dt><dd>{String(value)}</dd></div>)}</dl>
          </details>
          <div className="mt-8 flex flex-wrap gap-3"><Link href="/ready-to-ship" className="rounded-full bg-orange-500 px-6 py-3 font-semibold text-black">See what is ready now</Link><button type="button" onClick={() => { setResult(null); setStep(0); }} className="rounded-full border border-white/30 px-6 py-3">Change answers</button></div>
        </section>
      ) : (
        <section className="mt-12 rounded-3xl border border-white/15 bg-slate-950/80 p-6 sm:p-10">
          <div className="mb-8 flex items-center justify-between text-sm text-slate-300"><span>Step {step + 1} of 4</span><progress value={step + 1} max={4} aria-label="Journey progress" className="w-40 accent-orange-500" /></div>
          {step === 0 && <fieldset><legend className="text-2xl font-semibold">What will you mainly use your PC for?</legend><div className="mt-6 grid gap-3 sm:grid-cols-2">{uses.map(([value, label]) => <label key={value} className={`cursor-pointer rounded-xl border p-4 ${answers.primary_use === value ? "border-orange-400 bg-orange-500/10" : "border-white/20"}`}><input className="mr-3 accent-orange-500" type="radio" name="primary-use" checked={answers.primary_use === value} onChange={() => update({ primary_use: value })} />{label}</label>)}</div></fieldset>}
          {step === 1 && <div><label htmlFor="budget" className="block text-2xl font-semibold">What would you like to spend?</label><div className="mt-6 flex items-center gap-3"><span>£</span><input id="budget" type="number" min={300} max={20000} value={answers.budget_gbp} onChange={(event) => update({ budget_gbp: Number(event.target.value) })} className="w-40 rounded-xl border border-white/30 bg-slate-900 p-3" /></div><fieldset className="mt-7"><legend className="mb-3 font-medium">How firm is that number?</legend>{[["firm", "Firm maximum"], ["small_stretch", "A small stretch is OK"], ["best_value", "Show me the best-value point"]].map(([value, label]) => <label key={value} className="mb-3 block"><input type="radio" name="budget-policy" className="mr-3 accent-orange-500" checked={answers.budget_policy === value} onChange={() => update({ budget_policy: value })} />{label}</label>)}</fieldset></div>}
          {step === 2 && <div><h2 className="text-2xl font-semibold">A little about how you use it</h2>{answers.primary_use === "gaming" && <fieldset className="mt-6"><legend className="mb-3">What resolution do you play at?</legend>{[[null, "I'm not sure"], ["1080p", "1080p"], ["1440p", "1440p"], ["4k", "4K"]].map(([value, label]) => <label key={label} className="mr-5 inline-block py-2"><input type="radio" name="resolution" className="mr-2 accent-orange-500" checked={answers.resolution === value} onChange={() => update({ resolution: value })} />{label}</label>)}</fieldset>}<div className="mt-6 space-y-4"><label className="block"><input type="checkbox" className="mr-3 accent-orange-500" checked={answers.docker_or_vms} onChange={(event) => update({ docker_or_vms: event.target.checked })} />I use Docker or virtual machines</label><label className="block"><input type="checkbox" className="mr-3 accent-orange-500" checked={answers.local_ai} onChange={(event) => update({ local_ai: event.target.checked })} />I want to run AI models locally</label><label className="block"><input type="checkbox" className="mr-3 accent-orange-500" checked={answers.quiet} onChange={(event) => update({ quiet: event.target.checked })} />A quiet machine matters to me</label></div></div>}
          {step === 3 && <fieldset><legend className="text-2xl font-semibold">How should we approach component condition?</legend><p className="mt-3 text-slate-300">New parts are the default. We will never use refurbished or used parts without your agreement and a warranty disclosure.</p><div className="mt-6 space-y-4">{[["NEW_ONLY", "New only"], ["NEW_OR_REFURBISHED", "New or approved refurbished"], ["USED_ALLOWED", "Include approved used opportunities"]].map(([value, label]) => <label key={value} className="block rounded-xl border border-white/20 p-4"><input type="radio" name="condition" className="mr-3 accent-orange-500" checked={answers.condition_policy === value} onChange={() => update({ condition_policy: value })} />{label}</label>)}</div></fieldset>}
          {error && <p role="alert" className="mt-5 text-red-300">{error}</p>}
          <div className="mt-9 flex justify-between gap-3"><button type="button" disabled={step === 0} onClick={() => setStep((current) => current - 1)} className="rounded-full border border-white/30 px-6 py-3 disabled:opacity-40">Back</button>{step < 3 ? <button type="button" disabled={step === 0 && !answers.primary_use || step === 1 && (answers.budget_gbp < 300 || answers.budget_gbp > 20000)} onClick={() => setStep((current) => current + 1)} className="rounded-full bg-orange-500 px-6 py-3 font-semibold text-black disabled:opacity-40">Continue</button> : <button type="button" disabled={pending} onClick={recommend} className="rounded-full bg-orange-500 px-6 py-3 font-semibold text-black disabled:opacity-40">{pending ? "Working it out…" : "See my starting point"}</button>}</div>
        </section>
      )}
    </main>
  );
}
