'use client';

import { useEffect, useState } from 'react';
import { useConfiguratorStore } from '@/lib/configurator-store';

interface QuoteData {
  parts_cost_total: number;
  labor_cost: number;
  overhead_cost: number;
  total_price: number;
}

interface PricingSidebarProps {
  budget: number;
  onContinue?: () => void;
}

export function PricingSidebar({ budget, onContinue }: PricingSidebarProps) {
  const [quote, setQuote] = useState<QuoteData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const components = useConfiguratorStore((state) => ({
    cpu_id: state.cpu_id,
    gpu_id: state.gpu_id,
    ram_id: state.ram_id,
    ssd_id: state.ssd_id,
    psu_id: state.psu_id,
    case_id: state.case_id,
    cooler_id: state.cooler_id,
  }));

  useEffect(() => {
    const generateQuote = async () => {
      // Mock calculation - in production this would call the API
      const componentPrices: Record<string, number> = {
        cpu_1: 320,
        cpu_2: 480,
        cpu_3: 680,
        gpu_1: 500,
        gpu_2: 850,
        gpu_3: 1500,
        ram_1: 160,
        ram_2: 320,
        ram_3: 640,
        ssd_1: 120,
        ssd_2: 240,
        ssd_3: 480,
        psu_1: 140,
        psu_2: 200,
        psu_3: 300,
        case_1: 150,
        case_2: 280,
        case_3: 180,
        cooler_1: 110,
        cooler_2: 180,
        cooler_3: 95,
      };

      setIsLoading(true);

      try {
        // Simulate API delay
        await new Promise((resolve) => setTimeout(resolve, 200));

        let partsCost = 0;
        Object.entries(components).forEach(([key, id]) => {
          if (id !== null) {
            const priceKey = `${key.replace('_id', '')}_${id}`;
            partsCost += componentPrices[priceKey] || 0;
          }
        });

        const laborCost = 87.5; // Fixed labor cost
        const overhead = partsCost * 0.1; // 10% overhead
        const totalPrice = partsCost + laborCost + overhead;

        setQuote({
          parts_cost_total: partsCost,
          labor_cost: laborCost,
          overhead_cost: overhead,
          total_price: totalPrice,
        });
      } finally {
        setIsLoading(false);
      }
    };

    generateQuote();
  }, [components]);

  if (!quote) {
    return (
      <div className="pricing-sidebar loading">
        <h3>Build Summary</h3>
        <div style={{ opacity: 0.5, textAlign: 'center', paddingTop: '20px' }}>
          Calculating...
        </div>
      </div>
    );
  }

  const withinBudget = quote.total_price <= budget;
  const percentOfBudget = Math.min((quote.total_price / budget) * 100, 100);

  return (
    <div className="pricing-sidebar">
      <h3>Build Summary</h3>

      <div className="pricing-row">
        <span>Parts</span>
        <span>£{quote.parts_cost_total.toFixed(2)}</span>
      </div>

      <div className="pricing-row">
        <span>Labor (3.5h)</span>
        <span>£{quote.labor_cost.toFixed(2)}</span>
      </div>

      <div className="pricing-row">
        <span>Overhead (10%)</span>
        <span>£{quote.overhead_cost.toFixed(2)}</span>
      </div>

      <div className="pricing-row total">
        <span>Total</span>
        <span className={withinBudget ? 'within-budget' : 'over-budget'}>
          £{quote.total_price.toFixed(2)}
        </span>
      </div>

      <div className="budget-indicator">
        <div className="budget-bar">
          <div
            className="budget-used"
            style={{ width: `${percentOfBudget}%` }}
          />
        </div>
        <div className="budget-text">
          {withinBudget
            ? '✓ Within Budget'
            : `⚠ Over Budget by £${(quote.total_price - budget).toFixed(2)}`}
        </div>
      </div>

      <button
        className="cta-button"
        onClick={onContinue}
        disabled={isLoading}
      >
        {isLoading ? 'Calculating...' : 'Continue to Payment'}
      </button>
    </div>
  );
}
