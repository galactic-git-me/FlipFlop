"""Restore production foreign keys and checks that were absent from DEV."""

from alembic import op
import sqlalchemy as sa


revision = "20261103_0002"
down_revision = "20261103_0001"
branch_labels = None
depends_on = None


def _add_check_if_missing(bind, table, name, expression):
    existing = {item["name"] for item in sa.inspect(bind).get_check_constraints(table, schema="public")}
    if name not in existing:
        op.create_check_constraint(name, table, expression, schema="public")


def _add_fk_if_missing(bind, table, name, columns, referred_table, referred_columns):
    existing = {item["name"] for item in sa.inspect(bind).get_foreign_keys(table, schema="public")}
    if name not in existing:
        op.create_foreign_key(
            name,
            table,
            referred_table,
            columns,
            referred_columns,
            source_schema="public",
            referent_schema="public",
        )


def _add_index_if_missing(bind, table, name, columns):
    existing = {item["name"] for item in sa.inspect(bind).get_indexes(table, schema="public")}
    if name not in existing:
        op.create_index(name, table, columns, schema="public")


def _require_no_rows(bind, name, statement):
    count = bind.execute(sa.text(statement)).scalar_one()
    if count:
        raise RuntimeError(
            f"Cannot install {name}: {count} existing row(s) violate the production constraint"
        )


def upgrade():
    bind = op.get_bind()
    checks = {
        item["name"]
        for item in sa.inspect(bind).get_check_constraints(
            "customer_problems", schema="public"
        )
    }
    if "ck_customer_problem_one_source" not in checks:
        _require_no_rows(
            bind,
            "ck_customer_problem_one_source",
            "SELECT count(*) FROM public.customer_problems WHERE NOT "
            "((order_id IS NOT NULL AND manual_build_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NOT NULL))",
        )
    if "ck_customer_problem_repair_tracking_provider_reference" not in checks:
        _require_no_rows(
            bind,
            "ck_customer_problem_repair_tracking_provider_reference",
            "SELECT count(*) FROM public.customer_problems WHERE NOT "
            "((repair_tracking_provider IS NULL AND repair_tracking_provider_reference IS NULL) OR "
            "(repair_tracking_provider = 'parcel2go' AND repair_tracking_provider_reference IS NOT NULL))",
        )
    existing_fks = {
        item["name"]
        for item in sa.inspect(bind).get_foreign_keys(
            "customer_problems", schema="public"
        )
    }
    if "customer_problems_manual_build_id_fkey" not in existing_fks:
        _require_no_rows(
            bind,
            "customer_problems_manual_build_id_fkey",
            "SELECT count(*) FROM public.customer_problems cp "
            "LEFT JOIN public.manual_builds mb ON mb.id = cp.manual_build_id "
            "WHERE cp.manual_build_id IS NOT NULL AND mb.id IS NULL",
        )
    if "customer_problems_portal_grant_id_fkey" not in existing_fks:
        _require_no_rows(
            bind,
            "customer_problems_portal_grant_id_fkey",
            "SELECT count(*) FROM public.customer_problems cp "
            "LEFT JOIN public.portal_access_grants pg ON pg.id = cp.portal_grant_id "
            "WHERE cp.portal_grant_id IS NOT NULL AND pg.id IS NULL",
        )
    _add_check_if_missing(
        bind,
        "customer_problems",
        "ck_customer_problem_one_source",
        "(order_id IS NOT NULL AND manual_build_id IS NULL) OR "
        "(order_id IS NULL AND manual_build_id IS NOT NULL)",
    )
    _add_check_if_missing(
        bind,
        "customer_problems",
        "ck_customer_problem_repair_tracking_provider_reference",
        "(repair_tracking_provider IS NULL AND repair_tracking_provider_reference IS NULL) OR "
        "(repair_tracking_provider = 'parcel2go' AND repair_tracking_provider_reference IS NOT NULL)",
    )
    _add_fk_if_missing(
        bind,
        "customer_problems",
        "customer_problems_manual_build_id_fkey",
        ["manual_build_id"],
        "manual_builds",
        ["id"],
    )
    _add_fk_if_missing(
        bind,
        "customer_problems",
        "customer_problems_portal_grant_id_fkey",
        ["portal_grant_id"],
        "portal_access_grants",
        ["id"],
    )

    existing_unique = {
        item["name"] for item in sa.inspect(bind).get_unique_constraints("customer_problems", schema="public")
    }
    if "uq_customer_problem_repair_provider_reference" not in existing_unique:
        _require_no_rows(
            bind,
            "uq_customer_problem_repair_provider_reference",
            "SELECT count(*) FROM (SELECT repair_tracking_provider_reference "
            "FROM public.customer_problems WHERE repair_tracking_provider_reference IS NOT NULL "
            "GROUP BY repair_tracking_provider_reference HAVING count(*) > 1) duplicates",
        )
        op.create_unique_constraint(
            "uq_customer_problem_repair_provider_reference",
            "customer_problems",
            ["repair_tracking_provider_reference"],
            schema="public",
        )

    _add_index_if_missing(
        bind,
        "customer_problems",
        "ix_customer_problems_manual_build_id",
        ["manual_build_id"],
    )
    _add_index_if_missing(
        bind,
        "customer_problems",
        "ix_customer_problems_portal_grant_id",
        ["portal_grant_id"],
    )
    _add_index_if_missing(
        bind,
        "manual_builds",
        "ix_manual_builds_parcel2go_order_line_id",
        ["parcel2go_order_line_id"],
    )


def downgrade():
    raise RuntimeError(
        "Relationship constraints are forward-only; restore a verified DEV schema backup to roll back"
    )
