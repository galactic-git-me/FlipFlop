"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { BrandCubeLoader } from "@/components/ui/brand-cube-loader";
import { supplierArrivalEstimate, supplierDisplayLabel } from "@/lib/commercial-readiness";
import type {
  CompatibilitySecondOpinion,
  DeliveryProduct,
  PlaybookOffer,
  SupplierLicenceCandidate,
} from "@/lib/playbook-proposals";
import ConfigurationCommercialReview from "@/components/playbooks/ConfigurationCommercialReview";
import PlaybookAutomationHealth from "@/components/playbooks/PlaybookAutomationHealth";

const modes = [
  ["fast_track", "Fast Track"],
  ["standard", "Standard"],
  ["flexible", "Flex"],
] as const;
const reviewAreas = [
  ["builds", "Build proposals"],
  ["suppliers", "Listings"],
  ["compatibility", "Compatibility"],
  ["software", "Keys"],
  ["audit", "AUDIT"],
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
function AuditMark({ value }: { value: boolean | null }) {
  if (value === null) return <span aria-label="Not checked" className="inline-block min-w-5 text-center text-slate-600" />;
  return value
    ? <span aria-label="Completed successfully" className="font-bold text-emerald-300">✓</span>
    : <span aria-label="Did not pass" className="font-bold text-red-400">×</span>;
}
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
function postageLabel(part: PlaybookOffer["components"][number]) {
  if (part.source_observation?.postage_verified === true) {
    return money(part.source_observation.delivery_gbp ?? part.supplier_postage_gbp);
  }
  return "£0.00 (cost fallback)";
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
  const [cells, setCells] = useState<Array<{id:string;name:string;segment:string;tier:string;playbook_id:number|null}>>([]);
  const [licenceCandidates, setLicenceCandidates] = useState<
    SupplierLicenceCandidate[]
  >([]);
  const [licencesLoaded, setLicencesLoaded] = useState(false);
  const [licencesLoading, setLicencesLoading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [activeArea, setActiveArea] =
    useState<(typeof reviewAreas)[number][0]>(initialArea);
  const [loading, setLoading] = useState(true);
  const [licenceError, setLicenceError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [compatibilityOpinions, setCompatibilityOpinions] = useState<Record<number, CompatibilitySecondOpinion>>({});
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, cellData] = await Promise.all([
        api.commercialReadiness.proposals(),
        api.playbooks.curatedCells(),
      ]);
      const visible = contextCellId
        ? data.items.filter((item) => item.cell_id === contextCellId)
        : data.items;
      setCells(contextCellId
        ? cellData.items.filter((item) => item.id === contextCellId)
        : cellData.items);
      setOffers(visible);
      setCompatibilityOpinions({});
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
      setLoading(false);
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
  const loadLicences = useCallback(async () => {
    setLicencesLoading(true);
    setLicenceError(null);
    try {
      const licences = await api.commercialReadiness.supplierLicences();
      setLicenceCandidates(
        contextCellId
          ? licences.items.filter((candidate) =>
              candidate.catalogue_statuses.some(
                (link) => link.playbook_id === offers[0]?.playbook_id
              )
            )
          : licences.items
      );
      setLicencesLoaded(true);
    } catch (reason) {
      setLicenceError(reason instanceof Error ? reason.message : "Could not load software supplier listings");
    } finally {
      setLicencesLoading(false);
    }
  }, [contextCellId, offers]);
  useEffect(() => {
    if (activeArea === "software") void loadLicences();
  }, [activeArea, loadLicences]);
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
      toast.success(decision === "approve"
        ? "Build approved and published after all server checks passed."
        : "Build proposal rejected.");
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
      toast.error(reason instanceof Error ? reason.message : "Could not save this build decision");
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
  const offer = offers.find((item) => item.cell_id === selected);
  const segmentGroups = useMemo(
    () => Array.from(offers.reduce((groups, item) => groups.set(item.segment, [
      ...(groups.get(item.segment) || []), item,
    ]), new Map<string, PlaybookOffer[]>())),
    [offers]
  );
  const completeHardwareCount = offers.filter((item) =>
    item.components.filter((part) => !part.role.startsWith("os")).length >= item.required_hardware_count
  ).length;
  const compatibilityCount = offers.filter((item) => item.compatibility.verified).length;
  const auditOffers = cells.map((cell) => ({
    cell,
    offer: offers.find((item) => item.cell_id === cell.id),
  }));
  const auditStatus = (offer: PlaybookOffer | undefined, check: "listings" | "photos" | "model" | "compatibility" | "prices" | "paces" | "keys"): boolean | null => {
    if (!offer) return null;
    const parts = offer.components ?? [];
    const hardware = parts.filter((part) => !part.role.startsWith("os"));
    if (check === "listings") return hardware.length >= offer.required_hardware_count && hardware.every((part) => Boolean(part.listing_id && part.source_url));
    if (check === "photos") {
      if (!hardware.length) return null;
      if (hardware.every((part) => part.photo_ready === true)) return true;
      return hardware.some((part) => part.photo_approval_status === "rejected"
        || (part.photo_approval_status === "approved" && part.photo_ready !== true)) ? false : null;
    }
    if (check === "model") {
      if (!hardware.length) return null;
      if (hardware.every((part) => part.media_ready === true)) return true;
      return hardware.some((part) => ["FAILED", "REJECTED", "CANCELED", "CANCELLED"].includes(String(part.model_generation_status || "").toUpperCase())
        || part.media_preparation_status === "FAILED") ? false : null;
    }
    if (check === "compatibility") {
      const review = compatibilityOpinions[offer.proposal_id] ?? offer.compatibility_review;
      return review?.status === "compatible" ? true
        : review?.status === "review_pending" ? null
        : review ? false : null;
    }
    if (check === "prices") {
      const rows = Object.values(offer.delivery_products ?? {});
      const available = rows.filter((row) => row.available !== false);
      return rows.length > 0 && Boolean(offer.delivery_products.standard?.recommended_price_gbp)
        && available.every((row) => Boolean(row.recommended_price_gbp));
    }
    if (check === "paces") return ["fast_track", "standard", "flexible"].every((mode) => Boolean(offer.delivery_products?.[mode as keyof typeof offer.delivery_products]));
    if (check === "keys") {
      const keys = parts.filter((part) => part.role.startsWith("os"));
      return keys.length ? keys.every((part) => Boolean(part.listing_id && part.source_url)) : null;
    }
    return null;
  };
  const runAuditCompatibility = async (offer: PlaybookOffer) => {
    setBusy(true);
    setError(null);
    setNotice(`Asking the local model to check ${offer.name}…`);
    try {
      const result = await api.commercialReadiness.compatibilitySecondOpinion(offer);
      setCompatibilityOpinions((current) => ({ ...current, [offer.proposal_id]: result }));
      setNotice(`Local compatibility check saved for ${offer.name}: ${result.status.replaceAll("_", " ")}.`);
      await load();
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Could not run the local compatibility check";
      setCompatibilityOpinions((current) => ({
        ...current,
        [offer.proposal_id]: {
          status: "review_unavailable",
          summary: message,
          checks: [],
          authority: "advisory_only",
        },
      }));
      setError(message);
    } finally {
      setBusy(false);
    }
  };
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
              ? loading || error ? "" : ` (${offers.length})`
              : id === "suppliers"
              ? loading || error ? "" : ` (${offers.reduce((count, item) => count + item.components.filter((part) => Boolean(part.listing_id && part.source_url)).length, 0)})`
              : id === "compatibility"
              ? loading || error ? "" : ` (${compatibilityCount}/${offers.length})`
              : id === "software"
              ? !licencesLoaded || licenceError ? "" : ` (${licenceCandidates.length})`
              : ""}
          </button>
        ))}
      </nav>
      {loading ? (
        <div className="flex min-h-[42vh] items-center justify-center rounded border border-slate-800 bg-slate-950/40">
          <BrandCubeLoader size="md" />
        </div>
      ) : error ? (
        <section className="flex min-h-[30vh] flex-col items-center justify-center gap-3 rounded border border-red-900/60 bg-slate-950/40 p-6 text-center">
          <p className="text-slate-300">Playbook review data could not be loaded.</p>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
          >
            Retry loading Playbook data
          </button>
        </section>
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
                                      {part.supplier_offers.map((vendorOffer, vendorOfferIndex) => (
                                        <a
                                          key={`${vendorOffer.url}-${vendorOffer.source}-${vendorOfferIndex}`}
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
                      <p className="text-sm text-slate-300">A linked supplier listing counts as availability evidence. The displayed price and any captured postage are used by the existing Playbook calculations; no separate supplier approval is required.</p>
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
                      <p className="mt-2 text-xs text-slate-400">Ask the local LLM to check the selected parts against their captured specifications. It checks socket fit, AM4 with DDR4, motherboard-to-case fit, and GPU-to-case fit. Missing facts remain unresolved.</p>
                      <button type="button" disabled={busy} onClick={() => void checkCompatibilityWithAI(offer)} className="mt-3 rounded border border-cyan-700 px-3 py-1.5 text-xs text-cyan-200 disabled:opacity-40">Ask local LLM</button>
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
                        <p className="mt-2 text-xs text-amber-200">The saved local compatibility result is checked against the exact proposal facts before publication.</p>
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
          <section aria-label="Supplier listings" hidden={activeArea !== "suppliers"} className="space-y-4">
            <div>
              <h2 className="font-semibold">Linked component listings</h2>
              <p className="mt-1 max-w-4xl text-sm text-slate-400">A linked supplier listing is the availability evidence for the component. Captured prices, postage and arrival are shown as recorded; this view does not ask for a separate supplier approval.</p>
            </div>
            <div className="overflow-x-auto rounded border border-slate-700">
              <table className="w-full min-w-[800px] text-left text-sm">
                <thead className="bg-slate-950 text-xs uppercase text-slate-400"><tr><th className="p-3">Segment</th><th className="p-3">Component listing</th><th className="p-3">Listing price</th><th className="p-3">Availability evidence</th><th className="p-3">Captured</th></tr></thead>
                <tbody>{offers.flatMap((item) => item.components.map((part) => ({ item, part }))).map(({ item, part }) => (
                  <tr key={`${item.cell_id}:${part.role}:${part.listing_id}`} className="border-t border-slate-800">
                    <td className="p-3">{item.name}</td>
                    <td className="p-3"><span className="mr-2 text-xs uppercase text-slate-500">{part.role}</span><a href={sourceLink(part.source_observation?.url || part.source_url)} target="_blank" rel="noopener noreferrer" className="text-emerald-300">{part.title}</a></td>
                    <td className="p-3">{money(part.listing_price_gbp)}</td>
                    <td className="p-3 text-slate-300">{part.listing_id && part.source_url ? "Supplier listing linked" : "No listing linked"}</td>
                    <td className="p-3 text-xs text-slate-400">{part.source_observation?.observed_at ? new Date(part.source_observation.observed_at).toLocaleString("en-GB") : "Not captured"}</td>
                  </tr>
                ))}{offers.length === 0 && <tr><td colSpan={5} className="p-4 text-slate-400">Supplier listings appear here when a Playbook proposal has linked components.</td></tr>}</tbody>
              </table>
            </div>
          </section>
          <section
            aria-label="Compatibility"
            hidden={activeArea !== "compatibility"}
            className="space-y-4"
          >
            <div>
              <h2 className="font-semibold">Compatibility check</h2>
              <p className="mt-1 text-sm text-slate-400">
                The local LLM checks the selected parts against their captured specifications, including AM4 CPU and DDR4 RAM requirements, motherboard fit in the case, and GPU length in the case.
              </p>
            </div>
            {offer ? <div className="rounded border border-slate-700 p-4">
              <h3 className="font-medium">{offer.name}</h3>
              <p className="mt-2 text-sm text-slate-300">{(compatibilityOpinions[offer.proposal_id] ?? offer.compatibility_review)?.summary ?? "No local LLM compatibility check has been recorded for this proposal yet."}</p>
              <button type="button" disabled={busy} onClick={() => void runAuditCompatibility(offer)} className="mt-3 rounded border border-cyan-700 px-3 py-1.5 text-xs text-cyan-200 disabled:opacity-40">Ask local LLM</button>
              {(compatibilityOpinions[offer.proposal_id] ?? offer.compatibility_review)?.checks.map((check, index) => <p key={`${check.pair}:${index}`} className="mt-2 text-sm"><strong>{check.pair.replaceAll("_", " ↔ ")}</strong> · {check.verdict.replaceAll("_", " ")} — {check.explanation}</p>)}
            </div> : <p className="rounded border border-slate-700 p-4 text-sm text-slate-400">Open a segment with a saved proposal to run its compatibility check.</p>}
          </section>
          <section aria-label="Key availability" hidden={activeArea !== "software"} className="space-y-4">
            <div>
              <h2 className="font-semibold">Software key listings</h2>
              <p className="mt-1 max-w-4xl text-sm text-slate-400">This view checks whether supplier listings exist for keys included in a build. Listing presence is the availability evidence. Legal and licensing decisions are outside this workflow.</p>
            </div>
            {licencesLoading && !licencesLoaded ? (
              <div className="flex min-h-[24vh] items-center justify-center rounded border border-slate-800 bg-slate-950/40"><BrandCubeLoader size="sm" /></div>
            ) : licenceError ? (
              <section role="alert" className="rounded border border-red-900/60 p-4 text-red-300">
                Key supplier listings could not be loaded: {licenceError}
                <button type="button" className="ml-3 underline" onClick={() => void loadLicences()}>Retry</button>
              </section>
            ) : licenceCandidates.filter((candidate) => candidate.category === "os").length ? (
              <ul className="grid gap-3 lg:grid-cols-2">
                {licenceCandidates.filter((candidate) => candidate.category === "os").map((candidate) => (
                  <li key={candidate.listing_id} className="rounded border border-slate-700 p-4">
                    <a href={sourceLink(candidate.url)} target="_blank" rel="noopener noreferrer" className="font-medium text-emerald-400">{candidate.title}</a>
                    <p className="mt-2 text-sm text-slate-300">Supplier listing found · {money(candidate.price_gbp)}</p>
                    <p className="mt-1 text-xs text-slate-500">{candidate.supplier_handle || candidate.supplier_name} · captured {candidate.fresh ? "within 24 hours" : "previously"}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="rounded border border-slate-700 p-4 text-slate-400">No Windows key listings are currently captured.</p>
            )}
          </section>
          <section aria-label="Playbook audit" hidden={activeArea !== "audit"} className="space-y-4">
            <div>
              <h2 className="font-semibold">Publication audit by segment</h2>
              <p className="mt-1 text-sm text-slate-400">A tick means the check completed successfully, a red cross means it failed, and a blank means it has not run or does not apply. Listing presence is the availability evidence. Compatibility is checked by the local model against AM4/DDR4, socket, board-to-case fit, and GPU-to-case clearance.</p>
            </div>
            <div className="overflow-x-auto rounded border border-slate-700">
              <table className="w-full min-w-[1120px] border-collapse text-left text-sm">
                <thead className="bg-slate-950 text-xs uppercase tracking-wide text-slate-400">
                  <tr>
                    <th scope="col" className="sticky left-0 z-10 bg-slate-950 p-3">Playbook segment</th>
                    <th scope="col" className="p-3 text-center">Listings / availability</th>
                    <th scope="col" className="p-3 text-center">Photos approved</th>
                    <th scope="col" className="p-3 text-center">3D model approved</th>
                    <th scope="col" className="p-3 text-center">Compatibility</th>
                    <th scope="col" className="p-3 text-center">Price checks</th>
                    <th scope="col" className="p-3 text-center">Pace products</th>
                    <th scope="col" className="p-3 text-center">Keys listed</th>
                    <th scope="col" className="p-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {auditOffers.map(({ cell, offer: auditOffer }) => {
                    const llmResult = auditOffer && (compatibilityOpinions[auditOffer.proposal_id] ?? auditOffer.compatibility_review);
                    const compatStatus = auditStatus(auditOffer, "compatibility");
                    return <tr key={cell.id} className="border-t border-slate-800 hover:bg-slate-900/50">
                      <th scope="row" className="sticky left-0 z-10 bg-slate-950 p-3 font-medium text-slate-200">
                        <span className="block">{cell.name}</span><span className="mt-1 block text-xs font-normal text-slate-500">{cell.segment} · {cell.tier}</span>
                      </th>
                      {(["listings", "photos", "model", "compatibility", "prices", "paces", "keys"] as const).map((key) => (
                        <td key={key} className="p-3 text-center" title={key === "compatibility" ? llmResult?.summary : undefined}>
                          <AuditMark value={auditStatus(auditOffer, key)} />
                        </td>
                      ))}
                      <td className="p-3">
                        {auditOffer ? <div className="flex flex-wrap gap-2">
                          <button type="button" onClick={() => { setSelected(cell.id); setActiveArea("builds"); }} className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">Open segment</button>
                          {compatStatus !== true && <button type="button" disabled={busy} onClick={() => void runAuditCompatibility(auditOffer)} className="rounded border border-cyan-700 px-2 py-1 text-xs text-cyan-200 hover:bg-cyan-950/50 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400">{busy ? "Checking…" : "Ask local LLM"}</button>}
                        </div> : <span className="text-xs text-slate-600">No proposal yet</span>}
                        {llmResult && <p className="mt-2 max-w-xs text-xs text-slate-400">{llmResult.summary}</p>}
                      </td>
                    </tr>;
                  })}
                  {auditOffers.length === 0 && <tr><td colSpan={9} className="p-4 text-slate-400">No Playbook segments are available.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
          {activeArea === "configurations" && <ConfigurationCommercialReview />}
        </>
      )}
    </main>
  );
}
