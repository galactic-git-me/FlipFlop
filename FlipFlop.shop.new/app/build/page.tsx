'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { trackEvent } from '@/lib/analytics'

const BUDGET_RANGES = [
  { label: '£300 - £500', min: 300, max: 500, value: 400 },
  { label: '£500 - £800', min: 500, max: 800, value: 650 },
  { label: '£800 - £1,200', min: 800, max: 1200, value: 1000 },
  { label: '£1,200 - £1,800', min: 1200, max: 1800, value: 1500 },
  { label: '£1,800 - £2,500', min: 1800, max: 2500, value: 2150 },
  { label: '£2,500+', min: 2500, max: 10000, value: 3000 },
]

// Exact labels from BuildBot + PricingBot
const CUSTOMER_TYPES = [
  { 
    id: 'gaming-value', 
    name: 'Great-value Gaming', 
    icon: '🎮', 
    description: '1080p gaming, esports, first gaming PC',
    segment: 'Great-value Gaming'
  },
  { 
    id: 'gaming-performance', 
    name: 'High-performance Gaming', 
    icon: '👑', 
    description: '1440p/4K gaming, VR, premium builds',
    segment: 'High-performance Gaming'
  },
  { 
    id: 'student', 
    name: 'Student Hybrid', 
    icon: '🎓', 
    description: 'Study, coding, and light gaming',
    segment: 'Student Hybrid'
  },
  { 
    id: 'business', 
    name: 'Business & Office', 
    icon: '🏢', 
    description: 'Office work, productivity, reliability',
    segment: 'Business & Office'
  },
  { 
    id: 'content', 
    name: 'Content Creation', 
    icon: '🎬', 
    description: 'Video editing, streaming, design',
    segment: 'Content Creation'
  },
  { 
    id: 'ai', 
    name: 'AI Workstation', 
    icon: '🤖', 
    description: 'Local LLMs, AI development, ML training',
    segment: 'AI Workstation'
  },
  { 
    id: 'dev', 
    name: 'Software Development', 
    icon: '💻', 
    description: 'Coding, Docker, VMs, compilation',
    segment: 'Software Development'
  },
  { 
    id: 'family', 
    name: 'Family & Home', 
    icon: '🏠', 
    description: 'Homework, browsing, family media',
    segment: 'Family & Home'
  },
]

const TIERS = [
  { id: 'budget', label: 'Budget', icon: '💰', description: 'Great value for essential performance' },
  { id: 'mid', label: 'Mid-range', icon: '⚡', description: 'Balanced power and price' },
  { id: 'high', label: 'High-end', icon: '🚀', description: 'Maximum performance' },
]

export default function BuildWizard() {
  const router = useRouter()
  const [step, setStep] = useState<'budget' | 'type' | 'tier'>('budget')
  const [selectedBudget, setSelectedBudget] = useState<typeof BUDGET_RANGES[0] | null>(null)
  const [selectedType, setSelectedType] = useState<typeof CUSTOMER_TYPES[0] | null>(null)
  const [selectedTier, setSelectedTier] = useState<typeof TIERS[0] | null>(null)

  useEffect(() => {
    if (selectedBudget) {
      trackEvent('drop_off', 'wizard', { step: 'budget', budget: selectedBudget.value })
    }
  }, [selectedBudget])

  const handleBudgetSelect = (budget: typeof BUDGET_RANGES[0]) => {
    setSelectedBudget(budget)
    trackEvent('playbook_entered', 'wizard', { 
      event_type: 'budget_chosen',
      budget_min: budget.min, 
      budget_max: budget.max 
    })
    setStep('type')
  }

  const handleTypeSelect = (type: typeof CUSTOMER_TYPES[0]) => {
    setSelectedType(type)
    trackEvent('playbook_entered', type.segment, {
      event_type: 'customer_type_picked',
      customer_type: type.id,
      budget: selectedBudget?.value
    })
    setStep('tier')
  }

  const handleTierSelect = (tier: typeof TIERS[0]) => {
    setSelectedTier(tier)
    
    // Navigate to configurator with budget, type, and tier
    const params = new URLSearchParams({
      budget: selectedBudget!.value.toString(),
      type: selectedType!.id,
      tier: tier.id,
    })
    router.push(`/build/configure?${params}`)
  }

  const handleBack = () => {
    if (step === 'tier') {
      setStep('type')
      setSelectedTier(null)
    } else if (step === 'type') {
      setStep('budget')
      setSelectedType(null)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--background)] py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        {/* Progress Indicator */}
        <div className="mb-12">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
              step === 'budget' 
                ? 'bg-[var(--accent)] text-white' 
                : 'bg-[var(--accent)]/30 text-[var(--foreground)]'
            }`}>
              1
            </div>
            <div className={`h-1 w-16 ${step !== 'budget' ? 'bg-[var(--accent)]' : 'bg-[var(--card-border)]'}`} />
            <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
              step === 'type' 
                ? 'bg-[var(--accent)] text-white' 
                : step === 'tier'
                ? 'bg-[var(--accent)]/30 text-[var(--foreground)]'
                : 'bg-[var(--card-bg)] border border-[var(--card-border)]'
            }`}>
              2
            </div>
            <div className={`h-1 w-16 ${step === 'tier' ? 'bg-[var(--accent)]' : 'bg-[var(--card-border)]'}`} />
            <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
              step === 'tier' 
                ? 'bg-[var(--accent)] text-white' 
                : 'bg-[var(--card-bg)] border border-[var(--card-border)]'
            }`}>
              3
            </div>
          </div>
          <div className="text-center">
            <p className="text-sm text-[var(--muted)]">
              {step === 'budget' ? 'Step 1 of 3' : step === 'type' ? 'Step 2 of 3' : 'Step 3 of 3'}
            </p>
            <h1 className="text-3xl font-bold mt-2">
              {step === 'budget' 
                ? 'What\'s your budget?' 
                : step === 'type'
                ? 'What will you use it for?'
                : 'Choose your tier'}
            </h1>
            <p className="text-[var(--muted)] mt-2">
              {step === 'budget' 
                ? 'Choose an all-in price range (includes case, assembly, warranty, delivery)'
                : step === 'type'
                ? 'Select the type that best matches how you\'ll use your PC'
                : 'Pick Budget, Mid-range, or High-end for your needs'
              }
            </p>
          </div>
        </div>

        {/* Budget Selection */}
        {step === 'budget' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {BUDGET_RANGES.map((budget) => (
              <button
                key={budget.label}
                onClick={() => handleBudgetSelect(budget)}
                className={`p-6 rounded-lg border transition-all text-left ${
                  selectedBudget?.label === budget.label
                    ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                    : 'border-[var(--card-border)] bg-[var(--card-bg)] hover:border-[var(--accent)]'
                }`}
              >
                <div className="text-2xl font-bold mb-2">{budget.label}</div>
                <div className="text-sm text-[var(--muted)]">
                  All-in price including components, case, assembly, testing, warranty, and delivery
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Customer Type Selection */}
        {step === 'type' && (
          <>
            <button
              onClick={handleBack}
              className="mb-6 text-[var(--accent)] hover:underline flex items-center gap-2"
            >
              ← Change Budget
            </button>
            
            <div className="mb-6 p-4 bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg">
              <p className="text-sm text-[var(--muted)]">
                Your budget: <span className="font-bold text-[var(--foreground)]">{selectedBudget?.label}</span>
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {CUSTOMER_TYPES.map((type) => (
                <button
                  key={type.id}
                  onClick={() => handleTypeSelect(type)}
                  className={`p-6 rounded-lg border transition-all text-left ${
                    selectedType?.id === type.id
                      ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                      : 'border-[var(--card-border)] bg-[var(--card-bg)] hover:border-[var(--accent)]'
                  }`}
                >
                  <div className="flex items-start gap-3 mb-3">
                    <span className="text-3xl">{type.icon}</span>
                    <div className="flex-1">
                      <h3 className="font-bold text-lg">{type.name}</h3>
                    </div>
                  </div>
                  <p className="text-sm text-[var(--muted)]">{type.description}</p>
                </button>
              ))}
            </div>
          </>
        )}

        {/* Tier Selection */}
        {step === 'tier' && (
          <>
            <button
              onClick={handleBack}
              className="mb-6 text-[var(--accent)] hover:underline flex items-center gap-2"
            >
              ← Change Type
            </button>
            
            <div className="mb-6 p-4 bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg">
              <p className="text-sm text-[var(--muted)]">
                Budget: <span className="font-bold text-[var(--foreground)]">{selectedBudget?.label}</span>
                {' · '}
                Type: <span className="font-bold text-[var(--foreground)]">{selectedType?.name}</span>
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {TIERS.map((tier) => (
                <button
                  key={tier.id}
                  onClick={() => handleTierSelect(tier)}
                  className={`p-6 rounded-lg border transition-all text-center ${
                    selectedTier?.id === tier.id
                      ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                      : 'border-[var(--card-border)] bg-[var(--card-bg)] hover:border-[var(--accent)]'
                  }`}
                  disabled={tier.id === 'high' && selectedType?.id === 'ai'}
                >
                  <div className="text-4xl mb-3">{tier.icon}</div>
                  <h3 className="font-bold text-lg mb-2">{tier.label}</h3>
                  <p className="text-sm text-[var(--muted)]">{tier.description}</p>
                  {tier.id === 'high' && selectedType?.id === 'ai' && (
                    <p className="text-xs text-amber-400 mt-2">
                      ⚠️ Bespoke / Consult Only
                    </p>
                  )}
                </button>
              ))}
            </div>

            {selectedType?.id === 'ai' && (
              <div className="mt-6 p-4 bg-amber-900/10 border border-amber-700/50 rounded-lg">
                <p className="text-sm text-amber-400">
                  ℹ️ <strong>AI Workstation High</strong> (FF-AIW-03) is a bespoke build requiring consultation.
                  For Budget and Mid-range AI workstations, continue with your selection.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
