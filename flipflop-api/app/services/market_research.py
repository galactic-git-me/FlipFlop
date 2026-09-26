"""
Market price research service using LLM + eBay data.

Queries the database for comparable PC builds and uses Claude LLM to analyze
market pricing and suggest optimal price point.
"""
import json
import structlog
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.model_selection_service import model_selection_service

log = structlog.get_logger(__name__)


async def research_build_price(
    db: AsyncSession,
    playbook_name: str,
    specs: str,
) -> dict:
    """
    Research market price for a build using LLM + eBay data.

    Args:
        db: Database session
        playbook_name: Name of the playbook (e.g., "Gaming RTX 4070")
        specs: Component specs (e.g., "GPU: RTX 4070\nCPU: Ryzen 5 5500")

    Returns:
        {
            "suggested_price": 2500.00,
            "reasoning": "Based on 12 eBay comparables...",
            "sources_analyzed": 12
        }
    """
    try:
        from app.models.listing import Listing

        # Get recent sold comparables from the database
        # These are listings that have been analyzed and have resale estimates
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()

        result = await db.execute(
            select(
                Listing.title,
                Listing.price,
                Listing.estimated_resale,
                Listing.cpu,
                Listing.gpu,
                Listing.ram_gb,
                Listing.storage_gb,
                Listing.last_seen_at,
            )
            .where(
                Listing.estimated_resale.isnot(None),
                Listing.last_seen_at >= thirty_days_ago,
                Listing.status.in_(["active", "sold"]),
            )
            .order_by(Listing.last_seen_at.desc())
            .limit(50)
        )

        comparables = result.all()

        if not comparables:
            # Fallback: return conservative estimate
            return {
                "suggested_price": 2500.00,
                "reasoning": "No recent sold comparables found. Using conservative estimate. Please provide specific requirements for better pricing.",
                "sources_analyzed": 0,
            }

        # Format data for LLM analysis
        comp_data = [
            {
                "title": c[0],
                "listed_price": c[1],
                "estimated_resale": c[2],
                "cpu": c[3],
                "gpu": c[4],
                "ram": c[5],
                "storage": c[6],
                "date": c[7],
            }
            for c in comparables
        ]

        prompt = f"""You are a PC build pricing expert. Analyze these recent eBay comparable sales and suggest an optimal market price for a new custom build.

Build Type: {playbook_name}
Requested Specs:
{specs}

Recent Comparable Listings (last 30 days):
{json.dumps(comp_data, indent=2, default=str)}

Instructions:
1. Filter comparables to those with similar specs
2. Extract the estimated resale values (these are market prices)
3. Calculate the median/mean market price for similar builds
4. Consider current market trends
5. Suggest a price that is competitive and allows for £150+ profit margin

Respond in JSON format:
{{
  "suggested_price": <float>,
  "reasoning": "<explanation of your analysis and price suggestion>",
  "comparable_price_range": {{"min": <float>, "max": <float>}},
  "market_trend": "<stable/rising/falling>"
}}"""

        try:
            selected = await model_selection_service.complete(
                task="Build market price research", messages=[{"role": "user", "content": prompt}],
                max_tokens=500, json_mode=True,
            )
            response_text = selected.text
        except Exception as exc:
            log.warning("market_research.all_models_failed", error=str(exc))
            prices = [c[2] for c in comparables if c[2]]
            median_price = sorted(prices)[len(prices) // 2] if prices else 2500.0
            return {"suggested_price": float(median_price),
                    "reasoning": f"Based on {len(prices)} recent comparable sales (model service unavailable).",
                    "sources_analyzed": len(prices)}

        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            result_json = json.loads(response_text[json_start:json_end])
        except json.JSONDecodeError:
            # Fallback if the selected model doesn't return valid JSON
            result_json = {
                "suggested_price": 2500.00,
                "reasoning": response_text[:500],
                "comparable_price_range": {"min": 2300, "max": 2800},
                "market_trend": "stable",
            }

        return {
            "suggested_price": float(result_json.get("suggested_price", 2500.0)),
            "reasoning": result_json.get(
                "reasoning",
                "Based on market analysis of comparable builds",
            ),
            "sources_analyzed": len(comp_data),
        }

    except Exception as e:
        log.error("market_research.failed", error=str(e))
        raise
