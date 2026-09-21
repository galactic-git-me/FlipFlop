import { AnalyticsEvent } from './types'

/**
 * Track customer journey events for AnalyticsBot
 * 
 * Event order (as specified by Michael):
 * 1. budget_chosen - Customer selects budget range
 * 2. customer_type_picked - Customer picks one of the 8 types
 * 3. playbook_tier_shown - Matching playbook/tier displayed
 * 4. case_chosen - Customer selects case
 * 5. upsell_chosen - RAM/storage upgrades
 * 6. rgb_tweaked - ARGB settings changed
 * 7. ar_opened - AR view opened
 * 8. drop_off - Customer leaves without completing
 */
export function trackEvent(
  event_type: AnalyticsEvent['event_type'] | 'budget_chosen' | 'customer_type_picked' | 'playbook_tier_shown',
  curated_build_id: string,
  metadata?: Record<string, any>
) {
  const event: AnalyticsEvent = {
    event_type: event_type as AnalyticsEvent['event_type'],
    curated_build_id,
    metadata,
    timestamp: new Date().toISOString(),
  }

  // TODO: Wire to AnalyticsBot backend
  // POST /api/analytics/events
  // For now, log to console and store in sessionStorage for debugging
  console.log('[Analytics Event]', event)
  
  if (typeof window !== 'undefined') {
    const key = 'flipflop_analytics_events'
    const existing = JSON.parse(sessionStorage.getItem(key) || '[]')
    existing.push(event)
    sessionStorage.setItem(key, JSON.stringify(existing))
  }
}

export function getSessionEvents(): AnalyticsEvent[] {
  if (typeof window === 'undefined') return []
  const key = 'flipflop_analytics_events'
  return JSON.parse(sessionStorage.getItem(key) || '[]')
}
