"""Demand Export Service for Phase 3 F3.1.2.

Exports demand metrics to CSV with audit trail.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from io import StringIO
import csv
from app.models import ManualBuild, DemandMetricsSnapshot, DemandExportAudit
from app.services.feature_flags import is_enabled, FeatureFlags
import structlog

log = structlog.get_logger(__name__)


class DemandExportService:
    """Exports demand metrics to CSV."""

    @staticmethod
    async def export_builds_to_csv(
        db: AsyncSession,
        build_ids: list[int],
        include_metrics: bool = True,
        include_trends: bool = True,
    ) -> str:
        """Export demand metrics to CSV."""
        if not is_enabled(FeatureFlags.DEMAND_INTEL_EXPORTS):
            log.warning("export_builds_to_csv_exports_disabled")
            return ""

        try:
            output = StringIO()
            writer = csv.writer(output)

            # Write header
            headers = ["Build ID", "Build Name", "Price"]
            if include_metrics:
                headers.extend(
                    [
                        "Views",
                        "Conversions",
                        "Conversion Rate",
                        "Sell-Through %",
                    ]
                )
            if include_trends:
                headers.extend(["Trend", "Volatility"])

            writer.writerow(headers)

            # Query builds and metrics
            for build_id in build_ids:
                build = await db.get(ManualBuild, build_id)
                if not build:
                    continue

                # Get latest metrics
                stmt = select(DemandMetricsSnapshot).where(
                    DemandMetricsSnapshot.manual_build_id == build_id,
                ).order_by(DemandMetricsSnapshot.recorded_at.desc())

                result = await db.execute(stmt)
                metrics = result.scalars().first()

                # Write row
                row = [build_id, build.name, build.ebay_price or 0]

                if include_metrics and metrics:
                    row.extend(
                        [
                            metrics.view_count or 0,
                            metrics.conversion_count or 0,
                            f"{(metrics.view_to_conversion_rate or 0)*100:.1f}%",
                            f"{(metrics.sell_through_rate or 0)*100:.1f}%",
                        ]
                    )
                elif include_metrics:
                    row.extend([0, 0, "0.0%", "0.0%"])

                if include_trends and metrics:
                    row.extend(
                        [
                            metrics.demand_trend or "unknown",
                            f"{(metrics.volatility_score or 0)*100:.1f}",
                        ]
                    )
                elif include_trends:
                    row.extend(["unknown", "0.0"])

                writer.writerow(row)

            csv_content = output.getvalue()

            # Log audit trail
            audit = DemandExportAudit(
                export_type="builds",
                filter_params={"build_ids": build_ids},
                row_count=len(build_ids),
            )
            db.add(audit)
            await db.commit()

            log.info(
                "demand_export_completed",
                export_type="builds",
                row_count=len(build_ids),
            )

            return csv_content

        except Exception as e:
            log.error(
                "export_builds_to_csv_failed",
                build_ids=build_ids,
                error=str(e),
            )
            await db.rollback()
            return ""

    @staticmethod
    async def export_all_builds_csv(
        db: AsyncSession,
        status_filter: str | None = None,
    ) -> str:
        """Export metrics for all builds (or filtered)."""
        try:
            # Query builds
            stmt = select(ManualBuild)
            if status_filter:
                stmt = stmt.where(ManualBuild.status == status_filter)

            result = await db.execute(stmt)
            builds = result.scalars().all()

            build_ids = [b.id for b in builds]
            return await DemandExportService.export_builds_to_csv(db, build_ids)

        except Exception as e:
            log.error(
                "export_all_builds_csv_failed",
                status_filter=status_filter,
                error=str(e),
            )
            return ""

    @staticmethod
    async def get_export_history(
        db: AsyncSession,
        limit: int = 100,
    ) -> list[DemandExportAudit]:
        """Get audit trail of exports."""
        try:
            stmt = select(DemandExportAudit).order_by(
                DemandExportAudit.exported_at.desc()
            ).limit(limit)

            result = await db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            log.error(
                "get_export_history_failed",
                limit=limit,
                error=str(e),
            )
            return []
