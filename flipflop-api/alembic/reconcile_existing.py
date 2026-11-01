"""Explicit adoption of compatible DDL already created outside Alembic.

Never stamps revisions or ignores incompatible definitions.
"""
import sqlalchemy as sa


def install_reconciliation(context, *, empty_baseline=False):
    impl = context.impl
    connection = impl.connection
    original_table, original_column, original_index = impl.create_table, impl.add_column, impl.create_index
    original_add_constraint = impl.add_constraint

    def check_column(table_name, expected, actual):
        if context._compare_type(sa.Column(expected.name, actual["type"]), expected):
            raise RuntimeError(f"Cannot reconcile {table_name}.{expected.name}: incompatible type")
        if not expected.nullable and actual["nullable"]:
            if not empty_baseline:
                raise RuntimeError(f"Cannot reconcile {table_name}.{expected.name}: required NOT NULL constraint missing")
            impl.alter_column(
                table_name,
                expected.name,
                nullable=False,
                server_default=expected.server_default,
            )
            print(f"Restored NOT NULL constraint: {table_name}.{expected.name}")
        if expected.server_default is not None and actual.get("default") is None:
            # create_all may have used a Python-side default where the old
            # migration requires a database default. Restore it additively.
            impl.alter_column(table_name, expected.name, server_default=expected.server_default)
            print(f"Restored missing server default: {table_name}.{expected.name}")

    def create_table(table, **kwargs):
        inspector = sa.inspect(connection)
        if not inspector.has_table(table.name, schema=table.schema):
            return original_table(table, **kwargs)
        columns = {c["name"]: c for c in inspector.get_columns(table.name, schema=table.schema)}
        for expected in table.columns:
            if expected.name not in columns:
                raise RuntimeError(f"Cannot reconcile {table.name}: missing column {expected.name}")
            check_column(table.name, expected, columns[expected.name])
        expected_pk = [c.name for c in table.primary_key.columns]
        if expected_pk != inspector.get_pk_constraint(table.name, schema=table.schema)["constrained_columns"]:
            raise RuntimeError(f"Cannot reconcile {table.name}: incompatible primary key")
        for constraint in table.constraints:
            if isinstance(constraint, sa.UniqueConstraint):
                required = set(c.name for c in constraint.columns)
                actual = inspector.get_unique_constraints(table.name, schema=table.schema)
                actual += [i for i in inspector.get_indexes(table.name, schema=table.schema) if i["unique"]]
                if not any(set(c["column_names"]) == required for c in actual):
                    raise RuntimeError(f"Cannot reconcile {table.name}: unique constraint missing")
            elif isinstance(constraint, sa.ForeignKeyConstraint):
                required = [c.name for c in constraint.columns]
                targets = [e.target_fullname for e in constraint.elements]
                actual = inspector.get_foreign_keys(table.name, schema=table.schema)
                if not any(fk["constrained_columns"] == required and
                           [f'{fk["referred_table"]}.{c}' for c in fk["referred_columns"]] == targets for fk in actual):
                    raise RuntimeError(f"Cannot reconcile {table.name}: foreign key missing")
        print(f"Reconciled existing table: {table.name}")

    def add_column(table_name, column, schema=None, **kwargs):
        inspector = sa.inspect(connection)
        existing = {c["name"]: c for c in inspector.get_columns(table_name, schema=schema)}
        if column.name not in existing:
            return original_column(table_name, column, schema=schema, **kwargs)
        check_column(table_name, column, existing[column.name])
        print(f"Reconciled existing column: {table_name}.{column.name}")

    def create_index(index, **kwargs):
        existing = {i["name"]: i for i in sa.inspect(connection).get_indexes(index.table.name, schema=index.table.schema)}
        if index.name not in existing:
            return original_index(index, **kwargs)
        actual = existing[index.name]
        if actual["column_names"] != [c.name for c in index.columns] or bool(actual["unique"]) != bool(index.unique):
            raise RuntimeError(f"Cannot reconcile index {index.name}: incompatible definition")
        print(f"Reconciled existing index: {index.name}")

    def normalized_sql(value):
        normalized = str(value).lower().replace('"', "").replace("::text", "")
        # PostgreSQL adds casts and redundant grouping when reflecting CHECK
        # constraints. Compare the remaining ordered SQL tokens.
        return " ".join(normalized.replace("(", " ").replace(")", " ").split())

    def add_constraint(constraint):
        table_name = constraint.table.name
        name = constraint.name
        inspector = sa.inspect(connection)
        if isinstance(constraint, sa.UniqueConstraint):
            actual = inspector.get_unique_constraints(table_name)
            actual += [i for i in inspector.get_indexes(table_name) if i["unique"]]
            found = next((item for item in actual if item.get("name") == name), None)
            if found is None:
                return original_add_constraint(constraint)
            if found.get("column_names") != [c.name for c in constraint.columns]:
                raise RuntimeError(f"Cannot reconcile unique constraint {name}: incompatible definition")
            print(f"Reconciled existing unique constraint: {name}")
            return
        if isinstance(constraint, sa.CheckConstraint):
            found = next((item for item in inspector.get_check_constraints(table_name) if item.get("name") == name), None)
            if found is None:
                return original_add_constraint(constraint)
            if normalized_sql(found.get("sqltext", "")) != normalized_sql(constraint.sqltext):
                raise RuntimeError(f"Cannot reconcile check constraint {name}: incompatible definition")
            print(f"Reconciled existing check constraint: {name}")
            return
        if isinstance(constraint, sa.ForeignKeyConstraint):
            found = next((item for item in inspector.get_foreign_keys(table_name) if item.get("name") == name), None)
            if found is None:
                return original_add_constraint(constraint)
            expected_cols = [c.name for c in constraint.columns]
            expected_targets = [e.target_fullname for e in constraint.elements]
            actual_targets = [f"{found['referred_table']}.{col}" for col in found["referred_columns"]]
            if found["constrained_columns"] != expected_cols or actual_targets != expected_targets:
                raise RuntimeError(f"Cannot reconcile foreign key {name}: incompatible definition")
            print(f"Reconciled existing foreign key: {name}")
            return
        return original_add_constraint(constraint)

    impl.create_table, impl.add_column, impl.create_index = create_table, add_column, create_index
    impl.add_constraint = add_constraint
