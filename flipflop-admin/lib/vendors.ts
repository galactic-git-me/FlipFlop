// Fixed display order (per request) -- vendors always appear in this order,
// not sorted by count, so cards/tables are visually comparable at a glance.
export const VENDOR_ORDER = ["ebay", "amazon", "google_shopping", "scan", "overclockers", "awd_it", "computer_orbit", "bargain_hardware", "cex"] as const;

export interface VendorMeta {
  label: string;
  mark: string;
  color: string;
  domain: string;
}

export const VENDOR_META: Record<string, VendorMeta> = {
  ebay: { label: "eBay", mark: "eb", color: "#e53238", domain: "ebay.co.uk" },
  amazon: { label: "Amazon", mark: "a", color: "#ff9900", domain: "amazon.co.uk" },
  google_shopping: { label: "Google Shopping", mark: "G", color: "#4285f4", domain: "shopping.google.com" },
  overclockers: { label: "Overclockers", mark: "OC", color: "#f7941d", domain: "overclockers.co.uk" },
  temu: { label: "Temu", mark: "T", color: "#fb7701", domain: "temu.com" },
  cex: { label: "CeX", mark: "CX", color: "#2e7d32", domain: "uk.webuy.com" },
  scan: { label: "Scan.co.uk", mark: "SC", color: "#0057b8", domain: "scan.co.uk" },
  awd_it: { label: "AWD-IT", mark: "AW", color: "#e11d48", domain: "awd-it.co.uk" },
  computer_orbit: { label: "Computer Orbit", mark: "CO", color: "#7c3aed", domain: "computerorbit.com" },
  bargain_hardware: { label: "Bargain Hardware", mark: "BH", color: "#0f766e", domain: "bargainhardware.co.uk" },
  unknown: { label: "Other", mark: "?", color: "#64748b", domain: "" },
};
