"""
Social proof event pipeline — records real order/login events with a
best-effort location and broadcasts them live to connected storefront
globe widgets over WebSocket.

Location source:
- orders: the customer's shipping address, geocoded via OpenStreetMap
  Nominatim (keyless, rate-limited — fine for occasional order volume).
- logins: the request IP, resolved via ip-api.com (keyless, ~45 req/min
  free tier). Private/loopback IPs (localhost dev) resolve to nothing —
  the event is skipped rather than faked, matching this codebase's
  "no fabricated data" convention (see public_reviews.py).

Both lookups are cached in-process since the same address/IP repeats
across a session. An event without resolvable coordinates is dropped —
the globe has nothing to plot without a lat/lng.
"""
import httpx
import structlog
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social_proof_event import SocialProofEvent

log = structlog.get_logger(__name__)

_geocode_cache: dict[str, dict | None] = {}
_geoip_cache: dict[str, dict | None] = {}

_PRIVATE_IPS = {"127.0.0.1", "::1", "localhost", "testclient"}


async def geocode_address(address: str) -> dict | None:
    """Address text -> {city, country, lat, lng} via OSM Nominatim."""
    if not address or not address.strip():
        return None
    key = address.strip().lower()
    if key in _geocode_cache:
        return _geocode_cache[key]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": address, "format": "json", "limit": 1, "addressdetails": 1},
                headers={"User-Agent": "FlipFlop-SocialProof/1.0 (mac@theflipflop.shop)"},
            )
            resp.raise_for_status()
            results = resp.json()
        if not results:
            _geocode_cache[key] = None
            return None
        top = results[0]
        addr = top.get("address", {})
        location = {
            "city": addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county"),
            "country": addr.get("country"),
            "lat": float(top["lat"]),
            "lng": float(top["lon"]),
        }
        _geocode_cache[key] = location
        return location
    except Exception as exc:
        log.warning("social_proof.geocode_failed", error=str(exc))
        return None


async def geolocate_ip(ip: str | None) -> dict | None:
    """IP -> {city, country, lat, lng} via ip-api.com. Skips private/local IPs."""
    if not ip or ip in _PRIVATE_IPS:
        return None
    if ip in _geoip_cache:
        return _geoip_cache[ip]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,city,country,lat,lon"},
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") != "success":
            _geoip_cache[ip] = None
            return None
        location = {
            "city": data.get("city"),
            "country": data.get("country"),
            "lat": data.get("lat"),
            "lng": data.get("lon"),
        }
        _geoip_cache[ip] = location
        return location
    except Exception as exc:
        log.warning("social_proof.geoip_failed", error=str(exc))
        return None


def display_name_from(full_name: str | None) -> str:
    """'Sarah Mitchell' -> 'Sarah M.' — first name plus last initial, never a full surname."""
    parts = [p for p in (full_name or "").strip().split() if p]
    if not parts:
        return "A customer"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


def serialize_event(event: SocialProofEvent) -> dict:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "display_name": event.display_name,
        "product_name": event.product_name,
        "city": event.city,
        "country": event.country,
        "lat": event.lat,
        "lng": event.lng,
        "created_at": event.created_at.isoformat(),
    }


class _SocialProofBroadcaster:
    """In-process WebSocket fanout — matches this API's existing single-process
    asyncio-task architecture (no Redis/pubsub elsewhere in this codebase)."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)


broadcaster = _SocialProofBroadcaster()


async def record_order_event(
    db: AsyncSession,
    *,
    customer_name: str | None,
    address: str | None,
    product_name: str | None,
) -> None:
    location = await geocode_address(address) if address else None
    if location is None or location.get("lat") is None:
        log.info("social_proof.order.skipped_no_location")
        return

    event = SocialProofEvent(
        event_type="order",
        display_name=display_name_from(customer_name),
        product_name=product_name,
        city=location.get("city"),
        country=location.get("country"),
        lat=location["lat"],
        lng=location["lng"],
    )
    db.add(event)
    await db.flush()
    await db.commit()
    await broadcaster.broadcast(serialize_event(event))


async def record_login_event(
    db: AsyncSession,
    *,
    customer_name: str | None,
    ip: str | None,
) -> None:
    location = await geolocate_ip(ip)
    if location is None or location.get("lat") is None:
        log.info("social_proof.login.skipped_no_location", ip=ip)
        return

    event = SocialProofEvent(
        event_type="login",
        display_name=display_name_from(customer_name),
        product_name=None,
        city=location.get("city"),
        country=location.get("country"),
        lat=location["lat"],
        lng=location["lng"],
    )
    db.add(event)
    await db.flush()
    await db.commit()
    await broadcaster.broadcast(serialize_event(event))
