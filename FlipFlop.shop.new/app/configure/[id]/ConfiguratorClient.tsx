'use client'

import { useState, useEffect } from 'react'
import { CuratedBuild, CaseItem } from '@/lib/types'
import { formatPrice, getMemoryGeneration } from '@/lib/utils'
import { trackEvent } from '@/lib/analytics'
import Link from 'next/link'

interface Props {
  build: CuratedBuild
  cases: CaseItem[]
}

export function ConfiguratorClient({ build, cases }: Props) {
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null)
  const [ramCapacityGB, setRamCapacityGB] = useState<number>(32)
  const [storageCapacityGB, setStorageCapacityGB] = useState<number>(1000)
  const [rgbEnabled, setRgbEnabled] = useState(false)
  const [showARView, setShowARView] = useState(false)
  
  useEffect(() => {
    // Track playbook entry
    trackEvent('playbook_entered', build.id, {
      segment: build.segment,
      tier: build.tier,
    })
    
    // Auto-select preferred case if available
    const preferredCase = cases.find(c => c.is_preferred)
    if (preferredCase) {
      setSelectedCaseId(preferredCase.id)
    }
  }, [build.id, build.segment, build.tier, cases])

  const handleCaseSelection = (caseId: number) => {
    setSelectedCaseId(caseId)
    trackEvent('case_chosen', build.id, { case_id: caseId })
  }

  const handleRGBToggle = (enabled: boolean) => {
    setRgbEnabled(enabled)
    trackEvent('rgb_tweaked', build.id, { enabled })
  }

  const handleAROpen = () => {
    setShowARView(true)
    trackEvent('ar_opened', build.id)
  }

  const selectedCase = cases.find(c => c.id === selectedCaseId)
  const memoryGen = getMemoryGeneration(build.components.ram)

  return (
    <div className="min-h-screen bg-[var(--background)] py-12 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link href="/" className="text-[var(--accent)] hover:underline mb-4 inline-block">
            ← Back to Browse
          </Link>
          <h1 className="text-4xl font-bold mb-2">{build.name}</h1>
          <p className="text-[var(--muted)]">{build.description}</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Panel - 3D Viewer & Configuration */}
          <div className="lg:col-span-2 space-y-6">
            {/* 3D Viewer Placeholder */}
            <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-8 aspect-video flex items-center justify-center relative">
              <div className="text-center space-y-4">
                <div className="text-6xl">🖥️</div>
                <div>
                  <h3 className="text-xl font-bold mb-2">3D Viewer Coming Soon</h3>
                  <p className="text-[var(--muted)] text-sm">
                    Interactive 3D model with MeshyBot-generated GLB files
                  </p>
                </div>
                <div className="flex gap-3 justify-center">
                  <button
                    onClick={handleAROpen}
                    className="px-4 py-2 bg-[var(--card-bg)] border border-[var(--card-border)] rounded hover:border-[var(--accent)] transition-colors text-sm"
                  >
                    📱 AR View (Coming Soon)
                  </button>
                  <button
                    onClick={() => handleRGBToggle(!rgbEnabled)}
                    className={`px-4 py-2 rounded text-sm transition-colors ${
                      rgbEnabled
                        ? 'bg-[var(--accent)] text-white'
                        : 'bg-[var(--card-bg)] border border-[var(--card-border)] hover:border-[var(--accent)]'
                    }`}
                  >
                    {rgbEnabled ? '✨ RGB Enabled' : '💡 Enable RGB'}
                  </button>
                </div>
              </div>
              
              {/* Extension Points Annotation */}
              <div className="absolute bottom-4 right-4 text-xs text-[var(--muted)] bg-[var(--background)]/80 px-3 py-2 rounded">
                <div className="font-mono space-y-1">
                  <div>→ Extension: Load .glb from /api/3d-assets/{'{case_id}'}</div>
                  <div>→ Extension: ARGB binding via WebGL uniforms</div>
                  <div>→ Extension: AR via WebXR API</div>
                </div>
              </div>
            </div>

            {/* Component Specifications */}
            <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6">
              <h2 className="text-2xl font-bold mb-4">Core Components</h2>
              <div className="space-y-3">
                {Object.entries(build.components).map(([key, value]) => (
                  <div key={key} className="flex justify-between items-start py-2 border-b border-[var(--card-border)] last:border-0">
                    <span className="text-[var(--muted)] capitalize">{key}:</span>
                    <span className="text-right max-w-md text-sm">{value}</span>
                  </div>
                ))}
                <div className="flex justify-between items-start py-2 border-b border-[var(--card-border)]">
                  <span className="text-[var(--muted)]">Memory Gen:</span>
                  <span className="font-mono text-sm">{memoryGen}</span>
                </div>
              </div>
            </div>

            {/* Case Selection */}
            <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6">
              <h2 className="text-2xl font-bold mb-4">Select Case</h2>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {cases.slice(0, 12).map((caseItem) => (
                  <button
                    key={caseItem.id}
                    onClick={() => handleCaseSelection(caseItem.id)}
                    className={`p-4 rounded-lg border transition-all ${
                      selectedCaseId === caseItem.id
                        ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                        : 'border-[var(--card-border)] hover:border-[var(--accent)]'
                    }`}
                  >
                    <div className="aspect-square bg-[var(--background)] rounded mb-2 flex items-center justify-center">
                      {caseItem.images[0] ? (
                        <img src={caseItem.images[0]} alt={caseItem.name} className="w-full h-full object-cover rounded" />
                      ) : (
                        <span className="text-3xl">📦</span>
                      )}
                    </div>
                    <div className="text-xs font-medium truncate">{caseItem.brand}</div>
                    <div className="text-[var(--muted)] text-xs truncate">{caseItem.name.slice(0, 30)}...</div>
                    {caseItem.is_preferred && (
                      <div className="mt-1 text-xs text-[var(--accent)]">⭐ Recommended</div>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Capacity Customizations */}
            <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6">
              <h2 className="text-2xl font-bold mb-4">Customize Capacity</h2>
              
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium mb-2">RAM Capacity</label>
                  <div className="flex gap-2">
                    {[16, 32, 64, 128].map(gb => (
                      <button
                        key={gb}
                        onClick={() => setRamCapacityGB(gb)}
                        className={`px-4 py-2 rounded transition-colors ${
                          ramCapacityGB === gb
                            ? 'bg-[var(--accent)] text-white'
                            : 'bg-[var(--background)] border border-[var(--card-border)] hover:border-[var(--accent)]'
                        }`}
                      >
                        {gb} GB
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-[var(--muted)] mt-2">Memory generation: {memoryGen}</p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Storage Capacity</label>
                  <div className="flex gap-2">
                    {[500, 1000, 2000, 4000].map(gb => (
                      <button
                        key={gb}
                        onClick={() => setStorageCapacityGB(gb)}
                        className={`px-4 py-2 rounded transition-colors ${
                          storageCapacityGB === gb
                            ? 'bg-[var(--accent)] text-white'
                            : 'bg-[var(--background)] border border-[var(--card-border)] hover:border-[var(--accent)]'
                        }`}
                      >
                        {gb >= 1000 ? `${gb / 1000}TB` : `${gb}GB`}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel - Build Summary */}
          <div className="lg:col-span-1">
            <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6 sticky top-4">
              <h2 className="text-2xl font-bold mb-4">Build Summary</h2>
              
              <div className="space-y-3 mb-6">
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--muted)]">Base Configuration</span>
                  <span>{formatPrice(build.price_gbp)}</span>
                </div>
                {selectedCase && (
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--muted)]">Case</span>
                    <span>{formatPrice(selectedCase.rrp_gbp)}</span>
                  </div>
                )}
                {rgbEnabled && (
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--muted)]">RGB Lighting</span>
                    <span>+£45</span>
                  </div>
                )}
              </div>

              <div className="border-t border-[var(--card-border)] pt-4 mb-6">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-lg font-bold">Total</span>
                  <span className="text-2xl font-bold">
                    {formatPrice(
                      (build.price_gbp || 0) +
                      (selectedCase?.rrp_gbp || 0) +
                      (rgbEnabled ? 45 : 0)
                    )}
                  </span>
                </div>
                <p className="text-xs text-[var(--muted)]">
                  Includes assembly, testing, and warranty
                </p>
              </div>

              <button
                disabled={!selectedCaseId}
                className="w-full py-3 bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:bg-[var(--muted)] disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
              >
                {selectedCaseId ? 'Proceed to Checkout' : 'Select a case to continue'}
              </button>

              <div className="mt-4 p-4 bg-[var(--background)] rounded-lg">
                <h3 className="font-medium mb-2 text-sm">What's Included</h3>
                <ul className="text-xs text-[var(--muted)] space-y-1">
                  <li>✓ Professional assembly & testing</li>
                  <li>✓ 12-month warranty</li>
                  <li>✓ Insured delivery (3-5 days)</li>
                  <li>✓ Cable management</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* AR Modal Placeholder */}
      {showARView && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-8 max-w-md w-full">
            <h3 className="text-2xl font-bold mb-4">AR View Coming Soon</h3>
            <p className="text-[var(--muted)] mb-6">
              Augmented Reality view will allow you to visualize this build in your space using your phone's camera.
            </p>
            <p className="text-sm text-[var(--muted)] mb-6 font-mono">
              Extension point: Implement with WebXR API + 8th Wall or Model Viewer
            </p>
            <button
              onClick={() => setShowARView(false)}
              className="w-full py-2 bg-[var(--accent)] rounded hover:bg-[var(--accent-hover)]"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
