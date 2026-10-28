export type Mode = 'fast_track' | 'standard' | 'flexible';
export interface ReconciliationHealth {
  scheduled_enabled:boolean;last_success_at:string|null;
  runs:Array<{id:number;status:string;created_at:string;result:{imported?:number;reused?:number;error_type?:string;blocked?:Array<{part_key:string;reason:string}>}}>;
}
export const modes: Array<{id:Mode;label:string}> = [
  {id:'fast_track',label:'Fast Track'},{id:'standard',label:'Standard'},{id:'flexible',label:'Flexible'},
];
export const costFields = [
  ['build_labour','Build labour'],['packaging','Packaging'],['outbound_delivery','Outbound delivery'],
  ['insurance','Insurance'],['payment_fixed','Fixed payment charge'],['expected_failure_cost','Expected failures'],
  ['allocated_overhead','Allocated overhead'],['other_variable_costs','Other variable costs'],
] as const;
export type CostField = typeof costFields[number][0];
export interface ModeDraft {
  costs: Record<CostField,string|null>;
  minimum_contribution_gbp:string|null; minimum_margin_fraction:string|null; premium_gbp:string|null;
  workshop_working_days:number|null; courier_working_days:number|null; maximum_delivery_working_days:number|null;
}
export interface CommercialDraft {
  version:number; definition_sha256:string; checkout_enabled:false; condition:string;
  required_part_keys:string[]; checkout_slot_parts:Record<string,[number,string]>; checkout_case:[number,string]|null;
  vat_rate:string|null; payment_rate:string|null; warranty_rate:string|null; returns_rate:string|null;
  market_tolerance_fraction:string|null; modes:Record<Mode,ModeDraft>;
  market:{condition:string;sold_median_gbp:string|null;sold_sample_size:number|null;observed_at:string|null;
    evidence_source:string|null;evidence_ref:string|null};
}
export interface ReadinessCell {
  cell_id:string;name:string;segment:string;tier:string;playbook_id:number|null;
  policy_version:number|null;checkout_enabled:boolean;has_draft:boolean;
  required_products:number|null;evidenced_products:number;state:string;blockers:string[];
  catalogue_selected_products?:number;catalogue_required_products?:number;
}
export interface ReadinessIndex {items:ReadinessCell[];observed_at:string;note:string}
export interface SourcePreview {
  listing_db_id:number;listing_id:string;observation_id:number;observed_at:string;url:string;source:string;
  condition:string;item_gbp:string|null;delivery_gbp:string|null;delivery_working_days:number|null;
  delivery_estimate_source:string|null;active_listing:boolean;fingerprint:string;fresh:boolean;
  evidence_kind?:string;identity_source?:string;
  stock_status?:'available'|'unavailable'|'unknown';stock_evidence?:string|null;
  postage_verified?:boolean;postage_assumption?:'owner-approved-zero-fallback';commercial_capture_verified?:boolean;prime_eligible?:boolean|null;
}
export function supplierDisplayLabel(source: Partial<Pick<SourcePreview,'source'|'url'>> | null | undefined) {
  if (!source) return 'Supplier unconfirmed';
  let platform = source.source || 'Supplier';
  try {
    const host = source.url ? new URL(source.url).hostname.toLowerCase() : '';
    if (host === 'amazon.co.uk' || host.endsWith('.amazon.co.uk')) platform = 'Amazon';
    else if (host === 'overclockers.co.uk' || host.endsWith('.overclockers.co.uk')) platform = 'Overclockers UK';
    else if (host === 'royalcdkeys.com' || host.endsWith('.royalcdkeys.com')) platform = 'RoyalCDKeys';
    else if (host === 'releases.ubuntu.com') platform = 'Ubuntu';
    else if (host === 'ebay.co.uk' || host.endsWith('.ebay.co.uk') || host === 'ebay.com' || host.endsWith('.ebay.com')) platform = 'eBay';
    else if (host === 'vinted.co.uk' || host.endsWith('.vinted.co.uk')) platform = 'Vinted';
  } catch { /* Keep the captured source label when a URL is unavailable. */ }
  const seller = source.source?.trim();
  return seller && seller.toLowerCase() !== platform.toLowerCase()
    ? `${platform} · seller ${seller}` : platform;
}
export function supplierArrivalEstimate(source: Partial<Pick<SourcePreview,
  'source'|'url'|'delivery_working_days'|'delivery_estimate_source'|'prime_eligible'>> | null | undefined) {
  if (!source) return null;
  if (typeof source.delivery_working_days === 'number' && source.delivery_working_days >= 0) {
    return {days:source.delivery_working_days,label:source.delivery_estimate_source || 'captured estimate'};
  }
  const vendor=String(source.source || '').toLowerCase();
  let host='';
  try {host=source.url ? new URL(source.url).hostname.toLowerCase() : '';} catch { /* Use the captured vendor label. */ }
  const amazon=vendor.includes('amazon') || host==='amazon.co.uk' || host.endsWith('.amazon.co.uk');
  const marketplace=vendor.includes('ebay') || vendor.includes('vinted') || host.includes('ebay.') || host.includes('vinted.');
  if (amazon && source.prime_eligible === true) return {days:1,label:'Amazon Prime vendor default'};
  if (marketplace) return {days:7,label:'marketplace vendor default'};
  if (vendor || host) return {days:3,label:'supplier vendor default'};
  return {days:3,label:'general supplier default'};
}
export interface ReadinessPart {role:string;slot_id:number|null;variant_id:number|null;case_id?:number;
  title:string;part_key:string|null;source:SourcePreview|null;planned_title?:string|null;
  listing_url?:string|null;listed_item_gbp?:string|null;supplier_postage_gbp?:string|null;
  supplier_postage_assumption?:'captured'|'owner-approved-zero-fallback';
  listed_total_gbp?:string|null;price_observed_at?:string|null;catalogue_status?:string|null;catalogue_price_gbp?:string|null}
export interface DraftError {field:string;message:string}
export interface ReadinessDetail {
  cell_id:string;playbook_id:number;name:string;definition_sha256:string;base_policy_version:number;
  draft_id:number|null;draft:CommercialDraft;draft_errors:DraftError[];draft_complete:boolean;
  draft_stale:boolean;catalogue_error:string|null;parts:ReadinessPart[];cases:Array<{id:number;name:string}>;
  assessment:{modes:Partial<Record<Mode,{offerable:boolean;price_gbp:string|null;contribution_gbp?:string;
    delivery_working_days?:number;reason:string}>>}|null;checkout_enabled:boolean;
  catalogue_blockers?:string[];catalogue_parts_total_gbp?:string|null;
  price_review_sha256?:string|null;
}
export interface ImportEntry {part_key:string;observation_id:number;source_fingerprint:string;
  fees_gbp:string;risk_gbp:string;supplier_confidence:string;stock_confirmed:boolean}

export interface ConfigurationReview {
  request_id:number;playbook_name:string;curated_build_id:string|null;budget_tier:string|null;
  component_count:number;checkout_enabled:boolean;created_at:string;
}
export interface ConfigurationDetail {
  request_id:number;playbook_id:number;name:string;curated_build_id:string|null;budget_tier:string|null;
  base_policy_version:number;draft_id:number|null;definition_sha256:string;draft:CommercialDraft|null;
  draft_errors:DraftError[];parts:Array<ReadinessPart & {case_id?:number}>;assessment:ReadinessDetail['assessment'];checkout_enabled:boolean;
  policy_blockers:string[];
  catalogue_parts_total_gbp?:string|null;
  price_review_sha256?:string|null;
}

export interface ConfigurationEvidenceSelection {
  part_key:string;observation_id:number;source_fingerprint:string;
}

export function commercialPolicyPayload(draft:CommercialDraft, enabled:boolean) {
  const market=draft.market;
  const hasMarket=market&&[market.sold_median_gbp,market.sold_sample_size,market.observed_at,market.evidence_source,market.evidence_ref].some(value=>value!==null&&value!=='');
  return {...draft,modes:{...draft.modes,flexible:{...draft.modes.flexible,maximum_delivery_working_days:null}},checkout_enabled:enabled,market:hasMarket?market:null,market_tolerance_fraction:hasMarket?draft.market_tolerance_fraction:'0'};
}
