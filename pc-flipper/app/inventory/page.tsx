"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Package, Plus, Trash2, Edit2, X, RefreshCw, DollarSign,
  MemoryStick, Cpu, HardDrive, CircuitBoard, Zap, Wind, MonitorSpeaker,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

interface InventoryItem {
  id: number;
  component_name: string;
  component_type: string;
  quantity: number;
  actual_cost: number;
  purchase_date: string;
  source: string | null;
  notes: string | null;
  created_at: string;
}

interface Flip {
  id: number;
  name?: string;
}

interface InventoryAllocation {
  id: number;
  inventory_item_id: number;
  flip_id: number;
  quantity_allocated: number;
  cost_per_unit_at_allocation: number;
  notes: string | null;
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
  const [flips, setFlips] = useState<Flip[]>([]);
  const [selectedFlipId, setSelectedFlipId] = useState<number | null>(null);
  const [allocations, setAllocations] = useState<InventoryAllocation[]>([]);

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
      const [itemsData, statsData, flipsData, allocationsData] = await Promise.all([
        fetch("/api/inventory/").then(r => r.json()),
        fetch("/api/inventory/summary/stats").then(r => r.json()),
        fetch("/api/flips/").then(r => r.json()),
        fetch("/api/inventory-allocations/").then(r => r.json()),
      ]);
      setItems(itemsData);
      setStats(statsData);
      setFlips(flipsData);
      setAllocations(allocationsData);
    } catch {
      setItems([]);
      setFlips([]);
      setAllocations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadInventory();
  }, [loadInventory]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await fetch(`/api/inventory/${editingId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
      } else {
        await fetch("/api/inventory/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
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
    setSelectedFlipId(null);
    setShowForm(true);
  };

  const getFlipForItem = (itemId: number): Flip | null => {
    const allocation = allocations.find(a => a.inventory_item_id === itemId);
    if (!allocation) return null;
    return flips.find(f => f.id === allocation.flip_id) || null;
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
        <Button
          onClick={() => { setShowForm(!showForm); setEditingId(null); }}
          className="gap-2"
        >
          <Plus className="w-4 h-4" /> Add Item
        </Button>
      </div>

      {/* Stats */}
      {!loading && (
        <div className="grid grid-cols-3 gap-3">
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
        </div>
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
              <label className="block text-sm font-medium text-slate-300 mb-1">Assign to Build</label>
              <select
                value={selectedFlipId || ""}
                onChange={e => setSelectedFlipId(e.target.value ? parseInt(e.target.value) : null)}
                className="w-full px-3 py-2 bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 text-sm focus:border-[#00dc82] outline-none"
              >
                <option value="">Unassigned</option>
                {flips.map(flip => (
                  <option key={flip.id} value={flip.id}>Flip #{flip.id}</option>
                ))}
              </select>
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
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e2d45]">
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Component</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Type</th>
                <th className="text-center px-4 py-3 text-slate-400 font-medium">Qty</th>
                <th className="text-right px-4 py-3 text-slate-400 font-medium">Cost Each</th>
                <th className="text-right px-4 py-3 text-slate-400 font-medium">Total</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Source</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Date</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Assigned To</th>
                <th className="text-center px-4 py-3 text-slate-400 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => {
                const assignedFlip = getFlipForItem(item.id);
                return (
                  <tr key={item.id} className="border-b border-[#1e2d45] hover:bg-[#0a1119]">
                    <td className="px-4 py-3 text-slate-200">{item.component_name}</td>
                    <td className="px-4 py-3 text-slate-400">{item.component_type}</td>
                    <td className="px-4 py-3 text-center text-slate-300">{item.quantity}</td>
                    <td className="px-4 py-3 text-right text-amber-400">{formatCurrency(item.actual_cost)}</td>
                    <td className="px-4 py-3 text-right text-amber-400 font-semibold">{formatCurrency(item.actual_cost * item.quantity)}</td>
                    <td className="px-4 py-3 text-slate-400">{item.source || "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{formatRelativeTime(new Date(item.purchase_date))}</td>
                    <td className="px-4 py-3 text-slate-400">
                      {assignedFlip ? (
                        <span className="text-[#00dc82]">Flip #{assignedFlip.id}</span>
                      ) : (
                        <span className="text-slate-600">Unassigned</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex justify-center gap-2">
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
      )}
    </div>
  );
}
