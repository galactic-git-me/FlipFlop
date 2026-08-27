"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Package, Plus, Trash2, Edit2, X, RefreshCw, DollarSign,
  MemoryStick, Cpu, HardDrive, CircuitBoard, Zap, Wind, MonitorSpeaker, Layers3,
  History, AlertTriangle, TrendingUp,
  BrainCircuit, MapPin, Tag,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, type ManualBuildSummary } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

interface InventoryItem {
  id: number;
  component_name: string;
  component_type: string;
  quantity: number;
  quantity_unallocated: number;
  actual_cost: number;
  purchase_date: string;
  source: string | null;
  notes: string | null;
  created_at: string;
}

interface ManualBuildAssignment {
  allocation_id: number;
  inventory_item_id: number;
  quantity_allocated: number;
  build_id: number;
  manual_build_id: number;
  build_name: string;
  lifecycle_status: "reserved" | "consumed";
}

interface InventoryHealth {
  free_units: number; reserved_units: number; consumed_units: number;
  free_value: number; reserved_value: number; consumed_value: number; expected_profit: number;
  stale_items: Array<{ id: number; name: string; days: number; value: number }>;
  excess_stock: Array<{ component_type: string; free_units: number }>;
  build_blockers: Array<{ build_id: number; build_name: string; missing: string[] }>;
}

interface InventoryEvent {
  id: number; event_type: string; quantity: number; manual_build_id: number | null;
  build_name: string | null; detail: Record<string, unknown>; created_at: string;
}

interface InventoryUnit {
  id: number; inventory_item_id: number; unit_number: number; serial_number: string | null;
  condition_grade: string; status: string; storage_location: string | null;
  warranty_expires_at: string | null; test_results: Record<string, unknown>;
  exception_reason: string | null; writeoff_amount: number | null;
}

interface FormData {
  component_name: string;
  component_type: string;
  quantity: number;
  actual_cost: number;
  purchase_date: string;
  source: string;
  notes: string;
}

const COMPONENT_TYPES = [
  { id: "gpu", label: "Graphics Card", icon: <MonitorSpeaker className="w-4 h-4" /> },
  { id: "cpu", label: "Processor", icon: <Cpu className="w-4 h-4" /> },
  { id: "ram", label: "RAM", icon: <MemoryStick className="w-4 h-4" /> },
  { id: "motherboard", label: "Motherboard", icon: <CircuitBoard className="w-4 h-4" /> },
  { id: "cooler", label: "Cooling", icon: <Wind className="w-4 h-4" /> },
  { id: "ssd", label: "Storage", icon: <HardDrive className="w-4 h-4" /> },
  { id: "psu", label: "Power Supply", icon: <Zap className="w-4 h-4" /> },
];

export default function InventoryPage() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [stats, setStats] = useState({ total_cost: 0, total_quantity: 0, total_items: 0 });
  const [draftBuilds, setDraftBuilds] = useState<ManualBuildSummary[]>([]);
  const [selectedDraftBuildId, setSelectedDraftBuildId] = useState<number | null>(null);
  const [assignments, setAssignments] = useState<ManualBuildAssignment[]>([]);
  const [activeTab, setActiveTab] = useState<"free" | "assigned">("free");
  const [selectedItemIds, setSelectedItemIds] = useState<Set<number>>(new Set());
  const [assigning, setAssigning] = useState(false);
  const [assignmentMessage, setAssignmentMessage] = useState<string | null>(null);
  const [health, setHealth] = useState<InventoryHealth | null>(null);
  const [historyItem, setHistoryItem] = useState<InventoryItem | null>(null);
  const [historyEvents, setHistoryEvents] = useState<InventoryEvent[]>([]);
  const [unitsItem, setUnitsItem] = useState<InventoryItem | null>(null);
  const [units, setUnits] = useState<InventoryUnit[]>([]);
  const [showBulkModal, setShowBulkModal] = useState(false);

  const [form, setForm] = useState<FormData>({
    component_name: "",
    component_type: "gpu",
    quantity: 1,
    actual_cost: 0,
    purchase_date: new Date().toISOString().split("T")[0],
    source: "eBay",
    notes: "",
  });

  const loadInventory = useCallback(async () => {
    setLoading(true);
    try {
      const [itemsData, statsData, buildsData, assignmentsData, healthData] = await Promise.all([
        fetch("/api/inventory/").then(r => r.json()),
        fetch("/api/inventory/summary/stats").then(r => r.json()),
        api.manualBuilds.list(),
        fetch("/api/inventory-allocations/manual-build-assignments").then(r => r.json()),
        api.inventory.health(),
      ]);
      setItems(itemsData);
      setStats(statsData);
      setDraftBuilds(buildsData.filter(build => build.status === "in_progress"));
      setAssignments(assignmentsData);
      setHealth(healthData);
    } catch {
      setItems([]);
      setDraftBuilds([]);
      setAssignments([]);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadInventory(), 0);
    return () => window.clearTimeout(timer);
  }, [loadInventory]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      let response: Response;
      if (editingId) {
        response = await fetch(`/api/inventory/${editingId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
      } else {
        response = await fetch("/api/inventory/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
      }
      if (!response.ok) throw new Error((await response.json()).detail || "Unable to save item");
      const savedItem = await response.json() as InventoryItem;
      if (selectedDraftBuildId) {
        const assignmentResponse = await fetch(`/api/inventory-allocations/manual-builds/${selectedDraftBuildId}/bulk`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ inventory_item_ids: [savedItem.id] }),
        });
        if (!assignmentResponse.ok) throw new Error((await assignmentResponse.json()).detail || "Unable to assign item");
      }
      setShowForm(false);
      setEditingId(null);
      setForm({
        component_name: "",
        component_type: "gpu",
        quantity: 1,
        actual_cost: 0,
        purchase_date: new Date().toISOString().split("T")[0],
        source: "eBay",
        notes: "",
      });
      setSelectedDraftBuildId(null);
      await loadInventory();
    } catch (err) {
      alert("Error saving item: " + String(err));
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this item?")) return;
    try {
      await fetch(`/api/inventory/${id}`, { method: "DELETE" });
      await loadInventory();
    } catch (err) {
      alert("Error deleting item: " + String(err));
    }
  };

  const handleEdit = (item: InventoryItem) => {
    setForm({
      component_name: item.component_name,
      component_type: item.component_type,
      quantity: item.quantity,
      actual_cost: item.actual_cost,
      purchase_date: item.purchase_date.split("T")[0],
      source: item.source || "",
      notes: item.notes || "",
    });
    setEditingId(item.id);
    setSelectedDraftBuildId(null);
    setShowForm(true);
  };

  const getAssignmentsForItem = (itemId: number) => assignments.filter(a => a.inventory_item_id === itemId);

  const handleAssignSelected = async () => {
    if (!selectedDraftBuildId || selectedItemIds.size === 0) return;
    setAssigning(true);
    setAssignmentMessage(null);
    try {
      const response = await fetch(`/api/inventory-allocations/manual-builds/${selectedDraftBuildId}/bulk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inventory_item_ids: Array.from(selectedItemIds) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Unable to assign inventory");
      setAssignmentMessage(`${result.units_assigned} unit${result.units_assigned === 1 ? "" : "s"} assigned to ${result.build_name}.`);
      setSelectedItemIds(new Set());
      setSelectedDraftBuildId(null);
      await loadInventory();
    } catch (error) {
      setAssignmentMessage(error instanceof Error ? error.message : "Unable to assign inventory");
    } finally {
      setAssigning(false);
    }
  };

  const showHistory = async (item: InventoryItem) => {
    setHistoryItem(item);
    setHistoryEvents([]);
    try {
      setHistoryEvents(await api.inventory.events(item.id));
    } catch {
      setHistoryEvents([]);
    }
  };

  const showUnits = async (item: InventoryItem) => {
    setUnitsItem(item);
    setUnits([]);
    try {
      setUnits(await api.inventory.units(item.id));
    } catch {
      setUnits([]);
    }
  };

  const updateUnit = async (unitId: number, data: Record<string, unknown>) => {
    try {
      await api.inventory.updateUnit(unitId, data);
      if (unitsItem) setUnits(await api.inventory.units(unitsItem.id));
      await loadInventory();
    } catch (error) {
      alert(error instanceof Error ? error.message : "Unable to update inventory unit");
    }
  };

  const copyUnitLabel = async (unitId: number) => {
    const label = await api.inventory.unitLabel(unitId);
    await navigator.clipboard.writeText(`${label.sku}\n${label.component_name}\nSerial: ${label.serial_number || "—"}\nLocation: ${label.location || "—"}\n${window.location.origin}${label.qr_payload}`);
  };

  const handleBulkUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const data = JSON.parse(text);

      const response = await fetch("/api/inventory/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      const result = await response.json();

      if (!response.ok) {
        alert(`Error: ${result.detail || "Failed to import"}`);
        return;
      }

      alert(`✅ Imported ${result.created} items${result.errors?.length ? `\n⚠️ ${result.errors.length} errors:\n${result.errors.join("\n")}` : ""}`);
      await loadInventory();

      // Reset file input
      e.target.value = "";
    } catch (err) {
      if (err instanceof SyntaxError) {
        alert("Invalid JSON format. Please check your file.");
      } else {
        alert("Error uploading file: " + String(err));
      }
    }
  };

  const copySchemaToClipboard = () => {
    const schema = `JSON Format for Bulk Inventory Upload:

{
  "items": [
    {
      "component_name": "string (required) - Name of component, e.g. 'RTX 4070 12GB'",
      "component_type": "string (required) - Type: gpu, cpu, ram, motherboard, cooler, ssd, or psu",
      "quantity": "integer (required) - Number of units",
      "base_price": "number (required) - Price per unit before shipping/discount",
      "shipping_cost": "number (optional) - Shipping cost per unit, default: 0",
      "discount_amount": "number (optional) - Discount per unit, default: 0",
      "purchase_date": "string (required) - Date in YYYY-MM-DD format",
      "source": "string (optional) - Where purchased (eBay, Amazon, Newegg, etc.)",
      "notes": "string (optional) - Any notes (negotiated price, auction, etc.)"
    }
  ]
}

Example:
{
  "items": [
    {
      "component_name": "NVIDIA RTX 4070 12GB",
      "component_type": "gpu",
      "quantity": 1,
      "base_price": 450.00,
      "shipping_cost": 15.00,
      "discount_amount": 0,
      "purchase_date": "2026-06-15",
      "source": "eBay",
      "notes": "Excellent condition"
    }
  ]
}`;
    navigator.clipboard.writeText(schema);
    alert("✅ Schema copied to clipboard!");
  };

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            <Package className="w-5 h-5" /> Inventory
          </h1>
          <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
            Track components you own and actual costs paid
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/inventory/intelligence" className="inline-flex items-center gap-2 rounded-lg border border-[#2d4a6b] bg-[#0d1320] px-4 py-2 text-sm text-white transition-all hover:border-[#00dc82]/50 hover:text-[#00dc82]">
            <BrainCircuit className="h-4 w-4" /> Intelligence
          </Link>
          <Button
            onClick={() => { setShowForm(!showForm); setEditingId(null); }}
            className="gap-2"
          >
            <Plus className="w-4 h-4" /> Add Item
          </Button>
          <Button
            onClick={() => setShowBulkModal(true)}
            variant="outline"
            className="gap-2"
          >
            <RefreshCw className="w-4 h-4" /> Bulk Upload
          </Button>
          <input
            id="bulk-upload"
            type="file"
            accept=".json"
            style={{ display: "none" }}
            onChange={handleBulkUpload}
          />
        </div>
      </div>

      {/* Stats */}
      {!loading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-4">
            <div className="text-slate-600 text-sm">Total Items</div>
            <div className="text-2xl font-bold text-slate-200 mt-1">{stats.total_items}</div>
          </div>
          <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-4">
            <div className="text-slate-600 text-sm">Total Quantity</div>
            <div className="text-2xl font-bold text-slate-200 mt-1">{stats.total_quantity}</div>
          </div>
          <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-4">
            <div className="text-slate-600 text-sm flex items-center gap-1">
              <DollarSign className="w-4 h-4" /> Total Cost
            </div>
            <div className="text-2xl font-bold text-amber-400 mt-1">{formatCurrency(stats.total_cost)}</div>
          </div>
          <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-4">
            <div className="flex items-center gap-1 text-sm text-slate-500"><TrendingUp className="h-4 w-4" /> Expected stock profit</div>
            <div className="mt-1 text-2xl font-bold text-[#00dc82]">{formatCurrency(health?.expected_profit ?? 0)}</div>
          </div>
        </div>
      )}

      {!loading && health && (
        <section className="grid gap-3 lg:grid-cols-[1.2fr_1fr_1fr]" aria-label="Inventory health">
          <div className="rounded-lg border border-[#1e2d45] bg-[#0a1119] p-4">
            <h2 className="text-sm font-semibold text-slate-200">Stock lifecycle</h2>
            <div className="mt-3 grid grid-cols-3 gap-2">
              {[
                { label: "Free", units: health.free_units, value: health.free_value, color: "text-cyan-300" },
                { label: "Reserved", units: health.reserved_units, value: health.reserved_value, color: "text-amber-300" },
                { label: "Consumed", units: health.consumed_units, value: health.consumed_value, color: "text-[#00dc82]" },
              ].map(metric => <div key={metric.label} className="rounded-md bg-[#0d1624] p-3"><p className="text-[10px] uppercase tracking-wider text-slate-500">{metric.label}</p><p className={`mt-1 text-lg font-bold ${metric.color}`}>{metric.units}</p><p className="text-xs text-slate-400">{formatCurrency(metric.value)}</p></div>)}
            </div>
          </div>
          <div className="rounded-lg border border-[#1e2d45] bg-[#0a1119] p-4">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-200"><AlertTriangle className="h-4 w-4 text-amber-300" /> Build blockers</h2>
            <div className="mt-3 space-y-2 text-xs">
              {health.build_blockers.length === 0 ? <p className="text-slate-500">No active builds are waiting on parts.</p> : health.build_blockers.slice(0, 3).map(blocker => <div key={blocker.build_id}><p className="font-semibold text-slate-300">{blocker.build_name}</p><p className="truncate text-slate-500">Missing: {blocker.missing.join(", ")}</p></div>)}
            </div>
          </div>
          <div className="rounded-lg border border-[#1e2d45] bg-[#0a1119] p-4">
            <h2 className="text-sm font-semibold text-slate-200">Stock risks</h2>
            <div className="mt-3 space-y-2 text-xs text-slate-400">
              <p><span className="font-bold text-amber-300">{health.stale_items.length}</span> free rows held for 90+ days</p>
              <p><span className="font-bold text-cyan-300">{health.excess_stock.length}</span> component types with 3+ free units</p>
              {health.stale_items[0] && <p className="truncate text-slate-500">Oldest: {health.stale_items[0].name} · {health.stale_items[0].days}d</p>}
            </div>
          </div>
        </section>
      )}

      {/* Form */}
      {showForm && (
        <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-slate-200">{editingId ? "Edit Item" : "Add New Item"}</h2>
            <button
              onClick={() => { setShowForm(false); setEditingId(null); }}
              className="text-slate-600 hover:text-slate-400"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Component Name</label>
                <input
                  type="text"
                  value={form.component_name}
                  onChange={e => setForm({ ...form, component_name: e.target.value })}
                  placeholder="e.g., RTX 3060 12GB"
                  className="w-full px-3 py-2 bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 text-sm focus:border-[#00dc82] outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Type</label>
                <select
                  value={form.component_type}
                  onChange={e => setForm({ ...form, component_type: e.target.value })}
                  className="w-full px-3 py-2 bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 text-sm focus:border-[#00dc82] outline-none"
                >
                  {COMPONENT_TYPES.map(t => (
                    <option key={t.id} value={t.id}>{t.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Quantity</label>
                <input
                  type="number"
                  min="1"
                  value={form.quantity}
                  onChange={e => setForm({ ...form, quantity: parseInt(e.target.value) || 1 })}
                  className="w-full px-3 py-2 bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 text-sm focus:border-[#00dc82] outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Actual Cost (£)</label>
                <input
                  type="number"
                  step="0.01"
                  value={form.actual_cost}
                  onChange={e => setForm({ ...form, actual_cost: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 text-sm focus:border-[#00dc82] outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Purchase Date</label>
                <input
                  type="date"
                  value={form.purchase_date}
                  onChange={e => setForm({ ...form, purchase_date: e.target.value })}
                  className="w-full px-3 py-2 bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 text-sm focus:border-[#00dc82] outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Source</label>
                <input
                  type="text"
                  value={form.source}
                  onChange={e => setForm({ ...form, source: e.target.value })}
                  placeholder="eBay, Amazon, Local, Auction..."
                  className="w-full px-3 py-2 bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 text-sm focus:border-[#00dc82] outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Notes</label>
              <textarea
                value={form.notes}
                onChange={e => setForm({ ...form, notes: e.target.value })}
                placeholder="Negotiated price, shipping included, auction win, etc."
                className="w-full px-3 py-2 bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 text-sm focus:border-[#00dc82] outline-none resize-none"
                rows={2}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Assign to draft build</label>
              <select
                value={selectedDraftBuildId || ""}
                onChange={e => setSelectedDraftBuildId(e.target.value ? parseInt(e.target.value) : null)}
                className="w-full px-3 py-2 bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 text-sm focus:border-[#00dc82] outline-none"
              >
                <option value="">Unassigned</option>
                {draftBuilds.map(build => (
                  <option key={build.id} value={build.id}>{build.name}</option>
                ))}
              </select>
              {draftBuilds.length === 0 && (
                <p className="mt-1 text-xs text-slate-500">Create an in-progress draft build first to assign inventory.</p>
              )}
            </div>

            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => { setShowForm(false); setEditingId(null); }}
                className="px-4 py-2 text-sm border border-[#1e2d45] text-slate-400 hover:text-slate-300 rounded"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 text-sm bg-[#00dc82]/20 text-[#00dc82] border border-[#00dc82]/30 rounded hover:bg-[#00dc82]/30"
              >
                {editingId ? "Update" : "Add"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Inventory status tabs and bulk assignment */}
      {!loading && items.length > 0 && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1e2d45]">
            <div className="flex" role="tablist" aria-label="Inventory status">
              {([
                { id: "free" as const, label: "Free", count: items.filter(item => item.quantity_unallocated > 0).length },
                { id: "assigned" as const, label: "Assigned", count: new Set(assignments.map(item => item.inventory_item_id)).size },
              ]).map(tab => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  onClick={() => { setActiveTab(tab.id); setSelectedItemIds(new Set()); setAssignmentMessage(null); }}
                  className={`cursor-pointer border-b-2 px-5 py-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00dc82] ${activeTab === tab.id ? "border-[#00dc82] text-[#00dc82]" : "border-transparent text-slate-500 hover:text-slate-300"}`}
                >
                  {tab.label} <span className="ml-1.5 rounded-full bg-[#172235] px-2 py-0.5 text-xs text-slate-300">{tab.count}</span>
                </button>
              ))}
            </div>
            {activeTab === "free" && selectedItemIds.size > 0 && (
              <div className="mb-2 flex flex-wrap items-center gap-2 rounded-lg border border-[#00dc82]/30 bg-[#00dc82]/5 p-2">
                <span className="px-1 text-xs font-semibold text-[#00dc82]">{selectedItemIds.size} selected</span>
                <label htmlFor="bulk-draft-build" className="sr-only">Draft build</label>
                <select
                  id="bulk-draft-build"
                  value={selectedDraftBuildId || ""}
                  onChange={event => setSelectedDraftBuildId(event.target.value ? Number(event.target.value) : null)}
                  className="min-w-52 cursor-pointer rounded border border-[#30405c] bg-[#0d1320] px-3 py-2 text-sm text-slate-200 outline-none focus:border-[#00dc82]"
                >
                  <option value="">Choose a draft build…</option>
                  {draftBuilds.map(build => <option key={build.id} value={build.id}>{build.name}</option>)}
                </select>
                <Button onClick={() => void handleAssignSelected()} disabled={!selectedDraftBuildId || assigning} className="gap-2">
                  {assigning ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Layers3 className="h-4 w-4" />}
                  Assign to build
                </Button>
              </div>
            )}
          </div>
          {assignmentMessage && (
            <div role="status" className="rounded border border-[#00dc82]/25 bg-[#00dc82]/5 px-3 py-2 text-sm text-slate-300">{assignmentMessage}</div>
          )}
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-slate-500 gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading inventory…
        </div>
      ) : items.length === 0 ? (
        <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-8 text-center">
          <Package className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">No inventory items yet. Add one to get started.</p>
        </div>
      ) : (() => {
        const visibleItems = activeTab === "free"
          ? items.filter(item => item.quantity_unallocated > 0)
          : items.filter(item => getAssignmentsForItem(item.id).length > 0);
        const allVisibleSelected = visibleItems.length > 0 && visibleItems.every(item => selectedItemIds.has(item.id));
        return visibleItems.length === 0 ? (
          <div className="rounded-lg border border-[#1e2d45] bg-[#0a1119] p-8 text-center text-slate-400">
            No {activeTab} inventory items.
          </div>
        ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e2d45]">
                <th className="w-12 px-4 py-3 text-left">
                  <input
                    type="checkbox"
                    aria-label={`Select all ${activeTab} inventory items`}
                    checked={allVisibleSelected}
                    onChange={event => setSelectedItemIds(event.target.checked ? new Set(visibleItems.map(item => item.id)) : new Set())}
                    className="h-4 w-4 cursor-pointer accent-[#00dc82]"
                  />
                </th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Component</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Type</th>
                <th className="text-center px-4 py-3 text-slate-400 font-medium">{activeTab === "free" ? "Free / Total" : "Assigned / Total"}</th>
                <th className="text-right px-4 py-3 text-slate-400 font-medium">Cost Each</th>
                <th className="text-right px-4 py-3 text-slate-400 font-medium">Total</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Source</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Date</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Assigned To</th>
                <th className="text-center px-4 py-3 text-slate-400 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleItems.map(item => {
                const itemAssignments = getAssignmentsForItem(item.id);
                const assignedQuantity = itemAssignments.reduce((total, assignment) => total + assignment.quantity_allocated, 0);
                return (
                  <tr key={item.id} className={`border-b border-[#1e2d45] transition-colors hover:bg-[#0a1119] ${selectedItemIds.has(item.id) ? "bg-[#00dc82]/5" : ""}`}>
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        aria-label={`Select ${item.component_name}`}
                        checked={selectedItemIds.has(item.id)}
                        onChange={event => setSelectedItemIds(previous => {
                          const next = new Set(previous);
                          if (event.target.checked) next.add(item.id); else next.delete(item.id);
                          return next;
                        })}
                        className="h-4 w-4 cursor-pointer accent-[#00dc82]"
                      />
                    </td>
                    <td className="px-4 py-3 text-slate-200">{item.component_name}</td>
                    <td className="px-4 py-3 text-slate-400">{item.component_type}</td>
                    <td className="px-4 py-3 text-center text-slate-300">{activeTab === "free" ? item.quantity_unallocated : assignedQuantity} / {item.quantity}</td>
                    <td className="px-4 py-3 text-right text-amber-400">{formatCurrency(item.actual_cost)}</td>
                    <td className="px-4 py-3 text-right text-amber-400 font-semibold">{formatCurrency(item.actual_cost * item.quantity)}</td>
                    <td className="px-4 py-3 text-slate-400">{item.source || "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{formatRelativeTime(new Date(item.purchase_date))}</td>
                    <td className="px-4 py-3 text-slate-400">
                      {itemAssignments.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {itemAssignments.map(assignment => (
                            <span key={assignment.allocation_id} className="rounded bg-[#00dc82]/10 px-2 py-1 text-xs text-[#00dc82]">
                              {assignment.build_name} · {assignment.lifecycle_status} ({assignment.quantity_allocated})
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-slate-600">Unassigned</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex justify-center gap-2">
                        <button
                          onClick={() => void showUnits(item)}
                          className="cursor-pointer p-1 text-slate-500 transition-colors hover:text-violet-300"
                          title="Manage physical units"
                          aria-label={`Manage units for ${item.component_name}`}
                        >
                          <Tag className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => void showHistory(item)}
                          className="cursor-pointer p-1 text-slate-500 transition-colors hover:text-cyan-300"
                          title="View history"
                          aria-label={`View history for ${item.component_name}`}
                        >
                          <History className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleEdit(item)}
                          className="text-slate-500 hover:text-[#00dc82] p-1"
                          title="Edit"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(item.id)}
                          className="text-slate-500 hover:text-red-400 p-1"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        );
      })()}

      {unitsItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-labelledby="inventory-units-title">
          <div className="max-h-[88vh] w-full max-w-5xl overflow-y-auto rounded-xl border border-[#263650] bg-[#08111d] p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-3"><div><h2 id="inventory-units-title" className="flex items-center gap-2 font-semibold text-slate-100"><Tag className="h-4 w-4 text-violet-300" /> Physical units</h2><p className="mt-1 text-sm text-slate-400">{unitsItem.component_name} · receiving, testing and storage</p></div><button type="button" onClick={() => setUnitsItem(null)} className="cursor-pointer rounded p-1 text-slate-500 hover:text-white" aria-label="Close physical units"><X className="h-5 w-5" /></button></div>
            <div className="mt-4 space-y-3">
              {units.map(unit => (
                <div key={unit.id} className="rounded-lg border border-white/8 bg-black/20 p-4">
                  <div className="grid gap-3 md:grid-cols-[70px_1fr_150px_160px_1fr_auto] md:items-end">
                    <div><p className="text-[10px] uppercase text-slate-500">Unit</p><p className="mt-1 font-mono font-bold text-cyan-300">#{unit.unit_number}</p></div>
                    <label className="text-[10px] uppercase text-slate-500">Serial number<input defaultValue={unit.serial_number ?? ""} onBlur={event => { if (event.target.value !== (unit.serial_number ?? "")) void updateUnit(unit.id, { serial_number: event.target.value || null }); }} className="mt-1 w-full rounded border border-white/10 bg-slate-950 px-2 py-1.5 text-xs normal-case text-slate-200" /></label>
                    <label className="text-[10px] uppercase text-slate-500">Condition<select value={unit.condition_grade} onChange={event => void updateUnit(unit.id, { condition_grade: event.target.value })} className="mt-1 w-full cursor-pointer rounded border border-white/10 bg-slate-950 px-2 py-1.5 text-xs normal-case text-slate-200"><option value="unknown">Unknown</option><option value="new">New</option><option value="excellent">Excellent</option><option value="good">Good</option><option value="fair">Fair</option><option value="parts">Parts only</option></select></label>
                    <label className="text-[10px] uppercase text-slate-500">Status<select value={unit.status} onChange={event => void updateUnit(unit.id, { status: event.target.value })} className="mt-1 w-full cursor-pointer rounded border border-white/10 bg-slate-950 px-2 py-1.5 text-xs normal-case text-slate-200">{["ordered", "dispatched", "delivered", "inspection", "free", "reserved", "consumed", "quarantined", "faulty", "returned", "spares", "written_off", "sold"].map(status => <option key={status} value={status}>{status.replace("_", " ")}</option>)}</select></label>
                    <label className="text-[10px] uppercase text-slate-500">Location<div className="relative mt-1"><MapPin className="absolute left-2 top-2 h-3.5 w-3.5 text-slate-600" /><input defaultValue={unit.storage_location ?? ""} onBlur={event => { if (event.target.value !== (unit.storage_location ?? "")) void updateUnit(unit.id, { storage_location: event.target.value || null }); }} placeholder="Shelf / box" className="w-full rounded border border-white/10 bg-slate-950 py-1.5 pl-7 pr-2 text-xs normal-case text-slate-200" /></div></label>
                    <button type="button" onClick={() => void copyUnitLabel(unit.id)} className="flex h-8 cursor-pointer items-center gap-1 rounded border border-violet-300/20 px-2 text-xs text-violet-300 hover:bg-violet-300/10"><Tag className="h-3.5 w-3.5" /> Copy label</button>
                  </div>
                  {(unit.status === "quarantined" || unit.status === "faulty" || unit.status === "returned" || unit.status === "spares" || unit.status === "written_off") && <div className="mt-3 grid gap-2 border-t border-white/5 pt-3 sm:grid-cols-[1fr_160px]"><label className="text-[10px] uppercase text-slate-500">Exception / return reason<input defaultValue={unit.exception_reason ?? ""} onBlur={event => void updateUnit(unit.id, { exception_reason: event.target.value || null })} className="mt-1 w-full rounded border border-white/10 bg-slate-950 px-2 py-1.5 text-xs normal-case text-slate-200" /></label><label className="text-[10px] uppercase text-slate-500">Write-off (£)<input type="number" min={0} step="0.01" defaultValue={unit.writeoff_amount ?? ""} onBlur={event => void updateUnit(unit.id, { writeoff_amount: event.target.value ? Number(event.target.value) : null })} className="mt-1 w-full rounded border border-white/10 bg-slate-950 px-2 py-1.5 text-xs normal-case text-slate-200" /></label></div>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {historyItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-labelledby="inventory-history-title">
          <div className="max-h-[80vh] w-full max-w-xl overflow-y-auto rounded-xl border border-[#263650] bg-[#08111d] p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div><h2 id="inventory-history-title" className="flex items-center gap-2 font-semibold text-slate-100"><History className="h-4 w-4 text-cyan-300" /> Inventory history</h2><p className="mt-1 text-sm text-slate-400">{historyItem.component_name}</p></div>
              <button type="button" onClick={() => setHistoryItem(null)} className="cursor-pointer rounded p-1 text-slate-500 hover:text-white" aria-label="Close inventory history"><X className="h-5 w-5" /></button>
            </div>
            <div className="mt-5 space-y-0">
              {historyEvents.length === 0 ? <p className="rounded-lg border border-white/5 p-4 text-sm text-slate-500">No lifecycle events have been recorded yet.</p> : historyEvents.map((event, index) => (
                <div key={event.id} className="relative flex gap-3 pb-5">
                  {index < historyEvents.length - 1 && <span className="absolute left-[7px] top-4 h-full w-px bg-[#263650]" />}
                  <span className="relative mt-1.5 h-3.5 w-3.5 shrink-0 rounded-full border-2 border-cyan-300 bg-[#08111d]" />
                  <div className="min-w-0"><p className="text-sm font-semibold capitalize text-slate-200">{event.event_type} · {event.quantity}</p><p className="text-xs text-slate-500">{event.build_name ? `${event.build_name} · ` : ""}{new Date(event.created_at).toLocaleString()}</p></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Bulk Upload Modal */}
      {showBulkModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[#0a1119] border border-[#1e2d45] rounded-lg p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-slate-200">Bulk Upload - JSON Schema Reference</h2>
              <button
                onClick={() => setShowBulkModal(false)}
                className="text-slate-600 hover:text-slate-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="bg-[#0d1320] border border-[#1e2d45] rounded p-4">
                <h3 className="text-sm font-semibold text-slate-300 mb-3">Required & Optional Fields</h3>
                <div className="space-y-2 text-xs text-slate-400 font-mono">
                  <div><span className="text-amber-400">component_name</span> (required) - Component name, e.g. &quot;RTX 4070 12GB&quot;</div>
                  <div><span className="text-amber-400">component_type</span> (required) - gpu | cpu | ram | motherboard | cooler | ssd | psu</div>
                  <div><span className="text-amber-400">quantity</span> (required) - Number of units (integer)</div>
                  <div><span className="text-amber-400">base_price</span> (required) - Price per unit (number)</div>
                  <div><span className="text-green-400">shipping_cost</span> (optional) - Shipping per unit, default: 0</div>
                  <div><span className="text-green-400">discount_amount</span> (optional) - Discount per unit, default: 0</div>
                  <div><span className="text-amber-400">purchase_date</span> (required) - YYYY-MM-DD format</div>
                  <div><span className="text-green-400">source</span> (optional) - eBay, Amazon, Newegg, etc.</div>
                  <div><span className="text-green-400">notes</span> (optional) - Negotiated price, auction, etc.</div>
                </div>
              </div>

              <div className="bg-[#0d1320] border border-[#1e2d45] rounded p-4">
                <h3 className="text-sm font-semibold text-slate-300 mb-2">Example JSON</h3>
                <pre className="text-xs text-slate-400 overflow-x-auto bg-black/40 p-3 rounded">
{`{
  "items": [
    {
      "component_name": "RTX 4070",
      "component_type": "gpu",
      "quantity": 1,
      "base_price": 450.00,
      "shipping_cost": 15.00,
      "discount_amount": 0,
      "purchase_date": "2026-06-15",
      "source": "eBay",
      "notes": "Excellent condition"
    }
  ]
}`}
                </pre>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  onClick={copySchemaToClipboard}
                  className="flex-1 px-4 py-2 bg-[#00dc82]/20 text-[#00dc82] border border-[#00dc82]/30 rounded hover:bg-[#00dc82]/30 text-sm font-medium flex items-center justify-center gap-2"
                >
                  <RefreshCw className="w-4 h-4" /> Copy Schema to Clipboard
                </button>
                <button
                  onClick={() => document.getElementById("bulk-upload")?.click()}
                  className="flex-1 px-4 py-2 bg-blue-600/20 text-blue-400 border border-blue-600/30 rounded hover:bg-blue-600/30 text-sm font-medium"
                >
                  Select JSON File
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
