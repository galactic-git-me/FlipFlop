export interface CuratedBuild {
  id: string
  segment: string
  tier: 'Budget' | 'Mid-range' | 'High-end'
  name: string
  description: string
  use: string
  components: {
    cpu: string
    motherboard: string
    ram: string
    gpu: string
    storage: string
    case: string
    psu: string
    cooling: string
    os: string
  }
  playbook_id?: number
  missing_components: string[]
  price_gbp?: number
}

export interface CuratedBuildsResponse {
  builds: CuratedBuild[]
}

export interface Playbook {
  id: number
  name: string
  slots: PlaybookSlot[]
}

export interface PlaybookSlot {
  id: number
  slot_type: string
  is_customer_visible: boolean
  tier_names: Record<string, string>
}

export interface CaseItem {
  id: number
  name: string
  brand: string
  form_factor: string
  images: string[]
  rrp_gbp: number
  bestseller_rank?: number
  is_preferred: boolean
  is_transparent_panel: boolean
  height_mm?: number
  width_mm?: number
  depth_mm?: number
  max_gpu_length_mm?: number
  max_cooler_height_mm?: number
  radiator_support?: string[]
}

export interface ConfiguratorSelection {
  curated_build_id: string
  case_id?: number
  customizations: Record<string, any>
}

export interface AnalyticsEvent {
  event_type: 'playbook_entered' | 'case_chosen' | 'upsell_chosen' | 'rgb_tweaked' | 'ar_opened' | 'drop_off'
  curated_build_id: string
  metadata?: Record<string, any>
  timestamp: string
}
