"use client";

import { useState, useEffect, useRef } from "react";
import {
  Grid3x3,
  List,
  Download,
  Upload,
  Zap,
  Star,
  ChevronLeft,
  ChevronRight,
  X,
  ExternalLink,
  Check,
  Clock,
  AlertCircle,
  Package,
} from "lucide-react";

interface PCCase {
  id: string;
  name: string;
  brand: string;
  model: string;
  formFactor: string;
  materials: string[];
  features: string[];
  status: "has-model" | "reference-only" | "pending";
  rating: number;
  reviews: number;
  price: number;
  originalPrice?: number;
  image?: string;
  threeDModelUrl?: string;
  referenceImages?: string[];
  youtubeLinks?: { url: string; timestamp?: string; title: string }[];
  specifications?: Record<string, string>;
}

interface DetailedCaseProps {
  case: PCCase;
  onClose: () => void;
}

function CaseDetailModal({ case: caseData, onClose }: DetailedCaseProps) {
  const [activeTab, setActiveTab] = useState<"model" | "references" | "specs">(
    caseData.status === "has-model" ? "model" : "references"
  );
  const [currentImageIndex, setCurrentImageIndex] = useState(0);

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900/95 border border-slate-700/50 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700/50 sticky top-0 bg-slate-900/95">
          <div>
            <h2 className="text-2xl font-bold text-slate-100">{caseData.name}</h2>
            <p className="text-sm text-slate-500">{caseData.brand} • {caseData.model}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-700/30 rounded transition"
          >
            <X className="w-6 h-6 text-slate-400" />
          </button>
        </div>

        <div className="grid grid-cols-3 gap-6 p-6">
          {/* Main Content Area */}
          <div className="col-span-2 space-y-4">
            {/* Tabs */}
            <div className="flex gap-2 border-b border-slate-700/30">
              {caseData.status === "has-model" && (
                <button
                  onClick={() => setActiveTab("model")}
                  className={`px-4 py-2 border-b-2 transition font-medium text-sm ${
                    activeTab === "model"
                      ? "border-blue-500 text-blue-400"
                      : "border-transparent text-slate-500 hover:text-slate-400"
                  }`}
                >
                  3D Model
                </button>
              )}
              <button
                onClick={() => setActiveTab("references")}
                className={`px-4 py-2 border-b-2 transition font-medium text-sm ${
                  activeTab === "references"
                    ? "border-blue-500 text-blue-400"
                    : "border-transparent text-slate-500 hover:text-slate-400"
                }`}
              >
                References
              </button>
              <button
                onClick={() => setActiveTab("specs")}
                className={`px-4 py-2 border-b-2 transition font-medium text-sm ${
                  activeTab === "specs"
                    ? "border-blue-500 text-blue-400"
                    : "border-transparent text-slate-500 hover:text-slate-400"
                }`}
              >
                Specifications
              </button>
            </div>

            {/* Content */}
            {activeTab === "model" && caseData.threeDModelUrl && (
              <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg p-4 aspect-square flex items-center justify-center">
                <iframe
                  src={caseData.threeDModelUrl}
                  className="w-full h-full rounded"
                  allowFullScreen
                  allow="xr-spatial-tracking"
                />
              </div>
            )}

            {activeTab === "references" && (
              <div className="space-y-4">
                {/* Photo Gallery */}
                {caseData.referenceImages && caseData.referenceImages.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-slate-300 mb-3">Photo Gallery</h3>
                    <div className="space-y-3">
                      <div className="relative bg-slate-800/50 rounded-lg overflow-hidden aspect-video">
                        <img
                          src={caseData.referenceImages[currentImageIndex]}
                          alt={`Reference ${currentImageIndex + 1}`}
                          className="w-full h-full object-cover"
                        />
                        {caseData.referenceImages.length > 1 && (
                          <div className="absolute inset-x-0 bottom-0 flex justify-between p-2">
                            <button
                              onClick={() =>
                                setCurrentImageIndex((i) =>
                                  i === 0 ? caseData.referenceImages!.length - 1 : i - 1
                                )
                              }
                              className="bg-black/50 hover:bg-black/70 text-white p-2 rounded transition"
                            >
                              <ChevronLeft className="w-4 h-4" />
                            </button>
                            <div className="text-xs text-white bg-black/50 px-3 py-1 rounded">
                              {currentImageIndex + 1} / {caseData.referenceImages.length}
                            </div>
                            <button
                              onClick={() =>
                                setCurrentImageIndex((i) =>
                                  i === caseData.referenceImages!.length - 1 ? 0 : i + 1
                                )
                              }
                              className="bg-black/50 hover:bg-black/70 text-white p-2 rounded transition"
                            >
                              <ChevronRight className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                      </div>
                      <button className="w-full px-3 py-2 bg-slate-700/30 hover:bg-slate-700/50 text-slate-300 text-sm rounded transition flex items-center justify-center gap-2">
                        <Download className="w-4 h-4" />
                        Download All References
                      </button>
                    </div>
                  </div>
                )}

                {/* YouTube Videos */}
                {caseData.youtubeLinks && caseData.youtubeLinks.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-slate-300 mb-3">YouTube References</h3>
                    <div className="space-y-2">
                      {caseData.youtubeLinks.map((link, idx) => (
                        <a
                          key={idx}
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center justify-between p-3 bg-slate-800/30 hover:bg-slate-800/50 border border-slate-700/30 rounded transition group"
                        >
                          <div>
                            <p className="text-sm text-slate-300 group-hover:text-slate-100">{link.title}</p>
                            {link.timestamp && (
                              <p className="text-xs text-slate-500">@ {link.timestamp}</p>
                            )}
                          </div>
                          <ExternalLink className="w-4 h-4 text-slate-500 group-hover:text-slate-300" />
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === "specs" && caseData.specifications && (
              <div className="grid grid-cols-2 gap-3">
                {Object.entries(caseData.specifications).map(([key, value]) => (
                  <div
                    key={key}
                    className="bg-slate-800/30 border border-slate-700/30 rounded p-3"
                  >
                    <p className="text-xs text-slate-500 uppercase tracking-wide">{key}</p>
                    <p className="text-sm text-slate-200 font-medium">{value}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Status Badge */}
            <div className={`rounded-lg p-4 border ${
              caseData.status === "has-model"
                ? "bg-green-500/10 border-green-500/30"
                : caseData.status === "reference-only"
                ? "bg-blue-500/10 border-blue-500/30"
                : "bg-yellow-500/10 border-yellow-500/30"
            }`}>
              <div className="flex items-center gap-2 mb-1">
                {caseData.status === "has-model" && (
                  <>
                    <Check className="w-4 h-4 text-green-400" />
                    <span className="text-sm font-semibold text-green-400">3D Model Ready</span>
                  </>
                )}
                {caseData.status === "reference-only" && (
                  <>
                    <AlertCircle className="w-4 h-4 text-blue-400" />
                    <span className="text-sm font-semibold text-blue-400">Reference Only</span>
                  </>
                )}
                {caseData.status === "pending" && (
                  <>
                    <Clock className="w-4 h-4 text-yellow-400" />
                    <span className="text-sm font-semibold text-yellow-400">Pending Model</span>
                  </>
                )}
              </div>
              <p className="text-xs text-slate-500">Status</p>
            </div>

            {/* Rating */}
            <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                <span className="text-lg font-bold text-slate-100">{caseData.rating.toFixed(1)}</span>
              </div>
              <p className="text-xs text-slate-500">{caseData.reviews} reviews</p>
            </div>

            {/* Price */}
            <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg p-4">
              <div className="flex items-baseline gap-2 mb-1">
                <span className="text-2xl font-bold text-slate-100">
                  ${caseData.price}
                </span>
                {caseData.originalPrice && caseData.originalPrice > caseData.price && (
                  <span className="text-xs line-through text-slate-500">
                    ${caseData.originalPrice}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500">Current Price</p>
            </div>

            {/* Tags */}
            <div className="space-y-2">
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Form Factor</p>
                <span className="inline-block px-3 py-1 bg-slate-700/30 text-slate-300 text-xs rounded-full">
                  {caseData.formFactor}
                </span>
              </div>
              {caseData.features.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Features</p>
                  <div className="flex flex-wrap gap-1.5">
                    {caseData.features.slice(0, 4).map((feature, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-blue-500/10 text-blue-400 text-xs rounded"
                      >
                        {feature}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Admin Controls */}
            <div className="space-y-2 border-t border-slate-700/30 pt-4">
              <button className="w-full px-3 py-2 bg-slate-700/30 hover:bg-slate-700/50 text-slate-300 text-sm rounded transition flex items-center justify-center gap-2">
                <Upload className="w-4 h-4" />
                Upload Model
              </button>
              <button className="w-full px-3 py-2 bg-slate-700/30 hover:bg-slate-700/50 text-slate-300 text-sm rounded transition flex items-center justify-center gap-2">
                <AlertCircle className="w-4 h-4" />
                Edit References
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface PCCasesGalleryProps {
  cases: PCCase[];
  loading: boolean;
}

type StatusConfigType = Record<
  PCCase["status"],
  { icon: React.ComponentType<{ className?: string }>; label: string; color: string }
>;

const STATUS_CONFIG: StatusConfigType = {
  "has-model": { icon: Check, label: "3D Model", color: "text-green-400" },
  "reference-only": { icon: AlertCircle, label: "Reference Only", color: "text-blue-400" },
  pending: { icon: Clock, label: "Pending", color: "text-yellow-400" },
};

export function PCCasesGallery({ cases, loading }: PCCasesGalleryProps) {
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [selectedCase, setSelectedCase] = useState<PCCase | null>(null);
  const [filterFormFactor, setFilterFormFactor] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"rating" | "reviews" | "price" | "name">("rating");

  const formFactors = Array.from(new Set(cases.map((c) => c.formFactor)));
  const statuses: Array<PCCase["status"]> = ["has-model", "reference-only", "pending"];

  let filtered = cases.filter((c) => {
    if (filterFormFactor && c.formFactor !== filterFormFactor) return false;
    if (filterStatus && c.status !== filterStatus) return false;
    return true;
  });

  filtered.sort((a, b) => {
    switch (sortBy) {
      case "rating":
        return b.rating - a.rating;
      case "reviews":
        return b.reviews - a.reviews;
      case "price":
        return a.price - b.price;
      case "name":
        return a.name.localeCompare(b.name);
      default:
        return 0;
    }
  });

  const stats = {
    total: cases.length,
    hasModel: cases.filter((c) => c.status === "has-model").length,
    referenceOnly: cases.filter((c) => c.status === "reference-only").length,
    pending: cases.filter((c) => c.status === "pending").length,
  };

  const statusConfig = STATUS_CONFIG;

  return (
    <div className="relative z-10 space-y-6">
      {/* Header */}
      <div className="space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-100 mb-1">PC Cases 3D Review Gallery</h1>
            <p className="text-slate-400">32 premium sci-fi & themed cases with 3D models and reference materials</p>
          </div>
          <button className="px-4 py-2 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 text-sm rounded-lg border border-blue-500/30 transition flex items-center gap-2 font-medium">
            <Zap className="w-4 h-4" />
            Batch Import Models
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg p-4">
            <div className="text-2xl font-bold text-slate-100">{stats.total}</div>
            <p className="text-xs text-slate-500 mt-1">Total Cases</p>
          </div>
          <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
            <div className="text-2xl font-bold text-green-400">{stats.hasModel}</div>
            <p className="text-xs text-slate-500 mt-1">3D Models Ready</p>
          </div>
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
            <div className="text-2xl font-bold text-blue-400">{stats.referenceOnly}</div>
            <p className="text-xs text-slate-500 mt-1">Reference Only</p>
          </div>
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
            <div className="text-2xl font-bold text-yellow-400">{stats.pending}</div>
            <p className="text-xs text-slate-500 mt-1">Pending Models</p>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          {/* View Toggle */}
          <div className="flex gap-1 bg-slate-800/30 border border-slate-700/30 rounded-lg p-1">
            <button
              onClick={() => setViewMode("grid")}
              className={`p-2 rounded transition ${
                viewMode === "grid"
                  ? "bg-slate-700/50 text-slate-100"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              <Grid3x3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`p-2 rounded transition ${
                viewMode === "list"
                  ? "bg-slate-700/50 text-slate-100"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>

          {/* Sort Dropdown */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="px-3 py-2 bg-slate-800/30 border border-slate-700/30 text-slate-300 text-sm rounded-lg hover:border-slate-600/50 transition"
          >
            <option value="rating">Sort by Rating</option>
            <option value="reviews">Sort by Reviews</option>
            <option value="price">Sort by Price</option>
            <option value="name">Sort by Name</option>
          </select>
        </div>

        {/* Filters */}
        <div className="space-y-2">
          {/* Form Factor Filter */}
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Form Factor</p>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setFilterFormFactor(null)}
                className={`px-3 py-1.5 text-sm rounded-lg transition border ${
                  filterFormFactor === null
                    ? "bg-slate-700/50 border-slate-600 text-slate-100"
                    : "bg-slate-800/30 border-slate-700/30 text-slate-400 hover:border-slate-600/50"
                }`}
              >
                All
              </button>
              {formFactors.map((ff) => (
                <button
                  key={ff}
                  onClick={() => setFilterFormFactor(ff)}
                  className={`px-3 py-1.5 text-sm rounded-lg transition border ${
                    filterFormFactor === ff
                      ? "bg-slate-700/50 border-slate-600 text-slate-100"
                      : "bg-slate-800/30 border-slate-700/30 text-slate-400 hover:border-slate-600/50"
                  }`}
                >
                  {ff}
                </button>
              ))}
            </div>
          </div>

          {/* Status Filter */}
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Status</p>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setFilterStatus(null)}
                className={`px-3 py-1.5 text-sm rounded-lg transition border ${
                  filterStatus === null
                    ? "bg-slate-700/50 border-slate-600 text-slate-100"
                    : "bg-slate-800/30 border-slate-700/30 text-slate-400 hover:border-slate-600/50"
                }`}
              >
                All
              </button>
              {statuses.map((status) => {
                const config = STATUS_CONFIG[status];
                const IconComponent = config.icon;
                return (
                  <button
                    key={status}
                    onClick={() => setFilterStatus(status)}
                    className={`px-3 py-1.5 text-sm rounded-lg transition border flex items-center gap-2 ${
                      filterStatus === status
                        ? "bg-slate-700/50 border-slate-600 text-slate-100"
                        : "bg-slate-800/30 border-slate-700/30 text-slate-400 hover:border-slate-600/50"
                    }`}
                  >
                    <IconComponent className="w-3.5 h-3.5" />
                    {config.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Gallery */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="text-center">
            <div className="w-10 h-10 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin mx-auto mb-3" />
            <p className="text-slate-400">Loading cases...</p>
          </div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex items-center justify-center py-20">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400">No cases match your filters</p>
          </div>
        </div>
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((caseItem) => {
            const caseStatusConfig = STATUS_CONFIG[caseItem.status];
            const IconComponent = caseStatusConfig.icon;
            return (
              <button
                key={caseItem.id}
                onClick={() => setSelectedCase(caseItem)}
                className="group bg-slate-800/30 border border-slate-700/30 rounded-lg overflow-hidden hover:border-slate-600/50 transition"
              >
                {/* Image */}
                <div className="relative aspect-square bg-slate-900/50 overflow-hidden">
                  {caseItem.image ? (
                    <img
                      src={caseItem.image}
                      alt={caseItem.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-600">
                      <Package className="w-12 h-12 opacity-30" />
                    </div>
                  )}
                  {/* Status Badge */}
                  <div className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 bg-black/70 rounded-full">
                    <IconComponent className={`w-3.5 h-3.5 ${caseStatusConfig.color}`} />
                    <span className={`text-xs font-semibold ${caseStatusConfig.color}`}>
                      {caseStatusConfig.label}
                    </span>
                  </div>
                </div>

                {/* Info */}
                <div className="p-3 space-y-2">
                  <div>
                    <h3 className="font-semibold text-slate-100 text-sm group-hover:text-blue-400 transition">
                      {caseItem.name}
                    </h3>
                    <p className="text-xs text-slate-500">{caseItem.brand} • {caseItem.model}</p>
                  </div>

                  {/* Tags */}
                  <div className="flex flex-wrap gap-1">
                    <span className="px-2 py-0.5 bg-slate-700/30 text-slate-400 text-xs rounded">
                      {caseItem.formFactor}
                    </span>
                  </div>

                  {/* Rating and Price */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-700/30">
                    <div className="flex items-center gap-1">
                      <Star className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400" />
                      <span className="text-sm font-semibold text-slate-100">{caseItem.rating.toFixed(1)}</span>
                      <span className="text-xs text-slate-500">({caseItem.reviews})</span>
                    </div>
                    <span className="text-sm font-bold text-slate-100">${caseItem.price}</span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((caseItem) => {
            const caseStatusConfig = STATUS_CONFIG[caseItem.status];
            const IconComponent = caseStatusConfig.icon;
            return (
              <button
                key={caseItem.id}
                onClick={() => setSelectedCase(caseItem)}
                className="w-full bg-slate-800/30 border border-slate-700/30 rounded-lg p-4 hover:border-slate-600/50 transition flex gap-4"
              >
                {/* Thumbnail */}
                <div className="w-24 h-24 rounded-lg bg-slate-900/50 flex-shrink-0 overflow-hidden">
                  {caseItem.image ? (
                    <img
                      src={caseItem.image}
                      alt={caseItem.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-600">
                      <Package className="w-8 h-8 opacity-30" />
                    </div>
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 space-y-2 text-left">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-slate-100 text-sm hover:text-blue-400 transition">
                        {caseItem.name}
                      </h3>
                      <p className="text-xs text-slate-500">{caseItem.brand} • {caseItem.model}</p>
                    </div>
                    <div className="flex items-center gap-1 px-2 py-1 bg-black/40 rounded-full">
                      <IconComponent className={`w-3.5 h-3.5 ${caseStatusConfig.color}`} />
                      <span className={`text-xs font-semibold ${caseStatusConfig.color}`}>
                        {caseStatusConfig.label}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1">
                      <Star className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400" />
                      <span className="text-sm font-semibold text-slate-100">{caseItem.rating.toFixed(1)}</span>
                      <span className="text-xs text-slate-500">({caseItem.reviews} reviews)</span>
                    </div>
                    <span className="text-sm font-bold text-slate-100">${caseItem.price}</span>
                    <div className="flex flex-wrap gap-1 ml-auto">
                      <span className="px-2 py-0.5 bg-slate-700/30 text-slate-400 text-xs rounded">
                        {caseItem.formFactor}
                      </span>
                      {caseItem.features.slice(0, 2).map((f, idx) => (
                        <span key={idx} className="px-2 py-0.5 bg-blue-500/10 text-blue-400 text-xs rounded">
                          {f}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Detail Modal */}
      {selectedCase && (
        <CaseDetailModal case={selectedCase} onClose={() => setSelectedCase(null)} />
      )}
    </div>
  );
}
