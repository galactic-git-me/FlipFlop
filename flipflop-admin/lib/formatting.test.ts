import { describe, it, expect } from 'vitest'
import {
  formatCurrency,
  formatPercent,
  formatCompact,
  formatDate,
  formatDuration,
  truncate,
  percentChange,
  formatProfitMargin,
} from './formatting'

describe('Formatting Utilities', () => {
  describe('formatCurrency', () => {
    it('formats positive amounts as GBP', () => {
      expect(formatCurrency(79.99)).toBe('£79.99')
      expect(formatCurrency(100)).toBe('£100.00')
    })

    it('formats negative amounts as GBP', () => {
      expect(formatCurrency(-50.5)).toBe('-£50.50')
    })

    it('handles null and undefined', () => {
      expect(formatCurrency(null)).toBe('-')
      expect(formatCurrency(undefined)).toBe('-')
    })

    it('supports USD formatting', () => {
      expect(formatCurrency(100, 'USD')).toBe('$100.00')
    })

    it('supports EUR formatting', () => {
      expect(formatCurrency(100, 'EUR')).toBe('€100.00')
    })

    it('rounds to 2 decimal places', () => {
      expect(formatCurrency(79.996)).toBe('£80.00')
      expect(formatCurrency(79.994)).toBe('£79.99')
    })
  })

  describe('formatPercent', () => {
    it('formats percentages with default decimals', () => {
      expect(formatPercent(25)).toBe('25.0%')
      expect(formatPercent(33.333)).toBe('33.3%')
    })

    it('supports custom decimal places', () => {
      expect(formatPercent(33.333, 2)).toBe('33.33%')
      expect(formatPercent(33.333, 0)).toBe('33%')
    })

    it('handles null and undefined', () => {
      expect(formatPercent(null)).toBe('-')
      expect(formatPercent(undefined)).toBe('-')
    })

    it('handles negative percentages', () => {
      expect(formatPercent(-25)).toBe('-25.0%')
    })
  })

  describe('formatCompact', () => {
    it('formats billions', () => {
      expect(formatCompact(1_000_000_000)).toBe('1.0B')
      expect(formatCompact(1_500_000_000)).toBe('1.5B')
    })

    it('formats millions', () => {
      expect(formatCompact(1_000_000)).toBe('1.0M')
      expect(formatCompact(999_999)).toBe('1000.0K')
    })

    it('formats thousands', () => {
      expect(formatCompact(1_000)).toBe('1.0K')
      expect(formatCompact(999)).toBe('999')
    })

    it('formats small numbers without abbreviation', () => {
      expect(formatCompact(100)).toBe('100')
      expect(formatCompact(1)).toBe('1')
    })

    it('handles negative numbers', () => {
      expect(formatCompact(-1_000_000)).toBe('-1.0M')
    })

    it('handles null and undefined', () => {
      expect(formatCompact(null)).toBe('-')
      expect(formatCompact(undefined)).toBe('-')
    })
  })

  describe('formatDate', () => {
    it('formats Date objects', () => {
      const date = new Date('2026-08-23')
      const result = formatDate(date)
      expect(result).toContain('23')
      expect(result).toContain('Aug')
      expect(result).toContain('2026')
    })

    it('formats ISO date strings', () => {
      const result = formatDate('2026-08-23')
      expect(result).toContain('23')
      expect(result).toContain('Aug')
    })

    it('handles null and undefined', () => {
      expect(formatDate(null)).toBe('-')
      expect(formatDate(undefined)).toBe('-')
    })

    it('handles invalid dates', () => {
      expect(formatDate('invalid')).toBe('-')
    })

    it('handles empty strings', () => {
      expect(formatDate('')).toBe('-')
    })
  })

  describe('formatDuration', () => {
    it('formats hours and minutes', () => {
      expect(formatDuration(7200)).toBe('2h 0m')
      expect(formatDuration(3661)).toBe('1h 1m')
    })

    it('formats minutes and seconds', () => {
      expect(formatDuration(125)).toBe('2m 5s')
      expect(formatDuration(60)).toBe('1m 0s')
    })

    it('formats seconds only', () => {
      expect(formatDuration(45)).toBe('45s')
      expect(formatDuration(1)).toBe('1s')
    })

    it('handles null and undefined', () => {
      expect(formatDuration(null)).toBe('-')
      expect(formatDuration(undefined)).toBe('-')
    })

    it('handles zero', () => {
      expect(formatDuration(0)).toBe('0s')
    })
  })

  describe('truncate', () => {
    it('truncates long text with ellipsis', () => {
      expect(truncate('Hello World', 8)).toBe('Hello...')
      expect(truncate('This is a long string', 10)).toBe('This is...')
    })

    it('returns text unchanged if shorter than max length', () => {
      expect(truncate('Short', 10)).toBe('Short')
      expect(truncate('Exact', 5)).toBe('Exact')
    })

    it('handles null and undefined', () => {
      expect(truncate(null, 10)).toBe('-')
      expect(truncate(undefined, 10)).toBe('-')
    })

    it('handles empty strings', () => {
      expect(truncate('', 10)).toBe('-')
    })
  })

  describe('percentChange', () => {
    it('calculates percent increase', () => {
      expect(percentChange(120, 100)).toBe(20)
      expect(percentChange(150, 100)).toBe(50)
    })

    it('calculates percent decrease', () => {
      expect(percentChange(80, 100)).toBe(-20)
      expect(percentChange(50, 100)).toBe(-50)
    })

    it('handles zero previous value', () => {
      expect(percentChange(100, 0)).toBe(0)
    })

    it('handles same values', () => {
      expect(percentChange(100, 100)).toBe(0)
    })

    it('handles negative values', () => {
      expect(percentChange(-100, -50)).toBe(-100)
    })
  })

  describe('formatProfitMargin', () => {
    it('calculates profit margin percentage', () => {
      expect(formatProfitMargin(25, 100)).toBe('25.0%')
      expect(formatProfitMargin(33.33, 100)).toBe('33.3%')
    })

    it('handles high profit margins', () => {
      expect(formatProfitMargin(50, 100)).toBe('50.0%')
    })

    it('handles low profit margins', () => {
      expect(formatProfitMargin(5, 100)).toBe('5.0%')
    })

    it('handles zero profit (break-even)', () => {
      expect(formatProfitMargin(0, 100)).toBe('0.0%')
    })

    it('handles negative profit (loss)', () => {
      expect(formatProfitMargin(-25, 100)).toBe('-25.0%')
    })

    it('handles null and undefined', () => {
      expect(formatProfitMargin(null, 100)).toBe('-')
      expect(formatProfitMargin(25, null)).toBe('-')
      expect(formatProfitMargin(undefined, undefined)).toBe('-')
    })

    it('handles zero revenue', () => {
      expect(formatProfitMargin(25, 0)).toBe('-')
    })
  })
})
