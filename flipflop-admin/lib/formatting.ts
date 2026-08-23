/**
 * Formatting utilities for the admin dashboard.
 */

/**
 * Format a number as currency (GBP).
 * Uses the Money value type pattern for precision.
 */
export function formatCurrency(amount: number | null | undefined, currency = 'GBP'): string {
  if (amount === null || amount === undefined) {
    return '-'
  }

  const formatter = new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  return formatter.format(amount)
}

/**
 * Format a percentage value.
 */
export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined) {
    return '-'
  }

  return `${value.toFixed(decimals)}%`
}

/**
 * Format a large number with K/M/B abbreviations.
 */
export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '-'
  }

  const abs = Math.abs(value)
  if (abs >= 1e9) {
    return (value / 1e9).toFixed(1) + 'B'
  }
  if (abs >= 1e6) {
    return (value / 1e6).toFixed(1) + 'M'
  }
  if (abs >= 1e3) {
    return (value / 1e3).toFixed(1) + 'K'
  }
  return value.toString()
}

/**
 * Format a date in a human-readable way.
 */
export function formatDate(date: Date | string | null | undefined): string {
  if (!date) return '-'

  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return '-'

  return d.toLocaleDateString('en-GB', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Format a duration in seconds to human-readable format.
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '-'

  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)

  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  if (minutes > 0) {
    return `${minutes}m ${secs}s`
  }
  return `${secs}s`
}

/**
 * Truncate text to a maximum length with ellipsis.
 */
export function truncate(text: string | null | undefined, maxLength: number): string {
  if (!text) return '-'
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength - 3) + '...'
}

/**
 * Calculate percentage change between two values.
 */
export function percentChange(current: number, previous: number): number {
  if (previous === 0) return 0
  return ((current - previous) / previous) * 100
}

/**
 * Format a profit margin as a percentage.
 */
export function formatProfitMargin(profit: number | null | undefined, revenue: number | null | undefined): string {
  if (profit === null || profit === undefined || revenue === null || revenue === undefined) {
    return '-'
  }

  if (revenue === 0) return '-'

  const margin = (profit / revenue) * 100
  return formatPercent(margin, 1)
}
