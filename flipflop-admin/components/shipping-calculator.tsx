"use client";

import { useState } from "react";
import { Zap, Package, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface ShippingEstimate {
  case_model: string;
  estimated_width_cm: number;
  estimated_depth_cm: number;
  estimated_height_cm: number;
  case_weight_kg: number;
  total_weight_kg: number;
  box_width_cm: number;
  box_depth_cm: number;
  box_height_cm: number;
  reasoning: string;
}

interface ShippingCalculatorProps {
  caseModel: string;
  onEstimate: (cost: number, dimensions: ShippingEstimate) => void;
  disabled?: boolean;
}

export function ShippingCalculator({ caseModel, onEstimate, disabled }: ShippingCalculatorProps) {
  const [loading, setLoading] = useState(false);
  const [estimate, setEstimate] = useState<ShippingEstimate | null>(null);
  const [error, setError] = useState<string | null>(null);

  const calculateShippingCost = (estimate: ShippingEstimate): number => {
    const volume = (estimate.box_width_cm * estimate.box_depth_cm * estimate.box_height_cm) / 1000;
    const weight = estimate.total_weight_kg;
    const volumeWeight = volume / 5000;
    const chargeableWeight = Math.max(weight, volumeWeight);
    const baseRate = 2.5;
    const perKgRate = 1.2;
    return Math.round((baseRate + chargeableWeight * perKgRate) * 100) / 100;
  };

  const queryOllama = async () => {
    if (!caseModel || caseModel.trim() === "") {
      setError("Please specify a PC case model");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const prompt = `You are a PC shipping expert. Analyze this PC case model and provide shipping dimension and weight estimates.

PC Case Model: ${caseModel}

Provide your response in JSON format ONLY (no markdown, no explanation):
{
  "case_model": "${caseModel}",
  "estimated_width_cm": <number>,
  "estimated_depth_cm": <number>,
  "estimated_height_cm": <number>,
  "case_weight_kg": <number>,
  "total_weight_kg": <number (case + typical components)>,
  "box_width_cm": <number (with packing)>,
  "box_depth_cm": <number (with packing)>,
  "box_height_cm": <number (with packing)>,
  "reasoning": "<string explaining how you estimated these dimensions>"
}

Be realistic with estimates - add 5-10cm padding for packaging on each dimension.`;

      const response = await fetch("http://localhost:11434/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: process.env.NEXT_PUBLIC_OLLAMA_MODEL,
          prompt: prompt,
          stream: false,
          temperature: 0.3,
        }),
      });

      if (!response.ok) {
        throw new Error(`Ollama error: ${response.status}`);
      }

      const data = await response.json();
      const responseText = data.response || "";

      let estimateData: ShippingEstimate;
      try {
        const jsonMatch = responseText.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
          throw new Error("No JSON found in response");
        }
        estimateData = JSON.parse(jsonMatch[0]);
      } catch {
        throw new Error("Failed to parse Ollama response as JSON");
      }

      setEstimate(estimateData);
      const shippingCost = calculateShippingCost(estimateData);
      onEstimate(shippingCost, estimateData);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to calculate shipping";
      setError(message);
      console.error("Shipping calculator error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Package className="w-3.5 h-3.5 text-blue-400" /> Shipping Calculator (AI-Powered)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        <div className="space-y-2">
          <label className="text-xs text-slate-500 uppercase tracking-wider font-semibold">
            PC Case Model
          </label>
          <input
            type="text"
            value={caseModel}
            disabled
            className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-400 outline-none"
          />
          <p className="text-xs text-slate-500">
            Detected from your build specs
          </p>
        </div>

        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex gap-2">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <span className="text-xs text-red-300">{error}</span>
          </div>
        )}

        {estimate && (
          <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg space-y-2">
            <div className="text-xs font-semibold text-blue-300 mb-2">📦 Estimated Dimensions & Weight</div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-slate-500">Case Dims:</span>
                <span className="text-slate-300 ml-1 font-mono">
                  {estimate.estimated_width_cm}×{estimate.estimated_depth_cm}×{estimate.estimated_height_cm}cm
                </span>
              </div>
              <div>
                <span className="text-slate-500">Case Weight:</span>
                <span className="text-slate-300 ml-1 font-mono">{estimate.case_weight_kg}kg</span>
              </div>
              <div>
                <span className="text-slate-500">Box Dims:</span>
                <span className="text-slate-300 ml-1 font-mono">
                  {estimate.box_width_cm}×{estimate.box_depth_cm}×{estimate.box_height_cm}cm
                </span>
              </div>
              <div>
                <span className="text-slate-500">Total Weight:</span>
                <span className="text-slate-300 ml-1 font-mono">{estimate.total_weight_kg}kg</span>
              </div>
            </div>
            <div className="text-xs text-slate-400 mt-2 p-2 bg-[#0a1119]/50 rounded border border-slate-700">
              <span className="font-semibold text-slate-300">Reasoning: </span>
              {estimate.reasoning}
            </div>
          </div>
        )}

        <Button
          variant="primary"
          size="sm"
          onClick={queryOllama}
          disabled={loading || disabled || !caseModel}
          className="w-full justify-center"
        >
          {loading ? (
            <>
              <Zap className="w-3.5 h-3.5 animate-spin mr-2" />
              Calculating with Qwen2…
            </>
          ) : estimate ? (
            <>
              <Zap className="w-3.5 h-3.5" /> Recalculate
            </>
          ) : (
            <>
              <Zap className="w-3.5 h-3.5" /> Calculate Shipping
            </>
          )}
        </Button>

        <div className="text-xs text-slate-500">
          ✓ Uses local Ollama (Qwen2 7B) to estimate box dimensions based on case model
          <br />
          ✓ Estimates weight including typical components
          <br />
          ✓ Calculates carrier charge based on volumetric and actual weight
        </div>
      </CardContent>
    </Card>
  );
}
