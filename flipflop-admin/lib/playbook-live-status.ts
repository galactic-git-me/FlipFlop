import type { BookCell } from "./playbook-book";

export function playbookLiveStatus(cell: BookCell) {
  if (cell.is_live && cell.checkout_enabled && cell.availability_status === "in_stock") {
    return { colour: "green", label: "Live", reason: "Published and available to purchase." };
  }
  const offer = cell.offer;
  const delivery = offer?.delivery_products.standard;
  const ready = !!offer?.complete_hardware && offer.blockers.length === 0
    && delivery?.available === true && Number(delivery.recommended_price_gbp) > 0;
  return ready
    ? { colour: "amber", label: "Ready", reason: "Ready for approval and publication; not yet available to purchase." }
    : { colour: "red", label: "Not live", reason: offer?.blockers.join("\n") || "Build readiness checks are incomplete. See build details." };
}
