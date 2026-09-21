import { AnalyticsEvent, BuyingFlowData } from './types'

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

/**
 * Get buying flow data from session storage
 */
export function getBuyingFlowData(): BuyingFlowData | null {
  if (typeof window !== 'undefined') {
    const data = sessionStorage.getItem('flipflop_buying_flow')
    return data ? JSON.parse(data) : null
  }
  return null
}

/**
 * Update buying flow data (progressive disclosure)
 */
export function updateBuyingFlowData(updates: Partial<BuyingFlowData>) {
  if (typeof window !== 'undefined') {
    const existing = getBuyingFlowData() || {
      is_gift: false,
      discreet_packaging: false,
      is_business_buyer: false,
      wants_vat_invoice: false,
    }
    const updated = { ...existing, ...updates }
    sessionStorage.setItem('flipflop_buying_flow', JSON.stringify(updated))
  }
}

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

  console.log('[Analytics Event]', event)
  
  if (typeof window !== 'undefined') {
    // Store event locally
    const key = 'flipflop_analytics_events'
    const existing = JSON.parse(sessionStorage.getItem(key) || '[]')
    existing.push(event)
    sessionStorage.setItem(key, JSON.stringify(existing))
    
    // Send to backend with buying flow context
    const buyingFlow = getBuyingFlowData()
    const customerId = localStorage.getItem('flipflop_customer_id')
    
    fetch('/api/public/analytics/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_type: event.event_type,
        curated_build_id: event.curated_build_id,
        metadata: event.metadata,
        buying_flow: buyingFlow,
        customer_id: customerId ? parseInt(customerId) : null,
      }),
    }).catch(err => console.warn('Failed to send analytics event:', err))
  }
}

export function getSessionEvents(): AnalyticsEvent[] {
  if (typeof window === 'undefined') return []
  const key = 'flipflop_analytics_events'
  return JSON.parse(sessionStorage.getItem(key) || '[]')
}
