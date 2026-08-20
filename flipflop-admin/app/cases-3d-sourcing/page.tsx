"use client";

import { useEffect, useState, useRef } from "react";
import { Box, Download, Image, FileText, RefreshCw, CheckCircle2, AlertCircle, ExternalLink, Upload, Trash2, Check, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/utils";

interface CaseSourceItem {
  id: number;
  name: string;
  brand?: string;
  model?: string;
  price: number;
  source_site?: string;
  image_url?: string;
  bestseller_rank?: number;
  rating?: number;
  review_count?: number;
  keywords?: string[];
  form_factors?: string[];
}

interface ApprovedAssets {
  model3d?: {
    url: string;
    source: "found" | "uploaded";
    fromMeshy: boolean;
  };
  photos?: string[];
  youtubeUrl?: string;
  description?: string;
}

interface SourcingTask {
  case: CaseSourceItem;
  priority: number;
  status: "pending" | "sourcing" | "ready_for_approval" | "approved" | "modeling" | "completed";
  sources: {
    manufacturerCAD: { checked: boolean; url?: string; found: boolean };
    thirdPartyCAD: { checked: boolean; urls?: string[]; found: boolean };
    manufacturerPhotos: { checked: boolean; urls?: string[]; found: boolean };
    youtubeVideo: { checked: boolean; url?: string; found: boolean };
    description: { checked: boolean; text?: string };
  };
  approvedAssets?: ApprovedAssets;
  approvalNotes?: string;
}

export default function Cases3DSourcingPage() {
  const [tasks, setTasks] = useState<SourcingTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const response = await fetch("/api/cases/priority-for-3d?limit=30");
        const cases = (await response.json()) as CaseSourceItem[];

        const newTasks: SourcingTask[] = cases.map((caseItem, idx) => ({
          case: caseItem,
          priority: idx + 1,
          status: "pending",
          sources: {
            manufacturerCAD: { checked: false, found: false },
            thirdPartyCAD: { checked: false, found: false },
            manufacturerPhotos: { checked: false, found: false },
            youtubeVideo: { checked: false, found: false },
            description: { checked: false },
          },
          approvedAssets: {},
        }));

        setTasks(newTasks);
        if (newTasks.length > 0) {
          setActiveTaskId(newTasks[0].case.id);
        }
      } catch (error) {
        console.error("Error loading cases:", error);
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

  const updateTask = (caseId: number, updates: Partial<SourcingTask>) => {
    setTasks((prev) =>
      prev.map((t) => (t.case.id === caseId ? { ...t, ...updates } : t))
    );
  };

  const completedCount = tasks.filter((t) => t.status === "completed").length;
  const approvedCount = tasks.filter((t) => t.status === "approved").length;
  const readyCount = tasks.filter((t) => t.status === "ready_for_approval").length;
  const activeTask = tasks.find((t) => t.case.id === activeTaskId);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Box className="w-6 h-6 text-purple-400" /> 3D Model Sourcing & Approval
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Source assets → Approve → Generate 3D models (if needed) → Complete
        </p>
      </div>

      {/* Progress summary */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Completed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-[#00dc82]">{completedCount}</div>
            <p className="text-xs text-slate-500 mt-1">fully done</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Approved</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-cyan-400">{approvedCount}</div>
            <p className="text-xs text-slate-500 mt-1">ready to model</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Ready Review</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-purple-400">{readyCount}</div>
            <p className="text-xs text-slate-500 mt-1">awaiting approval</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Total</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-orange-400">{tasks.length}</div>
            <p className="text-xs text-slate-500 mt-1">in queue</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-purple-400">
              {Math.round((completedCount / tasks.length) * 100)}%
            </div>
            <p className="text-xs text-slate-500 mt-1">complete</p>
          </CardContent>
        </Card>
      </div>

      {/* Main layout: list + detail */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* List of tasks */}
        <div className="lg:col-span-1">
          <Card className="max-h-[calc(100vh-400px)] overflow-y-auto">
            <CardHeader>
              <CardTitle className="text-sm">Cases Queue ({tasks.length})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 p-3">
              {loading ? (
                <div className="text-center py-8 text-slate-500">
                  <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2" />
                  Loading...
                </div>
              ) : (
                tasks.map((task) => {
                  const statusColors = {
                    pending: "border-slate-600 bg-slate-900/20",
                    sourcing: "border-orange-400/30 bg-orange-400/5",
                    ready_for_approval: "border-purple-400/30 bg-purple-400/5",
                    approved: "border-cyan-400/30 bg-cyan-400/5",
                    modeling: "border-blue-400/30 bg-blue-400/5",
                    completed: "border-[#00dc82]/30 bg-[#00dc82]/5",
                  };

                  const statusIcons = {
                    pending: <div className="w-4 h-4 rounded-full border-2 border-slate-600" />,
                    sourcing: <div className="w-4 h-4 rounded-full border-2 border-orange-400 border-t-transparent animate-spin" />,
                    ready_for_approval: <AlertCircle className="w-4 h-4 text-purple-400" />,
                    approved: <Check className="w-4 h-4 text-cyan-400" />,
                    modeling: <div className="w-4 h-4 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />,
                    completed: <CheckCircle2 className="w-4 h-4 text-[#00dc82]" />,
                  };

                  return (
                    <button
                      key={task.case.id}
                      onClick={() => setActiveTaskId(task.case.id)}
                      className={`w-full text-left p-2 rounded-lg border transition-all ${
                        activeTaskId === task.case.id ? "border-purple-400/50 bg-purple-400/10" : statusColors[task.status]
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <div className="flex-shrink-0 mt-1">{statusIcons[task.status]}</div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-semibold text-slate-100 line-clamp-1">
                            #{task.priority} {task.case.name.split(" ").slice(0, 3).join(" ")}
                          </div>
                          <div className="text-[10px] text-slate-500 capitalize">{task.status.replace(/_/g, " ")}</div>
                        </div>
                      </div>
                    </button>
                  );
                })
              )}
            </CardContent>
          </Card>
        </div>

        {/* Detail view */}
        <div className="lg:col-span-2 space-y-4">
          {activeTask ? (
            <>
              {/* Case info */}
              <Card className="border-[#1e2d45]">
                <CardContent className="pt-6">
                  <div className="flex gap-4">
                    {activeTask.case.image_url && (
                      <div className="w-32 h-32 rounded-lg overflow-hidden flex-shrink-0 bg-[#0a1119]">
                        <img src={activeTask.case.image_url} alt="" className="w-full h-full object-cover" />
                      </div>
                    )}
                    <div className="flex-1">
                      <h2 className="text-lg font-bold text-slate-100 mb-2">{activeTask.case.name}</h2>
                      <div className="space-y-1 text-sm text-slate-400">
                        <p>
                          <span className="text-slate-600">Price:</span> {formatCurrency(activeTask.case.price)}
                        </p>
                        {activeTask.case.bestseller_rank && (
                          <p>
                            <span className="text-slate-600">Amazon Rank:</span> #{activeTask.case.bestseller_rank}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Status-based workflow */}
              {activeTask.status === "pending" || activeTask.status === "sourcing" ? (
                <SourcingPhase task={activeTask} onUpdate={(updates) => updateTask(activeTask.case.id, updates)} />
              ) : activeTask.status === "ready_for_approval" ? (
                <ApprovalPhase task={activeTask} onUpdate={(updates) => updateTask(activeTask.case.id, updates)} />
              ) : activeTask.status === "approved" ? (
                <ModelingPhase task={activeTask} onUpdate={(updates) => updateTask(activeTask.case.id, updates)} />
              ) : activeTask.status === "modeling" ? (
                <ModelingInProgressPhase task={activeTask} />
              ) : (
                <CompletedPhase task={activeTask} />
              )}
            </>
          ) : (
            <div className="text-center py-12 text-slate-500">
              <Box className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>Loading case details...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface PhaseProps {
  task: SourcingTask;
  onUpdate: (updates: Partial<SourcingTask>) => void;
}

function SourcingPhase({ task, onUpdate }: PhaseProps) {
  const allSourcesFound = task.sources.manufacturerCAD.checked || task.sources.thirdPartyCAD.checked;
  const allPhotosFound = task.sources.manufacturerPhotos.found;
  const allVideoFound = task.sources.youtubeVideo.found;
  const descriptionExists = task.sources.description.checked;

  const isReadyForApproval = allSourcesFound && allPhotosFound && allVideoFound && descriptionExists;

  return (
    <Card className="border-[#1e2d45]">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Step 1: Source Assets</CardTitle>
          <div className="text-xs text-slate-500">
            {[allSourcesFound, allPhotosFound, allVideoFound, descriptionExists].filter(Boolean).length}/4 complete
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          {/* 3D Model */}
          <div className={`p-3 rounded-lg border ${allSourcesFound ? "border-[#00dc82]/30 bg-[#00dc82]/5" : "border-slate-600 bg-slate-900/20"}`}>
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-slate-100 text-sm">1. 3D Model</h4>
              {allSourcesFound && <CheckCircle2 className="w-4 h-4 text-[#00dc82]" />}
            </div>
            <p className="text-xs text-slate-400 mb-2">Manufacturer CAD or Sketchfab</p>
            {!allSourcesFound && (
              <div className="space-y-2">
                <div>
                  <label className="text-xs text-slate-500 block mb-1">Manufacturer CAD URL (if found)</label>
                  <input
                    type="text"
                    placeholder="https://example.com/case.step"
                    onBlur={(e) => {
                      if (e.target.value.trim()) {
                        onUpdate({ sources: { ...task.sources, manufacturerCAD: { checked: true, url: e.target.value, found: true } } });
                        e.target.value = "";
                      }
                    }}
                    className="w-full px-2 py-1.5 bg-[#0a1119] border border-[#1e2d45] rounded text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-400/50"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500 block mb-1">Third-party CAD URL (Sketchfab, GrabCAD)</label>
                  <input
                    type="text"
                    placeholder="https://sketchfab.com/models/..."
                    onBlur={(e) => {
                      if (e.target.value.trim()) {
                        onUpdate({ sources: { ...task.sources, thirdPartyCAD: { checked: true, urls: [e.target.value], found: true } } });
                        e.target.value = "";
                      }
                    }}
                    className="w-full px-2 py-1.5 bg-[#0a1119] border border-[#1e2d45] rounded text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-400/50"
                  />
                </div>
              </div>
            )}
            {task.sources.manufacturerCAD.url && <p className="text-xs text-purple-400 mt-2">✓ Manufacturer CAD: {task.sources.manufacturerCAD.url}</p>}
            {task.sources.thirdPartyCAD.urls?.[0] && <p className="text-xs text-purple-400 mt-2">✓ Third-party CAD: {task.sources.thirdPartyCAD.urls[0]}</p>}
          </div>

          {/* Photos */}
          <div className={`p-3 rounded-lg border ${allPhotosFound ? "border-[#00dc82]/30 bg-[#00dc82]/5" : "border-slate-600 bg-slate-900/20"}`}>
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-slate-100 text-sm">2. Product Photos</h4>
              {allPhotosFound && <CheckCircle2 className="w-4 h-4 text-[#00dc82]" />}
            </div>
            <p className="text-xs text-slate-400 mb-2">Multi-angle manufacturer photos</p>
            {!allPhotosFound && (
              <div>
                <label className="text-xs text-slate-500 block mb-1">Photo URLs (paste each, press Enter)</label>
                <input
                  type="text"
                  placeholder="https://example.com/photo1.jpg"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && e.currentTarget.value.trim()) {
                      const newUrls = [...(task.sources.manufacturerPhotos.urls || []), e.currentTarget.value];
                      onUpdate({
                        sources: {
                          ...task.sources,
                          manufacturerPhotos: { checked: true, urls: newUrls, found: newUrls.length > 0 },
                        },
                      });
                      e.currentTarget.value = "";
                    }
                  }}
                  className="w-full px-2 py-1.5 bg-[#0a1119] border border-[#1e2d45] rounded text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-400/50"
                />
              </div>
            )}
            {task.sources.manufacturerPhotos.urls && (
              <div className="mt-2 space-y-1">
                {task.sources.manufacturerPhotos.urls.map((url, i) => (
                  <div key={i} className="text-xs text-purple-400 flex items-center justify-between">
                    <span>Photo {i + 1}: {url.slice(0, 40)}...</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* YouTube Video */}
          <div className={`p-3 rounded-lg border ${allVideoFound ? "border-[#00dc82]/30 bg-[#00dc82]/5" : "border-slate-600 bg-slate-900/20"}`}>
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-slate-100 text-sm">3. YouTube Product Video</h4>
              {allVideoFound && <CheckCircle2 className="w-4 h-4 text-[#00dc82]" />}
            </div>
            <p className="text-xs text-slate-400 mb-2">Official showcase or quality review</p>
            {!allVideoFound && (
              <input
                type="text"
                placeholder="https://youtube.com/watch?v=..."
                onBlur={(e) => {
                  if (e.target.value.trim()) {
                    onUpdate({ sources: { ...task.sources, youtubeVideo: { checked: true, url: e.target.value, found: true } } });
                    e.target.value = "";
                  }
                }}
                className="w-full px-2 py-1.5 bg-[#0a1119] border border-[#1e2d45] rounded text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-400/50"
              />
            )}
            {task.sources.youtubeVideo.url && <p className="text-xs text-purple-400 mt-2">✓ Video: {task.sources.youtubeVideo.url.slice(0, 50)}...</p>}
          </div>

          {/* Description */}
          <div className={`p-3 rounded-lg border ${descriptionExists ? "border-[#00dc82]/30 bg-[#00dc82]/5" : "border-slate-600 bg-slate-900/20"}`}>
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-slate-100 text-sm">4. Description & KSP</h4>
              {descriptionExists && <CheckCircle2 className="w-4 h-4 text-[#00dc82]" />}
            </div>
            <p className="text-xs text-slate-400 mb-2">Key features & selling points</p>
            {!descriptionExists && (
              <textarea
                placeholder="E.g., 'Premium airflow case supporting up to 360mm radiators. Features dual-chamber design with tempered glass panel and excellent cable management.'"
                rows={3}
                onBlur={(e) => {
                  if (e.target.value.trim()) {
                    onUpdate({ sources: { ...task.sources, description: { checked: true, text: e.target.value } } });
                    e.target.value = "";
                  }
                }}
                className="w-full px-2 py-1.5 bg-[#0a1119] border border-[#1e2d45] rounded text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-400/50"
              />
            )}
            {task.sources.description.text && <p className="text-xs text-purple-400 mt-2">✓ Description saved</p>}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 pt-2">
          <Button
            onClick={() => onUpdate({ status: "sourcing" })}
            disabled={task.status === "sourcing"}
            variant="secondary"
            size="sm"
            className="flex-1"
          >
            Start Sourcing
          </Button>
          <Button
            onClick={() => {
              if (isReadyForApproval) {
                onUpdate({ status: "ready_for_approval" });
              }
            }}
            disabled={!isReadyForApproval}
            size="sm"
            className="flex-1 bg-purple-600 hover:bg-purple-700"
          >
            Ready for Approval
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ApprovalPhase({ task, onUpdate }: PhaseProps) {
  const [modelFile, setModelFile] = useState<File | null>(null);
  const [photoFiles, setPhotoFiles] = useState<File[]>([]);
  const modelInputRef = useRef<HTMLInputElement>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);

  const handleApprove = () => {
    const approved: ApprovedAssets = {
      photos: task.sources.manufacturerPhotos.urls || [],
      youtubeUrl: task.sources.youtubeVideo.url,
      description: task.sources.description.text,
      model3d: task.sources.manufacturerCAD.found
        ? { url: task.sources.manufacturerCAD.url!, source: "found", fromMeshy: false }
        : task.sources.thirdPartyCAD.found
        ? { url: task.sources.thirdPartyCAD.urls![0], source: "found", fromMeshy: false }
        : undefined,
    };

    if (modelFile) {
      // In real implementation, upload to storage and get URL
      approved.model3d = { url: URL.createObjectURL(modelFile), source: "uploaded", fromMeshy: false };
    }

    if (photoFiles.length > 0) {
      // Add uploaded photos to approved list
      approved.photos = [
        ...(approved.photos || []),
        ...photoFiles.map((f) => URL.createObjectURL(f)),
      ];
    }

    onUpdate({
      status: "approved",
      approvedAssets: approved,
      approvalNotes: "User approved all assets",
    });
  };

  return (
    <Card className="border-purple-400/30 bg-purple-400/5">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Step 2: Review & Approve Assets</CardTitle>
          <AlertCircle className="w-5 h-5 text-purple-400" />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="bg-purple-900/20 border border-purple-400/20 rounded-lg p-3">
          <p className="text-xs text-slate-300 mb-3">
            ✓ All 4 assets sourced. Review them below. Approve to proceed to 3D modeling (only if no 3D model found), or upload your own assets to replace.
          </p>

          <div className="space-y-4">
            {/* 3D Model */}
            <div>
              <h4 className="text-sm font-semibold text-slate-100 mb-2">3D Model</h4>
              {task.sources.manufacturerCAD.found || task.sources.thirdPartyCAD.found ? (
                <div className="p-2 bg-[#0a1119] border border-[#1e2d45] rounded text-xs text-slate-400 mb-2">
                  Found: {task.sources.manufacturerCAD.url || task.sources.thirdPartyCAD.urls?.[0]}
                </div>
              ) : (
                <div className="p-2 bg-orange-900/20 border border-orange-400/20 rounded text-xs text-orange-300 mb-2">
                  No 3D model found - will call Meshy.ai API to generate after approval
                </div>
              )}
              <button
                onClick={() => modelInputRef.current?.click()}
                className="w-full px-3 py-2 text-xs bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 hover:border-purple-400/50 transition-colors flex items-center justify-center gap-2"
              >
                <Upload className="w-3.5 h-3.5" /> Replace with your own 3D model
              </button>
              <input
                ref={modelInputRef}
                type="file"
                accept=".glb,.gltf,.obj,.fbx,.step,.iges"
                onChange={(e) => setModelFile(e.target.files?.[0] || null)}
                className="hidden"
              />
              {modelFile && <p className="text-xs text-purple-400 mt-1">✓ {modelFile.name} selected</p>}
            </div>

            {/* Photos */}
            <div>
              <h4 className="text-sm font-semibold text-slate-100 mb-2">Product Photos ({task.sources.manufacturerPhotos.urls?.length || 0})</h4>
              <div className="space-y-1 mb-2">
                {task.sources.manufacturerPhotos.urls?.map((url, i) => (
                  <div key={i} className="p-2 bg-[#0a1119] border border-[#1e2d45] rounded text-xs text-slate-400 truncate">
                    Photo {i + 1}: {url}
                  </div>
                ))}
              </div>
              <button
                onClick={() => photoInputRef.current?.click()}
                className="w-full px-3 py-2 text-xs bg-[#0d1320] border border-[#1e2d45] rounded text-slate-300 hover:border-purple-400/50 transition-colors flex items-center justify-center gap-2"
              >
                <Upload className="w-3.5 h-3.5" /> Add/Replace photos
              </button>
              <input
                ref={photoInputRef}
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => setPhotoFiles(Array.from(e.target.files || []))}
                className="hidden"
              />
              {photoFiles.length > 0 && <p className="text-xs text-purple-400 mt-1">✓ {photoFiles.length} photos selected</p>}
            </div>

            {/* YouTube */}
            <div>
              <h4 className="text-sm font-semibold text-slate-100 mb-2">YouTube Video</h4>
              <div className="p-2 bg-[#0a1119] border border-[#1e2d45] rounded text-xs text-slate-400 mb-2 truncate">
                {task.sources.youtubeVideo.url}
              </div>
              <p className="text-xs text-slate-500">💡 Edit in the sourcing checklist if you want to change</p>
            </div>

            {/* Description */}
            <div>
              <h4 className="text-sm font-semibold text-slate-100 mb-2">Description</h4>
              <div className="p-2 bg-[#0a1119] border border-[#1e2d45] rounded text-xs text-slate-400">
                {task.sources.description.text}
              </div>
            </div>
          </div>
        </div>

        {/* Approval buttons */}
        <div className="flex gap-2 pt-2">
          <Button
            onClick={() => onUpdate({ status: "ready_for_approval", approvalNotes: "Needs more work" })}
            variant="secondary"
            size="sm"
            className="flex-1"
          >
            <X className="w-3.5 h-3.5 mr-1" /> Reject
          </Button>
          <Button onClick={handleApprove} size="sm" className="flex-1 bg-[#00dc82] hover:bg-[#00dc82]/90 text-black">
            <Check className="w-3.5 h-3.5 mr-1" /> Approve & Proceed
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ModelingPhase({ task, onUpdate }: PhaseProps) {
  const hasExistingModel = task.approvedAssets?.model3d?.source === "found";

  return (
    <Card className="border-cyan-400/30 bg-cyan-400/5">
      <CardHeader>
        <CardTitle className="text-sm">Step 3: 3D Modeling</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {hasExistingModel ? (
          <div className="bg-[#00dc82]/10 border border-[#00dc82]/30 rounded-lg p-3">
            <p className="text-xs text-[#00dc82] flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" /> 3D model already sourced - skipping Meshy.ai generation
            </p>
          </div>
        ) : (
          <div className="bg-cyan-900/20 border border-cyan-400/20 rounded-lg p-3 space-y-2">
            <p className="text-xs text-slate-300">
              No CAD model found. Will call Meshy.ai API to generate 3D model from product photos.
            </p>
            <p className="text-xs text-slate-400">
              Meshy prompt: Generate a photorealistic 3D model of a PC case: {task.case.name}. Use the reference photos provided to match colors, materials, and design accurately.
            </p>
            <button
              onClick={() => onUpdate({ status: "modeling" })}
              className="w-full px-3 py-2 text-xs bg-cyan-600 hover:bg-cyan-700 text-white rounded transition-colors"
            >
              Start Meshy.ai Generation
            </button>
          </div>
        )}

        {hasExistingModel && (
          <button
            onClick={() => onUpdate({ status: "completed" })}
            className="w-full px-3 py-2 text-xs bg-[#00dc82] hover:bg-[#00dc82]/90 text-black rounded font-semibold transition-colors"
          >
            Mark as Completed
          </button>
        )}
      </CardContent>
    </Card>
  );
}

function ModelingInProgressPhase({ task }: PhaseProps) {
  return (
    <Card className="border-blue-400/30 bg-blue-400/5">
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <div className="w-4 h-4 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
          Generating 3D Model with Meshy.ai
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-slate-400">
          Your 3D model is being generated. You can check back in a few minutes to see the result.
        </p>
      </CardContent>
    </Card>
  );
}

function CompletedPhase({ task }: { task: SourcingTask }) {
  return (
    <Card className="border-[#00dc82]/30 bg-[#00dc82]/5">
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-[#00dc82]" /> Complete ✓
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="text-xs text-[#00dc82]">
          <p>✓ 3D model ready</p>
          <p>✓ Product photos approved</p>
          <p>✓ YouTube video linked</p>
          <p>✓ Description approved</p>
        </div>
        <p className="text-xs text-slate-400 mt-3">This case is ready to be added to the customer builder.</p>
      </CardContent>
    </Card>
  );
}
