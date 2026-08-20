from app.services.amazon_bestsellers import (
    clean_sales_velocity,
    extract_asin,
    match_row_by_bestseller,
    name_similarity,
)


class _Row:
    def __init__(self, name: str, source_url: str):
        self.name = name
        self.source_url = source_url


def test_clean_sales_velocity_rejects_card_blob():
    assert clean_sales_velocity("400+ bought in past month") == "400+ bought in past month"
    assert clean_sales_velocity("Best Sellerin Computer CasesCORSAIR FRAME 4500X") is None
    assert clean_sales_velocity(None) is None


def test_extract_asin_from_dp_url():
    assert extract_asin("https://www.amazon.co.uk/dp/B0DF7RVRW2") == "B0DF7RVRW2"
    assert extract_asin("https://www.amazon.co.uk/foo/dp/B0AAAA1111/ref=sr_1") == "B0AAAA1111"
    assert extract_asin(None) is None


def test_name_similarity_ignores_case_words():
    assert name_similarity("HYTE Y60 PC Case", "HYTE Y60 Case") > 0.8


def test_match_prefers_asin_over_title():
    rows = [
        _Row("Unrelated tower", "https://www.amazon.co.uk/dp/B0AAAA1111"),
        _Row("HYTE Y60", "https://www.amazon.co.uk/foo/dp/B0BBBB2222?psc=1"),
    ]
    matched = match_row_by_bestseller(
        {"asin": "B0BBBB2222", "title": "Completely different title"},
        rows,
    )
    assert matched is rows[1]


def test_match_falls_back_to_fuzzy_title():
    rows = [_Row("Lian Li Lancool 217 Black ATX", "https://example.com/no-asin")]
    matched = match_row_by_bestseller(
        {"asin": "B0ZZZZZZZZ", "title": "Lian Li Lancool 217 PC Case Black"},
        rows,
    )
    assert matched is rows[0]
