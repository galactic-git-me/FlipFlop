// Simple script to generate placeholder glTF models
// These can be replaced with real downloaded models from Sketchfab

const fs = require('fs');
const path = require('path');

const modelsDir = path.join(__dirname, '../public/models');

// Simple colored box glTF (minimal valid format)
function createSimpleModel(color) {
  return {
    asset: { version: '2.0' },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0 }],
    meshes: [{
      primitives: [{
        attributes: { POSITION: 0, NORMAL: 1 },
        indices: 2,
        material: 0
      }]
    }],
    materials: [{
      pbrMetallicRoughness: { baseColorFactor: color }
    }],
    accessors: [
      { bufferView: 0, componentType: 5126, type: 'VEC3', count: 8 },
      { bufferView: 1, componentType: 5126, type: 'VEC3', count: 8 },
      { bufferView: 2, componentType: 5125, type: 'SCALAR', count: 36 }
    ],
    bufferViews: [
      { buffer: 0, byteOffset: 0, byteStride: 12 },
      { buffer: 0, byteOffset: 96, byteStride: 12 },
      { buffer: 0, byteOffset: 192 }
    ],
    buffers: [{ byteLength: 336 }]
  };
}

// Models to create (component type -> color RGBA)
const models = {
  gpu: [0.22, 0.77, 0.56, 1], // accent green
  cpu: [1, 0.75, 0.14, 1],    // yellow
  ram: [0.38, 0.65, 0.98, 1], // blue
  storage: [0.5, 0.57, 0.95, 1], // indigo
  cooling: [0.94, 0.27, 0.27, 1]  // red
};

// Generate placeholder models for each type
Object.entries(models).forEach(([type, color]) => {
  const dir = path.join(modelsDir, type);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  // Create 3 placeholder variants per type (2 for cooling)
  const variants = type === 'cooling' ? 2 : 3;
  for (let i = 1; i <= variants; i++) {
    const filename = path.join(dir, `variant-${i}.gltf`);
    const gltf = createSimpleModel(color);
    fs.writeFileSync(filename, JSON.stringify(gltf, null, 2));
    console.log(`Created: ${filename}`);
  }
});

console.log('\nPlaceholder models generated.');
console.log('Next: Download real models from Sketchfab and replace these files.');
