"""Cross-dialect support shared by the isolated test database."""

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB


@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(_type, _compiler, **_kwargs):
    """SQLite stores test JSONB values as JSON text; production stays JSONB."""
    return "JSON"
