'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { getCuratedBuilds } from '@/lib/api'
import { CuratedBuild } from '@/lib/types'
import { formatPrice, isBespokeOnly, getBuildTierColor, getMemoryGeneration } from '@/lib/utils'
import { trackEvent } from '@/lib/analytics'
import Link from 'next/link'

function BuildConfigureContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  
  const budget = parseFloat(searchParams.get('budget') || '0')
  const typeId = searchParams.get('type') || ''
  const tierId = searchParams.get('tier') || ''
  
  const [builds, setBuilds] = useState<CuratedBuild[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const CUSTOMER_TYPE_MAP: Record<string, string> = {
    'gaming-value': 'Great-value Gaming',
    'gaming-performance': 'High-performance Gaming',
    'student': 'Student Hybrid',
    'business': 'Business & Office',
    'content': 'Content Creation',
    'ai': 'AI Workstation',
    'dev': 'Software Development',
    'family': 'Family & Home',
  }

  const TIER_MAP: Record<string, string> = {
    'budget': 'Budget',
    'mid': 'Mid-range',
    'high': 'High-end',
  }

  useEffect(() => {
    async function loadBuilds() {
      try {
        const response = await getCuratedBuilds()
        setBuilds(response.builds)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load builds')
      } finally {
        setLoading(false)
      }
    }
    loadBuilds()
  }, [])

  if (!budget || !typeId || !tierId) {
    return (
      <div className="min-h-screen bg-[var(--background)] py-12 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-3xl font-bold mb-4">Invalid Configuration</h1>
          <p className="text-[var(--muted)] mb-6">
            Please start from the beginning to configure your build.
          </p>
          <Link href="/build" className="text-[var(--accent)] hover:underline">
            ← Start Over
          </Link>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--background)] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-[var(--accent)] mx-auto mb-4"></div>
          <p className="text-[var(--muted)]">Loading your options...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[var(--background)] py-12 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-3xl font-bold mb-4 text-red-500">Error</h1>
          <p className="text-[var(--muted)] mb-6">{error}</p>
          <Link href="/build" className="text-[var(--accent)] hover:underline">
            ← Start Over
          </Link>
        </div>
      </div>
    )
  }

  const customerType = CUSTOMER_TYPE_MAP[typeId]
  const tierName = TIER_MAP[tierId]

  // Filter builds matching customer type and tier
  const matchingBuilds = builds.filter((build) => {
    const segmentMatch = build.segment === customerType
    const tierMatch = build.tier.toLowerCase() === tierName.toLowerCase()
    const withinBudget = build.price_gbp ? build.price_gbp <= budget : false
    return segmentMatch && tierMatch && withinBudget
  })

  // Handle bespoke AI Workstation High
  const isBespoke = typeId === 'ai' && tierId === 'high'
  const bespokeBuilds = builds.filter(b => isBespokeOnly(b.id))

  // Find the recommended build (highest price within budget)
  const recommended = matchingBuilds.sort((a, b) => (b.price_gbp || 0) - (a.price_gbp || 0))[0]

  // Track analytics event for the recommended build
  useEffect(() => {
    if (recommended) {
      trackEvent('playbook_tier_shown', recommended.id, {
        segment: recommended.segment,
        tier: recommended.tier,
        budget,
        customer_type: typeId,
      })
    }
  }, [recommended, budget, typeId])

  const BuildCard = ({ build, badge }: { build: CuratedBuild; badge?: string }) => {
    const memGen = getMemoryGeneration(build.id)
    const tierColor = getBuildTierColor(build.tier)

    return (
      <div className={`bg-[var(--card-bg)] border rounded-lg p-6 hover:border-[var(--accent)] transition-all ${
        badge === 'Recommended' ? 'border-[var(--accent)] ring-2 ring-[var(--accent)]/20' : 'border-[var(--card-border)]'
      }`}>
        {badge && (
          <div className={`inline-block px-3 py-1 rounded-full text-xs font-bold mb-3 ${
            badge === 'Recommended' 
              ? 'bg-[var(--accent)] text-white'
              : badge === 'Bespoke'
              ? 'bg-amber-500 text-black'
              : 'bg-[var(--muted)]/20 text-[var(--muted)]'
          }`}>
            {badge}
          </div>
        )}
        
        <h3 className="text-xl font-bold mb-2">{build.name}</h3>
        <p className="text-[var(--muted)] text-sm mb-4 line-clamp-2">{build.description}</p>
        
        <div className="space-y-2 mb-4">
          <div className="flex justify-between text-sm">
            <span className="text-[var(--muted)]">Tier</span>
            <span className={`font-bold ${tierColor}`}>{build.tier}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-[var(--muted)]">Memory</span>
            <span className="font-mono">{memGen}</span>
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-[var(--card-border)]">
          <div>
            <div className="text-2xl font-bold">{formatPrice(build.price_gbp)}</div>
            <div className="text-xs text-[var(--muted)]">All-in price</div>
          </div>
          {isBespokeOnly(build.id) ? (
            <Link
              href="/contact"
              className="px-6 py-3 bg-amber-500 hover:bg-amber-600 text-black rounded-lg font-bold transition-colors"
            >
              Consult
            </Link>
          ) : (
            <Link
              href={`/configure/${build.id}`}
              className="px-6 py-3 bg-[var(--accent)] hover:bg-[var(--accent-hover)] rounded-lg font-bold transition-colors"
            >
              Configure
            </Link>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[var(--background)] py-12 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link href="/build" className="text-[var(--accent)] hover:underline mb-4 inline-block">
            ← Change Selection
          </Link>
          
          <h1 className="text-3xl font-bold mb-2">Your Curated Options</h1>
          <p className="text-[var(--muted)]">
            {customerType} · {tierName} · Budget: {formatPrice(budget)}
          </p>
        </div>

        {/* Bespoke Notice */}
        {isBespoke && (
          <div className="mb-8 p-6 bg-amber-900/10 border border-amber-700/50 rounded-lg">
            <h2 className="text-xl font-bold mb-2 text-amber-400">
              🤖 AI Workstation High-end: Bespoke Configuration
            </h2>
            <p className="text-sm text-amber-300 mb-4">
              High-end AI Workstation builds (FF-AIW-03) are bespoke configurations tailored to your specific 
              AI/ML workload requirements. These typically feature AMD Threadripper PRO processors and NVIDIA 
              RTX 6000 Ada Generation GPUs.
            </p>
            {bespokeBuilds.length > 0 && (
              <div className="grid grid-cols-1 gap-4">
                {bespokeBuilds.map(build => (
                  <BuildCard key={build.id} build={build} badge="Bespoke" />
                ))}
              </div>
            )}
            <div className="mt-4">
              <Link
                href="/contact"
                className="inline-block px-6 py-3 bg-amber-500 hover:bg-amber-600 text-black rounded-lg font-bold transition-colors"
              >
                Schedule Consultation
              </Link>
            </div>
          </div>
        )}

        {/* Recommended Build */}
        {!isBespoke && recommended && (
          <div className="mb-8">
            <h2 className="text-2xl font-bold mb-4">✨ Recommended for You</h2>
            <BuildCard build={recommended} badge="Recommended" />
          </div>
        )}

        {/* Other Matching Builds */}
        {!isBespoke && matchingBuilds.length > 1 && (
          <div className="mb-8">
            <h2 className="text-2xl font-bold mb-4">Alternative Options</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {matchingBuilds
                .filter(b => b.id !== recommended?.id)
                .map(build => (
                  <BuildCard key={build.id} build={build} />
                ))}
            </div>
          </div>
        )}

        {/* No matches */}
        {!isBespoke && matchingBuilds.length === 0 && (
          <div className="text-center py-12">
            <h2 className="text-2xl font-bold mb-4">No Exact Matches</h2>
            <p className="text-[var(--muted)] mb-6">
              We don't have a {tierName} {customerType} build within your {formatPrice(budget)} budget.
              Try adjusting your budget or tier selection.
            </p>
            <Link
              href="/build"
              className="inline-block px-6 py-3 bg-[var(--accent)] hover:bg-[var(--accent-hover)] rounded-lg font-bold transition-colors"
            >
              ← Adjust Selection
            </Link>
          </div>
        )}

        {/* Consider other tiers */}
        {!isBespoke && matchingBuilds.length > 0 && (
          <div className="mt-12 p-6 bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg">
            <h3 className="text-lg font-bold mb-2">Want to explore other options?</h3>
            <p className="text-sm text-[var(--muted)] mb-4">
              You can go back to adjust your budget or tier to see different configurations.
            </p>
            <Link
              href="/build"
              className="inline-block px-4 py-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] rounded-lg font-bold transition-colors"
            >
              ← Adjust Selection
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}

export default function BuildConfigurePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[var(--background)] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-[var(--accent)] mx-auto mb-4"></div>
          <p className="text-[var(--muted)]">Loading...</p>
        </div>
      </div>
    }>
      <BuildConfigureContent />
    </Suspense>
  )
}
