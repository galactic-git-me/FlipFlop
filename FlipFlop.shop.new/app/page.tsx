import { getCuratedBuilds } from '@/lib/api'
import { formatPrice, slugify, getBuildTierColor, getSegmentIcon, isBespokeOnly } from '@/lib/utils'
import Link from 'next/link'

export const dynamic = 'force-dynamic'

export default async function Home() {
  const { builds } = await getCuratedBuilds()
  
  // Group builds by segment (customer_type)
  const buildsBySegment = builds.reduce((acc, build) => {
    if (!acc[build.segment]) {
      acc[build.segment] = []
    }
    acc[build.segment].push(build)
    return acc
  }, {} as Record<string, typeof builds>)

  // Sort segments by order of importance
  const segmentOrder = [
    'Great-value Gaming',
    'High-performance Gaming',
    'Student Hybrid',
    'Business & Office',
    'Content Creation',
    'AI Workstation',
    'Software Development',
    'Family & Home',
  ]

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Hero Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            Professional PC Builds,<br />
            <span className="text-[var(--accent)]">Curated Components</span>
          </h1>
          <p className="text-xl text-[var(--muted)] max-w-2xl mx-auto mb-8">
            Every FlipFlop build is assembled from carefully selected components, 
            tested, and delivered with warranty. Choose your purpose and tier below.
          </p>
        </div>
      </section>

      {/* Builds by Segment */}
      <section className="pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto space-y-16">
          {segmentOrder.map((segment) => {
            const segmentBuilds = buildsBySegment[segment]
            if (!segmentBuilds || segmentBuilds.length === 0) return null

            return (
              <div key={segment} className="space-y-6">
                <div className="flex items-center gap-3">
                  <span className="text-3xl">{getSegmentIcon(segment)}</span>
                  <h2 className="text-3xl font-bold">{segment}</h2>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {segmentBuilds.map((build) => {
                    const bespoke = isBespokeOnly(build.id)
                    const incomplete = build.missing_components.length > 0
                    
                    return (
                      <Link
                        key={build.id}
                        href={bespoke ? '#' : `/configure/${slugify(build.id)}`}
                        className={`
                          block p-6 rounded-lg border border-[var(--card-border)] 
                          bg-[var(--card-bg)] transition-all
                          ${bespoke ? 'opacity-75 cursor-not-allowed' : 'hover:border-[var(--accent)] hover:shadow-lg'}
                        `}
                        onClick={(e) => bespoke && e.preventDefault()}
                      >
                        {/* Tier Badge */}
                        <div className="flex justify-between items-start mb-3">
                          <span className={`text-sm font-medium ${getBuildTierColor(build.tier)}`}>
                            {build.tier}
                          </span>
                          {bespoke && (
                            <span className="text-xs px-2 py-1 rounded bg-amber-900/30 text-amber-400 border border-amber-700/50">
                              Bespoke / Consult Only
                            </span>
                          )}
                          {incomplete && !bespoke && (
                            <span className="text-xs px-2 py-1 rounded bg-orange-900/30 text-orange-400 border border-orange-700/50">
                              Coming Soon
                            </span>
                          )}
                        </div>

                        {/* Build Name & Description */}
                        <h3 className="text-xl font-bold mb-2">{build.name}</h3>
                        <p className="text-[var(--muted)] text-sm mb-4">{build.description}</p>

                        {/* Use Case */}
                        <p className="text-xs text-[var(--muted)] mb-4 italic">{build.use}</p>

                        {/* Key Specs */}
                        <div className="space-y-1 mb-4 text-sm">
                          <div className="flex items-center gap-2">
                            <span className="text-[var(--muted)]">CPU:</span>
                            <span className="text-xs">{build.components.cpu}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-[var(--muted)]">GPU:</span>
                            <span className="text-xs">{build.components.gpu}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-[var(--muted)]">RAM:</span>
                            <span className="text-xs">{build.components.ram}</span>
                          </div>
                        </div>

                        {/* Price */}
                        <div className="flex justify-between items-center pt-4 border-t border-[var(--card-border)]">
                          <div>
                            {bespoke ? (
                              <span className="text-sm text-[var(--muted)]">Contact for pricing</span>
                            ) : incomplete ? (
                              <span className="text-sm text-[var(--muted)]">Price TBC</span>
                            ) : (
                              <span className="text-2xl font-bold">{formatPrice(build.price_gbp)}</span>
                            )}
                          </div>
                          {!bespoke && !incomplete && (
                            <span className="text-[var(--accent)] text-sm font-medium">
                              Configure →
                            </span>
                          )}
                          {bespoke && (
                            <span className="text-[var(--muted)] text-sm">
                              Enquire →
                            </span>
                          )}
                        </div>
                      </Link>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* Prometheus Pre-built Section */}
      <section className="pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="p-8 rounded-lg border-2 border-[var(--accent)] bg-[var(--card-bg)]">
            <div className="flex items-start gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="text-2xl font-bold">Prometheus ChromaFlair</h2>
                  <span className="text-xs px-2 py-1 rounded bg-[var(--accent)]/20 text-[var(--accent)] border border-[var(--accent)]/50">
                    Pre-built • Ready to Ship
                  </span>
                </div>
                <p className="text-[var(--muted)] mb-4">
                  Our signature showcase build featuring the stunning APNX Creator C1 ChromaFlair case. 
                  Pre-built, tested, and ready for immediate dispatch.
                </p>
                <div className="grid grid-cols-2 gap-3 text-sm mb-4">
                  <div><span className="text-[var(--muted)]">CPU:</span> AMD Ryzen 7 7800X3D</div>
                  <div><span className="text-[var(--muted)]">GPU:</span> AMD Radeon RX 9070 XT 16GB</div>
                  <div><span className="text-[var(--muted)]">RAM:</span> 32GB DDR5-6400</div>
                  <div><span className="text-[var(--muted)]">Storage:</span> 1TB PCIe 3.0 NVMe</div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-3xl font-bold">£1,449</span>
                  <span className="text-sm text-[var(--muted)]">Production cost: £944.74</span>
                </div>
              </div>
              <div>
                <Link
                  href="/prometheus"
                  className="inline-block px-6 py-3 bg-[var(--accent)] hover:bg-[var(--accent-hover)] rounded-lg font-medium transition-colors"
                >
                  View Details →
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
