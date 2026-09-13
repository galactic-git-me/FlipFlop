from pathlib import Path
base = Path(__file__).resolve().parents[2] / 'tmp/build-studio'
p = base / 'lib/studio.ts'
s = p.read_text(encoding='utf-8').replace("psu: 'Power supply', os:", "psu: 'Power supply', fan: 'Case fans', os:").replace("'cooling', 'psu', 'os'", "'cooling', 'psu', 'fan', 'os'")
p.write_text(s, encoding='utf-8')
p = base / 'components/studio/Studio.tsx'
s = p.read_text(encoding='utf-8').replace("addCartItem({kind:'configured',", "addCartItem({kind:'configured',validationMode:'studio',")
s = s.replace("setPlaybook(data.some(p => p.id===requested) ? requested : data[0]?.id ?? 0);", "setPlaybook(current => data.some(p => p.id===current) ? current : data.some(p => p.id===requested) ? requested : data[0]?.id ?? 0);")
s = s.replace("`${failures.length} issues to resolve`", "`${failures.length} ${failures.length===1?'issue':'issues'} to resolve`")
s = s.replace("{!loading && !error && sceneParts.length>0 ?", "{!error && sceneParts.length>0 ?")
p.write_text(s, encoding='utf-8')
p = base / 'app/studio/page.tsx'
s = p.read_text(encoding='utf-8').replace("title: 'Build Studio | FlipFlop'", "title: 'Build Studio'")
p.write_text(s, encoding='utf-8')
p = base / 'components/studio/studio.css'
s = p.read_text(encoding='utf-8')
if '.ff-studio h1,.ff-studio h2' not in s:
    s += '\n.ff-studio h1,.ff-studio h2,.ff-studio h3,.ff-studio h4{font-family:var(--font-body),Arial,sans-serif;text-transform:none}.studio-stage-title h2{font-family:var(--font-body),Arial,sans-serif}\n@media(min-width:801px) and (max-height:950px){.studio-stage,.studio-builder{height:680px;min-height:680px}.studio-layout{min-height:680px}}\n'
p.write_text(s, encoding='utf-8')
