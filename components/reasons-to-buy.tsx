/**
 * Reasons to Buy Banner
 * Inspired by Overclockers UK design
 * Displays key value propositions in a banner format
 */

import React from 'react'

interface Reason {
  icon: React.ReactNode
  title: string
  description: string
  highlight?: string
}

interface ReasonsToByProps {
  reasons?: Reason[]
  variant?: 'light' | 'dark'
}

export function ReasonsToBuy({ variant = 'light' }: ReasonsToByProps) {
  const defaultReasons: Reason[] = [
    {
      icon: '📦',
      title: 'CURATED SELECTION',
      description: 'Hand-picked PC cases from trusted retailers',
      highlight: 'Best quality, best prices',
    },
    {
      icon: '⚡',
      title: 'INSTANT BUILDS',
      description: 'Pre-configured systems ready to order',
      highlight: 'Amazon Prime next-day delivery',
    },
    {
      icon: '⭐',
      title: 'VERIFIED RATINGS',
      description: '4,000+ customer reviews on cases',
      highlight: 'Real demand data',
    },
    {
      icon: '💡',
      title: 'EXPERT GUIDANCE',
      description: 'AI-powered build recommendations',
      highlight: 'Optimized for your needs',
    },
    {
      icon: '💰',
      title: 'BEST VALUE',
      description: 'Real-time price tracking & discounts',
      highlight: 'See savings vs RRP',
    },
    {
      icon: '🎮',
      title: 'CUSTOMIZABLE',
      description: 'Build exactly what you want',
      highlight: 'Mix & match components',
    },
  ]

  return (
    <div className={`w-full py-8 px-4 ${variant === 'dark' ? 'bg-gray-900 text-white' : 'bg-gray-50 text-gray-900'}`}>
      <div className="max-w-7xl mx-auto">
        <h2 className="text-3xl font-bold mb-8 text-center">Why Choose FlipFlop?</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {defaultReasons.map((reason, idx) => (
            <div
              key={idx}
              className={`p-6 rounded-lg border ${
                variant === 'dark'
                  ? 'border-gray-700 bg-gray-800 hover:bg-gray-750'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              } transition-all hover:shadow-lg`}
            >
              <div className="text-4xl mb-3">{reason.icon}</div>
              <h3 className="font-bold text-lg mb-2">{reason.title}</h3>
              <p className="text-sm opacity-80 mb-2">{reason.description}</p>
              {reason.highlight && (
                <p className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide">
                  {reason.highlight}
                </p>
              )}
            </div>
          ))}
        </div>

        {/* Trust indicators */}
        <div className={`mt-8 pt-8 border-t ${variant === 'dark' ? 'border-gray-700' : 'border-gray-200'}`}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
            <div>
              <div className="text-3xl font-bold text-blue-600">489</div>
              <p className="text-sm opacity-75">PC Cases in catalogue</p>
            </div>
            <div>
              <div className="text-3xl font-bold text-blue-600">4K+</div>
              <p className="text-sm opacity-75">Customer reviews analyzed</p>
            </div>
            <div>
              <div className="text-3xl font-bold text-blue-600">99%</div>
              <p className="text-sm opacity-75">Positive ratings average</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ReasonsToBuy
