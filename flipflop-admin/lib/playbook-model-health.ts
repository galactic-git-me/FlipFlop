import type { PlaybookOffer } from "./playbook-proposals";

export function modelHealth(offer: PlaybookOffer | null, requiredCount: number) {
  const parts = (offer?.components ?? []).filter(part => !part.role.startsWith("os"));
  const ready = parts.filter(part => part.media_ready === true).length;
  const total = Math.max(requiredCount, parts.length);
  const issues = parts.filter(part => !part.media_ready).map(part =>
    `${part.role}: ${part.model_generation_status?.replaceAll("_", " ").toLowerCase() || "model not generated"} — ${part.title}`);
  if (parts.length < total) issues.push(`${total - parts.length} required components not yet linked`);
  const status = total > 0 && ready === total ? "green" : ready > 0 || parts.some(part => part.model_generation_status && !["FAILED", "ERROR"].includes(part.model_generation_status)) ? "amber" : "red";
  const label = status === "green" ? "3D models ready" : status === "amber" ? "3D models in progress" : "3D models needed";
  return { status, label, ready, total, issues };
}
