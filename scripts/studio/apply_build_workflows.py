"""Apply the three storefront workflows, preserving unrelated storefront edits."""
from pathlib import Path
import shutil
root = Path(__file__).resolve().parents[2]
shop = root.parent / 'FlipFlop.shop'
stage = root / 'tmp/build-studio'

def edit(path, replacements):
    target = shop / path
    text = target.read_text(encoding='utf-8')
    for old,new in replacements:
        text = text.replace(old,new)
    target.write_text(text,encoding='utf-8')

for relative in ('components/curated/CuratedBuild.tsx','components/curated/CuratedCollection.tsx','app/curated/[id]/page.tsx'):
    target=shop/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(stage/relative,target)

(shop/'app/products/page.tsx').write_text('''import CuratedCollection from '@/components/curated/CuratedCollection';
export const metadata = { title: 'Curated PC Builds', description: '24 curated builds for eight user types. Choose RAM capacity, SSD type and capacity, and your case.' };
export default function Page() { return <CuratedCollection />; }
''',encoding='utf-8')
edit('app/start/page.tsx',[
    ('title: "Ready-to-Ship"','title: "Pre-builts"'),
    ('Buy a machine we\'ve already built, tested, and benchmarked. Ships fast.','A specific machine we have built and tested. Buy its fixed specification, exactly as shown.'),
    ('Browse ready-to-ship','Browse pre-builts'),
    ('its memory, storage and case.','RAM capacity, SATA or NVMe SSD and capacity, and any available case.'),
    ('const PATHS = [','const PATHS = [\n  { n: "03", href: "/studio", title: "Custom Builds", body: "Choose every component from the same component catalogue used for our curated builds. Explore your configuration in the full 3D studio.", cta: "Create a custom build" },'),
    ('Curated for you, or ready right now. Same build quality.','Curated for your needs, customised by you, or already built.'),
    ('sm:grid-cols-2 gap-5 max-w-2xl','lg:grid-cols-3 gap-5 max-w-5xl'),
])
edit('app/layout.tsx',[('data-text="3D Studio"','data-text="Custom Builds"'),('                3D Studio','                Custom Builds'),('Ready-to-ship','Pre-builts')])
edit('app/ready-to-ship/page.tsx',[('Ready-to-Ship','Pre-builts'),('Buy now, ships fast.','Each is a real machine with a fixed specification. No component changes.'),('href="/start"','href="/studio"')])
prebuilt=shop/'app/ready-to-ship/[id]/page.tsx'
text=prebuilt.read_text(encoding='utf-8').replace('import { RgbControls } from "@/components/three/RgbControls";','').replace('← Ready-to-Ship','← Pre-builts')
start=text.find('          {product.twin_3d?.optimized_asset_ref && (')
if start>=0:
    end=text.index('          )}',start)+len('          )}')
    text=text[:start]+text[end:]
text=text.replace('<h1 className="text-3xl', '<p className="mb-3 text-sm text-secondary">Pre-built · Fixed specification</p>\n          <h1 className="text-3xl')
prebuilt.write_text(text,encoding='utf-8')
edit('lib/pending-checkout.ts',[("validationMode?: 'studio';","validationMode?: 'studio' | 'curated';\n  curatedBuildId?: string;")])
edit('app/order/payment/page.tsx',[('validation_mode: checkout.validationMode,','validation_mode: checkout.validationMode,\n            curated_build_id: checkout.curatedBuildId,')])
edit('app/cart/page.tsx',[('validationMode: item.validationMode,','validationMode: item.validationMode,\n      curatedBuildId: item.curatedBuildId,')])
edit('lib/cart.ts',[('JSON.stringify({ playbookId: item.playbookId,','JSON.stringify({ validationMode: item.validationMode, curatedBuildId: item.curatedBuildId, playbookId: item.playbookId,')])
edit('lib/api.ts',[('`/api/public/playbooks/${playbookId}/slots`','`/api/public/playbooks/${playbookId}/curated-slots`')])
edit('app/configure/[slug]/page.tsx',[('RAM, SSD capacity and operating system','RAM capacity, SSD type and capacity, and case')])
# Legacy purpose pages now return customers to the complete, named collection.
(shop/'app/configure/[slug]/page.tsx').write_text("import { redirect } from 'next/navigation';\nexport default function Page() { redirect('/products'); }\n",encoding='utf-8')
edit('components/studio/Studio.tsx',[("'playbooks/'+playbook+'/slots'","'playbooks/'+playbook+'/custom-slots'"),('CURATED COLLECTION','BUILD OPTIONS'),('href="/products" className="studio-back"','href="/start" className="studio-back"'),('<h1>Build Studio','<h1>Custom Build Studio')])
# Keep the staged source consistent with the installed custom studio.
shutil.copy2(shop/'components/studio/Studio.tsx',stage/'components/studio/Studio.tsx')
print('Installed curated collection, simple viewer, custom studio, and fixed pre-built presentation.')
