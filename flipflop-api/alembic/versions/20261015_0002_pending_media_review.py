"""Allow saving gallery choices before product approval."""
from alembic import op

revision = "20261015_0002"
down_revision = "20261015_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_bestseller_review_status", "curated_bestseller_reviews", type_="check")
    op.create_check_constraint("ck_bestseller_review_status", "curated_bestseller_reviews",
                               "status IN ('pending', 'approved', 'rejected')")


def downgrade():
    # Refuse to downgrade while pending photo selections exist rather than
    # deleting operator work or silently granting product approval.
    op.drop_constraint("ck_bestseller_review_status", "curated_bestseller_reviews", type_="check")
    op.create_check_constraint("ck_bestseller_review_status", "curated_bestseller_reviews",
                               "status IN ('approved', 'rejected')")
