"use client";

import { useEffect, useState } from "react";
import { Save, Eye, EyeOff, Plus, RefreshCw, Edit2, Trash2, Check, X } from "lucide-react";

interface CuratedBuild {
  id: number;
  definition_id: string;
  segment: string;
  tier: string;
  name: string;
  description: string;
  use: string;
  components: Record<string, string>;
  estimated_price_gbp: number | null;
  components_cost: number | null;
  markup_percentage: number;
  is_published: boolean;
  published_at: string | null;
  display_order: number;
  is_featured: boolean;
  is_available: boolean;
  availability_notes: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface BuildDefinition {
  id: string;
  segment: string;
  tier: string;
  name: string;
  description: string;
  use: string;
  components: Record<string, string>;
}

export default function CuratedBuildsPage() {
  const [builds, setBuilds] = useState<CuratedBuild[]>([]);
  const [definitions, setDefinitions] = useState<{ builds: BuildDefinition[] }>({ builds: [] });
  const [loading, setLoading] = useState(true);
  const [selectedBuild, setSelectedBuild] = useState<CuratedBuild | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);

  const fetchBuilds = async () => {
    try {
      const res = await fetch("/api/curated-builds");
      if (res.ok) {
        setBuilds(await res.json());
      }
    } catch (error) {
      console.error("Error fetching curated builds:", error);
    }
  };

  const fetchDefinitions = async () => {
    try {
      const res = await fetch("/api/curated-builds/definitions");
      if (res.ok) {
        setDefinitions(await res.json());
      }
    } catch (error) {
      console.error("Error fetching definitions:", error);
    }
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await Promise.all([fetchBuilds(), fetchDefinitions()]);
      setLoading(false);
    };
    load();
  }, []);

  const handleSync = async () => {
    try {
      const res = await fetch("/api/curated-builds/sync-from-definitions", { method: "POST" });
      if (res.ok) {
        const result = await res.json();
        alert(`Sync completed: ${result.created} created, ${result.skipped} skipped`);
        await fetchBuilds();
      }
    } catch (error) {
      console.error("Error syncing builds:", error);
      alert("Failed to sync builds");
    }
  };

  const handlePublish = async (buildId: number) => {
    try {
      const res = await fetch(`/api/curated-builds/${buildId}/publish`, { method: "POST" });
      if (res.ok) {
        await fetchBuilds();
      }
    } catch (error) {
      console.error("Error publishing build:", error);
    }
  };

  const handleUnpublish = async (buildId: number) => {
    try {
      const res = await fetch(`/api/curated-builds/${buildId}/unpublish`, { method: "POST" });
      if (res.ok) {
        await fetchBuilds();
      }
    } catch (error) {
      console.error("Error unpublishing build:", error);
    }
  };

  const handleDelete = async (buildId: number) => {
    if (!confirm("Are you sure you want to delete this curated build?")) return;
    
    try {
      const res = await fetch(`/api/curated-builds/${buildId}`, { method: "DELETE" });
      if (res.ok) {
        await fetchBuilds();
        if (selectedBuild?.id === buildId) {
          setSelectedBuild(null);
        }
      }
    } catch (error) {
      console.error("Error deleting build:", error);
    }
  };

  const handleCreateFromDefinition = async (definition: BuildDefinition) => {
    try {
      const res = await fetch("/api/curated-builds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          definition_id: definition.id,
          segment: definition.segment,
          tier: definition.tier,
          name: definition.name,
          description: definition.description,
          use: definition.use,
          components: definition.components,
        }),
      });
      
      if (res.ok) {
        await fetchBuilds();
        setShowAddModal(false);
        alert("Curated build created successfully!");
      } else if (res.status === 409) {
        alert("This build already exists");
      }
    } catch (error) {
      console.error("Error creating build:", error);
      alert("Failed to create build");
    }
  };

  const getExistingDefIds = () => new Set(builds.map(b => b.definition_id));
  const availableDefinitions = definitions.builds.filter(d => !getExistingDefIds().has(d.id));

  const groupedBuilds = builds.reduce((acc, build) => {
    if (!acc[build.segment]) acc[build.segment] = [];
    acc[build.segment].push(build);
    return acc;
  }, {} as Record<string, CuratedBuild[]>);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-slate-400">Loading curated builds...</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full gap-4 p-6 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Curated Builds Management</h1>
          <p className="text-slate-400 text-sm mt-1">
            Manage the catalogue of pre-designed PC builds shown on the storefront
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold flex items-center gap-2 transition"
          >
            <Plus className="w-4 h-4" /> Add Build
          </button>
          <button
            onClick={handleSync}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded font-semibold flex items-center gap-2 transition"
          >
            <RefreshCw className="w-4 h-4" /> Sync from Definitions
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {Object.keys(groupedBuilds).length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-400 mb-4">No curated builds yet</p>
            <button
              onClick={handleSync}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded font-semibold"
            >
              Sync from Definitions
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {Object.entries(groupedBuilds).map(([segment, segmentBuilds]) => (
              <div key={segment} className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                <h2 className="text-xl font-bold text-white mb-4">{segment}</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {segmentBuilds.map((build) => (
                    <div
                      key={build.id}
                      className="p-4 bg-slate-900 border border-slate-700 rounded-lg hover:border-blue-500 transition cursor-pointer"
                      onClick={() => setSelectedBuild(build)}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <h3 className="font-bold text-white">{build.name}</h3>
                          <span className="text-xs text-slate-400 uppercase">{build.tier}</span>
                        </div>
                        <div className="flex gap-1">
                          {build.is_featured && (
                            <span className="text-xs px-2 py-1 bg-amber-600/20 text-amber-300 rounded">★ Featured</span>
                          )}
                          {build.is_published ? (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleUnpublish(build.id);
                              }}
                              className="p-1 text-green-400 hover:text-green-300"
                              title="Published - click to unpublish"
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                          ) : (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handlePublish(build.id);
                              }}
                              className="p-1 text-slate-400 hover:text-slate-300"
                              title="Unpublished - click to publish"
                            >
                              <EyeOff className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                      <p className="text-sm text-slate-400 mb-2 line-clamp-2">{build.description}</p>
                      {build.estimated_price_gbp && (
                        <p className="text-lg font-bold text-emerald-400">£{build.estimated_price_gbp.toFixed(2)}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Build Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-white">Add Curated Build</h2>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-6 h-6" />
              </button>
            </div>

            {availableDefinitions.length === 0 ? (
              <p className="text-slate-400">All definitions have been added. Sync to refresh.</p>
            ) : (
              <div className="space-y-4">
                {availableDefinitions.map((def) => (
                  <div key={def.id} className="p-4 bg-slate-900 border border-slate-700 rounded-lg">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="font-bold text-white">{def.name}</h3>
                        <span className="text-xs text-slate-400 uppercase">{def.segment} • {def.tier}</span>
                        <p className="text-sm text-slate-300 mt-2">{def.description}</p>
                        <p className="text-xs text-slate-400 mt-1">{def.use}</p>
                      </div>
                      <button
                        onClick={() => handleCreateFromDefinition(def)}
                        className="ml-4 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-semibold whitespace-nowrap"
                      >
                        Add Build
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Build Detail Modal */}
      {selectedBuild && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-white">{selectedBuild.name}</h2>
              <div className="flex gap-2">
                <button
                  onClick={() => handleDelete(selectedBuild.id)}
                  className="p-2 text-red-400 hover:text-red-300"
                  title="Delete"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
                <button onClick={() => setSelectedBuild(null)} className="text-slate-400 hover:text-white">
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex gap-2">
                <span className="px-3 py-1 bg-slate-700 text-slate-300 rounded text-sm">{selectedBuild.segment}</span>
                <span className="px-3 py-1 bg-slate-700 text-slate-300 rounded text-sm uppercase">{selectedBuild.tier}</span>
                {selectedBuild.is_published ? (
                  <span className="px-3 py-1 bg-green-600/20 text-green-300 rounded text-sm flex items-center gap-1">
                    <Check className="w-4 h-4" /> Published
                  </span>
                ) : (
                  <span className="px-3 py-1 bg-slate-700 text-slate-400 rounded text-sm">Unpublished</span>
                )}
              </div>

              <div>
                <h3 className="font-semibold text-white mb-2">Description</h3>
                <p className="text-slate-300">{selectedBuild.description}</p>
              </div>

              <div>
                <h3 className="font-semibold text-white mb-2">Use Case</h3>
                <p className="text-slate-300">{selectedBuild.use}</p>
              </div>

              <div>
                <h3 className="font-semibold text-white mb-2">Components</h3>
                <div className="bg-slate-900 rounded p-3 space-y-2">
                  {Object.entries(selectedBuild.components).map(([key, value]) => (
                    <div key={key} className="flex justify-between text-sm">
                      <span className="text-slate-400 capitalize">{key.replace(/_/g, ' ')}</span>
                      <span className="text-slate-200">{value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {selectedBuild.estimated_price_gbp && (
                <div>
                  <h3 className="font-semibold text-white mb-2">Pricing</h3>
                  <p className="text-2xl font-bold text-emerald-400">£{selectedBuild.estimated_price_gbp.toFixed(2)}</p>
                </div>
              )}

              <div className="flex gap-2 pt-4">
                {selectedBuild.is_published ? (
                  <button
                    onClick={() => {
                      handleUnpublish(selectedBuild.id);
                      setSelectedBuild(null);
                    }}
                    className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded font-semibold flex items-center gap-2"
                  >
                    <EyeOff className="w-4 h-4" /> Unpublish
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      handlePublish(selectedBuild.id);
                      setSelectedBuild(null);
                    }}
                    className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded font-semibold flex items-center gap-2"
                  >
                    <Eye className="w-4 h-4" /> Publish
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
