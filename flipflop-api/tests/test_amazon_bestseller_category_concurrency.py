import asyncio

from app.services import amazon_bestsellers


class _Page:
    def __init__(self, context):
        self.context = context

    async def title(self):
        return "Test Hardware - Amazon.co.uk"

    async def close(self):
        self.context.active_pages -= 1


class _Context:
    def __init__(self):
        self.active_pages = 0
        self.max_active_pages = 0

    async def new_page(self):
        self.active_pages += 1
        self.max_active_pages = max(self.max_active_pages, self.active_pages)
        return _Page(self)


async def test_category_capture_uses_independent_pages_with_the_shared_cap(monkeypatch):
    context = _Context()
    semaphore = asyncio.Semaphore(2)

    async def fake_load_page(_page, url, _rank_offset):
        await asyncio.sleep(0.01)
        asin = url.rsplit("/", 1)[-1]
        return ([{"asin": asin, "rank": 1, "title": f"Part {asin}"}], None, True)

    monkeypatch.setattr(amazon_bestsellers, "_load_bestseller_page", fake_load_page)
    results = await asyncio.gather(*(
        amazon_bestsellers._capture_component_bestseller_category(
            context, f"category-{index}", "Test Hardware",
            f"https://example.test/{index}", semaphore,
        )
        for index in range(5)
    ))

    assert context.max_active_pages == 2
    assert context.active_pages == 0
    assert len(results) == 5
    assert all(error is None and page_count == 1 for _, page_count, error in results)
    assert all(len(products) == 1 for products, _, _ in results)
