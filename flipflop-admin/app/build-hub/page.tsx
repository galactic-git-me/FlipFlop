import Link from "next/link";
import { ArrowRight, Box, Cpu, Sparkles } from "lucide-react";

const buildTypes = [
  {
    href: "/builds",
    title: "Ready-to-Ship",
    label: "Existing builds",
    description: "Upload a build file or assemble a PC from the catalogue, then prepare it for listing and fulfilment.",
    icon: Box,
    accent: "border-orange-400/25 from-orange-400/[.08]",
  },
  {
    href: "/pc-builder",
    title: "Curated-for-you",
    label: "Playbook builds",
    description: "Manage the customer-type and budget cells, approved components, recommendations and curated build catalogue.",
    icon: Sparkles,
    accent: "border-cyan-400/25 from-cyan-400/[.08]",
  },
  {
    href: "/configurator-config",
    title: "Made-by-you",
    label: "Customer configured",
    description: "Set up the approved component choices and rules used when customers configure a build themselves.",
    icon: Cpu,
    accent: "border-violet-400/25 from-violet-400/[.08]",
  },
];

export default function BuildHubPage() {
  return (
    <div className="mx-auto w-full max-w-7xl space-y-8 p-6 lg:p-8">
      <header className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[.22em] text-cyan-300">Build operations</p>
        <h1 className="mt-2 text-3xl font-bold text-white">Builds</h1>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Choose a build workflow. Each route keeps its own tools and process while sharing the same Playbook foundation.
        </p>
      </header>

      <section aria-label="Build types" className="grid gap-4 xl:grid-cols-3">
        {buildTypes.map(({ href, title, label, description, icon: Icon, accent }) => (
          <Link
            key={href}
            href={href}
            className={`group flex min-h-64 flex-col rounded-2xl border bg-gradient-to-br ${accent} to-slate-950/90 p-6 transition duration-200 hover:-translate-y-1 hover:border-white/30 hover:shadow-xl hover:shadow-black/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300`}
          >
            <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-black/20 text-slate-100">
              <Icon aria-hidden="true" className="h-5 w-5" />
            </span>
            <span className="mt-7 text-[11px] font-semibold uppercase tracking-[.18em] text-slate-400">{label}</span>
            <span className="mt-2 text-xl font-semibold text-white">{title}</span>
            <span className="mt-2 text-sm leading-6 text-slate-400">{description}</span>
            <span className="mt-auto flex items-center gap-2 pt-6 text-sm font-semibold text-cyan-200">
              Open workflow <ArrowRight aria-hidden="true" className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </span>
          </Link>
        ))}
      </section>
    </div>
  );
}
