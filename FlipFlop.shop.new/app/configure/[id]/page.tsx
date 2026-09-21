import { getCuratedBuilds, getCases } from '@/lib/api'
import { ConfiguratorClient } from './ConfiguratorClient'
import { notFound } from 'next/navigation'

export const dynamic = 'force-dynamic'

interface PageProps {
  params: Promise<{ id: string }>
}

export default async function ConfigurePage({ params }: PageProps) {
  const { id } = await params
  const { builds } = await getCuratedBuilds()
  const cases = await getCases()
  
  const build = builds.find(b => 
    b.id.toLowerCase().replace(/[^a-z0-9]/g, '-') === id.toLowerCase()
  )
  
  if (!build) {
    notFound()
  }

  // Check if build is incomplete
  if (build.missing_components.length > 0) {
    return (
      <div className="min-h-screen bg-[var(--background)] py-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-4xl font-bold mb-4">Build Coming Soon</h1>
          <p className="text-[var(--muted)] mb-8">
            {build.name} is still being prepared. Some components are pending approval.
          </p>
          <div className="p-6 bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg inline-block text-left">
            <h3 className="font-bold mb-2">Missing Components:</h3>
            <ul className="list-disc list-inside text-[var(--muted)]">
              {build.missing_components.map(comp => (
                <li key={comp}>{comp}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    )
  }

  return <ConfiguratorClient build={build} cases={cases} />
}
