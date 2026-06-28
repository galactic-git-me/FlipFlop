import { getPlaybooks, getPlaybookSlots, getCases } from "@/lib/api";
import { PlaybookCard } from "@/components/PlaybookCard";
import type { PublicSlotWithVariants, PublicCase } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [playbooks, cases] = await Promise.all([
    getPlaybooks(),
    getCases(),
  ]).catch(() => [[], []]);

  // Fetch slots for all playbooks in parallel (needed for budget total)
  const slotsPerPlaybook: Record<number, PublicSlotWithVariants[]> = {};
  await Promise.all(
    playbooks.map(async (pb) => {
      try {
        slotsPerPlaybook[pb.id] = await getPlaybookSlots(pb.id);
      } catch {
        slotsPerPlaybook[pb.id] = [];
      }
    })
  );

  return (
    <div className="max-w-6xl mx-auto px-4 py-16">
      {/* Hero */}
      <div className="text-center mb-16">
        <h1 className="text-4xl sm:text-5xl font-bold mb-4 tracking-tight"
          style={{ fontFamily: "var(--font-heading)" }}>
          Your PC. <span style={{ color: "var(--color-accent)" }}>Built to order.</span>
        </h1>
        <p className="text-lg text-muted max-w-xl mx-auto">
          Curated second-hand components. Expert assembly. Tested before delivery.
          Choose your build type and configure it exactly how you want.
        </p>
      </div>

      {/* Playbook grid */}
      {playbooks.length === 0 ? (
        <p className="text-center text-muted">No builds available right now — check back soon.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {playbooks.map((pb) => (
            <PlaybookCard
              key={pb.id}
              playbook={pb}
              slots={slotsPerPlaybook[pb.id] ?? []}
              cases={cases}
            />
          ))}
        </div>
      )}

      {/* How it works */}
      <div id="how-it-works" className="mt-24 text-center">
        <h2 className="text-2xl font-bold mb-10" style={{ fontFamily: "var(--font-heading)" }}>
          How it works
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 text-left max-w-3xl mx-auto">
          {[
            { n: "1", title: "Pick your build", body: "Choose from our curated playbooks — each tailored to a specific use case and budget." },
            { n: "2", title: "Configure it", body: "Select your tier, swap any component, and choose a case. See live pricing as you go." },
            { n: "3", title: "We build and deliver", body: "We source, test, and assemble your PC. Delivered to your door within your chosen week." },
          ].map(({ n, title, body }) => (
            <div key={n}>
              <div className="text-2xl font-bold mb-2" style={{ color: "var(--color-accent)", fontFamily: "var(--font-heading)" }}>{n}.</div>
              <h3 className="font-semibold mb-2">{title}</h3>
              <p className="text-sm text-muted leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
