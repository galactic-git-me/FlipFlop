/**
 * Gem Build Recommendations Component
 *
 * Admin UI for viewing and managing LLM-generated speculative build recommendations.
 * Features:
 * - Generate new recommendations via Claude API
 * - Filter by risk level and use case
 * - View profit/margin analysis
 * - Build gems as orders
 * - Dismiss/reject recommendations
 */

"use client";

import React, { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AlertCircle, TrendingUp, Zap, Target } from "lucide-react";
import { gemApi } from "@/lib/gem-api";
import { formatCurrency, formatPercent } from "@/lib/utils";

interface Gem {
  id: number;
  name: string;
  use_case: string;
  target_budget: number;
  specs: Record<string, any>;
  estimated_cost: number;
  estimated_price: number;
  margin_gbp: number;
  margin_percent: number;
  confidence_score: number;
  risk_level: "low" | "medium" | "high";
  recommended_quantity: number;
  reasoning: string;
  cost_breakdown: Record<string, number>;
  generated_at: string;
}

interface DemandSummary {
  budget_distribution: Record<string, number>;
  popular_use_cases: Record<string, number>;
  top_component_combinations: Record<string, number>;
  insights: Record<string, any>;
}

const GemRecommendations = () => {
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [useCaseFilter, setUseCaseFilter] = useState<string>("all");
  const [gems, setGems] = useState<Gem[]>([]);
  const [demandSummary, setDemandSummary] = useState<DemandSummary | null>(
    null
  );

  // Query for fetching recommendations
  const {
    data: recommendationsData,
    isLoading: isLoadingRecs,
    refetch: refetchRecs,
  } = useQuery({
    queryKey: ["gems", "recommendations"],
    queryFn: () => gemApi.getRecommendations(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // Mutation for generating new recommendations
  const generateMutation = useMutation({
    mutationFn: (analysisDays: number) =>
      gemApi.generateRecommendations(analysisDays),
    onSuccess: (data) => {
      setGems(data.recommendations || []);
      setDemandSummary(data.demand_summary || null);
    },
    onError: (error) => {
      console.error("Failed to generate recommendations:", error);
    },
  });

  // Mutation for building a gem
  const buildMutation = useMutation({
    mutationFn: (gemId: number) =>
      gemApi.buildGem(gemId, { action: "build", quantity: 1 }),
    onSuccess: (data) => {
      console.log("Gem built successfully:", data);
      refetchRecs();
    },
    onError: (error) => {
      console.error("Failed to build gem:", error);
    },
  });

  // Mutation for dismissing a gem
  const dismissMutation = useMutation({
    mutationFn: (gemId: number) => gemApi.dismissGem(gemId),
    onSuccess: () => {
      refetchRecs();
    },
    onError: (error) => {
      console.error("Failed to dismiss gem:", error);
    },
  });

  // Load recommendations when component mounts
  useEffect(() => {
    if (recommendationsData) {
      setGems(recommendationsData.gems || []);
      setDemandSummary(recommendationsData.demand_summary || null);
    }
  }, [recommendationsData]);

  // Filter gems based on selected filters
  const filteredGems = gems.filter((gem) => {
    const riskMatch =
      riskFilter === "all" || gem.risk_level === riskFilter;
    const useCaseMatch =
      useCaseFilter === "all" || gem.use_case === useCaseFilter;
    return riskMatch && useCaseMatch;
  });

  // Get unique use cases from gems
  const uniqueUseCases = [...new Set(gems.map((g) => g.use_case))];

  // Risk color mapping
  const getRiskColor = (level: string) => {
    switch (level) {
      case "low":
        return "bg-green-100 text-green-800";
      case "medium":
        return "bg-yellow-100 text-yellow-800";
      case "high":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getRiskIcon = (level: string) => {
    switch (level) {
      case "low":
        return "✓";
      case "medium":
        return "⚠";
      case "high":
        return "!";
      default:
        return "?";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and Generation Controls */}
      <div className="space-y-4">
        <div>
          <h1 className="text-3xl font-bold">Gem Build Recommendations</h1>
          <p className="text-gray-600 mt-2">
            LLM-powered speculative inventory builds based on demand analysis
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Generate New Recommendations</CardTitle>
            <CardDescription>
              Analyze recent order data to generate gem build recommendations
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={() => generateMutation.mutate(30)}
              disabled={generateMutation.isPending}
              size="lg"
              className="w-full"
            >
              {generateMutation.isPending ? (
                <>
                  <span className="animate-spin mr-2">⟳</span>
                  Analyzing Demand...
                </>
              ) : (
                <>
                  <TrendingUp className="mr-2 h-4 w-4" />
                  Analyze Market & Generate Recommendations (Last 30 Days)
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Demand Summary */}
      {demandSummary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Market Insights</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="border rounded p-4">
                <div className="text-sm text-gray-600">Avg Budget</div>
                <div className="text-2xl font-bold">
                  {formatCurrency(
                    demandSummary.insights?.avg_budget_gbp || 0
                  )}
                </div>
              </div>
              <div className="border rounded p-4">
                <div className="text-sm text-gray-600">Popular Use Case</div>
                <div className="text-2xl font-bold">
                  {demandSummary.insights?.most_popular_use_case || "N/A"}
                </div>
              </div>
              <div className="border rounded p-4">
                <div className="text-sm text-gray-600">Unique Combos</div>
                <div className="text-2xl font-bold">
                  {demandSummary.insights?.total_unique_combos || 0}
                </div>
              </div>
              <div className="border rounded p-4">
                <div className="text-sm text-gray-600">Popular Combo</div>
                <div className="text-lg font-bold truncate">
                  {demandSummary.insights?.most_popular_combo || "N/A"}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filtering Controls */}
      {gems.length > 0 && (
        <div className="flex gap-4">
          <Select value={riskFilter} onValueChange={setRiskFilter}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Filter by risk..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Risk Levels</SelectItem>
              <SelectItem value="low">Low Risk</SelectItem>
              <SelectItem value="medium">Medium Risk</SelectItem>
              <SelectItem value="high">High Risk</SelectItem>
            </SelectContent>
          </Select>

          <Select value={useCaseFilter} onValueChange={setUseCaseFilter}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Filter by use case..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Use Cases</SelectItem>
              {uniqueUseCases.map((useCase) => (
                <SelectItem key={useCase} value={useCase}>
                  {useCase.charAt(0).toUpperCase() + useCase.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Gem Cards Grid */}
      {isLoadingRecs ? (
        <Card>
          <CardContent className="pt-8">
            <div className="text-center text-gray-600">
              Loading recommendations...
            </div>
          </CardContent>
        </Card>
      ) : filteredGems.length === 0 && gems.length === 0 ? (
        <Card>
          <CardContent className="pt-8">
            <div className="text-center text-gray-600">
              <AlertCircle className="mx-auto h-8 w-8 mb-2 opacity-50" />
              <p>No recommendations yet.</p>
              <p className="text-sm mt-2">
                Generate recommendations to get started.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filteredGems.map((gem) => (
            <Card key={gem.id} className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex justify-between items-start gap-2">
                  <div>
                    <CardTitle className="text-lg">{gem.name}</CardTitle>
                    <CardDescription className="mt-1">
                      {gem.use_case.charAt(0).toUpperCase() +
                        gem.use_case.slice(1)}{" "}
                      • Target: {formatCurrency(gem.target_budget)}
                    </CardDescription>
                  </div>
                  <Badge className={getRiskColor(gem.risk_level)}>
                    {getRiskIcon(gem.risk_level)} {gem.risk_level}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                {/* Build Specs Summary */}
                <div className="bg-gray-50 rounded p-3 text-sm space-y-1">
                  <div>
                    <span className="text-gray-600">CPU:</span>{" "}
                    <span className="font-mono">{gem.specs.cpu}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">GPU:</span>{" "}
                    <span className="font-mono">{gem.specs.gpu}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">RAM:</span>{" "}
                    <span className="font-mono">
                      {gem.specs.ram_gb}GB {gem.specs.ram_type}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-600">Storage:</span>{" "}
                    <span className="font-mono">{gem.specs.ssd_gb}GB SSD</span>
                  </div>
                </div>

                {/* Financial Metrics */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="border rounded p-3">
                    <div className="text-xs text-gray-600">Build Cost</div>
                    <div className="text-lg font-bold">
                      {formatCurrency(gem.estimated_cost)}
                    </div>
                  </div>
                  <div className="border rounded p-3">
                    <div className="text-xs text-gray-600">Est. Price</div>
                    <div className="text-lg font-bold">
                      {formatCurrency(gem.estimated_price)}
                    </div>
                  </div>
                  <div className="border rounded p-3 bg-green-50">
                    <div className="text-xs text-gray-600">Profit</div>
                    <div className="text-lg font-bold text-green-700">
                      {formatCurrency(gem.margin_gbp)}
                    </div>
                  </div>
                  <div className="border rounded p-3 bg-blue-50">
                    <div className="text-xs text-gray-600">Margin</div>
                    <div className="text-lg font-bold text-blue-700">
                      {formatPercent(gem.margin_percent)}
                    </div>
                  </div>
                </div>

                {/* Confidence & Reasoning */}
                <div className="space-y-2">
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-xs font-semibold text-gray-600">
                        Demand Confidence
                      </span>
                      <span className="text-xs font-bold">
                        {gem.confidence_score}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all"
                        style={{ width: `${gem.confidence_score}%` }}
                      />
                    </div>
                  </div>

                  <div className="text-sm text-gray-700 italic border-l-4 border-blue-300 pl-3 py-1">
                    "{gem.reasoning}"
                  </div>
                </div>

                {/* Recommended Quantity */}
                <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm">
                  <div className="flex items-center gap-2">
                    <Zap className="h-4 w-4 text-amber-600" />
                    <span>
                      Recommend building{" "}
                      <strong>{gem.recommended_quantity} unit(s)</strong>
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2 pt-2">
                  <Button
                    onClick={() => buildMutation.mutate(gem.id)}
                    disabled={buildMutation.isPending}
                    variant="default"
                    size="sm"
                    className="flex-1"
                  >
                    {buildMutation.isPending ? "Creating..." : "Build Gem"}
                  </Button>
                  <Button
                    onClick={() => dismissMutation.mutate(gem.id)}
                    disabled={dismissMutation.isPending}
                    variant="outline"
                    size="sm"
                  >
                    Dismiss
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Empty filtered state */}
      {filteredGems.length === 0 && gems.length > 0 && (
        <Card>
          <CardContent className="pt-8">
            <div className="text-center text-gray-600">
              No gems match the selected filters.
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default GemRecommendations;
