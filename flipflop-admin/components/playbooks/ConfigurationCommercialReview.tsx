"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { supplierArrivalEstimate, supplierDisplayLabel } from "@/lib/commercial-readiness";
import type {
  ConfigurationDetail,
  ConfigurationEvidenceSelection,
  ConfigurationReview,
} from "@/lib/commercial-readiness";
import CataloguePriceReview from "@/components/playbooks/CataloguePriceReview";

const modes = [
  ["fast_track", "Fast Track"],
  ["standard", "Standard"],
  ["flexible", "Flexible"],
] as const;

function money(value: string | null | undefined) {
  if (value == null) return "Not calculated";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
  }).format(Number(value));
}

function safeLink(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}

function sourceCanBeReviewed(source: ConfigurationDetail["parts"][number]["source"]) {
  const postageFallback = source?.postage_assumption === "owner-approved-zero-fallback" &&
    Number(source.delivery_gbp) === 0;
  if (!source?.fresh || !source.commercial_capture_verified || source.condition !== "new" ||
      source.delivery_gbp == null || (!source.postage_verified && !postageFallback)) return false;
  const item = Number(source.item_gbp);
  const postage = Number(source.delivery_gbp);
  const freeOfficialDownload = source.evidence_kind === "official_free_software" &&
    source.identity_source === "official_free_software" && source.source === "Ubuntu" &&
    source.stock_status === "available" && item === 0 && postage === 0 &&
    source.delivery_working_days === 0;
  return Boolean(
    Number.isFinite(item) && (item > 0 || freeOfficialDownload) &&
      Number.isFinite(postage) && postage >= 0
  );
}

export default function ConfigurationCommercialReview() {
  const [items, setItems] = useState<ConfigurationReview[]>([]);
  const [detail, setDetail] = useState<ConfigurationDetail | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [confirmedReview, setConfirmedReview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    try {
      const result = await api.commercialReadiness.configurations();
      setItems(result.items);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not load customer configuration reviews"
      );
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const open = async (id: number) => {
    setBusy(true);
    setError("");
    setNotice("");
    setSelected({});
    setConfirmedReview(false);
    try {
      setDetail(await api.commercialReadiness.configuration(id));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not load this exact configuration"
      );
    } finally {
      setBusy(false);
    }
  };

  const selectedSources = (): ConfigurationEvidenceSelection[] =>
    (detail?.parts ?? []).flatMap((part) => {
      const source = part.source;
      if (
        !part.part_key ||
        !source ||
        !selected[part.part_key] ||
        !sourceCanBeReviewed(source)
      ) {
        return [];
      }
      return [
        {
          part_key: part.part_key,
          observation_id: source.observation_id,
          source_fingerprint: source.fingerprint,
        },
      ];
    });

  const importSources = async () => {
    if (!detail || !confirmedReview) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.commercialReadiness.importConfiguration(
        detail,
        selectedSources()
      );
      const updated = await api.commercialReadiness.configuration(
        detail.request_id
      );
      setDetail(updated);
      setSelected({});
      setConfirmedReview(false);
      await refresh();
      setNotice(
        `Recorded ${result.imported} current source fact${result.imported === 1 ? "" : "s"}; ${result.reused} already existed. ${result.blocked.length ? `${result.blocked.length} item${result.blocked.length === 1 ? " remains" : "s remain"} unavailable: ${result.blocked.join("; ")}` : "No customer price or checkout setting changed."}`
      );
    } catch (reason) {
      if (reason instanceof Error && /changed|stale|refresh|capture/i.test(reason.message)) {
        try {
          const latest = await api.commercialReadiness.configuration(detail.request_id);
          setDetail(latest);
          setSelected({});
          setConfirmedReview(false);
          await refresh();
          setNotice("The source capture or configuration changed during review. Latest supplier facts and prices are loaded; select and review the current evidence again.");
          return;
        } catch (reloadReason) {
          setError(`The review data changed and could not be reloaded: ${reloadReason instanceof Error ? reloadReason.message : "unknown error"}`);
          return;
        }
      }
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not record the reviewed supplier facts"
      );
    } finally {
      setBusy(false);
    }
  };

  const approve = async () => {
    if (!detail?.price_review_sha256) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.commercialReadiness.approveConfiguration(
        detail.request_id,
        detail.price_review_sha256
      );
      const updated = await api.commercialReadiness.configuration(
        detail.request_id
      );
      setDetail(updated);
      await refresh();
      setNotice(
        "The exact customer configuration is approved for checkout at the reviewed prices. No catalogue build was published."
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not approve this exact configuration"
      );
    } finally {
      setBusy(false);
    }
  };

  const allModesOfferable = Boolean(
    detail?.assessment &&
      modes.every(([id]) => detail.assessment?.modes[id]?.offerable)
  );
  const canApprove = Boolean(
    detail &&
      !detail.checkout_enabled &&
      detail.draft &&
      !detail.policy_blockers.length &&
      !detail.draft_errors.length &&
      allModesOfferable &&
      detail.price_review_sha256
  );

  return (
    <section
      className="space-y-4 rounded border border-slate-700 p-4"
      aria-label="Customer configuration reviews"
    >
      <div className="flex flex-wrap justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Customer configurations</h2>
          <p className="mt-2 max-w-4xl text-sm text-slate-400">
            Prices and profit are calculated from the exact selected catalogue
            products, current supplier captures and Playbook pricing rules.
            Review the linked supplier facts and approve only when all three
            delivery options pass. There are no price or cost fields to enter.
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => void refresh()}
          className="text-cyan-300 underline"
        >
          Reload requests
        </button>
      </div>

      {error && <p role="alert" className="text-red-300">{error}</p>}
      {notice && <p role="status" className="text-cyan-300">{notice}</p>}

      {!items.length ? (
        <p className="text-sm text-slate-400">
          No exact customer builds are waiting for review. Requests appear here
          when the storefront asks the Playbook service to price a selected
          configuration.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <button
              type="button"
              key={item.request_id}
              disabled={busy}
              onClick={() => void open(item.request_id)}
              aria-pressed={detail?.request_id === item.request_id}
              className="rounded border border-slate-700 p-3 text-left text-sm disabled:opacity-40"
            >
              <strong className="block">
                {item.playbook_name} · {item.curated_build_id ?? "Custom build"}
              </strong>
              <span className="text-slate-400">
                {item.budget_tier ?? "Budget tier needed"} · {item.component_count} selected products · Review #{item.request_id}
              </span>
              <span className="block text-xs text-slate-400">
                {item.checkout_enabled ? "Approved for this exact configuration" : "Needs review"}
              </span>
            </button>
          ))}
        </div>
      )}

      {detail && (
        <div className="space-y-5 border-t border-slate-700 pt-4">
          <div>
            <h3 className="font-semibold">
              {detail.name} · exact configuration #{detail.request_id}
            </h3>
            <p className="mt-1 text-sm text-slate-400">
              The service resolves each component and case from the catalogue.
              Supplier facts below are inputs to pricing, not customer-visible
              stock approvals until you review them.
            </p>
          </div>

          {detail.policy_blockers.length > 0 && (
            <section className="rounded border border-amber-700 p-4" aria-label="Automatic pricing inputs missing">
              <h4 className="font-semibold">The service is waiting on source facts</h4>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-200">
                {detail.policy_blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
              </ul>
            </section>
          )}

          <CataloguePriceReview
            parts={detail.parts}
            total={detail.catalogue_parts_total_gbp}
            blockers={detail.policy_blockers}
          />

          <section className="space-y-3" aria-label="Review exact supplier sources">
            <h4 className="font-semibold">Review the linked supplier pages</h4>
            <p className="text-sm text-slate-400">
              Select only the current exact listings you have checked. Item
              price and availability must be current; captured buying postage
              is used when present, otherwise the approved £0.00 cost fallback
              applies. Supplier arrival time uses its vendor default when the
              listing has no delivery estimate.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400">
                    <th className="p-2">Review</th>
                    <th className="p-2">Selected product</th>
                    <th className="p-2">Current source facts</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.parts.map((part, index) => {
                    const source = part.source;
                    const reviewable = sourceCanBeReviewed(source);
                    const url = source ? safeLink(source.url) : null;
                    const partKey = part.part_key;
                    return (
                      <tr key={part.part_key ?? `${part.role}:${index}`} className="border-b border-slate-800 align-top">
                        <td className="p-2">
                          <input
                            type="checkbox"
                            aria-label={`Review ${part.role} source`}
                            checked={Boolean(partKey && selected[partKey])}
                            disabled={busy || !reviewable || !partKey}
                            onChange={(event) => {
                              if (!partKey) return;
                              setSelected((current) => ({
                                ...current,
                                [partKey]: event.target.checked,
                              }));
                            }}
                          />
                        </td>
                        <td className="min-w-48 p-2">
                          <strong className="block">{part.role}</strong>
                          {part.title}
                          <span className="block text-xs text-slate-500">
                            {part.part_key ?? "Catalogue mapping missing"}
                          </span>
                        </td>
                        <td className="min-w-64 p-2">
                          {source ? (
                            <>
                              <div>{supplierDisplayLabel(source)} · {source.condition}</div>
                              <div>{money(source.item_gbp)} + {source.postage_verified ? money(source.delivery_gbp) : "£0.00 (cost fallback)"} supplier postage</div>
                              <div className="text-xs text-slate-400">
                                {new Date(source.observed_at).toLocaleString("en-GB")} · {source.fresh ? "Current" : "Stale"} · {source.stock_status ?? "Stock unknown"} · {(() => { const arrival=supplierArrivalEstimate(source); return arrival ? `${arrival.days} working days · ${arrival.label}` : "No supplier-specific arrival default available"; })()}
                              </div>
                              {url && <a href={url} target="_blank" rel="noopener noreferrer" className="text-cyan-300 underline">Open exact supplier page</a>}
                              {!reviewable && <p className="text-xs text-amber-300">This capture is not approved for source-based checkout pricing. Missing buying postage is costed at £0.00; source verification remains separate.</p>}
                            </>
                          ) : (
                            <>
                              <span className="text-amber-300">No exact current supplier capture is linked.</span>
                              <span className="block text-xs text-slate-400">
                                {(() => { const arrival=supplierArrivalEstimate({url:part.listing_url ?? undefined}); return arrival ? `${arrival.days} working days · ${arrival.label}` : "No supplier-specific arrival default available"; })()} · Buying postage cost fallback: £0.00.
                              </span>
                            </>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <label className="flex items-start gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={confirmedReview}
                disabled={busy || selectedSources().length === 0}
                onChange={(event) => setConfirmedReview(event.target.checked)}
              />
              <span>I reviewed the selected exact supplier pages and their displayed stock and delivery facts.</span>
            </label>
            <button
              type="button"
              disabled={busy || !confirmedReview || selectedSources().length === 0}
              onClick={() => void importSources()}
              className="rounded border border-cyan-700 px-4 py-2 disabled:opacity-40"
            >
              Record reviewed source facts ({selectedSources().length})
            </button>
          </section>

          <section className="grid gap-3 md:grid-cols-3" aria-label="Calculated exact configuration prices">
            {modes.map(([id, label]) => {
              const result = detail.assessment?.modes[id];
              return (
                <article key={id} className="rounded border border-slate-700 p-4">
                  <h4 className="font-semibold">{label}</h4>
                  <p className="mt-2 text-xl">{money(result?.price_gbp)}</p>
                  <p className="mt-1 text-sm">Estimated profit: {money(result?.contribution_gbp)}</p>
                  <p className="mt-2 text-xs text-slate-400">
                    {id === "flexible" ? "No promised delivery date" : result?.delivery_working_days == null ? "End-to-end delivery estimate not calculated" : `${result.delivery_working_days} working days`} · {result?.reason ?? "The service will recalculate after source review."}
                  </p>
                </article>
              );
            })}
          </section>

          {detail.draft_errors.length > 0 && (
            <ul className="list-disc pl-5 text-sm text-amber-300">
              {detail.draft_errors.map((issue) => <li key={`${issue.field}:${issue.message}`}>{issue.message}</li>)}
            </ul>
          )}

          {detail.checkout_enabled ? (
            <p role="status" className="rounded border border-emerald-700 p-3 text-emerald-300">
              This exact component and case selection is approved for checkout. A different selection needs its own fresh review.
            </p>
          ) : (
            <button
              type="button"
              disabled={busy || !canApprove}
              onClick={() => void approve()}
              className="rounded bg-cyan-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-40"
            >
              Approve the calculated prices for this exact build
            </button>
          )}
        </div>
      )}
    </section>
  );
}
