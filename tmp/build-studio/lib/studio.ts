import { normalizeAnchorManifest, type ResolvedAsset } from './asset-api';

export type Specs = Record<string, unknown>;
export interface Product { id: number; title: string; display_price: number; images?: string[]; description?: string; specifications: Specs; price_updated_at?: string; availability?: string }
export interface Slot { slot_id: number; slot_type: string; variants_by_tier: Record<string, Product[]> }
export interface Chassis { id: number; name: string; brand: string; images: string[]; rrp_gbp: number; form_factor: string; width_mm?: number; height_mm?: number; depth_mm?: number; max_gpu_length_mm?: number; max_cooler_height_mm?: number; engineering?: Specs }
export interface Configuration { selections: Record<number, number>; caseId: number | null }
export interface Check { code: string; severity: 'pass' | 'warning' | 'unknown' | 'error'; message: string; affected: string[] }
export interface Evaluation { checks: Check[]; can_checkout: boolean; price: { total: number; parts_total: number; labour: number; overhead: number } | null; verdicts: { slot_id: number; variants: { variant_id: number; is_compatible: boolean; reason: string | null }[] }[] }
export const labels: Record<string, string> = { case: 'Chassis', cpu: 'Processor', gpu: 'Graphics', motherboard: 'Motherboard', ram: 'Memory', storage: 'Storage', cooling: 'Cooling', psu: 'Power supply', fan: 'Case fans', os: 'Operating system' };
export const order = ['case', 'cpu', 'motherboard', 'gpu', 'ram', 'storage', 'cooling', 'psu', 'fan', 'os'];
export const money = (value: number) => new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 2 }).format(value);
export const options = (slot: Slot) => Array.from(new Map(Object.values(slot.variants_by_tier).flat().map(p => [p.id, p])).values());
export function selected(slot: Slot, config: Configuration) { return options(slot).find(p => p.id === config.selections[slot.slot_id]); }
export function changePart(config: Configuration, slotId: number, variantId: number | null): Configuration {
  const selections = { ...config.selections };
  if (variantId === null) delete selections[slotId]; else selections[slotId] = variantId;
  return { ...config, selections };
}
export function defaults(slots: Slot[], cases: Chassis[]): Configuration {
  return { caseId: cases[0]?.id ?? null, selections: Object.fromEntries(slots.flatMap(s => { const p = s.variants_by_tier.mid?.[0] ?? options(s)[0]; return p ? [[s.slot_id, p.id]] : []; })) };
}
export async function request<T>(path: string, signal?: AbortSignal, body?: unknown): Promise<T> {
  const res = await fetch('/api/public/' + path, { signal, cache: 'no-store', ...(body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
  if (!res.ok) { const error = await res.json().catch(() => ({})); throw new Error(typeof error.detail === 'string' ? error.detail : `Catalogue unavailable (${res.status}). Please retry.`); }
  return res.json();
}
export async function getAssets(slots: Slot[], config: Configuration, signal: AbortSignal) {
  const subjects = slots.filter(s => config.selections[s.slot_id]).map(s => ({ subject_type: 'variant', subject_id: config.selections[s.slot_id], category: s.slot_type }));
  if (config.caseId) subjects.push({ subject_type: 'case', subject_id: config.caseId, category: 'case' });
  const data = await request<{ results: { query: { subject_type: string; subject_id: number }; asset: ResolvedAsset | null }[] }>('assets/resolve', signal, { subjects });
  return Object.fromEntries(data.results.map(r => [r.query.subject_type + ':' + r.query.subject_id, r.asset ? { ...r.asset, anchor_manifest: normalizeAnchorManifest(r.asset.anchor_manifest) } : null]));
}
export function assetURL(ref: string | null | undefined): string | null {
  if (!ref) return null;
  // Route backend media through the storefront; never expose an internal host.
  if (ref.startsWith('/media/')) return '/studio-assets/' + ref.slice(7);
  if (ref.startsWith('/') && !ref.startsWith('//')) return ref;
  try { const url = new URL(ref); if (url.pathname.startsWith('/media/')) return '/studio-assets/' + url.pathname.slice(7); return url.protocol === 'https:' ? ref : null; } catch { return null; }
}
