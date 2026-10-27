"""Review all displayed bestseller pairs locally; resume matching completed inputs.

Run from flipflop-api: .venv/Scripts/python scripts/review_bestseller_identities.py
No commercial review statuses, photo selections or publication flags are changed.
"""
import asyncio
from collections import Counter
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from sqlalchemy import text
from sqlalchemy.engine import make_url
from app.config import get_settings
from app.database import AsyncSessionLocal, engine
from app.api.curated_builds import bestseller_catalogue
from app.services.bestseller_identity_review import classify_batch, identity_fingerprint


async def main():
    settings = get_settings()
    database = make_url(str(engine.url))
    if database.host not in {'127.0.0.1', 'localhost'} or settings.app_env == 'production':
        raise RuntimeError('This runner is restricted to the local development database')
    base_url = settings.ollama_base_url
    model = settings.llm_primary_model
    # Never fall back to an external LLM, production gateway or direct engine.
    url = urlsplit(base_url)
    if url.hostname not in {'127.0.0.1', 'localhost', 'prometheus-ts'} or url.port != 11435:
        raise RuntimeError('Configure OLLAMA_BASE_URL to the local DEV gateway on port 11435')
    output = Path('output/bestseller-identity-review')
    output.mkdir(parents=True, exist_ok=True)
    report = output / 'decisions.jsonl'
    cached = {}
    if report.exists():
        for line in report.read_text(encoding='utf-8').splitlines():
            result = json.loads(line)
            if result.get('model') == model:
                cached[result['fingerprint']] = result
    async with AsyncSessionLocal() as db:
        rows = (await bestseller_catalogue(db))['items']
    pending = [row for row in rows if not row.get('identity_review')]
    pending.sort(key=lambda row: row['review_status'] != 'pending')
    print(json.dumps({'total': len(rows), 'remaining': len(pending), 'model': model}), flush=True)
    counts = Counter()
    queue = asyncio.Queue()
    for row in pending:
        queue.put_nowait(row)
    async with httpx.AsyncClient(timeout=240) as client:
        tags = await client.get(base_url.rstrip('/') + '/api/tags')
        tags.raise_for_status()
        if model not in {item['name'] for item in tags.json()['models']}:
            raise RuntimeError('Configured model is not installed locally')

        async def worker():
            while not queue.empty():
                row = queue.get_nowait()
                fingerprint = identity_fingerprint(row)
                result = cached.get(fingerprint)
                if result is None:
                    for attempt in range(3):
                        try:
                            result = (await classify_batch(client, base_url, model, [row]))[0]
                            with report.open('a', encoding='utf-8') as handle:
                                handle.write(json.dumps(result) + '\n')
                            break
                        except (httpx.HTTPError, ValueError, KeyError, TypeError):
                            print(json.dumps({'asin': row['asin'], 'attempt': attempt + 1, 'status': 'retry'}), flush=True)
                if result is None:
                    counts['failed'] += 1
                    continue
                async with AsyncSessionLocal() as db:
                    await db.execute(text("""
                        INSERT INTO curated_bestseller_reviews (category, cpk, status, reviewed_at, selected_media)
                        VALUES (:category, :cpk, 'pending', now(), jsonb_build_object(
                            'images', '[]'::jsonb, 'videos', '[]'::jsonb,
                            'identity_reviews', jsonb_build_object(CAST(:asin AS text), CAST(:result AS jsonb))))
                        ON CONFLICT (category, cpk) DO UPDATE SET selected_media =
                            jsonb_set(COALESCE(curated_bestseller_reviews.selected_media::jsonb, '{}'::jsonb),
                            '{identity_reviews}', COALESCE(curated_bestseller_reviews.selected_media::jsonb->'identity_reviews', '{}'::jsonb)
                            || jsonb_build_object(CAST(:asin AS text), CAST(:result AS jsonb)))
                    """), {'category': row['category'], 'cpk': row['cpk'], 'asin': row['asin'], 'result': json.dumps(result)})
                    await db.commit()
                counts[result['decision']] += 1
                print(json.dumps({'processed': sum(counts.values()), 'remaining_at_start': len(pending), 'decisions': dict(counts)}), flush=True)

        await asyncio.gather(*(worker() for _ in range(3)))
    async with AsyncSessionLocal() as db:
        final = (await bestseller_catalogue(db))['items']
    summary = {'total': len(final), 'decisions': dict(Counter(
        (row.get('identity_review') or {}).get('decision', 'unreviewed') for row in final)), 'model': model}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary), flush=True)
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
