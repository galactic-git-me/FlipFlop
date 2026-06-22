'use client';

import { useState } from 'react';
import type { BuildState, PublicSlotWithVariants } from '@/lib/types';

interface Props {
  build: BuildState;
  slots: PublicSlotWithVariants[];
  onComponentClick: (slotType: string) => void;
}

const COMPONENT_ICONS: Record<string, string> = {
  gpu: '🎮',
  cpu: '⚙️',
  ram: '💾',
  storage: '💿',
  cooling: '❄️',
};

export function ModelViewer3D({ build, slots, onComponentClick }: Props) {
  const [selectedComponent, setSelectedComponent] = useState<string | null>(null);

  return (
    <div className="w-full h-full bg-gradient-to-b from-gray-900 to-black rounded-lg flex flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h3 className="text-xl font-bold text-white mb-2">Your Build</h3>
        <p className="text-sm text-muted">Click components to customize</p>
      </div>

      <div className="flex flex-wrap justify-center gap-6">
        {Object.entries(build.slots).map(([slotType, variant]) => (
          <button
            key={slotType}
            onClick={() => onComponentClick(slotType)}
            className="flex flex-col items-center gap-3 p-4 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors cursor-pointer border border-gray-700 hover:border-green-500"
          >
            <div className="text-4xl">{COMPONENT_ICONS[slotType] || '📦'}</div>
            <div className="text-center">
              <p className="text-xs font-bold uppercase text-gray-400">{slotType}</p>
              {variant && (
                <>
                  <p className="text-sm font-semibold text-white">{variant.title}</p>
                  <p className="text-xs text-green-400">£{variant.display_price}</p>
                </>
              )}
            </div>
          </button>
        ))}
      </div>

      <div className="text-xs text-muted text-center">
        <p>3D visualization coming soon</p>
      </div>
    </div>
  );
}
