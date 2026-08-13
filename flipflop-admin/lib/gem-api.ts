/**
 * Gem Build API Client
 *
 * Client library for interacting with the FlipFlop API's gem recommendation endpoints.
 * Handles:
 * - Generating new recommendations via Claude API
 * - Fetching recommendation history
 * - Building gems as orders
 * - Dismissing recommendations
 */

import { API_BASE_URL } from "./api";

export interface Gem {
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

export interface GemRecommendationsResponse {
  generated_at: string;
  analysis_period_days: number;
  total_orders_analyzed: number;
  demand_summary: {
    budget_distribution: Record<string, number>;
    popular_use_cases: Record<string, number>;
    top_component_combinations: Record<string, number>;
    insights: Record<string, any>;
  };
  recommendations: Gem[];
}

export interface GemListResponse {
  total: number;
  gems: Gem[];
}

export interface GemBuildActionRequest {
  action: "build" | "dismiss";
  quantity?: number;
  notes?: string;
}

export interface GemBuildActionResponse {
  status: string;
  message: string;
  gem_id: number;
  action: string;
  result?: Record<string, any>;
}

export interface GemDismissResponse {
  status: string;
  message: string;
  gem_id: number;
}

/**
 * Generate new gem recommendations using Claude API analysis.
 *
 * Analyzes order data and market conditions to generate speculative build recommendations.
 *
 * @param analysisDays Number of days of order history to analyze (default: 30)
 * @returns Promise resolving to recommendations with demand summary
 */
export async function generateRecommendations(
  analysisDays: number = 30
): Promise<GemRecommendationsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/gems/recommendations?analysis_days=${analysisDays}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!response.ok) {
    throw new Error(
      `Failed to generate recommendations: ${response.statusText}`
    );
  }

  return response.json();
}

/**
 * Fetch recent gem recommendations with optional filtering.
 *
 * @param riskLevel Filter by risk level: "low", "medium", "high"
 * @param useCase Filter by use case (e.g., "gaming", "workstation")
 * @param limit Maximum number of results
 * @returns Promise resolving to list of gems
 */
export async function getRecommendations(
  riskLevel?: string,
  useCase?: string,
  limit: number = 20
): Promise<GemListResponse> {
  const params = new URLSearchParams();
  if (riskLevel && riskLevel !== "all") params.append("risk_level", riskLevel);
  if (useCase && useCase !== "all") params.append("use_case", useCase);
  params.append("limit", limit.toString());

  const response = await fetch(
    `${API_BASE_URL}/api/gems?${params.toString()}`,
    {
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch recommendations: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch a single gem recommendation by ID.
 *
 * @param gemId ID of the gem to fetch
 * @returns Promise resolving to the gem details
 */
export async function getGem(gemId: number): Promise<Gem> {
  const response = await fetch(`${API_BASE_URL}/api/gems/${gemId}`, {
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch gem: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Build a gem recommendation as an actual order.
 *
 * Creates an Order with the gem's specifications and triggers the standard build workflow.
 *
 * @param gemId ID of the gem to build
 * @param action Action details (quantity, notes)
 * @returns Promise resolving to action result with order reference
 */
export async function buildGem(
  gemId: number,
  action: GemBuildActionRequest
): Promise<GemBuildActionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/gems/${gemId}/build`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(action),
  });

  if (!response.ok) {
    throw new Error(`Failed to build gem: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Dismiss/delete a gem recommendation.
 *
 * Removes the recommendation from view, useful for rejecting builds
 * that aren't suitable or have changed market conditions.
 *
 * @param gemId ID of the gem to dismiss
 * @returns Promise resolving to confirmation
 */
export async function dismissGem(gemId: number): Promise<GemDismissResponse> {
  const response = await fetch(`${API_BASE_URL}/api/gems/${gemId}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to dismiss gem: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Export the API as a single object for convenience.
 * Usage: gemApi.generateRecommendations()
 */
export const gemApi = {
  generateRecommendations,
  getRecommendations,
  getGem,
  buildGem,
  dismissGem,
};
