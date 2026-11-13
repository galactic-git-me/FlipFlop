import CommercialReviewWorkspace from '@/components/playbooks/CommercialReviewWorkspace';

const reviewAreas = ['builds', 'suppliers', 'compatibility', 'software', 'workshop', 'configurations'] as const;

export default async function CommercialReadinessPage({
  searchParams,
}: {
  searchParams?: Promise<{ area?: string | string[] }>;
}) {
  const params: { area?: string | string[] } = searchParams ? await searchParams : {};
  const { area } = params;
  const requestedArea = Array.isArray(area) ? area[0] : area;
  const initialArea = reviewAreas.find(candidate => candidate === requestedArea) ?? 'builds';
  return <CommercialReviewWorkspace initialArea={initialArea} />;
}
