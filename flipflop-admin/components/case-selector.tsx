"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, X, Filter, Star, TrendingUp } from "lucide-react";
import { Part } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface CaseSelectorProps {
  onSelect: (caseItem: Part) => void;
  onClose: () => void;
  selectedCaseId?: number;
}

export function CaseSelector({ onSelect, onClose, selectedCaseId }: CaseSelectorProps) {
  const [cases, setCases] = useState<Part[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<"price-low" | "price-high" | "rating" | "demand">(
    "price-low"
  );
  const [filterSource, setFilterSource] = useState<"All" | "Amazon" | "Overclockers" | "eBay">(
    "All"
  );
  const [priceRange, setPriceRange] = useState({ min: 0, max: 500 });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterSource !== "All") params.source_site = filterSource;
      if (priceRange.min > 0) params.min_price = priceRange.min.toString();
      if (priceRange.max < 500) params.max_price = priceRange.max.toString();

      const data = (await api.parts.cases(params)) as Part[];
      setCases(data);
    } catch {
      setCases([]);
    } finally {
      setLoading(false);
    }
  }, [filterSource, priceRange]);

  useEffect(() => {
    const id = setTimeout(() => {
      void load();
    }, 0);
    return () => clearTimeout(id);
  }, [load]);

  // Filter by search query
  const filteredCases = cases.filter((c) => {
    const query = searchQuery.toLowerCase();
    return (
      c.name.toLowerCase().includes(query) ||
      (c.brand && c.brand.toLowerCase().includes(query)) ||
      (c.model && c.model.toLowerCase().includes(query)) ||
      (c.keywords && c.keywords.some((k) => k.toLowerCase().includes(query)))
    );
  });

  // Sort results
  const sortedCases = [...filteredCases].sort((a, b) => {
    const priceA = a.price_new ?? a.price ?? 0;
    const priceB = b.price_new ?? b.price ?? 0;
    const ratingA = a.rating ?? 0;
    const ratingB = b.rating ?? 0;

    switch (sortBy) {
      case "price-low":
        return priceA - priceB;
      case "price-high":
        return priceB - priceA;
      case "rating":
        return ratingB - ratingA;
      case "demand":
        const demandA = a.sales_velocity ? 1 : 0;
        const demandB = b.sales_velocity ? 1 : 0;
        return demandB - demandA;
      default:
        return 0;
    }
  });

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#0a1119] rounded-xl border border-[#1e2d45] w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1e2d45]">
          <div>
            <h2 className="text-lg font-bold text-slate-100">Select a PC Case</h2>
            <p className="text-xs text-slate-500 mt-1">{sortedCases.length} cases available</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-[#1e2d45] rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Filters & Search */}
        <div className="p-4 border-b border-[#1e2d45] space-y-3">
          {/* Search bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search cases by name, brand, or keyword..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-[#0d1320] border border-[#1e2d45] rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-400/50"
            />
          </div>

          {/* Filter row */}
          <div className="flex flex-wrap gap-3 items-center">
            {/* Source filter */}
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-500" />
              <select
                value={filterSource}
                onChange={(e) => setFilterSource(e.target.value as any)}
                className="px-3 py-1.5 bg-[#0d1320] border border-[#1e2d45] rounded-lg text-sm text-slate-100 focus:outline-none focus:border-purple-400/50"
              >
                <option value="All">All Sources</option>
                <option value="Amazon">Amazon</option>
                <option value="Overclockers">Overclockers</option>
                <option value="eBay">eBay</option>
              </select>
            </div>

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="px-3 py-1.5 bg-[#0d1320] border border-[#1e2d45] rounded-lg text-sm text-slate-100 focus:outline-none focus:border-purple-400/50"
            >
              <option value="price-low">Lowest Price</option>
              <option value="price-high">Highest Price</option>
              <option value="rating">Highest Rated</option>
              <option value="demand">Most In Demand</option>
            </select>

            {/* Price range */}
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-xs text-slate-500">£{priceRange.min}</span>
              <input
                type="range"
                min="0"
                max="500"
                value={priceRange.max}
                onChange={(e) => setPriceRange((p) => ({ ...p, max: parseInt(e.target.value) }))}
                className="w-24"
              />
              <span className="text-xs text-slate-500">£{priceRange.max}</span>
            </div>
          </div>
        </div>

        {/* Cases grid */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-slate-500">
              Loading cases…
            </div>
          ) : sortedCases.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-slate-500">
              No cases found matching your criteria
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {sortedCases.map((caseItem) => {
                const price = caseItem.price_new ?? caseItem.price ?? 0;
                const isSelected = selectedCaseId === caseItem.id;

                return (
                  <button
                    key={caseItem.id}
                    onClick={() => onSelect(caseItem)}
                    className={`text-left p-3 rounded-lg border-2 transition-all ${
                      isSelected
                        ? "border-purple-400 bg-purple-400/10"
                        : "border-[#1e2d45] bg-[#0d1320] hover:border-[#2a3f5a]"
                    }`}
                  >
                    {/* Image */}
                    {caseItem.image_url && (
                      <div className="mb-2 rounded-lg overflow-hidden h-32 bg-[#0a0f1a]">
                        <img
                          src={caseItem.image_url}
                          alt=""
                          className="w-full h-full object-cover"
                        />
                      </div>
                    )}

                    {/* Content */}
                    <h3 className="text-sm font-semibold text-white line-clamp-2 mb-1">
                      {caseItem.name}
                    </h3>

                    {/* Price & Source */}
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-lg font-bold text-[#00dc82]">
                        {formatCurrency(price)}
                      </span>
                      <span className="text-[10px] px-2 py-1 rounded bg-white/10 text-slate-400">
                        {caseItem.source_site}
                      </span>
                    </div>

                    {/* Rating & Demand */}
                    {(caseItem.rating || caseItem.sales_velocity) && (
                      <div className="flex items-center gap-2 text-xs text-slate-400 mb-2">
                        {caseItem.rating && (
                          <span className="flex items-center gap-1">
                            <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                            {caseItem.rating.toFixed(1)}
                          </span>
                        )}
                        {caseItem.sales_velocity && (
                          <span className="flex items-center gap-1 text-green-400">
                            <TrendingUp className="w-3 h-3" />
                            {caseItem.sales_velocity}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Keywords */}
                    {caseItem.keywords && caseItem.keywords.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {caseItem.keywords.slice(0, 3).map((kw) => (
                          <span
                            key={kw}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-purple-400/20 text-purple-300"
                          >
                            {kw}
                          </span>
                        ))}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
