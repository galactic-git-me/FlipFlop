'use client';

import { OSSelector } from '@/components/os-selection/OSSelector';
import { ThemePicker } from '@/components/theme-picker/ThemePicker';
import '@/components/configurator/configurator.css';

export function OSAndThemeFlow() {
  return (
    <div className="os-theme-flow">
      <OSSelector />
      <ThemePicker />
    </div>
  );
}
