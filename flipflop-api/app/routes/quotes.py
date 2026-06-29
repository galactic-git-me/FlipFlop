"""Quote generation endpoints for PC build recommendations."""
import structlog
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.quote import QuoteRequest, QuoteResponse, BudgetTiersResponse, BudgetTier
from app.services.quote_service import QuoteService

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.post("/generate", response_model=QuoteResponse, status_code=200)
async def generate_quote(
    request: QuoteRequest,
    db: AsyncSession = Depends(get_db),
) -> QuoteResponse:
    """
    Generate a PC build quote for a given budget.

    **Request:**
    - `budget`: Customer budget in GBP (800-3000)

    **Response:**
    - Complete quote with component recommendations and pricing breakdown
    - All prices in GBP
    - Includes parts cost, labor cost (3.5 hours @ £25/hr), and overhead (10%)

    **Example:**
    ```
    POST /api/quotes/generate
    {
        "budget": 1200
    }

    Response:
    {
        "budget": 1200,
        "tier_name": "Mid-Range Gaming",
        "recommended_specs": {...},
        "components": [...],
        "parts_cost_total": 850.50,
        "labor_cost": 87.50,
        "overhead_cost": 93.80,
        "subtotal": 938.00,
        "total_price": 1031.80,
        "estimated_build_days": 7,
        "budget_remaining": 168.20,
        "within_budget": true
    }
    ```
    """
    log.info("Generating quote", budget=request.budget)

    # Validate budget is in acceptable range
    if request.budget < 800 or request.budget > 3000:
        raise HTTPException(
            status_code=400,
            detail="Budget must be between £800 and £3000",
        )

    # Generate quote
    quote = await QuoteService.generate_quote(request.budget, db)

    if quote is None:
        raise HTTPException(
            status_code=400,
            detail="Unable to generate quote for this budget. Please try a budget between £800 and £3000.",
        )

    log.info(
        "Quote generated successfully",
        budget=request.budget,
        total_price=quote["total_price"],
        within_budget=quote["within_budget"],
    )

    return QuoteResponse(**quote)


@router.get("/budgets", response_model=BudgetTiersResponse, status_code=200)
async def get_budget_tiers() -> BudgetTiersResponse:
    """
    Get all available budget tiers and their recommended specs.

    **Response:**
    - List of budget tiers (£800, £1200, £1500, £2000, £3000)
    - Each tier includes recommended CPU, GPU, RAM, SSD, etc.
    - Useful for customers to understand pricing options

    **Example:**
    ```
    GET /api/quotes/budgets

    Response:
    {
        "tiers": [
            {
                "budget": 800,
                "name": "Budget Gaming",
                "specs": {
                    "cpu": "Ryzen 5 5600X",
                    "gpu": "RTX 3060",
                    ...
                }
            },
            ...
        ],
        "min_budget": 800,
        "max_budget": 3000
    }
    ```
    """
    log.info("Retrieving budget tiers")

    tiers_dict = QuoteService.get_budget_tiers()

    # Convert to response format
    tiers = [
        BudgetTier(
            budget=budget,
            name=specs.get("name", "Unknown"),
            specs={k: v for k, v in specs.items() if k != "name"},
        )
        for budget, specs in sorted(tiers_dict.items())
    ]

    return BudgetTiersResponse(
        tiers=tiers,
        min_budget=min(tiers_dict.keys()),
        max_budget=max(tiers_dict.keys()),
    )
