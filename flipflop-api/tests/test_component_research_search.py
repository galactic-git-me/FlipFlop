import pytest

from app.services.component_research_search import (
    discover_component_sources,
    parse_search_results,
)


def test_search_result_parser_unwraps_only_external_https_links():
    markup = '''
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fsupport.example.com%2Fmanual">Exact manual</a>
      <a class="result__a" href="https://support.example.com/manual">Duplicate result</a>
      <a class="result__a" href="http://manufacturer.example/manual">Insecure result</a>
      <a class="result__a" href="javascript:alert(1)">Script result</a>
      <a class="result__a" href="https://127.0.0.1/admin">Local IP result</a>
      <a class="result__a" href="https://localhost/admin">Local host result</a>
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fduckduckgo.com%2Fprivacy">Search provider</a>
    '''

    results = parse_search_results(markup)

    assert results == [{
        "title": "Exact manual",
        "source_url": "https://support.example.com/manual",
        "publisher": "support.example.com",
    }]


class FakeResponse:
    headers = {"content-type": "text/html; charset=utf-8"}
    text = '<a class="result__a" href="https://support.example.com/downloads">Downloads</a>'

    def raise_for_status(self):
        pass


class FakeSearchClient:
    def __init__(self):
        self.params = None

    async def get(self, url, *, params):
        self.params = params
        return FakeResponse()


@pytest.mark.asyncio
async def test_discovery_is_topic_scoped_and_returns_drafts_not_approval():
    client = FakeSearchClient()

    results = await discover_component_sources(
        "MSI MAG B650 TOMAHAWK WIFI",
        "manual",
        client=client,
    )

    assert client.params["kl"] == "uk-en"
    assert '"MSI MAG B650 TOMAHAWK WIFI"' in client.params["q"]
    assert "user manual PDF" in client.params["q"]
    assert results[0]["source_url"] == "https://support.example.com/downloads"
    assert "operator_approved" not in results[0]
    assert "claim" not in results[0]


@pytest.mark.asyncio
async def test_discovery_can_restrict_search_to_official_manufacturer_domain():
    client = FakeSearchClient()

    await discover_component_sources(
        "MSI X870 GAMING PLUS WIFI",
        "compatibility",
        publisher_domains=("msi.com",),
        client=client,
    )

    assert "site:msi.com" in client.params["q"]
    assert '"MSI X870 GAMING PLUS WIFI"' in client.params["q"]
