import Link from "next/link";
import { ArrowRight, Boxes, ListChecks, Plus } from "lucide-react";

const workflows = [
  { href: "/add-build", title: "Manual Build", description: "Create a Ready-to-Ship build and choose its components yourself.", icon: Plus, accent: "border-cyan-400/25 from-cyan-400/[.08]" },
  { href: "/gem-based-pre-builds", title: "Gem Builds", description: "Review compatible Gem-based pre-build concepts and create an unpaid sourcing draft.", icon: Boxes, accent: "border-emerald-400/25 from-emerald-400/[.08]" },
  { href: "/builds", title: "View current builds", description: "Open existing Ready-to-Ship builds and continue their preparation.", icon: ListChecks, accent: "border-violet-400/25 from-violet-400/[.08]" },
];

export default function ReadyToShipPage() {
  return <main className="mx-auto w-full max-w-7xl space-y-8 p-6 lg:p-8">
    <header className="max-w-3xl"><p className="text-xs font-semibold uppercase tracking-[.22em] text-cyan-300">Build operations · Ready-to-Ship</p><h1 className="mt-2 text-3xl font-bold text-white">Choose a Ready-to-Ship workflow</h1><p className="mt-2 text-sm leading-6 text-slate-400">Create a build manually, start from Gem candidates, or continue working on current builds.</p></header>
    <section aria-label="Ready-to-Ship workflows" className="grid gap-4 lg:grid-cols-3">{workflows.map(({ href, title, description, icon: Icon, accent }) => <Link key={href} href={href} className={`group flex min-h-64 flex-col rounded-2xl border bg-gradient-to-br ${accent} to-slate-950/90 p-6 shadow-lg transition hover:-translate-y-1 hover:border-white/35 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300`}>
      <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-black/20 text-slate-100"><Icon aria-hidden="true" className="h-5 w-5" /></span>
      <span className="mt-6 text-xl font-bold text-white">{title}</span><span className="mt-2 text-sm leading-6 text-slate-400">{description}</span>
      <span className="mt-auto flex items-center gap-2 pt-6 text-sm font-semibold text-cyan-200">Open workflow <ArrowRight aria-hidden="true" className="h-4 w-4 transition-transform group-hover:translate-x-1" /></span>
    </Link>)}</section>
  </main>;
}
