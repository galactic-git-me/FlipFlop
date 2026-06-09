// pc-flipper/app/flips/page.tsx
"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { Plus, ChevronDown, RotateCcw, Loader2 } from "lucide-react";
import { api, BuildComponent, ManualBuild, ManualBuildEvaluation } from "@/lib/api";
import { BuildRow } from "@/components/manual-build/BuildRow";
import { EntryModal } from "@/components/manual-build/EntryModal";
import { EvalPanel } from "@/components/manual-build/EvalPanel";

const DEFAULT_SLOTS = [
  "Base PC",
  "CPU",
  "GPU",
  "RAM",
  "Storage",
  "PSU",
  "Case",
  "Motherboard",
  "Cooling",
];

export default function ManualBuildPage() {
  // Build state
  const [build, setBuild] = useState<ManualBuild | null>(null);
  const [savedBuilds, setSavedBuilds] = useState<{ id: number; name: string; updated_at: string }[]>([]);
  const [customSlots, setCustomSlots] = useState<string[]>([]);
  const [loadingBuilds, setLoadingBuilds] = useState(true);
  const [showLoadDropdown, setShowLoadDropdown] = useState(false);

  // Save indicator
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved">("idle");
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Modal
  const [activeSlot, setActiveSlot] = useState<string | null>(null);

  // Evaluation
  const [evaluating, setEvaluating] = useState(false);
  const [evalResult, setEvalResult] = useState<ManualBuildEvaluation | null>(null);

  // Load saved builds list on mount
  useEffect(() => {
    api.manualBuilds.list().then((list) => {
      setSavedBuilds(list);
      setLoadingBuilds(false);
    }).catch(() => setLoadingBuilds(false));
  }, []);

  // Auto-save: debounced PATCH whenever build changes
  const autoSave = useCallback((updated: ManualBuild) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setSaveStatus("saving");
    saveTimer.current = setTimeout(async () => {
      try {
        await api.manualBuilds.patch(updated.id, {
          name: updated.name,
          components: updated.components,
        });
        setSaveStatus("saved");
        setTimeout(() => setSaveStatus("idle"), 1500);
      } catch {
        setSaveStatus("idle");
      }
    }, 400);
  }, []);

  async function createNewBuild() {
    const b = await api.manualBuilds.create("Untitled Build");
    setBuild(b);
    setEvalResult(null);
    setCustomSlots([]);
    setSavedBuilds((prev) => [
      { id: b.id, name: b.name, updated_at: b.updated_at },
      ...prev,
    ]);
  }

  async function loadBuild(id: number) {
    const b = await api.manualBuilds.get(id);
    setBuild(b);
    setEvalResult(b.last_evaluation ?? null);
    // Restore any custom slots from the loaded build
    const knownSlots = new Set(DEFAULT_SLOTS);
    const extras = b.components
      .map((c) => c.slot)
      .filter((s) => !knownSlots.has(s));
    setCustomSlots([...new Set(extras)]);
    setShowLoadDropdown(false);
  }

  function updateBuild(patch: Partial<ManualBuild>) {
    if (!build) return;
    const updated = { ...build, ...patch };
    setBuild(updated);
    autoSave(updated);
  }

  function handleNameChange(name: string) {
    updateBuild({ name });
  }

  function handleAddComponent(slot: string) {
    setActiveSlot(slot);
  }

  function handleComponentConfirmed(component: BuildComponent) {
    if (!build) return;
    const existing = build.components.filter((c) => c.slot !== component.slot);
    const newComponents = [...existing, component];
    updateBuild({ components: newComponents });
    setActiveSlot(null);
  }

  function handleRemoveComponent(slot: string) {
    if (!build) return;
    updateBuild({ components: build.components.filter((c) => c.slot !== slot) });
  }

  function handlePriceChange(slot: string, price: number) {
    if (!build) return;
    updateBuild({
      components: build.components.map((c) =>
        c.slot === slot ? { ...c, price_paid: price } : c
      ),
    });
  }

  function addCustomSlot() {
    const name = prompt("Custom slot name (e.g. Capture Card):");
    if (name?.trim()) setCustomSlots((prev) => [...prev, name.trim()]);
  }

  async function handleEvaluate() {
    if (!build) return;
    setEvaluating(true);
    try {
      const result = await api.manualBuilds.evaluate(build.id);
      setEvalResult(result);
    } catch {
      alert("Evaluation failed — check AI backend is configured in Settings.");
    }
    setEvaluating(false);
  }

  const allSlots = [...DEFAULT_SLOTS, ...customSlots];
  const componentBySlot = Object.fromEntries(
    (build?.components ?? []).map((c) => [c.slot, c])
  );
  const totalCost = build?.components.reduce((s, c) => s + c.price_paid, 0) ?? 0;

  // Suppress unused variable warning
  void loadingBuilds;

  return (
    <div className="flex flex-col h-full min-h-0 p-6 gap-4 max-w-2xl mx-auto w-full">
      {/* ── Header ── */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={build?.name ?? ""}
          onChange={(e) => handleNameChange(e.target.value)}
          placeholder="Build name…"
          disabled={!build}
          className="flex-1 text-lg font-semibold bg-transparent border-b border-slate-700 focus:border-[#00dc82] outline-none text-slate-100 placeholder-slate-600 pb-0.5 disabled:opacity-30"
        />

        {saveStatus === "saving" && (
          <span className="text-[10px] text-slate-500 font-mono">saving…</span>
        )}
        {saveStatus === "saved" && (
          <span className="text-[10px] text-[#00dc82] font-mono">Saved ✓</span>
        )}

        {/* Load dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowLoadDropdown((v) => !v)}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs border border-slate-700 rounded-md text-slate-400 hover:border-slate-500 hover:text-slate-200 transition-colors"
          >
            Load <ChevronDown className="w-3 h-3" />
          </button>
          {showLoadDropdown && (
            <div className="absolute right-0 top-full mt-1 w-64 bg-[#0b1220] border border-slate-700 rounded-lg shadow-xl z-20 overflow-hidden">
              {savedBuilds.length === 0 ? (
                <p className="px-3 py-2 text-xs text-slate-500">No saved builds</p>
              ) : (
                savedBuilds.map((b) => (
                  <button
                    key={b.id}
                    onClick={() => loadBuild(b.id)}
                    className="w-full px-3 py-2 text-left text-xs hover:bg-slate-800 transition-colors"
                  >
                    <span className="text-slate-200">{b.name}</span>
                    <span className="text-slate-500 ml-2">
                      {new Date(b.updated_at).toLocaleDateString()}
                    </span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        <button
          onClick={createNewBuild}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs bg-[#00dc82] text-[#04120d] rounded-md font-semibold hover:bg-[#00b86d] transition-colors"
        >
          <Plus className="w-3 h-3" /> New Build
        </button>
      </div>

      {/* ── Empty state ── */}
      {!build && (
        <div className="flex-1 flex flex-col items-center justify-center text-center gap-4 opacity-50">
          <p className="text-slate-400 text-sm">No build loaded. Create a new build or load an existing one.</p>
        </div>
      )}

      {/* ── Component list ── */}
      {build && (
        <div className="flex-1 flex flex-col gap-2 overflow-y-auto">
          {allSlots.map((slot) => (
            <BuildRow
              key={slot}
              slot={slot}
              component={componentBySlot[slot] ?? null}
              onAdd={handleAddComponent}
              onPriceChange={handlePriceChange}
              onRemove={handleRemoveComponent}
            />
          ))}

          {/* Add custom slot */}
          <button
            onClick={addCustomSlot}
            className="text-xs text-slate-600 hover:text-slate-400 text-left pl-1 pt-1 transition-colors"
          >
            + Add custom slot
          </button>
        </div>
      )}

      {/* ── Eval panel (shown after evaluation) ── */}
      {evalResult && build && (
        <EvalPanel evaluation={evalResult} totalCost={totalCost} />
      )}

      {/* ── Pinned footer ── */}
      {build && (
        <div className="flex items-center gap-4 border-t border-slate-800 pt-3">
          <span className="text-sm font-mono text-slate-400">
            Total paid:{" "}
            <span className="text-slate-100 font-semibold">£{totalCost.toFixed(0)}</span>
          </span>
          <div className="flex-1" />
          {evalResult && (
            <button
              onClick={handleEvaluate}
              disabled={evaluating || build.components.length === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-[#00dc82]/40 text-[#00dc82] rounded-md hover:bg-[#00dc82]/10 transition-colors disabled:opacity-40"
            >
              <RotateCcw className="w-3 h-3" /> Re-evaluate
            </button>
          )}
          {!evalResult && (
            <button
              onClick={handleEvaluate}
              disabled={evaluating || build.components.length === 0}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-semibold bg-[#00dc82] text-[#04120d] rounded-md hover:bg-[#00b86d] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {evaluating ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Evaluating…</>
              ) : (
                <>🤖 Evaluate Build →</>
              )}
            </button>
          )}
        </div>
      )}

      {/* ── Entry modal ── */}
      {activeSlot && (
        <EntryModal
          slot={activeSlot}
          onConfirm={handleComponentConfirmed}
          onClose={() => setActiveSlot(null)}
        />
      )}
    </div>
  );
}
