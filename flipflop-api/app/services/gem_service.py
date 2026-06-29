"""
GemRecommendationService

LLM-powered recommendation engine for speculative PC builds ("gems").
Analyzes demand trends, market conditions, and component availability to recommend
builds that should be built speculatively and held in inventory.

The service:
1. Fetches and analyzes order data from the last 30 days
2. Identifies demand patterns (popular budgets, use cases, components)
3. Fetches current market prices for components
4. Calls Claude API to analyze demand + market and generate build recommendations
5. Calculates actual profit margins and risk assessments
6. Stores recommendations in the database for admin review
"""

import json
import structlog
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from anthropic import Anthropic

from app.models.gem import GemBuild, GemRiskLevel
from app.models.order import Order, OrderStatus

log = structlog.get_logger(__name__)


class GemRecommendationService:
    """
    LLM-powered gem build recommendation service.

    Uses Claude to analyze demand patterns and generate speculative inventory recommendations.
    """

    def __init__(self, db: AsyncSession, anthropic_api_key: Optional[str] = None):
        """
        Initialize the service.

        Args:
            db: AsyncSession for database operations
            anthropic_api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        """
        self.db = db
        self.client = Anthropic(api_key=anthropic_api_key) if anthropic_api_key else Anthropic()

    async def generate_recommendations(self, analysis_days: int = 30) -> Dict[str, Any]:
        """
        Generate gem build recommendations using Claude API.

        Process:
        1. Analyze demand from recent orders
        2. Fetch market prices for components
        3. Call Claude to generate recommendations
        4. Calculate margins and risk
        5. Store in database

        Args:
            analysis_days: Number of days of order history to analyze (default: 30)

        Returns:
            Dict with analysis results and recommendations
        """
        try:
            log.info("Starting gem recommendation generation", analysis_days=analysis_days)

            # 1. Analyze demand from recent orders
            demand_analysis = await self._analyze_demand(analysis_days)
            log.info("Demand analysis complete", demand_analysis=demand_analysis)

            # 2. Get market prices for components
            market_prices = self._get_market_prices()
            log.info("Market prices fetched", component_count=len(market_prices))

            # 3. Call Claude with analysis
            recommendations = await self._call_claude_for_recommendations(
                demand_analysis, market_prices, analysis_days
            )
            log.info("Claude generated recommendations", count=len(recommendations))

            # 4. Enrich recommendations with financial analysis
            for rec in recommendations:
                self._enrich_recommendation_financial(rec, market_prices)

            # 5. Store in database
            stored_recs = []
            for rec in recommendations:
                gem = await self._store_recommendation(rec, analysis_days)
                stored_recs.append(gem)
                log.info("Recommendation stored", gem_id=gem.id, gem_name=gem.name)

            return {
                "status": "success",
                "generated_at": datetime.utcnow().isoformat(),
                "analysis_period_days": analysis_days,
                "total_orders_analyzed": demand_analysis.get("total_orders", 0),
                "demand_summary": {
                    "budget_distribution": demand_analysis.get("budget_distribution", {}),
                    "popular_use_cases": demand_analysis.get("use_cases", {}),
                    "top_component_combinations": demand_analysis.get("popular_combos", {}),
                    "insights": demand_analysis.get("insights", {}),
                },
                "recommendations": [gem.to_dict() for gem in stored_recs],
            }

        except Exception as e:
            log.error("Error generating recommendations", error=str(e), exc_info=True)
            raise

    async def _analyze_demand(self, days: int) -> Dict[str, Any]:
        """
        Analyze demand patterns from recent orders.

        Examines:
        - Budget tier distribution (how many £500-£1000, £1000-£1500, etc.)
        - Popular use cases (gaming, workstation, streaming, office)
        - Popular component combinations (GPU + CPU pairings)
        - Market gaps (underserved budget/use case combos)

        Args:
            days: Number of days to look back

        Returns:
            Dict with demand analysis
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Fetch completed/confirmed orders from the period
            stmt = select(Order).where(
                Order.created_at >= cutoff_date,
                Order.status.in_([OrderStatus.COMPLETED, OrderStatus.READY_TO_SHIP, OrderStatus.SHIPPED])
            )
            result = await self.db.execute(stmt)
            orders = result.scalars().all()

            log.info("Fetched orders for analysis", order_count=len(orders), days=days)

            if not orders:
                return {
                    "total_orders": 0,
                    "budget_distribution": {},
                    "use_cases": {},
                    "popular_combos": {},
                    "insights": {
                        "note": "Insufficient order data to analyze"
                    }
                }

            # Group by budget tier
            budget_buckets = {}
            use_cases = {}
            popular_combos = {}
            all_budgets = []

            for order in orders:
                try:
                    # Budget tier
                    price = order.customer_price or 0
                    bucket = self._get_budget_bucket(price)
                    budget_buckets[bucket] = budget_buckets.get(bucket, 0) + 1
                    all_budgets.append(price)

                    # Use case (from specs or placeholder)
                    specs = order.specs or {}
                    uc = specs.get("use_case", "unknown")
                    use_cases[uc] = use_cases.get(uc, 0) + 1

                    # Component combinations
                    cpu = specs.get("cpu", "Unknown")
                    gpu = specs.get("gpu", "Unknown")
                    if cpu and gpu:
                        combo_key = f"{gpu} + {cpu}"
                        popular_combos[combo_key] = popular_combos.get(combo_key, 0) + 1

                except Exception as e:
                    log.warning("Error processing order", order_id=order.id, error=str(e))
                    continue

            # Calculate insights
            avg_budget = sum(all_budgets) / len(all_budgets) if all_budgets else 0
            median_budget = sorted(all_budgets)[len(all_budgets) // 2] if all_budgets else 0

            # Find most popular combo
            most_popular_combo = max(popular_combos.items(), key=lambda x: x[1])[0] if popular_combos else "N/A"

            return {
                "total_orders": len(orders),
                "budget_distribution": budget_buckets,
                "use_cases": use_cases,
                "popular_combos": popular_combos,
                "insights": {
                    "avg_budget_gbp": round(avg_budget, 2),
                    "median_budget_gbp": round(median_budget, 2),
                    "most_popular_use_case": max(use_cases.items(), key=lambda x: x[1])[0] if use_cases else "unknown",
                    "most_popular_combo": most_popular_combo,
                    "total_unique_use_cases": len(use_cases),
                    "total_unique_combos": len(popular_combos),
                }
            }

        except Exception as e:
            log.error("Error analyzing demand", error=str(e), exc_info=True)
            raise

    @staticmethod
    def _get_budget_bucket(price: float) -> str:
        """Bucket a price into a budget tier."""
        if price < 500:
            return "£0-500"
        elif price < 800:
            return "£500-800"
        elif price < 1000:
            return "£800-1000"
        elif price < 1200:
            return "£1000-1200"
        elif price < 1500:
            return "£1200-1500"
        elif price < 2000:
            return "£1500-2000"
        else:
            return "£2000+"

    @staticmethod
    def _get_market_prices() -> Dict[str, Dict[str, float]]:
        """
        Fetch current component market prices.

        In production, this would integrate with real supplier APIs (eBay, Amazon, etc.).
        For now, returns reasonable UK market prices as of June 2026.

        Returns:
            Dict with component categories and current prices in GBP
        """
        return {
            "CPUs": {
                "Intel i9-14900K": 589,
                "Intel i7-14700K": 399,
                "Intel i5-14600K": 249,
                "AMD Ryzen 9 7950X": 549,
                "AMD Ryzen 7 7700X": 329,
                "AMD Ryzen 5 5600X": 189,
            },
            "GPUs": {
                "RTX 4090": 1399,
                "RTX 4080": 899,
                "RTX 4070 Super": 569,
                "RTX 4070": 499,
                "RTX 4060 Ti": 349,
                "RTX 4060": 249,
                "RX 7900 XTX": 699,
                "RX 7900 XT": 549,
            },
            "RAM": {
                "DDR5 32GB": 120,
                "DDR5 16GB": 70,
                "DDR4 32GB": 80,
                "DDR4 16GB": 50,
            },
            "Storage": {
                "1TB NVMe Gen4": 79,
                "2TB NVMe Gen4": 119,
                "1TB NVMe Gen5": 89,
                "2TB NVMe Gen5": 149,
            },
            "PSU": {
                "Corsair RM1000e": 149,
                "Corsair RM850e": 119,
                "Corsair RM750e": 99,
                "EVGA G6 850W": 89,
                "EVGA G6 750W": 79,
            },
            "Cases": {
                "Fractal Design Torrent": 189,
                "Corsair Crystal": 129,
                "NZXT H7": 99,
                "Lian Li Lancool": 79,
            },
            "Coolers": {
                "NZXT Kraken X73": 199,
                "Corsair H150i": 189,
                "Be Quiet Dark Rock": 69,
            },
            "Motherboards": {
                "ASUS ROG Strix Z890": 379,
                "MSI MPG Z890": 349,
                "ASUS TUF Z890": 299,
            },
        }

    async def _call_claude_for_recommendations(
        self,
        demand_analysis: Dict[str, Any],
        market_prices: Dict[str, Dict[str, float]],
        analysis_days: int,
    ) -> List[Dict[str, Any]]:
        """
        Call Claude API to analyze demand and generate gem recommendations.

        Claude receives:
        - Demand patterns from the last N days
        - Current market prices
        - FlipFlop business context

        Claude generates:
        - 3-5 specific build recommendations
        - Each with full spec, cost, market price, and reasoning

        Args:
            demand_analysis: Results from _analyze_demand()
            market_prices: Current component prices
            analysis_days: Number of days analyzed

        Returns:
            List of recommendations as dicts (not yet enriched with DB values)
        """
        try:
            # Build the analysis prompt
            analysis_prompt = f"""
You are a market analyst for FlipFlop, a UK-based made-to-order PC building business.

ANALYZE THIS PC MARKET DATA AND GENERATE 3-5 SPECIFIC "GEM BUILD" RECOMMENDATIONS

Your job: recommend speculative inventory builds that are likely to:
1. Sell quickly (based on real recent demand)
2. Generate strong profit margins (20%+ preferred)
3. Address market gaps or trending demand patterns
4. Minimize inventory risk through high confidence scores

RECENT DEMAND DATA (Last {analysis_days} days):
{json.dumps(demand_analysis, indent=2)}

CURRENT MARKET PRICES (UK suppliers):
{json.dumps(market_prices, indent=2)}

FLIPFLOP CONTEXT:
- Made-to-order is primary revenue
- Speculative gems fund cash flow and reduce risk by selling pre-built stock
- High-demand builds (80%+ confidence) recommended
- Target 20-30% profit margins on gems
- Build 1-3 units per gem based on confidence

PROVIDE OUTPUT AS VALID JSON ONLY (no markdown, no explanation):

{{
  "recommendations": [
    {{
      "name": "Build Name (e.g., '1440p Gaming Beast')",
      "use_case": "gaming/workstation/streaming/office/hybrid",
      "target_budget_gbp": 1200,
      "specs": {{
        "cpu": "Exact model name",
        "gpu": "Exact model name",
        "ram_gb": 32,
        "ram_type": "DDR5",
        "ssd_gb": 1000,
        "psu_watts": 850,
        "case": "Case name/style",
        "cooler": "Cooler model or 'Stock'",
        "motherboard": "Motherboard model"
      }},
      "estimated_cost_gbp": 850,
      "estimated_market_price_gbp": 1200,
      "confidence_score": 85,
      "risk_level": "low",
      "recommended_quantity": 2,
      "reasoning": "Brief explanation of why to build this now based on demand"
    }},
    ...
  ]
}}

IMPORTANT:
- Use real products from the market prices provided above
- Be specific with model numbers
- Cost estimate should be sum of components + labor
- Market price should be what UK customers currently pay for similar
- Confidence score 0-100: >80 = high confidence, 60-80 = medium, <60 = low
- Risk level: "low" for high confidence, "medium" for 60-80%, "high" for speculative
- Keep reasoning to 1-2 sentences, specific to demand data
- Ensure JSON is valid (no trailing commas, proper quotes)
""".strip()

            log.info("Calling Claude API for recommendations")

            # Call Claude
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ]
            )

            response_text = message.content[0].text
            log.info("Received Claude response", response_length=len(response_text))

            # Extract JSON from response (Claude may include markdown fencing)
            json_str = response_text
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(json_str)
            recommendations = parsed.get("recommendations", [])

            log.info("Parsed recommendations from Claude", count=len(recommendations))
            return recommendations

        except json.JSONDecodeError as e:
            log.error("Failed to parse Claude JSON response", error=str(e))
            raise ValueError(f"Invalid JSON from Claude: {str(e)}")
        except Exception as e:
            log.error("Error calling Claude API", error=str(e), exc_info=True)
            raise

    def _enrich_recommendation_financial(
        self,
        rec: Dict[str, Any],
        market_prices: Dict[str, Dict[str, float]],
    ) -> None:
        """
        Enrich a recommendation with detailed financial analysis.

        Calculates:
        - Actual component costs based on market prices
        - Total cost including labor and overhead
        - Actual profit and margin
        - Cost breakdown for transparency

        Modifies rec in place.

        Args:
            rec: Recommendation dict from Claude
            market_prices: Current market prices
        """
        try:
            specs = rec.get("specs", {})

            # Calculate component costs from market prices
            cost_breakdown = {
                "cpu": self._find_component_price(specs.get("cpu"), market_prices.get("CPUs", {})),
                "gpu": self._find_component_price(specs.get("gpu"), market_prices.get("GPUs", {})),
                "motherboard": self._find_component_price(
                    specs.get("motherboard"),
                    market_prices.get("Motherboards", {})
                ),
                "ram": self._estimate_ram_cost(specs.get("ram_gb"), specs.get("ram_type", "DDR5"), market_prices),
                "ssd": self._estimate_ssd_cost(specs.get("ssd_gb"), market_prices),
                "psu": self._find_component_price(specs.get("psu_watts"), market_prices.get("PSU", {})),
                "case": self._find_component_price(specs.get("case"), market_prices.get("Cases", {})),
                "cooler": self._find_component_price(specs.get("cooler"), market_prices.get("Coolers", {})),
            }

            # Filter out zeros and calculate totals
            actual_costs = {k: v for k, v in cost_breakdown.items() if v > 0}
            component_total = sum(actual_costs.values())

            # Add labor and overhead (standard rates)
            labor_hours = 3.0
            labor_rate = 25.0  # £25/hour
            labor_cost = labor_hours * labor_rate

            overhead_rate = 0.10  # 10% of component costs
            overhead = component_total * overhead_rate

            total_cost = component_total + labor_cost + overhead

            # Calculate profit
            market_price = rec.get("estimated_market_price_gbp", 1000)
            profit = market_price - total_cost
            margin_pct = (profit / market_price * 100) if market_price > 0 else 0

            # Update recommendation with actual financials
            rec["actual_cost_to_build"] = round(total_cost, 2)
            rec["actual_margin_gbp"] = round(profit, 2)
            rec["actual_margin_percent"] = round(margin_pct, 1)
            rec["cost_breakdown"] = {k: round(v, 2) for k, v in actual_costs.items()}
            rec["labor_cost"] = round(labor_cost, 2)
            rec["overhead_cost"] = round(overhead, 2)

            log.info(
                "Enriched recommendation with financials",
                name=rec.get("name"),
                actual_cost=rec["actual_cost_to_build"],
                profit=rec["actual_margin_gbp"],
                margin_pct=rec["actual_margin_percent"]
            )

        except Exception as e:
            log.error("Error enriching recommendation", error=str(e), exc_info=True)
            # Fall back to Claude's estimates
            rec["actual_cost_to_build"] = rec.get("estimated_cost_gbp", 0)
            rec["actual_margin_gbp"] = rec.get("estimated_market_price_gbp", 0) - rec.get("estimated_cost_gbp", 0)
            rec["actual_margin_percent"] = 0

    @staticmethod
    def _find_component_price(component_name: Optional[str], price_dict: Dict[str, float]) -> float:
        """
        Find a component price by trying substring matching.

        Args:
            component_name: Component name to search for
            price_dict: Dictionary of {component: price}

        Returns:
            Price in GBP, or 0 if not found
        """
        if not component_name or not price_dict:
            return 0.0

        component_name = component_name.strip().lower()

        # Try exact match first
        for name, price in price_dict.items():
            if name.lower() == component_name:
                return float(price)

        # Try substring match
        for name, price in price_dict.items():
            if name.lower() in component_name or component_name in name.lower():
                return float(price)

        return 0.0

    @staticmethod
    def _estimate_ram_cost(ram_gb: Optional[int], ram_type: str, market_prices: Dict) -> float:
        """Estimate RAM cost based on capacity and type."""
        if not ram_gb:
            return 0.0

        ram_prices = market_prices.get("RAM", {})

        # Determine closest capacity
        if ram_gb >= 32:
            key = f"{ram_type} 32GB"
        elif ram_gb >= 16:
            key = f"{ram_type} 16GB"
        else:
            key = f"{ram_type} 16GB"

        return float(ram_prices.get(key, 100.0))

    @staticmethod
    def _estimate_ssd_cost(ssd_gb: Optional[int], market_prices: Dict) -> float:
        """Estimate SSD cost based on capacity."""
        if not ssd_gb:
            return 0.0

        ssd_prices = market_prices.get("Storage", {})

        # Prefer Gen5 if available
        if ssd_gb >= 2000:
            return float(ssd_prices.get("2TB NVMe Gen5", 149.0))
        elif ssd_gb >= 1000:
            return float(ssd_prices.get("1TB NVMe Gen5", 89.0))
        else:
            return float(ssd_prices.get("1TB NVMe Gen4", 79.0))

    async def _store_recommendation(self, rec: Dict[str, Any], analysis_days: int) -> GemBuild:
        """
        Store a recommendation in the database.

        Args:
            rec: Recommendation dict from Claude (enriched with financials)
            analysis_days: Number of days analyzed

        Returns:
            Created GemBuild model instance
        """
        try:
            # Determine risk level based on confidence
            confidence = rec.get("confidence_score", 50)
            if confidence >= 80:
                risk_level = GemRiskLevel.LOW
            elif confidence >= 60:
                risk_level = GemRiskLevel.MEDIUM
            else:
                risk_level = GemRiskLevel.HIGH

            gem = GemBuild(
                name=rec.get("name", "Unknown Gem"),
                use_case=rec.get("use_case", "gaming"),
                target_budget_gbp=float(rec.get("target_budget_gbp", 1000)),
                specs=rec.get("specs", {}),
                estimated_cost_to_build=float(rec.get("actual_cost_to_build", rec.get("estimated_cost_gbp", 0))),
                estimated_market_price=float(rec.get("estimated_market_price_gbp", 1000)),
                margin_gbp=float(rec.get("actual_margin_gbp", 0)),
                margin_percent=float(rec.get("actual_margin_percent", 0)),
                confidence_score=int(rec.get("confidence_score", 50)),
                risk_level=risk_level,
                recommended_quantity=int(rec.get("recommended_quantity", 1)),
                reasoning=rec.get("reasoning", "Recommended by LLM analysis"),
                cost_breakdown=rec.get("cost_breakdown", {}),
                analysis_period_days=analysis_days,
            )

            self.db.add(gem)
            await self.db.flush()  # Get the ID without committing
            await self.db.refresh(gem)

            log.info("Stored recommendation", gem_id=gem.id, gem_name=gem.name)
            return gem

        except Exception as e:
            log.error("Error storing recommendation", error=str(e), exc_info=True)
            raise

    async def get_recommendation_by_id(self, gem_id: int) -> Optional[GemBuild]:
        """Fetch a single recommendation by ID."""
        stmt = select(GemBuild).where(GemBuild.id == gem_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recommendations(
        self,
        risk_level: Optional[str] = None,
        use_case: Optional[str] = None,
        limit: int = 20,
    ) -> List[GemBuild]:
        """
        List recommendations with optional filtering.

        Args:
            risk_level: Filter by risk level (low, medium, high)
            use_case: Filter by use case
            limit: Maximum results

        Returns:
            List of GemBuild models
        """
        stmt = select(GemBuild)

        if risk_level:
            stmt = stmt.where(GemBuild.risk_level == GemRiskLevel(risk_level))

        if use_case:
            stmt = stmt.where(GemBuild.use_case == use_case)

        stmt = stmt.order_by(GemBuild.generated_at.desc()).limit(limit)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete_recommendation(self, gem_id: int) -> bool:
        """Delete a recommendation."""
        gem = await self.get_recommendation_by_id(gem_id)
        if not gem:
            return False

        await self.db.delete(gem)
        return True
