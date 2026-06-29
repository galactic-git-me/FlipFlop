import * as THREE from 'three';

/**
 * Create a stylized PC case with modular design
 */
export function buildPCCase(): THREE.Group {
  const caseGroup = new THREE.Group();
  caseGroup.userData.type = 'case';

  // Main case body (dark metallic)
  const bodyGeometry = new THREE.BoxGeometry(0.4, 0.6, 0.5);
  const bodyMaterial = new THREE.MeshStandardMaterial({
    color: 0x1a1f2b,
    metalness: 0.7,
    roughness: 0.3,
    emissive: 0x0a0f15,
  });
  const caseBody = new THREE.Mesh(bodyGeometry, bodyMaterial);
  caseBody.castShadow = true;
  caseBody.receiveShadow = true;
  caseGroup.add(caseBody);

  // Front panel (slightly different color)
  const frontGeometry = new THREE.BoxGeometry(0.38, 0.58, 0.02);
  const frontMaterial = new THREE.MeshStandardMaterial({
    color: 0x0f1419,
    metalness: 0.8,
    roughness: 0.2,
  });
  const frontPanel = new THREE.Mesh(frontGeometry, frontMaterial);
  frontPanel.position.z = 0.26;
  frontPanel.castShadow = true;
  caseGroup.add(frontPanel);

  // Side vents
  const ventGeometry = new THREE.BoxGeometry(0.35, 0.08, 0.02);
  const ventMaterial = new THREE.MeshStandardMaterial({
    color: 0x000000,
    metalness: 0.5,
    roughness: 0.4,
  });
  for (let i = 0; i < 4; i++) {
    const vent = new THREE.Mesh(ventGeometry, ventMaterial);
    vent.position.y = -0.15 + i * 0.12;
    vent.position.x = 0.21;
    vent.castShadow = true;
    caseGroup.add(vent);
  }

  // Placeholder for internal components visibility
  const internalGlow = new THREE.PointLight(0x4a9eff, 0.3, 1.5);
  internalGlow.position.z = 0;
  caseGroup.add(internalGlow);

  return caseGroup;
}

/**
 * Create a GPU representation (changes case lighting when swapped)
 */
export function buildGPU(gpuId?: number): THREE.Group {
  const gpuGroup = new THREE.Group();
  gpuGroup.userData.type = 'gpu';

  // GPU card body
  const cardGeometry = new THREE.BoxGeometry(0.12, 0.08, 0.25);
  const cardMaterial = new THREE.MeshStandardMaterial({
    color: 0x2a3f5f,
    metalness: 0.6,
    roughness: 0.4,
  });
  const gpuCard = new THREE.Mesh(cardGeometry, cardMaterial);
  gpuCard.castShadow = true;
  gpuCard.receiveShadow = true;
  gpuGroup.add(gpuCard);

  // Cooling fans (2 circular faces)
  const fanGeometry = new THREE.CylinderGeometry(0.04, 0.04, 0.01, 16);
  const fanMaterial = new THREE.MeshStandardMaterial({
    color: 0x1a1a1a,
    metalness: 0.4,
    roughness: 0.6,
  });

  for (let i = 0; i < 2; i++) {
    const fan = new THREE.Mesh(fanGeometry, fanMaterial);
    fan.rotation.x = Math.PI / 2;
    fan.position.y = -0.01 + i * 0.04;
    fan.castShadow = true;
    gpuGroup.add(fan);
  }

  // GPU-specific glow based on tier (changes lighting dynamics)
  const glowColor = gpuId && gpuId > 2 ? 0xff6b35 : 0x4a9eff;
  const gpuGlow = new THREE.PointLight(glowColor, 0.4, 1.2);
  gpuGlow.position.z = 0.1;
  gpuGroup.add(gpuGlow);

  return gpuGroup;
}

/**
 * Create CPU cooler (changes tower height)
 */
export function buildCooler(coolerId?: number): THREE.Group {
  const coolerGroup = new THREE.Group();
  coolerGroup.userData.type = 'cooler';

  // Base plate
  const baseGeometry = new THREE.BoxGeometry(0.08, 0.02, 0.08);
  const baseMaterial = new THREE.MeshStandardMaterial({
    color: 0x3a4a5a,
    metalness: 0.7,
    roughness: 0.3,
  });
  const basePlate = new THREE.Mesh(baseGeometry, baseMaterial);
  basePlate.castShadow = true;
  basePlate.receiveShadow = true;
  coolerGroup.add(basePlate);

  // Tower height varies by cooler tier
  const towerHeight = coolerId && coolerId > 2 ? 0.15 : 0.1;
  const towerGeometry = new THREE.BoxGeometry(0.06, towerHeight, 0.06);
  const towerMaterial = new THREE.MeshStandardMaterial({
    color: 0x2a3a4a,
    metalness: 0.6,
    roughness: 0.4,
  });
  const tower = new THREE.Mesh(towerGeometry, towerMaterial);
  tower.position.y = towerHeight / 2 + 0.01;
  tower.castShadow = true;
  tower.receiveShadow = true;
  coolerGroup.add(tower);

  // Heatsink fins (simple representation)
  const finGeometry = new THREE.BoxGeometry(0.08, 0.005, 0.08);
  const finMaterial = new THREE.MeshStandardMaterial({
    color: 0x1a2a3a,
    metalness: 0.8,
    roughness: 0.2,
  });
  for (let i = 0; i < 4; i++) {
    const fin = new THREE.Mesh(finGeometry, finMaterial);
    fin.position.y = 0.03 + i * 0.025;
    fin.castShadow = true;
    coolerGroup.add(fin);
  }

  // Fan
  const fanGeometry = new THREE.CylinderGeometry(0.04, 0.04, 0.01, 16);
  const fanMaterial = new THREE.MeshStandardMaterial({
    color: 0x1a1a1a,
    metalness: 0.4,
    roughness: 0.6,
  });
  const fan = new THREE.Mesh(fanGeometry, fanMaterial);
  fan.rotation.x = Math.PI / 2;
  fan.position.y = towerHeight + 0.06;
  fan.castShadow = true;
  coolerGroup.add(fan);

  return coolerGroup;
}

/**
 * Setup premium lighting for the 3D scene
 */
export function setupLighting(scene: THREE.Scene): void {
  // Warm keylight (main illumination)
  const keyLight = new THREE.DirectionalLight(0xffd4a3, 1.2);
  keyLight.position.set(2, 1.5, 1.5);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.width = 2048;
  keyLight.shadow.mapSize.height = 2048;
  keyLight.shadow.camera.far = 10;
  scene.add(keyLight);

  // Soft fill light
  const fillLight = new THREE.DirectionalLight(0xaad4f0, 0.6);
  fillLight.position.set(-1.5, 1, -1.5);
  scene.add(fillLight);

  // Ambient for base illumination
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
  scene.add(ambientLight);

  // Subtle back light for depth
  const backLight = new THREE.DirectionalLight(0xffffff, 0.2);
  backLight.position.set(0, 0, -2);
  scene.add(backLight);
}

/**
 * Create camera positioned for optimal PC case viewing
 */
export function createConfiguratorCamera(width: number, height: number): THREE.PerspectiveCamera {
  const camera = new THREE.PerspectiveCamera(
    45,
    width / height,
    0.1,
    1000
  );
  camera.position.set(0.6, 0.5, 0.8);
  camera.lookAt(0, 0.2, 0);
  return camera;
}

/**
 * Get material preset for different component finishes
 */
export function getMaterialPreset(type: 'matte-metal' | 'glossy-plastic' | 'rgb-accent') {
  const presets = {
    'matte-metal': new THREE.MeshStandardMaterial({
      color: 0x4a5a6a,
      metalness: 0.6,
      roughness: 0.6,
    }),
    'glossy-plastic': new THREE.MeshStandardMaterial({
      color: 0x3a4a5a,
      metalness: 0.2,
      roughness: 0.8,
    }),
    'rgb-accent': new THREE.MeshStandardMaterial({
      color: 0xff6b35,
      metalness: 0.7,
      roughness: 0.3,
      emissive: 0xaa3311,
    }),
  };
  return presets[type];
}
