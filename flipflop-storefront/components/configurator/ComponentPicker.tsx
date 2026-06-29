'use client';

import { useEffect, useState } from 'react';
import { useConfiguratorStore } from '@/lib/configurator-store';

interface Component {
  id: number;
  name: string;
  price: number;
  in_stock: boolean;
  recommended?: boolean;
}

interface ComponentPickerProps {
  componentType: 'cpu' | 'gpu' | 'ram' | 'ssd' | 'psu' | 'case' | 'cooler';
  label?: string;
}

export function ComponentPicker({ componentType, label }: ComponentPickerProps) {
  const [components, setComponents] = useState<Component[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const selectedId = useConfiguratorStore((state) => state[`${componentType}_id`]);
  const setComponent = useConfiguratorStore((state) => state.setComponent);

  useEffect(() => {
    const fetchComponents = async () => {
      try {
        setIsLoading(true);
        // Mock data - in production this would call the actual API
        const mockComponents: Record<string, Component[]> = {
          cpu: [
            { id: 1, name: 'Intel i5-13600K', price: 320, in_stock: true, recommended: true },
            { id: 2, name: 'Intel i7-13700K', price: 480, in_stock: true },
            { id: 3, name: 'Intel i9-13900K', price: 680, in_stock: false },
          ],
          gpu: [
            { id: 1, name: 'RTX 4070', price: 500, in_stock: true, recommended: true },
            { id: 2, name: 'RTX 4080', price: 850, in_stock: true },
            { id: 3, name: 'RTX 4090', price: 1500, in_stock: false },
          ],
          ram: [
            { id: 1, name: '32GB DDR5', price: 160, in_stock: true, recommended: true },
            { id: 2, name: '64GB DDR5', price: 320, in_stock: true },
            { id: 3, name: '128GB DDR5', price: 640, in_stock: false },
          ],
          ssd: [
            { id: 1, name: '1TB NVMe', price: 120, in_stock: true, recommended: true },
            { id: 2, name: '2TB NVMe', price: 240, in_stock: true },
            { id: 3, name: '4TB NVMe', price: 480, in_stock: false },
          ],
          psu: [
            { id: 1, name: '850W Gold', price: 140, in_stock: true, recommended: true },
            { id: 2, name: '1000W Platinum', price: 200, in_stock: true },
            { id: 3, name: '1200W Titanium', price: 300, in_stock: false },
          ],
          case: [
            { id: 1, name: 'NZXT H7 Flow', price: 150, in_stock: true, recommended: true },
            { id: 2, name: 'Corsair 5000T', price: 280, in_stock: true },
            { id: 3, name: 'Lian Li O11', price: 180, in_stock: false },
          ],
          cooler: [
            { id: 1, name: 'Arctic Liquid Freezer II', price: 110, in_stock: true, recommended: true },
            { id: 2, name: 'EK AIO', price: 180, in_stock: true },
            { id: 3, name: 'Noctua NH-D15', price: 95, in_stock: false },
          ],
        };

        setComponents(mockComponents[componentType] || []);
      } finally {
        setIsLoading(false);
      }
    };

    fetchComponents();
  }, [componentType]);

  const selected = components.find((c) => c.id === selectedId);

  const displayLabel = label || componentType.toUpperCase();

  return (
    <div className="component-picker">
      <label htmlFor={`${componentType}-select`}>{displayLabel}</label>
      <select
        id={`${componentType}-select`}
        value={selectedId || ''}
        onChange={(e) => {
          const id = parseInt(e.target.value);
          if (!isNaN(id)) {
            setComponent(componentType, id);
          }
        }}
        disabled={isLoading}
      >
        <option value="">
          {isLoading ? 'Loading...' : `Select ${componentType}`}
        </option>
        {components.map((comp) => (
          <option key={comp.id} value={comp.id}>
            {comp.name} • £{comp.price.toFixed(2)}
            {comp.recommended ? ' ⭐' : ''}
          </option>
        ))}
      </select>

      {selected && (
        <div className="component-info">
          <div className="component-name">{selected.name}</div>
          <div className="component-price">£{selected.price.toFixed(2)}</div>
          {selected.in_stock && <div className="in-stock">✓ In Stock</div>}
          {!selected.in_stock && <div className="in-stock" style={{ color: '#f97316' }}>⚠ On Order</div>}
        </div>
      )}
    </div>
  );
}
