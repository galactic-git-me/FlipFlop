'use client';

import { useEffect, useState } from 'react';
import { useOSStore, type OSOption, type LicenseKey } from '@/lib/os-store';
import './os-selection.css';

export function OSSelector() {
  const [osOptions, setOSOptions] = useState<OSOption[]>([]);
  const [licenses, setLicenses] = useState<LicenseKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectedOS = useOSStore((state) => state.selectedOS);
  const selectedLicense = useOSStore((state) => state.selectedLicense);
  const setOS = useOSStore((state) => state.setOS);
  const setLicense = useOSStore((state) => state.setLicense);

  // Fetch OS options on mount
  useEffect(() => {
    const fetchOS = async () => {
      try {
        setLoading(true);
        const res = await fetch('/api/os-options');
        if (!res.ok) throw new Error('Failed to fetch OS options');
        const data = await res.json();
        setOSOptions(data.items || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    fetchOS();
  }, []);

  // Fetch licenses when Windows is selected
  useEffect(() => {
    const fetchLicenses = async () => {
      if (selectedOS?.name.includes('Windows')) {
        try {
          const res = await fetch('/api/licenses/available?type=windows');
          if (!res.ok) throw new Error('Failed to fetch licenses');
          const data = await res.json();
          setLicenses(data.items || []);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } else {
        setLicenses([]);
      }
    };
    fetchLicenses();
  }, [selectedOS]);

  if (loading) {
    return <div className="os-selector loading">Loading operating system options...</div>;
  }

  return (
    <div className="os-selector">
      <h3>Operating System & License</h3>
      {error && <div className="error-message">{error}</div>}

      <div className="os-options">
        {osOptions.map((os) => (
          <label key={os.id} className="os-option">
            <input
              type="radio"
              name="os"
              value={os.id}
              checked={selectedOS?.id === os.id}
              onChange={() => setOS(os)}
              aria-label={`Select ${os.name}`}
            />
            <span className="os-name">{os.name}</span>
            <span className="os-price">+£{os.price.toFixed(2)}</span>
          </label>
        ))}
      </div>

      {selectedOS?.name.includes('Windows') && (
        <div className="license-selection">
          <label htmlFor="license-key">License Key:</label>
          <select
            id="license-key"
            value={selectedLicense?.id || ''}
            onChange={(e) => {
              const license = licenses.find((l) => l.id === parseInt(e.target.value, 10));
              setLicense(license || null);
            }}
            aria-label="Select Windows license key"
          >
            <option value="">Select a license</option>
            {licenses.map((license) => (
              <option key={license.id} value={license.id}>
                {license.key} — {license.available ? '✓ Available' : '⚠ On Order'}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
