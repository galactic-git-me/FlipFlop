// pc-flipper-customer/lib/model-helpers.ts
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

// Model caching to prevent duplicate downloads
const modelCache = new Map<string, THREE.Group>();
const gltfLoader = new GLTFLoader();

// localStorage management for persisting models across sessions
const STORAGE_KEY = 'flipflop_3d_models';

const storageManager = {
  async saveToStorage(url: string, gltf: any) {
    try {
      // Only cache if localStorage is available and size is reasonable
      const serialized = JSON.stringify(gltf);
      if (serialized.length > 5 * 1024 * 1024) {
        // Skip if > 5MB
        return;
      }

      const store = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      store[url] = {
        data: gltf,
        cached_at: Date.now(),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    } catch (error) {
      // Silently fail if localStorage is full or disabled
      console.debug('Failed to cache model:', error);
    }
  },

  getFromStorage(url: string): any | null {
    try {
      const store = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      const cached = store[url];

      if (cached) {
        // Cache hit - return the data
        return cached.data;
      }
    } catch (error) {
      console.debug('Failed to retrieve cached model:', error);
    }
    return null;
  },

  clearStorage() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.debug('Failed to clear storage:', error);
    }
  },
};

export interface SceneConfig {
  canvasContainer: HTMLDivElement;
  width: number;
  height: number;
}

export interface ModelReference {
  mesh: THREE.Group | THREE.Mesh;
  slotType: string;
}

export class PCBuilderScene {
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  renderer: THREE.WebGLRenderer;
  raycaster: THREE.Raycaster;
  mouse: THREE.Vector2;
  models: Map<string, ModelReference> = new Map();
  autoRotationEnabled: boolean = true;
  autoRotationSpeed: number = 0.003;
  lastInteractionTime: number = Date.now();
  interactionIdleTime: number = 3000; // Resume auto-rotate after 3s of no interaction
  animationFrameId: number | null = null;
  isDragging: boolean = false;
  previousMousePosition: { x: number; y: number } = { x: 0, y: 0 };
  rotation: { x: number; y: number } = { x: 0, y: 0 };
  dragSensitivity: number = 0.005;

  constructor(config: SceneConfig) {
    // Scene setup
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0f0f11);

    // Camera
    const aspect = config.width / config.height;
    this.camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);
    this.camera.position.set(5, 3, 5);
    this.camera.lookAt(0, 0, 0);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(config.width, config.height);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    config.canvasContainer.appendChild(this.renderer.domElement);

    // Raycasting for click detection
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    // Lighting
    this.setupLighting();

    // Handle window resize
    window.addEventListener('resize', () => this.onWindowResize());
  }

  private setupLighting() {
    // Ambient light
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambientLight);

    // Directional light (key light)
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(5, 8, 5);
    dirLight.castShadow = true;
    this.scene.add(dirLight);

    // Fill light
    const fillLight = new THREE.DirectionalLight(0x4488ff, 0.3);
    fillLight.position.set(-5, 2, -5);
    this.scene.add(fillLight);
  }

  // Load a glTF model from URL and position it
  async loadModel(
    url: string,
    slotType: string,
    position: THREE.Vector3,
    scale: number = 1
  ): Promise<THREE.Group> {
    try {
      let modelGroup: THREE.Group;

      if (url && url.trim().length > 0) {
        // Try to load real model from URL
        if (modelCache.has(url)) {
          // Use cached model (clone it)
          const cached = modelCache.get(url)!;
          modelGroup = cached.clone();
        } else {
          // Check localStorage cache first
          const cachedGltf = storageManager.getFromStorage(url);
          if (cachedGltf && cachedGltf.scene) {
            modelGroup = (cachedGltf.scene as THREE.Group).clone();
            // Also cache in memory for this session
            modelCache.set(url, modelGroup.clone());
          } else {
            // Load from URL
            try {
              const gltf = await new Promise<any>((resolve, reject) => {
                gltfLoader.load(url, resolve, undefined, reject);
              });

              modelGroup = gltf.scene as THREE.Group;

              // Ensure all meshes cast/receive shadows
              modelGroup.traverse((child) => {
                if (child instanceof THREE.Mesh) {
                  child.castShadow = true;
                  child.receiveShadow = true;
                }
              });

              // Cache for future use (both in memory and localStorage)
              modelCache.set(url, modelGroup.clone());
              await storageManager.saveToStorage(url, gltf);
            } catch (error) {
              console.warn(`Failed to load model from ${url}, using placeholder`, error);
              // Fall back to placeholder
              modelGroup = this.createPlaceholder(slotType, scale);
            }
          }
        }
      } else {
        // No URL provided, use placeholder
        modelGroup = this.createPlaceholder(slotType, scale);
      }

      modelGroup.position.copy(position);
      modelGroup.scale.set(scale, scale, scale);
      modelGroup.userData.slotType = slotType;
      modelGroup.userData.url = url;

      this.scene.add(modelGroup);
      this.models.set(slotType, { mesh: modelGroup, slotType });

      return modelGroup;
    } catch (error) {
      console.error(`Error loading model for ${slotType}:`, error);
      // Fallback to placeholder
      const placeholder = this.createPlaceholder(slotType, scale);
      placeholder.position.copy(position);
      placeholder.userData.slotType = slotType;
      this.scene.add(placeholder);
      this.models.set(slotType, { mesh: placeholder, slotType });
      return placeholder;
    }
  }

  private createPlaceholder(slotType: string, scale: number): THREE.Group {
    const group = new THREE.Group();

    // Create simple geometric placeholders for each component
    let geometry: THREE.BufferGeometry;
    let color: number;

    switch (slotType) {
      case 'gpu':
        geometry = new THREE.BoxGeometry(2, 1.2, 0.8, 16, 16, 16);
        color = 0x22c55e; // accent green
        break;
      case 'cpu':
        geometry = new THREE.BoxGeometry(1, 0.8, 1, 8, 8, 8);
        color = 0xfbbf24; // mid-range yellow
        break;
      case 'ram':
        geometry = new THREE.BoxGeometry(0.5, 1.5, 0.2, 4, 16, 2);
        color = 0x60a5fa; // budget blue
        break;
      case 'storage':
        geometry = new THREE.BoxGeometry(1.5, 0.3, 1, 4, 2, 4);
        color = 0x818cf8; // indigo
        break;
      case 'cooling':
        geometry = new THREE.CylinderGeometry(0.6, 0.6, 1.2, 32);
        color = 0xef4444; // danger red
        break;
      default:
        geometry = new THREE.BoxGeometry(1, 1, 1);
        color = 0x71717a; // muted gray
    }

    const material = new THREE.MeshStandardMaterial({
      color,
      metalness: 0.3,
      roughness: 0.7,
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.slotType = slotType;

    group.add(mesh);
    return group;
  }

  // Update model position/scale
  updateComponentPosition(slotType: string, position: THREE.Vector3) {
    const ref = this.models.get(slotType);
    if (ref) {
      ref.mesh.position.copy(position);
    }
  }

  // Remove a component from scene
  removeComponent(slotType: string) {
    const ref = this.models.get(slotType);
    if (ref) {
      this.scene.remove(ref.mesh);
      this.models.delete(slotType);
    }
  }

  // Update a component with a new model
  async updateComponent(
    slotType: string,
    newUrl: string,
    scale: number = 1
  ): Promise<boolean> {
    try {
      // Remove old component
      const oldRef = this.models.get(slotType);
      if (oldRef) {
        const position = oldRef.mesh.position.clone();
        this.scene.remove(oldRef.mesh);

        // Load new model at same position
        await this.loadModel(newUrl, slotType, position, scale);
        return true;
      }
      return false;
    } catch (error) {
      console.error(`Failed to update component ${slotType}:`, error);
      return false;
    }
  }

  // Preload models to cache them
  async preloadModels(urls: string[]): Promise<void> {
    const promises = urls.map((url) => {
      if (!modelCache.has(url)) {
        return new Promise<void>((resolve) => {
          gltfLoader.load(
            url,
            (gltf) => {
              const cloned = (gltf.scene as THREE.Group).clone();
              modelCache.set(url, cloned);
              resolve();
            },
            undefined,
            (error) => {
              console.warn(`Failed to preload model ${url}`, error);
              resolve(); // Don't fail entire preload
            }
          );
        });
      }
      return Promise.resolve();
    });

    await Promise.all(promises);
  }

  // Get component at mouse position for hover detection
  getComponentAtMousePosition(event: MouseEvent, canvas: HTMLCanvasElement): string | null {
    const rect = canvas.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);

    const allMeshes = Array.from(this.models.values()).map(ref => {
      const meshes: THREE.Object3D[] = [];
      ref.mesh.traverse((child: THREE.Object3D) => {
        if (child instanceof THREE.Mesh) meshes.push(child);
      });
      return meshes;
    }).flat();

    const intersects = this.raycaster.intersectObjects(allMeshes);

    if (intersects.length > 0) {
      const hovered = intersects[0].object;
      let obj: THREE.Object3D | null = hovered;
      while (obj) {
        if (obj.userData?.slotType && obj.userData.slotType !== 'case') {
          return obj.userData.slotType;
        }
        obj = obj.parent;
      }
    }

    return null;
  }

  // Get clicked component (raycasting)
  getClickedComponent(event: MouseEvent, canvas: HTMLCanvasElement): string | null {
    const rect = canvas.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);

    const allMeshes = Array.from(this.models.values()).map(ref => {
      // Get all children meshes from the group
      const meshes: THREE.Object3D[] = [];
      ref.mesh.traverse((child: THREE.Object3D) => {
        if (child instanceof THREE.Mesh) meshes.push(child);
      });
      return meshes;
    }).flat();

    const intersects = this.raycaster.intersectObjects(allMeshes);

    if (intersects.length > 0) {
      const clickedMesh = intersects[0].object;
      // Traverse up to find the group with userData.slotType
      let obj: THREE.Object3D | null = clickedMesh;
      while (obj) {
        if (obj.userData?.slotType) {
          return obj.userData.slotType;
        }
        obj = obj.parent;
      }
    }

    return null;
  }

  // Render the scene
  render() {
    this.renderer.render(this.scene, this.camera);
  }

  // Cleanup
  dispose() {
    this.stopAutoRotation();
    this.renderer.dispose();
    this.scene.clear();
    this.renderer.domElement.remove();
  }

  // Start auto-rotation animation loop
  startAutoRotation() {
    if (this.animationFrameId) return;

    const animate = () => {
      const now = Date.now();
      const timeSinceInteraction = now - this.lastInteractionTime;

      // Only rotate if idle for more than interactionIdleTime
      if (timeSinceInteraction > this.interactionIdleTime && this.autoRotationEnabled) {
        this.models.forEach(ref => {
          ref.mesh.rotation.y += this.autoRotationSpeed;
        });
      }

      this.animationFrameId = requestAnimationFrame(animate);
    };

    animate();
  }

  // Stop auto-rotation animation loop
  stopAutoRotation() {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  // Record user interaction to pause auto-rotation
  recordInteraction() {
    this.lastInteractionTime = Date.now();
  }

  // Start drag interaction
  startDrag(event: MouseEvent | TouchEvent) {
    this.isDragging = true;
    this.recordInteraction();

    const clientX = event instanceof TouchEvent ? event.touches[0].clientX : event.clientX;
    const clientY = event instanceof TouchEvent ? event.touches[0].clientY : event.clientY;

    this.previousMousePosition = { x: clientX, y: clientY };
  }

  // Handle drag movement
  moveDrag(event: MouseEvent | TouchEvent) {
    if (!this.isDragging) return;

    const clientX = event instanceof TouchEvent ? event.touches[0].clientX : event.clientX;
    const clientY = event instanceof TouchEvent ? event.touches[0].clientY : event.clientY;

    const deltaX = clientX - this.previousMousePosition.x;
    const deltaY = clientY - this.previousMousePosition.y;

    this.rotation.y += deltaX * this.dragSensitivity;
    this.rotation.x += deltaY * this.dragSensitivity;

    // Clamp X rotation to prevent flip
    this.rotation.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, this.rotation.x));

    // Apply rotation to all models
    this.models.forEach(ref => {
      ref.mesh.rotation.order = 'YXZ';
      ref.mesh.rotation.y = this.rotation.y;
      ref.mesh.rotation.x = this.rotation.x;
    });

    this.previousMousePosition = { x: clientX, y: clientY };
  }

  // End drag interaction
  endDrag() {
    this.isDragging = false;
  }

  // Reset rotation to default
  resetRotation() {
    this.rotation = { x: 0, y: 0 };
    this.models.forEach(ref => {
      ref.mesh.rotation.set(0, 0, 0);
    });
  }

  // Play victory spin animation when build is finalized
  async playVictorySpin(duration: number = 3000) {
    const startTime = Date.now();
    const startRotations = new Map<string, { x: number; y: number; z: number }>();

    // Store initial rotations
    this.models.forEach((ref, slotType) => {
      startRotations.set(slotType, {
        x: ref.mesh.rotation.x,
        y: ref.mesh.rotation.y,
        z: ref.mesh.rotation.z,
      });
    });

    return new Promise<void>((resolve) => {
      const animate = () => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Spin multiple rotations
        const spins = 2;
        const totalRotation = (spins * Math.PI * 2 * progress);

        this.models.forEach((ref) => {
          const initial = startRotations.get(ref.slotType) || { x: 0, y: 0, z: 0 };
          ref.mesh.rotation.y = initial.y + totalRotation;
          // Bob up and down during spin
          ref.mesh.rotation.x = initial.x + Math.sin(progress * Math.PI) * 0.3;
        });

        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          resolve();
        }
      };

      animate();
    });
  }

  // Set the speed of auto-rotation
  setAutoRotationSpeed(speed: number) {
    this.autoRotationSpeed = speed;
  }

  // Get a group containing all models (for potential grouping operations)
  getModelsCenterGroup(): THREE.Group | null {
    if (this.models.size === 0) return null;
    const group = new THREE.Group();
    this.models.forEach(ref => {
      group.add(ref.mesh);
    });
    return group;
  }

  private onWindowResize() {
    // Handle window resize (will be called from component)
  }

  setSize(width: number, height: number) {
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }
}

export function initScene(container: HTMLDivElement): PCBuilderScene {
  const width = container.clientWidth;
  const height = container.clientHeight;
  return new PCBuilderScene({ canvasContainer: container, width, height });
}

// Helper to get model URL for a component variant
export function getModelUrl(slotType: string, variantId?: number): string {
  // Phase 2: Will be populated with actual Sketchfab URLs
  // Format: public/models/{slotType}/{variantId}.gltf
  if (!variantId) return '';

  // Return URL relative to public folder
  // This will be updated once we have real models
  const typeMap: Record<string, string> = {
    gpu: 'gpu',
    cpu: 'cpu',
    ram: 'ram',
    storage: 'storage',
    cooling: 'cooling',
  };

  const folder = typeMap[slotType] || slotType;
  return `/models/${folder}/${variantId}.gltf`;
}
