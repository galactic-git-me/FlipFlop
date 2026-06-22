// pc-flipper-customer/lib/model-manifest.ts

// Maps variant IDs to Sketchfab/3D model URLs
// Format: {slotType: {variantId: url}}
// These will be populated with actual Sketchfab URLs in Phase 2.3

export const MODEL_URLS: Record<string, Record<number, string>> = {
  // GPU variants
  gpu: {
    // For now, using a generic GPU model from Sketchfab
    // Real IDs will be mapped to actual variant IDs from the backend
    1: '/models/gpu/generic-gpu.gltf', // Placeholder
    2: '/models/gpu/generic-gpu.gltf', // Placeholder
    3: '/models/gpu/generic-gpu.gltf', // Placeholder
  },

  // CPU variants
  cpu: {
    1: '/models/cpu/generic-cpu.gltf', // Placeholder
    2: '/models/cpu/generic-cpu.gltf', // Placeholder
    3: '/models/cpu/generic-cpu.gltf', // Placeholder
  },

  // RAM variants
  ram: {
    1: '/models/ram/generic-ram.gltf', // Placeholder
    2: '/models/ram/generic-ram.gltf', // Placeholder
    3: '/models/ram/generic-ram.gltf', // Placeholder
  },

  // Storage variants
  storage: {
    1: '/models/storage/generic-ssd.gltf', // Placeholder
    2: '/models/storage/generic-ssd.gltf', // Placeholder
    3: '/models/storage/generic-hdd.gltf', // Placeholder
  },

  // Cooling variants
  cooling: {
    1: '/models/cooling/generic-cooler.gltf', // Placeholder
    2: '/models/cooling/generic-cooler.gltf', // Placeholder
  },
};

// Helper to get model URL for a specific variant
export function getVariantModelUrl(slotType: string, variantId: number): string {
  const typeUrls = MODEL_URLS[slotType];
  if (!typeUrls) return '';

  const url = typeUrls[variantId];
  return url || '';
}

// Get all model URLs for preloading
export function getAllModelUrls(): string[] {
  const urls: Set<string> = new Set();
  Object.values(MODEL_URLS).forEach((typeUrls) => {
    Object.values(typeUrls).forEach((url) => {
      if (url) urls.add(url);
    });
  });
  return Array.from(urls);
}

// Component positioning (will vary based on case type in future)
export const COMPONENT_POSITIONS: Record<string, { x: number; y: number; z: number }> = {
  gpu: { x: 2, y: 0.5, z: -0.5 },
  cpu: { x: 0, y: 0.5, z: 0.5 },
  ram: { x: -1.5, y: 1.2, z: -1 },
  storage: { x: -2, y: -1, z: 0 },
  cooling: { x: 0, y: 2, z: 0 },
};

// Component scaling (relative to component size)
export const COMPONENT_SCALES: Record<string, number> = {
  gpu: 1,
  cpu: 0.8,
  ram: 0.6,
  storage: 0.7,
  cooling: 1.2,
};
