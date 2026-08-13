"""
Public reviews endpoint — no auth required.

No review/testimonial model exists in this codebase yet (verified: no
Review/Testimonial table, no Trustpilot/Google integration). This endpoint
is real infrastructure for when that lands — it returns an empty list today
rather than fabricated quotes. The storefront reviews marquee must render an
honest "reviews coming soon" state on an empty response, never placeholder
testimonials.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/public", tags=["public-reviews"])


@router.get("/reviews")
async def public_list_reviews():
    """Approved customer reviews. Empty until a real review source is wired up."""
    return []
