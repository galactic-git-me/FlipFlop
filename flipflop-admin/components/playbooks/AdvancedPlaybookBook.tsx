"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ChevronLeft, ChevronRight, RefreshCw, X } from "lucide-react";
import { api } from "@/lib/api";
import { supplierArrivalEstimate } from "@/lib/commercial-readiness";
import dynamic from "next/dynamic";
const PlaybookMediaDialog = dynamic(() => import("./PlaybookMediaDialog"), { ssr: false });
import {
  BOOK_PAGES,
  bookMoney,
  bookPage,
  deliveryModes,
} from "@/lib/playbook-book";
import type {
  BookCell,
  BookPage,
  PlaybookBook as BookData,
} from "@/lib/playbook-book";
import type { PlaybookOffer, PlaybookPart } from "@/lib/playbook-proposals";
import CommercialReviewWorkspace from "./CommercialReviewWorkspace";
import PlaybookAutomationHealth from "./PlaybookAutomationHealth";
import PlaybookMarketReview from "./PlaybookMarketReview";

type Props = {
  refreshKey?: number;
  onEdit: (segmentId: number) => void;
  renderTools?: (page: BookPage, cell: BookCell) => ReactNode;
};
const field = (label: string, value: ReactNode) => (
  <div className="flex justify-between gap-3">
    <dt className="text-slate-400">{label}</dt>
    <dd className="text-right text-slate-100">{value}</dd>
  </div>
);
const text = (value: string | undefined | null) =>
  value?.replaceAll("_", " ") || "Not recorded";
const postageCost = (part: PlaybookPart) =>
  part.source_observation?.postage_verified === true
    ? bookMoney(part.source_observation.delivery_gbp ?? part.supplier_postage_gbp)
    : "£0.00 (cost fallback)";
const offerKind = (value: string) =>
  value === "ready_to_ship"
    ? "Ready-to-Ship build"
    : value === "curated"
    ? "Curated offer"
    : value === "curated_template"
    ? "Curated template"
    : text(value);
function Evidence({ children }: { children: ReactNode }) {
  return <p className="text-xs leading-5 text-slate-400">{children}</p>;
}
function modelReadinessReason(reason: string | null | undefined) {
  if (!reason || /photos? need approval|approve.*photos/i.test(reason))
    return "Choose one to four photos for the 3D model, then approve the finished model.";
  if (reason === "No captured product photos are available")
    return "No captured photos are available to choose as 3D model references.";
  if (/choose one to four/i.test(reason))
    return "Choose one to four photos for the 3D model, then approve the finished model.";
  return reason;
}
function explainProposalBlocker(blocker: string) {
  if (blocker.startsWith("Playbook sourcing needs catalogue products:"))
    return `Missing catalogue links for ${blocker.split(":").slice(1).join(":").trim()}. Link products that match the build.`;
  if (blocker.startsWith("Refresh exact supplier stock evidence for:"))
    return `Supplier listing, stock, or price evidence needs a refresh for ${blocker.split(":").slice(1).join(":").trim()}.`;
  if (blocker === "Automatic product research must resolve compatibility evidence before recommendation")
    return "The selected parts do not yet have verified fit evidence. Open Compatibility to review the checks.";
  if (blocker === "Automatic sourcing must link the operating-system licence and its cost from the catalogue")
    return "The operating-system licence is not linked to a catalogue product and cost yet.";
  if (blocker.startsWith("Automatic sourcing needs a matching "))
    return `A matching catalogue product is missing for ${blocker.replace("Automatic sourcing needs a matching ", "").replace(" catalogue product", "").toUpperCase()}.`;
  if (blocker.includes("not live:") && blocker.includes("no media-ready substitute passed selection")) {
    const [role, reason = "This part is not ready to show customers."] = blocker.split(" not live: ");
    return `${role.toUpperCase()} is not ready for the customer listing: ${reason.replace("; no media-ready substitute passed selection", "").replaceAll("_", " ")}.`;
  }
  if (blocker.startsWith("Fast Track:")) return `Fast Track cannot currently be offered: ${blocker.slice("Fast Track:".length).trim()}`;
  if (blocker.startsWith("Standard:")) return `Standard delivery cannot currently be offered: ${blocker.slice("Standard:".length).trim()}`;
  if (blocker.startsWith("Flexible:")) return `Flexible delivery cannot currently be offered: ${blocker.slice("Flexible:".length).trim()}`;
  if (blocker === "No active parent Playbook") return "There is no active Playbook policy for this build.";
  if (blocker === "Calculate and review selling prices") return "Selling prices still need to be calculated and reviewed.";
  if (blocker === "Approved policy needs correction") return "The approved pricing or delivery policy needs correction.";
  if (blocker === "Build definition changed since review") return "The build changed after its last review. Review the updated build before approval.";
  if (blocker === "Sold-market comparison is stale") return "The sold-market comparison needs to be refreshed.";
  if (blocker === "Current workshop evidence is missing or full") return "Workshop capacity evidence is missing or does not show available capacity.";
  if (blocker === "Automatic BOM assembly currently supports at most two authored storage devices") return "The proposal builder currently supports pricing up to two storage drives, but this build defines more. The builder needs support for the full storage list.";
  if (blocker.includes("complete authored build is not represented")) return "The selected catalogue parts do not yet represent every item in the authored build.";
  return blocker;
}
function ProposalIssues({ offer }: { offer: PlaybookOffer }) {
  const blockers = [...new Set(offer.blockers)];
  if (!blockers.length && offer.complete_hardware) return null;
  const shown = blockers.slice(0, 2);
  const remaining = blockers.slice(2);
  return (
    <section aria-label="Why this proposal needs attention" className="mt-3 rounded-lg border border-rose-400/40 bg-rose-950/30 p-3">
      <h4 className="text-xs font-semibold text-rose-200">{blockers.length ? `${blockers.length} things to fix before this build can be approved` : "This proposal is incomplete; the API did not return specific blocker details."}</h4>
      {!!shown.length && <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-rose-100">{shown.map((blocker) => <li key={blocker}>{explainProposalBlocker(blocker)}</li>)}</ul>}
      {!!remaining.length && <details className="mt-2 text-xs text-rose-100"><summary className="cursor-pointer">Show {remaining.length} more</summary><ul className="mt-2 list-disc space-y-1 pl-4">{remaining.map((blocker) => <li key={blocker}>{explainProposalBlocker(blocker)}</li>)}</ul></details>}
      <p className="mt-2 text-[11px] text-rose-200/80">Open the matching Playbook slice above to review the evidence and next step.</p>
    </section>
  );
}
function Parts({
  parts,
  detail = false,
}: {
  parts: PlaybookPart[];
  detail?: boolean;
}) {
  if (!parts.length)
    return <Evidence>No selected catalogue components recorded.</Evidence>;
  const priority = ["cpu", "gpu", "ram", "storage"];
  const ordered = [...parts].sort(
    (a, b) =>
      (priority.indexOf(a.role) < 0 ? 99 : priority.indexOf(a.role)) -
      (priority.indexOf(b.role) < 0 ? 99 : priority.indexOf(b.role))
  );
  return (
    <ul className="space-y-2">
      {ordered.slice(0, detail ? parts.length : 4).map((part) => (
        <li
          key={`${part.role}:${part.variant_id}`}
          title={part.title}
          className={`text-xs ${detail ? "" : "line-clamp-2"}`}
        >
          <span className="uppercase text-cyan-300">{part.role}: </span>
          {part.title}
          {detail && (
            <span className="block text-slate-400">
              Supplier item {bookMoney(part.listing_price_gbp)} · postage{" "}
              {postageCost(part)} ·{" "}
              {part.media_ready === false
                ? `3D model: ${part.not_live_reason}`
                : "Final 3D model approved"}
            </span>
          )}
        </li>
      ))}
      {!detail && parts.length > 4 && (
        <li className="text-xs text-slate-400">
          +{parts.length - 4} more components
        </li>
      )}
    </ul>
  );
}
function CellPage({
  cell,
  page,
  detail = false,
}: {
  cell: BookCell;
  page: BookPage;
  detail?: boolean;
}) {
  const offer = cell.offer;
  const parts = offer?.components ?? [];
  const upgrades = offer?.upsells ?? [];
  const limit = detail ? 100 : 3;
  switch (page) {
    case "build":
      return (
        <>
          <p className="font-medium"><span className="text-xs font-normal text-slate-400">Build name: </span>{cell.name}</p>
          {offer ? (
            <Parts parts={parts} detail={detail} />
          ) : (
            <ul className="space-y-1 text-xs">
              {Object.entries(cell.definition.components)
                .slice(0, detail ? undefined : 4)
                .map(([role, title]) => (
                  <li key={role}>
                    <span className="uppercase text-cyan-300">{role}: </span>
                    {title}
                  </li>
                ))}
            </ul>
          )}
          {!offer && (
            <Evidence>
              Authored recommendation only; no sourced proposal.
            </Evidence>
          )}
          {offer && <ProposalIssues offer={offer} />}
        </>
      );
    case "pricing":
      return (
        <>
          <dl className="space-y-1 text-xs">
            {field(
              "Approved selling price",
              bookMoney(cell.approved_price_gbp)
            )}
            {field(
              "Proposed Standard price",
              bookMoney(
                offer?.delivery_products.standard?.recommended_price_gbp
              )
            )}
            {field("Sold median", bookMoney(cell.market?.sold_median_gbp))}
            {field("Market review", text(cell.market_review_status ?? "not_collected"))}
            {field("Active market", bookMoney(cell.active_build_market_gbp))}
            {field(
              "Walk-away (approved sell floor)",
              bookMoney(cell.walk_away_price_gbp)
            )}
            {field(
              "Proposed sell floor",
              bookMoney(cell.proposed_walk_away_price_gbp)
            )}
          </dl>
          {detail && (
            <>
              <Evidence>
                Supplier listing prices are shown on the Linked listings page;
                they are not complete-PC market comparables.
              </Evidence>
              <Evidence>
                Last approved floor:{" "}
                {cell.walk_away_observed_at ?? "Not recorded"}. Current source
                and checkout checks still apply.
              </Evidence>
              <Evidence>
                Sold evidence: {cell.market?.evidence_source ?? "Not recorded"}{" "}
                · observed {cell.market?.observed_at ?? "Not recorded"} · sample{" "}
                {cell.market?.sold_sample_size ?? "Not recorded"}
              </Evidence>
              {cell.pricing_gaps.map((gap) => (
                <Evidence key={gap}>{gap}</Evidence>
              ))}
            </>
          )}
        </>
      );
    case "economics":
      return (
        <>
          <dl className="space-y-2 text-xs">
            {deliveryModes.map(([mode, label]) => {
              const quote = offer?.delivery_products[mode];
              const price = quote?.recommended_price_gbp;
              const profit = quote?.estimated_profit_gbp;
              return (
                <div key={mode} className="border-b border-white/10 pb-2">
                  <dt className="font-semibold text-cyan-200">{label}</dt>
                  <dd>
                    {bookMoney(price)} · estimated profit {bookMoney(profit)}
                  </dd>
                  <dd className="text-slate-400">
                    Estimated operating cost (net){" "}
                    {bookMoney(quote?.estimated_total_cost_gbp)}
                    {quote?.estimated_delivery_working_days != null
                      ? ` · ${quote.estimated_delivery_working_days} working days`
                      : ""}
                  </dd>
                  {detail && (
                    <dd className="text-slate-400">
                      Net revenue {bookMoney(quote?.net_revenue_gbp)} · VAT{" "}
                      {bookMoney(quote?.vat_gbp)} · minimum selling price{" "}
                      {bookMoney(quote?.profit_floor_gbp)}
                    </dd>
                  )}
                  {detail && (
                    <dd className="text-slate-400">
                      {quote?.reason ?? "No commercial quote recorded"}
                    </dd>
                  )}
                </div>
              );
            })}
          </dl>
          <Evidence>
            Estimates from the proposal; publication and checkout recheck the
            exact evidence.
          </Evidence>
        </>
      );
    case "supply":
      return (
        <>
          <p className="text-xs">
            {
              parts.filter(
                (part) =>
                  part.source_observation?.fresh &&
                  part.source_observation?.stock_status === "available"
              ).length
            }
            /{parts.length} supplier availability records assessed as fresh
          </p>
          <ul className="space-y-2">
            {parts.slice(0, limit).map((part) => (
              <li key={part.variant_id} className="text-xs">
                <span className="uppercase text-cyan-300">{part.role}</span> ·{" "}
                {part.title}
                <span className="block text-slate-400">
                  {text(part.source_observation?.stock_status)} ·{" "}
                  {part.source_observation?.fresh
                    ? "fresh at assessment"
                    : "missing or stale at assessment"}{" "}
                  · {bookMoney(part.listing_price_gbp)}
                </span>
                {detail && (
                  <>
                    <a
                      className="text-cyan-300 underline"
                      href={safeUrl(part.source_url)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Supplier listing
                    </a>
                    <span className="block">
                      Postage {postageCost(part)} · arrival{" "}
                      {(() => {
                        const arrival = supplierArrivalEstimate(
                          part.source_observation ?? { url: part.source_url }
                        );
                        return arrival
                          ? `${arrival.days} working days · ${arrival.label}`
                          : "no supplier-specific default available";
                      })()}
                    </span>
                  </>
                )}
              </li>
            ))}
          </ul>
          {!parts.length && <Evidence>No linked supplier proposal.</Evidence>}
        </>
      );
    case "upsells":
      return (
        <>
          <p className="text-xs">
            {upgrades.length} alternatives ·{" "}
            {upgrades.filter((item) => item.publication_eligible).length}{" "}
            publication-eligible
          </p>
          <ul className="space-y-2">
            {upgrades.slice(0, limit).map((item) => (
              <li
                key={`${item.role}:${item.component.variant_id}`}
                className="text-xs"
              >
                <span className="text-cyan-300">{item.role}: </span>
                {item.component.title}
                {detail && (
                  <span className="block text-slate-400">
                    Fit {item.compatibility_verified ? "verified" : "pending"} ·
                    performance {item.quality_verified ? "verified" : "pending"}{" "}
                    ·{" "}
                    {item.publication_eligible
                      ? "eligible"
                      : "not eligible for publication"}
                  </span>
                )}
              </li>
            ))}
          </ul>
          {!upgrades.length && (
            <Evidence>No assessed alternatives recorded.</Evidence>
          )}
        </>
      );
    case "upsell-economics":
      return (
        <>
          <Evidence>
            Exact upgraded whole-build prices, not component price deltas.
          </Evidence>
          <ul className="space-y-2">
            {upgrades.slice(0, limit).map((item) => (
              <li
                key={`${item.role}:${item.component.variant_id}`}
                className="text-xs"
              >
                <p>{item.component.title}</p>
                {deliveryModes.map(([mode, label]) => (
                  <p key={mode} className="text-slate-400">
                    {label}:{" "}
                    {bookMoney(
                      item.delivery_products[mode]?.recommended_price_gbp
                    )}{" "}
                    · profit{" "}
                    {bookMoney(
                      item.delivery_products[mode]?.estimated_profit_gbp
                    )}
                  </p>
                ))}
              </li>
            ))}
          </ul>
          {!upgrades.length && <Evidence>No upsell costing recorded.</Evidence>}
        </>
      );
    case "media":
    case "assets":
      return (
        <>
          <p className="text-xs">
            {parts.filter((part) => part.media_ready === true).length}/
            {parts.length} components pass the exact 3D model gate
          </p>
          <ul className="space-y-1">
            {parts
              .filter((part) => part.media_ready !== true)
              .slice(0, limit)
              .map((part) => (
                <li key={part.variant_id} className="text-xs text-amber-300">
                  {part.role}:{" "}
                  {modelReadinessReason(part.not_live_reason) ??
                    "Final model status is not verified in this snapshot"}
                </li>
              ))}
          </ul>
          <Evidence>
            {page === "media"
              ? "Captured listing photos and videos are automatically included. Choose one to four photos for each 3D model."
              : "Only an active final model matching the chosen model-reference photos passes."}
          </Evidence>
        </>
      );
    case "performance":
      return (
        <>
          <ul className="space-y-2">
            {parts
              .filter((part) => ["cpu", "gpu"].includes(part.role))
              .map((part) => {
                const evidence = part.performance_evidence;
                return (
                  <li key={part.variant_id} className="text-xs">
                    <p className="text-cyan-300">
                      {part.role}: {part.title}
                    </p>
                    <p>
                      Overall {evidence?.overall_score ?? "Not recorded"} ·
                      gaming {evidence?.gaming_score ?? "Not recorded"} ·
                      workstation{" "}
                      {evidence?.workstation_score ?? "Not recorded"}
                    </p>
                    {detail && (
                      <p className="text-slate-400">
                        {evidence?.benchmark_source ?? "No benchmark source"} ·
                        confidence {evidence?.confidence_score ?? "unknown"}
                      </p>
                    )}
                  </li>
                );
              })}
          </ul>
          <Evidence>
            Stored model benchmarks; no measured complete-PC result is implied.
          </Evidence>
        </>
      );
    case "live":
      return (
        <>
          <dl className="space-y-1 text-xs">
            {field(
              "Publication status",
              cell.is_live ? "Published" : "Not published"
            )}
            {field(
              "Checkout policy",
              cell.checkout_enabled ? "Enabled" : "Disabled"
            )}
            {field("Catalogue availability", text(cell.availability_status))}
            {field("Policy version", cell.policy_version ?? "Not recorded")}
          </dl>
          <Evidence>
            {offer?.blockers.length
              ? `${offer.blockers.length} proposal blockers`
              : "Current proposal checks must be revalidated before publication."}
          </Evidence>
          {detail && (
            <ul className="list-disc space-y-1 pl-4 text-xs text-amber-200">
              {offer?.blockers.map((blocker) => (
                <li key={blocker}>{blocker}</li>
              ))}
            </ul>
          )}
        </>
      );
    case "approvals":
      return (
        <>
          <p className="text-xs">
            {cell.proposal_status === "pending"
              ? "Proposal awaiting review"
              : "No pending build proposal"}
          </p>
          <p className="text-xs text-amber-300">
            {offer?.blockers.length ?? 0} recorded blockers
          </p>
          <p className="text-xs">Market evidence: {text(cell.market_review_status ?? "not_collected")}</p>
          {detail ? (
            <ul className="list-disc space-y-1 pl-4 text-xs">
              {offer?.blockers.map((blocker) => (
                <li key={blocker}>{blocker}</li>
              ))}
            </ul>
          ) : (
            <Evidence>
              {offer?.blockers[0] ??
                "Open this cell to review exact source, compatibility and publication decisions."}
            </Evidence>
          )}
        </>
      );
    case "history":
      return (
        <>
          <ul className="space-y-3">
            {cell.history.slice(0, limit).map((event) => (
              <li key={event.id} className="text-xs">
                <p className="text-cyan-200">{text(event.event)}</p>
                <p className="text-slate-400">
                  {event.at
                    ? new Date(event.at).toLocaleString("en-GB")
                    : "Time not recorded"}{" "}
                  · {event.actor}
                </p>
                {detail && (
                  <>
                    <p>{event.reason}</p>
                    {event.before && (
                      <details className="mt-1">
                        <summary>Before / after evidence</summary>
                        <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all p-2 text-[11px]">
                          {JSON.stringify(
                            { before: event.before, after: event.after },
                            null,
                            2
                          )}
                        </pre>
                      </details>
                    )}
                  </>
                )}
              </li>
            ))}
          </ul>
          {!cell.history.length && (
            <Evidence>No recorded events for this cell.</Evidence>
          )}
          {detail && <Evidence>{cell.history_coverage}</Evidence>}
        </>
      );
    case "distribution":
      return (
        <>
          <ul className="space-y-2">
            {cell.distribution.slice(0, limit).map((channel, index) => (
              <li key={`${channel.channel}:${index}`} className="text-xs">
                <p className="capitalize text-cyan-200">
                  {channel.channel} · {text(channel.status)}
                  {channel.offer_kind
                    ? ` · ${offerKind(channel.offer_kind)}`
                    : ""}
                </p>
                {detail && (
                  <p className="text-slate-400">
                    {channel.title ? `${channel.title} · ` : ""}
                    {channel.source} ·{" "}
                    {channel.external_id ?? "No external listing ID"}
                    {channel.updated_at
                      ? ` · ${new Date(channel.updated_at).toLocaleString(
                          "en-GB"
                        )}`
                      : ""}
                  </p>
                )}
              </li>
            ))}
          </ul>
          {detail && <Evidence>{cell.distribution_coverage}</Evidence>}
        </>
      );
    case "compatibility":
      return (
        <>
          <p
            className={`text-xs ${
              offer?.compatibility.verified
                ? "text-emerald-300"
                : "text-amber-300"
            }`}
          >
            {offer?.compatibility.verified
              ? "Proposal fit verified"
              : "Fit evidence incomplete"}
          </p>
          <ul className="space-y-1">
            {(offer?.compatibility.checks ?? [])
              .filter((check) => detail || check.severity !== "info")
              .slice(0, limit)
              .map((check, index) => (
                <li key={`${check.code}:${index}`} className="text-xs">
                  {check.message}
                </li>
              ))}
          </ul>
        </>
      );
    case "software":
      return (
        <>
          <p className="text-xs">
            {cell.software_profile?.recommended_package_ids?.join(", ") ||
              "No separate cell software profile; reviewed use-case defaults apply"}
          </p>
          <ul className="space-y-1">
            {parts
              .filter((part) => part.role.startsWith("os"))
              .map((part) => (
                <li key={part.variant_id} className="text-xs text-cyan-200">
                  {part.title} · {bookMoney(part.listing_price_gbp)}
                </li>
              ))}
          </ul>
          {detail && <Evidence>{cell.software_profile?.rationale}</Evidence>}
        </>
      );
    case "automation":
      return (
        <>
          <p className="text-xs">
            Latest stored proposal:{" "}
            {cell.proposal_observed_at
              ? new Date(cell.proposal_observed_at).toLocaleString("en-GB")
              : "Not recorded"}
          </p>
          <Evidence>
            Scheduled work is shared across the matrix. Open a cell for current
            run health.
          </Evidence>
        </>
      );
  }
}
function safeUrl(value: string) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : undefined;
  } catch {
    return undefined;
  }
}

function pageNeedsAttention(
  page: BookPage,
  cells: BookCell[],
  book: BookData | null,
  includeUnassignedDistribution = true
) {
  switch (page) {
    case "build":
      return cells.some((cell) => cell.offer && !cell.offer.complete_hardware);
    case "pricing":
      // Missing market comparisons are useful review context, but do not by
      // themselves block a cell. An approved minimum selling price does.
      return cells.some((cell) =>
        cell.pricing_gaps.some((gap) =>
          gap.toLowerCase().includes("approved cell minimum selling price")
        )
      );
    case "economics":
      return cells.some((cell) => {
        const quotes = cell.offer?.delivery_products;
        return !!quotes && !deliveryModes.some(([mode]) => {
          const quote = quotes[mode];
          return quote?.available && quote.recommended_price_gbp != null &&
            quote.estimated_total_cost_gbp != null;
        });
      });
    case "upsell-economics":
      return cells.some((cell) =>
        cell.offer?.upsells.some((item) =>
          item.publication_eligible && deliveryModes.some(([mode]) => {
            const quote = item.delivery_products[mode];
            return !quote?.available || quote.recommended_price_gbp == null ||
              quote.estimated_total_cost_gbp == null;
          })
        )
      );
    case "supply":
      return cells.some((cell) =>
        (cell.offer?.components ?? []).some(
          (part) =>
            !part.source_observation?.fresh ||
            part.source_observation.stock_status !== "available"
        )
      );
    case "upsells":
      return cells.some((cell) =>
        cell.offer?.upsells.some(
          // Fit is a deterministic gate; performance evidence is advisory.
          (item) => !item.compatibility_verified
        )
      );
    case "media":
    case "assets":
      return cells.some((cell) =>
        (cell.offer?.components ?? []).some((part) => part.media_ready !== true)
      );
    case "performance":
      // Component benchmark scores are explanatory and advisory, not a gate.
      return false;
    case "live":
      // Offline is a valid planned state. Flag only a contradictory state where
      // checkout is enabled even though the cell has not been published.
      return cells.some((cell) => !cell.is_live && cell.checkout_enabled);
    case "approvals":
      return cells.some(
        (cell) => cell.proposal_status === "pending" || !!cell.offer?.blockers.length
      );
    case "distribution":
      return includeUnassignedDistribution && !!(
        book?.unassigned_channel_records || book?.unassigned_distribution?.length
      );
    case "compatibility":
      return cells.some((cell) => cell.offer && !cell.offer.compatibility.verified);
    case "software":
      // Cells without a separate profile use their reviewed customer-type default.
      return false;
    case "history":
    case "automation":
      return false;
  }
}

export default function PlaybookBook({
  refreshKey,
  onEdit,
  renderTools,
}: Props) {
  const [mediaCell, setMediaCell] = useState<BookCell | null>(null);
  const [book, setBook] = useState<BookData | null>(null);
  const [page, setPage] = useState<BookPage>("build");
  const [selected, setSelected] = useState<string | null>(null);
  const [density, setDensity] = useState<"compact" | "detailed">("compact");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [customer, setCustomer] = useState("all");
  const detailRef = useRef<HTMLElement>(null);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setBook(await api.commercialReadiness.book());
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not load operational Playbook"
      );
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    setPage(bookPage(query.get("slice")));
    setSelected(query.get("cell"));
    if (query.get("detail") === "1") setDensity("detailed");
  }, []);
  useEffect(() => {
    void load();
  }, [load, refreshKey]);
  const selectPage = (next: BookPage) => {
    setPage(next);
    updateUrl(next, selected, density);
  };
  const selectCell = (id: string | null) => {
    setSelected(id);
    updateUrl(page, id, density);
  };
  function updateUrl(next: BookPage, id: string | null, view: string) {
    const url = new URL(window.location.href);
    url.searchParams.set("slice", next);
    url.searchParams.set("detail", view === "detailed" ? "1" : "0");
    if (id) url.searchParams.set("cell", id);
    else url.searchParams.delete("cell");
    window.history.replaceState(null, "", url);
  }
  const cells = book?.cells ?? [];
  const customers = [...new Set(cells.map((cell) => cell.customer_type))];
  const tiers = [
    ...new Set([
      "Budget",
      "Mid-range",
      "High-end",
      ...cells.map((cell) => cell.budget_tier),
    ]),
  ];
  const current = cells.find((cell) => cell.cell_id === selected);
  const pageIndex = BOOK_PAGES.findIndex(([id]) => id === page);
  useEffect(() => {
    if (!current || window.location.hash !== "#selected-playbook-cell") return;
    const frame = window.requestAnimationFrame(() =>
      detailRef.current?.scrollIntoView({ block: "start" })
    );
    return () => window.cancelAnimationFrame(frame);
  }, [current, page]);
  return (
    <section aria-label="The Playbook operational book" className="space-y-4">
      {mediaCell && <PlaybookMediaDialog cell={mediaCell} onClose={() => { setMediaCell(null); void load(); }} />}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">The Playbook</h2>
          <p className="text-sm text-slate-400">
            One matrix. Every page shows another view of the same customer type
            × budget cells.
          </p>
          {book && (
            <p className="mt-1 text-xs text-slate-500">
              Read at {new Date(book.observed_at).toLocaleString("en-GB")} ·{" "}
              {cells.length} cells · pending proposals and published records
              labelled separately
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded border border-white/15 px-3 py-2 text-sm disabled:opacity-50"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh Playbook
        </button>
      </header>
      <div className="sticky top-16 z-30 flex flex-wrap items-center gap-3 rounded-xl border border-cyan-400/20 bg-[#101924] p-3">
        <nav aria-label="Playbook pages" className="flex min-w-0 flex-1 flex-wrap gap-2">
          {BOOK_PAGES.map(([id, label], index) => {
            const needsAttention = Boolean(book && pageNeedsAttention(id, cells, book));
            return (
              <button
                key={id}
                type="button"
                aria-current={page === id ? "page" : undefined}
                aria-label={`${index + 1}. ${label}${needsAttention ? ", requires attention" : ""}`}
                title={needsAttention ? `${label} requires attention` : label}
                onClick={() => selectPage(id)}
                className={`rounded-full border px-3 py-1.5 text-xs transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400 ${
                  needsAttention
                    ? "animate-pulse border-red-400 bg-red-500/15 text-red-200"
                    : page === id
                      ? "border-cyan-300 bg-cyan-400 text-slate-950"
                      : "border-white/15 text-slate-300 hover:border-cyan-300/60 hover:text-white"
                }`}
              >
                {label}
              </button>
            );
          })}
        </nav>
        <label className="text-xs text-slate-400">
          Customer type
          <select
            aria-label="Playbook customer type"
            value={customer}
            onChange={(event) => setCustomer(event.target.value)}
            className="ml-2 rounded border border-white/15 bg-[#0b1119] p-2 text-white"
          >
            <option value="all">All customer types</option>
            {customers.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <div role="group" aria-label="Matrix detail" className="flex gap-1">
          {(["compact", "detailed"] as const).map((view) => (
            <button
              key={view}
              type="button"
              aria-pressed={density === view}
              onClick={() => {
                setDensity(view);
                updateUrl(page, selected, view);
              }}
              className={`rounded px-3 py-2 text-xs capitalize ${
                density === view
                  ? "bg-cyan-400 text-slate-950"
                  : "border border-white/15 text-slate-300"
              }`}
            >
              {view}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <div
          role="alert"
          className="rounded border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-200"
        >
          {error} Use Refresh Playbook to retry.
          {book ? " Showing the previous snapshot." : ""}
        </div>
      )}
      {!book && loading ? (
        <p role="status">Loading the operational matrix…</p>
      ) : !cells.length ? (
        <Evidence>
          No Playbook cells loaded. Existing records have not been removed.
        </Evidence>
      ) : (
        <div
          className="max-h-[72vh] overflow-auto rounded-xl border border-white/10"
          tabIndex={0}
          aria-label="Scrollable Playbook matrix"
        >
          <table
            className="w-full min-w-[980px] table-fixed text-left"
            aria-label={`${BOOK_PAGES[pageIndex][1]} matrix`}
          >
            <thead className="sticky top-0 z-20 bg-[#14202d]">
              <tr>
                <th className="sticky left-0 z-30 w-40 bg-[#14202d] p-3 text-xs">
                  Customer type
                </th>
                {tiers.map((tier) => (
                  <th
                    key={tier}
                    scope="col"
                    className="p-3 text-sm text-cyan-200"
                  >
                    {tier}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {customers
                .filter((name) => customer === "all" || name === customer)
                .map((name) => (
                  <tr key={name} className="border-t border-white/10">
                    <th
                      scope="row"
                      className="sticky left-0 z-10 bg-[#101924] p-3 text-sm align-top"
                    >
                      {name}
                    </th>
                    {tiers.map((tier) => {
                      const cell = cells.find(
                        (item) =>
                          item.customer_type === name &&
                          item.budget_tier === tier
                      );
                      const cellNeedsAttention = Boolean(
                        cell && pageNeedsAttention(page, [cell], book, false)
                      );
                      return (
                        <td
                          key={tier}
                          className={`border-l border-white/10 p-3 align-top ${
                            selected === cell?.cell_id
                              ? "bg-cyan-400/10"
                              : "bg-[#0b1119]"
                          }`}
                        >
                          {cell ? (
                            <>
                              <button
                                type="button"
                                aria-label={`Open ${name} ${tier}${cellNeedsAttention ? ", requires attention" : ""}`}
                                aria-pressed={selected === cell.cell_id}
                                onClick={() => {
                                  selectCell(cell.cell_id);
                                  window.setTimeout(
                                    () =>
                                      detailRef.current?.scrollIntoView({
                                        block: "start",
                                        behavior: "auto",
                                      }),
                                    0
                                  );
                                }}
                                className={`mb-2 flex w-full items-start justify-between gap-2 rounded border px-2 py-1.5 text-left text-xs underline underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400 ${
                                  cellNeedsAttention
                                    ? "animate-pulse border-red-400 bg-red-500/15 text-red-200"
                                    : "border-transparent text-cyan-200"
                                }`}
                              >
                                <span>{cell.cell_id}</span>
                                <span
                                  className={
                                    cell.is_live
                                      ? "text-emerald-300"
                                      : "text-amber-300"
                                  }
                                >
                                  {cell.is_live ? "Published" : "Not published"}
                                </span>
                              </button>
                              {cellNeedsAttention && (
                                <a
                                  href={`/pc-builder?tab=playbook&slice=${encodeURIComponent(page)}&cell=${encodeURIComponent(cell.cell_id)}&detail=1#selected-playbook-cell`}
                                  aria-label={`Open ${name} ${tier} on ${BOOK_PAGES[pageIndex][1]} to resolve the issue`}
                                  className="mb-2 inline-flex rounded border border-amber-300/30 px-2 py-1 text-[10px] font-semibold text-amber-200 underline underline-offset-2 hover:bg-amber-300/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-300"
                                >
                                  Resolve this issue
                                </a>
                              )}
                              {cell.offer && <button type="button" onClick={() => setMediaCell(cell)} className="mb-2 block rounded border border-cyan-400/40 px-2 py-1 text-xs text-cyan-200">Photos &amp; 3D models</button>}
                              <p
                                className="mb-2 text-[10px] uppercase tracking-wide text-slate-500"
                                title={`Stored assessment: ${
                                  cell.proposal_observed_at ?? "not recorded"
                                }`}
                              >
                                {text(cell.offer_basis)}
                              </p>
                              {cell.proposal_observed_at &&
                                Date.now() -
                                  new Date(
                                    cell.proposal_observed_at
                                  ).getTime() >
                                  86400000 && (
                                  <p className="mb-2 text-xs text-amber-300">
                                    Assessment over 24 hours old; source checks
                                    need refreshing.
                                  </p>
                                )}
                              <div className="space-y-2">
                                <CellPage
                                  cell={cell}
                                  page={page}
                                  detail={density === "detailed"}
                                />
                              </div>
                            </>
                          ) : (
                            <Evidence>No cell configured.</Evidence>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
      {current && (
        <section
          ref={detailRef}
          id="selected-playbook-cell"
          aria-label="Selected Playbook cell"
          className="scroll-mt-64 space-y-4 rounded-xl border border-cyan-400/30 bg-[#101924] p-4"
        >
          <header className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs text-cyan-300">
                {current.cell_id} · {current.customer_type} ·{" "}
                {current.budget_tier}
              </p>
              <h3 className="text-xl font-semibold">{current.name}</h3>
              <p className="text-sm text-slate-400">
                {BOOK_PAGES[pageIndex][1]} · {text(current.offer_basis)}
              </p>
            </div>
            <button
              type="button"
              onClick={() => selectCell(null)}
              aria-label="Close selected cell"
              className="rounded border border-white/15 p-2"
            >
              <X className="h-4 w-4" />
            </button>
          </header>
          {current.offer && <button type="button" onClick={() => setMediaCell(current)} className="rounded border border-cyan-400/40 px-3 py-2 text-sm text-cyan-200">Photos &amp; 3D models</button>}
          <CellPage cell={current} page={page} detail />
          {(page === "pricing" || page === "approvals") && <PlaybookMarketReview key={current.cell_id} cell={current} onUpdated={() => void load()} />}
          {current.segment_id != null && (
            <button
              type="button"
              onClick={() => onEdit(current.segment_id!)}
              className="rounded border border-cyan-400/40 px-3 py-2 text-sm text-cyan-200"
            >
              Edit this cell’s build and software
            </button>
          )}
          {[
            "approvals",
            "compatibility",
            "supply",
            "software",
            "economics",
            "upsell-economics",
          ].includes(page) && (
            <CommercialReviewWorkspace
              key={`${current.cell_id}:${page}`}
              contextCellId={current.cell_id}
              initialArea={
                page === "compatibility"
                  ? "compatibility"
                  : page === "software"
                  ? "software"
                  : page === "supply"
                  ? "suppliers"
                  : "builds"
              }
              onUpdated={() => void load()}
            />
          )}
          {page === "automation" && <PlaybookAutomationHealth />}
          {renderTools?.(page, current)}
        </section>
      )}
      {page === "pricing" && Boolean(book?.build_market_references?.length) && (
        <details className="rounded-xl border border-amber-400/20 p-4">
          <summary className="cursor-pointer text-sm text-amber-200">
            Build-specific sold evidence requiring cell review (
            {book?.build_market_references?.reduce(
              (total, item) => total + item.observations,
              0
            )}{" "}
            observations)
          </summary>
          <p className="mt-2 text-xs text-slate-400">
            These comparisons belong to individual builds. A Playbook assignment
            alone does not prove an exact specification and condition match for
            cell pricing.
          </p>
          <ul className="mt-3 space-y-2">
            {book?.build_market_references?.map((item) => (
              <li key={item.build_id} className="text-sm">
                <a
                  href={`/builds/${item.build_id}`}
                  className="text-cyan-200 underline"
                >
                  {item.name}
                </a>
                <span className="ml-2 text-xs text-slate-400">
                  {item.observations} observations · latest{" "}
                  {item.last_observed_at
                    ? new Date(item.last_observed_at).toLocaleString("en-GB")
                    : "not recorded"}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
      {page === "distribution" &&
        Boolean(book?.unassigned_distribution?.length) && (
          <details className="rounded-xl border border-amber-400/20 p-4">
            <summary className="cursor-pointer text-sm text-amber-200">
              Recorded channel presence requiring a cell assignment (
              {book?.unassigned_distribution?.length})
            </summary>
            <ul className="mt-3 space-y-3">
              {book?.unassigned_distribution?.map((item, index) => (
                <li
                  key={`${item.channel}:${item.external_id}:${index}`}
                  className="text-sm"
                >
                  <p>
                    {item.title} · {item.channel} · {text(item.status)}
                  </p>
                  <p className="text-xs text-slate-400">
                    {item.assignment_reason} · {item.source} ·{" "}
                    {item.external_id ?? "No listing ID"}
                  </p>
                  <a
                    className="text-xs text-cyan-200 underline"
                    href={
                      item.manual_build_id
                        ? `/builds/${item.manual_build_id}`
                        : "/build-hub"
                    }
                  >
                    Review the build’s Playbook assignment
                  </a>
                </li>
              ))}
            </ul>
          </details>
        )}
      {page === "distribution" && book && (
        <Evidence>
          {book.unassigned_channel_records} channel records have no exact cell
          identity and are not assigned to a budget column. Channel presence is
          a stored record, not a live external poll.
        </Evidence>
      )}
    </section>
  );
}
