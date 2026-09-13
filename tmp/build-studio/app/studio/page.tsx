import type { Metadata } from 'next';
import Studio from '@/components/studio/Studio';
export const metadata: Metadata = { title: 'Build Studio', description: 'Explore your next gaming PC in interactive 3D. Real FlipFlop components, current catalogue prices and transparent compatibility checks.' };
export default function StudioPage() { return <Studio />; }
