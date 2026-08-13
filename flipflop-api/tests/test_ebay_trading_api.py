"""
eBay legacy Trading API client. Not verifiable against live eBay (no network
egress to any eBay domain in this environment) — tested against mocked HTTP
responses shaped like eBay's documented Trading API XML contract. The exact
element nesting has NOT been confirmed against a real eBay response; treat
this as implemented-to-spec but unverified until it runs against production
eBay, same caveat as the rest of this session's eBay integration work.
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.services import ebay_trading_api as trading

NS = trading._NS


def _xml_response(ack: str, body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<GetBestOffersResponse xmlns="{NS}">
  <Ack>{ack}</Ack>
  {body}
</GetBestOffersResponse>"""


def _mock_httpx(status_code: int, text: str):
    mock_resp = AsyncMock()
    mock_resp.status_code = status_code
    mock_resp.text = text
    patcher = patch("httpx.AsyncClient")
    MockClient = patcher.start()
    MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
    return patcher


async def test_get_best_offers_parses_success_response():
    body = f"""
    <BestOfferArray>
      <BestOffer>
        <BestOfferID>5001</BestOfferID>
        <Buyer><UserID>buyer123</UserID></Buyer>
        <Price currencyID="GBP">720.00</Price>
        <Status>Active</Status>
      </BestOffer>
    </BestOfferArray>"""
    patcher = _mock_httpx(200, _xml_response("Success", body))
    try:
        with patch("app.services.ebay_trading_api.get_settings") as mock_settings:
            mock_settings.return_value.ebay_environment = "production"
            offers = await trading.get_best_offers("item-1", "token-1")
    finally:
        patcher.stop()

    assert len(offers) == 1
    assert offers[0]["best_offer_id"] == "5001"
    assert offers[0]["buyer_id"] == "buyer123"
    assert offers[0]["price"] == 720.0
    assert offers[0]["status"] == "Active"


async def test_get_best_offers_raises_on_failure_ack():
    body = """
    <Errors><LongMessage>Invalid item ID</LongMessage></Errors>"""
    patcher = _mock_httpx(200, _xml_response("Failure", body))
    try:
        with patch("app.services.ebay_trading_api.get_settings") as mock_settings:
            mock_settings.return_value.ebay_environment = "production"
            with pytest.raises(RuntimeError, match="Invalid item ID"):
                await trading.get_best_offers("bad-item", "token-1")
    finally:
        patcher.stop()


async def test_respond_to_best_offer_counter():
    patcher = _mock_httpx(200, _xml_response("Success", ""))
    try:
        with patch("app.services.ebay_trading_api.get_settings") as mock_settings:
            mock_settings.return_value.ebay_environment = "production"
            ok = await trading.respond_to_best_offer("item-1", "5001", "Counter", 860.0, "token-1")
    finally:
        patcher.stop()
    assert ok is True


async def test_call_raises_on_http_error():
    patcher = _mock_httpx(500, "Internal Server Error")
    try:
        with patch("app.services.ebay_trading_api.get_settings") as mock_settings:
            mock_settings.return_value.ebay_environment = "production"
            with pytest.raises(RuntimeError, match="HTTP 500"):
                await trading.get_best_offers("item-1", "token-1")
    finally:
        patcher.stop()
