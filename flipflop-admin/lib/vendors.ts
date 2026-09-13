// Fixed display order (per request) -- vendors always appear in this order,
// not sorted by count, so cards/tables are visually comparable at a glance.
export const VENDOR_ORDER = ["ebay", "amazon", "scan", "overclockers", "awd_it", "computer_orbit", "bargain_hardware", "newegg_uk", "ebuyer", "google_shopping", "aliexpress", "cex"] as const;

export interface VendorMeta {
  label: string;
  mark: string;
  color: string;
  domain: string;
}

export const VENDOR_META: Record<string, VendorMeta> = {
  ebay: { label: "eBay", mark: "eb", color: "#e53238", domain: "ebay.co.uk" },
  amazon: { label: "Amazon", mark: "a", color: "#ff9900", domain: "amazon.co.uk" },
  overclockers: { label: "Overclockers", mark: "OC", color: "#f7941d", domain: "overclockers.co.uk" },
  temu: { label: "Temu", mark: "T", color: "#fb7701", domain: "temu.com" },
  cex: { label: "CeX", mark: "CX", color: "#2e7d32", domain: "uk.webuy.com" },
  scan: { label: "Scan.co.uk", mark: "SC", color: "#0057b8", domain: "scan.co.uk" },
  awd_it: { label: "AWD-IT", mark: "AW", color: "#e11d48", domain: "awd-it.co.uk" },
  computer_orbit: { label: "Computer Orbit", mark: "CO", color: "#7c3aed", domain: "computerorbit.com" },
  bargain_hardware: { label: "Bargain Hardware", mark: "BH", color: "#0f766e", domain: "bargainhardware.co.uk" },
  newegg_uk: { label: "Newegg UK", mark: "NG", color: "#f59e0b", domain: "newegg.com" },
  ebuyer: { label: "Ebuyer", mark: "EB", color: "#2563eb", domain: "ebuyer.com" },
  google_shopping: { label: "Google Shopping", mark: "G", color: "#4285f4", domain: "shopping.google.com" },
  aliexpress: { label: "AliExpress", mark: "AE", color: "#ff4747", domain: "aliexpress.com" },
  unknown: { label: "Other vendor", mark: "OT", color: "#64748b", domain: "" },
};

// Sources arrive from both the extension's canonical key and older hostname
// based payloads. Normalising at the display boundary prevents a known seller
// from falling through to the '?' tile while old rows are being backfilled.
export function canonicalVendorKey(value: string): string {
  const key = value.toLowerCase().replace(/^www\./, "").replace(/[.-]/g, "_");
  const aliases: Record<string, string> = {
    scan_co_uk: "scan", scan: "scan", ocuk: "overclockers", overclockers_co_uk: "overclockers",
    awd_it_co_uk: "awd_it", computerorbit_com: "computer_orbit", bargainhardware_co_uk: "bargain_hardware",
    newegg: "newegg_uk", newegg_uk: "newegg_uk", ebuyer_com: "ebuyer", google: "google_shopping",
  };
  return aliases[key] ?? key;
}
