import Link from "next/link";
import { ArrowRight, Box, Cpu, Sparkles } from "lucide-react";
import PixelCard from "../../components/ui/PixelCard";

const buildTypes = [
  {
    href: "/ready-to-ship",
    title: "Ready-to-Ship",
    label: "Build workflows",
    description: "Create a build manually, start with Gem-based pre-build concepts, or continue working on current builds.",
    icon: Box,
    titleColor: "admin-lime-title",
    accent: "border-orange-400/25 from-orange-400/[.08]",
  },
  {
    href: "/pc-builder",
    title: "Curated-for-you",
    label: "Playbook builds",
    description: "Manage the customer-type and budget cells, approved components, recommendations and curated build catalogue.",
    icon: Sparkles,
    titleColor: "admin-lime-title",
    accent: "border-cyan-400/25 from-cyan-400/[.08]",
  },
  {
    href: "/configurator-config",
    title: "Made-by-you",
    label: "Customer configured",
    description: "Set up the approved component choices and rules used when customers configure a build themselves.",
    icon: Cpu,
    titleColor: "admin-lime-title",
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
        {buildTypes.map(({ href, title, label, description, icon: Icon, accent, titleColor }) => (
          <Link
            key={href}
            href={href}
            className={`group block min-h-64 overflow-hidden rounded-2xl border bg-gradient-to-br ${accent} to-slate-950/90 p-0 shadow-[0_16px_32px_rgba(0,0,0,.38),inset_0_1px_0_rgba(255,255,255,.14)] transition duration-300 hover:-translate-y-1 hover:border-white/35 hover:shadow-[0_25px_48px_rgba(0,0,0,.48),inset_0_1px_0_rgba(255,255,255,.2)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300`}
          >
            <PixelCard variant="brand" className="build-workflow-pixels flex min-h-64 flex-col rounded-[inherit] border-0 bg-transparent p-6 shadow-none backdrop-blur-0">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-black/20 text-slate-100">
              <Icon aria-hidden="true" className="h-5 w-5" />
            </span>
            <span className="admin-lime-title mt-6 text-[11px] font-semibold uppercase tracking-[.18em]">{label}</span>
            <span className={`mt-2 text-xl font-bold ${titleColor}`}>{title}</span>
            <span className="mt-2 text-sm leading-6 text-slate-400">{description}</span>
            <span className="admin-orange-blue-title mt-auto flex items-center gap-2 pt-6 text-sm font-semibold">
              Open workflow <ArrowRight aria-hidden="true" className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </span>
            </PixelCard>
          </Link>
        ))}
      </section>
    </div>
  );
}
