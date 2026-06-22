// pc-flipper-customer/lib/model-manifest.ts

// Maps variant IDs to 3D model URLs
// IMPORTANT: These are placeholder URLs. To get real 3D models:
// 1. Go to https://sketchfab.com
// 2. Search for free CC-licensed models (e.g., "PC case", "graphics card", "CPU cooler")
// 3. Download the glTF/GLB version
// 4. Place in public/models/{slotType}/{filename}.gltf
// 5. Update the URLs below

export const MODEL_URLS: Record<string, Record<number, string>> = {
  // GPU variants - search Sketchfab for "graphics card" or specific GPU models
  gpu: {
    1: '/models/gpu/variant-1.gltf',  // Placeholder - replace with real model
    2: '/models/gpu/variant-2.gltf',  // Placeholder - replace with real model
    3: '/models/gpu/variant-3.gltf',  // Placeholder - replace with real model
  },

  // CPU variants - search Sketchfab for "CPU" or "processor"
  cpu: {
    1: '/models/cpu/variant-1.gltf',  // Placeholder - replace with real model
    2: '/models/cpu/variant-2.gltf',  // Placeholder - replace with real model
    3: '/models/cpu/variant-3.gltf',  // Placeholder - replace with real model
  },

  // RAM variants - search Sketchfab for "RAM" or "memory stick"
  ram: {
    1: '/models/ram/variant-1.gltf',  // Placeholder - replace with real model
    2: '/models/ram/variant-2.gltf',  // Placeholder - replace with real model
    3: '/models/ram/variant-3.gltf',  // Placeholder - replace with real model
  },

  // Storage variants - search Sketchfab for "SSD" or "hard drive"
  storage: {
    1: '/models/storage/variant-1.gltf',  // Placeholder - SSD model
    2: '/models/storage/variant-2.gltf',  // Placeholder - SSD model
    3: '/models/storage/variant-3.gltf',  // Placeholder - HDD model
  },

  // Cooling variants - search Sketchfab for "CPU cooler" or "heatsink"
  cooling: {
    1: '/models/cooling/variant-1.gltf',  // Placeholder - replace with real model
    2: '/models/cooling/variant-2.gltf',  // Placeholder - replace with real model
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
