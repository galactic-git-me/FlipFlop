"use client";

import { ManualBuild } from "@/lib/api";
import {
  Sparkles,
  AlertCircle,
  Tag,
  Monitor,
  Box,
  Target,
  Hash,
  Square,
  Database,
  HardDrive,
  Cpu,
  Gauge,
  MemoryStick,
  AppWindow,
  Wifi,
  Star,
  MonitorPlay,
  Layers,
  Image as ImageIcon,
  ShieldCheck,
  Globe,
  Palette,
  CircuitBoard,
  Calendar,
  Disc,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { EBAY_COUNTRY_OF_ORIGIN_VALUES } from "@/lib/ebay-country-values";

// Mirrors flipflop-api's EBAY_PC_SPECIFICS + FREE_TEXT_ASPECTS keys (see
// app/services/ebay_specifics_generator.py) — the full set of eBay Item
// Specifics for "PC Desktops & All-in-Ones" (category 179). Every one of
// these is always shown as a row, generated or not, rather than the section
// only ever displaying whatever subset the last generation call happened to
// return — a partial LLM response used to look identical to a broken one.
const EBAY_ASPECT_FIELDS = [
  "Brand", "Type", "Model", "Most Suitable For", "MPN", "Form Factor",
  "Storage Type", "Hard Drive Capacity", "Processor", "Processor Speed",
  "RAM Size", "Operating System", "Connectivity", "Features", "GPU",
  "Series", "Graphics Processing Type", "Manufacturer Warranty",
  "Country of Origin", "Colour", "Maximum RAM Capacity",
  "Motherboard Model", "Release Year", "SSD Capacity",
];
const EBAY_REQUIRED_ASPECTS = new Set(["Brand", "Type"]);

// eBay's confirmed per-value length cap (verified via a real listing
// rejection — errorId 25002, "Enter a value of no more than 65
// characters") — see validate_aspects_for_ebay in
// app/services/ebay_specifics_generator.py for the matching backend check.
// Applied uniformly since eBay's Taxonomy API doesn't expose a narrower
// per-field limit.
const EBAY_ASPECT_VALUE_MAX_LENGTH = 65;

// Country of Origin is the one field eBay's Taxonomy API actually reports
// as SELECTION_ONLY (a real closed enum) for this category — every other
// aspect (Brand, GPU, Processor, Connectivity, ...) is FREE_TEXT with a
// list of merely-recommended values, so only this one gets a hard dropdown
// instead of a free-text input.
const EBAY_SELECTION_ONLY_ASPECTS: Record<string, string[]> = {
  "Country of Origin": EBAY_COUNTRY_OF_ORIGIN_VALUES,
};

// eBay's REAL per-aspect cardinality (confirmed via the Taxonomy API —
// get_item_aspects_for_category, category 179) — every aspect NOT in this
// set is itemToAspectCardinality: SINGLE, meaning eBay rejects more than
// one value outright ("Colour should contain only one value..."). This
// bit the admin for real: a build's "Colour" value
// "ChromaFlair (Metallic, colour-shifting blue-green-purple)" got blindly
// split on every comma — including the one inside the parentheses — into
// two array entries, which eBay then rejected at publish time. Only these
// four aspects should ever be comma-split into multiple values; every
// other field's entire input is ONE value, commas and all.
const EBAY_MULTI_VALUE_ASPECTS = new Set(["Most Suitable For", "Features", "Connectivity", "MPN"]);

/** Turns one aspect's raw text input into the value array eBay expects —
 * comma-split only for genuinely multi-value aspects, otherwise the whole
 * trimmed input is a single value (see EBAY_MULTI_VALUE_ASPECTS above). */
function parseAspectInput(aspectName: string, rawValue: string): string[] {
  if (EBAY_MULTI_VALUE_ASPECTS.has(aspectName)) {
    return rawValue.split(",").map((v) => v.trim()).filter((v) => v);
  }
  const trimmed = rawValue.trim();
  return trimmed ? [trimmed] : [];
}

// eBay's length cap applies per individual value. For multi-value aspects
// that's per comma-split item; for single-value aspects (the vast
// majority) it's the whole trimmed input, commas and all — mirrors
// parseAspectInput's own splitting rule so what gets flagged here matches
// what actually gets saved. Mirrors the backend's validate_aspects_for_ebay.
function findOverLengthValues(aspectName: string, rawValue: string): string[] {
  return parseAspectInput(aspectName, rawValue).filter((v) => v.length > EBAY_ASPECT_VALUE_MAX_LENGTH);
}

// One icon per aspect, chosen for what the attribute actually represents
// rather than decoratively — makes the 3-column grid scannable at a glance.
const EBAY_ASPECT_ICONS: Record<string, LucideIcon> = {
  "Brand": Tag,
  "Type": Monitor,
  "Model": Box,
  "Most Suitable For": Target,
  "MPN": Hash,
  "Form Factor": Square,
  "Storage Type": Database,
  "Hard Drive Capacity": HardDrive,
  "Processor": Cpu,
  "Processor Speed": Gauge,
  "RAM Size": MemoryStick,
  "Operating System": AppWindow,
  "Connectivity": Wifi,
  "Features": Star,
  "GPU": MonitorPlay,
  "Series": Layers,
  "Graphics Processing Type": ImageIcon,
  "Manufacturer Warranty": ShieldCheck,
  "Country of Origin": Globe,
  "Colour": Palette,
  "Maximum RAM Capacity": MemoryStick,
  "Motherboard Model": CircuitBoard,
  "Release Year": Calendar,
  "SSD Capacity": Disc,
};

interface Props {
  build: ManualBuild;
  onGenerateSpecifics: () => Promise<void>;
  onUpdateAspects: (aspects: Record<string, string[]>) => Promise<void>;
  generating?: boolean;
  saving?: boolean;
}

export function EbaySpecificsSection({
  build,
  onGenerateSpecifics,
  onUpdateAspects,
  generating,
  saving,
}: Props) {
  const [editingAspects, setEditingAspects] = useState<Record<string, string> | null>(null);
  const [editingSpecific, setEditingSpecific] = useState<string | null>(null);
  const [editingSpecificValue, setEditingSpecificValue] = useState<string>("");

  const aspects = build.generated_aspects || {};
  const hasAnyGenerated = Object.keys(aspects).length > 0;
  const isEditing = editingAspects !== null;
  const hasAnyOverLengthValue = isEditing
    ? Object.entries(editingAspects!).some(
        ([name, raw]) => !EBAY_SELECTION_ONLY_ASPECTS[name] && findOverLengthValues(name, raw).length > 0
      )
    : false;

  const handleEditStart = () => {
    const drafts: Record<string, string> = {};
    for (const name of EBAY_ASPECT_FIELDS) {
      drafts[name] = (aspects[name] || []).join(", ");
    }
    setEditingAspects(drafts);
  };

  const handleEditCancel = () => {
    setEditingAspects(null);
  };

  const handleEditSave = async () => {
    if (!editingAspects) return;
    try {
      const normalized: Record<string, string[]> = {};
      for (const [key, value] of Object.entries(editingAspects)) {
        normalized[key] = parseAspectInput(key, value);
      }
      await onUpdateAspects(normalized);
      setEditingAspects(null);
    } catch (error) {
      console.error("Error saving aspects:", error);
      alert("Failed to save specifics. Please try again.");
    }
  };

  const handleSpecificEditStart = (aspectName: string) => {
    const currentValue = (aspects[aspectName] || []).join(", ");
    setEditingSpecific(aspectName);
    setEditingSpecificValue(currentValue);
  };

  const handleSpecificEditSave = async (aspectName: string) => {
    try {
      const normalized: Record<string, string[]> = {
        ...aspects,
        [aspectName]: parseAspectInput(aspectName, editingSpecificValue),
      };
      await onUpdateAspects(normalized);
      setEditingSpecific(null);
      setEditingSpecificValue("");
    } catch (error) {
      console.error("Error saving aspect:", error);
      alert("Failed to save. Please try again.");
    }
  };

  const handleSpecificEditCancel = () => {
    setEditingSpecific(null);
    setEditingSpecificValue("");
  };

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800 p-4 space-y-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-amber-400" />
          <h3 className="text-sm font-semibold text-slate-100">Item Specifics (eBay Attributes)</h3>
        </div>
        <span className="text-xs text-slate-400">
          {Object.keys(aspects).length}/{EBAY_ASPECT_FIELDS.length} filled
        </span>
      </div>

      {!hasAnyGenerated && (
        <div className="flex items-start gap-3 p-3 rounded bg-amber-900/20 border border-amber-700/30">
          <AlertCircle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
          <div className="text-xs text-amber-200">
            <p className="font-semibold mb-1">No item specifics yet</p>
            <p>
              Click "Generate Specifics" to have the local AI fill in these attributes from
              this build's components, or fill them in yourself below.
            </p>
          </div>
        </div>
      )}

      {isEditing ? (
        // 3 columns of 8, filled column-first (grid-flow-col + grid-rows-8)
        // so the 24-field list reads top-to-bottom within a column rather
        // than as one long vertical scroll.
        <div className="grid grid-cols-3 grid-flow-col grid-rows-8 gap-3">
          {EBAY_ASPECT_FIELDS.map((name) => {
            const Icon = EBAY_ASPECT_ICONS[name];
            const selectionValues = EBAY_SELECTION_ONLY_ASPECTS[name];
            const rawValue = editingAspects[name] ?? "";
            const overLength = selectionValues ? [] : findOverLengthValues(name, rawValue);
            return (
            <div key={name} className="space-y-1">
              <label className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                <Icon className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                {name}
                {EBAY_REQUIRED_ASPECTS.has(name) && <span className="text-amber-400"> *</span>}
              </label>
              {selectionValues ? (
                <select
                  value={rawValue}
                  onChange={(e) => setEditingAspects({ ...editingAspects, [name]: e.target.value })}
                  className="w-full rounded bg-slate-700 px-3 py-2 text-sm text-slate-100 border border-slate-600 focus:border-blue-500 focus:outline-none"
                >
                  <option value="">— Select —</option>
                  {selectionValues.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              ) : (
                <>
                  <input
                    type="text"
                    value={rawValue}
                    onChange={(e) =>
                      setEditingAspects({ ...editingAspects, [name]: e.target.value })
                    }
                    className={`w-full rounded bg-slate-700 px-3 py-2 text-sm text-slate-100 border focus:outline-none ${
                      overLength.length > 0
                        ? "border-red-600 focus:border-red-500"
                        : "border-slate-600 focus:border-blue-500"
                    }`}
                    placeholder={EBAY_MULTI_VALUE_ASPECTS.has(name) ? "Comma-separated values" : "Single value"}
                  />
                  {overLength.length > 0 && (
                    <p className="text-[10px] text-red-400">
                      eBay allows max {EBAY_ASPECT_VALUE_MAX_LENGTH} chars per value — too long:{" "}
                      {overLength.map((v) => `"${v.slice(0, 20)}…" (${v.length})`).join(", ")}
                    </p>
                  )}
                </>
              )}
            </div>
            );
          })}
        </div>
      ) : (
        <div className="grid grid-cols-3 grid-flow-col grid-rows-8 gap-2">
          {EBAY_ASPECT_FIELDS.map((name) => {
            const values = aspects[name];
            const isEmpty = !values || values.length === 0;
            const Icon = EBAY_ASPECT_ICONS[name];
            const isEditingThis = editingSpecific === name;

            if (isEditingThis) {
              const selectionValues = EBAY_SELECTION_ONLY_ASPECTS[name];
              const overLength = selectionValues ? [] : findOverLengthValues(name, editingSpecificValue);
              return (
                <div key={name} className="space-y-1">
                  <label className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                    <Icon className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    {name}
                    {EBAY_REQUIRED_ASPECTS.has(name) && <span className="text-amber-400"> *</span>}
                  </label>
                  {selectionValues ? (
                    <select
                      autoFocus
                      value={editingSpecificValue}
                      onChange={(e) => setEditingSpecificValue(e.target.value)}
                      className="w-full rounded bg-slate-700 px-2 py-1.5 text-xs text-slate-100 border border-blue-500 focus:border-blue-400 focus:outline-none"
                    >
                      <option value="">— Select —</option>
                      {selectionValues.map((v) => (
                        <option key={v} value={v}>{v}</option>
                      ))}
                    </select>
                  ) : (
                    <>
                      <input
                        type="text"
                        autoFocus
                        value={editingSpecificValue}
                        onChange={(e) => setEditingSpecificValue(e.target.value)}
                        className={`w-full rounded bg-slate-700 px-2 py-1.5 text-xs text-slate-100 border focus:outline-none ${
                          overLength.length > 0
                            ? "border-red-600 focus:border-red-500"
                            : "border-blue-500 focus:border-blue-400"
                        }`}
                        placeholder={EBAY_MULTI_VALUE_ASPECTS.has(name) ? "Comma-separated values" : "Single value"}
                      />
                      {overLength.length > 0 && (
                        <p className="text-[10px] text-red-400">
                          Max {EBAY_ASPECT_VALUE_MAX_LENGTH} chars per value ({overLength[0].length} chars)
                        </p>
                      )}
                    </>
                  )}
                  <div className="flex gap-1">
                    <button
                      onClick={() => handleSpecificEditSave(name)}
                      disabled={saving || overLength.length > 0}
                      className="flex-1 rounded bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed px-2 py-1 text-xs font-semibold text-white transition"
                    >
                      Save
                    </button>
                    <button
                      onClick={handleSpecificEditCancel}
                      className="flex-1 rounded bg-slate-700 hover:bg-slate-600 px-2 py-1 text-xs font-semibold text-slate-200 transition"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              );
            }

            return (
              <button
                key={name}
                onClick={() => handleSpecificEditStart(name)}
                type="button"
                className={`flex items-start gap-2 p-2 rounded border text-left transition-colors hover:border-opacity-100 ${
                  isEmpty
                    ? "bg-slate-800/50 border-dashed border-slate-700 hover:bg-slate-800/70 hover:border-slate-600"
                    : "bg-emerald-950/40 border-emerald-700/50 hover:bg-emerald-950/60 hover:border-emerald-600"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${isEmpty ? "text-slate-700" : "text-emerald-400"}`} />
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-slate-300">
                    {name}
                    {EBAY_REQUIRED_ASPECTS.has(name) && <span className="text-amber-400"> *</span>}
                  </p>
                  <p className={`text-xs truncate ${isEmpty ? "text-slate-600 italic" : "text-emerald-100"}`}>
                    {isEmpty ? "Not set" : values.join(", ")}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      )}

      <div className="flex gap-2 pt-2">
        {isEditing ? (
          <>
            <button
              onClick={handleEditSave}
              disabled={saving || hasAnyOverLengthValue}
              title={hasAnyOverLengthValue ? "Fix over-length values before saving" : undefined}
              className="flex-1 rounded bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed px-3 py-2 text-xs font-semibold text-white transition"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
            <button
              onClick={handleEditCancel}
              className="flex-1 rounded bg-slate-700 hover:bg-slate-600 px-3 py-2 text-xs font-semibold text-slate-200 transition"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <button
              onClick={handleEditStart}
              className="flex-1 rounded bg-slate-700 hover:bg-slate-600 px-3 py-2 text-xs font-semibold text-slate-200 transition"
            >
              Edit
            </button>
            <button
              onClick={onGenerateSpecifics}
              disabled={generating}
              className="flex-1 rounded bg-amber-600 hover:bg-amber-700 disabled:bg-slate-600 disabled:cursor-not-allowed px-3 py-2 text-xs font-semibold text-white transition flex items-center justify-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {generating ? "Generating..." : hasAnyGenerated ? "Regenerate" : "Generate Specifics"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
