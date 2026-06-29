'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import { useOSStore, type Theme } from '@/lib/os-store';
import './theme-picker.css';

export function ThemePicker() {
  const [themes, setThemes] = useState<Theme[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectedTheme = useOSStore((state) => state.selectedTheme);
  const setTheme = useOSStore((state) => state.setTheme);
  const selectedOS = useOSStore((state) => state.selectedOS);

  // Fetch themes on mount
  useEffect(() => {
    const fetchThemes = async () => {
      try {
        setLoading(true);
        const res = await fetch('/api/themes');
        if (!res.ok) throw new Error('Failed to fetch themes');
        const data = await res.json();
        setThemes(data.items || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    fetchThemes();
  }, []);

  // Hide theme picker for non-Windows OS
  if (!selectedOS?.name.includes('Windows')) {
    return null;
  }

  if (loading) {
    return (
      <div className="theme-picker">
        <h3>Desktop Theme (Rainmeter)</h3>
        <div className="loading-message">Loading themes...</div>
      </div>
    );
  }

  return (
    <div className="theme-picker">
      <h3>Desktop Theme (Rainmeter)</h3>
      <p className="subtitle">Customize your desktop aesthetic with pre-made Rainmeter themes</p>

      {error && <div className="error-message">{error}</div>}

      {themes.length === 0 ? (
        <div className="no-themes">No themes available</div>
      ) : (
        <div className="theme-grid">
          {themes.map((theme) => (
            <button
              key={theme.id}
              className={`theme-card ${selectedTheme?.id === theme.id ? 'selected' : ''}`}
              onClick={() => setTheme(theme)}
              type="button"
              aria-pressed={selectedTheme?.id === theme.id}
              aria-label={`Select ${theme.name} theme`}
            >
              <div className="theme-preview">
                <Image
                  src={theme.preview_image_url}
                  alt={theme.name}
                  width={200}
                  height={150}
                  style={{ objectFit: 'cover' }}
                  priority={false}
                />
                <div className="theme-category">{theme.category}</div>
              </div>

              <div className="theme-info">
                <h4>{theme.name}</h4>
                <p className="theme-description">{theme.widgets_included}</p>
                <span className="theme-select-label">
                  {selectedTheme?.id === theme.id ? '✓ Selected' : 'Select'}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
