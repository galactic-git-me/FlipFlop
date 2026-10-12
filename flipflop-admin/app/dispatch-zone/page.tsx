"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type Row = Awaited<ReturnType<typeof api.dispatch.list>>[number];
type AppItem = Awaited<ReturnType<typeof api.dispatch.softwareCatalogue>>["items"][number];
type PlaybookCell = Awaited<ReturnType<typeof api.playbooks.curatedCells>>["items"][number];
type Generated = Record<string, unknown>;
type ResearchTopic = "driver_firmware" | "manual" | "rgb" | "software" | "compatibility";
type ResearchSource = {component_name: string; topic: ResearchTopic; source_url: string; publisher: string; title: string; accessed_at: string; claim: string; operator_approved: boolean};
type ResearchSuggestion = {title: string; source_url: string; publisher: string};
type CachedManualMatch = {manual_id: number; component_key: string; component_name: string; source_url: string; filename: string; sha256: string; size_bytes: number};
const hasPhysicalHandover = (row: Row) => row.has_physical_handover || row.dispatch_status === "dispatched" || row.dispatch_status === "delivered";
const blankResearchSource = (): ResearchSource => ({component_name: "", topic: "driver_firmware", source_url: "", publisher: "", title: "", accessed_at: "", claim: "", operator_approved: false});

function ReviewedManualUploader({
  buildId,
  source,
  componentVerified,
  onSaved,
}: {
  buildId: number;
  source: ResearchSource;
  componentVerified: boolean;
  onSaved: (manual: CachedManualMatch) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const canUpload = source.topic === "manual"
    && componentVerified
    && source.operator_approved
    && source.component_name.trim().length >= 8
    && source.source_url.startsWith("https://")
    && Boolean(source.publisher.trim() && source.title.trim() && source.accessed_at && source.claim.trim().length >= 8);

  if (source.topic !== "manual") return null;

  const upload = async (file?: File) => {
    if (!file || !canUpload || busy) return;
    if (!window.confirm(`Save this PDF as the active cached manual for build ${buildId}, component “${source.component_name.trim()}”? Confirm you opened and checked the PDF and that it came from the official manufacturer source: ${source.source_url}. Saving an existing model key replaces its current library record.`)) return;
    setBusy(true);
    setMessage(null);
    try {
      const saved = await api.settings.uploadComponentManual({
        component_key: source.component_name.trim(),
        component_name: source.component_name.trim(),
        source_url: source.source_url.trim(),
        file,
        confirm_official_source: true,
      });
      onSaved({
        manual_id: saved.id,
        component_key: saved.component_key,
        component_name: saved.component_name,
        source_url: saved.source_url,
        filename: saved.filename,
        sha256: saved.sha256,
        size_bytes: saved.size_bytes,
      });
      setMessage(`Saved to the shared manual library · SHA-256 ${saved.sha256}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save this manual.");
    } finally {
      setBusy(false);
    }
  };

  return <div className="mt-3 rounded border border-slate-700 p-2 md:col-span-2">
    <label className="block text-[10px] text-slate-400">Upload the manually downloaded, reviewed PDF to the shared exact-model library
      <input type="file" accept="application/pdf,.pdf" disabled={!canUpload || busy} onChange={event => { void upload(event.currentTarget.files?.[0]); event.currentTarget.value = ""; }} className="mt-2 block w-full text-[10px] text-slate-400 file:mr-2 file:rounded file:border-0 file:bg-slate-700 file:px-2 file:py-1 file:text-slate-100 disabled:opacity-50" />
    </label>
    {!canUpload && <p className="mt-2 text-[10px] text-slate-500">Search this exact build component first, then complete and approve its source details before uploading the PDF.</p>}
    {message && <p role="status" className="mt-2 break-all text-[10px] text-cyan-200">{message}</p>}
  </div>;
}

function DriverFirmwareOutcomeList({ checklist }: { checklist?: Record<string, unknown> }) {
  const outcomes = checklist?._driver_firmware_outcomes;
  if (!Array.isArray(outcomes) || outcomes.length === 0) return null;
  return <div className="mt-3 rounded-lg border border-violet-400/20 bg-violet-400/5 p-3">
    <p className="text-xs font-semibold text-violet-200">Recorded driver and firmware outcomes</p>
    <ul className="mt-2 space-y-1">{outcomes.map((value, index) => {
      const item = value as {component_name?: string; outcome?: string; source_url?: string | null; details?: string};
      return <li key={`${item.component_name ?? "component"}-${index}`} className="break-words text-[11px] text-slate-300">
        <strong>{item.component_name ?? "Component"}</strong>: {item.outcome === "updated" ? "updated" : "no update applies"} — {item.details}
        {item.source_url && <> · <a href={item.source_url} target="_blank" rel="noreferrer" className="text-cyan-300 underline">reviewed source</a></>}
      </li>;
    })}</ul>
  </div>;
}

const OPERATOR_ACTIONS = [
  ["source_data_complete", "Source data checked"],
  ["customer_selections_locked", "Customer choices locked"],
  ["component_manuals_reviewed", "Component manuals checked and outcomes recorded"],
  ["driver_firmware_reviewed", "Driver and firmware guidance reviewed for every component"],
  ["software_setup", "Selected apps installed"],
  ["usb_verified", "Workshop USB verified"],
  ["machine_setup_run", "Machine setup run"],
  ["windows_target_confirmed", "Intended Windows target drive recorded before package approval and install"],
  ["windows_deployment_completed", "Windows 11 Pro en-GB installed; target drive verified"],
  ["windows_activation_checked", "Windows activation checked"],
  ["drivers_updates_complete", "Drivers and updates complete"],
  ["ai_services_complete", "Paid AI services complete"],
  ["rgb_theme_applied", "RGB and desktop theme applied"],
  ["qa_recheck_passed", "Final QA and benchmarks passed"],
  ["portal_published", "Build portal published"],
  ["leaflet_printed", "Portal leaflet printed"],
] as const;
// Keep this list aligned with app.services.getting_started_jobs.DISPATCH_BLOCKING_ACTIONS.
// Checklist values also contain private audit metadata, so readiness must only
// inspect the explicit server-side dispatch gate keys.
const DISPATCH_BLOCKING_ACTIONS = [
  "source_data_complete",
  "customer_selections_locked",
  "content_manifest",
  "component_manuals_reviewed",
  "driver_firmware_reviewed",
  "artifacts_generated",
  "artifacts_reviewed",
  "customer_package",
  "software_setup",
  "usb_verified",
  "machine_setup_run",
  "windows_target_confirmed",
  "windows_deployment_completed",
  "windows_activation_checked",
  "drivers_updates_complete",
  "ai_services_complete",
  "rgb_theme_applied",
  "qa_recheck_passed",
  "portal_published",
  "leaflet_printed",
  "working_pc_photo",
  "package_contents_photo",
  "sealed_package_photo",
] as const;
const OPTIONAL_CHECKLIST_ACTIONS = new Set(["ai_services_complete", "rgb_theme_applied"]);

export default function DispatchZonePage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [apps, setApps] = useState<AppItem[]>([]);
  const [playbookCells, setPlaybookCells] = useState<PlaybookCell[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"getting-ready" | "delivery" | "evidence">("getting-ready");
  const [segments, setSegments] = useState<Record<number, string>>({});
  const [researchDrafts, setResearchDrafts] = useState<Record<number, ResearchSource[]>>({});
  const [researchSuggestions, setResearchSuggestions] = useState<Record<number, Record<number, ResearchSuggestion[]>>>({});
  const [researchCacheMatches, setResearchCacheMatches] = useState<Record<number, Record<number, CachedManualMatch[]>>>({});
  const [researchVerifiedIdentity, setResearchVerifiedIdentity] = useState<Record<number, Record<number, string>>>({});
  const [researchSearchKey, setResearchSearchKey] = useState<string | null>(null);
  const researchRequestIdentity = useRef<Record<string, string>>({});
  const [generated, setGenerated] = useState<Record<number, Generated>>({});
  const [packages, setPackages] = useState<Record<number, {filename: string; version: number; size_bytes: number; sha256: string; workshop_filename?: string; workshop_size_bytes?: number; workshop_sha256?: string; windows_license_helper_required?: boolean}>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [evidenceMessage, setEvidenceMessage] = useState<Record<number, string>>({});
  const [insuranceQuotes, setInsuranceQuotes] = useState<Record<number, {price_gbp: number; insured_value_gbp: number; currency: string}>>({});
  const [insuranceMessage, setInsuranceMessage] = useState<Record<number, string>>({});
  const [portalClaims, setPortalClaims] = useState<Record<number, {grantId: number; url?: string; guidance: string; directOrder: boolean; emailStatus?: "pending" | "sent" | "failed" | null}>>({});
  const [error, setError] = useState<string | null>(null);
  const soldRows = rows.filter(row => row.status === "sold");
  const load = async () => {
    setLoading(true);
    try { const [builds, catalogue, cells] = await Promise.all([api.dispatch.list(), api.dispatch.softwareCatalogue(), api.playbooks.curatedCells()]); setRows(builds); setPortalClaims(Object.fromEntries(builds.filter(row => row.portal_grant_id).map(row => [row.id, {grantId: row.portal_grant_id!, guidance: "Saved private claim. The raw one-time URL is not retained; download the QR leaflet or issue a fresh claim if needed.", directOrder: Boolean(row.portal_order_id), emailStatus: row.portal_claim_email_status}]))); setResearchDrafts(current => Object.fromEntries(builds.map(row => [row.id, current[row.id] ?? ((row.getting_started?.approved_research_bundle ?? []) as unknown as ResearchSource[]).map(({component_name, topic, source_url, publisher, title, accessed_at, claim, operator_approved}) => ({component_name, topic, source_url, publisher, title, accessed_at, claim, operator_approved}))])) as Record<number, ResearchSource[]>); setApps(catalogue.items); setPlaybookCells(cells.items.filter(cell => cell.playbook_id !== null)); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not load Dispatch Centre."); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  const schedule = async (id: number) => {
    const value = window.prompt("Collection date/time (YYYY-MM-DDTHH:mm)");
    if (!value) return;
    await api.dispatch.setCollectionDate(id, new Date(value).toISOString());
    await load();
  };
  const searchResearchSources = async (id: number, index: number) => {
    const source = researchDrafts[id]?.[index];
    if (!source?.component_name.trim()) { setError("Enter the exact component name from this build before searching."); return; }
    const key = `${id}:${index}`;
    const identity = JSON.stringify([source.component_name.trim(), source.topic]);
    researchRequestIdentity.current[key] = identity;
    setResearchVerifiedIdentity(current => ({...current, [id]: {...(current[id] ?? {}), [index]: ""}}));
    setResearchSearchKey(key); setError(null);
    try {
      const result = await api.dispatch.suggestGettingReadySources(id, source.component_name, source.topic);
      if (researchRequestIdentity.current[key] !== identity) return;
      setResearchVerifiedIdentity(current => ({...current, [id]: {...(current[id] ?? {}), [index]: identity}}));
      setResearchSuggestions(current => ({...current, [id]: {...(current[id] ?? {}), [index]: result.suggestions}}));
      setResearchCacheMatches(current => ({...current, [id]: {...(current[id] ?? {}), [index]: result.cached_manual_matches}}));
    } catch (err) {
      if (researchRequestIdentity.current[key] === identity) {
        setError(err instanceof Error ? err.message : "Could not search for component sources.");
      }
    }
    finally {
      if (researchRequestIdentity.current[key] === identity) {
        setResearchSearchKey(current => current === key ? null : current);
      }
    }
  };
  const clearResearchResults = (id: number, index: number) => {
    delete researchRequestIdentity.current[`${id}:${index}`];
    setResearchSearchKey(current => current === `${id}:${index}` ? null : current);
    setResearchSuggestions(current => ({...current, [id]: {...(current[id] ?? {}), [index]: []}}));
    setResearchCacheMatches(current => ({...current, [id]: {...(current[id] ?? {}), [index]: []}}));
    setResearchVerifiedIdentity(current => ({...current, [id]: {...(current[id] ?? {}), [index]: ""}}));
  };
  const removeResearchDraft = (id: number, index: number) => {
    for (const key of Object.keys(researchRequestIdentity.current)) {
      if (key.startsWith(`${id}:`)) delete researchRequestIdentity.current[key];
    }
    setResearchSuggestions(current => ({...current, [id]: {}}));
    setResearchCacheMatches(current => ({...current, [id]: {}}));
    setResearchVerifiedIdentity(current => ({...current, [id]: {}}));
    setResearchSearchKey(current => current?.startsWith(`${id}:`) ? null : current);
    setResearchDrafts(current => ({...current, [id]: (current[id] ?? []).filter((_, i) => i !== index)}));
  };
  const useResearchSuggestion = (id: number, index: number, suggestion: ResearchSuggestion) => {
    setResearchDrafts(current => ({...current, [id]: (current[id] ?? []).map((item, i) => i === index ? {
      ...item,
      source_url: suggestion.source_url,
      publisher: suggestion.publisher,
      title: suggestion.title,
      accessed_at: "",
      claim: "",
      operator_approved: false,
    } : item)}));
  };
  const generate = async (id: number) => {
    setBusyId(id); setError(null);
    try {
      const row = rows.find(item => item.id === id);
      const cellId = segments[id] || row?.playbook_assignment?.curated_build_id;
      const cell = playbookCells.find(item => item.id === cellId);
      if (!cell?.playbook_id) throw new Error("Choose a valid customer-type × budget cell before generating this Ready-to-Ship package.");
      const research = (researchDrafts[id] ?? []).filter(item => item.operator_approved);
      if (research.some(item => !item.component_name.trim() || !item.source_url.startsWith("https://") || !item.publisher.trim() || !item.title.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(item.accessed_at) || item.claim.trim().length < 8)) throw new Error("Complete each approved source's exact component, HTTPS URL, publisher, title, date and evidence claim.");
      if (research.length > 0 && !window.confirm(`Confirm that you reviewed all ${research.length} source records, that each URL supports its stated claim, and that these primary sources are suitable for this exact build.`)) return;
      const result = await api.dispatch.generateGettingReady(id, {
        playbook_id: cell.playbook_id,
        curated_build_id: cell.id,
        approved_research_bundle: research as unknown as Record<string, unknown>[],
      });
      setGenerated(current => ({ ...current, [id]: result }));
    } catch (err) { setError(err instanceof Error ? err.message : "Content generation failed."); }
    finally { setBusyId(null); }
  };
  const downloadScript = async (row: Row) => {
    setBusyId(row.id); setError(null);
    try { await api.dispatch.downloadSoftwareInstallScript(row.id); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not download the reviewed software script."); }
    finally { setBusyId(null); }
  };
  const approvePackage = async (row: Row) => {
    if (!window.confirm("Confirm that you reviewed the generated manifest and build plaque, exact build specification, benchmark evidence, software choices, driver/manual sources and customer details.")) return;
    const acceptIndirectDefaults = row.getting_started?.order_id == null && row.getting_started?.checklist.software_selection_submitted !== true;
    if (acceptIndirectDefaults && !window.confirm("This indirect-channel buyer has no saved FlipFlop software selection. Confirm that the Playbook-recommended app list is appropriate for this buyer and may be installed on their build.")) return;
    if (!window.confirm("If a Windows 11 Pro key is assigned, the reviewed ZIP will expect a separate activation-helper download from Dispatch Centre. The key will not be stored in the ZIP or sent to AI/customer documents. Continue?")) return;
    if (!window.confirm("Create the versioned customer-documents ZIP and separate workshop USB ZIP now? This creates files only; it does not install software, book delivery or buy insurance.")) return;
    const notes = window.prompt("Optional reviewer notes") || undefined;
    setBusyId(row.id); setError(null);
    try {
      const result = await api.dispatch.approveGettingReadyPackage(row.id, notes, acceptIndirectDefaults);
      setPackages(current => ({ ...current, [row.id]: result }));
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create the reviewed package."); }
    finally { setBusyId(null); }
  };
  const downloadWindowsLicenseHelper = async (row: Row) => {
    if (!window.confirm(`Release the assigned Windows Pro key for ${row.name} to a one-time workshop-helper download? The response is not stored by the service. Keep the downloaded file private; the master setup removes it from the USB folder after successful installation.`)) return;
    setBusyId(row.id); setError(null);
    try { await api.dispatch.downloadWindowsLicenseHelper(row.id); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not download the Windows licence helper."); }
    finally { setBusyId(null); }
  };
  const reconcileInsurancePolicy = async (row: Row) => {
    if (!window.confirm("Check the Figural/Secursus provider account for this build before continuing. Do not retry while the result is unknown.")) return;
    const resolution = window.prompt("After checking, enter policy_exists or no_policy.")?.trim();
    if (resolution !== "policy_exists" && resolution !== "no_policy") return;
    const note = window.prompt("Record what you checked in the insurer account (at least 12 characters).")?.trim();
    if (!note || note.length < 12) return;
    const payload: Parameters<typeof api.dispatch.reconcileInsurancePolicy>[1] = {
      resolution,
      provider_checked: true,
      note,
    };
    if (resolution === "no_policy") {
      if (!window.confirm("Confirm the provider account shows no active policy for this parcel. This clears the uncertain state and permits a new, separately confirmed purchase.")) return;
    } else {
      const providerResponse = row.insurance_provider_response;
      const policyId = window.prompt(
        "Enter the existing provider policy ID and verify it against the insurer account.",
        providerResponse?.policy_id || "",
      )?.trim();
      const providerTracking = window.prompt("Enter the tracking number recorded against that provider policy.", row.tracking_number || "")?.trim();
      const insuredValue = Number(window.prompt(
        "Enter the insured value in GBP and verify it against the insurer account.",
        String(providerResponse?.insured_value_gbp ?? row.sale_price ?? ""),
      ));
      const cost = Number(window.prompt(
        "Enter the policy premium in GBP and verify it against the insurer account.",
        providerResponse?.price_gbp == null ? "" : String(providerResponse.price_gbp),
      ));
      if (!policyId || !providerTracking || !Number.isFinite(insuredValue) || insuredValue <= 0 || !Number.isFinite(cost) || cost < 0) return;
      payload.policy_id = policyId;
      payload.provider_tracking_number = providerTracking;
      payload.invoice_id = window.prompt(
        "Enter the invoice ID if shown, or leave blank.",
        providerResponse?.invoice_id || "",
      )?.trim() || undefined;
      payload.insured_value_gbp = insuredValue;
      payload.cost_gbp = cost;
      if (!window.confirm(`Attach policy ${policyId} for £${insuredValue.toFixed(2)} insured value and £${cost.toFixed(2)} premium to this build?`)) return;
    }
    setBusyId(row.id); setError(null);
    try {
      await api.dispatch.reconcileInsurancePolicy(row.id, payload);
      setEvidenceMessage(current => ({...current, [row.id]: resolution === "no_policy" ? "Provider check recorded; you can request a fresh quote." : "Existing provider policy attached to this build."}));
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not reconcile the insurance policy."); }
    finally { setBusyId(null); }
  };
  const setChecklistAction = async (row: Row, action: string, status: "complete" | "not_required") => {
    if (action === "windows_deployment_completed" || action === "windows_target_confirmed") return;
    let paidAiScopeConfirmed = false;
    let driverFirmwareOutcomes: Array<{component_id: string; component_name: string; outcome: "updated" | "no_update_applicable"; source_url?: string | null; details: string}> | undefined;
    if (action === "ai_services_complete" && status === "complete") {
      const purchases = row.getting_started?.purchased_ai_services ?? [];
      if (purchases.length > 0) {
        if (!window.confirm(`This build has ${purchases.length} paid AI service selection(s). Confirm the customer approved the exact assistant/model, account and data permissions, and that each service was installed and checked according to the Getting Ready runbook.`)) return;
        paidAiScopeConfirmed = true;
      }
    }
    if (action === "driver_firmware_reviewed" && status === "complete") {
      if (!window.confirm("Confirm that every exact component model in the generated list has an outcome recorded, and that each source and any applicable update were reviewed.")) return;
      const currentManifest = generated[row.id]?.manifest as Record<string, unknown> | undefined;
      const manifestRows = (currentManifest ?? row.getting_started?.manifest)?.driver_and_firmware_review;
      if (!Array.isArray(manifestRows) || manifestRows.length === 0) { setError("Generate the component driver/firmware review list first."); return; }
      driverFirmwareOutcomes = [];
      for (const candidate of manifestRows as Array<Record<string, unknown>>) {
        const componentId = String(candidate.component_id ?? "");
        const componentName = String(candidate.component_name ?? "");
        const outcome = window.prompt(`Driver/firmware outcome for ${componentName}: enter updated or no_update_applicable.`)?.trim();
        if (outcome !== "updated" && outcome !== "no_update_applicable") return;
        const sourceUrl = typeof candidate.source_url === "string" ? candidate.source_url : null;
        if (outcome === "updated" && !sourceUrl) { setError(`Add and approve an exact manufacturer source for ${componentName}, then regenerate the manifest before recording an installed update.`); return; }
        const details = window.prompt(outcome === "updated"
          ? `For ${componentName}, record the installed driver/firmware name and version.`
          : `For ${componentName}, explain what you checked and why no update applies.`)?.trim();
        if (!details || details.length < 12) return;
        driverFirmwareOutcomes.push({component_id: componentId, component_name: componentName, outcome, source_url: sourceUrl, details});
      }
    }
    const notePrompt = action === "driver_firmware_reviewed"
      ? "Summarise the per-component outcomes above (at least 12 characters)."
      : status === "complete"
        ? "Required: record what was completed and any useful evidence reference (at least 12 characters)."
        : "Required: explain why this action is not required (at least 12 characters).";
    const note = window.prompt(notePrompt)?.trim();
    if (!note || note.length < 12) return;
    setBusyId(row.id); setError(null);
    try { await api.dispatch.updateChecklist(row.id, action, status, note, undefined, paidAiScopeConfirmed, undefined, driverFirmwareOutcomes); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not update the checklist."); }
    finally { setBusyId(null); }
  };
  const recordWindowsTarget = async (row: Row) => {
    const model = window.prompt("Before approving the workshop package, record the exact model of the new build's intended Windows target drive.")?.trim();
    if (!model) return;
    const serial = window.prompt("Record the target drive's serial number from its label, firmware inventory, or hardware record.")?.trim();
    if (!serial) return;
    if (!window.confirm(`Confirm this is the new build's drive selected for Windows installation:\n\n${model}\nSerial: ${serial}\n\nWindows Setup must still show and let you confirm the intended drive before any partition is deleted.`)) return;
    const note = window.prompt("Required: note how you identified this target drive before installation (at least 12 characters).")?.trim();
    if (!note || note.length < 12) return;
    setBusyId(row.id); setError(null);
    try {
      await api.dispatch.updateChecklist(row.id, "windows_target_confirmed", "complete", note, undefined, false, {
        model, serial, inspected_at_utc: new Date().toISOString(), confirm_new_build_drive: true,
      });
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not record the intended Windows target."); }
    finally { setBusyId(null); }
  };
  const importWindowsEvidence = async (row: Row, file?: File) => {
    if (!file) return;
    setError(null);
    try {
      if (file.size > 64 * 1024) throw new Error("The Windows evidence report must be 64 KB or smaller.");
      const report = JSON.parse(await file.text()) as Record<string, unknown>;
      if (!report || typeof report !== "object" || report.schema_version !== "1.0" || report.build_id !== row.id) {
        throw new Error("Choose the Windows evidence report generated for this build.");
      }
      const model = String(report.target_drive_model || "").trim();
      const serial = String(report.target_drive_serial || "").trim();
      if (!model || !serial) throw new Error("The report is missing the system-drive model or serial.");
      const target = row.getting_started?.checklist.windows_target as {model?: string; serial?: string} | undefined;
      if (!target?.model || !target?.serial) throw new Error("Record the intended target drive before installing Windows.");
      if (target.model.trim().toLowerCase() !== model.toLowerCase() || target.serial.trim().toLowerCase() !== serial.toLowerCase()) {
        throw new Error("The installed system drive does not match the drive recorded before installation.");
      }
      if (!window.confirm(`The installed system drive matches the target recorded before installation:\n\n${model}\nSerial: ${serial}\n\nThis records verification only; it does not install Windows or erase a disk.`)) return;
      const installationMethod = window.prompt("How was Windows installed?")?.trim();
      if (!installationMethod) return;
      const note = window.prompt("Required: record the pre-install target-drive check")?.trim();
      if (!note || note.length < 12) return;
      setBusyId(row.id);
      await api.dispatch.updateChecklist(row.id, "windows_deployment_completed", "complete", note, {
        ...report,
        installation_method: installationMethod,
        target_drive_confirmed: true,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not import the Windows evidence report.");
    } finally {
      setBusyId(null);
    }
  };
  const dispatchBuild = async (row: Row) => {
    if (!window.confirm("Confirm the sealed parcel has physically been handed to the courier. This marks the order Dispatched and sends the customer tracking update.")) return;
    setBusyId(row.id); setError(null);
    try {
      const result = await api.dispatch.markDispatched(row.id);
      if (result.portal_grant_id) {
        setPortalClaims(current => ({
          ...current,
          [row.id]: {
            grantId: result.portal_grant_id!,
            guidance: "Automatic dispatch claim. The one-time URL is not retained here; the private QR leaflet can be printed if email delivery failed.",
            directOrder: true,
            emailStatus: result.portal_claim_email_status,
          },
        }));
      }
      const message = result.warning
        || (result.portal_claim_email_sent === true
          ? "Dispatch recorded; the direct guest portal link and tracking details were emailed."
          : result.portal_claim_email_sent === false
            ? `Dispatch recorded, but the direct guest portal email was not confirmed${result.email_sent ? "; a tracking-only email was sent" : ""}. Include the private QR leaflet and issue a replacement claim if needed.`
            : result.email_sent
              ? "Dispatch recorded and the customer shipment update was sent."
              : "Dispatch recorded. Follow the channel guidance for customer updates.");
      setEvidenceMessage(current => ({ ...current, [row.id]: message }));
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not mark the build dispatched."); }
    finally { setBusyId(null); }
  };
  const uploadEvidence = async (buildId: number, category: "working_pc" | "package_contents" | "sealed_package", file?: File) => {
    if (!file) return;
    setBusyId(buildId); setError(null);
    try {
      const saved = await api.dispatch.uploadEvidence(buildId, category, file);
      setEvidenceMessage(current => ({ ...current, [buildId]: `Saved private evidence (${Math.ceil(saved.size_bytes / 1024)} KB).` }));
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Evidence upload failed."); }
    finally { setBusyId(null); }
  };
  const reviewEvidence = async (row: Row, artifactId: string, approved: boolean) => {
    if (approved && !window.confirm("Confirm you inspected this file and it clearly shows the correct build or packaging stage.")) return;
    const note = window.prompt("Record what you checked (at least 12 characters).")?.trim();
    if (!note || note.length < 12) return;
    setBusyId(row.id); setError(null);
    try {
      await api.dispatch.reviewEvidence(row.id, artifactId, approved, note);
      setEvidenceMessage(current => ({ ...current, [row.id]: approved ? "Evidence reviewed and approved." : "Evidence rejected; upload a suitable replacement." }));
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not review shipment evidence."); }
    finally { setBusyId(null); }
  };
  const downloadEvidence = async (row: Row, artifactId: string, filename: string) => {
    try {
      const blob = await api.dispatch.getEvidenceFile(row.id, artifactId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open shipment evidence.");
    }
  };
  const createPortalClaim = async (row: Row) => {
    const isDirectOrder = Boolean(row.portal_order_id);
    if (isDirectOrder && !row.customer_email) { setError("A verified order email is required for direct guest portal access."); return; }
    const allowedChannels = isDirectOrder
      ? ["direct_guest"]
      : ["ebay", "vinted", "marketplace", "printed_insert"];
    const channelText = window.prompt(
      `Channel: ${allowedChannels.join(", ")}`,
      isDirectOrder ? "direct_guest" : "printed_insert",
    );
    if (!channelText || !allowedChannels.includes(channelText)) return;
    if (channelText === "direct_guest" && !row.portal_order_id) {
      setError("A verified linked direct order is required to send a guest claim by email.");
      return;
    }
    const deliveryNote = channelText === "direct_guest"
      ? `Issue/reissue a one-time portal claim to verified order email ${row.customer_email}?`
      : "Create a one-time claim bound to this build. Print the QR leaflet and include it inside the sealed parcel. Do not send the URL through the marketplace.";
    if (!window.confirm(`${deliveryNote} Any older unclaimed link for this build will be revoked.`)) return;
    setBusyId(row.id); setError(null);
    try {
      const claim = await api.dispatch.createGuestPortalClaim(
        row.id,
        row.portal_order_id ?? null,
        channelText === "direct_guest" ? row.customer_email! : null,
        channelText as "direct_guest" | "ebay" | "vinted" | "marketplace" | "printed_insert",
      );
      setPortalClaims(current => ({ ...current, [row.id]: { grantId: claim.id, url: channelText === "direct_guest" && claim.claim_url ? claim.claim_url : undefined, guidance: claim.delivery_guidance, directOrder: channelText === "direct_guest", emailStatus: claim.email_status } }));
    } catch (err) { setError(err instanceof Error ? err.message : "Could not issue portal access."); }
    finally { setBusyId(null); }
  };
  const quoteInsurance = async (row: Row) => {
    if (!row.sale_price || row.sale_price <= 0) { setError("A confirmed sale value is required for an insurance quote."); return; }
    setBusyId(row.id); setError(null);
    try {
      const quote = await api.manualBuilds.getInsuranceQuote(row.id, row.sale_price);
      setInsuranceQuotes(current => ({ ...current, [row.id]: quote }));
      setInsuranceMessage(current => ({ ...current, [row.id]: `Live quote: £${quote.price_gbp.toFixed(2)} to cover £${quote.insured_value_gbp.toFixed(2)}.` }));
    } catch (err) { setError(err instanceof Error ? err.message : "Could not get the insurer quote."); }
    finally { setBusyId(null); }
  };
  const buyInsurance = async (row: Row) => {
    const quote = insuranceQuotes[row.id];
    if (!quote) return;
    if (!window.confirm("Confirm the PC is protected in new, resistant double packaging inside a rigid outer box; it cannot be identified by touch; and packaging does not reveal its contents or value. Confirm the contents-before-packing and sealed-parcel photos are uploaded.")) return;
    if (!window.confirm("Confirm the package does not disclose the item type/value or display business/website branding; the courier label does not disclose the item type/value; the service has adult/direct signature; and handover is by carrier collection or at an official carrier depot/branch (not a parcel shop or locker).")) return;
    if (!window.confirm("Confirm the insurer terms are reviewed and you are authorised to share the buyer's name, email, delivery address and sale value with the insurer.")) return;
    if (!window.confirm(`This creates a live insurance policy and may charge £${quote.price_gbp.toFixed(2)}. Continue?`)) return;
    setBusyId(row.id); setError(null);
    try {
    const policy = await api.manualBuilds.createInsurancePolicy(row.id, quote.price_gbp, { signedForDelivery: true, doublePackaging: true, discreetPackaging: true, rigidOuterContainer: true, contentsNotDeducible: true, directSignature: true, officialCarrierHandover: true });
      setInsuranceMessage(current => ({ ...current, [row.id]: `Policy ${policy.policy_id || "created"} registered for £${(policy.cost_gbp || quote.price_gbp).toFixed(2)}.` }));
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create the insurance policy."); }
    finally { setBusyId(null); }
  };
  const reconcileShipmentBooking = async (row: Row) => {
    if (row.shipment_booked_at && row.tracking_number && row.parcel2go_order_id && !row.parcel2go_order_line_id) {
      if (!window.confirm("Verify this already-paid shipment in Parcel2Go. This only attaches its shipment tracking reference; it will not make another booking or payment.")) return;
      const provider_order_line_id = window.prompt("Verified Parcel2Go shipment OrderLineId")?.trim();
      if (!provider_order_line_id) return;
      const note = window.prompt("Record how you verified this order-line ID against the existing paid booking (at least 10 characters)")?.trim();
      if (!note || note.length < 10) return;
      setBusyId(row.id); setError(null);
      try {
        await api.dispatch.reconcileShipmentBooking(row.id, {
          resolution: "attach_tracking_reference",
          provider_order_id: row.parcel2go_order_id,
          provider_order_line_id,
          tracking_number: row.tracking_number,
          note,
        });
        await load();
      } catch (err) { setError(err instanceof Error ? err.message : "Could not attach the verified tracking reference."); }
      finally { setBusyId(null); }
      return;
    }
    if (!window.confirm("Check Parcel2Go before continuing. If you find an existing paid booking, attach it here instead of booking again.")) return;
    const existingOrderId = window.prompt("Existing paid Parcel2Go order ID (leave blank only if there is no active or paid booking)");
    let resolution: "no_active_booking" | "paid_booking" = "no_active_booking";
    let provider_order_id: string | undefined;
    let provider_order_line_id: string | undefined;
    let tracking_number: string | undefined;
    let shipping_label_url: string | undefined;
    if (existingOrderId === null) return;
    if (existingOrderId.trim()) {
      resolution = "paid_booking";
      provider_order_id = existingOrderId.trim();
      provider_order_line_id = window.prompt("Parcel2Go shipment OrderLineId (shown in the API order response)")?.trim() || undefined;
      if (!provider_order_line_id) return;
      tracking_number = window.prompt("Tracking number for that paid booking")?.trim();
      if (!tracking_number) return;
      shipping_label_url = window.prompt("Optional Parcel2Go label URL")?.trim() || undefined;
    } else if (!window.confirm("Confirm Parcel2Go has no active or paid booking for this build and that a new purchase is safe.")) return;
    const note = window.prompt("Record how you checked the provider account (required)");
    if (!note || note.trim().length < 10) return;
    setBusyId(row.id); setError(null);
    try { await api.dispatch.reconcileShipmentBooking(row.id, { resolution, provider_order_id, provider_order_line_id, tracking_number, shipping_label_url, note: note.trim() }); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not reconcile the shipment attempt."); }
    finally { setBusyId(null); }
  };
  const appName = (id: string) => apps.find(app => app.package_id === id)?.name || id;
  return <div className="space-y-6">
    <div><h1 className="text-2xl font-semibold text-white">Dispatch Centre</h1><p className="mt-1 text-sm text-slate-400">Review built systems before listing, then prepare the sold build for its customer and dispatch.</p></div>
    <div className="flex gap-2 border-b border-slate-800">
      <button onClick={() => setTab("getting-ready")} className={`px-4 py-2 text-sm ${tab === "getting-ready" ? "border-b-2 border-emerald-400 text-emerald-300" : "text-slate-400"}`}>Getting Ready</button>
      <button onClick={() => setTab("delivery")} className={`px-4 py-2 text-sm ${tab === "delivery" ? "border-b-2 border-emerald-400 text-emerald-300" : "text-slate-400"}`}>Delivery &amp; Insurance</button>
      <button onClick={() => setTab("evidence")} className={`px-4 py-2 text-sm ${tab === "evidence" ? "border-b-2 border-emerald-400 text-emerald-300" : "text-slate-400"}`}>Media Evidence &amp; Dispatch</button>
    </div>
    {error && <div role="alert" className="rounded-lg border border-red-500/30 bg-red-950/20 p-3 text-sm text-red-300">{error}</div>}
    {tab === "getting-ready" ? <>
    <div className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 p-4 text-xs text-slate-400">Generated documents and the WinGet script are saved as an admin-review manifest. Before approving the workshop ZIP, record the new build's intended Windows drive model and serial below; the destructive installer is bound to that exact drive and will refuse a target record older than 30 days. Changing the target after approval requires a new package review. Review the build content and selected apps before using the script on the workshop USB. Windows installation, driver/BIOS updates, RGB profiles, evidence uploads, and package completion gates are not automated in this step.</div>
      {loading ? <p className="text-slate-400">Loading builds…</p> : rows.length === 0 ? <p className="rounded-xl border border-slate-800 p-8 text-center text-slate-500">No built or sold systems are awaiting preparation.</p> : <div className="space-y-4">{rows.map(row => <section key={row.id} className="rounded-xl border border-slate-700 bg-[#0b121d]/90 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><a href={`/builds/${row.id}`} className="font-semibold text-white hover:text-emerald-300">{row.name}</a><p className="mt-1 text-xs text-slate-500">Build {row.id} · {row.buyer_name || "Buyer details pending"}</p></div><span className="rounded-full border border-amber-400/30 px-2 py-1 text-[10px] uppercase tracking-wide text-amber-300">{row.dispatch_status.replaceAll("_", " ")}</span></div>
        {hasPhysicalHandover(row) && <p className="mt-3 rounded border border-emerald-400/20 bg-emerald-400/[.04] p-3 text-xs text-emerald-200">Courier handover is recorded. Preparation and shipment evidence are locked; customer portal access and existing evidence downloads remain available.</p>}
        {row.status === "sold" && <div className="mt-3 flex flex-wrap items-center justify-between gap-3"><a href={api.dispatch.dispatchChecklistDownloadUrl(row.id)} className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-300">Download operator checklist</a><p className="text-[11px] text-slate-500">Keep the checklist with this build's dispatch record.</p></div>}
        {row.status === "sold" && <div className="mt-3 rounded-lg border border-slate-800 bg-black/10 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-xs font-semibold text-slate-200">Guest or marketplace portal</p><p className="mt-1 text-[11px] text-slate-500">Direct guest claims use the verified order email. Marketplace claims are bound to this build and delivered only through the print-ready QR leaflet inside the parcel.</p></div><button disabled={busyId === row.id || (Boolean(row.portal_order_id) && !row.customer_email)} onClick={() => void createPortalClaim(row)} className="rounded border border-cyan-400/30 px-3 py-1.5 text-xs text-cyan-200 disabled:opacity-40">Issue / reissue claim</button></div>{portalClaims[row.id] && <div className="mt-3 border-t border-slate-800 pt-3">{portalClaims[row.id].url && <a href={portalClaims[row.id].url} target="_blank" rel="noreferrer" className="break-all text-xs text-cyan-300 underline">{portalClaims[row.id].url}</a>}<p className="mt-2 text-[11px] leading-5 text-slate-500">{portalClaims[row.id].guidance}</p>{portalClaims[row.id].emailStatus === "sent" && <p role="status" className="mt-2 text-[11px] text-emerald-300">Claim email sent to the verified direct-order email.</p>}{portalClaims[row.id].emailStatus === "pending" && <p role="status" className="mt-2 text-[11px] text-amber-200">Claim email attempt has no saved delivery result. Issue a fresh claim if the customer did not receive access.</p>}{portalClaims[row.id].emailStatus === "failed" && <p role="status" className="mt-2 text-[11px] text-amber-200">Claim email failed. Include the printed QR leaflet or issue a replacement claim.</p>}{portalClaims[row.id].emailStatus == null && <p role="status" className="mt-2 text-[11px] text-slate-400">{portalClaims[row.id].directOrder ? "No email result is recorded for this older claim. Verify access with the customer or issue a fresh claim." : "Claim link is not emailed for this channel. Include the printed QR leaflet."}</p>}<div className="mt-2 flex flex-wrap gap-2"><a href={api.dispatch.portalLeafletDownloadUrl(portalClaims[row.id].grantId)} className="rounded bg-cyan-300 px-2 py-1 text-[10px] font-semibold text-slate-950">Download print-ready QR leaflet</a>{portalClaims[row.id].url && <button onClick={() => void navigator.clipboard.writeText(portalClaims[row.id].url!)} className="rounded border border-slate-700 px-2 py-1 text-[10px] text-slate-300">Copy claim URL (approved channel only)</button>}</div></div>}</div>}
        {row.status === "sold" && row.shipment_booked_at && row.tracking_number && row.parcel2go_order_id && !row.parcel2go_order_line_id && !hasPhysicalHandover(row) && <div role="alert" className="mt-3 rounded border border-amber-400/30 bg-amber-400/5 p-3 text-xs text-amber-200"><p>This existing shipment predates saved Parcel2Go tracking references. Verify its shipment OrderLineId in Parcel2Go; attaching it will not create another booking or payment.</p><button disabled={busyId === row.id} onClick={() => void reconcileShipmentBooking(row)} className="mt-2 rounded border border-amber-300/40 px-3 py-1.5 font-semibold disabled:opacity-50">Attach verified tracking reference</button></div>}
        <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_2fr_auto]">
          <label className="text-xs text-slate-400">Playbook cell<select disabled={hasPhysicalHandover(row)} value={segments[row.id] ?? row.playbook_assignment?.curated_build_id ?? ""} onChange={event => setSegments(current => ({ ...current, [row.id]: event.target.value }))} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-white"><option value="">Select customer type × budget</option>{playbookCells.map(cell => <option key={cell.id} value={cell.id}>{cell.segment} · {cell.tier} · {cell.name}</option>)}</select><span className="mt-1 block text-[10px] text-slate-500">{row.playbook_assignment ? `Assigned before sale: ${row.playbook_assignment.customer_type} · ${row.playbook_assignment.budget_tier}` : "Legacy build: assign a Playbook cell now"}</span></label>
          <div><p className="mb-1 text-xs text-slate-400">Customer-selected software for the USB</p>{row.getting_started?.software_selections.length ? <div className="flex flex-wrap gap-2">{row.getting_started.software_selections.map(id => <span key={id} className="rounded-full border border-slate-700 px-2 py-1 text-xs text-slate-300">{appName(id)}</span>)}</div> : <p className="text-xs text-amber-300">No app selection saved yet; the customer can choose in their portal.</p>}<p className="mt-2 text-[11px] text-slate-500">The customer's saved selection is sent to the setup service. Package licences still apply.</p></div>
          <button disabled={busyId === row.id || hasPhysicalHandover(row)} onClick={() => void generate(row.id)} className="self-end rounded bg-emerald-400 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50">{busyId === row.id ? "Generating…" : "Generate review pack"}</button>
        </div>
        <div className="mt-3 rounded-lg border border-slate-800 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-xs font-semibold text-slate-300">Research reviewed for this exact build</p><p className="mt-1 text-[10px] leading-4 text-slate-500">Editing a reviewed field clears its approval. Search results never authorize automatic downloads or installation; manually downloaded PDFs require a separate review and confirmation before entering the shared library.</p></div><button type="button" onClick={() => setResearchDrafts(current => ({...current, [row.id]: [...(current[row.id] ?? []), blankResearchSource()]}))} className="rounded border border-slate-600 px-2 py-1.5 text-[10px] text-slate-200">Add source</button></div>{(researchDrafts[row.id] ?? []).map((source, index) => <div key={`${row.id}-research-${index}`} className="mt-3 grid gap-2 rounded border border-slate-800 p-3 md:grid-cols-2"><label className="text-[10px] text-slate-400">Exact component name<input value={source.component_name} onChange={event => { clearResearchResults(row.id, index); setResearchDrafts(current => ({...current, [row.id]: (current[row.id] ?? []).map((item, i) => i === index ? {...item, component_name: event.target.value, operator_approved: false} : item)})); }} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-white" placeholder="Must appear in this build’s specification"/></label><label className="text-[10px] text-slate-400">Research topic<select value={source.topic} onChange={event => { clearResearchResults(row.id, index); setResearchDrafts(current => ({...current, [row.id]: (current[row.id] ?? []).map((item, i) => i === index ? {...item, topic: event.target.value as ResearchTopic, operator_approved: false} : item)})); }} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-white"><option value="driver_firmware">Drivers / firmware</option><option value="manual">Instruction manual</option><option value="rgb">RGB configuration</option><option value="software">Software support</option><option value="compatibility">Compatibility</option></select></label><button type="button" disabled={researchSearchKey === `${row.id}:${index}`} onClick={() => void searchResearchSources(row.id, index)} className="self-end rounded border border-cyan-400/30 px-2 py-1.5 text-[10px] text-cyan-200 disabled:opacity-50">{researchSearchKey === `${row.id}:${index}` ? "Searching…" : "Suggest sources"}</button><label className="text-[10px] text-slate-400">HTTPS source URL<input value={source.source_url} onChange={event => setResearchDrafts(current => ({...current, [row.id]: (current[row.id] ?? []).map((item, i) => i === index ? {...item, source_url: event.target.value, operator_approved: false} : item)}))} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-white" placeholder="https://manufacturer.example/support"/></label><label className="text-[10px] text-slate-400">Publisher<input value={source.publisher} onChange={event => setResearchDrafts(current => ({...current, [row.id]: (current[row.id] ?? []).map((item, i) => i === index ? {...item, publisher: event.target.value, operator_approved: false} : item)}))} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-white"/></label><label className="text-[10px] text-slate-400">Page or document title<input value={source.title} onChange={event => setResearchDrafts(current => ({...current, [row.id]: (current[row.id] ?? []).map((item, i) => i === index ? {...item, title: event.target.value, operator_approved: false} : item)}))} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-white"/></label><label className="text-[10px] text-slate-400">Accessed on<input type="date" value={source.accessed_at} onChange={event => setResearchDrafts(current => ({...current, [row.id]: (current[row.id] ?? []).map((item, i) => i === index ? {...item, accessed_at: event.target.value, operator_approved: false} : item)}))} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-white"/></label><label className="text-[10px] text-slate-400 md:col-span-2">What does this source support?<textarea value={source.claim} onChange={event => setResearchDrafts(current => ({...current, [row.id]: (current[row.id] ?? []).map((item, i) => i === index ? {...item, claim: event.target.value, operator_approved: false} : item)}))} rows={2} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-white" placeholder="State one factual claim, such as the relevant driver or supported memory specification."/></label><div className="flex items-center justify-between md:col-span-2"><label className="flex items-center gap-2 text-[10px] text-amber-200"><input type="checkbox" checked={source.operator_approved} onChange={event => setResearchDrafts(current => ({...current, [row.id]: (current[row.id] ?? []).map((item, i) => i === index ? {...item, operator_approved: event.target.checked} : item)}))}/>I checked that this primary source supports the claim above.</label><button type="button" onClick={() => removeResearchDraft(row.id, index)} className="text-[10px] text-red-300 underline">Remove source</button></div>{(researchCacheMatches[row.id]?.[index] ?? []).map(manual => <p key={`${row.id}-${index}-cached-${manual.manual_id}`} role="status" className="text-[10px] leading-5 text-emerald-200 md:col-span-2">Exact active library match: {manual.component_name} · {manual.filename}. It can be included in this build ZIP; generation and package approval recheck the exact model, active status and file checksum.</p>)}{(researchSuggestions[row.id]?.[index] ?? []).map((suggestion, suggestionIndex) => <div key={`${row.id}-${index}-suggestion-${suggestionIndex}`} className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 py-2 md:col-span-2"><a href={suggestion.source_url} target="_blank" rel="noreferrer" className="break-all text-[10px] text-cyan-300 underline">{suggestion.title} · {suggestion.publisher}</a><button type="button" onClick={() => useResearchSuggestion(row.id, index, suggestion)} className="rounded border border-slate-600 px-2 py-1 text-[10px] text-slate-200">Use as unapproved draft</button></div>)}<ReviewedManualUploader buildId={row.id} source={source} componentVerified={researchVerifiedIdentity[row.id]?.[index] === JSON.stringify([source.component_name.trim(), source.topic])} onSaved={manual => setResearchCacheMatches(current => ({...current, [row.id]: {...(current[row.id] ?? {}), [index]: [manual]}}))} /></div>)}</div>
        {!!row.getting_started?.cached_component_manuals?.length && <div className="mt-3 rounded-lg border border-cyan-400/20 bg-cyan-400/[.03] p-3"><p className="text-xs font-semibold text-cyan-200">Exact-match cached manuals eligible for this ZIP</p><ul className="mt-2 space-y-1">{row.getting_started.cached_component_manuals.map(manual => <li key={manual.manual_id} className="break-all text-[11px] text-slate-400">{manual.component_name} · key “{manual.component_key}” · {manual.filename} · SHA-256 {manual.sha256} · <a href={manual.source_url} target="_blank" rel="noreferrer" className="text-cyan-300 underline">source</a></li>)}</ul><p className="mt-2 text-[10px] text-slate-500">Package approval rechecks this model match, active state and checksum.</p></div>}
        {(generated[row.id] || row.getting_started?.manifest) && <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950/70 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-medium text-emerald-300">Generated for admin review</p><div className="flex flex-wrap gap-2">{row.status === "sold" && row.getting_started?.latest_package && row.getting_started.checklist.software_selection_submitted && <button disabled={busyId === row.id || hasPhysicalHandover(row)} onClick={() => void downloadScript(row)} className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-200 disabled:opacity-50">Download software script</button>}<button disabled={busyId === row.id || hasPhysicalHandover(row) || row.status !== "sold"} onClick={() => void approvePackage(row)} className="rounded bg-cyan-300 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-50">{row.status === "sold" ? "Approve & create ZIPs" : "ZIPs available after sale"}</button></div></div>{row.status !== "sold" && <p className="mt-2 text-xs text-amber-200">Pre-sale review supports QA and listing. Lock customer software choices after sale before downloading the setup script or creating the customer ZIP.</p>}{generated[row.id] && <p className="mt-2 text-xs text-slate-400">{String((generated[row.id].software_time_saving_estimate as {minutes?: number} | undefined)?.minutes ?? 0)} estimated minutes saved. The manifest is stored on this build’s evidence record.</p>}<pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words text-[11px] text-slate-400">{JSON.stringify(generated[row.id]?.manifest || row.getting_started?.manifest, null, 2)}</pre>{(() => { const pkg = packages[row.id] || row.getting_started?.latest_package; return pkg && row.status === "sold" ? <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-slate-800 pt-3"><span className="text-xs text-emerald-300">Customer documents v{pkg.version} · {Math.ceil(pkg.size_bytes / 1024)} KB</span><a href={api.dispatch.packageDownloadUrl(row.id, pkg.version)} className="rounded border border-emerald-400/40 px-3 py-1.5 text-xs text-emerald-200">Download workshop USB ZIP</a><span className="text-xs text-slate-400">Workshop ZIP · {Math.ceil((pkg.workshop_size_bytes ?? pkg.size_bytes) / 1024)} KB</span><code className="max-w-full truncate text-[10px] text-slate-500" title={pkg.workshop_sha256 || pkg.sha256}>Workshop SHA-256 {pkg.workshop_sha256 || pkg.sha256}</code></div> : null; })()}</div>}
        {(() => { const pkg = packages[row.id] || row.getting_started?.latest_package; return pkg?.windows_license_helper_required ? <div className="mt-2 rounded border border-amber-300/20 bg-amber-300/[.03] p-3"><p className="text-xs text-amber-100">This order has an assigned Windows Pro key. Download this helper separately and place it beside the workshop master script; it is not part of the ZIP.</p><button disabled={busyId === row.id || hasPhysicalHandover(row)} onClick={() => void downloadWindowsLicenseHelper(row)} className="mt-2 rounded border border-amber-300/40 px-3 py-1.5 text-xs text-amber-100 disabled:opacity-50">Download private licence helper</button></div> : null; })()}
        {row.getting_started && <div className="mt-4 rounded-lg border border-slate-800 p-3"><DriverFirmwareOutcomeList checklist={row.getting_started.checklist} /><p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Workshop completion</p><p className="mt-1 text-[11px] text-slate-500">Record the intended drive before installation. After setup, its model and serial must match the read-only machine report. Every completion or exception needs an audit note.</p><div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{OPERATOR_ACTIONS.map(([action, label]) => { const status = String(row.getting_started?.checklist[action] || "not ready"); const done = status === "complete" || status === "not_required"; const target = row.getting_started?.checklist.windows_target as {model?: string; serial?: string} | undefined; return <div key={action} className={`rounded border p-2 ${done ? "border-emerald-400/20 bg-emerald-400/5" : "border-slate-800"}`}><p className="text-xs text-slate-200">{label}</p><p className={`mt-1 text-[10px] uppercase ${done ? "text-emerald-300" : "text-amber-300"}`}>{status.replaceAll("_", " ")}</p>{action === "windows_target_confirmed" && target && <p className="mt-1 break-all text-[10px] text-slate-400">{target.model} · {target.serial}</p>}{!done && action === "windows_target_confirmed" && <button disabled={busyId === row.id || hasPhysicalHandover(row)} onClick={() => void recordWindowsTarget(row)} className="mt-2 rounded border border-amber-300/30 px-2 py-1 text-[10px] text-amber-100">Record intended drive</button>}{!done && action === "windows_deployment_completed" && <label className="mt-2 inline-flex cursor-pointer rounded border border-amber-300/30 px-2 py-1 text-[10px] text-amber-100">Import machine report<input className="sr-only" type="file" accept="application/json,.json" disabled={busyId === row.id || hasPhysicalHandover(row)} onChange={event => { void importWindowsEvidence(row, event.currentTarget.files?.[0]); event.currentTarget.value = ""; }} /></label>}{!done && action !== "windows_deployment_completed" && action !== "windows_target_confirmed" && <div className="mt-2 flex gap-1"><button disabled={busyId === row.id || hasPhysicalHandover(row)} onClick={() => void setChecklistAction(row, action, "complete")} className="rounded bg-emerald-400 px-2 py-1 text-[10px] font-semibold text-slate-950">Complete</button>{(action === "ai_services_complete" || action === "rgb_theme_applied") && <button disabled={busyId === row.id || hasPhysicalHandover(row)} onClick={() => void setChecklistAction(row, action, "not_required")} className="rounded border border-slate-700 px-2 py-1 text-[10px] text-slate-300">Not required</button>}</div>}</div>; })}</div></div>}
      </section>)}</div>}
    </> : tab === "delivery" ? <>
      <div className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 p-4 text-xs leading-5 text-slate-400">Sequence: explicitly book and pay for the signed-for courier first, upload the working-build, package-contents and sealed-parcel photos next, then explicitly buy insurance. Dispatch remains a separate physical-handover confirmation after cover is registered. Confirm current provider eligibility and packaging rules before purchase. Keep the packaging and record any damage with the carrier promptly.</div>
      {loading ? <p className="text-slate-400">Loading dispatch queue…</p> : soldRows.length === 0 ? <p className="rounded-xl border border-slate-800 p-8 text-center text-slate-500">No sold builds are awaiting shipment.</p> : <div className="space-y-3">{soldRows.map(row => <div key={row.id} className="rounded-xl border border-slate-700 bg-[#0b121d]/90 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><a href={`/builds/${row.id}`} className="font-semibold text-white hover:text-emerald-300">{row.name}</a><p className="mt-1 text-xs text-slate-500">Build {row.id} · {row.buyer_name || "Buyer details pending"} · {row.customer_email || "customer email pending"}</p></div><span className="rounded-full border border-amber-400/30 px-2 py-1 text-[10px] uppercase tracking-wide text-amber-300">{row.dispatch_status.replaceAll("_", " ")}</span></div>{row.shipment_booking_state === "reconciliation_required" && !hasPhysicalHandover(row) && <div role="alert" className="mt-3 rounded border border-amber-400/30 bg-amber-400/5 p-3 text-xs text-amber-200"><p>A Parcel2Go request may have created or charged for a shipment. Verify the provider account. Attach an existing paid booking here, or confirm there is no active booking before permitting a new purchase.</p><button disabled={busyId === row.id} onClick={() => void reconcileShipmentBooking(row)} className="mt-2 rounded border border-amber-300/40 px-3 py-1.5 font-semibold disabled:opacity-50">Reconcile provider booking</button></div>}<div className="mt-4 flex flex-wrap items-center gap-3 text-sm"><span className="text-slate-300">Sale: £{(row.sale_price || 0).toFixed(2)}</span>{row.tracking_number && <a href={row.shipping_label_url || "#"} target="_blank" rel="noreferrer" className="text-cyan-300 hover:underline">Tracking {row.tracking_number}</a>}{row.collection_date && <span className="text-slate-400">Collection {new Date(row.collection_date).toLocaleString("en-GB")}</span>}<button disabled={hasPhysicalHandover(row)} onClick={() => void schedule(row.id)} className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-200 hover:border-emerald-400/50">{row.collection_date ? "Change collection day" : "Set collection day"}</button>{hasPhysicalHandover(row) ? <span className="rounded border border-emerald-400/20 px-3 py-1.5 text-xs text-emerald-200">Shipment booking closed after handover</span> : <a href={`/builds/${row.id}`} className="rounded bg-emerald-400 px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-emerald-300">Open shipment booking</a>}</div><div className="mt-4 rounded-lg border border-slate-800 bg-black/10 p-3"><p className="text-xs text-slate-300">Insurance: {row.insurance_policy_id ? `Policy ${row.insurance_policy_id} · £${(row.insurance_cost_gbp || 0).toFixed(2)}` : row.insurance_status || "not created"}</p>{row.insurance_status === "creation_uncertain" && row.insurance_provider_response && <div role="alert" className="mt-2 rounded border border-amber-400/30 bg-amber-400/5 p-3 text-[11px] text-amber-100"><p>Provider response needs reconciliation: policy {row.insurance_provider_response.policy_id || "ID unavailable"} · mode {row.insurance_provider_response.mode || "unknown"} · currency {row.insurance_provider_response.currency || "unknown"}</p><p className="mt-1">Insured value {row.insurance_provider_response.insured_value_gbp == null ? "unknown" : `£${row.insurance_provider_response.insured_value_gbp.toFixed(2)}`} · premium {row.insurance_provider_response.price_gbp == null ? "unknown" : `£${row.insurance_provider_response.price_gbp.toFixed(2)}`}</p>{row.insurance_provider_response.mismatches.length > 0 && <p className="mt-1">Needs review: {row.insurance_provider_response.mismatches.join("; ")}</p>}<p className="mt-1">Dispatch stays blocked. Verify these details in the provider account before reconciling.</p></div>}{!row.insurance_policy_id && (row.insurance_status === "creating" || row.insurance_status === "creation_uncertain") && <button disabled={busyId === row.id || hasPhysicalHandover(row)} onClick={() => void reconcileInsurancePolicy(row)} className="mt-2 rounded border border-amber-300/40 px-3 py-1.5 text-xs text-amber-100 disabled:opacity-50">Reconcile insurer account</button>}{!row.insurance_policy_id && <div className="mt-2 flex flex-wrap items-center gap-2"><button disabled={busyId === row.id || hasPhysicalHandover(row) || row.shipment_booking_state !== "booked" || !row.tracking_number || row.insurance_status === "creating" || row.insurance_status === "creation_uncertain"} onClick={() => void quoteInsurance(row)} className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-200">{busyId === row.id ? "Working…" : "Get Figural quote"}</button>{insuranceQuotes[row.id] && <button disabled={busyId === row.id || hasPhysicalHandover(row) || row.shipment_booking_state !== "booked" || !row.tracking_number || row.getting_started?.checklist.working_pc_photo !== "complete" || row.getting_started?.checklist.package_contents_photo !== "complete" || row.getting_started?.checklist.sealed_package_photo !== "complete" || row.insurance_status === "creating" || row.insurance_status === "creation_uncertain"} onClick={() => void buyInsurance(row)} className="rounded bg-amber-300 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-50">Create policy · £{insuranceQuotes[row.id].price_gbp.toFixed(2)}</button>}{insuranceMessage[row.id] && <span className="text-xs text-slate-400">{insuranceMessage[row.id]}</span>}</div>}</div></div>)}</div>}
    </> : <DispatchEvidenceTab rows={soldRows} loading={loading} busyId={busyId} uploadEvidence={uploadEvidence} dispatchBuild={dispatchBuild} evidenceMessage={evidenceMessage} />}
  </div>;
}

function DispatchEvidenceTab({ rows, loading, busyId, uploadEvidence, dispatchBuild, evidenceMessage }: {
  rows: Row[];
  loading: boolean;
  busyId: number | null;
  uploadEvidence: (buildId: number, category: "working_pc" | "package_contents" | "sealed_package", file?: File) => Promise<void>;
  dispatchBuild: (row: Row) => Promise<void>;
  evidenceMessage: Record<number, string>;
}) {
  return <section className="space-y-4">
    <div className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 p-4 text-xs leading-5 text-slate-400">
      After courier booking, upload unedited evidence of the working build, the contents before packing, and the sealed parcel. Review and approve each file; contents and sealed-parcel evidence must be still photos. These remain private. Register the confirmed signed-for insurance policy before physical handover; dispatch sends the tracking update to the customer.
    </div>
    {loading ? <p className="text-slate-400">Loading shipment evidence…</p> : rows.length === 0 ? <p className="rounded-xl border border-slate-800 p-8 text-center text-slate-500">No sold builds need shipment evidence.</p> : <div className="space-y-3">{rows.map(row => {
      const checklist = row.getting_started?.checklist ?? {};
      const statuses = [
        ["working_pc_photo", "Working-build photo"],
        ["package_contents_photo", "Contents-before-packing photo"],
        ["sealed_package_photo", "Sealed-parcel photo"],
      ] as const;
      const complete = DISPATCH_BLOCKING_ACTIONS.every(key =>
        checklist[key] === "complete" || (checklist[key] === "not_required" && OPTIONAL_CHECKLIST_ACTIONS.has(key))
      );
      const handedOver = hasPhysicalHandover(row);
      const canUpload = !handedOver && row.shipment_booking_state === "booked" && Boolean(row.tracking_number);
      const canDispatch = canUpload && complete && Boolean(row.insurance_policy_id) && !handedOver;
      return <article key={row.id} className="rounded-xl border border-slate-700 bg-[#0b121d]/90 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><a href={`/builds/${row.id}`} className="font-semibold text-white hover:text-emerald-300">{row.name}</a><p className="mt-1 text-xs text-slate-500">Build {row.id} · {row.buyer_name || "Buyer details pending"} · {row.tracking_number ? `Tracking ${row.tracking_number}` : "Courier booking required first"}</p></div>
          <span className="rounded-full border border-amber-400/30 px-2 py-1 text-[10px] uppercase tracking-wide text-amber-300">{row.dispatch_status.replaceAll("_", " ")}</span>
        </div>
        {handedOver ? <p className="mt-3 rounded border border-emerald-400/20 bg-emerald-400/[.04] p-3 text-xs text-emerald-200">Physical handover is recorded. Evidence remains available to download, but uploads and reviews are closed.</p> : !canUpload && <p className="mt-3 rounded border border-amber-400/20 bg-amber-400/[.04] p-3 text-xs text-amber-200">Book and pay for the signed-for courier in Delivery &amp; Insurance before uploading these photos.</p>}
        <div className="mt-4 grid gap-2 sm:grid-cols-3">{statuses.map(([key, label]) => <div key={key} className={`rounded border p-3 ${checklist[key] === "complete" ? "border-emerald-400/30 bg-emerald-400/[.04]" : "border-slate-700"}`}><p className="text-xs text-slate-200">{label}</p><p className="mt-1 text-[10px] uppercase text-slate-400">{String(checklist[key] ?? "not ready").replaceAll("_", " ")}</p></div>)}</div>
        {(row.getting_started?.shipment_evidence ?? []).length > 0 && <div className="mt-4 space-y-2 border-t border-slate-800 pt-3"><p className="text-xs font-semibold uppercase tracking-wide text-cyan-200">Review uploaded evidence</p>{row.getting_started?.shipment_evidence?.map(item => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-700 p-3"><div><p className="text-xs text-slate-200">{item.filename} · {item.category.replaceAll("_", " ")}</p><p className="mt-1 text-[10px] text-slate-400">Uploaded by {item.uploaded_by_admin_name || "staff"} · {new Date(item.uploaded_at).toLocaleString("en-GB")} · {String(item.review_status || "needs_review").replaceAll("_", " ")}{item.review_note ? ` · ${item.review_note}` : ""}</p></div><div className="flex gap-2"><button type="button" disabled={busyId === row.id} onClick={() => void downloadEvidence(row, item.id, item.filename)} className="rounded border border-slate-600 px-2 py-1 text-xs">Download</button>{item.review_status !== "approved" && <button type="button" disabled={busyId === row.id || handedOver} onClick={() => void reviewEvidence(row, item.id, true)} className="rounded border border-emerald-400/40 px-2 py-1 text-xs text-emerald-200">Approve</button>}{item.review_status !== "rejected" && <button type="button" disabled={busyId === row.id || handedOver} onClick={() => void reviewEvidence(row, item.id, false)} className="rounded border border-red-400/40 px-2 py-1 text-xs text-red-200">Reject</button>}</div></div>)}</div>}
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-800 pt-3">
          <label className={`rounded border px-3 py-2 text-xs ${canUpload ? "cursor-pointer border-slate-600 text-slate-200" : "cursor-not-allowed border-slate-800 text-slate-600"}`}>Working-build photo (or video)<input type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm" disabled={!canUpload || busyId === row.id} className="sr-only" onChange={event => void uploadEvidence(row.id, "working_pc", event.target.files?.[0])} /></label>
          <label className={`rounded border px-3 py-2 text-xs ${canUpload ? "cursor-pointer border-slate-600 text-slate-200" : "cursor-not-allowed border-slate-800 text-slate-600"}`}>Contents-before-packing photo<input type="file" accept="image/jpeg,image/png,image/webp" disabled={!canUpload || busyId === row.id} className="sr-only" onChange={event => void uploadEvidence(row.id, "package_contents", event.target.files?.[0])} /></label>
          <label className={`rounded border px-3 py-2 text-xs ${canUpload ? "cursor-pointer border-slate-600 text-slate-200" : "cursor-not-allowed border-slate-800 text-slate-600"}`}>Sealed-parcel photo<input type="file" accept="image/jpeg,image/png,image/webp" disabled={!canUpload || busyId === row.id} className="sr-only" onChange={event => void uploadEvidence(row.id, "sealed_package", event.target.files?.[0])} /></label>
          {evidenceMessage[row.id] && <span role="status" className="text-xs text-emerald-300">{evidenceMessage[row.id]}</span>}
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-400">Insurance: {row.insurance_policy_id ? `policy ${row.insurance_policy_id} registered` : "policy required before handover"}</p>
          {handedOver ? <span className="rounded border border-emerald-400/30 px-3 py-2 text-xs text-emerald-200">{row.dispatch_status === "delivered" ? "Delivered" : "Handover recorded"}</span> : <button disabled={!canDispatch || busyId === row.id} onClick={() => void dispatchBuild(row)} className="rounded bg-cyan-300 px-3 py-2 text-xs font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">Confirm handover &amp; dispatch</button>}
        </div>
        {!complete && <p className="mt-2 text-[11px] text-amber-300">Finish all remaining Getting Ready actions and upload the working-build photo/video plus the two required still photos before dispatch.</p>}
      </article>;
    })}</div>}
  </section>;
}
