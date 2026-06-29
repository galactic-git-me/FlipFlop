# 3D PC Configurator

Premium 3D PC configurator UI with real-time pricing and component selection.

## Features

- **3D Viewport** with Three.js
  - Interactive rotation (mouse drag)
  - Auto-rotation when idle
  - Responsive canvas sizing
  - Premium lighting (warm keylight + soft fill)

- **Component Picker**
  - 7 component categories (CPU, GPU, RAM, SSD, PSU, Case, Cooler)
  - Real-time availability status
  - "Most Popular" recommendations
  - Live price updates

- **Real-time Pricing Sidebar**
  - Parts subtotal
  - Labor cost (£87.50)
  - Overhead calculation (10%)
  - Total price with budget indicator
  - "Within budget" status (green/red)

- **State Management** with Zustand
  - Component selections persist
  - Budget tracking
  - Component ID management

## Components

### Configurator3D
3D scene rendering using Three.js. Supports:
- Interactive PC case model
- Dynamic GPU and cooler components
- Auto-rotation with idle detection
- Responsive resizing

**Props:**
```tsx
components: {
  gpu_id: number | null;
  cooler_id: number | null;
  cpu_id?: number | null;
  ram_id?: number | null;
  ssd_id?: number | null;
  psu_id?: number | null;
  case_id?: number | null;
}
```

### ComponentPicker
Dropdown selector for a single component category.

**Props:**
```tsx
componentType: 'cpu' | 'gpu' | 'ram' | 'ssd' | 'psu' | 'case' | 'cooler'
label?: string  // Custom label (defaults to uppercase component type)
```

### PricingSidebar
Real-time pricing calculation and budget status.

**Props:**
```tsx
budget: number           // Budget ceiling in GBP
onContinue?: () => void  // Callback for "Continue to Payment" button
```

## State Management

Uses Zustand store at `lib/configurator-store.ts`:

```ts
const store = useConfiguratorStore();

// Select a component
store.setComponent('gpu', 2);

// Get all component IDs
const ids = store.getComponentIds();

// Reset all
store.reset();

// Update budget
store.setBudget(2000);
```

## Styling

Premium dark theme with:
- Deep charcoal surface (#0f1419)
- Gold accents (#d4af37)
- Smooth transitions
- Responsive grid layout
- Custom scrollbar styling

All styles are in `configurator.css`.

## Three.js Utilities

Helper functions in `lib/three-utils.ts`:
- `buildPCCase()` - Create case geometry
- `buildGPU()` - Create GPU model (color varies by tier)
- `buildCooler()` - Create CPU cooler (height varies by tier)
- `setupLighting()` - Premium scene lighting
- `createConfiguratorCamera()` - Optimal camera positioning
- `getMaterialPreset()` - Material presets for components

## Testing

Comprehensive test suite in `tests/configurator.test.tsx`:
- Component picker functionality
- Pricing calculations
- State management
- Budget indicators

Run tests:
```bash
npm test -- configurator.test.tsx
```

## Integration

Use in a page:

```tsx
'use client';

import { Configurator3D } from '@/components/configurator/Configurator3D';
import { ComponentPicker } from '@/components/configurator/ComponentPicker';
import { PricingSidebar } from '@/components/configurator/PricingSidebar';
import '@/components/configurator/configurator.css';

export default function ConfiguratorPage() {
  const components = useConfiguratorStore(state => ({
    cpu_id: state.cpu_id,
    gpu_id: state.gpu_id,
    // ... other components
  }));

  return (
    <div className="configurator-container">
      <div className="configurator-viewport">
        <Configurator3D components={components} />
      </div>
      <div className="configurator-sidebar">
        <ComponentPicker componentType="cpu" />
        <ComponentPicker componentType="gpu" />
        {/* ... more pickers ... */}
        <PricingSidebar budget={1200} onContinue={() => {}} />
      </div>
    </div>
  );
}
```

## Future Enhancements

- [ ] Load actual 3D models from Meshy AI
- [ ] Real API integration for component data
- [ ] Component compatibility checking
- [ ] Build history and favorites
- [ ] Export configuration as PDF
- [ ] Share configuration links
- [ ] Component comparison view
- [ ] Video setup guide
