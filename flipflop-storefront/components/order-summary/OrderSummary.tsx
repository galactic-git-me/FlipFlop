'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useConfiguratorStore } from '@/lib/configurator-store';
import { useOSStore } from '@/lib/os-store';
import './order-summary.css';

interface Quote {
  cpu_name: string;
  gpu_name: string;
  ram_name: string;
  ssd_name: string;
  psu_name: string;
  case_name: string;
  cooler_name: string;
  parts_cost_total: number;
  labor_cost: number;
  overhead_cost: number;
  total_price: number;
}

export function OrderSummary() {
  const router = useRouter();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const components = useConfiguratorStore((state) => ({
    cpu_id: state.cpu_id,
    gpu_id: state.gpu_id,
    ram_id: state.ram_id,
    ssd_id: state.ssd_id,
    psu_id: state.psu_id,
    case_id: state.case_id,
    cooler_id: state.cooler_id,
  }));

  const osSelection = useOSStore((state) => ({
    os: state.selectedOS,
    license: state.selectedLicense,
    theme: state.selectedTheme,
  }));

  // Fetch quote when component IDs change
  useEffect(() => {
    const fetchQuote = async () => {
      setLoading(true);
      try {
        const res = await fetch('/api/quotes/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...components,
            os_id: osSelection.os?.id,
          }),
        });
        if (!res.ok) throw new Error('Failed to generate quote');
        const data = await res.json();
        setQuote(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    if (components.cpu_id) {
      fetchQuote();
    }
  }, [components, osSelection.os?.id]);

  const totalPrice = quote
    ? quote.total_price + (osSelection.os?.price || 0)
    : 0;

  if (loading) {
    return (
      <div className="order-summary-container">
        <div className="order-summary loading">Loading order summary...</div>
      </div>
    );
  }

  return (
    <div className="order-summary-container">
      <div className="order-summary">
        <h2>Order Summary</h2>

        {error && <div className="error-message">{error}</div>}

        {quote && (
          <>
            <div className="summary-section">
              <h3>PC Build</h3>
              <div className="component-summary">
                {quote.cpu_name && <div className="item">CPU: {quote.cpu_name}</div>}
                {quote.gpu_name && <div className="item">GPU: {quote.gpu_name}</div>}
                {quote.ram_name && <div className="item">RAM: {quote.ram_name}</div>}
                {quote.ssd_name && <div className="item">Storage: {quote.ssd_name}</div>}
                {quote.psu_name && <div className="item">PSU: {quote.psu_name}</div>}
                {quote.case_name && <div className="item">Case: {quote.case_name}</div>}
                {quote.cooler_name && (
                  <div className="item">Cooler: {quote.cooler_name}</div>
                )}
              </div>
            </div>

            <div className="summary-section">
              <h3>Operating System</h3>
              <div className="os-summary">
                {osSelection.os && (
                  <div className="item">{osSelection.os.name}</div>
                )}
                {osSelection.license && (
                  <div className="item">License: {osSelection.license.key}</div>
                )}
              </div>
            </div>

            {osSelection.theme && (
              <div className="summary-section">
                <h3>Desktop Theme</h3>
                <div className="theme-summary">
                  <div className="item">
                    {osSelection.theme.name} ({osSelection.theme.category})
                  </div>
                </div>
              </div>
            )}

            <div className="summary-section pricing">
              <div className="price-row">
                <span>Parts</span>
                <span>£{quote.parts_cost_total.toFixed(2)}</span>
              </div>
              <div className="price-row">
                <span>Labor</span>
                <span>£{quote.labor_cost.toFixed(2)}</span>
              </div>
              <div className="price-row">
                <span>Overhead</span>
                <span>£{quote.overhead_cost.toFixed(2)}</span>
              </div>
              {osSelection.os && osSelection.os.price > 0 && (
                <div className="price-row">
                  <span>OS License</span>
                  <span>£{osSelection.os.price.toFixed(2)}</span>
                </div>
              )}
              <div className="price-row total">
                <span>Total</span>
                <span>£{totalPrice.toFixed(2)}</span>
              </div>
            </div>
          </>
        )}

        <div className="summary-actions">
          <button
            className="secondary-button"
            onClick={() => router.back()}
            type="button"
          >
            ← Edit Configuration
          </button>
          <button
            className="cta-button"
            onClick={() => router.push('/order/payment')}
            type="button"
          >
            Continue to Payment →
          </button>
        </div>
      </div>
    </div>
  );
}
