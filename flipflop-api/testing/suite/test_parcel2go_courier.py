from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock

from app.services import parcel2go_booking, parcel2go_courier
from app.services.ebay_order_sync import BuyerAddress
from app.services.parcel2go_booking import Parcel2GoBookingError
from app.services.parcel2go_courier import Parcel2GoError, _parse_tracked_quotes


def test_quote_parser_omits_rows_without_a_bookable_service_or_finite_positive_price():
    parsed = _parse_tracked_quotes({
        "Quotes": [
            {"Service": {"Slug": "dpd-home", "CourierName": "DPD", "Name": "Home"}, "TotalPrice": "12.50", "Extras": [{"Type": "Signature", "Amount": 1.5}]},
            {"Service": {"Slug": "", "CourierName": "Unknown"}, "TotalPrice": 5, "Extras": [{"Type": "Signature"}]},
            {"Service": {"Slug": "zero-price"}, "TotalPrice": 0, "Extras": [{"Type": "Signature"}]},
            {"Service": {"Slug": "nan-price"}, "TotalPrice": "NaN", "Extras": [{"Type": "Signature"}]},
            {"Service": {"Slug": "infinite-price"}, "TotalPrice": "Infinity", "Extras": [{"Type": "Signature"}]},
            {"Service": {"Slug": "not-a-number"}, "TotalPrice": "invalid", "Extras": [{"Type": "Signature"}]},
            {"Service": {"Slug": "no-signature"}, "TotalPrice": 7},
            {"TotalPrice": 2},
            None,
        ]
    })

    assert len(parsed) == 1
    assert parsed[0].service_slug == "dpd-home"
    assert parsed[0].price_gbp == 12.5
    assert parsed[0].signature_tracking is True


def test_quote_parser_returns_empty_for_malformed_envelope():
    assert _parse_tracked_quotes({"Quotes": {"unexpected": "object"}}) == []
    assert _parse_tracked_quotes([]) == []


@pytest.mark.parametrize(
    "candidate, expected",
    [
        (" https://tracking.example.test/track/ABC123 ", "https://tracking.example.test/track/ABC123"),
        ("http://tracking.example.test/track/ABC123", None),
        ("https://operator:secret@tracking.example.test/track/ABC123", None),
        ("https:///missing-host", None),
        ("https://tracking.example.test/" + "x" * 1000, None),
        (None, None),
    ],
)
def test_provider_tracking_url_must_be_safe_for_customer_display(candidate, expected):
    assert parcel2go_booking._safe_provider_tracking_url(candidate) == expected


def test_order_portal_falls_back_to_safe_booking_url_for_older_handover_events():
    from app.api.orders import _manual_build_tracking_url

    build = SimpleNamespace(evidence_data={
        "shipment_booking_confirmation": {
            "tracking_url": "https://tracking.example.test/track/OLDER-BOOKING",
        }
    })
    assert _manual_build_tracking_url(build, []) == (
        "https://tracking.example.test/track/OLDER-BOOKING"
    )

    event = SimpleNamespace(tracking_url="https://tracking.example.test/track/NEW-EVENT")
    assert _manual_build_tracking_url(build, [event]) == (
        "https://tracking.example.test/track/NEW-EVENT"
    )

    unsafe_build = SimpleNamespace(evidence_data={
        "shipment_booking_confirmation": {
            "tracking_url": "https://operator:secret@tracking.example.test/track/unsafe",
        }
    })
    assert _manual_build_tracking_url(unsafe_build, []) is None


def test_customer_tracking_event_serializer_revalidates_stored_urls():
    from app.api.orders import _tracking_event_dict

    event = SimpleNamespace(
        id=1,
        provider="parcel2go",
        status_code="in_transit",
        description="Parcel in transit",
        location=None,
        tracking_url="https://tracking.example.test/track/ABC123",
        live_map_url="https://maps.example.test/live/ABC123",
        occurred_at=SimpleNamespace(isoformat=lambda: "2026-09-30T12:00:00"),
    )
    serialized = _tracking_event_dict(event)
    assert serialized["tracking_url"] == "https://tracking.example.test/track/ABC123"
    assert serialized["live_map_url"] == "https://maps.example.test/live/ABC123"

    event.tracking_url = "https://user:password@tracking.example.test/private"
    event.live_map_url = "http://maps.example.test/live"
    serialized = _tracking_event_dict(event)
    assert serialized["tracking_url"] is None
    assert serialized["live_map_url"] is None


@pytest.mark.asyncio
async def test_live_quote_request_includes_signature_extra(monkeypatch):
    captured = {}
    monkeypatch.setattr(parcel2go_courier, "_get_access_token", AsyncMock(return_value="test-token"))

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"Quotes": [{
                "Service": {"Slug": "dpd-home", "CourierName": "DPD", "Name": "Home"},
                "TotalPrice": 12.5,
                "Extras": [{"Type": "Signature", "Amount": 1.5}],
            }]}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, *, json, **_kwargs):
            captured.update(json)
            return FakeResponse()

    monkeypatch.setattr(parcel2go_courier.httpx, "AsyncClient", FakeClient)
    quotes = await parcel2go_courier.get_tracked_quotes(
        weight_kg=10, length_cm=50, width_cm=40, height_cm=30,
        value_gbp=800, environment="sandbox",
    )

    assert captured["Extras"] == [{"Type": "Signature"}]
    assert len(quotes) == 1 and quotes[0].signature_tracking is True


@pytest.mark.asyncio
async def test_create_order_sends_signature_as_upsell_and_returns_provider_total(monkeypatch):
    captured = {}
    settings = SimpleNamespace(
        parcel2go_environment="sandbox",
        seller_forename="Flip", seller_surname="Flop", seller_email="seller@example.test",
        seller_phone="07123456789", seller_address_property="1",
        seller_address_street="Test Street", seller_address_town="London",
        seller_address_county="Greater London", seller_address_postcode="SW1A 1AA",
        seller_address_country_iso="GBR",
    )
    monkeypatch.setattr(parcel2go_booking, "get_settings", lambda: settings)
    monkeypatch.setattr(parcel2go_booking, "_get_access_token", AsyncMock(return_value="test-token"))

    class FakeResponse:
        status_code = 201

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, *, json, **_kwargs):
            captured.update(json)
            item_id = json["Items"][0]["Id"]
            return FakeResponse({
                "OrderId": "P2G-TEST-1",
                "Hash": "provider-hash",
                "TotalPrice": 12.5,
                "OrderlineIdMap": [{"ItemId": item_id, "OrderLineId": "P2G-LINE-1"}],
            })

    monkeypatch.setattr(parcel2go_booking.httpx, "AsyncClient", FakeClient)
    order_id, order_hash, line_id, provider_total = await parcel2go_booking.create_order(
        service_slug="dpd-home",
        weight_kg=10, length_cm=50, width_cm=40, height_cm=30,
        value_gbp=800,
        buyer_address=BuyerAddress(
            contact_name="Test Buyer", address_line1="2 Buyer Road", address_line2=None,
            city="London", state_or_province=None, postal_code="SW1A 1AA",
            country_code="GB", phone=None,
        ),
        upsells=["Signature"],
        environment="sandbox",
    )

    assert captured["Items"][0]["Upsells"] == [{"Type": "Signature"}]
    assert (order_id, order_hash, line_id, provider_total) == (
        "P2G-TEST-1", "provider-hash", "P2G-LINE-1", 12.5,
    )


@pytest.mark.asyncio
async def test_payment_failure_does_not_log_or_return_raw_provider_body(monkeypatch):
    private_provider_text = "buyer@example.test 1 Private Road SW1A 1AA"
    logged = []
    monkeypatch.setattr(parcel2go_booking, "_get_access_token", AsyncMock(return_value="token"))
    monkeypatch.setattr(
        parcel2go_booking,
        "log",
        SimpleNamespace(error=lambda *args, **kwargs: logged.append((args, kwargs))),
    )

    class FakeResponse:
        status_code = 402
        text = private_provider_text

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(parcel2go_booking.httpx, "AsyncClient", FakeClient)
    with pytest.raises(Parcel2GoBookingError) as raised:
        await parcel2go_booking.pay_order_with_prepay("P2G-ORDER-1", environment="sandbox")

    assert private_provider_text not in str(raised.value)
    assert all("body" not in kwargs for _args, kwargs in logged)
    assert private_provider_text not in repr(logged)


@pytest.mark.asyncio
async def test_order_create_failure_does_not_log_or_return_raw_provider_body(monkeypatch):
    private_provider_text = "buyer@example.test 1 Private Road SW1A 1AA"
    logged = []
    monkeypatch.setattr(
        parcel2go_booking,
        "get_settings",
        lambda: SimpleNamespace(
            parcel2go_environment="sandbox",
            seller_forename="Flip", seller_surname="Flop", seller_email="seller@example.test",
            seller_phone="07123456789", seller_address_property=None,
            seller_address_street="Test Street", seller_address_town="London",
            seller_address_county=None, seller_address_postcode="SW1A 1AA",
            seller_address_country_iso="GBR",
        ),
    )
    monkeypatch.setattr(parcel2go_booking, "_get_access_token", AsyncMock(return_value="token"))
    monkeypatch.setattr(
        parcel2go_booking,
        "log",
        SimpleNamespace(
            error=lambda *args, **kwargs: logged.append((args, kwargs)),
            info=lambda *args, **kwargs: None,
        ),
    )

    class FakeResponse:
        status_code = 500
        text = private_provider_text

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(parcel2go_booking.httpx, "AsyncClient", FakeClient)
    with pytest.raises(Parcel2GoBookingError) as raised:
        await parcel2go_booking.create_order(
            service_slug="dpd-home",
            weight_kg=10, length_cm=50, width_cm=40, height_cm=30,
            value_gbp=800,
            buyer_address=BuyerAddress(
                contact_name="Test Buyer", address_line1="2 Buyer Road", address_line2=None,
                city="London", state_or_province=None, postal_code="SW1A 1AA",
                country_code="GB", phone=None,
            ),
            upsells=["Signature"],
            environment="sandbox",
        )

    assert private_provider_text not in str(raised.value)
    assert private_provider_text not in repr(logged)


@pytest.mark.asyncio
async def test_quote_failure_does_not_log_or_return_raw_provider_body(monkeypatch):
    private_provider_text = "buyer@example.test 1 Private Road SW1A 1AA"
    logged = []
    monkeypatch.setattr(
        parcel2go_courier,
        "get_settings",
        lambda: SimpleNamespace(parcel2go_environment="sandbox"),
    )
    monkeypatch.setattr(parcel2go_courier, "_get_access_token", AsyncMock(return_value="token"))
    monkeypatch.setattr(
        parcel2go_courier,
        "log",
        SimpleNamespace(error=lambda *args, **kwargs: logged.append((args, kwargs))),
    )

    class FakeResponse:
        status_code = 502
        text = private_provider_text

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(parcel2go_courier.httpx, "AsyncClient", FakeClient)
    with pytest.raises(Parcel2GoError) as raised:
        await parcel2go_courier.get_tracked_quotes(
            weight_kg=10, length_cm=50, width_cm=40, height_cm=30,
            value_gbp=800, environment="sandbox",
        )

    assert private_provider_text not in str(raised.value)
    assert private_provider_text not in repr(logged)


@pytest.mark.asyncio
async def test_auth_failure_does_not_log_or_return_raw_provider_body(monkeypatch):
    private_provider_text = "client secret or account detail from provider"
    logged = []
    monkeypatch.setattr(
        parcel2go_courier,
        "get_settings",
        lambda: SimpleNamespace(
            parcel2go_client_id="client-id",
            parcel2go_client_secret="client-secret",
            parcel2go_environment="sandbox",
        ),
    )
    monkeypatch.setattr(
        parcel2go_courier,
        "log",
        SimpleNamespace(error=lambda *args, **kwargs: logged.append((args, kwargs))),
    )

    class FakeResponse:
        status_code = 401
        text = private_provider_text

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(parcel2go_courier.httpx, "AsyncClient", FakeClient)
    with pytest.raises(Parcel2GoError) as raised:
        await parcel2go_courier._get_access_token("sandbox")

    assert private_provider_text not in str(raised.value)
    assert private_provider_text not in repr(logged)


@pytest.mark.asyncio
async def test_successful_booking_retains_only_parsed_fields_and_safe_log_flags(monkeypatch):
    private_provider_data = {
        "buyer_email": "buyer@example.test",
        "delivery_address": "1 Private Road, London",
        "Links": [
            {
                "Rel": "label",
                "Href": "https://labels.example.test/private-label-token",
            },
            {
                "Rel": "track",
                "Href": "https://tracking.example.test/private-tracking-token",
                "TrackingNumber": "PRIVATE-TRACKING-123",
            },
        ],
    }
    logged = []
    monkeypatch.setattr(
        parcel2go_booking,
        "get_settings",
        lambda: SimpleNamespace(parcel2go_environment="sandbox"),
    )
    monkeypatch.setattr(parcel2go_booking, "_get_access_token", AsyncMock(return_value="token"))
    monkeypatch.setattr(
        parcel2go_booking,
        "log",
        SimpleNamespace(
            error=lambda *args, **kwargs: logged.append((args, kwargs)),
            info=lambda *args, **kwargs: logged.append((args, kwargs)),
        ),
    )

    class FakeResponse:
        status_code = 200

        def json(self):
            return private_provider_data

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(parcel2go_booking.httpx, "AsyncClient", FakeClient)
    shipment = await parcel2go_booking.pay_order_with_prepay(
        "P2G-ORDER-1", environment="sandbox"
    )

    assert shipment.parcel2go_order_id == "P2G-ORDER-1"
    assert shipment.tracking_number == "PRIVATE-TRACKING-123"
    assert shipment.label_url == "https://labels.example.test/private-label-token"
    assert shipment.tracking_url == "https://tracking.example.test/private-tracking-token"
    assert not hasattr(shipment, "raw_response")
    assert "buyer@example.test" not in repr(logged)
    assert "1 Private Road" not in repr(logged)
    assert "PRIVATE-TRACKING-123" not in repr(logged)
    assert "private-label-token" not in repr(logged)
    assert "private-tracking-token" not in repr(logged)
    assert logged[-1][1] == {
        "order_id": "P2G-ORDER-1",
        "has_label_url": True,
        "has_tracking_number": True,
    }
