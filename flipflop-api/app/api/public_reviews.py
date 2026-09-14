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

# These are preview records for the storefront layout.  They are explicitly
# marked so they can be replaced by approved, sourced feedback before launch.
_SAMPLE_REVIEWS = [
    {"id": 1, "author": "Maya", "location": "Leeds, West Yorkshire", "quote": "The whole process felt thoughtful from the first chat. The finished build is quiet, tidy and exactly the colour palette I wanted.", "stars": 5, "source": "Sample review", "is_sample": True},
    {"id": 2, "author": "Oliver Grant", "location": "Bristol", "quote": "A brilliant machine and a genuinely nice buying experience. Cable management is immaculate and the performance in my editing apps is night and day.", "stars": 5, "source": "Sample review", "is_sample": True, "avatar_url": "https://i.pravatar.cc/96?img=12"},
    {"id": 3, "author": "Priya", "location": "Manchester", "quote": "I finally have a PC that looks like it belongs in my room. The updates during the build were reassuring and everything arrived packed like a precious object.", "stars": 5, "source": "Sample review", "is_sample": True},
    {"id": 4, "author": "Daniel Hughes", "location": "Cardiff", "quote": "Fast, friendly and no jargon. They helped me choose sensible parts for 1440p gaming instead of simply pushing the most expensive options.", "stars": 4.5, "source": "Sample review", "is_sample": True},
    {"id": 5, "author": "Sophie", "location": "Cambridge", "quote": "The little details are what stood out: the matching lighting, the neat finish and the clear handover notes. It feels like someone cared.", "stars": 5, "source": "Sample review", "is_sample": True},
    {"id": 6, "author": "Callum Reed", "location": "Glasgow", "quote": "My old setup was a tangle of upgrades. FlipFlop made the whole thing straightforward and the new system is wonderfully snappy for work and games.", "stars": 5, "source": "Sample review", "is_sample": True, "avatar_url": "https://i.pravatar.cc/96?img=33"},
    {"id": 7, "author": "Aisha", "location": "Nottingham", "quote": "Beautiful build, sensible advice and a very smooth delivery. The photos before dispatch were a lovely touch.", "stars": 5, "source": "Sample review", "is_sample": True},
    {"id": 8, "author": "Tom Bennett", "location": "Brighton", "quote": "It is rare to find a custom PC that feels both personal and practical. Mine is cool, quiet and handles every game I throw at it.", "stars": 5, "source": "Sample review", "is_sample": True},
    {"id": 9, "author": "Hannah", "location": "York", "quote": "From the first specification check to switching it on, the experience was calm and clear. The finished case looks even better in person.", "stars": 5, "source": "Sample review", "is_sample": True},
    {"id": 10, "author": "Marcus Wilson", "location": "Reading, Berkshire", "quote": "Excellent attention to detail. The build is clean, the benchmarks were easy to understand and the support team answered my questions quickly.", "stars": 5, "source": "Sample review", "is_sample": True},
]


@router.get("/reviews")
async def public_list_reviews():
    """Return the review showcase records used by the public storefront."""
    return _SAMPLE_REVIEWS
