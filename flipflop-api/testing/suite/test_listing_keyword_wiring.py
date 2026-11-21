"""
Row 24: the title/description generator should pull real buyer search terms
from the keyword-research tool rather than guessing — verifies the wiring,
not the LLM's actual output (which is mocked).
"""
from unittest.mock import AsyncMock, patch

from app.services import ai_service


async def test_generate_listing_content_includes_keyword_terms_in_prompt():
    captured_prompt = {}

    async def fake_chat(message, history, listing_context=None):
        captured_prompt["prompt"] = message
        return '{"titles": ["Gaming PC i7-13700K RTX 4070"], "description": "desc"}', "mock-model"

    fake_keywords = {
        "query": "i7-13700K RTX 4070",
        "sample_titles": ["Gaming PC i7-13700K RTX 4070 32GB 1TB SSD"],
        "frequent_tokens": [("RTX", 3), ("4070", 3), ("13700K", 2)],
        "note": "test",
    }

    with patch("app.services.ai_service.chat", new=fake_chat), \
         patch("app.services.performance_dashboard.search_title_keywords", new=AsyncMock(return_value=fake_keywords)):
        titles, description = await ai_service.generate_listing_content(
            cpu="i7-13700K", ram_gb=32, ram_type="DDR5", storage_gb=1000, storage_type="SSD",
            gpu="RTX 4070", location="UK",
        )

    assert titles == ["Gaming PC i7-13700K RTX 4070"]
    assert "RTX" in captured_prompt["prompt"]
    assert "4070" in captured_prompt["prompt"]
    assert "Real buyer search terms" in captured_prompt["prompt"]


async def test_generate_listing_content_survives_keyword_lookup_failure():
    async def fake_chat(message, history, listing_context=None):
        return '{"titles": ["Gaming PC"], "description": "desc"}', "mock-model"

    with patch("app.services.ai_service.chat", new=fake_chat), \
         patch("app.services.performance_dashboard.search_title_keywords", new=AsyncMock(side_effect=RuntimeError("boom"))):
        titles, description = await ai_service.generate_listing_content(
            cpu="i7-13700K", ram_gb=32, ram_type="DDR5", storage_gb=1000, storage_type="SSD",
            gpu="RTX 4070", location="UK",
        )

    assert titles == ["Gaming PC"]
