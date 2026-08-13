"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { TabProps } from "./types";

export function OtherTab({ flip }: TabProps) {
  const [notes, setNotes] = useState(flip.notes ?? "");

  async function saveNotes() {
    await api.flips.patch(flip.id, { notes });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 flex flex-col gap-2">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Notes</p>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={saveNotes}
          placeholder="Add notes about this flip…"
          rows={5}
          className="w-full bg-transparent text-sm text-slate-300 placeholder-slate-700 resize-none outline-none focus:text-slate-200 transition-colors"
        />
      </div>
    </div>
  );
}
