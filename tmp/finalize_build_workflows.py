from pathlib import Path
import shutil
shop=Path('C:/Users/mclar/CODING/FlipFlop.shop')
stage=Path('tmp/build-studio')
shutil.copy2(stage/'components/curated/CuratedBuild.tsx',shop/'components/curated/CuratedBuild.tsx')
p=shop/'components/studio/studio.css'
s=p.read_text(encoding='utf-8')
if '.curated-preview .studio-canvas' not in s:
    s+='\n.curated-preview .studio-canvas{inset:0}\n'
p.write_text(s,encoding='utf-8')
shutil.copy2(p,stage/'components/studio/studio.css')
p=shop/'components/three/ProductModelViewer.tsx'
s=p.read_text(encoding='utf-8').replace('function Model({ url }: { url: string })','function Model({ url, configurableLighting }: { url: string; configurableLighting: boolean })').replace('if (document.hidden) return;', 'if (document.hidden || !configurableLighting) return;').replace('arReady = false }: { url: string; title: string; arReady?: boolean }', 'arReady = false, configurableLighting = true }: { url: string; title: string; arReady?: boolean; configurableLighting?: boolean }').replace('<Model url={url} />','<Model url={url} configurableLighting={configurableLighting} />')
p.write_text(s,encoding='utf-8')
p=shop/'app/ready-to-ship/[id]/page.tsx'
s=p.read_text(encoding='utf-8').replace('<ProductModelViewer','<ProductModelViewer\n                configurableLighting={false}')
p.write_text(s,encoding='utf-8')
for route,destination in [('app/build/page.tsx','/studio'),('app/products/[slug]/page.tsx','/products')]:
    (shop/route).write_text("import { redirect } from 'next/navigation';\nexport default function Page() { redirect('"+destination+"'); }\n",encoding='utf-8')
p=shop/'app/start/page.tsx'
s=p.read_text(encoding='utf-8').replace('n: "03", href: "/studio"','n: "01", href: "/studio"').replace('n: "01",\n    href: "/ready-to-ship"','n: "02",\n    href: "/ready-to-ship"').replace('n: "02",\n    href: "/products"','n: "03",\n    href: "/products"')
p.write_text(s,encoding='utf-8')
print('Viewer layout, fixed prebuilt lighting and legacy routes updated.')
