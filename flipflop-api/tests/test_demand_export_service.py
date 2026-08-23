"""Tests for Demand Export Service (Phase 3, F3.1.2).

Verifies CSV export and audit logging.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ManualBuild, DemandMetricsSnapshot, DemandExportAudit
from app.services.demand_export_service import DemandExportService
from app.services.feature_flags import set_flag_for_testing


@pytest.mark.asyncio
class TestExportCSV:
    """Test CSV export."""

    async def test_export_single_build(self, db: AsyncSession):
        """Export single build to CSV."""
        set_flag_for_testing("FEATURE_DEMAND_INTEL_EXPORTS", True)

        build = ManualBuild(name="Test Build", ebay_price=99.99)
        db.add(build)
        await db.commit()

        metrics = DemandMetricsSnapshot(
            manual_build_id=build.id,
            view_count=100,
            conversion_count=10,
            view_to_conversion_rate=0.1,
        )
        db.add(metrics)
        await db.commit()

        csv = await DemandExportService.export_builds_to_csv(db, [build.id])

        assert "Build ID" in csv
        assert "Test Build" in csv
        assert "99.99" in csv

        set_flag_for_testing("FEATURE_DEMAND_INTEL_EXPORTS", False)

    async def test_export_multiple_builds(self, db: AsyncSession):
        """Export multiple builds."""
        set_flag_for_testing("FEATURE_DEMAND_INTEL_EXPORTS", True)

        builds = []
        for i in range(3):
            build = ManualBuild(name=f"Build {i}", ebay_price=100.0 + i)
            db.add(build)
            builds.append(build)
        await db.commit()

        csv = await DemandExportService.export_builds_to_csv(db, [b.id for b in builds])

        # Should have header + 3 rows
        lines = csv.strip().split('\n')
        assert len(lines) >= 4

        set_flag_for_testing("FEATURE_DEMAND_INTEL_EXPORTS", False)

    async def test_csv_format(self, db: AsyncSession):
        """Verify CSV format."""
        set_flag_for_testing("FEATURE_DEMAND_INTEL_EXPORTS", True)

        build = ManualBuild(name="Format Test", ebay_price=99.99)
        db.add(build)
        await db.commit()

        csv = await DemandExportService.export_builds_to_csv(db, [build.id])

        # Should have expected headers
        assert "Build ID" in csv
        assert "Build Name" in csv
        assert "Price" in csv
        assert "Views" in csv
        assert "Conversions" in csv

        set_flag_for_testing("FEATURE_DEMAND_INTEL_EXPORTS", False)

    async def test_export_flag_disabled(self, db: AsyncSession):
        """Export disabled by flag."""
        set_flag_for_testing("FEATURE_DEMAND_INTEL_EXPORTS", False)

        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        csv = await DemandExportService.export_builds_to_csv(db, [build.id])

        assert csv == ""


@pytest.mark.asyncio
class TestExportAudit:
    """Test export audit trail."""

    async def test_export_creates_audit(self, db: AsyncSession):
        """Export creates audit entry."""
        set_flag_for_testing("FEATURE_DEMAND_INTEL_EXPORTS", True)

        build = ManualBuild(name="Audit Test")
        db.add(build)
        await db.commit()

        await DemandExportService.export_builds_to_csv(db, [build.id])

        # Check audit was logged
        from sqlalchemy import select
        stmt = select(DemandExportAudit).order_by(
            DemandExportAudit.exported_at.desc()
        )
        result = await db.execute(stmt)
        audits = result.scalars().all()

        assert len(audits) > 0
        latest = audits[0]
        assert latest.row_count == 1

        set_flag_for_testing("FEATURE_DEMAND_INTEL_EXPORTS", False)

    async def test_get_export_history(self, db: AsyncSession):
        """Query export history."""
        set_flag_for_testing("FEATURE_DEMAND_INTEL_EXPORTS", True)

        build = ManualBuild(name="History")
        db.add(build)
        await db.commit()

        # Create multiple exports
        for _ in range(3):
            await DemandExportService.export_builds_to_csv(db, [build.id])

        history = await DemandExportService.get_export_history(db, limit=10)

        assert len(history) >= 3

        set_flag_for_testing("FEATURE_DEMAND_INTEL_EXPORTS", False)
