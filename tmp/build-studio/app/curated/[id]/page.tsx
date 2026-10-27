import CuratedBuild from '@/components/curated/CuratedBuild';

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <CuratedBuild buildId={(await params).id} />;
}
