"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface Slot {
  id: number;
  playbook_id: number;
  slot_type: string;
  is_customer_visible: boolean;
  tier_names: { budget: string; mid: string; high: string };
}

const SLOT_ORDER = ["cpu", "gpu", "ram", "storage", "cooling", "os"];

export default function SlotConfigPage() {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<number | null>(null);
  const [edits, setEdits] = useState<Record<number, Partial<Slot>>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.catalogue.slots();
      setSlots(data as Slot[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const patch = (id: number, changes: Partial<Slot>) => {
    setEdits(prev => ({ ...prev, [id]: { ...prev[id], ...changes } }));
  };

  const save = async (slot: Slot) => {
    setSaving(slot.id);
    try {
      const changes = edits[slot.id];
      if (changes) {
        await api.catalogue.updateSlot(slot.id, changes as Record<string, unknown>);
        setEdits(prev => { const next = { ...prev }; delete next[slot.id]; return next; });
        await load();
      }
    } finally {
      setSaving(null);
    }
  };

  const grouped: Record<number, Slot[]> = {};
  for (const s of slots) {
    (grouped[s.playbook_id] ??= []).push(s);
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Slot Configuration</h1>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {Object.entries(grouped).map(([playbookId, pbSlots]) => {
        const ordered = SLOT_ORDER.map(st => pbSlots.find(s => s.slot_type === st)).filter(Boolean) as Slot[];
        return (
          <div key={playbookId} className="mb-6 border rounded-lg overflow-hidden">
            <div className="px-4 py-2 bg-muted/30 border-b text-sm font-semibold">
              Playbook #{playbookId}
            </div>
            <table className="w-full text-sm">
              <thead className="border-b">
                <tr>
                  <th className="text-left px-3 py-2 text-muted-foreground font-medium">Slot</th>
                  <th className="text-center px-3 py-2 text-muted-foreground font-medium">Visible to customer</th>
                  <th className="text-left px-3 py-2 text-muted-foreground font-medium">Budget tier name</th>
                  <th className="text-left px-3 py-2 text-muted-foreground font-medium">Mid tier name</th>
                  <th className="text-left px-3 py-2 text-muted-foreground font-medium">High tier name</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {ordered.map(slot => {
                  const e = edits[slot.id] ?? {};
                  const visible = e.is_customer_visible ?? slot.is_customer_visible;
                  const names = { ...slot.tier_names, ...(e.tier_names ?? {}) };
                  const isDirty = !!edits[slot.id];
                  return (
                    <tr key={slot.id} className="border-b last:border-0 hover:bg-muted/10">
                      <td className="px-3 py-2 font-mono uppercase text-xs">{slot.slot_type}</td>
                      <td className="px-3 py-2 text-center">
                        <input
                          type="checkbox"
                          checked={visible}
                          onChange={e => patch(slot.id, { is_customer_visible: e.target.checked })}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className="border rounded px-2 py-0.5 text-xs bg-background w-full"
                          value={names.budget}
                          onChange={ev => patch(slot.id, { tier_names: { ...names, budget: ev.target.value } })}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className="border rounded px-2 py-0.5 text-xs bg-background w-full"
                          value={names.mid}
                          onChange={ev => patch(slot.id, { tier_names: { ...names, mid: ev.target.value } })}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className="border rounded px-2 py-0.5 text-xs bg-background w-full"
                          value={names.high}
                          onChange={ev => patch(slot.id, { tier_names: { ...names, high: ev.target.value } })}
                        />
                      </td>
                      <td className="px-3 py-2">
                        {isDirty && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={saving === slot.id}
                            onClick={() => save(slot)}
                          >
                            <Save className="w-3 h-3" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })}

      {!loading && Object.keys(grouped).length === 0 && (
        <p className="text-center text-muted-foreground text-sm py-12">
          No slots found. Run <code className="bg-muted px-1 rounded">seed_catalogue_slots.py</code> first.
        </p>
      )}
    </div>
  );
}
