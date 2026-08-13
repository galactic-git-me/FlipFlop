"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, ImagePlus, Video } from "lucide-react";
import { api } from "@/lib/api";
import type { TabProps } from "./types";

// Row 48: minimum-shot checklist before a build can be marked listing-ready.
// Row 41: boot-up/benchmark video slot — soft-required (default proposed,
// confirm once): a checklist item with an override, not a hard block, since
// eBay caps video at one per listing and not every build gets a clean run.
const SHOT_CHECKLIST = ["Front", "Side", "Internals", "Cable routing", "Ports"];

function storageKey(flipId: number) {
  return `flip-${flipId}-photo-checklist`;
}

export function PhotosTab({ flip, onFlipUpdated }: TabProps) {
  const [generating, setGenerating] = useState(false);
  const [images, setImages] = useState<string[]>(flip.generated_images_urls ?? []);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [videoDone, setVideoDone] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey(flip.id));
      if (raw) {
        const parsed = JSON.parse(raw) as { shots: string[]; video: boolean };
        setChecked(new Set(parsed.shots));
        setVideoDone(!!parsed.video);
      }
    } catch {
      // ignore corrupt local state
    }
  }, [flip.id]);

  function persist(nextChecked: Set<string>, nextVideo: boolean) {
    try {
      localStorage.setItem(
        storageKey(flip.id),
        JSON.stringify({ shots: Array.from(nextChecked), video: nextVideo })
      );
    } catch {
      // best-effort only
    }
  }

  function toggleShot(shot: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      next.has(shot) ? next.delete(shot) : next.add(shot);
      persist(next, videoDone);
      return next;
    });
  }

  function toggleVideo() {
    setVideoDone((prev) => {
      const next = !prev;
      persist(checked, next);
      return next;
    });
  }

  async function handleGenerateImages() {
    setGenerating(true);
    try {
      const result = await api.flips.generateImages(flip.id);
      setImages(result.images ?? []);
      const updated = await api.flips.get(flip.id);
      onFlipUpdated(updated as import("./types").Flip);
    } finally {
      setGenerating(false);
    }
  }

  const allShotsDone = SHOT_CHECKLIST.every((s) => checked.has(s));

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Minimum-shot checklist</p>
          {allShotsDone && (
            <span className="text-xs font-bold text-emerald-400 flex items-center gap-1">
              <Check className="w-3 h-3" /> Complete
            </span>
          )}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {SHOT_CHECKLIST.map((shot) => {
            const done = checked.has(shot);
            return (
              <button
                key={shot}
                onClick={() => toggleShot(shot)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium transition-colors ${
                  done
                    ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-400"
                    : "border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-600"
                }`}
              >
                <span className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center ${
                  done ? "bg-emerald-500 border-emerald-500" : "border-slate-600"
                }`}>
                  {done && <Check className="w-2.5 h-2.5 text-white" />}
                </span>
                {shot}
              </button>
            );
          })}
        </div>
      </div>

      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
        <button
          onClick={toggleVideo}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium transition-colors self-start ${
            videoDone
              ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-400"
              : "border-amber-500/30 bg-amber-500/5 text-amber-400"
          }`}
        >
          <Video className="w-3.5 h-3.5" />
          {videoDone ? "Boot/benchmark video attached" : "Boot/benchmark video — not attached (soft-required)"}
        </button>
        <p className="text-[11px] text-slate-600">
          Row 41: up to 1 minute, MP4/MOV, one per listing. Recommended for a high-ticket,
          hard-to-verify-from-photos item, but not a hard block on listing-ready.
        </p>
      </div>

      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Generated listing images</p>
          <button
            onClick={handleGenerateImages}
            disabled={generating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#00dc82] text-[#04120d] rounded-md font-semibold hover:bg-[#00b86d] transition-colors disabled:opacity-40"
          >
            {generating ? <><Loader2 className="w-3 h-3 animate-spin" /> Generating…</> : <><ImagePlus className="w-3 h-3" /> Generate</>}
          </button>
        </div>
        {images.length > 0 ? (
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
            {images.map((url, i) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={i} src={url} alt={`Generated listing photo ${i + 1}`} className="rounded-lg border border-slate-800 aspect-square object-cover" />
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-600 italic">No branded images generated yet.</p>
        )}
      </div>
    </div>
  );
}
