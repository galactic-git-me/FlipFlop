import type { BookCell } from "./playbook-book";
import type { PlaybookOffer } from "./playbook-proposals";

/** Supplier hardware availability, independent of media and publication approval. */
export function inventoryHealth(cell: BookCell, offer: PlaybookOffer | null, now = Date.now()) {
  const required = ["cpu", "motherboard", "ram", "storage", "psu", "cooling", "case"];
  if (!/integrated/i.test(cell.definition.components.gpu ?? "")) required.push("gpu");
  if ((cell.definition.components.storage ?? "").split("+").filter(value => value.trim()).length > 1) required.push("storage_secondary");
  const parts = (offer?.components ?? []).filter(part => !part.role.startsWith("os"));
  const roles = [...new Set([...required, ...parts.map(part => part.role)])];
  const issues: string[] = [];
  let unavailable = 0;
  let available = 0;
  for (const role of roles) {
    const part = parts.find(value => value.role === role);
    if (!part) { unavailable++; issues.push(`${role}: missing component`); continue; }
    const suggested = part.suggested_supplier_offer;
    // Never transfer an original supplier's stock claim to a different supplier.
    const source = !suggested || suggested.url === part.source_url ? part.source_observation : undefined;
    const stock = suggested?.stock_status ?? source?.stock_status;
    const observed = suggested?.observed_at ?? source?.observed_at ?? (!suggested ? part.price_observed_at : null);
    const age = observed ? now - Date.parse(observed) : NaN;
    if (["unavailable", "out_of_stock", "sold_out"].includes(stock ?? "")) {
      unavailable++; issues.push(`${role}: unavailable — ${part.title}`);
    } else if (stock === "available" && Number.isFinite(age) && age >= 0 && age <= 24 * 60 * 60 * 1000) {
      available++;
    } else {
      issues.push(`${role}: ${stock === "available" ? "stock check older than 24 hours or undated" : "stock unconfirmed"} — ${part.title}`);
    }
  }
  const status = unavailable ? "red" : issues.length ? "amber" : "green";
  const label = unavailable ? "Parts unavailable" : issues.length ? "Check availability" : "All parts available";
  return { status, label, available, total: roles.length, issues };
}
