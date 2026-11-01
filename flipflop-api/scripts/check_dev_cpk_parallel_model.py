"""Explicitly authorized DEV model canary: four fixtures, no database writes."""
import asyncio
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.environment import load_application_environment
load_application_environment(Path(__file__).resolve().parents[1])
from app.config import get_settings
from app.gem_radar import cpk_extractor as extractor
from app.gem_radar.product_identifiers import identity_conflicts

CASES = [
    ('AMD Ryzen 5 5600 6-Core 12-Thread AM4 Desktop Processor','cpu','amd','5600'),
    ('Intel Core i5-12400F 6-Core LGA1700 Desktop Processor','cpu','intel','12400f'),
    ('Corsair Vengeance LPX 32GB (2x16GB) DDR4 3200MHz CL16 RAM Kit','ram','corsair','vengeance'),
    ('Samsung 970 EVO Plus 1TB M.2 NVMe SSD','ssd','samsung','970'),
]

async def main():
    settings = get_settings()
    assert settings.app_env == 'dev'
    service = extractor._extraction_service(settings.model_copy(update={'dev_cpk_ollama_model':'qwen3:4b'}))
    extractor._extraction_service = lambda: service
    async def run(case):
        title,category,brand,token=case
        started=time.monotonic()
        try:
            result=await extractor._extract_cpk_uncached(title,category,'new',local_only=True,timeout=180,raise_on_provider_error=True)
            data=result.to_dict() if result else None
            passed=bool(result and result.category==category and result.brand==brand and token in result.model and not identity_conflicts(title,data))
            return {'title':title,'seconds':round(time.monotonic()-started,2),'passed':passed,'result':data}
        except Exception as exc:
            return {'title':title,'seconds':round(time.monotonic()-started,2),'passed':False,'error':str(exc)}
    started=time.monotonic()
    results=await asyncio.gather(*(run(c) for c in CASES))
    report={'model':'qwen3:4b','elapsed_seconds':round(time.monotonic()-started,2),'passed':sum(r['passed'] for r in results),'total':len(results),'results':results}
    out=Path(__file__).resolve().parents[2]/'output/sourcing/qwen3-parallel-canary.json'
    out.parent.mkdir(exist_ok=True,parents=True)
    out.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))
    if report['passed']!=report['total']:sys.exit(1)

if __name__=='__main__':asyncio.run(main())
