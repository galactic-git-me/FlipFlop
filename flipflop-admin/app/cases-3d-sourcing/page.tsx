"use client";

import { useEffect, useState } from "react";
import { Box, Download, Image, FileText, RefreshCw, CheckCircle2, AlertCircle, ExternalLink } from "lucide-react";
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

interface SourcingTask {
  case: CaseSourceItem;
  priority: number;
  status: "pending" | "in_progress" | "completed";
  sources: {
    manufacturerCAD: {
      checked: boolean;
      url?: string;
      found: boolean;
    };
    thirdPartyCAD: {
      checked: boolean;
      urls?: string[];
      found: boolean;
    };
    manufacturerPhotos: {
      checked: boolean;
      urls?: string[];
      found: boolean;
    };
    internetPhotos: {
      checked: boolean;
      urls?: string[];
      found: boolean;
    };
    description: {
      checked: boolean;
      text?: string;
    };
  };
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
            internetPhotos: { checked: false, found: false },
            description: { checked: false },
          },
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
  const inProgressCount = tasks.filter((t) => t.status === "in_progress").length;
  const activeTask = tasks.find((t) => t.case.id === activeTaskId);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Box className="w-6 h-6 text-purple-400" /> 3D Model Sourcing Guide
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Systematic sourcing for top 30 cases. Priority: CAD → Photos → Description
        </p>
      </div>

      {/* Progress summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Completed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-[#00dc82]">{completedCount}</div>
            <p className="text-xs text-slate-500 mt-1">/ {tasks.length}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">In Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-cyan-400">{inProgressCount}</div>
            <p className="text-xs text-slate-500 mt-1">currently working on</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Pending</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-orange-400">{tasks.length - completedCount - inProgressCount}</div>
            <p className="text-xs text-slate-500 mt-1">waiting to start</p>
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
                tasks.map((task) => (
                  <button
                    key={task.case.id}
                    onClick={() => setActiveTaskId(task.case.id)}
                    className={`w-full text-left p-2 rounded-lg border transition-all ${
                      activeTaskId === task.case.id
                        ? "border-purple-400/50 bg-purple-400/10"
                        : "border-[#1e2d45] hover:border-[#2a3f5a]"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <div className="flex-shrink-0 mt-1">
                        {task.status === "completed" ? (
                          <CheckCircle2 className="w-4 h-4 text-[#00dc82]" />
                        ) : task.status === "in_progress" ? (
                          <div className="w-4 h-4 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
                        ) : (
                          <div className="w-4 h-4 rounded-full border-2 border-slate-600" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-semibold text-slate-100 line-clamp-1">
                          #{task.priority} {task.case.name.split(" ").slice(0, 3).join(" ")}
                        </div>
                        {task.case.bestseller_rank && (
                          <div className="text-[10px] text-slate-500">
                            Rank #{task.case.bestseller_rank}
                          </div>
                        )}
                      </div>
                    </div>
                  </button>
                ))
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
                        <img
                          src={activeTask.case.image_url}
                          alt=""
                          className="w-full h-full object-cover"
                        />
                      </div>
                    )}
                    <div className="flex-1">
                      <h2 className="text-lg font-bold text-slate-100 mb-2">
                        {activeTask.case.name}
                      </h2>
                      <div className="space-y-1 text-sm text-slate-400">
                        <p>
                          <span className="text-slate-600">Price:</span> {formatCurrency(activeTask.case.price)}
                        </p>
                        {activeTask.case.bestseller_rank && (
                          <p>
                            <span className="text-slate-600">Amazon Rank:</span> #{activeTask.case.bestseller_rank}
                          </p>
                        )}
                        {activeTask.case.rating && (
                          <p>
                            <span className="text-slate-600">Rating:</span> {activeTask.case.rating.toFixed(1)}★ ({activeTask.case.review_count} reviews)
                          </p>
                        )}
                        {activeTask.case.keywords && activeTask.case.keywords.length > 0 && (
                          <p>
                            <span className="text-slate-600">Tags:</span> {activeTask.case.keywords.join(", ")}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Sourcing checklist */}
              <Card className="border-[#1e2d45]">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">Sourcing Checklist</CardTitle>
                    <div className="flex gap-2">
                      <button
                        onClick={() =>
                          updateTask(activeTask.case.id, { status: "in_progress" })
                        }
                        disabled={activeTask.status === "in_progress"}
                        className={`px-3 py-1 text-xs rounded-lg transition-colors ${
                          activeTask.status === "in_progress"
                            ? "bg-cyan-400/20 text-cyan-400 border border-cyan-400/30"
                            : "bg-slate-700/30 text-slate-400 hover:bg-cyan-400/20 hover:text-cyan-400 border border-slate-600"
                        }`}
                      >
                        Start
                      </button>
                      <button
                        onClick={() =>
                          updateTask(activeTask.case.id, { status: "completed" })
                        }
                        disabled={activeTask.status === "completed"}
                        className={`px-3 py-1 text-xs rounded-lg transition-colors ${
                          activeTask.status === "completed"
                            ? "bg-[#00dc82]/20 text-[#00dc82] border border-[#00dc82]/30"
                            : "bg-slate-700/30 text-slate-400 hover:bg-[#00dc82]/20 hover:text-[#00dc82] border border-slate-600"
                        }`}
                      >
                        Complete
                      </button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* 1. Manufacturer CAD */}
                  <SourceChecklistItem
                    icon={<Download className="w-5 h-5" />}
                    title="1. Manufacturer CAD/3D Model"
                    description="Search official product pages or support sites"
                    suggestions={[
                      `Search: "${activeTask.case.name} CAD" or "${activeTask.case.name} 3D model"`,
                      "Check manufacturer website: Downloads/CAD/Technical specs",
                      "Try: brand official support/resources section",
                      "Look for: .step, .igs, .fbx, .obj, .blend files",
                    ]}
                    status={activeTask.sources.manufacturerCAD.found ? "found" : activeTask.sources.manufacturerCAD.checked ? "checked" : "pending"}
                    url={activeTask.sources.manufacturerCAD.url}
                    onUpdate={(url) =>
                      updateTask(activeTask.case.id, {
                        sources: {
                          ...activeTask.sources,
                          manufacturerCAD: { checked: true, found: !!url, url },
                        },
                      })
                    }
                  />

                  {/* 2. Third-party CAD */}
                  <SourceChecklistItem
                    icon={<Download className="w-5 h-5" />}
                    title="2. Third-Party CAD (Sketchfab, Grabcad, etc.)"
                    description="Community-uploaded models from free sites"
                    suggestions={[
                      "Search Sketchfab: https://sketchfab.com/search?q=" + encodeURIComponent(activeTask.case.name),
                      "Search Grabcad: https://grabcad.com/library?query=" + encodeURIComponent(activeTask.case.name),
                      "Search Thingiverse: https://www.thingiverse.com/search",
                      "Look for Creative Commons licensed models",
                    ]}
                    status={activeTask.sources.thirdPartyCAD.found ? "found" : activeTask.sources.thirdPartyCAD.checked ? "checked" : "pending"}
                    urls={activeTask.sources.thirdPartyCAD.urls}
                    onUpdate={(urls) =>
                      updateTask(activeTask.case.id, {
                        sources: {
                          ...activeTask.sources,
                          thirdPartyCAD: { checked: true, found: urls && urls.length > 0, urls },
                        },
                      })
                    }
                  />

                  {/* 3. Manufacturer Photos */}
                  <SourceChecklistItem
                    icon={<Image className="w-5 h-5" />}
                    title="3. Official Manufacturer Photos"
                    description="High-quality product photos from official sources"
                    suggestions={[
                      `Search: "${activeTask.case.brand} ${activeTask.case.name} specifications"`,
                      "Check product page: Gallery/Media section",
                      "Look for: Front, back, side, top-down, interior views",
                      "Get: Close-ups of rear ports, cable management, features",
                      "Format: PNG/JPG, high resolution (2K+)",
                    ]}
                    status={activeTask.sources.manufacturerPhotos.found ? "found" : activeTask.sources.manufacturerPhotos.checked ? "checked" : "pending"}
                    urls={activeTask.sources.manufacturerPhotos.urls}
                    onUpdate={(urls) =>
                      updateTask(activeTask.case.id, {
                        sources: {
                          ...activeTask.sources,
                          manufacturerPhotos: { checked: true, found: urls && urls.length > 0, urls },
                        },
                      })
                    }
                  />

                  {/* 4. Internet Photos */}
                  <SourceChecklistItem
                    icon={<Image className="w-5 h-5" />}
                    title="4. High-Quality Internet Photos"
                    description="Reviews, YouTube, tech sites with great photography"
                    suggestions={[
                      `YouTube: Search "${activeTask.case.name} review" or "unboxing"`,
                      `Reddit: r/pcmasterrace, r/buildapc with case photos`,
                      `Tech reviews: GamersNexus, JayzTwoCents, Linus Tech Tips`,
                      "Angles needed: Front, back, sides, interior, ports close-up, RGB areas",
                      "⚠️ RGB: Replace with FlipFlop orange-blue gradient",
                    ]}
                    status={activeTask.sources.internetPhotos.found ? "found" : activeTask.sources.internetPhotos.checked ? "checked" : "pending"}
                    urls={activeTask.sources.internetPhotos.urls}
                    onUpdate={(urls) =>
                      updateTask(activeTask.case.id, {
                        sources: {
                          ...activeTask.sources,
                          internetPhotos: { checked: true, found: urls && urls.length > 0, urls },
                        },
                      })
                    }
                  />

                  {/* 5. Description */}
                  <SourceChecklistItem
                    icon={<FileText className="w-5 h-5" />}
                    title="5. Feature Description"
                    description="Key features for customer decision-making"
                    suggestions={[
                      "Form factors: What motherboard sizes fit (ATX, MATX, ITX)?",
                      "Cooling: Radiator support, fan slots, airflow design",
                      "Features: Tempered glass, cable management, dust filters, RGB",
                      "Aesthetics: Material, color, design style, durability",
                      "Usability: Port accessibility, hard drive bays, drive support",
                    ]}
                    status={activeTask.sources.description.checked ? "filled" : "pending"}
                    onUpdateText={(text) =>
                      updateTask(activeTask.case.id, {
                        sources: {
                          ...activeTask.sources,
                          description: { checked: true, text },
                        },
                      })
                    }
                  />
                </CardContent>
              </Card>

              {/* Notes */}
              <Card className="bg-slate-700/20 border-slate-600">
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <AlertCircle className="w-4 h-4" /> Notes
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-xs text-slate-400 space-y-1">
                  <p>✨ <strong>Geometry Green case:</strong> Use your existing model as first item</p>
                  <p>🎨 <strong>RGB recoloring:</strong> When photos show RGB, edit to FlipFlop orange-blue gradient</p>
                  <p>📸 <strong>Photo quality matters:</strong> Multi-angle + interior shots help customers visualize</p>
                  <p>💾 <strong>Store sources:</strong> Save all URLs/files for reference during 3D modeling</p>
                </CardContent>
              </Card>
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

interface SourceChecklistItemProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  suggestions: string[];
  status: "pending" | "checked" | "found" | "filled";
  url?: string;
  urls?: string[];
  onUpdate?: (url: string) => void;
  onUpdateText?: (text: string) => void;
}

function SourceChecklistItem({
  icon,
  title,
  description,
  suggestions,
  status,
  url,
  urls,
  onUpdate,
  onUpdateText,
}: SourceChecklistItemProps) {
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [inputValue, setInputValue] = useState(url || urls?.join("\n") || "");

  const statusColors = {
    pending: "border-slate-600 bg-slate-900/20",
    checked: "border-orange-400/30 bg-orange-400/5",
    found: "border-[#00dc82]/30 bg-[#00dc82]/5",
    filled: "border-purple-400/30 bg-purple-400/5",
  };

  const statusIcons = {
    pending: <div className="w-4 h-4 rounded-full border-2 border-slate-600" />,
    checked: <AlertCircle className="w-4 h-4 text-orange-400" />,
    found: <CheckCircle2 className="w-4 h-4 text-[#00dc82]" />,
    filled: <CheckCircle2 className="w-4 h-4 text-purple-400" />,
  };

  return (
    <div className={`p-3 rounded-lg border ${statusColors[status]}`}>
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 text-slate-400 mt-1">{icon}</div>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-slate-100 text-sm mb-1">{title}</h4>
          <p className="text-xs text-slate-400 mb-2">{description}</p>

          {/* Suggestions */}
          <button
            onClick={() => setShowSuggestions(!showSuggestions)}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors mb-2 flex items-center gap-1"
          >
            💡 {showSuggestions ? "Hide" : "Show"} search tips
          </button>

          {showSuggestions && (
            <ul className="text-xs text-slate-500 mb-2 space-y-1 pl-4 list-disc">
              {suggestions.map((s, i) => (
                <li key={i} className="text-slate-400">
                  {s}
                </li>
              ))}
            </ul>
          )}

          {/* Input */}
          {onUpdate && (
            <input
              type="text"
              placeholder="Paste URL here..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onBlur={() => {
                if (inputValue.trim()) {
                  onUpdate(inputValue.trim());
                  setInputValue("");
                }
              }}
              className="w-full px-2 py-1 bg-[#0a1119] border border-[#1e2d45] rounded text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-400/50 mb-2"
            />
          )}

          {onUpdateText && (
            <textarea
              placeholder="Describe key features..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onBlur={() => {
                if (inputValue.trim()) {
                  onUpdateText(inputValue.trim());
                  setInputValue("");
                }
              }}
              rows={3}
              className="w-full px-2 py-1 bg-[#0a1119] border border-[#1e2d45] rounded text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-400/50"
            />
          )}

          {/* Display saved URLs */}
          {urls && urls.length > 0 && (
            <div className="text-xs space-y-1 mt-2">
              {urls.map((u, i) => (
                <a
                  key={i}
                  href={u}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-purple-400 hover:text-purple-300 flex items-center gap-1 break-all"
                >
                  <ExternalLink className="w-3 h-3 flex-shrink-0" /> {u.slice(0, 50)}...
                </a>
              ))}
            </div>
          )}
        </div>
        <div className="flex-shrink-0 mt-1">{statusIcons[status]}</div>
      </div>
    </div>
  );
}
