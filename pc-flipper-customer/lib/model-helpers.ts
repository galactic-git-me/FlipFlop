// pc-flipper-customer/lib/model-helpers.ts
import * as THREE from 'three';

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
    // For now, return a placeholder geometric shape
    // In Phase 2, we'll use GLTFLoader to load actual models
    const placeholder = this.createPlaceholder(slotType, scale);
    placeholder.position.copy(position);
    placeholder.userData.slotType = slotType;

    this.scene.add(placeholder);
    this.models.set(slotType, { mesh: placeholder, slotType });

    return placeholder;
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
