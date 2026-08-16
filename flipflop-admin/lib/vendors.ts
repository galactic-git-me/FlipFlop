// Fixed display order (per request) -- vendors always appear in this order,
// not sorted by count, so cards/tables are visually comparable at a glance.
export const VENDOR_ORDER = ["ebay", "amazon", "vinted", "overclockers", "temu", "cex", "aliexpress"] as const;

export interface VendorMeta {
  label: string;
  mark: string;
  color: string;
  domain: string;
}

export const VENDOR_META: Record<string, VendorMeta> = {
  ebay: { label: "eBay", mark: "eb", color: "#e53238", domain: "ebay.co.uk" },
  amazon: { label: "Amazon", mark: "a", color: "#ff9900", domain: "amazon.co.uk" },
  vinted: { label: "Vinted", mark: "V", color: "#09b1ba", domain: "vinted.co.uk" },
  overclockers: { label: "Overclockers", mark: "OC", color: "#f7941d", domain: "overclockers.co.uk" },
  temu: { label: "Temu", mark: "T", color: "#fb7701", domain: "temu.com" },
  cex: { label: "CeX", mark: "CX", color: "#2e7d32", domain: "uk.webuy.com" },
  aliexpress: { label: "AliExpress", mark: "AE", color: "#e60012", domain: "aliexpress.com" },
  scan: { label: "Scan.co.uk", mark: "SC", color: "#0057b8", domain: "scan.co.uk" },
  unknown: { label: "Other", mark: "?", color: "#64748b", domain: "" },
};
