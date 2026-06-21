import { notFound } from "next/navigation";
import { getPlaybooks, getPlaybookSlots, getCases, getAvailableWeeks } from "@/lib/api";
import { getPlaybookMeta, playbookSlug } from "@/lib/playbook-config";
import { ConfiguratorClient } from "./ConfiguratorClient";

export const revalidate = 30;

interface Props {
  params: { slug: string };
  searchParams: { tier?: string };
}

export default async function ConfiguratorPage({ params, searchParams }: Props) {
  const playbooks = await getPlaybooks();

  // Resolve slug → playbook
  const playbook = playbooks.find(
    (pb) => playbookSlug(pb.name) === params.slug
  );
  if (!playbook) notFound();

  const [slots, cases, weeks] = await Promise.all([
    getPlaybookSlots(playbook.id),
    getCases(),
    getAvailableWeeks(),
  ]);

  const initialTier = (["budget", "mid", "high"].includes(searchParams.tier ?? ""))
    ? (searchParams.tier as "budget" | "mid" | "high")
    : "mid";

  const meta = getPlaybookMeta(playbook.name);

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      <div className="mb-8">
        <p className="text-sm text-muted mb-1">
          <a href="/" className="hover:text-white">FlipFlop</a> / {playbook.name}
        </p>
        <h1 className="text-3xl font-bold" style={{ fontFamily: "var(--font-heading)" }}>
          {meta.emoji} {playbook.name}
        </h1>
        <p className="text-muted mt-1">{meta.tagline}</p>
      </div>

      <ConfiguratorClient
        playbook={playbook}
        slots={slots}
        cases={cases}
        weeks={weeks}
        initialTier={initialTier}
      />
    </div>
  );
}
