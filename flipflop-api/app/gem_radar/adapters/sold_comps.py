"""Sold evidence contracts.

The backend does not request eBay sold pages. FlipFlopXtension performs those
captures in the signed-in browser and submits observations through the API.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SoldComp:
    price: float
    postage: float
    condition: str
    sold_at: str
    url: str | None = None
    title: str | None = None
    delivery_cost_known: bool = False
    sold_date_text: str | None = None


@dataclass
class SoldCompsResult:
    available: bool
    comps: list[SoldComp] = field(default_factory=list)
    unavailable_reason: str | None = None


class SoldCompsAdapter(ABC):
    """Read sold evidence supplied by the extension; never scrape eBay."""

    @abstractmethod
    async def fetch(self, query: str, condition: str) -> SoldCompsResult: ...


class UnavailableSoldCompsAdapter(SoldCompsAdapter):
    """Fallback used when no matching extension-submitted observations exist."""

    async def fetch(self, query: str, condition: str) -> SoldCompsResult:
        return SoldCompsResult(
            available=False,
            unavailable_reason=(
                "No matching extension-submitted sold observations are available; "
                "backend eBay sold-page requests are disabled."
            ),
        )
