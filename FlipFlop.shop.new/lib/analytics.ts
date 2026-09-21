import { AnalyticsEvent } from './types'

export function trackEvent(
  event_type: AnalyticsEvent['event_type'],
  curated_build_id: string,
  metadata?: Record<string, any>
) {
  const event: AnalyticsEvent = {
    event_type,
    curated_build_id,
    metadata,
    timestamp: new Date().toISOString(),
  }

  // TODO: Wire to AnalyticsBot when available
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
