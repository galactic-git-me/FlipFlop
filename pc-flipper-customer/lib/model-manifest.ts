// pc-flipper-customer/lib/model-manifest.ts
//
// 3D Model URLs for PC Component Configurator
//
// This file maps component types and variants to glTF 3D model URLs.
// See MODEL_SOURCING_GUIDE.md for comprehensive sourcing and integration instructions.
//
// Quick Start:
// 1. Download models from Sketchfab (https://sketchfab.com)
// 2. Place .gltf files in: public/models/{type}/variant-{N}.gltf
// 3. Models automatically load - no code changes needed!
//
// Model Requirements:
// - Format: .gltf or .glb (glTF 2.0)
// - Size: < 2MB per model (aim for 300-800KB)
// - License: CC0 or CC-BY (free commercial use)
// - Placement: public/models/gpu/, cpu/, ram/, storage/, cooling/
//
// Recommended Models by Type:
// GPU:     3 variants (RTX 4090, RTX 3070, budget)
// CPU:     3 variants (i9, i7, i5)
// RAM:     3 variants (DDR5, DDR4, DDR3)
// Storage: 3 variants (M.2 NVMe, 2.5" SSD, 3.5" HDD)
// Cooling: 2-3 variants (air tower, liquid AIO, compact)

export const MODEL_URLS: Record<string, Record<number, string>> = {
  /**
   * GPU (Graphics Card) Models
   * High-end → Mid-range → Budget variants
   *
   * Recommended searches:
   * - High-end: "nvidia rtx 4090", "geforce graphics card"
   * - Mid-range: "graphics card gaming", "RTX 3070"
   * - Budget: "budget gpu", "old graphics card"
   *
   * File size: 200-900KB per model
   * Look for: Realistic dual/triple fan designs, visible heatsinks
   */
  gpu: {
    1: '/models/gpu/variant-1.gltf',  // High-end GPU (e.g., RTX 4090)
    2: '/models/gpu/variant-2.gltf',  // Mid-range GPU (e.g., RTX 3070)
    3: '/models/gpu/variant-3.gltf',  // Budget GPU (e.g., older card)
  },

  /**
   * CPU (Processor) Models
   * High-end → Mid-range → Budget variants
   *
   * Recommended searches:
   * - High-end: "intel core i9", "AMD Ryzen 9"
   * - Mid-range: "i7 processor", "ryzen 7"
   * - Budget: "budget processor", "i5 cpu"
   *
   * File size: 200-900KB per model
   * Look for: CPU chip with visible socket/pins, ideally with heatsink
   */
  cpu: {
    1: '/models/cpu/variant-1.gltf',  // High-end CPU (e.g., i9/Ryzen 9)
    2: '/models/cpu/variant-2.gltf',  // Mid-range CPU (e.g., i7/Ryzen 7)
    3: '/models/cpu/variant-3.gltf',  // Budget CPU (e.g., i5)
  },

  /**
   * RAM (Memory Module) Models
   * Modern → Standard → Legacy variants
   *
   * Recommended searches:
   * - High-end: "DDR5 memory", "ddr5 ram stick"
   * - Mid-range: "DDR4 memory", "RAM module"
   * - Budget: "DDR3 memory", "old RAM"
   *
   * File size: 100-500KB per model
   * Look for: DIMM form factor (vertical stick), recognizable heatspreader
   */
  ram: {
    1: '/models/ram/variant-1.gltf',  // High-end DDR5 RAM
    2: '/models/ram/variant-2.gltf',  // Mid-range DDR4/5
    3: '/models/ram/variant-3.gltf',  // Budget/Legacy DDR3
  },

  /**
   * Storage (SSD/HDD) Models
   * Fast → Medium → Traditional variants
   *
   * Recommended searches:
   * - Fast: "NVMe SSD", "M.2 drive"
   * - Medium: "2.5 SSD", "ssd drive"
   * - Traditional: "hard drive", "3.5 HDD"
   *
   * File size: 100-600KB per model
   * Look for: Recognizable form factors (thin for M.2, flat for 2.5", large for 3.5")
   */
  storage: {
    1: '/models/storage/variant-1.gltf',  // NVMe M.2 (fastest, smallest)
    2: '/models/storage/variant-2.gltf',  // 2.5" SSD (medium)
    3: '/models/storage/variant-3.gltf',  // 3.5" HDD (traditional, large)
  },

  /**
   * Cooling (CPU Cooler) Models
   * Air tower → Liquid cooler → Compact variants
   *
   * Recommended searches:
   * - Air tower: "CPU cooler", "tower heatsink", "noctua cooler"
   * - Liquid: "liquid cooler", "water cooler AIO", "all in one"
   * - Compact: "low profile cooler", "compact cpu cooler"
   *
   * File size: 300-1500KB per model (larger files acceptable here)
   * Look for: Detailed fin designs (air), prominent radiator (liquid)
   */
  cooling: {
    1: '/models/cooling/variant-1.gltf',  // Air tower cooler (Noctua style)
    2: '/models/cooling/variant-2.gltf',  // Liquid cooler (AIO)
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
