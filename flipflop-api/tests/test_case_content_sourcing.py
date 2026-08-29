from types import SimpleNamespace

from app.workers.case_content_sourcing import (
    _looks_exact,
    _page_images,
    _search_result_urls,
    _youtube_candidates,
)


def _case():
    return SimpleNamespace(brand="MSI", model="MAG FORGE 321R AIRFLOW", name="MSI MAG FORGE 321R AIRFLOW PC Case")


def test_exact_match_requires_distinctive_model_token():
    assert _looks_exact(_case(), "MSI MAG FORGE 321R AIRFLOW review")
    assert not _looks_exact(_case(), "MSI MAG FORGE 120A review")


def test_duckduckgo_redirects_are_unwrapped():
    markup = '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fcase">Case</a>'
    assert _search_result_urls(markup) == ["https://example.com/case"]


def test_page_images_excludes_branding_assets_and_deduplicates():
    markup = '''
      <meta property="og:image" content="/media/321r.webp">
      <img src="/media/321r.webp"><img src="/img/logo.png">
    '''
    assert _page_images("https://msi.test/product/321r", markup) == [{
        "url": "https://msi.test/media/321r.webp", "source": "msi.test",
        "source_page": "https://msi.test/product/321r", "label": None,
    }]


def test_youtube_candidates_keep_exact_model_only():
    markup = (
        '"videoId":"abcdefghijk","title":{"runs":[{"text":"MSI MAG FORGE 321R AIRFLOW Review"'
        '"videoId":"zzzzzzzzzzz","title":{"runs":[{"text":"MSI MAG FORGE 120A Review"'
    )
    assert _youtube_candidates(markup, _case()) == [{
        "url": "https://www.youtube.com/watch?v=abcdefghijk",
        "title": "MSI MAG FORGE 321R AIRFLOW Review",
    }]
