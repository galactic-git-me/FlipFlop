"""
Case demand scoring — combines Google Trends + keyword analysis.
Runs daily to update demand scores for case selection in builds.
"""
import asyncio
from datetime import datetime
from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models.part import Part, PartCategory
import structlog

log = structlog.get_logger(__name__)


async def score_case_demand() -> dict:
    """
    Score case demand (0-100) based on:
    1. Google Trends interest for keywords
    2. Keyword popularity multipliers
    3. Form factor trendiness
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        log.warning("case_demand.pytrends_missing", msg="Install pytrends: pip install pytrends")
        return {"scored": 0, "error": "pytrends not installed"}

    try:
        pytrends = TrendReq(hl='en-GB', tz=0)

        # Get trend data for case-related keywords
        trend_keywords = [
            'gaming pc case',
            'RGB case',
            'tempered glass case',
            'dual chamber case',
            'airflow case',
            'compact case',
            'mini itx case',
        ]

        # Fetch latest trends (last 30 days)
        pytrends.build_payload(trend_keywords, cat=0, timeframe='today 1m', geo='GB')
        trends = pytrends.interest_over_time()

        # Get latest interest values (most recent day)
        latest_trends = trends[trend_keywords].iloc[-1] if len(trends) > 0 else {}

        log.info("case_demand.trends_fetched", keywords=len(trend_keywords), latest=dict(latest_trends))

        # Keyword popularity multipliers (what factors into demand)
        keyword_multipliers = {
            'gaming': 1.5,  # Gaming cases are hot
            'RGB': 1.8,     # RGB highly demanded
            'tempered-glass': 1.4,  # Popular feature
            'dual-chamber': 1.6,     # Trending design
            'airflow': 1.3,
            'white': 0.8,   # Common, less differentiating
            'black': 0.7,
            'wood': 1.2,    # Trendy aesthetic
            'compact': 1.1,
            'tower': 0.9,
            'silent': 1.2,
            'premium': 1.3,
            'budget': 0.6,
        }

        # Trend keyword to database keyword mapping
        trend_to_keyword_bonus = {
            'gaming pc case': ['gaming', 'RGB'],  # Gaming cases often have RGB
            'RGB case': ['RGB'],
            'tempered glass case': ['tempered-glass'],
            'dual chamber case': ['dual-chamber'],
            'airflow case': ['airflow'],
            'compact case': ['compact', 'ITX'],
            'mini itx case': ['ITX', 'compact'],
        }

        # Score all cases
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Part).where(Part.category == PartCategory.case)
            )
            cases = result.scalars().all()

            scored = 0
            for case in cases:
                score = 50  # Base score

                # Add trend-based scores
                for trend_key, bonus_keywords in trend_to_keyword_bonus.items():
                    trend_value = latest_trends.get(trend_key, 0)
                    if trend_value > 0:
                        # Check if case has any of these bonus keywords
                        case_keywords = case.keywords or []
                        if any(k in case_keywords for k in bonus_keywords):
                            score += (trend_value / 100) * 15  # Max +15 per matching trend

                # Add keyword multipliers
                if case.keywords:
                    keyword_bonus = 0
                    for keyword in case.keywords:
                        keyword_bonus += keyword_multipliers.get(keyword, 0.5)
                    score += min(20, keyword_bonus * 2)  # Cap at +20 from keywords

                # Form factor trendiness
                if case.form_factors:
                    # ITX cases are trendy right now
                    if any(f in case.form_factors for f in ['ITX', 'MINI_ITX']):
                        score += 5
                    # EATX is niche
                    if 'EATX' in case.form_factors:
                        score -= 3

                # Cap at 100
                score = min(100, max(0, score))

                # Update case with score
                await db.execute(
                    update(Part)
                    .where(Part.id == case.id)
                    .values(demand_score=score)
                )
                scored += 1

            await db.commit()

        log.info("case_demand.scoring_complete", scored=scored)
        return {"scored": scored, "error": None}

    except Exception as exc:
        log.error("case_demand.error", error=str(exc))
        return {"scored": 0, "error": str(exc)}
