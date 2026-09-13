"""Install only the prepared Studio integration into the sibling storefront."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[2]
shop = root.parent / 'FlipFlop.shop'
stage = root / 'tmp/build-studio'
assert (shop / 'package.json').is_file()
for source in stage.rglob('*'):
    if source.is_file():
        target = shop / source.relative_to(stage)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

config = shop / 'next.config.ts'
text = config.read_text(encoding='utf-8')
if 'studio-assets' not in text:
    text = text.replace('    return [\n      {\n        source: "/api/auth/', '    return [\n      { source: "/studio-assets/:path*", destination: `${backendUrl}/media/:path*` },\n      {\n        source: "/api/auth/')
if 'STUDIO_PREVIEW' not in text:
    text = text.replace('const nextConfig: NextConfig = {', 'const nextConfig: NextConfig = {\n  distDir: process.env.STUDIO_PREVIEW === "1" ? ".next-studio" : ".next",')
config.write_text(text, encoding='utf-8')

layout = shop / 'app/layout.tsx'
text = layout.read_text(encoding='utf-8')
if 'href="/studio"' not in text:
    start = text.index('              <a\n                href="https://theflipflop.shop"')
    end = text.index('              </a>', start) + len('              </a>')
    text = text[:start] + '''              <Link href="/studio" className="nav-link hidden sm:inline" data-text="3D Studio" style={{ color: "var(--color-accent, #ff7426)" }}>
                3D Studio
              </Link>''' + text[end:]
layout.write_text(text, encoding='utf-8')

curated = shop / 'app/configure/[slug]/ConfiguratorClient.tsx'
text = curated.read_text(encoding='utf-8')
if '/studio?' not in text:
    text = text.replace('import { useSearchParams }', 'import Link from "next/link";\nimport { useSearchParams }')
    marker = '        <CuratedMachinePreview'
    text = text.replace(marker, '''        <Link
          href={`/studio?playbook=${playbook.id}&case=${build.case?.id ?? ""}&parts=${encodeURIComponent(JSON.stringify(Object.fromEntries(slots.flatMap(slot => { const variant = build.slots[slot.slot_type]; return variant ? [[slot.slot_id, variant.id]] : []; }))))}`}
          className="flex items-center justify-between rounded-xl border p-5"
          style={{ borderColor: "#ff742650", background: "linear-gradient(120deg,#172338,#211c1b)", color: "#f5e5da" }}
        ><span><strong className="block text-lg">Step inside Build Studio</strong><span className="text-xs opacity-70">Explore this configuration in interactive 3D</span></span><span aria-hidden="true">↗</span></Link>
''' + marker)
curated.write_text(text, encoding='utf-8')
ignore = shop / '.gitignore'
text = ignore.read_text(encoding='utf-8')
if '.next-studio/' not in text:
    ignore.write_text(text + '\n# Isolated Build Studio preview\n.next-studio/\n', encoding='utf-8')
print('Installed Build Studio, storefront navigation and curated-build handoff.')

pending = shop / 'lib/pending-checkout.ts'
text = pending.read_text(encoding='utf-8')
if 'validationMode' not in text:
    text = text.replace('  playbookId: number;', "  validationMode?: 'studio';\n  playbookId: number;")
pending.write_text(text, encoding='utf-8')
payment = shop / 'app/order/payment/page.tsx'
text = payment.read_text(encoding='utf-8')
if 'validation_mode:' not in text:
    text = text.replace('chosen_week: checkout.chosenWeek,', 'chosen_week: checkout.chosenWeek,\n            validation_mode: checkout.validationMode,')
payment.write_text(text, encoding='utf-8')
cart = shop / 'app/cart/page.tsx'
text = cart.read_text(encoding='utf-8')
if 'validationMode:' not in text:
    text = text.replace('      playbookId: item.playbookId,', '      validationMode: item.validationMode,\n      playbookId: item.playbookId,')
cart.write_text(text, encoding='utf-8')
