'use client';

import { Component, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, useGLTF, Html, Environment, Lightformer } from '@react-three/drei';
import * as THREE from 'three';
import type { OrbitControls as Controls } from 'three-stdlib';
import { assetURL, labels } from '@/lib/studio';
import type { ResolvedAsset } from '@/lib/asset-api';

export interface ScenePart { category: string; id: number; title: string; asset?: ResolvedAsset | null }
interface Props { parts: ScenePart[]; active: string; onSelect: (category: string) => void; mode: 'assembled' | 'exploded' | 'xray'; open: boolean; accent: string; rotating: boolean; resetKey: number; reducedMotion: boolean }
type V3 = [number, number, number];
const previewBounds: Record<string, V3> = { case: [.422,.46,.24], motherboard: [.244,.305,.04], cpu: [.043,.043,.008], cooling: [.12,.12,.15], gpu: [.29,.06,.12], ram: [.035,.135,.035], storage: [.08,.022,.006], psu: [.15,.086,.14], fan: [.012,.33,.105] };
const positions: Record<string, V3> = { case: [0,0,0], motherboard: [-.045,.038,-.104], cpu: [-.07,.103,-.087], cooling: [-.07,.103,-.072], gpu: [-.025,-.048,.008], ram: [.035,.098,-.077], storage: [-.065,-.025,-.091], psu: [-.095,-.184,0], fan:[.194,.04,0] };
const explosions: Record<string, V3> = { case: [0,0,0], motherboard: [-.16,.06,-.13], cpu: [-.12,.25,.14], cooling: [-.1,.2,.39], gpu: [0,-.035,.35], ram: [.2,.13,.22], storage: [.2,-.06,.2], psu: [-.16,-.15,.2], fan:[.22,0,.08] };
const anchors: Record<string,string> = { motherboard:'motherboard_mount',cpu:'cpu_socket',cooling:'cpu_socket',gpu:'gpu_slot_1',ram:'ram_slot_1',storage:'storage_bay_1',psu:'psu_bay' };

class ModelBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

function Model({ url, active, hovered, xray, accent, fit }: { url: string; active: boolean; hovered: boolean; xray: boolean; accent: string; fit?: V3 }) {
  const gltf = useGLTF(url);
  const scene = useMemo(() => {
    const copy = gltf.scene.clone(true);
    copy.traverse(o => { if (o instanceof THREE.Mesh) { o.castShadow = true; o.receiveShadow = true; o.material = Array.isArray(o.material) ? o.material.map(m => m.clone()) : o.material.clone(); } });
    // Generated photography assets have arbitrary units. Fit them for visual
    // preview only; this does not confer validated physical dimensions.
    if (fit) {
      const bounds = new THREE.Box3().setFromObject(copy);
      const size = bounds.getSize(new THREE.Vector3());
      const factor = Math.min(...fit.map((v, i) => v / Math.max(size.getComponent(i), .000001)));
      copy.position.sub(bounds.getCenter(new THREE.Vector3()));
      copy.scale.multiplyScalar(factor);
      copy.position.multiplyScalar(factor);
    }
    copy.traverse(o => { if (o instanceof THREE.Mesh) for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
      if (m instanceof THREE.MeshStandardMaterial) {
      m.userData.studioOriginal = {
        emissive: m.emissive.clone(), intensity: m.emissiveIntensity,
        transparent: m.transparent, opacity: m.opacity, depthWrite: m.depthWrite,
        illuminated: !!m.emissiveMap || (m.emissiveIntensity > 0 && m.emissive.getHex() !== 0) || /(?:rgb|argb|led|emission|light.?ring)/i.test(m.name + ' ' + o.name),
      };
      if (m.emissiveMap) {
        // Preserve the LED mask, removing baked rainbow hues that would
        // otherwise multiply against (and muddy) the selected light colour.
        m.onBeforeCompile = shader => {
          shader.fragmentShader = shader.fragmentShader.replace('#include <emissivemap_fragment>',
            THREE.ShaderChunk.emissivemap_fragment.replace('totalEmissiveRadiance *= emissiveColor.rgb;',
              'totalEmissiveRadiance *= max(max(emissiveColor.r, emissiveColor.g), emissiveColor.b);'));
        };
        m.customProgramCacheKey = () => 'studio-led-mask-v1';
      }
      }
    } });
    return copy;
  }, [gltf, fit]);
  useEffect(() => {
    scene.traverse(o => { if (o instanceof THREE.Mesh) for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
      if (m instanceof THREE.MeshStandardMaterial) {
        const original = m.userData.studioOriginal;
        // Keep emission maps as masks so only actual LEDs change colour.
        m.emissive.copy(original.emissive);
        m.emissiveIntensity = original.intensity;
        if (original.illuminated) { m.emissive.set(accent); m.emissiveIntensity = Math.max(original.intensity, 2); }
        else if (active || hovered) { m.emissive.set(accent); m.emissiveIntensity = hovered ? .12 : .04; }
        m.transparent = xray || original.transparent; m.opacity = xray ? .16 : original.opacity; m.depthWrite = xray ? false : original.depthWrite; m.needsUpdate = true;
      }
    } });
  }, [scene, active, hovered, xray, accent]);
  useEffect(() => () => { scene.traverse(o => { if (o instanceof THREE.Mesh) for (const m of Array.isArray(o.material) ? o.material : [o.material]) m.dispose(); }); }, [scene]);
  return <primitive object={scene} />;
}

function Fan({ position, rotation = [0,0,0], accent }: { position: V3; rotation?: V3; accent: string }) {
  return <group position={position} rotation={rotation}>
    <mesh><cylinderGeometry args={[.049,.049,.012,24]} /><meshStandardMaterial color="#151c26" metalness={.6} roughness={.3} /></mesh>
    <mesh rotation={[Math.PI/2,0,0]} position={[0,.007,0]}><torusGeometry args={[.043,.0024,6,32]} /><meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={2.5} /></mesh>
    {Array.from({ length: 7 }, (_,i) => <mesh key={i} rotation={[0,i*Math.PI*2/7,0]} position={[0,.008,0]}><boxGeometry args={[.007,.003,.075]} /><meshStandardMaterial color="#313b4c" metalness={.7} roughness={.3} /></mesh>)}
    <mesh position={[0,.01,0]}><cylinderGeometry args={[.013,.013,.005,16]} /><meshStandardMaterial color="#adb9c9" metalness={.9} roughness={.2} /></mesh>
    <pointLight position={[0,.025,0]} color={accent} intensity={.025} distance={.22} decay={2} />
  </group>;
}

function Part({ part, props, chassis, onHover }: { part: ScenePart; props: Props; chassis?: ScenePart; onHover: (text: string) => void }) {
  const ref = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  const anchor = chassis?.asset?.anchor_manifest?.anchors[anchors[part.category]];
  const trustedCase = chassis?.asset?.scale_validated && chassis.asset.anchor_manifest;
  const base = trustedCase && anchor ? anchor.position : positions[part.category];
  const offset = props.mode === 'exploded' ? explosions[part.category] : [0,0,0];
  const target = new THREE.Vector3(base[0]+offset[0],base[1]+offset[1],base[2]+offset[2]);
  useFrame((_,dt) => { ref.current?.position.lerp(target, props.reducedMotion ? 1 : 1-Math.exp(-dt*8)); });
  const fallback = '/models/studio/' + part.category + '.glb';
  const exact = part.asset?.scale_validated && part.asset.fallback_level === 'exact' && (part.category !== 'case' || trustedCase);
  const url = assetURL(part.asset?.glb_ref) || fallback;
  const modelProps = { active: props.active === part.category && part.category !== 'case', hovered, xray: props.mode === 'xray' && part.category === 'case', accent: props.accent };
  return <group ref={ref} position={base} rotation={trustedCase && anchor?.rotation ? anchor.rotation : [0,0,0]} scale={trustedCase && anchor?.scale ? anchor.scale : 1}
    onClick={e => { e.stopPropagation(); props.onSelect(part.category); }}
    onPointerOver={e => { e.stopPropagation(); setHovered(true); onHover(part.title); }}
    onPointerOut={() => { setHovered(false); onHover(''); }}>
    <Suspense fallback={<mesh><boxGeometry args={[.08,.08,.08]} /><meshStandardMaterial wireframe color={props.accent} /></mesh>}>
      <ModelBoundary key={url} fallback={<Model url={fallback} {...modelProps} />}><Model url={url} {...modelProps} fit={url !== fallback && !exact ? previewBounds[part.category] : undefined} /></ModelBoundary>
    </Suspense>
    {url === fallback && part.category === 'gpu' && [-.092,0,.092].map(x => <Fan key={x} position={[x,-.035,0]} rotation={[Math.PI,0,0]} accent={props.accent} />)}
    {url === fallback && part.category === 'cooling' && <Fan position={[0,0,.124]} rotation={[Math.PI/2,0,0]} accent={props.accent} />}
    {url === fallback && part.category === 'ram' && [-.009,.009].map(x => <mesh key={x} position={[x,0,.018]}><boxGeometry args={[.006,.126,.004]} /><meshStandardMaterial color={props.accent} emissive={props.accent} emissiveIntensity={3} /></mesh>)}
    {part.category === 'fan' && url === fallback && [-.112,0,.112].map(y => <Fan key={y} position={[0,y,0]} rotation={[0,0,-Math.PI/2]} accent={props.accent} />)}
    {part.category === 'case' && url === fallback && <>
      <SidePanel open={props.open || props.mode === 'exploded'} xray={props.mode === 'xray'} reduced={props.reducedMotion} />
    </>}
    {props.mode === 'exploded' && part.category !== 'case' && <Html center position={[0,.055,.05]} distanceFactor={1.5} style={{ pointerEvents: 'none' }}><span className="studio-annotation">{labels[part.category]}</span></Html>}
  </group>;
}

function SidePanel({ open, xray, reduced }: { open: boolean; xray: boolean; reduced: boolean }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((_,dt) => { if (ref.current) ref.current.position.z = THREE.MathUtils.damp(ref.current.position.z, open ? .4 : .122, reduced ? 1000 : 7, dt); });
  return <mesh ref={ref} position={[0,0,.122]} visible={!xray}><boxGeometry args={[.41,.44,.003]} /><meshPhysicalMaterial color="#b2c6dc" transparent opacity={open ? .09 : .12} roughness={.12} metalness={.25} depthWrite={false} side={THREE.DoubleSide} /></mesh>;
}

function Camera({ props, interaction }: { props: Props; interaction: React.MutableRefObject<number> }) {
  const controls = useRef<Controls>(null);
  const { camera, invalidate } = useThree();
  const focus = useRef<{ target: THREE.Vector3; position: THREE.Vector3 } | null>(null);
  useEffect(() => {
    const p = positions[props.active] || [0,0,0];
    const e = props.mode === 'exploded' ? explosions[props.active] || [0,0,0] : [0,0,0];
    const target = new THREE.Vector3(p[0]+e[0],p[1]+e[1],p[2]+e[2]);
    const dist = props.active === 'case' ? 1.12 : .7;
    focus.current = { target, position: target.clone().add(new THREE.Vector3(.65,.35,1).normalize().multiplyScalar(dist)) };
    interaction.current = performance.now(); invalidate();
  }, [props.active,props.mode,props.resetKey,interaction,invalidate]);
  useFrame((_,dt) => {
    if (!controls.current) return;
    const f = focus.current;
    if (f) { const t=props.reducedMotion ? 1 : 1-Math.exp(-dt*5); camera.position.lerp(f.position,t); controls.current.target.lerp(f.target,t); if (camera.position.distanceTo(f.position)<.002) focus.current=null; }
    controls.current.autoRotate = props.rotating && !props.reducedMotion && !f && performance.now()-interaction.current>3500;
    controls.current.autoRotateSpeed = THREE.MathUtils.damp(controls.current.autoRotateSpeed, controls.current.autoRotate ? .35 : 0, 2, dt);
    controls.current.update();
  });
  return <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={.08} minDistance={.25} maxDistance={2.3} maxPolarAngle={Math.PI*.85} autoRotateSpeed={0}
    onStart={() => { focus.current=null; interaction.current=Infinity; }} onEnd={() => { interaction.current=performance.now(); }} />;
}

export default function StudioScene(props: Props) {
  const [hover, setHover] = useState('');
  const [lost, setLost] = useState(false);
  const interaction = useRef(0);
  const chassis = props.parts.find(p => p.category === 'case');
  return <div className="studio-canvas" style={{ cursor: hover ? 'pointer' : 'grab' }} aria-label="Interactive PC. Drag to orbit, scroll or pinch to zoom. Use the component list for keyboard selection.">
    {lost ? <div className="studio-fallback"><strong>3D preview paused</strong><p>Your build and product controls are still available.</p><button onClick={() => setLost(false)}>Reload 3D</button></div> :
      <ModelBoundary fallback={<div className="studio-fallback">3D is unavailable on this device. Explore your build using the component list.</div>}>
        <Canvas dpr={[1,1.5]} camera={{ position:[.7,.35,1], fov:38, near:.01, far:15 }} gl={{ antialias:true, alpha:true, powerPreference:'high-performance' }}
          onCreated={({ gl }) => { gl.domElement.addEventListener('webglcontextlost', e => { e.preventDefault(); setLost(true); }, { once:true }); }}>
          <ambientLight intensity={1.6} /><hemisphereLight args={['#c6dcff','#15203a',2]} />
          <Environment resolution={128} frames={1}>
            <Lightformer intensity={3} position={[0,3,1]} scale={[4,2,1]} rotation={[Math.PI/2,0,0]} />
            <Lightformer intensity={4} position={[-3,1,1]} scale={[2,4,1]} rotation={[0,Math.PI/2,0]} color="#b4d2ff" />
            <Lightformer intensity={2} position={[2,1,-2]} scale={[3,4,1]} rotation={[0,-Math.PI/3,0]} color="#ffe4ca" />
          </Environment>
          <directionalLight position={[1,2,3]} intensity={4} /><directionalLight position={[-2,1,-1]} color="#85b8ff" intensity={3} />
          <pointLight position={[.2,.1,.2]} color={props.accent} intensity={.4} distance={1} />
          <Suspense fallback={null}>{props.parts.filter(p => positions[p.category]).map(p => <Part key={p.category+':'+p.id} part={p} props={props} chassis={chassis} onHover={setHover} />)}</Suspense>
          <mesh position={[0,-.265,0]} rotation={[-Math.PI/2,0,0]}><circleGeometry args={[.42,64]} /><meshStandardMaterial color="#121c2b" metalness={.7} roughness={.5} /></mesh>
          <mesh position={[0,-.263,0]} rotation={[-Math.PI/2,0,0]}><ringGeometry args={[.419,.421,96]} /><meshBasicMaterial color={props.accent} transparent opacity={.45} /></mesh>
          <Camera props={props} interaction={interaction} />
        </Canvas>
      </ModelBoundary>}
    {hover && <div className="studio-hover">{hover}</div>}
  </div>;
}
