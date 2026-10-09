export function formatPrice(amount: number | undefined): string {
  if (amount === undefined || amount === null) return 'Price TBC'
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: 'GBP',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function getMemoryGeneration(ramSpec: string): string {
  if (ramSpec.includes('DDR5')) return 'DDR5'
  if (ramSpec.includes('DDR4')) return 'DDR4'
  if (ramSpec.includes('LPDDR5X')) return 'LPDDR5X'
  return 'DDR4'
}

export function isBespokeOnly(buildId: string): boolean {
  return buildId === 'FF-AIW-03'
}

export function getBuildTierColor(tier: string): string {
  switch (tier) {
    case 'Budget':
      return 'text-green-400'
    case 'Mid-range':
      return 'text-blue-400'
    case 'High-end':
      return 'text-purple-400'
    default:
      return 'text-gray-400'
  }
}

export function getSegmentIcon(segment: string): string {
  const icons: Record<string, string> = {
    'Great-value Gaming': '🎮',
    'High-performance Gaming': '👑',
    'Student Hybrid': '🎓',
    'Business & Office': '🏢',
    'Content Creation': '🎬',
    'AI Workstation': '🤖',
    'Software Development': '💻',
    'Family & Home': '🏠',
  }
  return icons[segment] || '🖥️'
}
