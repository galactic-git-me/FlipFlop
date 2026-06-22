// pc-flipper-customer/lib/model-helpers.ts
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

// Model caching to prevent duplicate downloads
const modelCache = new Map<string, THREE.Group>();
const gltfLoader = new GLTFLoader();

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

            // Cache for future use
            modelCache.set(url, modelGroup.clone());
          } catch (error) {
            console.warn(`Failed to load model from ${url}, using placeholder`, error);
            // Fall back to placeholder
            modelGroup = this.createPlaceholder(slotType, scale);
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

  // Animation loop (auto-rotate when idle)
  autoRotate(enabled: boolean = true) {
    if (enabled) {
      const animate = () => {
        this.models.forEach(ref => {
          ref.mesh.rotation.y += 0.005;
        });
        this.render();
        requestAnimationFrame(animate);
      };
      animate();
    }
  }

  // Cleanup
  dispose() {
    this.renderer.dispose();
    this.scene.clear();
    this.renderer.domElement.remove();
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
