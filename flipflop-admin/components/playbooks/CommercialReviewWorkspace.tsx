"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { supplierArrivalEstimate, supplierDisplayLabel } from "@/lib/commercial-readiness";
import type {
  CompatibilitySecondOpinion,
  DeliveryProduct,
  PlaybookOffer,
  SupplierLicenceCandidate,
} from "@/lib/playbook-proposals";
import { EngineeringReview } from "@/app/playbooks/commercial/engineering-review";
import ConfigurationCommercialReview from "@/components/playbooks/ConfigurationCommercialReview";
import PlaybookAutomationHealth from "@/components/playbooks/PlaybookAutomationHealth";

const modes = [
  ["fast_track", "Fast Track"],
  ["standard", "Standard"],
  ["flexible", "Flex"],
] as const;
const reviewAreas = [
  ["builds", "Build proposals"],
  ["suppliers", "Supplier listings"],
  ["compatibility", "Compatibility"],
  ["software", "Software licences"],
  ["workshop", "Workshop planning"],
  ["configurations", "Customer configurations"],
] as const;
const money = (value: string | null | undefined) =>
  value == null
    ? "Not calculated"
    : new Intl.NumberFormat("en-GB", {
        style: "currency",
        currency: "GBP",
      }).format(Number(value));
const deliveryPriceLabel = (product: DeliveryProduct | undefined) =>
  !product
    ? "Not calculated"
    : product.available === false
      ? "Unavailable"
      : product.recommended_price_gbp == null
        ? "Not priced"
      : money(product.recommended_price_gbp);
const deliveryProfitLabel = (product: DeliveryProduct | undefined) =>
  !product
    ? "Not calculated"
    : product.available === false
      ? "Not offered"
      : product.estimated_profit_gbp == null
        ? "Not calculated"
      : money(product.estimated_profit_gbp);
function DeliveryTiming({ product }: { product: DeliveryProduct | undefined }) {
  if (product?.workshop_working_days == null) return null;
  const fields = [
    ["Supplier arrival", product.supplier_arrival_working_days],
    ["Workshop queue", product.workshop_wait_working_days],
    ["Build and QA allowance", product.workshop_working_days],
    ["Customer courier", product.courier_working_days],
    ["End-to-end estimate", product.estimated_delivery_working_days],
    ["Customer deadline", product.maximum_delivery_working_days],
  ] as const;
  return (
    <section
      aria-label="Delivery timing breakdown"
      className="mt-3 border-t border-slate-700 pt-3 text-xs"
    >
      <p className="text-slate-400">
        {product.timing_basis === "reviewed_workshop_policy"
          ? "Reviewed workshop timing"
          : "Proposed allowance from the delivery target; review against actual workshop throughput."}{" "}
        All times are working days.
      </p>
      <dl className="mt-2 space-y-1">
        {fields.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-2">
            <dt>{label}</dt>
            <dd>{value ?? "Not confirmed"}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
function sourceLink(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? url.href
      : undefined;
  } catch {
    return undefined;
  }
}
function directRetailProduct(value: string | undefined) {
  try {
    const url = new URL(value || "");
    if (url.protocol !== "https:" || url.username || url.password) return false;
    const host = url.hostname.toLowerCase();
    return (
      ((host === "amazon.co.uk" || host.endsWith(".amazon.co.uk")) &&
        /\/(?:dp|gp\/product)\/[A-Z0-9]{10}(?:\/|$)/i.test(url.pathname)) ||
      ((host === "overclockers.co.uk" ||
        host.endsWith(".overclockers.co.uk")) &&
        (url.pathname.toLowerCase().includes("/product/") ||
          /-[a-z0-9]+-\d{4,}\.html$/i.test(url.pathname) ||
          /^\/[a-z0-9][a-z0-9.-]+\/[a-z]{2,4}-[a-z0-9]{2,6}-[a-z0-9]{2,6}\.html$/i.test(url.pathname)))
    );
  } catch {
    return false;
  }
}
function postageCanBeReviewed(part: PlaybookOffer["components"][number]) {
  // Unknown buying postage has an owner-approved £0 costing fallback. It does
  // not block reviewing the separately captured item, stock and arrival facts.
  return Boolean(part.source_observation);
}
function postageLabel(part: PlaybookOffer["components"][number]) {
  if (part.source_observation?.postage_verified === true) {
    return money(part.source_observation.delivery_gbp ?? part.supplier_postage_gbp);
  }
  return "£0.00 (cost fallback)";
}
function supplierEvidence(offer: PlaybookOffer) {
  return offer.components.flatMap((part) => {
    const fingerprint = part.source_observation?.fingerprint;
    return fingerprint && part.listing_id
      ? [{ role: part.role, listing_id: part.listing_id, fingerprint }]
      : [];
  }).sort((a, b) => a.role.localeCompare(b.role) || a.listing_id - b.listing_id);
}
export default function CommercialReviewWorkspace({
  contextCellId,
  initialArea = "builds",
  onUpdated,
}: {
  contextCellId?: string;
  initialArea?: (typeof reviewAreas)[number][0];
  onUpdated?: () => void;
}) {
  const [offers, setOffers] = useState<PlaybookOffer[]>([]);
  const [licenceCandidates, setLicenceCandidates] = useState<
    SupplierLicenceCandidate[]
  >([]);
  const [licenceAcknowledgements, setLicenceAcknowledgements] = useState<
    Record<number, boolean>
  >({});
  const [selected, setSelected] = useState<string | null>(null);
  const [activeArea, setActiveArea] =
    useState<(typeof reviewAreas)[number][0]>(initialArea);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [compatibilityOpinions, setCompatibilityOpinions] = useState<Record<number, CompatibilitySecondOpinion>>({});
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, licences] = await Promise.all([
        api.commercialReadiness.proposals(),
        api.commercialReadiness.supplierLicences(),
      ]);
      const visible = contextCellId
        ? data.items.filter((item) => item.cell_id === contextCellId)
        : data.items;
      setOffers(visible);
      setCompatibilityOpinions({});
      setLicenceCandidates(
        contextCellId
          ? licences.items.filter((candidate) =>
              candidate.catalogue_statuses.some(
                (link) => link.playbook_id === visible[0]?.playbook_id
              )
            )
          : licences.items
      );
      setLicenceAcknowledgements({});
      setSelected((current) =>
        visible.some((item) => item.cell_id === current)
          ? current
          : visible.find(
              (item) =>
                item.cell_id ===
                new URLSearchParams(window.location.search).get("cell")
            )?.cell_id ??
            visible[0]?.cell_id ??
            null
      );
      return true;
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not load Playbook proposals"
      );
      return false;
    } finally {
      setLoading(false);
    }
  }, [contextCellId]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    setActiveArea(initialArea);
  }, [initialArea]);
  const rebuildCaptured = async () => {
    const started = await api.commercialReadiness.rebuildProposals();
    let job = await api.commercialReadiness.refreshStatus(started.job_id);
    while (job.status === "queued" || job.status === "running") {
      setNotice(`Playbook rebuild: ${job.phase}…`);
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      job = await api.commercialReadiness.refreshStatus(started.job_id);
    }
    if (job.status === "failed")
      throw new Error(job.error || "Playbook proposal rebuild failed");
    const result = job.result;
    if (!result)
      throw new Error(
        "Proposal rebuild finished without a result; inspect the API logs."
      );
    if (!(await load()))
      throw new Error(
        "Proposals rebuilt, but the refreshed review list could not be loaded."
      );
    onUpdated?.();
    return result;
  };
  const reloadCurrentReview = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (await load()) {
        setNotice("Loaded the latest saved Playbook proposal and supplier facts. Check the updated details before reviewing again.");
      }
    } finally {
      setBusy(false);
    }
  };
  const approveLicence = async (candidate: SupplierLicenceCandidate) => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.commercialReadiness.approveSupplierLicence(
        candidate
      );
      await load();
      try {
        const rebuilt = await rebuildCaptured();
        setNotice(
          `${
            candidate.category === "os"
              ? `Reviewed this exact Windows offer and added ${result.activated_catalogue_links} internal OS catalogue candidates.`
              : "Recorded review of this exact supplier product."
          } Rebuilt ${
            rebuilt.cells
          } proposals from stored facts. Prices and products remain unpublished.`
        );
      } catch (reason) {
        setError(
          `Source review was saved, but proposal rebuilding failed: ${
            reason instanceof Error ? reason.message : "unknown error"
          }`
        );
      }
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not review this supplier product"
      );
    } finally {
      setBusy(false);
    }
  };
  const review = async (
    offer: PlaybookOffer,
    decision: "approve" | "reject"
  ) => {
    setBusy(true);
    setError(null);
    try {
      // The scheduled proposal thread may update a cell while this review
      // page is open. Reload the current revision before submitting so a
      // harmless background refresh does not turn the review click into an
      // opaque 409. A changed offer is shown for a fresh human decision.
      const latest = await api.commercialReadiness.proposals();
      const currentOffer = latest.items.find(
        (item) => item.proposal_id === offer.proposal_id
      );
      if (!currentOffer || currentOffer.revision_sha256 !== offer.revision_sha256) {
        await load();
        setNotice(currentOffer
          ? "This proposal changed since it was displayed. The latest build and delivery totals are loaded; review them before deciding."
          : "This proposal is no longer pending. The latest Playbook proposals are loaded.");
        return;
      }
      await api.commercialReadiness.reviewProposal(currentOffer, decision);
      setNotice(
        decision === "approve"
          ? "Exact proposal approved and published after the server repeated publication checks."
          : "Proposal rejected."
      );
      await load();
      onUpdated?.();
    } catch (reason) {
      if (reason instanceof Error &&
          /proposal changed|catalogue products, prices or availability changed|reload before reviewing/i.test(reason.message)) {
        try {
          setError(null);
          await load();
          setNotice("The proposal changed before your decision was saved. The latest proposal is loaded; review its updated parts, source evidence and price before deciding again.");
        } catch (refreshReason) {
          setError(`The proposal changed and could not be reloaded: ${refreshReason instanceof Error ? refreshReason.message : "unknown error"}`);
        }
        return;
      }
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not review this revision"
      );
    } finally {
      setBusy(false);
    }
  };
  const checkCompatibilityWithAI = async (offer: PlaybookOffer) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const latest = await api.commercialReadiness.proposals();
      const currentOffer = latest.items.find(
        (item) => item.proposal_id === offer.proposal_id
      );
      if (!currentOffer || currentOffer.revision_sha256 !== offer.revision_sha256) {
        await load();
        setNotice("This build changed since it loaded. The current proposal is shown; review it and run the compatibility check again.");
        return;
      }
      const result = await api.commercialReadiness.compatibilitySecondOpinion(currentOffer);
      setCompatibilityOpinions(current => ({ ...current, [currentOffer.proposal_id]: result }));
    } catch (reason) {
      if (reason instanceof Error && /proposal changed|reload before reviewing/i.test(reason.message)) {
        await load();
        setNotice("This build changed during the compatibility check. The current proposal is shown; review it and run the check again.");
        return;
      }
      setError(reason instanceof Error ? reason.message : "Could not run the advisory compatibility review");
    } finally {
      setBusy(false);
    }
  };
  const approveSources = async (offer: PlaybookOffer) => {
    setBusy(true);
    setError(null);
    try {
      // A scheduled rebuild can replace this proposal while the operator is
      // reviewing it. Submit the exact supplier fingerprints that were shown;
      // the API imports only facts that still match and leaves changed choices
      // pending, instead of rejecting the whole review on revision churn.
      const latest = await api.commercialReadiness.proposals();
      const currentOffer = latest.items.find(
        (item) => item.proposal_id === offer.proposal_id
      );
      if (!currentOffer) {
        await load();
        setNotice("This proposal is no longer awaiting review. The current Playbook data has been loaded.");
        return;
      }
      // Bind this click to the fingerprints that were on screen. The API
      // imports only matching current captures and reports changed parts as
      // pending, so one changing offer cannot block the rest of the review.
      const result = await api.commercialReadiness.approveSupplierSources(
        currentOffer,
        supplierEvidence(offer)
      );
      await load();
      try {
        const rebuilt = await rebuildCaptured();
        const changed = result.pending_roles.length
          ? ` ${result.pending_roles.length} changed or unavailable component capture(s) remain pending and were not approved.`
          : "";
        const outcome = result.imported || result.reused
          ? `Saved ${result.imported} exact supplier fact${result.imported === 1 ? "" : "s"} for Playbook costing; ${result.reused} already approved.`
          : "No supplier facts were saved because the displayed captures had changed or were unavailable. The current proposals have been reloaded.";
        setNotice(`${outcome}${changed} Rebuilt ${rebuilt.cells} proposals from saved captures; unknown buying postage was costed at £0.00. No customer prices were published.`);
      } catch (reason) {
        setError(
          `Supplier review was saved, but proposal rebuilding failed: ${
            reason instanceof Error ? reason.message : "unknown error"
          }`
        );
      }
    } catch (reason) {
      if (reason instanceof Error && /proposal changed|supplier .*changed|capture .*changed|revision changed|current capture/i.test(reason.message)) {
        try {
          // The current API deliberately binds supplier approval to the
          // displayed (role, listing, capture fingerprint), not the proposal
          // revision. A revision-only conflict is recovered by reloading the
          // latest proposal and comparing exact supplier evidence; unchanged
          // evidence can then be reviewed without losing the click.
          const latest = await api.commercialReadiness.proposals();
          const currentOffer = latest.items.find(item => item.proposal_id === offer.proposal_id);
          if (currentOffer && JSON.stringify(supplierEvidence(currentOffer)) === JSON.stringify(supplierEvidence(offer))) {
            const result = await api.commercialReadiness.approveSupplierSources(currentOffer, supplierEvidence(currentOffer));
            await load();
            setError(null);
            const rebuilt = await rebuildCaptured();
            setNotice(`Saved ${result.imported} exact supplier fact${result.imported === 1 ? "" : "s"}; ${result.reused} already approved. Rebuilt ${rebuilt.cells} proposals from captured data.`);
          } else {
            await load();
            setError(null);
            setNotice("Supplier evidence changed during review. The current listings are loaded; review the updated facts and try again.");
          }
        } catch (refreshReason) {
          setError(`Could not complete supplier review after reloading the current proposal: ${refreshReason instanceof Error ? refreshReason.message : "unknown error"}`);
        }
        return;
      }
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not approve current supplier facts"
      );
    } finally {
      setBusy(false);
    }
  };
  const approveAllSources = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const latest = await api.commercialReadiness.proposals();
      const currentById = new Map(latest.items.map((item) => [item.proposal_id, item]));
      const reviewed = offers.flatMap((shown) => {
        const current = currentById.get(shown.proposal_id);
        return current
          ? [{ ...current, source_evidence: supplierEvidence(shown) }]
          : [];
      });
      if (!reviewed.length) {
        await load();
        setNotice("These proposals are no longer awaiting supplier review. The current Playbook list has been loaded.");
        return;
      }
      const result = await api.commercialReadiness.approveAllSupplierSources(reviewed);
      await load();
      try {
        const rebuilt = await rebuildCaptured();
        setNotice(`Reviewed ${result.proposals} build proposals: ${result.imported} exact supplier facts saved; ${result.reused} already approved; ${result.pending_roles.length} changed or unavailable component captures remain pending${result.skipped_proposals ? `; ${result.skipped_proposals} proposals were no longer pending` : ""}. Rebuilt ${rebuilt.cells} proposals from saved captures; unknown buying postage was costed at £0.00. No prices or products were published.`);
      } catch (reason) {
        setError(
          `Supplier reviews were saved, but proposal rebuilding failed: ${
            reason instanceof Error ? reason.message : "unknown error"
          }`
        );
      }
    } catch (reason) {
      if (reason instanceof Error && /proposal changed|supplier .*changed|capture .*changed|generated proposal set changed/i.test(reason.message)) {
        try {
          const rebuilt = await rebuildCaptured();
          setError(null);
          setNotice(`Supplier evidence changed during the batch review. Refreshed ${rebuilt.cells} proposals from captured data; review the updated facts and try again.`);
        } catch (refreshReason) {
          setError(`Supplier evidence changed, but the captured-data rebuild failed: ${refreshReason instanceof Error ? refreshReason.message : "unknown error"}`);
        }
        return;
      }
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not approve the reviewed supplier facts"
      );
    } finally {
      setBusy(false);
    }
  };
  const offer = offers.find((item) => item.cell_id === selected);
  const segmentGroups = useMemo(
    () =>
      Array.from(
        offers.reduce(
          (groups, item) =>
            groups.set(item.segment, [
              ...(groups.get(item.segment) || []),
              item,
            ]),
          new Map<string, PlaybookOffer[]>()
        )
      ),
    [offers]
  );
  const completeHardwareCount = offers.filter(
    (item) =>
      item.components.filter(
        (part) => part.role !== "os" && part.role !== "os_secondary"
      ).length >= item.required_hardware_count
  ).length;
  const compatibilityCount = offers.filter(
    (item) => item.compatibility.verified
  ).length;
  const reviewableSources =
    offer?.components.filter((part) => {
      const source = part.source_observation;
      return (
        source?.fresh &&
        source.commercial_capture_verified &&
        source.active_listing &&
        source.condition === "new" &&
        source.listing_type === "buy_it_now" &&
        source.stock_status === "available" &&
        Boolean(source.stock_evidence) &&
        postageCanBeReviewed(part) &&
        directRetailProduct(source.url)
      );
    }).length ?? 0;
  const allReviewableSources = Array.from(
    new Map<number, PlaybookOffer["components"][number]>(
      offers
        .flatMap((item) =>
          item.components.filter((part) => {
            const source = part.source_observation;
            return (
              source?.fresh &&
              source.commercial_capture_verified &&
              source.active_listing &&
              source.condition === "new" &&
              source.listing_type === "buy_it_now" &&
              source.stock_status === "available" &&
              Boolean(source.stock_evidence) &&
              postageCanBeReviewed(part) &&
              directRetailProduct(source.url)
            );
          })
        )
        .map((part) => [part.listing_id, part] as const)
    ).values()
  ).sort(
    (a, b) => a.role.localeCompare(b.role) || a.title.localeCompare(b.title)
  );
  return (
    <main className="mx-auto max-w-7xl space-y-6 p-6">
      {!contextCellId && (
        <Link href="/pc-builder" className="text-sm text-slate-400">
          Back to The Playbook
        </Link>
      )}
      <div>
        <h1 className="text-2xl font-semibold">Playbook review</h1>
        <p className="mt-2 max-w-4xl text-slate-400">
          The Playbook assembles builds from catalogue listings and calculates
          component costs, compatibility, delivery prices and estimated profit.
          You review the evidence and proposals here; there are no prices or
          component values to type in.
        </p>
      </div>
      <section
        aria-label="Playbook update automation"
        className="rounded border border-slate-700 p-4"
      >
        <h2 className="font-semibold">Automatic Playbook updates</h2>
        <p className="mt-1 max-w-5xl text-sm text-slate-300">
          There is nothing to click for routine updates. Supplier and
          marketplace capture, demand signals and proposal refresh run on
          schedules. When reconciliation detects a changed price or availability
          fact for a supplier offer you have already reviewed, it queues a
          Playbook recalculation automatically; the queue checks for work every
          minute. Approving new supplier facts also recalculates proposals.
        </p>
        <p className="mt-2 max-w-5xl text-sm text-slate-400">
          Source collection itself is scheduled, so new vendor changes are not
          seen instantly. Automated recalculation never approves new supplier
          facts, approves builds for sale, sets public prices or publishes
          products. Recent paid component choices feed the next proposal cycle
          as a tie-breaker after current source evidence and availability;
          compatibility and your approval remain required. Consented browsing
          sessions are reported separately and are not treated as representative
          sales demand.
        </p>
        <PlaybookAutomationHealth />
        <p className="mt-3 text-sm text-slate-400">
          Photo and 3D reviews are separate approvals:{" "}
          <Link
            href="/pc-builder?tab=images"
            className="text-cyan-300 underline"
          >
            choose listing photos
          </Link>{" "}
          and{" "}
          <Link href="/catalogue/3d-assets" className="text-cyan-300 underline">
            review product models
          </Link>
          .
        </p>
      </section>
      {error && (
        <p
          role="alert"
          className="rounded border border-red-700 p-4 text-red-300"
        >
          {error}
          {/proposal changed|supplier .*changed|capture .*changed|generated proposal set changed|reload before reviewing/i.test(error) && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void reloadCurrentReview()}
              className="ml-3 rounded border border-red-300/50 px-3 py-1 text-sm text-red-100 disabled:opacity-50"
            >
              Reload current proposals
            </button>
          )}
        </p>
      )}
      {notice && (
        <p role="status" className="rounded border border-emerald-700 p-4">
          {notice}
        </p>
      )}
      <nav
        aria-label="Playbook review areas"
        className="flex flex-wrap gap-2 border-b border-slate-700 pb-3"
      >
        {reviewAreas.map(([id, label]) => (
          <button
            key={id}
            type="button"
            aria-pressed={activeArea === id}
            onClick={() => setActiveArea(id)}
            className={`rounded px-4 py-2 text-sm ${
              activeArea === id
                ? "bg-emerald-700 text-white"
                : "border border-slate-700 text-slate-300 hover:bg-slate-800"
            }`}
          >
            {label}
            {id === "builds"
              ? ` (${offers.length})`
              : id === "suppliers"
              ? ` (${allReviewableSources.length})`
              : id === "compatibility"
              ? ` (${compatibilityCount}/${offers.length})`
              : id === "software"
              ? ` (${licenceCandidates.length})`
              : ""}
          </button>
        ))}
      </nav>
      {loading ? (
        <p role="status">Loading Playbook review data…</p>
      ) : (
        <>
          <section
            aria-label="Build proposals"
            hidden={activeArea !== "builds"}
            className="space-y-5"
          >
            <div className="grid gap-3 sm:grid-cols-3">
              <article className="rounded border border-slate-700 p-3">
                <strong className="block text-xl">{offers.length}</strong>
                <span className="text-sm text-slate-400">
                  segment and tier proposals
                </span>
              </article>
              <article className="rounded border border-slate-700 p-3">
                <strong className="block text-xl">
                  {completeHardwareCount}/{offers.length}
                </strong>
                <span className="text-sm text-slate-400">
                  with a complete hardware list
                </span>
              </article>
              <article className="rounded border border-slate-700 p-3">
                <strong className="block text-xl">
                  {compatibilityCount}/{offers.length}
                </strong>
                <span className="text-sm text-slate-400">
                  with verified compatibility
                </span>
              </article>
            </div>
            {offers.length === 0 ? (
              <section className="rounded border border-slate-700 p-6">
                <h2 className="font-semibold">
                  No generated proposals awaiting review
                </h2>
                <p className="mt-2 text-slate-400">
                  The automatic catalogue cycle will assemble proposals when
                  eligible source listings are available. Check the automation
                  status above for its last and next run.
                </p>
              </section>
            ) : (
              <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
                <nav
                  aria-label="Build proposals by segment"
                  className="space-y-3"
                >
                  {segmentGroups.map(([segment, items]) => (
                    <details
                      key={segment}
                      open={items.some((item) => item.cell_id === selected)}
                      className="rounded border border-slate-700"
                    >
                      <summary className="cursor-pointer px-3 py-2 font-semibold">
                        {segment}{" "}
                        <span className="text-xs font-normal text-slate-400">
                          {items.length} proposals
                        </span>
                      </summary>
                      <div className="space-y-2 p-2">
                        {items.map((item) => (
                          <button
                            key={item.cell_id}
                            onClick={() => setSelected(item.cell_id)}
                            aria-pressed={selected === item.cell_id}
                            className={`w-full rounded border p-3 text-left ${
                              selected === item.cell_id
                                ? "border-emerald-500 bg-emerald-950/30"
                                : "border-slate-700"
                            }`}
                          >
                            <strong className="block">{item.tier}</strong>
                            <span className="text-sm text-slate-400">
                              {
                                item.components.filter(
                                  (part) =>
                                    part.role !== "os" &&
                                    part.role !== "os_secondary"
                                ).length
                              }
                              /{item.required_hardware_count} hardware
                              components ·{" "}
                              {item.compatibility.verified
                                ? "compatibility verified"
                                : "compatibility pending"}
                            </span>
                            <span className="mt-1 block text-xs">
                              {item.blockers.length
                                ? `${item.blockers.length} service checks remaining`
                                : "Ready for your review"}
                            </span>
                          </button>
                        ))}
                      </div>
                    </details>
                  ))}
                </nav>
                {offer && (
                  <section className="space-y-5">
                    <div>
                      <h2 className="text-xl font-semibold">{offer.name}</h2>
                      <p className="mt-1 text-slate-400">{offer.description}</p>
                    </div>
                    <section
                      aria-label="Recorded customer demand"
                      className="rounded border border-slate-700 p-4"
                    >
                      <h3 className="font-semibold">Paid storefront orders</h3>
                      <p className="mt-1 text-sm text-slate-300">
                        {offer.storefront_sales?.last_30_days ?? 0} in the last
                        30 days ·{" "}
                        {offer.storefront_sales?.previous_30_days ?? 0} in the
                        prior 30 days. This is observed paid-order volume, not a
                        conversion rate or a market-wide demand estimate.
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        Delivery choices: Fast Track{" "}
                        {offer.storefront_sales?.delivery_options?.fast_track ??
                          0}{" "}
                        · Standard{" "}
                        {offer.storefront_sales?.delivery_options?.standard ??
                          0}{" "}
                        · Flexible{" "}
                        {offer.storefront_sales?.delivery_options?.flexible ??
                          0}
                        {offer.storefront_sales?.last_paid_order_at
                          ? ` · Last paid order ${new Date(
                              offer.storefront_sales.last_paid_order_at
                            ).toLocaleString("en-GB")}`
                          : ""}
                      </p>
                      <p className="mt-3 border-t border-slate-700 pt-3 text-sm text-slate-300">
                        Analytics-consented journey sessions, last 30 days: opened {offer.consented_journey?.view_sessions ?? 0} · configured {offer.consented_journey?.configured_sessions ?? 0} · added to cart {offer.consented_journey?.cart_sessions ?? 0} · began checkout {offer.consented_journey?.checkout_sessions ?? 0}.
                      </p>
                      <p className="mt-1 text-xs text-slate-400">These are separate funnel counts from visitors who accepted analytics. They exclude visitors who declined or have not chosen, so they are not conversion rates.</p>
                    </section>
                    {!!offer.availability_replacements?.length && (
                      <section
                        aria-label="Availability replacements"
                        className="rounded border border-cyan-700/60 bg-cyan-950/20 p-4"
                      >
                        <h3 className="font-semibold text-cyan-200">
                          Suggested replacements for unavailable parts
                        </h3>
                        <p className="mt-1 text-sm text-slate-400">
                          The service selected active catalogue alternatives and is rechecking the complete build before it can be approved.
                        </p>
                        <ul className="mt-3 space-y-3 text-sm">
                          {offer.availability_replacements.map((replacement) => (
                            <li key={`${replacement.role}-${replacement.from_variant_id}`}>
                              <p>
                                <span className="font-medium capitalize">{replacement.role}</span>: {replacement.from_title || "Previous part"} → {replacement.to_title}
                              </p>
                              <p className="mt-1 text-xs text-slate-400">
                                {replacement.reason} Old catalogue status: {replacement.from_catalogue_status}; supplier stock: {replacement.from_stock_status || "unconfirmed"}.
                              </p>
                            </li>
                          ))}
                        </ul>
                      </section>
                    )}
                    {offer.blockers.length > 0 && (
                      <section
                        aria-label="Service work remaining"
                        className="rounded border border-amber-700 p-4"
                      >
                        <h3 className="font-semibold">
                          The service must finish these checks
                        </h3>
                        <p className="mt-1 text-sm text-slate-400">
                          These are data collection and implementation tasks,
                          not requests for you to enter values. This build
                          cannot be approved for sale yet.
                        </p>
                        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
                          {offer.blockers.map((message) => (
                            <li key={message}>{message}</li>
                          ))}
                        </ul>
                      </section>
                    )}
                    <div className="grid gap-3 md:grid-cols-3">
                      {modes.map(([id, label]) => (
                        <article
                          key={id}
                          className="rounded border border-slate-700 p-4"
                        >
                          <h3 className="font-semibold">{label}</h3>
                          <p className="mt-2 text-xl">
                            {deliveryPriceLabel(offer.delivery_products[id])}
                          </p>
                          <p className="mt-1 text-sm">
                            Estimated profit:{" "}
                            {deliveryProfitLabel(offer.delivery_products[id])}
                          </p>
                          <p className="mt-2 text-xs text-slate-400">
                            {offer.delivery_products[id]?.reason}
                          </p>
                          {(offer.delivery_products[id]?.postage_assumptions?.length ?? 0) > 0 && (
                            <p className="mt-2 text-xs text-amber-200">
                              Missing supplier postage is costed at £0.00 for: {offer.delivery_products[id]?.postage_assumptions?.join(", ")}.
                            </p>
                          )}
                          <DeliveryTiming
                            product={offer.delivery_products[id]}
                          />
                        </article>
                      ))}
                    </div>
                    <section
                      aria-label="Source listing prices"
                      className="overflow-x-auto rounded border border-slate-700"
                    >
                      <table className="w-full text-left text-sm">
                        <thead>
                          <tr className="border-b border-slate-700">
                            <th className="p-3">Component and source</th>
                            <th className="p-3">
                              Stock or download and delivery evidence
                            </th>
                            <th className="p-3">Item / licence cost</th>
                            <th className="p-3">Supplier postage</th>
                          </tr>
                        </thead>
                        <tbody>
                          {offer.components.map((part) => {
                            const source = part.source_observation;
                            const freeSoftware =
                              source?.evidence_kind ===
                              "official_free_software";
                            return (
                              <tr
                                key={part.role}
                                className="border-b border-slate-800"
                              >
                                <td className="p-3">
                                  <span className="block text-xs uppercase text-slate-400">
                                    {part.role}
                                  </span>
                                  <a
                                    href={sourceLink(part.source_url)}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-emerald-400"
                                  >
                                    {part.title}
                                  </a>
                                  {part.amazon_listing_url && part.asin && (
                                    <a
                                      href={sourceLink(part.amazon_listing_url)}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="mt-1 block text-xs text-cyan-300"
                                    >
                                      Amazon bestseller listing · ASIN {part.asin}
                                    </a>
                                  )}
                                  {!!part.supplier_offers?.length && (
                                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs">
                                      <span className="text-slate-400">Matched vendor listings:</span>
                                      {part.supplier_offers.map((vendorOffer) => (
                                        <a
                                          key={`${vendorOffer.url}-${vendorOffer.source}`}
                                          href={sourceLink(vendorOffer.url)}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-emerald-300"
                                          title={`${vendorOffer.title} · ${vendorOffer.stock_status || "stock unconfirmed"}`}
                                        >
                                          {vendorOffer.source || "Vendor"} · {money(vendorOffer.item_gbp)}
                                        </a>
                                      ))}
                                    </div>
                                  )}
                                  {part.media_ready === false && (
                                    <p className="mt-1 text-xs text-amber-300">
                                      Not live: {part.not_live_reason}. No
                                      media-ready substitute passed selection.
                                    </p>
                                  )}
                                  <span className="mt-1 block text-xs text-slate-400">
                                    {source
                                      ? `${supplierDisplayLabel({
                                          source: source.source,
                                          url: source.url,
                                        })} · ${
                                          source.condition ||
                                          "condition unconfirmed"
                                        }`
                                      : "Supplier unconfirmed"}{" "}
                                    ·{" "}
                                    {part.catalogue_approved
                                      ? "Catalogue approved"
                                      : "Included in this catalogue review"}{" "}
                                    ·{" "}
                                    {part.price_observed_at
                                      ? new Date(
                                          part.price_observed_at
                                        ).toLocaleString("en-GB")
                                      : "Capture date unavailable"}
                                  </span>
                                  {part.performance_evidence && (
                                    <span className="mt-1 block text-xs text-slate-400">
                                      {part.performance_evidence.model}{" "}
                                      benchmark ·{" "}
                                      {
                                        part.performance_evidence
                                          .benchmark_source
                                      }{" "}
                                      ·{" "}
                                      {part.performance_evidence
                                        .overall_score ??
                                        "Score unavailable"}{" "}
                                      overall
                                      {part.performance_comparison
                                        ? ` · ${
                                            part.performance_comparison
                                              .meets_or_exceeds
                                              ? "meets or exceeds"
                                              : "does not meet"
                                          } this cell's ${
                                            part.performance_comparison.baseline
                                              .model
                                          } target`
                                        : ""}
                                    </span>
                                  )}
                                  <span className="mt-1 block text-xs text-slate-400">
                                    Demand signal: {part.cell_paid_orders_90d ?? 0} paid order{part.cell_paid_orders_90d === 1 ? "" : "s"} used this exact part in this build in 90 days · {part.all_cell_paid_orders_90d ?? 0} across curated builds. Popularity only breaks ties after source evidence and availability; it never overrides compatibility or approval.
                                  </span>
                                </td>
                                <td className="p-3 text-xs">
                                  <span className="block">
                                    {freeSoftware
                                      ? "Official download available; no physical stock"
                                      : source?.stock_status === "available"
                                      ? "In stock evidence captured"
                                      : source?.stock_status === "unavailable"
                                      ? "Supplier reports out of stock"
                                      : "Stock unconfirmed"}
                                    {source?.fresh
                                      ? " · captured within 24 hours"
                                      : ""}
                                  </span>
                                  <span className="block text-slate-400">
                                    {source?.stock_evidence ||
                                      "No explicit stock statement"}
                                  </span>
                                  <span className="mt-1 block text-slate-400">
                                    {(() => {
                                      const arrival = supplierArrivalEstimate(
                                        source ?? { url: part.source_url }
                                      );
                                      return freeSoftware
                                        ? "Digital download · no postage"
                                        : arrival
                                        ? `${arrival.days} working days${
                                            source?.delivery_destination
                                              ? ` to ${source.delivery_destination}`
                                              : ""
                                          } · ${arrival.label}`
                                        : "No supplier-specific arrival default available";
                                    })()}
                                    {freeSoftware
                                      ? ""
                                      : ` · ${
                                          source?.postage_verified
                                            ? "postage confirmed"
                                            : "postage not captured; £0 cost fallback used"
                                        }`}
                                  </span>
                                  {source?.source?.toLowerCase().includes("amazon") && <span className="block text-slate-400">
                                    Amazon Prime: {source.prime_eligible === true ? "captured eligible" : source.prime_eligible === false ? "captured not eligible" : "not confirmed; non-Prime default used"}
                                  </span>}
                                </td>
                                <td className="p-3">
                                  {money(part.listing_price_gbp)}
                                </td>
                                <td className="p-3">
                                  {freeSoftware
                                    ? "No postage"
                                    : postageLabel(part)}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </section>
                    <div className="rounded border border-slate-700 p-4">
                      <p className="text-sm text-slate-300">
                        Review real supplier stock from the linked listing. Only
                        fresh, exact-product offers with explicit stock are
                        saved. Captured postage is retained; missing buying
                        postage uses the £0.00 cost fallback and is not treated
                        as free-delivery evidence.
                      </p>
                      <button
                        disabled={busy || reviewableSources === 0}
                        onClick={() => void approveSources(offer)}
                        className="mt-3 rounded border border-emerald-500/50 px-4 py-2 text-sm text-emerald-300 disabled:opacity-40"
                      >
                        Approve {reviewableSources} supplier cost record
                        {reviewableSources === 1 ? "" : "s"}
                      </button>
                    </div>
                    <details className="rounded border border-slate-700 p-4">
                      <summary>
                        Case choices and component alternatives (
                        {offer.case_choices.length} cases,{" "}
                        {offer.upsells.length} alternatives)
                      </summary>
                      <ul className="mt-3 space-y-2 text-sm">
                        {offer.upsells.map((item) => (
                          <li
                            key={`${item.role}:${item.component.variant_id}`}
                            className="rounded border border-slate-800 p-3"
                          >
                            <strong>{item.role}: </strong>
                            {item.component.title} ·{" "}
                            {money(item.component.listing_price_gbp)} ·{" "}
                            {item.compatibility_verified
                              ? "Fit checks passed"
                              : "Fit evidence pending"}{" "}
                            ·{" "}
                            {item.quality_verified
                              ? "performance evidence passed"
                              : "performance evidence pending"}{" "}
                            ·{" "}
                            {item.publication_eligible
                              ? "eligible for this Playbook approval"
                              : "not eligible for publication"}
                            <dl className="mt-2 grid gap-2 text-xs sm:grid-cols-3">
                              {modes.map(([mode, label]) => {
                                const quote = item.delivery_products[mode];
                                return (
                                  <div key={mode}>
                                    <dt className="text-slate-400">{label}</dt>
                                    <dd>
                                      Proposed total {money(quote?.recommended_price_gbp)}
                                      {quote?.estimated_profit_gbp != null
                                        ? ` · estimated contribution ${money(quote.estimated_profit_gbp)}`
                                        : " · profit unavailable"}
                                    </dd>
                                    <dd className="text-slate-500">
                                      {mode === "flexible" ? "No promised delivery date" : quote?.delivery_working_days != null || quote?.estimated_delivery_working_days != null
                                        ? `Estimated ${quote.delivery_working_days ?? quote.estimated_delivery_working_days} working days end to end`
                                        : quote?.reason || "Delivery estimate unavailable"}
                                    </dd>
                                    {quote?.available === false && quote.recommended_price_gbp != null && (
                                      <dd className="text-amber-300">Proposal only; not approved for customer checkout.</dd>
                                    )}
                                  </div>
                                );
                              })}
                            </dl>
                            <p className="mt-2 text-xs text-slate-400">
                              Paid orders using this part: {item.component.cell_paid_orders_90d ?? 0} in this build and {item.component.all_cell_paid_orders_90d ?? 0} across curated builds, over 90 days.
                            </p>
                          </li>
                        ))}
                      </ul>
                    </details>
                    <details className="rounded border border-slate-700 p-4">
                      <summary>Compatibility checks</summary>
                      <p className="mt-2 text-xs text-slate-400">Deterministic checks decide fit. Ask the local or free tier LLM for an evidence based second opinion; it cannot approve or clear a build.</p>
                      <button type="button" disabled={busy} onClick={() => void checkCompatibilityWithAI(offer)} className="mt-3 rounded border border-cyan-700 px-3 py-1.5 text-xs text-cyan-200 disabled:opacity-40">Ask AI to cross-check evidence</button>
                      <ul className="mt-3 space-y-2 text-sm">
                        {offer.compatibility.checks.map((check, index) => (
                          <li key={`${check.code}:${index}`}>
                            {check.severity}: {check.message}
                          </li>
                        ))}
                      </ul>
                      {compatibilityOpinions[offer.proposal_id] && <div role="status" className="mt-3 rounded border border-cyan-900 p-3 text-sm">
                        <p>{compatibilityOpinions[offer.proposal_id].summary}</p>
                        <ul className="mt-2 list-disc space-y-1 pl-5">{compatibilityOpinions[offer.proposal_id].checks.map((check, index) => <li key={index}><strong>{check.pair.replaceAll("_", " ↔ ")}</strong> · {check.verdict.replaceAll("_", " ")}: {check.explanation} <span className="text-xs text-slate-400">({check.evidence.join(", ")} · {check.confidence} confidence)</span></li>)}</ul>
                        <p className="mt-2 text-xs text-amber-200">This LLM assessment is advisory; the source-backed deterministic checks above control publication.</p>
                      </div>}
                    </details>
                    <div className="rounded border border-cyan-800 bg-cyan-950/20 p-4">
                      <p className="font-medium">What this decision means</p>
                      <p className="mt-1 text-sm text-slate-300">
                        This is the final storefront approval. It records your
                        review of this exact revision, publishes this build at
                        its proposed Standard price, publishes only the listed
                        eligible upsells, and enables checkout. Fast Track,
                        Standard and Flex prices are rechecked by the server
                        before publication. The approval is blocked while any
                        source, compatibility, availability or pricing check
                        remains unresolved.
                      </p>
                      <div className="mt-3 flex flex-wrap gap-3">
                        <button
                          disabled={busy || offer.blockers.length > 0}
                          onClick={() => void review(offer, "approve")}
                          className="rounded bg-emerald-600 px-4 py-2 disabled:opacity-40"
                        >
                          Approve & publish this build
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => void review(offer, "reject")}
                          className="rounded border border-slate-600 px-4 py-2 disabled:opacity-40"
                        >
                          Reject proposal
                        </button>
                      </div>
                    </div>
                  </section>
                )}
              </div>
            )}
          </section>
          <section
            aria-label="Supplier listings"
            hidden={activeArea !== "suppliers"}
            className="space-y-5"
          >
            {offers.length === 0 ? (
              <p className="rounded border border-slate-700 p-4 text-slate-400">
                Supplier facts appear here when Playbook proposals have linked
                listings.
              </p>
            ) : (
              <section
                aria-label="All supplier facts for review"
                className="rounded border border-slate-700 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 className="font-semibold">
                      Supplier facts across all {offers.length} builds
                    </h2>
                    <p className="mt-1 max-w-3xl text-sm text-slate-400">
                      Item price, condition and stock come from the linked
                      supplier page. Supplier arrival uses captured data or the
                      saved vendor estimate; missing inbound postage costs £0.00
                      by default. Approval saves source evidence for costing
                      only. It does not approve a customer price or publish a
                      build.
                    </p>
                  </div>
                  <button
                    disabled={busy || allReviewableSources.length === 0}
                    onClick={() =>
                      void (contextCellId && offer
                        ? approveSources(offer)
                        : approveAllSources())
                    }
                    className="rounded border border-emerald-500/50 px-4 py-2 text-sm text-emerald-300 disabled:opacity-40"
                  >
                    Approve all {allReviewableSources.length} reviewed supplier
                    products
                  </button>
                </div>
                <div className="mt-4 max-h-[65vh] overflow-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="sticky top-0 bg-slate-950">
                      <tr className="border-b border-slate-700">
                        <th className="p-2">Product and supplier</th>
                        <th className="p-2">Captured stock</th>
                        <th className="p-2">Item price</th>
                        <th className="p-2">Postage</th>
                        <th className="p-2">Arrival</th>
                        <th className="p-2">Retailer specifications</th>
                      </tr>
                    </thead>
                    <tbody>
                      {allReviewableSources.map((part) => {
                        const source = part.source_observation!;
                        const properties = Object.entries(
                          source.product_properties || {}
                        );
                        return (
                          <tr
                            key={part.listing_id}
                            className="border-b border-slate-800"
                          >
                            <td className="p-2">
                              <span className="block text-xs uppercase text-slate-400">
                                {part.role} ·{" "}
                                {supplierDisplayLabel({
                                  source: source.source,
                                  url: source.url,
                                })}
                              </span>
                              <a
                                href={sourceLink(source.url || part.source_url)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-emerald-400"
                              >
                                {part.title}
                              </a>
                              {part.amazon_listing_url && part.asin && (
                                <a
                                  href={sourceLink(part.amazon_listing_url)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="mt-1 block text-xs text-cyan-300"
                                >
                                  Amazon listing · ASIN {part.asin}
                                </a>
                              )}
                              {!!part.supplier_offers?.length && (
                                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs">
                                  {part.supplier_offers.map((vendorOffer) => (
                                    <a
                                      key={`${vendorOffer.url}-${vendorOffer.source}`}
                                      href={sourceLink(vendorOffer.url)}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-emerald-300"
                                      title={`${vendorOffer.title} · ${vendorOffer.stock_status || "stock unconfirmed"}`}
                                    >
                                      {vendorOffer.source || "Vendor"} · {money(vendorOffer.item_gbp)}
                                    </a>
                                  ))}
                                </div>
                              )}
                            </td>
                            <td className="p-2 text-xs">
                              {source.stock_evidence}
                              {source.capture_refresh_warning && (
                                <span className="mt-1 block text-amber-300">
                                  Latest refresh could not retrieve the page;
                                  showing the last captured evidence.
                                </span>
                              )}
                              <span className="mt-1 block text-slate-400">
                                {source.condition} ·{" "}
                                {source.fresh
                                  ? "captured within 24 hours"
                                  : "stale"}
                              </span>
                            </td>
                            <td className="p-2">
                              {money(part.listing_price_gbp)}
                            </td>
                            <td className="p-2">
                              {postageLabel(part)}
                            </td>
                            <td className="p-2 text-xs">
                              {(() => {
                                const arrival = supplierArrivalEstimate(
                                  source ?? { url: part.source_url }
                                );
                                return arrival
                                  ? `${arrival.days} working days${
                                      source?.delivery_destination
                                        ? ` to ${source.delivery_destination}`
                                        : ""
                                    } · ${arrival.label}`
                                  : "Supplier URL unavailable for vendor ETA default";
                              })()}
                            </td>
                            <td className="p-2 text-xs">
                              {properties.length > 0 ? (
                                <details>
                                  <summary>
                                    Show {properties.length} captured specs
                                  </summary>
                                  <dl className="mt-2 space-y-1">
                                    {properties.map(([name, value]) => (
                                      <div key={name}>
                                        <dt className="inline text-slate-400">
                                          {name}:{" "}
                                        </dt>
                                        <dd className="inline">
                                          {String(value)}
                                        </dd>
                                      </div>
                                    ))}
                                  </dl>
                                  <p className="mt-2 text-slate-400">
                                    These retailer fields are source data, not
                                    yet approved compatibility specs.
                                  </p>
                                </details>
                              ) : (
                                "Not shown by retailer"
                              )}
                            </td>
                          </tr>
                        );
                      })}
                      {allReviewableSources.length === 0 && (
                        <tr>
                          <td colSpan={6} className="p-3 text-slate-400">
                            No fresh exact supplier facts currently meet the
                            review requirements.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </section>
          <section
            aria-label="Compatibility"
            hidden={activeArea !== "compatibility"}
            className="space-y-4"
          >
            <div>
              <h2 className="font-semibold">Compatibility evidence</h2>
              <p className="mt-1 text-sm text-slate-400">
                Review source-backed component specifications and engineering
                checks here. A catalogue listing by itself does not prove that
                parts fit together.
              </p>
            </div>
            <EngineeringReview
              listingIds={
                contextCellId
                  ? [
                      ...(offer?.components ?? []),
                      ...(offer?.upsells.map((item) => item.component) ?? []),
                    ].map((part) => part.listing_id)
                  : undefined
              }
              boardTitles={
                contextCellId
                  ? [
                      ...(offer?.components ?? []),
                      ...(offer?.upsells.map((item) => item.component) ?? []),
                    ]
                      .filter((part) => part.role === "motherboard")
                      .map((part) => part.title)
                  : undefined
              }
              onApproved={async () => {
                await rebuildCaptured();
              }}
            />
          </section>
          <section
            aria-label="Software licences"
            hidden={activeArea !== "software"}
            className="space-y-4"
          >
            {licenceCandidates.length > 0 ? (
              <section
                aria-label="Software supplier source review"
                className="space-y-4 rounded border border-amber-700/70 p-4"
              >
                <div>
                  <h2 className="font-semibold">
                    Windows, Office and Google AI offers to review
                  </h2>
                  <p className="mt-1 max-w-4xl text-sm text-slate-400">
                    Exact product pages captured from the selected software
                    suppliers. Review the product page,
                    region/activation conditions and supplier terms. A Windows
                    approval may add an internal OS catalogue candidate. Office
                    and Google AI approvals only record source review; they do
                    not add the product to a segment, set its selling price,
                    establish entitlement or resale rights, publish it, or
                    enable checkout.
                  </p>
                </div>
                <ul className="grid gap-3 lg:grid-cols-2">
                  {licenceCandidates.map((candidate) => (
                    <li
                      key={candidate.listing_id}
                      className="space-y-3 rounded border border-slate-700 p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <a
                            href={sourceLink(candidate.url)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-emerald-400"
                          >
                            {candidate.title}
                          </a>
                          <p className="mt-1 text-xs text-slate-400">
                            {candidate.category === "os"
                              ? "Windows licence"
                              : candidate.category === "office"
                              ? "Microsoft Office"
                              : "Google AI subscription"}{" "}
                            ·{" "}
                            {candidate.supplier_handle || "Exact supplier page"}{" "}
                            ·{" "}
                            {candidate.fresh
                              ? "captured within 24 hours"
                              : "capture is stale"}{" "}
                            ·{" "}
                            {candidate.stock_status === "available"
                              ? "supplier reports available"
                              : candidate.stock_status === "unavailable"
                              ? "supplier reports unavailable"
                              : "stock not confirmed"}
                          </p>
                        </div>
                        <strong>{money(candidate.price_gbp)}</strong>
                      </div>
                      <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
                        {Object.entries(candidate.product_properties).map(
                          ([name, value]) => (
                            <div key={name}>
                              <dt className="inline text-slate-400">
                                {name}:{" "}
                              </dt>
                              <dd className="inline">{String(value)}</dd>
                            </div>
                          )
                        )}
                      </dl>
                      {candidate.seller_product_claims && (
                        <details className="text-xs">
                          <summary>Supplier’s product claims</summary>
                          <p className="mt-2 whitespace-pre-wrap text-slate-300">
                            {candidate.seller_product_claims}
                          </p>
                        </details>
                      )}
                      <p className="text-xs text-slate-400">
                        OS catalogue links:{" "}
                        {candidate.catalogue_statuses.length
                          ? candidate.catalogue_statuses
                              .map((row) => row.status)
                              .join(", ")
                          : "none"}
                      </p>
                      <a
                        href={sourceLink(candidate.terms_url)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-emerald-400"
                      >
                        Read {candidate.supplier_name} terms
                      </a>
                      {candidate.licence_source_reviewed ? (
                        <p role="status" className="text-sm text-emerald-300">
                          Exact source review recorded.{" "}
                          {candidate.category === "os"
                            ? "The OS candidate still needs separate build, selling-price and publication approval."
                            : "Not attached to any Playbook segment or customer offer."}
                        </p>
                      ) : (
                        <>
                          <label className="flex items-start gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={
                                licenceAcknowledgements[
                                  candidate.listing_id
                                ] === true
                              }
                              onChange={(event) =>
                                setLicenceAcknowledgements((current) => ({
                                  ...current,
                                  [candidate.listing_id]: event.target.checked,
                                }))
                              }
                            />
                            <span>
                              I reviewed this exact supplier listing and its
                              terms. I understand this does not establish
                              independent entitlement or resale authorization.
                            </span>
                          </label>
                          <button
                            disabled={
                              busy ||
                              !candidate.fresh ||
                              !candidate.licence_review_fingerprint ||
                              !licenceAcknowledgements[candidate.listing_id]
                            }
                            onClick={() => void approveLicence(candidate)}
                            className="rounded border border-amber-500/70 px-3 py-2 text-sm disabled:opacity-40"
                          >
                            Review this source for Playbook consideration
                          </button>
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            ) : (
              <p className="rounded border border-slate-700 p-4 text-slate-400">
                No Windows, Office or Google AI supplier offers are awaiting
                source review.
              </p>
            )}
          </section>
          <section
            aria-label="Workshop planning"
            hidden={activeArea !== "workshop"}
            className="space-y-4"
          >
            <div>
              <h2 className="font-semibold">Workshop planning</h2>
              <p className="mt-1 text-sm text-slate-400">
                There is no concurrent-build sales cap and no weekly build
                count to enter. Delivery prices use current supplier arrival
                evidence and the reviewed work, QA and courier allowances. The
                Workshop Calendar organises paid builds by deadline, delivery
                priority and parts readiness for your daily review.
              </p>
              <Link href="/orders" className="mt-3 inline-flex rounded border border-cyan-700 px-3 py-2 text-sm text-cyan-200 hover:bg-cyan-950/40">
                Open Workshop Calendar
              </Link>
            </div>
          </section>
          {activeArea === "configurations" && <ConfigurationCommercialReview />}
        </>
      )}
    </main>
  );
}
